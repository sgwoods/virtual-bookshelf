"""docs/ARCHITECTURE.md describes what exists, so it is checked against the tree.

Every repository path it names in `backticks` must exist, every relative link
must resolve, and every command it tells you to run must name a real script.
Intent and plans live in docs/ROADMAP.md, which is not checked.

Run:  python3 -m unittest discover -s tests
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs/ARCHITECTURE.md"
TOP = ("data/", "docs/", "scripts/", "site/", "tests/", ".github/")
GENERATED = {"data/overrides.csv", "data/resolved.csv", "data/reading.csv", "data/cache/", "_site/", "photos/"}  # created locally, or git-ignored


class Architecture(unittest.TestCase):
    text = DOC.read_text(encoding="utf-8")

    def test_named_paths_exist(self):
        for path in sorted(set(re.findall(r"`([^`\s]+)`", self.text))):
            if path.startswith(TOP) and path not in GENERATED:
                with self.subTest(path):
                    self.assertTrue((ROOT / path).exists(), f"{path} is named but missing")

    def test_relative_links_resolve(self):
        for link in re.findall(r"\]\((?!https?:|#)([^)#]+)", self.text):
            with self.subTest(link):
                self.assertTrue((DOC.parent / link).resolve().exists(), f"broken link {link}")

    def test_commands_name_real_scripts(self):
        for script in sorted(set(re.findall(r"python3 (scripts/\w+\.py)", self.text))):
            with self.subTest(script):
                self.assertTrue((ROOT / script).exists())


if __name__ == "__main__":
    unittest.main()
