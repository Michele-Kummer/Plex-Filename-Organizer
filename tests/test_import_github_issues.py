"""scripts/import_github_issues.py reads the import plan and the stories file, builds each
issue with its real dates and labels, previews by default, and imports in the planned order,
stopping when GitHub's numbers don't match the plan (US-63). Nothing here contacts GitHub.
Run with: python -m unittest discover -s tests"""

import datetime
import io
import pathlib
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'tools'))
import import_github_issues as gi  # noqa: E402

REPO = 'Owner/project'
CDT = datetime.timezone(datetime.timedelta(hours=-5))

PLAN = """# GitHub import order

| # | Epic | Was | Opened | Closed |
|---|---|---|---|---|
| 1 | Setup | Epic 1 | 2026-10-06 09:00 | 2026-10-06 10:56 (`aaaaaaa`) |
| 2 | Flatten disc rips | Epic 2 | 2026-10-06 09:01 | |

| # | Opened | Closed | Issue | Epic | Labels | State |
|---|---|---|---|---|---|---|
| 3 | 2026-10-06 09:02 | 2026-10-06 10:56 (`aaaaaaa`) | US-01 Install the plugin | Setup | P1 | Closed |
| 4 | 2026-10-06 09:03 | | US-02 Flatten: Flatten folders | Flatten disc rips | P2 | Open, In progress |
| 5 | 2026-10-06 09:04 | 2026-10-07 14:00 (`bbbbbbb`) | BUG-01 Flatten lost a file | | P1, S1 | Closed |
| 6 | 2026-11-03 09:00 | | US-03 Keep named folders | Flatten disc rips | P3 | Open |
| 7 | 2026-11-03 09:01 | | BUG-02 Slow on big folders | | P3, S3 | Open |
"""

BUG_TABLE = """
| Bug | User story | Epic |
|---|---|---|
| BUG-01 | US-02 | Flatten disc rips |
| BUG-02 | | Setup |
"""

STORIES = """# User stories and bugs

<details>
<summary><strong>Epic 1 — Setup</strong> (US-01)</summary>

Install the plugin.

#### US-01 Install the plugin
As a media owner, I want to install it, so that I can use it.

- See [the README](../README.md) and [the case study](case-study.md#top).

**Status:** Done

</details>

<details>
<summary><strong>Epic 2 — Flatten disc rips</strong> (US-02 to US-03)</summary>

Tidy the folders.

#### US-02 Flatten folders
As a media owner, I want flat folders.

**Status:** Partly done. It can lose a file (BUG-01).

#### US-03 Keep named folders
As a media owner, I want named folders kept.

**Status:** Not started

</details>

---

## Part 2 — Bugs

#### BUG-02 Slow on big folders
**Severity:** Low · **Found by:** Michele Kummer · **Affects:** photos

It reads too much.

#### BUG-01 Flatten lost a file
**Found by:** Claude · **Affects:** photos · **Fixed in:** `bbbbbbb`

It overwrote a file.
**Fix:** It never overwrites now.
"""

COMMITS = {'aaaaaaa': datetime.datetime(2026, 10, 6, 10, 56, 3, tzinfo=CDT),
           'bbbbbbb': datetime.datetime(2026, 10, 7, 14, 0, 30, tzinfo=CDT)}


def plan():
    return gi.build_plan(PLAN, STORIES, REPO, commit_time=COMMITS.__getitem__)


class DateTests(unittest.TestCase):

    def test_central_offset_follows_daylight_saving(self):
        self.assertEqual(gi.central_offset(datetime.date(2026, 10, 6)).utcoffset(None), datetime.timedelta(hours=-5))
        self.assertEqual(gi.central_offset(datetime.date(2026, 11, 3)).utcoffset(None), datetime.timedelta(hours=-6))
        self.assertEqual(gi.central_offset(datetime.date(2026, 1, 15)).utcoffset(None), datetime.timedelta(hours=-6))

    def test_parse_local_time(self):
        self.assertEqual(gi.iso(gi.parse_local_time('2026-11-15 00:08')), '2026-11-15T00:08:00-06:00')


class PlanTests(unittest.TestCase):

    def test_reads_epics_stories_and_bugs_in_number_order(self):
        items = plan()
        self.assertEqual([i['number'] for i in items], [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual([i['kind'] for i in items], ['epic', 'epic', 'story', 'story', 'bug', 'story', 'bug'])
        self.assertEqual(items[3]['epic'], 'Flatten disc rips')

    def test_payload_keeps_real_dates_and_state(self):
        items = {i['id']: i for i in plan()}
        closed = items['US-01']['payload']['issue']
        self.assertEqual(closed['created_at'], '2026-10-06T09:02:00-05:00')
        self.assertEqual(closed['closed_at'], '2026-10-06T10:56:03-05:00')
        self.assertTrue(closed['closed'])
        still_open = items['US-03']['payload']['issue']
        self.assertFalse(still_open['closed'])
        self.assertNotIn('closed_at', still_open)
        self.assertEqual(still_open['created_at'], '2026-11-03T09:00:00-06:00')

    def test_labels(self):
        items = {i['id']: i for i in plan()}
        self.assertEqual(items['Setup']['labels_full'], ['epic', 'Setup'])
        self.assertEqual(items['US-02']['labels_full'], ['user story', 'Flatten disc rips', 'P2: High', 'In progress'])
        self.assertEqual(items['BUG-01']['labels_full'], ['bug', 'P1: Critical', 'S1: Blocker', 'Found by: Claude'])
        self.assertEqual(items['BUG-02']['labels_full'],
                         ['bug', 'P3: Medium', 'S3: Minor', 'Found by: Michele Kummer'])

    def test_a_bug_whose_finder_is_to_be_confirmed(self):
        stories = STORIES.replace('**Found by:** Claude', '**Found by:** to confirm')
        items = {i['id']: i for i in gi.build_plan(PLAN, stories, REPO, commit_time=COMMITS.__getitem__)}
        self.assertIn('Found by: To confirm', items['BUG-01']['labels_full'])
        self.assertIn('Found 2026-10-06. Who found it is still to be confirmed. Closed by bbbbbbb.',
                      items['BUG-01']['body'])

    def test_a_bug_found_by_someone_unknown_is_refused(self):
        stories = STORIES.replace('**Found by:** Claude', '**Found by:** Someone else')
        with self.assertRaisesRegex(gi.PlanError, 'not one of the found-by labels'):
            gi.build_plan(PLAN, stories, REPO, commit_time=COMMITS.__getitem__)

    def test_epic_labels_drop_commas_github_does_not_allow(self):
        self.assertEqual(gi.label_name('Workflow, safety and record-keeping'), 'Workflow safety and record-keeping')
        self.assertEqual(gi.label_name('Flatten disc rips'), 'Flatten disc rips')

    def test_closing_before_opening_is_refused(self):
        early = PLAN.replace('| 3 | 2026-10-06 09:02 |', '| 3 | 2026-10-06 11:30 |')
        with self.assertRaisesRegex(gi.PlanError, 'closes before it opens'):
            gi.build_plan(early, STORIES, REPO, commit_time=COMMITS.__getitem__)

    def test_a_story_missing_from_the_plan_is_refused(self):
        short = '\n'.join(line for line in PLAN.splitlines() if 'US-03' not in line)
        short = short.replace('| 7 |', '| 6 |')
        with self.assertRaisesRegex(gi.PlanError, 'Not in the plan: US-03'):
            gi.build_plan(short, STORIES, REPO, commit_time=COMMITS.__getitem__)

    def test_gaps_in_numbers_are_refused(self):
        with self.assertRaisesRegex(gi.PlanError, 'no gaps'):
            gi.build_plan(PLAN.replace('| 7 |', '| 8 |'), STORIES, REPO, commit_time=COMMITS.__getitem__)


class BodyTests(unittest.TestCase):

    def test_story_body_names_epic_and_dates(self):
        body = {i['id']: i for i in plan()}['US-01']['body']
        self.assertTrue(body.startswith('**Epic:** Setup (#1)'))
        self.assertIn('As a media owner, I want to install it', body)
        self.assertIn('Imported from docs/user-stories-and-bugs.md, where it is US-01. Built 2026-10-06. '
                      'Closed by aaaaaaa.', body)

    def test_titles_leave_out_the_old_numbers_and_keep_the_area(self):
        titles = [i['title'] for i in plan()]
        self.assertEqual(titles, ['Epic: Setup', 'Epic: Flatten disc rips', 'Install the plugin',
                                  'Flatten: Flatten folders', 'Flatten lost a file', 'Keep named folders',
                                  'Slow on big folders'])

    def test_not_started_story_says_asked_for(self):
        self.assertIn('Asked for 2026-11-03.', {i['id']: i for i in plan()}['US-03']['body'])

    def test_bug_body_says_who_found_it_and_links_the_commit(self):
        body = {i['id']: i for i in plan()}['BUG-01']['body']
        self.assertIn('Found 2026-10-06 by Claude. Closed by bbbbbbb.', body)
        self.assertIn('**Fixed in:** bbbbbbb', body)
        self.assertIn('**Fix:** It never overwrites now.', body)

    def test_references_link_to_their_issues(self):
        body = {i['id']: i for i in plan()}['US-02']['body']
        self.assertIn('It can lose a file (BUG-01 (#5)).', body)

    def test_relative_links_point_at_github(self):
        body = {i['id']: i for i in plan()}['US-01']['body']
        self.assertIn('[the README](https://github.com/Owner/project/blob/main/README.md)', body)
        self.assertIn('[the case study](https://github.com/Owner/project/blob/main/docs/case-study.md#top)', body)

    def test_epic_body_lists_its_stories(self):
        body = {i['id']: i for i in plan()}['Flatten disc rips']['body']
        self.assertIn('Tidy the folders.', body)
        self.assertIn('- #4 Flatten: Flatten folders\n- #6 Keep named folders', body)


def plan_with_bugs(table=BUG_TABLE):
    return gi.build_plan(PLAN + table, STORIES, REPO, commit_time=COMMITS.__getitem__)


class BugLinkTests(unittest.TestCase):

    def test_a_bug_names_its_epic_and_user_story(self):
        items = {i['id']: i for i in plan_with_bugs()}
        self.assertTrue(items['BUG-01']['body'].startswith(
            '**Epic:** Flatten disc rips (#2) · **User story:** Flatten: Flatten folders (#4)\n\n'))
        self.assertTrue(items['BUG-02']['body'].startswith('**Epic:** Setup (#1)\n\n'))
        self.assertNotIn('User story:', items['BUG-02']['body'])

    def test_a_bug_gets_its_epic_label(self):
        items = {i['id']: i for i in plan_with_bugs()}
        self.assertEqual(items['BUG-01']['labels_full'],
                         ['bug', 'Flatten disc rips', 'P1: Critical', 'S1: Blocker', 'Found by: Claude'])

    def test_an_epic_lists_its_stories_and_bugs(self):
        body = {i['id']: i for i in plan_with_bugs()}['Flatten disc rips']['body']
        self.assertIn('**User stories**\n\n- #4 Flatten: Flatten folders\n- #6 Keep named folders', body)
        self.assertIn('**Bugs**\n\n- #5 Flatten lost a file', body)
        self.assertNotIn('Slow on big folders', body)

    def test_bugs_are_linked_under_their_epics(self):
        github = FakeGitHub()
        gi.apply(plan_with_bugs(), github, log=quiet, sleep=quiet)
        self.assertEqual(sorted(github.links), [(1, 1003), (1, 1007), (2, 1004), (2, 1005), (2, 1006)])

    def test_a_bug_missing_from_the_table_is_refused(self):
        table = '\n'.join(line for line in BUG_TABLE.splitlines() if 'BUG-02' not in line)
        with self.assertRaisesRegex(gi.PlanError, 'BUG-02 is not in the bugs and stories table'):
            plan_with_bugs(table)

    def test_an_epic_that_does_not_match_the_story_is_refused(self):
        with self.assertRaisesRegex(gi.PlanError, 'BUG-01 is under "Setup", but US-02'):
            plan_with_bugs(BUG_TABLE.replace('| US-02 | Flatten disc rips |', '| US-02 | Setup |'))

    def test_an_unknown_story_is_refused(self):
        with self.assertRaisesRegex(gi.PlanError, 'BUG-01 names US-99'):
            plan_with_bugs(BUG_TABLE.replace('US-02', 'US-99'))


class FakeGitHub:
    """Stands in for gh: records calls and numbers issues the way GitHub would."""

    def __init__(self, existing=None, skip_number=False):
        self.issues = dict(existing or {})
        self.labels = {'bug'}
        self.created_labels, self.imported, self.links = [], [], []
        self.types = {}
        self.pending = {}
        self.skip_number = skip_number

    def existing_issues(self):
        return dict(self.issues)

    def label_names(self):
        return set(self.labels)

    def create_label(self, name, color, description):
        self.created_labels.append(name)
        self.labels.add(name)

    def start_import(self, payload):
        import_id = len(self.pending) + 1
        self.pending[import_id] = payload
        return {'id': import_id, 'status': 'pending'}

    def import_status(self, import_id):
        number = max(self.issues, default=0) + (2 if self.skip_number else 1)
        self.issues[number] = self.pending[import_id]['issue']['title']
        self.imported.append(number)
        return {'id': import_id, 'status': 'imported',
                'issue_url': f'https://api.github.com/repos/{REPO}/issues/{number}'}

    def issue_id(self, number):
        return 1000 + number

    def sub_issue_numbers(self, number):
        return {child - 1000 for parent, child in self.links if parent == number}

    def set_type(self, number, issue_type):
        self.types[number] = issue_type

    def add_sub_issue(self, parent, child_id):
        self.links.append((parent, child_id))


def quiet(*args):
    pass


class ApplyTests(unittest.TestCase):

    def test_imports_in_order_creates_missing_labels_and_links_stories(self):
        github = FakeGitHub()
        gi.apply(plan(), github, log=quiet, sleep=quiet)
        self.assertEqual(github.imported, [1, 2, 3, 4, 5, 6, 7])
        self.assertIn('Flatten disc rips', github.created_labels)
        self.assertIn('In progress', github.created_labels)
        self.assertIn('Found by: Claude', github.created_labels)
        self.assertNotIn('Found by: Automated tests', github.created_labels)
        self.assertNotIn('bug', github.created_labels)
        self.assertNotIn('S4: Trivial', github.created_labels)
        self.assertEqual(sorted(github.links), [(1, 1003), (2, 1004), (2, 1006)])
        self.assertEqual(github.types, {3: 'Feature', 4: 'Feature', 5: 'Bug', 6: 'Feature', 7: 'Bug'})

    def test_a_rerun_skips_what_is_already_there(self):
        items = plan()
        github = FakeGitHub(existing={1: items[0]['title'], 2: items[1]['title'], 3: items[2]['title']})
        gi.apply(items, github, log=quiet, sleep=quiet)
        self.assertEqual(github.imported, [4, 5, 6, 7])

    def test_limit_imports_only_the_first_issues(self):
        github = FakeGitHub()
        gi.apply(plan(), github, log=quiet, sleep=quiet, limit=4)
        self.assertEqual(github.imported, [1, 2, 3, 4])
        self.assertEqual(sorted(github.links), [(1, 1003), (2, 1004)])

    def test_stops_when_an_existing_issue_is_not_the_planned_one(self):
        github = FakeGitHub(existing={1: 'Some other issue'})
        with self.assertRaisesRegex(gi.PlanError, 'Nothing was imported'):
            gi.apply(plan(), github, log=quiet, sleep=quiet)
        self.assertEqual(github.imported, [])

    def test_stops_when_github_gives_an_unplanned_number(self):
        github = FakeGitHub(skip_number=True)
        with self.assertRaisesRegex(gi.PlanError, 'became #2, not #1'):
            gi.apply(plan(), github, log=quiet, sleep=quiet)
        self.assertEqual(github.imported, [2])

    def test_preview_changes_nothing_and_says_so(self):
        out = io.StringIO()
        with redirect_stdout(out):
            gi.preview(plan())
        text = out.getvalue()
        self.assertIn('WOULD IMPORT #5 Flatten lost a file', text)
        self.assertIn('7 issues: 2 epics, 3 user stories, 2 bugs (3 closed after import)', text)
        self.assertIn('DRY RUN: nothing was changed.', text)


@unittest.skipUnless(gi.ORDER_FILE.exists(), 'the local import plan is not on this computer')
class RealPlanTests(unittest.TestCase):

    def test_the_real_plan_matches_the_stories_file(self):
        items = gi.build_plan(gi.ORDER_FILE.read_text(encoding='utf-8'),
                              gi.STORIES_FILE.read_text(encoding='utf-8'), gi.DEFAULT_REPO)
        kinds = [i['kind'] for i in items]
        self.assertEqual(kinds.count('epic'), 8)
        self.assertEqual(len(items), len(set(i['id'] for i in items)))


if __name__ == '__main__':
    unittest.main()
