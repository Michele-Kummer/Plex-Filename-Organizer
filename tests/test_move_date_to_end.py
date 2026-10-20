import unittest

from helpers import SeasonTestCase

import move_date_to_end


class MoveDateToEndTests(SeasonTestCase):
    def test_moves_date_to_end(self):
        self.make("Show - s01e06 - 1998-07-12 - Secret Sex.mp4")
        self.run_main(move_date_to_end, str(self.season), "--apply")
        self.assertEqual(self.names(), ["Show - s01e06 - Secret Sex [1998-07-12].mp4"])

    def test_dry_run_changes_nothing(self):
        self.make("Show - s01e06 - 1998-07-12 - Secret Sex.mp4")
        out = self.run_main(move_date_to_end, str(self.season))
        self.assertEqual(self.names(), ["Show - s01e06 - 1998-07-12 - Secret Sex.mp4"])
        self.assertIn("Would rename 1 file(s)", out)

    def test_skips_other_formats(self):
        keep = ["Show - Secret Sex - Trailer.mp4", "Show - s01e01 - Pilot [1998-06-07].mp4", "notes.txt"]
        for name in keep:
            self.make(name)
        self.run_main(move_date_to_end, str(self.season), "--apply")
        self.assertEqual(self.names(), sorted(keep))

    def test_title_with_dashes_and_commas(self):
        self.make("Show - s01e12 - 1998-08-23 - Oh Come, All Ye - Faithful.mp4")
        self.run_main(move_date_to_end, str(self.season), "--apply")
        self.assertEqual(self.names(), ["Show - s01e12 - Oh Come, All Ye - Faithful [1998-08-23].mp4"])

    def test_never_overwrites(self):
        self.make("Show - s01e06 - 1998-07-12 - Secret Sex.mp4", size=1)
        self.make("Show - s01e06 - Secret Sex [1998-07-12].mp4", size=2)
        out = self.run_main(move_date_to_end, str(self.season), "--apply")
        self.assertIn("SKIP", out)
        self.assertEqual(len(self.names()), 2)
        self.assertEqual((self.season / "Show - s01e06 - Secret Sex [1998-07-12].mp4").stat().st_size, 2)


if __name__ == "__main__":
    unittest.main()
