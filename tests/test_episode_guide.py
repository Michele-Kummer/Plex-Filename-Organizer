import unittest

from helpers import SeasonTestCase  # noqa: F401  (sets up the import path)

from episode_guide import pick_show, season_guide

SEARCH = [
    {"show": {"id": 20329, "name": "Sex and the City", "premiered": "2012-07-09"}},
    {"show": {"id": 676, "name": "Sex and the City", "premiered": "1998-06-06"}},
    {"show": {"id": 49081, "name": "Ex and the City", "premiered": "2019-10-28"}},
]


class PickShowTests(unittest.TestCase):
    def test_year_picks_between_shows_with_the_same_name(self):
        self.assertEqual(pick_show(SEARCH, "Sex and the City", 1998)["id"], 676)

    def test_without_year_takes_first_exact_name(self):
        self.assertEqual(pick_show(SEARCH[::-1], "sex and the city", None)["id"], 676)

    def test_no_results(self):
        self.assertIsNone(pick_show([], "Nothing", None))


class SeasonGuideTests(unittest.TestCase):
    def test_keeps_only_the_seasons_numbered_episodes(self):
        episodes = [
            {"season": 3, "number": 18, "name": "Cock a Doodle Do!", "airdate": "2000-10-15"},
            {"season": 4, "number": 1, "name": "The Agony and the 'Ex'-tacy", "airdate": "2001-06-03"},
            {"season": 4, "number": None, "name": "A Special", "airdate": "2001-06-01"},
            {"season": 4, "number": 2, "name": "The Real Me", "airdate": ""},
        ]
        self.assertEqual(season_guide(episodes, 4), [
            {"episode": 1, "title": "The Agony and the 'Ex'-tacy", "air_date": "2001-06-03"},
            {"episode": 2, "title": "The Real Me", "air_date": None},
        ])


if __name__ == "__main__":
    unittest.main()
