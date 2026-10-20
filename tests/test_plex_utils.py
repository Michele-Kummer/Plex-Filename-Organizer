import unittest
from pathlib import Path
from unittest import mock

from helpers import SeasonTestCase  # noqa: F401  (sets up the import path)

import plex_utils
from plex_utils import _parse_duration, is_extra, safe_filename, show_and_season_from_folder


class SafeFilenameTests(unittest.TestCase):
    def test_removes_characters_windows_does_not_allow(self):
        self.assertEqual(safe_filename('Attack of the 5\'10" Woman'), "Attack of the 5'10 Woman")
        self.assertEqual(safe_filename("Are We Sluts?"), "Are We Sluts")
        self.assertEqual(safe_filename("A*B<C>D|E/F\\G"), "ABCDEFG")

    def test_colon_becomes_dash(self):
        self.assertEqual(safe_filename("Part: Two"), "Part - Two")
        self.assertEqual(safe_filename("Part:Two"), "Part - Two")

    def test_keeps_dots_apostrophes_and_punctuation(self):
        self.assertEqual(safe_filename("Where There's Smoke..."), "Where There's Smoke...")
        self.assertEqual(safe_filename("Cock a Doodle Do!"), "Cock a Doodle Do!")

    def test_collapses_spaces_and_falls_back_when_empty(self):
        self.assertEqual(safe_filename("  Two   Spaces  "), "Two Spaces")
        self.assertEqual(safe_filename("???"), "Untitled")


class IsExtraTests(unittest.TestCase):
    def test_plex_extra_suffixes(self):
        self.assertTrue(is_extra(Path("Show - Pilot - Trailer.mkv")))
        self.assertTrue(is_extra(Path("Show - Behind The Scenes.mp4")))
        self.assertTrue(is_extra(Path("Making Of-featurette.mkv")))

    def test_episodes_are_not_extras(self):
        self.assertFalse(is_extra(Path("Show - s01e01 - Pilot [2000-01-01].mkv")))
        self.assertFalse(is_extra(Path("Disc 01 - title_t00.mkv")))


class ParseDurationTests(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(_parse_duration("0:29:37"), 29 * 60 + 37)
        self.assertEqual(_parse_duration("1:02:03"), 3723)
        self.assertEqual(_parse_duration("35.50 s"), 35.5)
        self.assertIsNone(_parse_duration("-"))


class ShowAndSeasonTests(unittest.TestCase):
    def test_plex_style_path(self):
        folder = Path(r"C:\TV Shows\Sex and the City (1998)\Season 03 (2000)")
        self.assertEqual(show_and_season_from_folder(folder), ("Sex and the City", 3))

    def test_without_years(self):
        self.assertEqual(show_and_season_from_folder(Path("/tv/Frasier/Season 11")), ("Frasier", 11))

    def test_no_season_number(self):
        self.assertEqual(show_and_season_from_folder(Path("/tv/Frasier/Specials")), ("Frasier", None))


class DurationsTests(unittest.TestCase):
    def test_none_for_every_file_without_exiftool(self):
        paths = [Path("a.mkv"), Path("b.mkv")]
        with mock.patch.object(plex_utils.shutil, "which", return_value=None):
            self.assertEqual(plex_utils.durations(paths), {paths[0]: None, paths[1]: None})


if __name__ == "__main__":
    unittest.main()
