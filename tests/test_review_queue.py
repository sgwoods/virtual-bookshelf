"""The one-book-at-a-time queue: which books need a person, and that a decision
leaves the queue at once (applied to resolved.csv), can be undone, and that
skipped books go to the back.

Run:  python3 -m unittest discover -s tests
"""
import csv
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import resolve        # noqa: E402
import review_queue as q  # noqa: E402

BOOKS = [
    # photo, stack, position, title, author, confidence, notes
    ("IMG_1", "shelf", "0", "(shelf label)", "", "high", ""),
    ("IMG_1", "shelf", "1", "Wake", "Robert J. Sawyer", "high", ""),                   # weak
    ("IMG_1", "shelf", "2", "Outliers", "Malcolm Gladwell", "high", ""),               # matched: fine
    ("IMG_1", "shelf", "3", "Serenity: Better Days", "Joss Whedon", "high", ""),       # subtitle dropped
    ("IMG_1", "shelf", "4", "unknown (worn black spine)", "?", "low", ""),            # unreadable
    ("IMG_1", "shelf", "5", "Dune", "Frank Herbert", "medium", ""),                    # hard to read
]
WAKE = [{"source": "openlibrary", "work_id": "/works/W1", "title": "Wake", "author": "Robert J. Sawyer",
         "year": 2009, "cover_url": "", "score": 0.7},
        {"source": "openlibrary", "work_id": "/works/W2", "title": "The Wake", "author": "Neil Gaiman",
         "year": 1997, "cover_url": "", "score": 0.5}]


def res(pos, status, title="", cands=(), work_id=""):
    r = dict.fromkeys(resolve.OUT_FIELDS, "")
    b = BOOKS[pos]
    r.update(row_id=f"IMG_1:shelf:{pos}", photo="IMG_1", stack="shelf", position=str(pos), title=b[3],
             author=b[4], confidence=b[5], status=status, match_title=title, work_id=work_id,
             candidates=json.dumps(list(cands)))
    return r


class Queue(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.saved = (q.BOOKS, q.RESOLVED, q.OVERRIDES, q.published_decisions)
        q.BOOKS, q.RESOLVED, q.OVERRIDES = (self.tmp / n for n in ("books.csv", "resolved.csv", "overrides.csv"))
        self.head = {}
        q.published_decisions = lambda: dict(self.head)
        q.SKIPPED.clear(); q.UNDO.clear()
        with open(q.BOOKS, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["photo", "stack", "position", "title", "author", "confidence", "notes"])
            w.writerows(BOOKS)
        rows = [res(1, "weak", "Wake", WAKE, "/works/W1"),
                res(2, "matched", "Outliers: The Story of Success"),
                res(3, "matched", "Serenity", [{"source": "openlibrary", "work_id": "/works/S", "title": "Serenity",
                                                "author": "Joss Whedon", "score": 0.9}], "/works/S"),
                res(4, "skipped"), res(5, "matched", "Dune")]
        with open(q.RESOLVED, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=resolve.OUT_FIELDS); w.writeheader(); w.writerows(rows)

    def tearDown(self):
        q.BOOKS, q.RESOLVED, q.OVERRIDES, q.published_decisions = self.saved
        q.SKIPPED.clear(); q.UNDO.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def status(self, row_id):
        return next(r for r in q.read_csv(q.RESOLVED) if r["row_id"] == row_id)["status"]

    def test_queue_holds_only_books_that_need_a_person(self):
        s = q.state()
        self.assertEqual(s["order"], ["IMG_1:shelf:1", "IMG_1:shelf:3", "IMG_1:shelf:4", "IMG_1:shelf:5"])
        self.assertEqual((s["to_review"], s["ready"], s["published"], s["total"]), (4, 0, 1, 5))

    def test_reasons_are_plain(self):
        self.assertIn("possible match", q.book("IMG_1:shelf:1")["why"])
        self.assertIn("subtitle", q.book("IMG_1:shelf:3")["why"])
        self.assertIn("couldn't be read", q.book("IMG_1:shelf:4")["why"])
        self.assertIn("hard to read", q.book("IMG_1:shelf:5")["why"])

    def test_current_match_is_flagged_and_first(self):
        b = q.book("IMG_1:shelf:3")
        self.assertTrue(b["current"])
        self.assertEqual(b["candidates"][0]["title"], "Serenity")
        self.assertFalse(q.book("IMG_1:shelf:1")["current"], "a weak match is not offered as 'current'")
        self.assertTrue(q.book("IMG_1:shelf:4")["unreadable"])

    def test_a_decision_is_applied_at_once_and_leaves_the_queue(self):
        q.decide("IMG_1:shelf:1", "pick", json.dumps(WAKE[0]))
        self.assertEqual(self.status("IMG_1:shelf:1"), "confirmed")
        s = q.state()
        self.assertNotIn("IMG_1:shelf:1", s["order"])
        self.assertEqual((s["to_review"], s["ready"], s["published"]), (3, 1, 1))
        self.head = {"IMG_1:shelf:1": "pick|" + json.dumps(WAKE[0])}       # pushed to GitHub
        s = q.state()
        self.assertEqual((s["to_review"], s["ready"], s["published"]), (3, 0, 2))

    def test_other_outcomes(self):
        q.decide("IMG_1:shelf:4", "no-match")
        q.decide("IMG_1:shelf:5", "not-a-book")
        self.assertEqual(self.status("IMG_1:shelf:4"), "confirmed-unlisted")
        self.assertEqual(self.status("IMG_1:shelf:5"), "not-a-book")
        with self.assertRaises(ValueError):
            q.decide("IMG_1:shelf:3", "rm -rf")

    def test_undo_puts_it_back_as_it_was(self):
        q.decide("IMG_1:shelf:1", "not-a-book")
        q.undo("IMG_1:shelf:1")
        self.assertEqual(self.status("IMG_1:shelf:1"), "weak")
        self.assertEqual(q.state()["order"][0], "IMG_1:shelf:1")
        self.assertEqual(q.read_csv(q.OVERRIDES), [])

    def test_skip_goes_to_the_back(self):
        q.skip("IMG_1:shelf:1")
        self.assertEqual(q.state()["order"][-1], "IMG_1:shelf:1")
        q.decide("IMG_1:shelf:1", "no-match")
        self.assertNotIn("IMG_1:shelf:1", q.SKIPPED)


if __name__ == "__main__":
    unittest.main()
