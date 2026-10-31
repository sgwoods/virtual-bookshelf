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


class SearchHarder(unittest.TestCase):
    """search_more() and the decisions it feeds, with the network stubbed out."""

    def setUp(self):
        self.calls = []
        self._ol, self._gb = R.ol_search, R.gb_search

        def ol(**p):
            self.calls.append(("ol", p))
            if p.get("q", "").startswith("isbn:"):
                return [{"key": "/works/OL1W", "title": "Wake", "author_name": ["Robert J. Sawyer"],
                         "first_publish_year": 2009, "isbn": ["9780441016792"], "cover_i": 1}]
            return [{"key": "/works/OL2W", "title": "The Wake", "author_name": ["Neil Gaiman"]},
                    {"key": "/works/OL1W", "title": "Wake", "author_name": ["Robert J. Sawyer"],
                     "first_publish_year": 2009}]

        def gb(title, author, q="", n=5):
            self.calls.append(("gb", q))
            return []
        R.ol_search, R.gb_search = ol, gb
        self.row = {"title": "Wake", "author": "Robert J. Sawyer"}

    def tearDown(self):
        R.ol_search, R.gb_search = self._ol, self._gb

    def test_wider_search_ranks_the_right_book_first(self):
        out = R.search_more(self.row)
        self.assertEqual(out[0]["work_id"], "/works/OL1W")
        self.assertEqual(len({c["work_id"] for c in out}), len(out), "duplicates removed")
        self.assertTrue(all(p.get("limit") == 20 for kind, p in self.calls if kind == "ol"))

    def test_isbn_is_looked_up_directly(self):
        out = R.search_more(self.row, isbn="978-0-441-01679-2")
        self.assertIn(("ol", {"q": "isbn:9780441016792"}), self.calls)
        self.assertIn(("gb", "isbn:9780441016792"), self.calls)
        self.assertEqual(out[0]["isbn"], "9780441016792")

    def test_own_text_is_searched_as_typed(self):
        R.search_more(self.row, q="wake www trilogy")
        self.assertEqual([p for k, p in self.calls if k == "ol"], [{"q": "wake www trilogy", "limit": 20}])

    def test_edited_pick_wins(self):
        pick = {"source": "openlibrary", "work_id": "/works/OL9W", "title": "Children of the Lens",
                "author": "E. E. Smith", "year": "1954", "isbn": "123", "cover_url": "u"}
        rec = R.apply_override({"status": "matched", "year": "2017"},
                               {"decision": "pick", "pick_json": R.json.dumps(pick)})
        self.assertEqual((rec["status"], rec["year"], rec["isbns"]), ("confirmed", "1954", "123"))

    def test_not_listed_keeps_typed_details(self):
        d = {"title": "Arena: The Art of Hockey", "author": "Art Gallery of Nova Scotia", "year": "2008",
             "publisher": "AGNS", "isbn": ""}
        rec = R.apply_override({"status": "weak", "work_id": "/works/X", "cover_url": "c"},
                               {"decision": "no-match", "pick_json": R.json.dumps(d)})
        self.assertEqual(rec["status"], "confirmed-unlisted")
        self.assertEqual((rec["match_title"], rec["year"], rec["work_id"], rec["cover_url"]),
                         ("Arena: The Art of Hockey", "2008", "", ""))

    def test_not_listed_without_details_still_works(self):
        rec = R.apply_override({"status": "weak", "match_title": "X"}, {"decision": "no-match", "pick_json": ""})
        self.assertEqual((rec["status"], rec["match_title"]), ("confirmed-unlisted", ""))
