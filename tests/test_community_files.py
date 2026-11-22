"""The security policy, contributing guide, code of conduct and accessibility statement are where
GitHub looks for them, and every relative link in them points at a file that exists.
Run with: python -m unittest discover -s tests"""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = ['.github/SECURITY.md', '.github/CONTRIBUTING.md', '.github/CODE_OF_CONDUCT.md', 'docs/accessibility.md']


class CommunityFileTests(unittest.TestCase):

    def test_files_exist(self):
        for name in FILES:
            self.assertTrue((ROOT / name).is_file(), name)

    def test_relative_links_point_at_real_files(self):
        for name in FILES + ['README.md']:
            path = ROOT / name
            for target in re.findall(r'\]\(([^)\s]+)\)', path.read_text(encoding='utf-8')):
                if re.match(r'[a-z]+:|#', target):
                    continue
                self.assertTrue((path.parent / target.split('#')[0]).exists(), f'{name} links to {target}')

    def test_code_of_conduct_has_a_contact_and_no_placeholders(self):
        text = (ROOT / '.github/CODE_OF_CONDUCT.md').read_text(encoding='utf-8')
        self.assertNotIn('INSERT', text)
        self.assertIn('https://github.com/Michele-Kummer', text)

    def test_task_template_sets_the_task_type(self):
        text = (ROOT / '.github/ISSUE_TEMPLATE/task.md').read_text(encoding='utf-8')
        self.assertTrue(text.startswith('---\nname: Task\n'))
        self.assertIn('\ntype: Task\n', text)

    def test_no_double_spaces(self):
        for name in FILES:
            for number, line in enumerate((ROOT / name).read_text(encoding='utf-8').splitlines(), 1):
                self.assertNotIn('  ', line.strip(), f'{name}:{number}')


if __name__ == '__main__':
    unittest.main()
