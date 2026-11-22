"""The GitHub issue forms in .github/ISSUE_TEMPLATE give stories and bugs the same layout
and labels as the imported ones (US-32). Run with: python -m unittest discover -s tests"""

import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FORMS = ROOT / '.github' / 'ISSUE_TEMPLATE'
sys.path.insert(0, str(ROOT / 'tools'))
import import_github_issues as gi  # noqa: E402


def read(name):
    return (FORMS / name).read_text(encoding='utf-8')


def options(text, field_id):
    """The options of one dropdown in a form."""
    block = text.split(f'id: {field_id}\n', 1)[1].split('\n  - type:', 1)[0]
    return re.findall(r'^        - "?(.+?)"?$', block, flags=re.M)


class IssueFormTests(unittest.TestCase):

    def test_story_form(self):
        text = read('story.yml')
        self.assertIn('labels: ["user story"]', text)
        self.assertIn('\ntype: Feature\n', text)
        self.assertNotIn('title:', text)
        self.assertEqual(options(text, 'priority'), list(gi.PRIORITY.values()))
        self.assertEqual(options(text, 'persona'), ['TV series owner', 'Movie owner', 'Video owner', 'Maintainer'])
        epics = [re.sub(r' \(#\d+\)$', '', option) for option in options(text, 'epic')]
        self.assertEqual(sorted(epics), sorted(gi.EPIC_SHORT_NAMES.values()))

    def test_bug_form(self):
        text = read('bug.yml')
        self.assertIn('labels: ["bug"]', text)
        self.assertIn('\ntype: Bug\n', text)
        self.assertNotIn('title:', text)
        self.assertEqual([o.split(' (')[0] for o in options(text, 'severity')], list(gi.SEVERITY.values()))
        # 'To confirm' is only for bugs imported before the finder was recorded
        self.assertEqual(options(text, 'found_by'), [who for who in gi.FOUND_BY if who != 'To confirm'])
        for heading in ('Affects', 'Where', 'Steps to reproduce', 'Expected', 'Actual'):
            self.assertIn(f'label: {heading}\n', text)

    def test_no_tabs_or_trailing_spaces(self):
        for path in FORMS.glob('*.yml'):
            for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                self.assertNotIn('\t', line, f'{path.name}:{number}')
                self.assertEqual(line, line.rstrip(), f'{path.name}:{number}')


if __name__ == '__main__':
    unittest.main()
