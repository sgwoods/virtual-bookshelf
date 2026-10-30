"""Scoring rules in scripts/resolve.py — offline, no network.

Run:  python3 -m unittest discover -s tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import resolve as R  # noqa: E402

MATCH = R.MATCH


def status(*args):
    s = R.score(*args)
    return "matched" if s >= R.MATCH else "weak" if s >= R.WEAK else "none"


class MustMatch(unittest.TestCase):
    """The same book, written differently by the spine and by Open Library."""

    cases = [
        # (spine title, spine author, OL title, OL authors)
        ("Dune", "Frank Herbert", "Dune", ["Frank Herbert"]),
        ("The Gripping Hand", "Larry Niven and Jerry Pournelle", "The gripping hand", ["Larry Niven", "Jerry Pournelle"]),
        ("Fantastic Voyage: Microcosm", "Kevin J. Anderson", "Microcosm", ["Kevin J. Anderson"]),
        # series naming: "Star Trek - X" vs "X (Star Trek #n)"
        ("Ishmael (Star Trek #23)", "Barbara Hambly", "Star Trek - Ishmael", ["Barbara Hambly"]),
        ("Time for Yesterday (Star Trek #39)", "A. C. Crispin", "Star Trek - Time for Yesterday", ["A. C. Crispin"]),
        # notes in Open Library's title
        ("Von Neumann's War", "John Ringo and Travis S. Taylor", "Von Neumann's War (Von Neuman)", ["John Ringo"]),
        ("Today and Tomorrow and...", "Isaac Asimov", "Today and Tomorrow and ... [32 essays]", ["Isaac Asimov"]),
        ("Paycheck and Other Classic Stories", "Philip K. Dick",
         "Paycheck And Other Classic Stories By Philip K. Dick", ["Philip K. Dick"]),
        # franchise prefix only on one side
        ("Isaac Asimov's Have Robot Will Travel", "Alexander C. Irvine", "Have Robot, Will Travel", ["Alex Irvine"]),
        # author listed only in another script
        ("The Wandering Earth", "Cixin Liu", "The Wandering Earth", ["刘慈欣"]),
        ("Anna Karenina", "Leo Tolstoy", "Anna Karenina", ["Лев Толстой", "Lew Nikolajewitsch Tolstoi"]),
        # matches that held before the Oct 30 patch must still hold
        ("The Hugo Winners Vol. 1", "Isaac Asimov (ed.)", "The Hugo Winners [volume I]", ["Isaac Asimov"]),
    ]

    def test_cases(self):
        for spine_t, spine_a, ol_t, ol_a in self.cases:
            with self.subTest(spine_t):
                self.assertEqual(status(spine_t, spine_a, ol_t, ol_a), "matched")


class MustNotMatch(unittest.TestCase):
    """Different books that look alike. These go to review, never straight in."""

    cases = [
        ("Dune", "Frank Herbert", "Dune Messiah", ["Frank Herbert"]),
        ("Wake", "Robert J. Sawyer", "The Wake", ["Neil Gaiman"]),
        ("The Three-Body Problem", "Cixin Liu (trans. Ken Liu)", "The Three-Body Problem", ["Mauri Valtonen"]),
        ("The Dark Forest", "Cixin Liu", "The dark forest", ["Hugh Walpole"]),
        ("Other Minds", "Peter Godfrey-Smith", "Other minds", ["John Wisdom"]),
        ("Ender's Game", "Orson Scott Card", "Game", ["Someone Else"]),
        ("The Best of Trek 2", "Walter Irwin (ed.)", "The Best of the Best of Trek 2", []),
    ]

    def test_cases(self):
        for spine_t, spine_a, ol_t, ol_a in self.cases:
            with self.subTest(spine_t):
                self.assertNotEqual(status(spine_t, spine_a, ol_t, ol_a), "matched")


class Normalising(unittest.TestCase):
    def test_first_author_drops_roles(self):
        self.assertEqual(R.first_author("Cixin Liu (trans. Ken Liu)"), "Cixin Liu")
        self.assertEqual(R.first_author("Isaac Asimov and Martin H. Greenberg (eds.)"), "Isaac Asimov")

    def test_surname_skips_suffixes(self):
        self.assertEqual(R.surname("Walter M. Miller Jr."), "miller")
        self.assertEqual(R.surname("Peter Attia MD"), "attia")

    def test_number_words(self):
        self.assertEqual(R.norm("Star Trek Log Two"), R.norm("Star Trek Log 2"))


if __name__ == "__main__":
    unittest.main()
