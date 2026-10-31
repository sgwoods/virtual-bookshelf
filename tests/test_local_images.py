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
        self.assertEqual(sorted(p.name for p in d.iterdir()), ["cover.jpg", "cover.orig.jpg", "meta.json"])

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


class Sources(unittest.TestCase):
    """Where an image came from is captured without anyone typing it."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "Downloads").mkdir()
        os.environ["VB_DOWNLOADS"] = str(self.tmp / "Downloads")
        os.environ["VB_CONFIG"] = str(self.tmp / "config")
        self._root, self._images = local_images.ROOT, local_images.IMAGES
        local_images.ROOT, local_images.IMAGES = self.tmp, self.tmp / "images"

    def tearDown(self):
        for k in ("VB_DOWNLOADS", "VB_CONFIG"):
            os.environ.pop(k, None)
        local_images.ROOT, local_images.IMAGES = self._root, self._images
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_macos_where_from_record(self):
        import plistlib
        raw = plistlib.dumps(["https://i.ebayimg.com/images/trek2.jpg", "https://www.ebay.com/itm/123"],
                             fmt=plistlib.FMT_BINARY).hex()
        got = local_images.parse_where_froms(" ".join(raw[i:i + 2] for i in range(0, len(raw), 2)))
        self.assertEqual(got, {"image_url": "https://i.ebayimg.com/images/trek2.jpg",
                               "page_url": "https://www.ebay.com/itm/123"})
        self.assertEqual(local_images.parse_where_froms("not hex"), {})

    def fake_fetch(self, ctype="image/jpeg", data=JPEG):
        class R:
            headers = {"Content-Type": ctype}
            def read(self, n): return data
            def __enter__(self): return self
            def __exit__(self, *a): return False
        real = local_images.urllib.request.urlopen
        local_images.urllib.request.urlopen = lambda req, timeout=0: R()
        self.addCleanup(setattr, local_images.urllib.request, "urlopen", real)

    def test_bookmark_grab_saves_to_downloads_with_its_source(self):
        self.fake_fetch()
        name = local_images.grab("https://i.ebayimg.com/images/trek2.jpg", "https://www.ebay.com/itm/123")
        self.assertTrue((self.tmp / "Downloads" / name).is_file())
        [f] = local_images.recent_downloads()
        self.assertEqual((f["name"], f["source"]), (name, "ebay.com"))
        local_images.attach(ROW, name, "cover", CROP)
        self.assertEqual(local_images.describe(ROW, "cover"),
                         {"source": "ebay.com", "source_url": "https://www.ebay.com/itm/123", "published": True})

    def test_grab_refuses_non_images_and_non_web_addresses(self):
        self.fake_fetch(ctype="text/html", data=b"<html>")
        with self.assertRaises(ValueError):
            local_images.grab("https://example.com/page")
        with self.assertRaises(ValueError):
            local_images.grab("file:///etc/passwd")

    def test_grab_key_is_stable(self):
        self.assertEqual(local_images.grab_key(), local_images.grab_key())
        self.assertGreaterEqual(len(local_images.grab_key()), 20)


class Publishing(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._root, self._images = local_images.ROOT, local_images.IMAGES
        local_images.ROOT, local_images.IMAGES = self.tmp, self.tmp / "images"
        d = local_images.folder(ROW)
        d.mkdir(parents=True)
        (d / "cover.jpg").write_bytes(CROP)
        (d / "cover.orig.jpg").write_bytes(JPEG)
        (d / "spine.jpg").write_bytes(CROP)
        local_images.write_meta(ROW, {"cover": {"image_url": "https://i.ebayimg.com/a.jpg",
                                                "page_url": "https://www.ebay.com/itm/1", "published": True},
                                      "spine": {"published": False}})

    def tearDown(self):
        local_images.ROOT, local_images.IMAGES = self._root, self._images
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_only_published_images_are_exported_with_their_source(self):
        n = local_images.export_published(self.tmp, log=lambda *_: None)
        self.assertEqual(n, 1)
        pub = local_images.published(self.tmp)
        self.assertEqual(list(pub), [ROW])
        self.assertEqual(set(pub[ROW]), {"cover"})
        self.assertEqual(pub[ROW]["cover"]["source"], "ebay.com")
        self.assertTrue((self.tmp / pub[ROW]["cover"]["file"]).is_file())
        self.assertFalse(any("orig" in p.name for p in (self.tmp / "site_images").rglob("*")))

    def test_unpublishing_removes_the_copy(self):
        local_images.export_published(self.tmp, log=lambda *_: None)
        local_images.set_published(ROW, "cover", False)
        local_images.export_published(self.tmp, log=lambda *_: None)
        self.assertEqual(local_images.published(self.tmp), {})
        self.assertFalse(any(p.is_file() for p in (self.tmp / "site_images").rglob("*")))

    def test_public_build_uses_published_images_with_credit(self):
        local_images.export_published(self.tmp, log=lambda *_: None)
        real = build_site.ROOT
        build_site.ROOT = self.tmp
        self.addCleanup(setattr, build_site, "ROOT", real)
        out = self.tmp / "out"
        n = build_site.build(out)
        trek = [c for c in n["cards"] if c["t"] == "The Best of Trek 2"][0]
        self.assertTrue(trek["c"].startswith("site_images/"))
        self.assertEqual((trek["is"], trek["iu"]), ("ebay.com", "https://www.ebay.com/itm/1"))
        self.assertTrue((out / trek["c"]).is_file(), "images copied into the site")
