"""The published page: every catalogued book is on it, and it is self-contained.

Run:  python3 -m unittest discover -s tests
"""
import csv
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_site  # noqa: E402


class Site(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.n = build_site.build(Path(cls.tmp.name))
        cls.html = (Path(cls.tmp.name) / "index.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_book_is_on_the_page(self):
        books = [r for r in csv.DictReader(open(ROOT / "data/books.csv", encoding="utf-8"))
                 if r["position"] != "0"]
        resolved = ROOT / "data/resolved.csv"
        not_books = set()
        if resolved.exists():
            not_books = {r["row_id"] for r in csv.DictReader(open(resolved, encoding="utf-8"))
                         if r["status"] == "not-a-book"}
        expected = sum(1 for b in books if build_site.row_id(b) not in not_books)
        self.assertEqual(self.n["copies"], expected)

    def test_data_is_embedded(self):
        self.assertNotIn("/*BOOKS*/", self.html)
        self.assertNotIn("/*BUILT*/", self.html)
        data = json.loads(re.search(r"const books = (\[.*?\]);\n", self.html, re.S).group(1))
        self.assertEqual(len(data), self.n["titles"])
        for card in data:
            self.assertTrue(card["t"] and card["a"], card)
            self.assertIn(card["s"], ("unread", "reading", "read"))
            self.assertTrue(card["c"] == "" or card["c"].startswith("https://"), card)

    def test_missing_covers_are_counted_not_dropped(self):
        self.assertEqual(self.n["covers_missing"], sum(1 for c in self.n["cards"] if not c["c"]))

    def test_no_external_code(self):
        # Only images come from outside; no scripts or stylesheets.
        self.assertNotRegex(self.html, r'<script[^>]+src=')
        self.assertNotRegex(self.html, r'<link[^>]+stylesheet')


if __name__ == "__main__":
    unittest.main()
