"""pipeline.py git steps, against a throwaway repository and a local 'origin'.

Checks that publishing never commits to main, only ever adds the three data
files, and that updating refuses to run over unpublished review data.

Run:  python3 -m unittest discover -s tests
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import pipeline  # noqa: E402


def sh(cwd, *cmd):
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@unittest.skipUnless(shutil.which("git"), "git not installed")
class Publish(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        origin, work = self.tmp / "origin.git", self.tmp / "work"
        sh(self.tmp, "git", "init", "-q", "--bare", "-b", "main", str(origin))
        sh(self.tmp, "git", "init", "-q", "-b", "main", str(work))
        for k, v in (("user.name", "Test"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
            sh(work, "git", "config", k, v)
        (work / "data").mkdir()
        for f in ("books.csv", "resolved.csv"):
            (work / "data" / f).write_text("a,b\n1,2\n")
        (work / "notes.txt").write_text("not data\n")
        sh(work, "git", "add", ".")
        sh(work, "git", "commit", "-q", "-m", "start")
        sh(work, "git", "remote", "add", "origin", str(origin))
        sh(work, "git", "push", "-q", "-u", "origin", "main")
        self.work, self._root = work, pipeline.ROOT
        pipeline.ROOT = work
        self.log = []

    def tearDown(self):
        pipeline.ROOT = self._root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_nothing_to_publish(self):
        self.assertTrue(pipeline.publish(self.log.append))
        self.assertEqual(pipeline.branch(), "main")
        self.assertIn("Nothing to publish", "\n".join(self.log))

    def test_publish_goes_to_a_review_branch_with_data_only(self):
        (self.work / "data/resolved.csv").write_text("a,b\n1,3\n")
        (self.work / "data/overrides.csv").write_text("row_id,decision\nx,accept\n")
        (self.work / "notes.txt").write_text("changed but not data\n")
        self.assertTrue(pipeline.publish(self.log.append, "review"))
        br = pipeline.branch()
        self.assertTrue(br.startswith("review-"), br)
        changed = sh(self.work, "git", "show", "--name-only", "--format=", "HEAD").split()
        self.assertEqual(sorted(changed), ["data/overrides.csv", "data/resolved.csv"])
        self.assertEqual(sh(self.work, "git", "rev-parse", "main"), sh(self.work, "git", "rev-parse", "origin/main"),
                         "main must not move")
        self.assertEqual(sh(self.work, "git", "rev-parse", "HEAD"), sh(self.work, "git", "rev-parse", f"origin/{br}"))
        self.assertIn(pipeline.compare_url(br), self.log)
        self.assertIn("notes.txt", sh(self.work, "git", "status", "--porcelain"))

    def test_publish_includes_published_images_not_originals(self):
        import local_images
        d = self.work / "images" / "IMG_1__shelf__1"
        d.mkdir(parents=True)
        (d / "cover.jpg").write_bytes(b"\xff\xd8crop")
        (d / "cover.orig.jpg").write_bytes(b"\xff\xd8original")
        (d / "meta.json").write_text('{"cover": {"published": true, "page_url": "https://www.ebay.com/itm/1"}}')
        (self.work / ".gitignore").write_text("images/\n")
        self.assertTrue(pipeline.publish(self.log.append, "images"))
        changed = sorted(sh(self.work, "git", "show", "--name-only", "--format=", "HEAD").split())
        self.assertEqual(changed, ["data/images.csv", "site_images/IMG_1__shelf__1/cover.jpg"])

    def advance_origin(self, name="new.txt"):
        """Someone (me, via a merged PR) pushes a new commit to GitHub's main."""
        other = self.tmp / "other"
        if not other.exists():
            sh(self.tmp, "git", "clone", "-q", str(self.tmp / "origin.git"), str(other))
            for k, v in (("user.name", "Other"), ("user.email", "o@example.com"), ("commit.gpgsign", "false")):
                sh(other, "git", "config", k, v)
        sh(other, "git", "pull", "-q")
        (other / name).write_text("new version\n")
        sh(other, "git", "add", name)
        sh(other, "git", "commit", "-q", "-m", "new version")
        sh(other, "git", "push", "-q")

    def test_behind_counts_new_commits_on_github(self):
        self.assertEqual(pipeline.behind(), 0)
        self.advance_origin()
        self.assertEqual(pipeline.behind(), 1)

    def test_update_code_on_main_with_unpublished_data(self):
        (self.work / "data/resolved.csv").write_text("a,b\n7,7\n")
        self.advance_origin()
        self.assertTrue(pipeline.update_code(self.log.append))
        self.assertTrue((self.work / "new.txt").exists())
        self.assertEqual((self.work / "data/resolved.csv").read_text(), "a,b\n7,7\n", "review data untouched")
        self.assertEqual(pipeline.behind(), 0)

    def test_update_code_on_review_branch_keeps_unpublished_data_there(self):
        (self.work / "data/resolved.csv").write_text("a,b\n1,3\n")
        pipeline.publish(self.log.append, "review")
        br = pipeline.branch()
        (self.work / "data/overrides.csv").write_text("row_id,decision\nx,accept\ny,accept\n")
        self.advance_origin()
        self.assertTrue(pipeline.update_code(self.log.append))
        self.assertEqual(pipeline.branch(), br)
        self.assertTrue((self.work / "new.txt").exists())
        self.assertIn("y,accept", (self.work / "data/overrides.csv").read_text())

    def test_update_code_returns_to_main_when_nothing_is_unpublished(self):
        (self.work / "data/resolved.csv").write_text("a,b\n1,3\n")
        pipeline.publish(self.log.append, "review")
        self.advance_origin()
        self.assertTrue(pipeline.update_code(self.log.append))
        self.assertEqual(pipeline.branch(), "main")
        self.assertTrue((self.work / "new.txt").exists())

    def test_import_shelf_photos_from_a_drive_download(self):
        import os, zipfile
        dl = self.tmp / "Downloads"
        dl.mkdir()
        os.environ["VB_DOWNLOADS"] = str(dl)
        self.addCleanup(os.environ.pop, "VB_DOWNLOADS", None)
        with zipfile.ZipFile(dl / "drive-download-20261031.zip", "w") as z:
            z.writestr("Bookshelf/IMG_8879.jpg", b"\xff\xd8one")
            z.writestr("Bookshelf/IMG_8880.JPG", b"\xff\xd8two")
            z.writestr("Bookshelf/notes.txt", b"not a photo")
        self.assertTrue(pipeline.import_photos(self.log.append))
        names = sorted(p.name for p in (self.work / "photos/jpg").iterdir())
        if not shutil.which("sips"):          # Linux CI: JPEGs are copied as they are
            self.assertEqual(names, ["IMG_8879.jpg", "IMG_8879_small.jpg", "IMG_8880.jpg", "IMG_8880_small.jpg"])
        self.assertFalse((self.work / "photos/raw/notes.txt").exists())

    def test_import_says_what_to_do_when_nothing_is_there(self):
        import os
        (self.tmp / "Empty").mkdir()
        os.environ["VB_DOWNLOADS"] = str(self.tmp / "Empty")
        self.addCleanup(os.environ.pop, "VB_DOWNLOADS", None)
        self.assertFalse(pipeline.import_photos(self.log.append))
        self.assertIn("Download all", "\n".join(self.log))

    def test_update_refuses_over_unpublished_data(self):
        (self.work / "data/resolved.csv").write_text("a,b\n9,9\n")
        self.assertFalse(pipeline.update(self.log.append))
        self.assertIn("not yet published", "\n".join(self.log))

    def test_update_returns_to_main_after_publishing(self):
        (self.work / "data/resolved.csv").write_text("a,b\n1,3\n")
        pipeline.publish(self.log.append, "review")
        self.assertTrue(pipeline.update(self.log.append))
        self.assertEqual(pipeline.branch(), "main")

    def test_branch_name(self):
        self.assertEqual(pipeline.review_branch_name(datetime(2026, 10, 31, 8, 5)), "review-20261031-0805")


if __name__ == "__main__":
    unittest.main()
