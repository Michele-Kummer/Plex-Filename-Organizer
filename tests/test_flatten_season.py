import unittest

from helpers import SeasonTestCase

import flatten_season


class FlattenSeasonTests(SeasonTestCase):
    def make_discs(self):
        """Two discs, each with its own episode and the same trailer (sizes differ by a few bytes)."""
        self.make("Disc 01/title_t00.mkv", size=5000)
        self.make("Disc 01/title_t01.mkv", size=300)
        self.make("Disc 02/title_t00.mkv", size=9000)
        self.make("Disc 02/title_t01.mkv", size=310)
        return {"title_t00.mkv": 1800, "title_t01.mkv": 36}

    def test_moves_videos_up_with_disc_prefix(self):
        lengths = self.make_discs()
        self.run_main(flatten_season, str(self.season), "--apply", lengths=lengths)
        self.assertEqual(self.names(), ["Disc 01 - title_t00.mkv", "Disc 01 - title_t01.mkv",
                                        "Disc 02 - title_t00.mkv", "_duplicates"])

    def test_copies_go_to_duplicates_not_deleted(self):
        lengths = self.make_discs()
        self.run_main(flatten_season, str(self.season), "--apply", lengths=lengths)
        self.assertEqual(self.names(self.season / "_duplicates"), ["Disc 02 - title_t01.mkv"])

    def test_removes_empty_disc_folders(self):
        lengths = self.make_discs()
        out = self.run_main(flatten_season, str(self.season), "--apply", lengths=lengths)
        self.assertFalse((self.season / "Disc 01").exists())
        self.assertFalse((self.season / "Disc 02").exists())
        self.assertIn("Removed empty folders", out)

    def test_dry_run_changes_nothing(self):
        lengths = self.make_discs()
        out = self.run_main(flatten_season, str(self.season), lengths=lengths)
        self.assertEqual(self.names(), ["Disc 01", "Disc 02"])
        self.assertIn("Would move 3 file(s) to the season folder and 1 copy(ies)", out)

    def test_same_size_but_different_length_is_not_a_copy(self):
        self.make("Disc 01/a.mkv", size=300)
        self.make("Disc 02/b.mkv", size=300)
        self.run_main(flatten_season, str(self.season), "--apply", lengths={"a.mkv": 36, "b.mkv": 40})
        self.assertEqual(self.names(), ["Disc 01 - a.mkv", "Disc 02 - b.mkv"])

    def test_size_tolerance(self):
        self.make("Disc 01/a.mkv", size=300)
        self.make("Disc 02/a.mkv", size=310)
        self.run_main(flatten_season, str(self.season), "--apply", "--size-tolerance", "5")
        self.assertEqual(self.names(), ["Disc 01 - a.mkv", "Disc 02 - a.mkv"])

    def test_skips_underscore_folders_and_keeps_non_videos(self):
        self.make("_duplicates/old.mkv")
        self.make("Disc 01/title_t00.mkv")
        self.make("Disc 01/info.nfo")
        out = self.run_main(flatten_season, str(self.season), "--apply")
        self.assertTrue((self.season / "_duplicates" / "old.mkv").exists())
        self.assertTrue((self.season / "Disc 01" / "info.nfo").exists())
        self.assertIn("Non-video files left", out)

    def test_refuses_when_target_exists(self):
        self.make("Disc 01/title_t00.mkv")
        self.make("Disc 01 - title_t00.mkv")
        with self.assertRaises(SystemExit):
            self.run_main(flatten_season, str(self.season), "--apply")
        self.assertTrue((self.season / "Disc 01" / "title_t00.mkv").exists())

    def test_nothing_to_flatten(self):
        self.make("episode.mkv")
        out = self.run_main(flatten_season, str(self.season), "--apply")
        self.assertIn("nothing to flatten", out)


if __name__ == "__main__":
    unittest.main()
