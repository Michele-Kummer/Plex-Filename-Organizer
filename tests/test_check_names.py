import unittest
from unittest import mock

from helpers import SeasonTestCase

import check_names
from check_names import classify_extra, plex_folder


class ClassifyExtraTests(unittest.TestCase):
    def test_old_inline_suffix(self):
        self.assertEqual(classify_extra("Show - Catch-38 - Trailer", "Show"), ("Trailers", "Catch-38"))

    def test_keyword_prefix(self):
        self.assertEqual(classify_extra("Show - Trailer - Back for a Second Season", "Show"),
                         ("Trailers", "Back for a Second Season"))

    def test_bonus_suffix(self):
        self.assertEqual(classify_extra("Show - HBO Farewell Tribute 1 - Bonus", "Show"),
                         ("Other", "HBO Farewell Tribute 1"))

    def test_keyword_inside_title_keeps_title(self):
        self.assertEqual(classify_extra("Show - Deleted Scene 01", "Show"), ("Deleted Scenes", "Deleted Scene 01"))

    def test_type_only_name_is_titled_after_the_show(self):
        self.assertEqual(classify_extra("Show - Behind The Scenes", "Show"), ("Behind The Scenes", "Show"))

    def test_unknown(self):
        self.assertIsNone(classify_extra("Disc 01 - title_t00", "Show"))


class PlexFolderTests(unittest.TestCase):
    def test_names(self):
        self.assertEqual(plex_folder("Trailers"), "Trailers")
        self.assertEqual(plex_folder("trailer"), "Trailers")
        self.assertEqual(plex_folder("Behind the Scenes"), "Behind The Scenes")
        self.assertEqual(plex_folder("Bonus Features"), "Other")
        self.assertIsNone(plex_folder("Disc 01"))


class CheckNamesTests(SeasonTestCase):
    def check(self, *args, folder=None):
        return self.run_main(check_names, str(folder or self.season), *args)

    def files(self) -> list[str]:
        return sorted(p.relative_to(self.season).as_posix() for p in self.season.rglob("*") if p.is_file())

    def test_fixes_misnamed_extras_and_episodes(self):
        self.make("Test Show - Pilot - Trailer.mkv")
        self.make("Test Show - Trailer - Promo Two.mp4")
        self.make("Test Show - Tribute - Bonus.mkv")
        self.make("Test Show - Deleted Scene 01.mkv")
        self.make("Test Show - s02e07 - 2002-02-02 -The Dance.mp4")
        self.make("Test Show - s02e01 - Pilot [2002-01-01].mkv")
        self.make("Test Show - s02e01 - Pilot - Ending 1-deleted.mkv")
        self.check("--apply")
        self.assertEqual(self.files(), sorted([
            "Trailers/Pilot.mkv",
            "Trailers/Promo Two.mp4",
            "Other/Tribute.mkv",
            "Deleted Scenes/Deleted Scene 01.mkv",
            "Test Show - s02e07 - The Dance [2002-02-02].mp4",
            "Test Show - s02e01 - Pilot [2002-01-01].mkv",
            "Test Show - s02e01 - Pilot - Ending 1-deleted.mkv",
        ]))

    def test_fixes_episode_spacing(self):
        self.make("Test Show s02e01 - Pilot.mp4")
        self.make("Test Show - s02e02- 2002-01-08 - Part Two.mkv")
        self.make("Test Show - s2e3 -  Three [2002-01-15].mkv")
        self.check("--apply")
        self.assertEqual(self.files(), sorted([
            "Test Show - s02e01 - Pilot.mp4",
            "Test Show - s02e02 - Part Two [2002-01-08].mkv",
            "Test Show - s02e03 - Three [2002-01-15].mkv",
        ]))

    def test_tag_padded_and_any_date_moved_to_the_end(self):
        self.make("Test Show - S2E4 - (2002-01-22) Four.mkv")
        self.make("Test Show - 2002-01-29 - s02e05 - Five.mkv")
        self.check("--apply")
        self.assertEqual(self.files(), sorted([
            "Test Show - s02e04 - Four [2002-01-22].mkv",
            "Test Show - s02e05 - Five [2002-01-29].mkv",
        ]))

    def test_bracketed_year_is_the_date(self):
        self.make("Test Show - s01e01 - The Friendly Ghost 1945].mp4")
        self.make("Test Show - s01e02 - Boos To-Night [1948].mp4")
        self.make("Test Show - s1e03 - A Haunting We Will Go (1949).mp4")
        self.make("Test Show - s01e04 - Escape 1997.mp4")
        self.check("--apply")
        self.assertEqual(self.files(), sorted([
            "Test Show - s01e01 - The Friendly Ghost [1945].mp4",
            "Test Show - s01e02 - Boos To-Night [1948].mp4",
            "Test Show - s01e03 - A Haunting We Will Go [1949].mp4",
            "Test Show - s01e04 - Escape 1997.mp4",
        ]))

    def test_long_numbers_and_letters_kept_and_split_dates_joined(self):
        self.make("Test Show - s2e214 - 1991-01-08 - Fran Live.mkv")
        self.make("Test Show - s03e317 - 1993 -02-19 - Honey.mkv")
        self.make("Test Show - 2015-10-02 - s1e4A - Split Episode.mkv")
        self.check("--apply")
        self.assertEqual(self.files(), ["Test Show - s01e04A - Split Episode [2015-10-02].mkv",
                                        "Test Show - s02e214 - Fran Live [1991-01-08].mkv",
                                        "Test Show - s03e317 - Honey [1993-02-19].mkv"])

    def test_reports_episode_problems(self):
        self.make("Test Show - s02e06 - 2002-02-05 - Six - 2002-02-06.mkv")
        self.make("Test Show - 2022-01-14 - s0121B - No E.mkv")
        self.make("Test Show - s02e07 - 1994 -067-20 - Typo.mkv")
        out = self.check()
        self.assertIn("'1994 -067-20' looks like a mistyped date", out)
        self.assertIn("more than one date (2002-02-05, 2002-02-06)", out)
        self.assertIn("CHECK  Test Show - 2022-01-14 - s0121B - No E.mkv  (season/episode not in s##e##", out)

    def test_hyphens_made_consistent_everywhere(self):
        self.make("Test Show - 2013-08-12 - Pups Save the Game -.mkv")
        self.make("Trailers/Eggs- Pre-marital  sex.mkv")
        self.check("--apply")
        self.assertEqual(self.files(), ["Test Show - 2013-08-12 - Pups Save the Game.mkv",
                                        "Trailers/Eggs - Pre-marital sex.mkv"])

    def test_specific_word_beats_bonus(self):
        self.assertEqual(classify_extra("Show - Bonus - I'm The Baby featurette", "Show"),
                         ("Featurettes", "I'm The Baby featurette"))

    def test_date_based_episodes_are_fine(self):
        self.make("Test Show - 2013-08-12 - Pups and the Kitty-tastrophe.mkv")
        out = self.check()
        self.assertIn("Would rename 0; 0 to check by hand", out)

    def test_easter_eggs_go_to_other(self):
        self.assertEqual(classify_extra("Show - Eggs - Meeting Jim Henson", "Show"),
                         ("Other", "Eggs - Meeting Jim Henson"))
        self.assertEqual(classify_extra("Show - Eggs - Baby Sinclair - TGIF Trailer", "Show"),
                         ("Other", "Eggs - Baby Sinclair - TGIF Trailer"))
        self.assertEqual(classify_extra("Show - Eggs - Pre-marital sex - Trailer", "Show"),
                         ("Other", "Eggs - Pre-marital sex - Trailer"))

    def test_renames_extras_folders_and_their_files(self):
        self.make("Bonus Features/Test Show - Making Of.mkv")
        self.make("trailers/Pilot.mkv")
        self.check("--apply")
        self.assertEqual(self.files(), ["Other/Making Of.mkv", "Trailers/Pilot.mkv"])
        self.assertEqual(self.names(), ["Other", "Trailers"])

    def test_reports_what_it_cannot_fix(self):
        self.make("Disc 01/title_t00.mkv")
        self.make("rip.mkv")
        self.make("Random Folder/x.mkv")
        out = self.check("--apply")
        self.assertIn("CHECK  Disc 01  (disc folder", out)
        self.assertIn("CHECK  rip.mkv  (not an episode", out)
        self.assertIn("CHECK  Random Folder  (unknown folder)", out)
        self.assertIn("3 to check by hand", out)
        self.assertEqual(len(self.files()), 3)

    def test_date_based_name_gets_separator_and_year_brackets(self):
        self.make("Test Show 2016-09-17 - Pups Get Growing - Pups Save the Bunnies (2017).mkv")
        self.make("Test Show - s01e04A - Catboy - Let's Go (2017) [2015-10-02].mkv")
        self.make("Test Show - 2022-01-14 - s01e21B - Gekko - Let's Go (2017).mkv")
        out = self.check("--apply")
        self.assertEqual(self.files(), [
            "Test Show - 2016-09-17 - Pups Get Growing - Pups Save the Bunnies [2017].mkv",
            "Test Show - s01e04A - Catboy - Let's Go (2017) [2015-10-02].mkv",  # has an air date: year kept
            "Test Show - s01e21B - Gekko - Let's Go (2017) [2022-01-14].mkv",
        ])
        self.assertIn("1  minor formatting", out)
        self.assertIn("0 to check by hand", out)

    def test_type_word_removed_only_in_its_own_folder(self):
        self.make("Trailers/Pilot - Trailer.mkv")
        self.make("Other/Eggs - Pre-marital sex - Trailer.mkv")
        self.check("--apply")
        self.assertEqual(self.files(), ["Other/Eggs - Pre-marital sex - Trailer.mkv", "Trailers/Pilot.mkv"])

    def test_tally_by_kind_of_fix(self):
        self.make("Test Show - S2E1 - 2002-01-01 - Pilot.mkv")      # tag + date moved
        self.make("Test Show - s02e02 - Two (2002).mkv")            # brackets only
        self.make("Test Show - s02e03 -Three.mkv")                  # hyphen
        self.make("Test Show - Four - Trailer.mkv")                 # extra
        self.make("Test Show - Eggs - Five.mkv")                    # extra
        self.make("extras/Six.mkv")                                 # folder
        out = self.check()
        self.assertIn("1  date or year moved to the end in []", out)
        self.assertIn("1  season/episode written as s##e##", out)
        self.assertIn("2  minor formatting (spaces, hyphens, brackets)", out)
        self.assertIn("1  extras folder renamed", out)
        self.assertIn("1  extra moved to Other", out)
        self.assertIn("1  extra moved to Trailers", out)
        self.assertIn("RENAME Test Show - S2E1 - 2002-01-01 - Pilot.mkv  "
                      "(season/episode written as s##e##; date or year moved to the end in [])", out)

    def test_dry_run_changes_nothing(self):
        self.make("Test Show - Pilot - Trailer.mkv")
        out = self.check()
        self.assertEqual(self.files(), ["Test Show - Pilot - Trailer.mkv"])
        self.assertIn("Would rename 1", out)

    def test_never_overwrites(self):
        self.make("Test Show - Pilot - Trailer.mkv", size=1)
        self.make("Trailers/Pilot.mkv", size=2)
        out = self.check("--apply")
        self.assertIn("SKIP", out)
        self.assertEqual((self.season / "Trailers" / "Pilot.mkv").stat().st_size, 2)

    def test_clean_season_reports_nothing(self):
        self.make("Test Show - s02e01 - Pilot [2002-01-01].mkv")
        self.make("Trailers/Pilot.mkv")
        self.make("_duplicates/whatever.mkv")
        out = self.check()
        self.assertIn("Would rename 0; 0 to check by hand", out)

    def test_season_folders_padded_and_show_year_reported(self):
        show = self.tmp / "Other Show"
        for name in ("Season 1", "Season 2 (2004)", "Season 03 [2005]", "Season 10", "Specials"):
            (show / name).mkdir(parents=True)
        with mock.patch.object(check_names, "suggest_year", return_value="1999"):
            out = self.check("--apply", folder=show)
        self.assertEqual(sorted(p.name for p in show.iterdir()),
                         ["Season 01", "Season 02", "Season 03", "Season 10", "Specials"])
        self.assertIn("CHECK  Other Show  (show folder has no year; TVmaze says it started in 1999: "
                      "'Other Show (1999)')", out)
        self.assertIn("2  season folder numbered 01", out)
        self.assertIn("2  year removed from season folder", out)
        out = self.check(folder=self.season)
        self.assertNotIn("has no year", out)  # "Test Show (2001)"

    def test_show_and_library_folders(self):
        self.make("Test Show - Pilot - Trailer.mkv")
        other = self.tmp / "Test Show (2001)" / "Season 03"
        other.mkdir()
        (other / "Test Show - Finale - Trailer.mkv").write_bytes(b"x")
        for folder in (self.season.parent, self.tmp):
            out = self.check(folder=folder)
            self.assertIn("Would rename 2", out)


if __name__ == "__main__":
    unittest.main()
