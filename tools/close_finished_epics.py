"""Close an issue's epic once every story and bug under it is closed.

GitHub's Actions workflow .github/workflows/close-epics.yml runs this each time an issue is
closed. It looks up the closed issue's parent issue (its epic). When the epic is still open
and all of its sub-issues are closed, it closes the epic as completed, with a comment saying
why. It then does the same for that epic's own parent, if it has one.

It uses the GitHub CLI (gh), signed in, or given a token in GH_TOKEN.

Previews by default. Nothing is closed unless --apply is given.

    py tools/close_finished_epics.py --issue 116              preview
    py tools/close_finished_epics.py --issue 116 --apply      close the epic if it is done
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

DEFAULT_REPO = 'Michele-Kummer/Plex-Filename-Organizer'
COMMENT = 'All {total} of its stories and bugs are closed, so this epic is closed too.'

PARENT_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    issue(number: $number) {
      parent {
        number
        title
        state
        subIssuesSummary { total completed }
      }
    }
  }
}
"""


def find_gh():
    """The gh command, or its usual Windows install path when it isn't on PATH."""
    found = shutil.which('gh')
    if found:
        return found
    windows = r'C:\Program Files\GitHub CLI\gh.exe'
    return windows if os.path.exists(windows) else 'gh'


def run_gh(args):
    """Run gh with these arguments and return its output. Stops on an error."""
    result = subprocess.run([find_gh()] + args, capture_output=True, text=True, encoding='utf-8')
    if result.returncode != 0:
        raise RuntimeError(f'gh {" ".join(args[:2])} failed: {result.stderr.strip()}')
    return result.stdout


def get_parent(repo, number, gh=run_gh):
    """The parent issue of issue NUMBER as a dict (number, title, state, total, completed),
    or None when it has no parent."""
    owner, name = repo.split('/', 1)
    out = gh(['api', 'graphql', '-f', f'query={PARENT_QUERY}', '-f', f'owner={owner}',
              '-f', f'name={name}', '-F', f'number={number}'])
    issue = (json.loads(out).get('data') or {}).get('repository', {}).get('issue')
    parent = (issue or {}).get('parent')
    if not parent:
        return None
    summary = parent.get('subIssuesSummary') or {}
    return {'number': parent['number'], 'title': parent['title'], 'state': parent['state'],
            'total': summary.get('total', 0), 'completed': summary.get('completed', 0)}


def is_finished(parent):
    """True when the epic is open and has sub-issues, all of them closed."""
    return parent['state'] == 'OPEN' and parent['total'] > 0 and parent['completed'] == parent['total']


def close_finished_epics(repo, number, apply=False, gh=run_gh, out=print):
    """Walk up from issue NUMBER, closing each open parent whose sub-issues are all closed.
    Returns the numbers of the epics closed (or that would be closed, in a preview)."""
    closed = []
    seen = {number}
    parent = get_parent(repo, number, gh)
    if parent is None:
        out(f'#{number} has no parent epic. Nothing to do.')
    while parent is not None and parent['number'] not in seen:
        seen.add(parent['number'])
        label = f"#{parent['number']} {parent['title']}"
        if parent['state'] != 'OPEN':
            out(f'{label} is already closed.')
            break
        if not is_finished(parent):
            out(f"{label} stays open: {parent['completed']} of {parent['total']} closed.")
            break
        if apply:
            gh(['issue', 'close', str(parent['number']), '--repo', repo, '--reason', 'completed',
                '--comment', COMMENT.format(total=parent['total'])])
            out(f"CLOSED {label}: all {parent['total']} closed.")
        else:
            out(f"WOULD CLOSE {label}: all {parent['total']} closed.")
        closed.append(parent['number'])
        parent = get_parent(repo, parent['number'], gh)
    return closed


def main(argv=None):
    ap = argparse.ArgumentParser(description='Close an issue\'s epic once every story and bug under it is closed.')
    ap.add_argument('--issue', type=int, required=True, help='The issue that was just closed.')
    ap.add_argument('--repo', default=DEFAULT_REPO, help=f'OWNER/NAME (default {DEFAULT_REPO}).')
    ap.add_argument('--apply', action='store_true', help='Close the epic. Without it, only preview.')
    args = ap.parse_args(argv)
    try:
        close_finished_epics(args.repo, args.issue, apply=args.apply)
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
