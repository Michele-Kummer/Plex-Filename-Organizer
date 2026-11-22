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
            text = path.read_text(encoding='utf-8')
            for target in re.findall(r'\]\(([^)\s]+)\)', text) + re.findall(r'(?:src|srcset)="([^"]+)"', text):
                if re.match(r'[a-z]+:|#', target):
                    continue
                self.assertTrue((path.parent / target.split('#')[0]).exists(), f'{name} links to {target}')

    def test_license_and_logo(self):
        self.assertIn('Copyright (c) 2026 SK | SkyOrbit', (ROOT / 'LICENSE').read_text(encoding='utf-8'))
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        # The README loads the animated logo, in light and dark mode alike, from the profile
        # repository, and keeps no logo file here, so none is under this repo's MIT license
        base = 'https://raw.githubusercontent.com/Michele-Kummer/Michele-Kummer/main/images'
        self.assertIn(f'src="{base}/SkyOrbitLogo.gif"', readme)
        self.assertNotIn('<picture>', readme)
        self.assertIn('not covered by the MIT license', readme)
        self.assertIn('docs/branding/', (ROOT / '.gitignore').read_text(encoding='utf-8').splitlines())

    def test_readme_shows_the_tests_badge(self):
        self.assertIn('/actions/workflows/tests.yml/badge.svg', (ROOT / 'README.md').read_text(encoding='utf-8'))
        self.assertTrue((ROOT / '.github/workflows/tests.yml').is_file())

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
