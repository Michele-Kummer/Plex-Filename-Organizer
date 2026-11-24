"""tools/close_finished_epics.py closes an issue's epic once all of the epic's stories and
bugs are closed, previews unless --apply, and leaves open or already closed epics alone.
Nothing here contacts GitHub.
Run with: python -m unittest discover -s tests"""

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import close_finished_epics as ce  # noqa: E402

REPO = 'Owner/project'


class FakeGitHub:
    """Answers gh calls from a table of issues: number -> parent dict or None."""

    def __init__(self, parents):
        self.parents = parents
        self.closed = []

    def __call__(self, args):
        if args[:2] == ['api', 'graphql']:
            number = int(next(a for a in args if a.startswith('number=')).split('=', 1)[1])
            parent = self.parents.get(number)
            if parent is not None:
                parent = dict(parent)
                if parent['number'] in self.closed:
                    parent['state'] = 'CLOSED'
                parent['subIssuesSummary'] = {'total': parent.pop('total'), 'completed': parent.pop('completed')}
            return json.dumps({'data': {'repository': {'issue': {'parent': parent}}}})
        if args[:2] == ['issue', 'close']:
            self.closed.append(int(args[2]))
            return ''
        raise AssertionError(f'unexpected gh call {args}')


def epic(number, total, completed, state='OPEN'):
    return {'number': number, 'title': f'Epic: {number}', 'state': state, 'total': total, 'completed': completed}


class CloseFinishedEpicsTests(unittest.TestCase):

    def run_it(self, parents, issue=10, apply=True):
        gh = FakeGitHub(parents)
        lines = []
        result = ce.close_finished_epics(REPO, issue, apply=apply, gh=gh, out=lines.append)
        return result, gh, lines

    def test_closes_the_epic_when_every_child_is_closed(self):
        result, gh, lines = self.run_it({10: epic(5, 12, 12)})
        self.assertEqual(result, [5])
        self.assertEqual(gh.closed, [5])
        self.assertEqual(lines, ['CLOSED #5 Epic: 5: all 12 closed.'])

    def test_preview_closes_nothing(self):
        result, gh, lines = self.run_it({10: epic(5, 3, 3)}, apply=False)
        self.assertEqual(result, [5])
        self.assertEqual(gh.closed, [])
        self.assertTrue(lines[0].startswith('WOULD CLOSE #5'))

    def test_leaves_the_epic_open_while_a_child_is_open(self):
        result, gh, lines = self.run_it({10: epic(5, 12, 11)})
        self.assertEqual((result, gh.closed), ([], []))
        self.assertEqual(lines, ['#5 Epic: 5 stays open: 11 of 12 closed.'])

    def test_leaves_an_already_closed_epic_alone(self):
        result, gh, lines = self.run_it({10: epic(5, 2, 2, state='CLOSED')})
        self.assertEqual((result, gh.closed), ([], []))
        self.assertIn('already closed', lines[0])

    def test_issue_without_an_epic_does_nothing(self):
        result, gh, lines = self.run_it({})
        self.assertEqual((result, gh.closed), ([], []))
        self.assertIn('no parent epic', lines[0])

    def test_closes_the_parent_of_a_finished_epic_too(self):
        result, gh, _ = self.run_it({10: epic(5, 1, 1), 5: epic(2, 3, 3)})
        self.assertEqual(gh.closed, [5, 2])
        self.assertEqual(result, [5, 2])

    def test_comment_and_reason(self):
        calls = []
        gh = FakeGitHub({10: epic(5, 4, 4)})

        def spy(args):
            calls.append(args)
            return gh(args)
        ce.close_finished_epics(REPO, 10, apply=True, gh=spy, out=lambda line: None)
        close = next(c for c in calls if c[:2] == ['issue', 'close'])
        self.assertIn('--reason', close)
        self.assertEqual(close[close.index('--reason') + 1], 'completed')
        self.assertIn('All 4 of its stories and bugs are closed', close[close.index('--comment') + 1])
        self.assertEqual(close[close.index('--repo') + 1], REPO)

    def test_an_epic_with_no_children_is_not_closed(self):
        self.assertFalse(ce.is_finished(epic(5, 0, 0)))

    def test_workflow_runs_the_script_when_an_issue_closes(self):
        text = (ROOT / '.github' / 'workflows' / 'close-epics.yml').read_text(encoding='utf-8')
        self.assertIn('types: [closed]', text)
        self.assertIn('issues: write', text)
        self.assertIn('tools/close_finished_epics.py', text)
        self.assertIn('--apply', text)


if __name__ == '__main__':
    unittest.main()
