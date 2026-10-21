import io
import json
import os
import unittest
from pathlib import Path
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

    def files(self) -> list[str]:
        """Every file in the show folder, as paths relative to the season folder ('../Trailers/Season 02/Pilot.mkv')."""
        return sorted(Path(os.path.relpath(p, self.season)).as_posix()
                      for p in self.season.parent.rglob("*") if p.is_file())

    def test_names_disc_rips_and_trailers(self):
        lengths = {}
        for i, disc in enumerate(["Disc 01 - title_t00", "Disc 01 - title_t01", "Disc 02 - title_t00"]):
            self.make(disc + ".mkv")
            lengths[disc + ".mkv"] = EPISODE
        for t in range(3):
            self.make(f"Disc 01 - title_t0{t + 2}.mkv")
            lengths[f"Disc 01 - title_t0{t + 2}.mkv"] = CLIP
        self.rename("--apply", lengths=lengths)
        self.assertEqual(self.files(), sorted([
            "Test Show (2001) - s02e01 - Pilot [2002-01-01].mkv",
            "Test Show (2001) - s02e02 - Part - Two [2002-01-08].mkv",
            "Test Show (2001) - s02e03 - Three....mkv",
            "../Trailers/Season 02/Pilot.mkv",
            "../Trailers/Season 02/Part - Two.mkv",
            "../Trailers/Season 02/Three....mkv",
        ]))

    def test_disc_order_is_numeric(self):
        lengths = {"Disc 2 - a.mkv": EPISODE, "Disc 10 - a.mkv": EPISODE, "Disc 1 - a.mkv": EPISODE}
        for name in lengths:
            self.make(name)
        out = self.rename(lengths=lengths)
        self.assertLess(out.index("Disc 1 - a.mkv"), out.index("Disc 2 - a.mkv"))
        self.assertIn("Disc 10 - a.mkv  (30:00)\n  -> Test Show (2001) - s02e03", out)

    def test_dry_run_changes_nothing(self):
        self.make("rip.mkv")
        out = self.rename(lengths={"rip.mkv": EPISODE})
        self.assertEqual(self.names(), ["rip.mkv"])
        self.assertIn("Would rename 1 file(s)", out)

    def test_tagged_files_get_guide_title(self):
        self.make("Test Show - S02E02 - old name.mp4")
        self.make("Test Show (2001) - s02e01 - Pilot [2002-01-01].mkv")
        out = self.rename("--apply")
        self.assertIn("Test Show (2001) - s02e02 - Part - Two [2002-01-08].mp4", self.names())
        self.assertIn("1 already correct", out)

    def test_untagged_fill_missing_episodes(self):
        self.make("Test Show - s02e01 - Pilot [2002-01-01].mkv")
        self.make("rip.mkv")
        self.rename("--apply", lengths={"rip.mkv": EPISODE})
        self.assertIn("Test Show (2001) - s02e02 - Part - Two [2002-01-08].mkv", self.names())

    def test_first_option(self):
        self.make("rip.mkv")
        out = self.rename("--first", "3", "--apply", lengths={"rip.mkv": EPISODE})
        self.assertEqual(self.names(), ["Test Show (2001) - s02e03 - Three....mkv"])
        self.assertNotIn("WARNING", out)

    def test_reports_episodes_with_no_file(self):
        self.make("rip.mkv")
        out = self.rename(lengths={"rip.mkv": EPISODE})
        self.assertIn("WARNING 1 episode file(s) for 3 missing", out)
        self.assertIn("Episodes with no file: s02e02, s02e03", out)

    def test_episode_files_beyond_the_guide_become_bonus_extras(self):
        lengths = {f"rip{i}.mkv": EPISODE for i in range(5)}
        for name in lengths:
            self.make(name)
        out = self.rename("--apply", lengths=lengths)
        self.assertIn("the last 2 become bonus extras", out)
        self.assertEqual(self.files(), sorted([
            "Test Show (2001) - s02e01 - Pilot [2002-01-01].mkv",
            "Test Show (2001) - s02e02 - Part - Two [2002-01-08].mkv",
            "Test Show (2001) - s02e03 - Three....mkv",
            "Other/Season 2 Bonus 01.mkv",
            "Other/Season 2 Bonus 02.mkv",
        ]))

    def test_bonus_option_takes_a_file_out_of_the_episodes(self):
        lengths = {f"rip{i}.mkv": EPISODE for i in range(5)}
        for name in lengths:
            self.make(name)
        self.rename("--bonus", "rip1.mkv", "--bonus", "RIP3.mkv", "--apply", lengths=lengths)
        self.assertEqual(self.files(), sorted([
            "Test Show (2001) - s02e01 - Pilot [2002-01-01].mkv",
            "Other/Season 2 Bonus 01.mkv",
            "Test Show (2001) - s02e02 - Part - Two [2002-01-08].mkv",
            "Other/Season 2 Bonus 02.mkv",
            "Test Show (2001) - s02e03 - Three....mkv",
        ]))

    def test_unknown_bonus_file_is_an_error(self):
        self.make("rip0.mkv")
        with self.assertRaises(SystemExit), mock.patch("sys.stderr", io.StringIO()):
            self.rename("--bonus", "nope.mkv", lengths={"rip0.mkv": EPISODE})

    def test_trailers_first_names_the_first_clips_after_episodes(self):
        lengths = {f"rip{i}.mkv": EPISODE for i in range(3)}
        lengths.update({f"rip{i}.mkv": CLIP for i in range(3, 8)})
        for name in lengths:
            self.make(name)
        self.rename("--trailers-first", "--apply", lengths=lengths)
        self.assertEqual(self.files(), sorted([
            "Test Show (2001) - s02e01 - Pilot [2002-01-01].mkv",
            "Test Show (2001) - s02e02 - Part - Two [2002-01-08].mkv",
            "Test Show (2001) - s02e03 - Three....mkv",
            "../Trailers/Season 02/Pilot.mkv",
            "../Trailers/Season 02/Part - Two.mkv",
            "../Trailers/Season 02/Three....mkv",
            "Other/Season 2 Extra 01.mkv",
            "Other/Season 2 Extra 02.mkv",
        ]))

    def test_rerun_renames_clips_numbered_earlier(self):
        names = [f"Trailers/Season 2 Extra {i:02d}.mkv" for i in range(1, 3)]  # numbered by older versions
        names.append("Test Show - Season 2 Extra 04 - Trailer.mkv")
        names.append("Test Show (2001) - S02 - Extra 03-trailer.mkv")
        names.append("../Trailers/Season 02/Season 2 Trailer 05.mkv")  # numbered by this version
        for name in names:
            self.make(name)
        self.rename("--trailers-first", "--apply", lengths={Path(n).name: CLIP for n in names})
        self.assertEqual(self.files(), sorted([
            "../Trailers/Season 02/Pilot.mkv",
            "../Trailers/Season 02/Part - Two.mkv",
            "../Trailers/Season 02/Three....mkv",
            "Other/Season 2 Extra 01.mkv",
            "Other/Season 2 Extra 02.mkv",
        ]))

    def test_rerun_leaves_finished_names_alone(self):
        lengths = {f"rip{i}.mkv": CLIP for i in range(5)}
        for name in lengths:
            self.make(name)
        self.rename("--trailers-first", "--apply", lengths=lengths)
        before = self.files()
        out = self.rename("--apply", lengths={Path(n).name: CLIP for n in before})
        self.assertEqual(self.files(), before)
        self.assertIn("Renamed 0 file(s)", out)

    def test_old_inline_extras_move_to_extras_folders(self):
        self.make("Test Show - Catch-38 (Version 2) - Trailer.mkv")
        self.make("Test Show - Bloopers - featurette.mkv")
        self.make("Test Show - Tribute - Behind the Scenes.mkv")
        self.make("Test Show - Season 2 Bonus 01 - Other.mkv")
        self.make("Test Show - s02e01 - Pilot [2002-01-01].mkv")
        self.rename("--apply")
        self.assertEqual(self.files(), sorted([
            "../Trailers/Season 02/Catch-38 (Version 2).mkv",
            "Featurettes/Bloopers.mkv",
            "Behind The Scenes/Tribute.mkv",
            "Other/Season 2 Bonus 01.mkv",
            "Test Show (2001) - s02e01 - Pilot [2002-01-01].mkv",
        ]))

    def test_plex_named_episode_extras_left_alone(self):
        self.make("Test Show - s02e01 - Pilot [2002-01-01].mkv")
        self.make("Test Show - s02e01 - Pilot - Alternate Ending 1-deleted.mkv")
        out = self.rename("--apply")
        self.assertEqual(self.files(), ["Test Show (2001) - s02e01 - Pilot [2002-01-01].mkv",
                                        "Test Show - s02e01 - Pilot - Alternate Ending 1-deleted.mkv"])
        self.assertIn("Renamed 1 file(s)", out)  # only the episode, which gains the year

    def test_extras_only_moves_extras_and_leaves_episodes(self):
        self.guide.unlink()  # not needed
        self.make("Test Show - s02e01 - My Own Title [2002-01-01].mkv")
        self.make("Test Show - Pilot - Trailer.mkv")
        self.make("rip.mkv")
        self.rename("--extras-only", "--apply")
        self.assertEqual(self.files(), ["../Trailers/Season 02/Pilot.mkv",
                                        "Test Show - s02e01 - My Own Title [2002-01-01].mkv", "rip.mkv"])

    def test_unknown_extra_type_is_an_error(self):
        with self.assertRaises(SystemExit), mock.patch("sys.stderr", io.StringIO()) as err:
            self.rename("--extra-type", "Blooper")
        self.assertIn("unknown --extra-type Blooper", err.getvalue())

    def test_clips_numbered_when_count_differs(self):
        lengths = {"a.mkv": CLIP, "b.mkv": CLIP}
        for name in lengths:
            self.make(name)
        out = self.rename("--apply", lengths=lengths)
        self.assertEqual(self.files(), ["../Trailers/Season 02/Season 2 Trailer 01.mkv", "../Trailers/Season 02/Season 2 Trailer 02.mkv"])
        self.assertIn("so they were numbered", out)

    def test_number_extras_and_extra_type(self):
        lengths = {f"c{i}.mkv": CLIP for i in range(3)}
        for name in lengths:
            self.make(name)
        self.rename("--number-extras", "--extra-type", "Featurette", "--apply", lengths=lengths)
        self.assertIn("Featurettes/Season 2 Extra 03.mkv", self.files())

    def test_existing_extras_left_alone(self):
        self.make("Trailers/Pilot.mkv")
        self.make("Deleted Scenes/Alternate Ending.mkv")
        out = self.rename("--apply")
        self.assertEqual(self.files(), ["Deleted Scenes/Alternate Ending.mkv", "Trailers/Pilot.mkv"])
        self.assertIn("Renamed 0 file(s)", out)

    def test_size_used_when_length_unknown(self):
        self.make("big.mkv", size=1000)
        self.make("small.mkv", size=10)
        self.rename("--number-extras", "--apply")
        self.assertIn("Test Show (2001) - s02e01 - Pilot [2002-01-01].mkv", self.names())
        self.assertIn("../Trailers/Season 02/Season 2 Trailer 01.mkv", self.files())

    def test_show_and_season_overrides(self):
        self.make("rip.mkv")
        self.rename("--show", "Other: Show", "--season", "7", "--apply", lengths={"rip.mkv": EPISODE})
        self.assertEqual(self.names(), ["Other - Show (2001) - s07e01 - Pilot [2002-01-01].mkv"])

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
        self.assertEqual(self.names(), ["Test Show (2001) - s02e01 - Pilot [2002-01-01].mkv"])

    def test_season_from_folder_required(self):
        folder = self.tmp / "Loose Files"
        folder.mkdir()
        with self.assertRaises(SystemExit):
            self.run_main(rename_episodes, str(folder), "--guide", str(self.guide))

    def test_downloads_guide_when_none_given(self):
        self.make("rip.mkv")
        saved = self.tmp / "saved.json"
        with mock.patch.object(rename_episodes, "fetch_guide", return_value=("Test Show (2001)", GUIDE)) as fetch:
            out = self.run_main(rename_episodes, str(self.season), "--save-guide", str(saved), "--apply",
                                lengths={"rip.mkv": EPISODE})
        fetch.assert_called_once_with("Test Show", 2, 2001)
        self.assertIn("TVmaze, Test Show (2001) season 2", out)
        self.assertEqual(self.names(), ["Test Show (2001) - s02e01 - Pilot [2002-01-01].mkv"])
        self.assertEqual(json.loads(saved.read_text(encoding="utf-8")), GUIDE)

    def test_download_failure_is_a_clear_error(self):
        with mock.patch.object(rename_episodes, "fetch_guide", side_effect=OSError("offline")), \
                mock.patch("sys.stderr", io.StringIO()) as err:
            with self.assertRaises(SystemExit):
                self.run_main(rename_episodes, str(self.season))
        self.assertIn("could not download the episode guide: offline", err.getvalue())


if __name__ == "__main__":
    unittest.main()
