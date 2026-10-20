import io
import json
import unittest
from unittest import mock

from helpers import SeasonTestCase

import rename_episodes

GUIDE = [
    {"episode": 1, "title": "Pilot?", "air_date": "2002-01-01"},
    {"episode": 2, "title": "Part: Two", "air_date": "2002-01-08"},
    {"episode": 3, "title": "Three...", "air_date": None},
]
EPISODE, CLIP = 1800, 36


class RenameEpisodesTests(SeasonTestCase):
    def setUp(self):
        super().setUp()
        self.guide = self.tmp / "guide.json"
        self.guide.write_text(json.dumps(GUIDE), encoding="utf-8")

    def rename(self, *args, lengths=None):
        return self.run_main(rename_episodes, str(self.season), "--guide", str(self.guide), *args,
                             lengths=lengths)

    def test_names_disc_rips_and_trailers(self):
        lengths = {}
        for i, disc in enumerate(["Disc 01 - title_t00", "Disc 01 - title_t01", "Disc 02 - title_t00"]):
            self.make(disc + ".mkv")
            lengths[disc + ".mkv"] = EPISODE
        for t in range(3):
            self.make(f"Disc 01 - title_t0{t + 2}.mkv")
            lengths[f"Disc 01 - title_t0{t + 2}.mkv"] = CLIP
        self.rename("--apply", lengths=lengths)
        self.assertEqual(self.names(), sorted([
            "Test Show - s02e01 - Pilot [2002-01-01].mkv",
            "Test Show - s02e02 - Part - Two [2002-01-08].mkv",
            "Test Show - s02e03 - Three....mkv",
            "Test Show - Pilot - Trailer.mkv",
            "Test Show - Part - Two - Trailer.mkv",
            "Test Show - Three... - Trailer.mkv",
        ]))

    def test_disc_order_is_numeric(self):
        lengths = {"Disc 2 - a.mkv": EPISODE, "Disc 10 - a.mkv": EPISODE, "Disc 1 - a.mkv": EPISODE}
        for name in lengths:
            self.make(name)
        out = self.rename(lengths=lengths)
        self.assertLess(out.index("Disc 1 - a.mkv"), out.index("Disc 2 - a.mkv"))
        self.assertIn("Disc 10 - a.mkv  (30:00)\n  -> Test Show - s02e03", out)

    def test_dry_run_changes_nothing(self):
        self.make("rip.mkv")
        out = self.rename(lengths={"rip.mkv": EPISODE})
        self.assertEqual(self.names(), ["rip.mkv"])
        self.assertIn("Would rename 1 file(s)", out)

    def test_tagged_files_get_guide_title(self):
        self.make("Test Show - S02E02 - old name.mp4")
        self.make("Test Show - s02e01 - Pilot [2002-01-01].mkv")
        out = self.rename("--apply")
        self.assertIn("Test Show - s02e02 - Part - Two [2002-01-08].mp4", self.names())
        self.assertIn("1 already correct", out)

    def test_untagged_fill_missing_episodes(self):
        self.make("Test Show - s02e01 - Pilot [2002-01-01].mkv")
        self.make("rip.mkv")
        self.rename("--apply", lengths={"rip.mkv": EPISODE})
        self.assertIn("Test Show - s02e02 - Part - Two [2002-01-08].mkv", self.names())

    def test_first_option(self):
        self.make("rip.mkv")
        out = self.rename("--first", "3", "--apply", lengths={"rip.mkv": EPISODE})
        self.assertEqual(self.names(), ["Test Show - s02e03 - Three....mkv"])
        self.assertNotIn("WARNING", out)

    def test_reports_episodes_with_no_file(self):
        self.make("rip.mkv")
        out = self.rename(lengths={"rip.mkv": EPISODE})
        self.assertIn("WARNING 1 episode file(s) for 3 missing", out)
        self.assertIn("Episodes with no file: s02e02, s02e03", out)

    def test_too_many_episode_files(self):
        lengths = {f"rip{i}.mkv": EPISODE for i in range(4)}
        for name in lengths:
            self.make(name)
        with self.assertRaises(SystemExit):
            self.rename("--apply", lengths=lengths)
        self.assertEqual(self.names(), sorted(lengths))

    def test_clips_numbered_when_count_differs(self):
        lengths = {"a.mkv": CLIP, "b.mkv": CLIP}
        for name in lengths:
            self.make(name)
        out = self.rename("--apply", lengths=lengths)
        self.assertEqual(self.names(), ["Test Show - Season 2 Extra 01 - Trailer.mkv",
                                        "Test Show - Season 2 Extra 02 - Trailer.mkv"])
        self.assertIn("so they were numbered", out)

    def test_number_extras_and_extra_type(self):
        lengths = {f"c{i}.mkv": CLIP for i in range(3)}
        for name in lengths:
            self.make(name)
        self.rename("--number-extras", "--extra-type", "Featurette", "--apply", lengths=lengths)
        self.assertIn("Test Show - Season 2 Extra 03 - Featurette.mkv", self.names())

    def test_existing_extras_left_alone(self):
        self.make("Test Show - Pilot - Trailer.mkv")
        out = self.rename("--apply")
        self.assertEqual(self.names(), ["Test Show - Pilot - Trailer.mkv"])
        self.assertIn("Renamed 0 file(s)", out)

    def test_size_used_when_length_unknown(self):
        self.make("big.mkv", size=1000)
        self.make("small.mkv", size=10)
        self.rename("--number-extras", "--apply")
        self.assertIn("Test Show - s02e01 - Pilot [2002-01-01].mkv", self.names())
        self.assertIn("Test Show - Season 2 Extra 01 - Trailer.mkv", self.names())

    def test_show_and_season_overrides(self):
        self.make("rip.mkv")
        self.rename("--show", "Other: Show", "--season", "7", "--apply", lengths={"rip.mkv": EPISODE})
        self.assertEqual(self.names(), ["Other - Show - s07e01 - Pilot [2002-01-01].mkv"])

    def test_refuses_to_overwrite(self):
        self.make("Test Show - s02e01 - Pilot [2002-01-01].mkv")
        self.make("Test Show - s02e01 - other copy.mkv")
        with self.assertRaises(SystemExit):
            self.rename("--apply")
        self.assertEqual(len(self.names()), 2)

    def test_missing_guide_is_a_clear_error(self):
        self.guide.unlink()
        with self.assertRaises(SystemExit), mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            self.rename()
        self.assertIn("episode guide not found", err.getvalue())

    def test_invalid_guide_is_a_clear_error(self):
        self.guide.write_text('[{"title": "no number"}]', encoding="utf-8")
        with self.assertRaises(SystemExit), mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            self.rename()
        self.assertIn("could not read the episode guide", err.getvalue())

    def test_guide_saved_with_notepad_bom(self):
        self.guide.write_text(json.dumps(GUIDE), encoding="utf-8-sig")
        self.make("rip.mkv")
        self.rename("--apply", lengths={"rip.mkv": EPISODE})
        self.assertEqual(self.names(), ["Test Show - s02e01 - Pilot [2002-01-01].mkv"])

    def test_season_from_folder_required(self):
        folder = self.tmp / "Loose Files"
        folder.mkdir()
        with self.assertRaises(SystemExit):
            self.run_main(rename_episodes, str(folder), "--guide", str(self.guide))


if __name__ == "__main__":
    unittest.main()
