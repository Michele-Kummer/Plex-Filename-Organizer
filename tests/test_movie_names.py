import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401  (puts scripts/ on the path)

import movie_names
from movie_names import (classify, split_copies, fix_name, load_corrections, match_name, strip_title,
                         studio_intro)

CORRECTIONS = {
    "words": {"Rembering": "Remembering", "Unreated": "Unrated", "Dalmations": "Dalmatians"},
    "movies": {"Castaway": "Cast Away (2000)", "American Pie 2": "American Pie 2 (2001)",
               "jackassthe movie": "Jackass The Movie (2002)", "Matrix Reloaded": "The Matrix Reloaded (2003)",
               "Shrek": "Shrek (2001)", "101 Dalmatians II": "101 Dalmatians II (2003)"},
}


def corrections():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "c.json"
        path.write_text(json.dumps(CORRECTIONS), encoding="utf-8")
        return load_corrections(path)


class FixNameTests(unittest.TestCase):
    def fix(self, name, **kw):
        return fix_name(name, corrections(), **kw).name

    def test_year_goes_before_the_edition(self):
        self.assertEqual(self.fix("American Wedding {edition-Extended Unrated Party Edition} (2003)"),
                         "American Wedding (2003) {edition-Extended Unrated Party Edition}")
        self.assertEqual(self.fix("American Pie 2 {edition-Collector's Edition} (2002)"),
                         "American Pie 2 (2001) {edition-Collector's Edition}")  # and the release year

    def test_edition_tag_written_one_way(self):
        self.assertEqual(self.fix("The Hangover (2009) {edition - Unreated}"), "The Hangover (2009) {edition-Unrated}")
        self.assertEqual(self.fix("Van Wilder - The Rise of Taj (2006) {editon-Unrated}"),
                         "Van Wilder - The Rise of Taj (2006) {edition-Unrated}")
        self.assertEqual(self.fix("Hannibal (2001) {Edition-Special Edition}"), "Hannibal (2001) {edition-Special Edition}")
        self.assertEqual(self.fix("The Fox and the Hound (1981) {edition-Gold Classic Collection"),
                         "The Fox and the Hound (1981) {edition-Gold Classic Collection}")
        self.assertEqual(self.fix("Bambi (1942) edition-Platinum Edition}"), "Bambi (1942) {edition-Platinum Edition}")

    def test_titles_and_years_from_the_corrections(self):
        self.assertEqual(self.fix("Castaway ()"), "Cast Away (2000)")
        self.assertEqual(self.fix("jackassthe movie (2002) {edition-Special Collector's Edition}"),
                         "Jackass The Movie (2002) {edition-Special Collector's Edition}")
        self.assertEqual(self.fix("Matrix Reloaded (2003)"), "The Matrix Reloaded (2003)")
        self.assertEqual(self.fix("101 Dalmations Ii"), "101 Dalmatians II (2003)")
        self.assertEqual(self.fix("Shrek (2003) 2"), "Shrek (2001) 2")  # a part number is kept

    def test_small_fixes(self):
        self.assertEqual(self.fix("The Little Mermaid Ariel's Beginning  (2008)"), "The Little Mermaid Ariel's Beginning (2008)")
        self.assertEqual(self.fix("Dr . Seuss How The Grinch Stole Christmas (1957)"),
                         "Dr. Seuss How The Grinch Stole Christmas (1957)")
        self.assertEqual(self.fix("The Sweetest Thing 2002)"), "The Sweetest Thing (2002)")

    def test_empty_year_filled_from_the_folder(self):
        self.assertEqual(self.fix("The Hunger Games ()", folder_year=2012, folder_keys=("hungergames",)),
                         "The Hunger Games (2012)")
        self.assertEqual(self.fix("Something Else ()", folder_year=2012, folder_keys=("hungergames",)), "Something Else")

    def test_good_names_unchanged(self):
        for name in ("Aladdin (1992) {edition-Platinum Edition}", "The Cobweb Hotel (1936) [For Flies Only]",
                     "Care Bears Movie 2 - A New Generation (1986)", "Monsters, Inc. (2001) {Full Screen}"):
            fixed = fix_name(name, corrections())
            self.assertEqual((fixed.name, fixed.kinds), (name, []))


class ExtraNameTests(unittest.TestCase):
    def test_movie_name_dropped(self):
        self.assertEqual(strip_title("The Wizard of Oz (1939) {edition-70th Anniversary Edition}_The Making Of",
                                     ["The Wizard of Oz"]), "The Making Of")
        self.assertEqual(strip_title("How The Grinch Stole Christmas -Tree Song", ["How the Grinch Stole Christmas"]),
                         "Tree Song")
        self.assertEqual(strip_title("40 Year Old Virgin Trailer", ["40 Year Old Virgin"]), "Trailer")
        self.assertEqual(strip_title("Kung Fu Fighting", ["Monsters vs Aliens"]), "Kung Fu Fighting")

    def test_classify(self):
        self.assertEqual(classify("Behind The Scenes Featurette"), ("Behind The Scenes", "Behind The Scenes Featurette"))
        self.assertEqual(classify("Deleted Scenes"), ("Deleted Scenes", "Deleted Scenes"))
        self.assertEqual(classify("trailer"), ("Trailers", "Trailer"))
        self.assertEqual(classify("The Old Mill Animated Short (1937)"), ("Shorts", "The Old Mill Animated Short (1937)"))
        self.assertEqual(classify("Bloopers (3)"), ("Other", "Bloopers (3)"))
        self.assertEqual(classify("From Rags to Riches The Making of Cinderella 1"),
                         ("Behind The Scenes", "From Rags to Riches The Making of Cinderella 1"))
        self.assertEqual(classify("Shrek Musical 1"), ("Other", "Shrek Musical 1"))

    def test_studio_intro(self):
        self.assertEqual(studio_intro("Intro Lionsgate"), "Lionsgate")
        self.assertEqual(studio_intro("Universal Intro"), "Universal")
        self.assertIsNone(studio_intro("Intro And First Song"))
        self.assertIsNone(studio_intro("Intro"))


class MatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for name in ("Trolls (2016)", "Bambi (1942) {edition-Platinum Edition}", "Bambi II (2006)",
                     "The Twilight Saga Twilight (2008)", "Into the Woods (2014)", "Shrek (2003)", "Home Alone (1990)"):
            (self.tmp / name).mkdir()
        self.movies = movie_names.index_movies(self.tmp, corrections())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def match(self, stem):
        movie, text = match_name(stem, self.movies, corrections())
        return (movie.path.name if movie else None), text

    def test_matches(self):
        self.assertEqual(self.match("Trolls (2016) - Deleted Scenes"), ("Trolls (2016)", "Deleted Scenes"))
        self.assertEqual(self.match("Trolls (2016) - Travel Through Troll Village"),
                         ("Trolls (2016)", "Travel Through Troll Village"))
        self.assertEqual(self.match("Bambi - The Old Mill Animated Short (1937)"),
                         ("Bambi (1942) {edition-Platinum Edition}", "The Old Mill Animated Short"))
        self.assertEqual(self.match("Twilight (2008) - Bonus"), ("The Twilight Saga Twilight (2008)", "Bonus"))
        self.assertEqual(self.match("Multiple trailers from Into the Woods (2014)"),
                         ("Into the Woods (2014)", "Multiple trailers from Into the Woods"))
        self.assertEqual(self.match("Shrek (2003) - Bonus"), ("Shrek (2003)", "Bonus"))  # folder's year is fixed too
        self.assertEqual(self.match("Trolls - Trailer (2016)_36"), ("Trolls (2016)", "Trailer"))

    def test_no_match(self):
        self.assertIsNone(self.match("Home - Trailer")[0])
        self.assertIsNone(self.match("Kung Fu Fighting - Music Video")[0])

    def test_split_copies(self):
        files = []
        for name, data in (("Loser - Trailer.mkv", b"a"), ("Loser - Trailer_20.mp4", b"b"),
                           ("Home Alone 3 - Trailer.mp4", b"c"), ("Home Alone 3 - Trailer_13.mp4", b"dd"),
                           ("Panic Room - Trailer.mp4", b"e"), ("Panic Room - Trailer_22.mp4", b"e")):
            (self.tmp / name).write_bytes(data)
            files.append(self.tmp / name)
        keep, copies = split_copies(files)
        self.assertEqual([f.name for f in copies], ["Loser - Trailer.mkv", "Panic Room - Trailer_22.mp4"])
        self.assertEqual(len(keep), 4)  # the two Home Alone 3 trailers differ


class MovieRunTests(unittest.TestCase):
    """A movie library and a separate folder of trailers and bonus material."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.movies = self.tmp / "Movies"
        self.bonus = self.tmp / "Bonus"
        self.tv = self.tmp / "TV"
        for d in (self.movies, self.bonus, self.tv):
            d.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make(self, path: Path, size: int = 10) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
        return path

    def files(self, folder: Path) -> list[str]:
        return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())

    def run_check(self, folder: Path, apply=True, lengths=None) -> str:
        out = io.StringIO()
        fake = lambda paths: {p: (lengths or {}).get(p.name) for p in paths}
        with redirect_stdout(out), mock.patch.object(movie_names, "durations", fake):
            movie_names.run(folder, self.movies, apply, corrections(), self.tv)
        return out.getvalue()

    def test_library_folders_and_movie_files(self):
        self.make(self.movies / "Castaway (2000)" / "Castaway (2000).mp4")
        self.make(self.movies / "Matrix Reloaded (2003)" / "Matrix Reloaded (2003).mp4")
        self.make(self.movies / "Hannibal (2001) {Edition-Special Edition}" / "Hannibal (2001) {Edition-Special Edition}.mp4")
        self.make(self.movies / "Hunger Games (2012)" / "The Hunger Games ().mp4")
        self.make(self.movies / "Hunger Games (2012)" / "Special Features" / "The Hunger Games - Casting.mp4")
        self.make(self.movies / "Hunger Games (2012)" / "Special Features" / "The Hunger Games - Trailer 2.mp4")
        self.make(self.movies / "Hunger Games (2012)" / "Intro - Lionsgate.mp4")
        self.make(self.movies / "Home Alone 3 (1997)" / "Home Alone 3 (1997).mp4")
        self.make(self.movies / "Home Alone 3 (1997)" / "Home Alone 3 Trailer (2).mp4")
        self.make(self.movies / "Snowman" / "Snowman.mp4")
        out = self.run_check(self.movies)
        self.assertEqual(self.files(self.movies), [
            "Cast Away (2000)/Cast Away (2000).mp4",
            "Hannibal (2001) {edition-Special Edition}/Hannibal (2001) {edition-Special Edition}.mp4",
            "Home Alone 3 (1997)/Home Alone 3 (1997).mp4",
            "Home Alone 3 (1997)/Trailers/Trailer (2).mp4",
            "Hunger Games (2012)/Intro - Lionsgate.mp4",
            "Hunger Games (2012)/Other/Casting.mp4",
            "Hunger Games (2012)/The Hunger Games (2012).mp4",
            "Hunger Games (2012)/Trailers/Trailer 2.mp4",
            "Snowman/Snowman.mp4",
            "The Matrix Reloaded (2003)/The Matrix Reloaded (2003).mp4",
        ])
        self.assertFalse((self.movies / "Hunger Games (2012)" / "Special Features").exists())
        self.assertIn("CHECK  Snowman  (no year in the name", out)
        self.assertIn("studio intro (Lionsgate)", out)

    def test_other_movies_and_rips_in_the_library_are_reported(self):
        self.make(self.movies / "A Charlie Brown Christmas (1965)" / "A Charlie Brown Christmas (1965).mp4")
        self.make(self.movies / "A Charlie Brown Christmas (1965)" / "It's Christmas Time Again, Charlie Brown (1992).mp4")
        self.make(self.movies / "NASA (2003)" / "Apollo 11.mp4")
        self.make(self.movies / "NASA (2003)" / "Skylab.mp4")
        self.make(self.movies / "The Girl Next Door (2004)" / "The Girl Next Door (2004).mp4")
        self.make(self.movies / "The Girl Next Door (2004)" / "B2_t00.mkv", size=2_000_000)
        before = self.files(self.movies)
        out = self.run_check(self.movies)
        self.assertEqual(self.files(self.movies), before)
        self.assertIn("another movie (1992)?", out)
        self.assertIn("CHECK  NASA (2003)  (no file named after the movie", out)
        self.assertIn("1 raw rip name(s) (B2_t00.mkv)", out)

    def test_bonus_folder_extras_move_to_the_movie(self):
        self.make(self.movies / "Cast Away (2000)" / "Cast Away (2000).mp4")
        self.make(self.movies / "Trolls (2016)" / "Trolls (2016).mp4")
        self.make(self.movies / "Double Jeopardy (1999)" / "Double Jeopardy (1999).mp4")
        self.make(self.movies / "Young Guns II (1990)" / "Young Guns II (1990).mp4")
        self.make(self.movies / "The Wizard of Oz (1939) {edition-70th Anniversary Edition}" / "Oz.mp4")
        self.make(self.movies / "Dirty Dancing (1987)" / "Dirty Dancing (1987).mp4")
        self.make(self.bonus / "Castaway ()" / "A1_t01.mkv", size=2_000_000)
        self.make(self.bonus / "Castaway ()" / "A2_t02.mkv", size=2_000_000)
        self.make(self.bonus / "Castaway ()" / "Castaway - Trailer.mkv")
        self.make(self.bonus / "Castaway ()" / "Castaway - Special Features (1).mkv")
        self.make(self.bonus / "The Wizard of Oz (1939) {edition-70th Anniversary Edition}" /
                  "The Wizard of Oz (1939) {edition-70th Anniversary Edition}_The Making Of.mkv")
        self.make(self.bonus / "Dirty Dancing (1987)" / "A1_t00.mkv", size=2_000_000)
        self.make(self.bonus / "Dirty Dancing - Bonus (1987)" / "A1_t00.mkv", size=2_000_000)
        self.make(self.bonus / "Happy Feet (2006)" / "A1_t00.mkv", size=2_000_000)
        self.make(self.bonus / "Trolls (2016)" / "Happy Feet Trailer.mp4")
        self.make(self.bonus / "Trolls (2016)" / "Universal Intro.mkv")
        self.make(self.bonus / "_Intros" / "Intro - Disney.mp4")
        self.make(self.bonus / "Double Jeopardy - Behind The Scenes Featurette.mp4")
        self.make(self.bonus / "Trolls (2016) - Deleted Scenes.mp4")
        self.make(self.bonus / "_Trailers" / "Young Guns II - Trailer.mkv", size=20)
        self.make(self.bonus / "_Trailers" / "Young Guns Ii - Trailer_40.mp4", size=10)
        self.make(self.bonus / "_Trailers" / "The Golden Girls S5 - Trailer.mp4")
        self.make(self.bonus / "_Trailers" / "Scrubs - Trailer.mp4")
        out = self.run_check(self.bonus, lengths={"A2_t02.mkv": 4.0})

        self.assertEqual(self.files(self.movies), [
            "Cast Away (2000)/Cast Away (2000).mp4",
            "Cast Away (2000)/Trailers/Trailer.mkv",
            "Dirty Dancing (1987)/Dirty Dancing (1987).mp4",
            "Double Jeopardy (1999)/Behind The Scenes/Behind The Scenes Featurette.mp4",
            "Double Jeopardy (1999)/Double Jeopardy (1999).mp4",
            "The Wizard of Oz (1939) {edition-70th Anniversary Edition}/Behind The Scenes/The Making Of.mkv",
            "The Wizard of Oz (1939) {edition-70th Anniversary Edition}/Oz.mp4",
            "Trolls (2016)/Deleted Scenes/Deleted Scenes.mp4",
            "Trolls (2016)/Trolls (2016).mp4",
            "Young Guns II (1990)/Trailers/Trailer.mp4",
            "Young Guns II (1990)/Young Guns II (1990).mp4",
        ])
        self.assertEqual(self.files(self.bonus), [
            "Cast Away (2000)/A1_t01.mkv",                      # raw rips and generic names stay, reported
            "Cast Away (2000)/Castaway - Special Features (1).mkv",
            "Dirty Dancing (1987)/A1_t00.mkv",
            "Dirty Dancing (1987)/Bonus A1_t00.mkv",            # bonus folder merged
            "Happy Feet (2006)/A1_t00.mkv",
            "Trolls (2016)/Happy Feet Trailer.mp4",             # Happy Feet has no folder in the library
            "_Intros/Intro - Disney.mp4",
            "_Intros/Intro - Universal.mkv",
            "_Tiny clips/Castaway ()/A2_t02.mkv",
            "_Trailers/Scrubs - Trailer.mp4",
            "_Trailers/The Golden Girls S5 - Trailer.mp4",
            "_duplicates/_Trailers/Young Guns II - Trailer.mkv",  # the .mp4 copy was kept
        ])
        self.assertIn("trailer for Happy Feet (2006), which has no folder", out)
        self.assertIn("1 numbered generic name(s)", out)
        self.assertIn("trailer for TV show 'The Golden Girls' season 5", out)
        self.assertIn("no movie folder for 'Scrubs'", out)
        self.assertFalse((self.bonus / "Dirty Dancing - Bonus (1987)").exists())

    def test_copy_numbers_removed_in_the_library(self):
        self.make(self.movies / "Bruce Almighty (2003)" / "Bruce Almighty (2003)_1.mp4")
        self.make(self.movies / "Van Wilder (2002)" / "Van Wilder (2002).mp4").write_bytes(b"movie")
        self.make(self.movies / "Van Wilder (2002)" / "C4_t04_2.mkv", size=2_000_000)
        self.make(self.movies / "Grease (1978)" / "Grease (1978).mp4").write_bytes(b"same")
        self.make(self.movies / "Grease (1978)" / "Grease (1978)_1.mp4").write_bytes(b"same")
        out = self.run_check(self.movies)
        self.assertEqual(self.files(self.movies), [
            "Bruce Almighty (2003)/Bruce Almighty (2003).mp4",
            "Grease (1978)/Grease (1978).mp4",
            "Van Wilder (2002)/C4_t04.mkv",
            "Van Wilder (2002)/Van Wilder (2002).mp4",
            "_duplicates/Grease (1978)/Grease (1978)_1.mp4",
        ])
        self.assertIn("copy number removed (_1)", out)

    def test_tv_trailer_goes_into_its_season(self):
        self.make(self.bonus / "_Trailers" / "The Golden Girls S5 - Trailer.mp4")
        (self.tv / "The Golden Girls (1985)" / "Season 05").mkdir(parents=True)
        self.run_check(self.bonus)
        self.assertEqual(self.files(self.tv), ["The Golden Girls (1985)/Trailers/Season 05/Season 5 Trailer.mp4"])

    def test_dry_run_changes_nothing(self):
        self.make(self.movies / "Castaway (2000)" / "Castaway (2000).mp4")
        self.make(self.bonus / "Castaway ()" / "Castaway - Trailer.mkv")
        out = self.run_check(self.bonus, apply=False)
        self.assertEqual(self.files(self.bonus), ["Castaway ()/Castaway - Trailer.mkv"])
        self.assertIn("Would change 2", out)


if __name__ == "__main__":
    unittest.main()
