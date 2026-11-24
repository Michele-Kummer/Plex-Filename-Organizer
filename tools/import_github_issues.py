"""Import the epics, user stories and bugs into GitHub Issues, with their real dates (US-63).

The order, dates, labels and states come from docs/github-import-order.md (a local plan,
not pushed). The text of each issue comes from docs/user-stories-and-bugs.md.

It uses GitHub's Issue Import API, which keeps each issue's real opened and closed dates,
and the GitHub CLI (gh), which must be signed in.

Previews by default. Nothing is created unless --apply is given.

    py tools/import_github_issues.py                 preview every issue
    py tools/import_github_issues.py --show US-04    print the text of one issue
    py tools/import_github_issues.py --apply         create the labels and issues
    py tools/import_github_issues.py --apply --repo OWNER/test --limit 20
                                                       try the first 20 on a test repository
"""

import argparse
import datetime
import json
import pathlib
import posixpath
import re
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
ORDER_FILE = ROOT / 'docs' / 'github-import-order.md'
STORIES_FILE = ROOT / 'docs' / 'user-stories-and-bugs.md'
DEFAULT_REPO = 'Michele-Kummer/Plex-Filename-Organizer'
IMPORT_ACCEPT = 'application/vnd.github.golden-comet-preview+json'

PRIORITY = {'P1': 'P1: Critical', 'P2': 'P2: High', 'P3': 'P3: Medium', 'P4': 'P4: Low'}
SEVERITY = {'S1': 'S1: Blocker', 'S2': 'S2: Major', 'S3': 'S3: Minor', 'S4': 'S4: Trivial'}
ISSUE_TYPES = {'story': 'Feature', 'bug': 'Bug'}   # GitHub issue types, so the type filters work
FOUND_BY = ('Michele Kummer', 'Claude', 'Automated tests', 'To confirm')

# The Epic column in the plan uses short names
EPIC_SHORT_NAMES = {
    'Setup': 'Setup',
    'Safe changes': 'Safe changes',
    'Flatten disc rips': 'Flatten disc rips',
    'Name episodes': 'Name episodes from the guide',
    'Check names': 'Check names across the TV library',
    'Movies': 'Movies',
    'Plugin': 'Claude Code plugin',
    'Maintenance': 'Maintenance',
}

# Labels the script creates when they are missing: name -> (color, description).
# Epics are found through sub-issues and progress through the board's Status, so there are
# no epic-name or In progress labels.
BASE_LABELS = {
    'epic': ('8250DF', 'High-level initiative or feature set broken down into user stories'),
    'user story': ('0969DA', "End-user requirement written from the user's perspective"),
    'bug': ('D73A4A', 'Defect, error, or unexpected behavior'),
    **{name: ('EDEDED', '') for name in PRIORITY.values()},
    **{name: ('EDEDED', '') for name in SEVERITY.values()},
    **{f'Found by: {who}': ('C5DEF5', f'Bug found by {who}') for who in FOUND_BY},
}


class PlanError(Exception):
    """The plan or the stories file is not what the script expects."""


# ---------------------------------------------------------------- dates

def _nth_sunday(year, month, n):
    day = datetime.date(year, month, 1)
    day += datetime.timedelta(days=(6 - day.weekday()) % 7)
    return day + datetime.timedelta(weeks=n - 1)


def central_offset(day):
    """US Central time offset on a date: -05:00 in daylight saving time, else -06:00."""
    if _nth_sunday(day.year, 3, 2) <= day < _nth_sunday(day.year, 11, 1):
        return datetime.timezone(datetime.timedelta(hours=-5))
    return datetime.timezone(datetime.timedelta(hours=-6))


def parse_local_time(text):
    """'2026-10-06 09:07' in Central time -> aware datetime."""
    naive = datetime.datetime.strptime(text.strip(), '%Y-%m-%d %H:%M')
    return naive.replace(tzinfo=central_offset(naive.date()))


def git_commit_time(commit):
    """The author time of a commit, as in the plan's Closed column."""
    out = subprocess.run(['git', '-C', str(ROOT), 'log', '-1', '--format=%aI', commit],
                         capture_output=True, text=True, check=True).stdout.strip()
    if not out:
        raise PlanError(f'Commit {commit} is not in the git history')
    return datetime.datetime.fromisoformat(out)


def iso(moment):
    return moment.isoformat(timespec='seconds')


# ---------------------------------------------------------------- reading the files

def _cells(line):
    return [cell.strip() for cell in line.strip().strip('|').split('|')]


def parse_plan(text, commit_time=git_commit_time):
    """Read the epics table and the timeline from the import plan, in issue number order."""
    items = []
    for line in text.splitlines():
        if not re.match(r'\| \d+ \|', line):
            continue
        cells = _cells(line)
        if len(cells) == 5:        # epics table: # | Epic | Was | Opened | Closed
            number, name, _was, opened, closed = cells
            item = {'number': int(number), 'kind': 'epic', 'id': name, 'title': f'Epic: {name}',
                    'epic': name, 'labels': [], 'state': 'Closed' if closed else 'Open'}
        elif len(cells) == 7:      # timeline: # | Opened | Closed | Issue | Epic | Labels | State
            number, opened, closed, issue, epic, labels, state = cells
            if issue.startswith('Epic: '):
                name = issue[len('Epic: '):]
                item = {'number': int(number), 'kind': 'epic', 'id': name, 'title': issue,
                        'epic': name, 'labels': [], 'state': state}
            else:
                match = re.match(r'((US|BUG)-\d+) (.+)$', issue)
                if not match:
                    raise PlanError(f'Cannot read the issue in: {line}')
                kind = 'story' if match.group(2) == 'US' else 'bug'
                epic_name = EPIC_SHORT_NAMES.get(epic, epic) if epic else None
                if epic and epic not in EPIC_SHORT_NAMES:
                    raise PlanError(f'Unknown epic "{epic}" in: {line}')
                item = {'number': int(number), 'kind': kind, 'id': match.group(1), 'title': match.group(3),
                        'epic': epic_name, 'labels': [x.strip() for x in labels.split(',') if x.strip()],
                        'state': state}
        else:
            continue
        item['opened'] = parse_local_time(opened)
        commit = re.search(r'`([0-9a-f]{7,40})`', closed)
        item['commit'] = commit.group(1) if commit else None
        item['closed'] = commit_time(item['commit']) if commit else None
        items.append(item)
    items.sort(key=lambda i: i['number'])
    return items


def parse_stories(text):
    """Read the epics and every US and BUG section from the stories file."""
    epics, sections = {}, {}
    lines = text.splitlines()
    current_epic = None
    i = 0
    while i < len(lines):
        line = lines[i]
        summary = re.match(r'<summary><strong>Epic \d+ — (.+?)</strong>', line)
        if summary:
            current_epic = summary.group(1)
            body = []
            i += 1
            while i < len(lines) and not lines[i].startswith('#### ') and lines[i] != '</details>':
                body.append(lines[i])
                i += 1
            epics[current_epic] = '\n'.join(body).strip()
            continue
        heading = re.match(r'#### ((US|BUG)-\d+) (.+)$', line)
        if heading:
            body = []
            i += 1
            while i < len(lines) and not re.match(r'(#### |</details>|## |---$)', lines[i]):
                body.append(lines[i])
                i += 1
            sections[heading.group(1)] = {'title': heading.group(3), 'body': '\n'.join(body).strip(),
                                          'epic': current_epic if heading.group(2) == 'US' else None}
            continue
        if line.startswith('## Part 2'):
            current_epic = None
        i += 1
    return epics, sections


# ---------------------------------------------------------------- issue text

def rewrite_links(text, repo, branch='main', base='docs'):
    """Point relative links in the stories file at the files on GitHub."""
    def fix(match):
        target = match.group(2)
        if re.match(r'[a-z]+:|#', target):
            return match.group(0)
        path = posixpath.normpath(posixpath.join(base, target))
        return f'{match.group(1)}(https://github.com/{repo}/blob/{branch}/{path})'
    return re.sub(r'(\[[^\]]+\])\(([^)\s]+)\)', fix, text)


def link_references(text, numbers):
    """'BUG-02' -> 'BUG-02 (#57)', and `1111480` -> 1111480 so GitHub links the commit."""
    def ref(match):
        number = numbers.get(match.group(0))
        return f'{match.group(0)} (#{number})' if number else match.group(0)
    text = re.sub(r'\b(?:US|BUG)-\d+\b', ref, text)
    return re.sub(r'`([0-9a-f]{7,40})`', r'\1', text)


def found_by(body):
    match = re.search(r'\*\*Found by:\*\* ([^·\n]+)', body)
    return match.group(1).strip() if match else None


def build_body(item, epics, sections, numbers, epic_numbers, repo, titles=None, epic_of=None):
    when = item['opened'].strftime('%Y-%m-%d')
    titles = titles or {}
    epic_of = epic_of or {sid: s['epic'] for sid, s in sections.items()}
    if item['kind'] == 'epic':
        text = epics.get(item['epic'])
        if text is None:
            raise PlanError(f'Epic "{item["epic"]}" is not in the stories file')
        children = {'story': [], 'bug': []}
        for sid, number in sorted(numbers.items(), key=lambda kv: kv[1]):
            kind = 'story' if sid.startswith('US-') else 'bug'
            if epic_of.get(sid) == item['epic']:
                children[kind].append(f'- #{number} {titles.get(sid, sections[sid]["title"])}')
        parts = [text] + [f'**{heading}**\n\n' + '\n'.join(children[kind])
                          for kind, heading in (('story', 'User stories'), ('bug', 'Bugs')) if children[kind]]
        source = f'Planned {when}.'
    else:
        section = sections.get(item['id'])
        if section is None:
            raise PlanError(f'{item["id"]} is not in the stories file')
        parts = []
        if item['kind'] == 'story':
            parts.append(f'**Epic:** {item["epic"]} (#{epic_numbers[item["epic"]]})')
            not_started = '**Status:** Not started' in section['body']
            source = f'{"Asked for" if not_started else "Built"} {when}.'
        else:
            who = found_by(section['body'])
            if who and who.lower() == 'to confirm':
                source = f'Found {when}. Who found it is still to be confirmed.'
            else:
                source = f'Found {when}' + (f' by {who}.' if who else '.')
            header = []
            if item.get('epic'):
                header.append(f'**Epic:** {item["epic"]} (#{epic_numbers[item["epic"]]})')
            if item.get('story'):
                header.append(f'**User story:** {titles[item["story"]]} (#{numbers[item["story"]]})')
            if header:
                parts.append(' · '.join(header))
        parts.append(section['body'])
    if item['commit']:
        source += f' Closed by {item["commit"]}.'
    source = link_references(source, numbers)
    body = link_references(rewrite_links('\n\n'.join(p for p in parts if p), repo), numbers)
    # The old number goes in last, so it is not linked to the issue itself
    where = '' if item['kind'] == 'epic' else f', where it is {item["id"]}'
    return f'{body}\n\n---\n<sub>Imported from docs/user-stories-and-bugs.md{where}. {source}</sub>'


def labels_for(item):
    labels = {'epic': ['epic'], 'story': ['user story'], 'bug': ['bug']}[item['kind']]
    for code in item['labels']:
        table = PRIORITY if code.startswith('P') else SEVERITY
        if code not in table:
            raise PlanError(f'Unknown label "{code}" on {item["title"]}')
        labels.append(table[code])
    if item['kind'] == 'bug':
        labels.append(found_by_label(item.get('found_by')))
    return labels


def found_by_label(who):
    # The stories file writes 'to confirm' in lower case
    who = next((name for name in FOUND_BY if who and name.lower() == who.lower()), who)
    if who not in FOUND_BY:
        raise PlanError(f'"{who}" is not one of the found-by labels: {", ".join(FOUND_BY)}')
    return f'Found by: {who}'


def build_plan(plan_text, stories_text, repo, commit_time=git_commit_time):
    items = parse_plan(plan_text, commit_time)
    epics, sections = parse_stories(stories_text)
    validate(items, sections)
    attach_bugs(items, parse_bug_links(plan_text), sections)
    numbers = {i['id']: i['number'] for i in items if i['kind'] != 'epic'}
    epic_numbers = {i['epic']: i['number'] for i in items if i['kind'] == 'epic'}
    titles = {i['id']: i['title'] for i in items if i['kind'] != 'epic'}
    epic_of = {i['id']: i['epic'] for i in items if i['kind'] != 'epic'}
    for item in items:
        if item['kind'] == 'bug':
            item['found_by'] = found_by(sections[item['id']]['body'])
        item['labels_full'] = labels_for(item)
        item['issue_type'] = ISSUE_TYPES.get(item['kind'])
        item['body'] = build_body(item, epics, sections, numbers, epic_numbers, repo, titles, epic_of)
        item['payload'] = {'issue': {
            'title': item['title'], 'body': item['body'], 'created_at': iso(item['opened']),
            'closed': item['state'] == 'Closed', 'labels': item['labels_full']}}
        if item['state'] == 'Closed':
            item['payload']['issue']['closed_at'] = iso(item['closed'])
            item['payload']['issue']['updated_at'] = iso(item['closed'])
    return items


def parse_bug_links(text):
    """The plan's 'Bugs and their stories' table: bug id -> (story id or None, epic short name)."""
    links = {}
    for line in text.splitlines():
        if re.match(r'\| BUG-\d+ \|', line):
            bug, story, epic = (_cells(line) + ['', ''])[:3]
            links[bug] = (story or None, epic or None)
    return links


def attach_bugs(items, links, sections):
    """Give each bug its user story and epic. Without the table, bugs keep no epic."""
    if not links:
        return
    story_epic = {i['id']: i['epic'] for i in items if i['kind'] == 'story'}
    problems = []
    for item in items:
        if item['kind'] != 'bug':
            continue
        if item['id'] not in links:
            problems.append(f'{item["id"]} is not in the bugs and stories table')
            continue
        story, epic = links[item['id']]
        if story and story not in story_epic:
            problems.append(f'{item["id"]} names {story}, which is not in the plan')
            continue
        named_epic = EPIC_SHORT_NAMES.get(epic) if epic else None
        if epic and not named_epic:
            problems.append(f'{item["id"]} names an unknown epic "{epic}"')
            continue
        if story and named_epic and named_epic != story_epic[story]:
            problems.append(f'{item["id"]} is under "{named_epic}", but {story} is under "{story_epic[story]}"')
            continue
        item['story'] = story
        item['epic'] = story_epic[story] if story else named_epic
        if not item['epic']:
            problems.append(f'{item["id"]} has no user story and no epic')
    if problems:
        raise PlanError('\n'.join(problems))


def validate(items, sections):
    problems = []
    numbers = [i['number'] for i in items]
    if numbers != list(range(1, len(items) + 1)):
        problems.append('Issue numbers are not 1, 2, 3 ... with no gaps or repeats')
    seen = set()
    for item in items:
        if item['id'] in seen:
            problems.append(f'{item["id"]} is in the plan twice')
        seen.add(item['id'])
        if item['state'] == 'Closed' and not item['closed']:
            problems.append(f'{item["title"]} is closed but has no closing commit')
        if item['state'] != 'Closed' and item['closed']:
            problems.append(f'{item["title"]} is open but has a closing commit')
        if item['closed'] and item['closed'] <= item['opened']:
            problems.append(f'{item["title"]} closes before it opens')
        if item['kind'] == 'story' and item['epic'] is None:
            problems.append(f'{item["title"]} has no epic')
        if item['kind'] != 'epic' and item['id'] not in sections:
            problems.append(f'{item["id"]} is not in the stories file')
    missing = sorted(set(sections) - seen, key=lambda s: (s[0], int(s.split('-')[1])))
    if missing:
        problems.append('Not in the plan: ' + ', '.join(missing))
    if problems:
        raise PlanError('\n'.join(problems))


# ---------------------------------------------------------------- GitHub

def find_gh():
    found = shutil.which('gh')
    if found:
        return found
    for path in (r'C:\Program Files\GitHub CLI\gh.exe',):
        if pathlib.Path(path).exists():
            return path
    raise PlanError('The GitHub CLI (gh) is not installed. Install it and run: gh auth login')


class GitHub:
    """Calls the GitHub REST API through the gh CLI."""

    def __init__(self, repo, gh=None):
        self.repo = repo
        self.gh = gh or find_gh()

    def api(self, path, method='GET', data=None, accept=None, paginate=False):
        cmd = [self.gh, 'api', path.format(repo=self.repo), '-X', method]
        if accept:
            cmd += ['-H', f'Accept: {accept}']
        if paginate:
            cmd += ['--paginate', '--slurp']
        if data is not None:
            cmd += ['--input', '-']
        run = subprocess.run(cmd, input=json.dumps(data) if data is not None else None,
                             capture_output=True, text=True, encoding='utf-8')
        if run.returncode != 0:
            raise RuntimeError(f'gh api {method} {path} failed: {run.stdout.strip()} {run.stderr.strip()}'.strip())
        result = json.loads(run.stdout) if run.stdout.strip() else None
        if paginate and isinstance(result, list):
            result = [entry for page in result for entry in page]
        return result

    def existing_issues(self):
        """Every issue and pull request: number -> title."""
        found = self.api('repos/{repo}/issues?state=all&per_page=100', paginate=True) or []
        return {entry['number']: entry['title'] for entry in found}

    def label_names(self):
        return {entry['name'] for entry in self.api('repos/{repo}/labels?per_page=100', paginate=True) or []}

    def create_label(self, name, color, description):
        self.api('repos/{repo}/labels', 'POST', {'name': name, 'color': color, 'description': description})

    def start_import(self, payload):
        return self.api('repos/{repo}/import/issues', 'POST', payload, accept=IMPORT_ACCEPT)

    def import_status(self, import_id):
        return self.api(f'repos/{{repo}}/import/issues/{import_id}', accept=IMPORT_ACCEPT)

    def issue_id(self, number):
        return self.api(f'repos/{{repo}}/issues/{number}')['id']

    def sub_issue_numbers(self, number):
        return {entry['number'] for entry in self.api(f'repos/{{repo}}/issues/{number}/sub_issues?per_page=100',
                                                      paginate=True) or []}

    def set_type(self, number, issue_type):
        self.api(f'repos/{{repo}}/issues/{number}', 'PATCH', {'type': issue_type})

    def add_sub_issue(self, parent, child_id):
        self.api(f'repos/{{repo}}/issues/{parent}/sub_issues', 'POST', {'sub_issue_id': child_id})


def wanted_labels(items):
    used = {label for i in items for label in i['labels_full']}
    return {name: value for name, value in BASE_LABELS.items() if name in used}


def check_existing(items, existing):
    """Which planned issues already exist. Stops if GitHub's numbers don't match the plan."""
    by_number = {item['number']: item for item in items}
    for number, title in sorted(existing.items()):
        planned = by_number.get(number)
        if planned is None or planned['title'] != title:
            expected = f'"{planned["title"]}"' if planned else 'nothing'
            raise PlanError(f'#{number} on GitHub is "{title}", but the plan has {expected} there. '
                            'Nothing was imported.')
    if sorted(existing) != list(range(1, len(existing) + 1)):
        raise PlanError('The issues already on GitHub are not numbered 1, 2, 3 ... with no gaps, so new issues '
                        'would not get the planned numbers. Nothing was imported.')
    return set(existing)


def import_issue(github, item, wait=1.0, timeout=120, sleep=time.sleep, log=print):
    started = github.start_import(item['payload'])
    deadline = timeout
    status = started
    while status.get('status') == 'pending':
        if deadline <= 0:
            raise RuntimeError(f'Import of {item["title"]} was still pending after {timeout} seconds')
        sleep(wait)
        deadline -= wait
        status = github.import_status(started['id'])
    if status.get('status') != 'imported':
        raise RuntimeError(f'Import of {item["title"]} failed: {json.dumps(status.get("errors") or status)}')
    number = int(status['issue_url'].rstrip('/').rsplit('/', 1)[1])
    if number != item['number']:
        raise PlanError(f'{item["title"]} became #{number}, not #{item["number"]} as planned. Stopped, so the '
                        'numbers after it stay correct. Check the repository before running again.')
    log(f'IMPORTED #{number} {item["title"]}')
    return number


def apply(items, github, log=print, sleep=time.sleep, limit=None):
    if limit:
        items = [item for item in items if item['number'] <= limit]
    existing = github.existing_issues()
    done = check_existing(items, existing)
    have = github.label_names()
    for name, (color, description) in wanted_labels(items).items():
        if name not in have:
            github.create_label(name, color, description)
            log(f'CREATED LABEL {name}')
    for item in items:
        if item['number'] in done:
            log(f'ALREADY THERE #{item["number"]} {item["title"]}')
            continue
        import_issue(github, item, sleep=sleep, log=log)
        if item['issue_type']:
            # The Import API cannot set an issue type, so it is set straight after
            github.set_type(item['number'], item['issue_type'])
    epic_numbers = {i['epic']: i['number'] for i in items if i['kind'] == 'epic'}
    linked = {number: github.sub_issue_numbers(number) for number in epic_numbers.values()}
    for item in items:
        if item['kind'] == 'epic':
            continue
        parent = epic_numbers.get(item.get('epic'))
        if parent is None or item['number'] in linked[parent]:
            continue
        github.add_sub_issue(parent, github.issue_id(item['number']))
        log(f'LINKED #{item["number"]} {item["id"]} under epic #{parent}')
    log(f'Done: {len(items) - len(done)} issues imported, {len(done)} already there.')


def preview(items, log=print):
    for item in items:
        closed = f'closed {iso(item["closed"])}' if item['closed'] else 'open'
        log(f'WOULD IMPORT #{item["number"]} {item["title"]}\n'
            f'    opened {iso(item["opened"])}, {closed}\n'
            f'    labels: {", ".join(item["labels_full"])}')
    kinds = {k: sum(1 for i in items if i['kind'] == k) for k in ('epic', 'story', 'bug')}
    log(f'\n{len(items)} issues: {kinds["epic"]} epics, {kinds["story"]} user stories, {kinds["bug"]} bugs '
        f'({sum(1 for i in items if i["state"] == "Closed")} closed after import). '
        f'Each story and bug is linked to its epic as a sub-issue.')
    log('DRY RUN: nothing was changed. Run the same command again with --apply to make these changes.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--apply', action='store_true', help='create the labels and issues on GitHub')
    parser.add_argument('--repo', default=DEFAULT_REPO, help=f'OWNER/NAME (default {DEFAULT_REPO})')
    parser.add_argument('--limit', type=int, metavar='N', help='import only issues #1 to #N, to try it out')
    parser.add_argument('--show', metavar='ID', help='print the text of one issue, such as US-04 or BUG-02')
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        if not ORDER_FILE.exists():
            raise PlanError(f'{ORDER_FILE} is missing. It is the local import plan and is not in the repository.')
        items = build_plan(ORDER_FILE.read_text(encoding='utf-8'), STORIES_FILE.read_text(encoding='utf-8'),
                           args.repo)
        if args.show:
            match = [i for i in items if i['id'].lower() == args.show.lower()
                     or i['title'].lower() == args.show.lower()]
            if not match:
                raise PlanError(f'{args.show} is not in the plan')
            print(f'#{match[0]["number"]} {match[0]["title"]}\n\n{match[0]["body"]}')
            return 0
        if args.apply:
            apply(items, GitHub(args.repo), limit=args.limit)
        else:
            preview([item for item in items if not args.limit or item['number'] <= args.limit])
        return 0
    except (PlanError, RuntimeError) as error:
        print(f'STOPPED: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
