"""Own images: picked up from Downloads, cropped, kept on this Mac only.

Run:  python3 -m unittest discover -s tests
"""
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_site      # noqa: E402
import local_images    # noqa: E402
import review          # noqa: E402

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64          # enough of a JPEG for these tests
CROP = b"\xff\xd8\xff\xdbcropped"
ROW = "IMG_8879:far-right:1"


class OwnImages(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.dl = self.tmp / "Downloads"
        self.dl.mkdir()
        os.environ["VB_DOWNLOADS"] = str(self.dl)
        self._root, self._images = local_images.ROOT, local_images.IMAGES
        local_images.ROOT, local_images.IMAGES = self.tmp, self.tmp / "images"

    def tearDown(self):
        os.environ.pop("VB_DOWNLOADS", None)
        local_images.ROOT, local_images.IMAGES = self._root, self._images
        shutil.rmtree(self.tmp, ignore_errors=True)

    def download(self, name, data=JPEG, age=0):
        p = self.dl / name
        p.write_bytes(data)
        if age:
            t = time.time() - age
            os.utime(p, (t, t))
        return p

    def test_recent_downloads_are_images_newest_first(self):
        self.download("old.jpg", age=3600)
        self.download("new.webp")
        self.download("notes.pdf")
        self.download(".hidden.jpg")
        self.assertEqual([f["name"] for f in local_images.recent_downloads()], ["new.webp", "old.jpg"])
        since = time.time() - 60
        self.assertEqual([f["name"] for f in local_images.recent_downloads(since)], ["new.webp"])

    def test_attach_with_crop_keeps_the_original(self):
        self.download("trek.jpg")
        rel = local_images.attach(ROW, "trek.jpg", "spine", CROP)
        d = self.tmp / "images" / "IMG_8879__far-right__1"
        self.assertEqual(rel, "images/IMG_8879__far-right__1/spine.jpg")
        self.assertEqual((d / "spine.jpg").read_bytes(), CROP)
        self.assertEqual((d / "spine.orig.jpg").read_bytes(), JPEG)
        self.assertFalse((self.dl / "trek.jpg").exists(), "moved out of Downloads")
        self.assertEqual(local_images.images_for(ROW), {"spine": rel})
        self.assertEqual(local_images.original(ROW, "spine"), "images/IMG_8879__far-right__1/spine.orig.jpg")

    def test_attach_whole_image_and_replace(self):
        self.download("a.png", b"\x89PNG first")
        local_images.attach(ROW, "a.png", "cover")
        self.download("b.jpg")
        local_images.attach(ROW, "b.jpg", "cover")
        d = self.tmp / "images" / "IMG_8879__far-right__1"
        self.assertEqual(sorted(p.name for p in d.iterdir()), ["cover.jpg", "cover.orig.jpg"])

    def test_recrop_replaces_only_the_crop(self):
        self.download("trek.jpg")
        local_images.attach(ROW, "trek.jpg", "cover")
        local_images.recrop(ROW, "cover", CROP)
        d = self.tmp / "images" / "IMG_8879__far-right__1"
        self.assertEqual((d / "cover.jpg").read_bytes(), CROP)
        self.assertEqual((d / "cover.orig.jpg").read_bytes(), JPEG)

    def test_detach(self):
        self.download("trek.jpg")
        local_images.attach(ROW, "trek.jpg", "cover")
        local_images.detach(ROW, "cover")
        self.assertEqual(local_images.images_for(ROW), {})

    def test_only_files_directly_in_downloads(self):
        for bad in ("../secret.jpg", "sub/x.jpg", "", ".hidden.jpg", "notes.pdf"):
            with self.subTest(bad), self.assertRaises(ValueError):
                local_images.safe_download(bad)
        with self.assertRaises(ValueError):
            local_images.folder("../../etc")
        with self.assertRaises(ValueError):
            local_images.serve_path("../scripts/review.py")

    def test_crop_must_be_jpeg(self):
        self.download("trek.jpg")
        with self.assertRaises(ValueError):
            local_images.attach(ROW, "trek.jpg", "cover", b"<svg/>")

    def test_data_url_parsing(self):
        self.assertIsNone(review.jpeg_from_data_url(""))
        self.assertEqual(review.jpeg_from_data_url("data:image/jpeg;base64,/9j/"), b"\xff\xd8\xff")
        with self.assertRaises(ValueError):
            review.jpeg_from_data_url("data:image/svg+xml;base64,PHN2Zy8+")


class SiteUsesOwnImagesOnlyLocally(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._images = local_images.IMAGES
        local_images.IMAGES = self.tmp / "images"
        self._root = local_images.ROOT
        local_images.ROOT = self.tmp
        d = local_images.folder(ROW)
        d.mkdir(parents=True)
        (d / "cover.jpg").write_bytes(JPEG)

    def tearDown(self):
        local_images.IMAGES, local_images.ROOT = self._images, self._root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def cover_of_trek(self, **kw):
        n = build_site.build(self.tmp / "out", **kw)
        return [c for c in n["cards"] if c["t"] == "The Best of Trek 2"][0]["c"]

    def test_public_build_ignores_own_images(self):
        self.assertFalse(self.cover_of_trek().startswith("../images/"))

    def test_local_preview_uses_them(self):
        self.assertEqual(self.cover_of_trek(local_images=True), "../images/IMG_8879__far-right__1/cover.jpg")


if __name__ == "__main__":
    unittest.main()
