"""Pictures from the web on the review page: reading Bing's and DuckDuckGo's
results, falling back between them, caching, and pasted images.

Run:  python3 -m unittest discover -s tests
"""
import base64
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import image_search  # noqa: E402
import local_images  # noqa: E402

BING = """<div class="imgpt"><a class="iusc" style="height:180px" m="{&quot;cid&quot;:&quot;x&quot;,
&quot;purl&quot;:&quot;https://www.ebay.com/itm/123&quot;,&quot;murl&quot;:&quot;https://i.ebayimg.com/images/g/a/s-l1600.jpg&quot;,
&quot;turl&quot;:&quot;https://tse1.mm.bing.net/th?id=OIP.abc&amp;pid=Api&quot;,&quot;t&quot;:&quot;The Best of Trek 2 &amp;amp; more&quot;}"
 href="/images/search?view=detailV2"></a></div>
<a class="iusc" m="{&quot;murl&quot;:&quot;javascript:alert(1)&quot;}"></a>
<a class="iusc" m="{not json}"></a>"""


class Parsing(unittest.TestCase):
    def test_bing_results_carry_image_page_and_thumbnail(self):
        r = image_search.parse_bing(BING)
        self.assertEqual(len(r), 1, "non-web addresses and broken entries are dropped")
        self.assertEqual(r[0]["image"], "https://i.ebayimg.com/images/g/a/s-l1600.jpg")
        self.assertEqual(r[0]["page"], "https://www.ebay.com/itm/123")
        self.assertEqual(r[0]["thumb"], "https://tse1.mm.bing.net/th?id=OIP.abc&pid=Api")
        self.assertEqual(r[0]["title"], "The Best of Trek 2 & more")

    def test_duckduckgo(self):
        self.assertEqual(image_search.parse_ddg_token("...vqd='4-12345678901234567890'..."), "4-12345678901234567890")
        self.assertEqual(image_search.parse_ddg_token('vqd="4-99"'), "4-99")
        r = image_search.parse_ddg({"results": [{"image": "https://a.com/x.jpg", "url": "https://a.com/p",
                                                 "thumbnail": "https://t.com/x", "title": "X", "width": 500,
                                                 "height": 800}, {"image": "data:image/png;base64,AA"}]})
        self.assertEqual([x["image"] for x in r], ["https://a.com/x.jpg"])


class Search(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.saved = (image_search.CACHE, image_search.bing, image_search.ddg)
        image_search.CACHE = self.tmp
        self.calls = []

    def tearDown(self):
        image_search.CACHE, image_search.bing, image_search.ddg = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fake(self, name, result):
        def fn(q, *a):
            self.calls.append(name)
            if isinstance(result, Exception):
                raise result
            return result
        return fn

    def test_falls_back_to_duckduckgo_and_caches(self):
        image_search.bing = self.fake("bing", OSError("blocked"))
        image_search.ddg = self.fake("ddg", [{"image": "https://www.abebooks.com/a.jpg", "page": "", "thumb": "t",
                                               "title": ""}] * 2)
        r = image_search.search("  Wake   Robert J. Sawyer ")
        self.assertEqual((r["source"], len(r["results"]), r["results"][0]["host"]), ("DuckDuckGo", 1, "abebooks.com"))
        self.assertEqual(r["query"], "Wake Robert J. Sawyer")
        image_search.search("wake robert j. sawyer")
        self.assertEqual(self.calls, ["bing", "ddg"], "the second search came from the cache")

    def test_reports_why_nothing_was_found(self):
        image_search.bing = self.fake("bing", [])
        image_search.ddg = self.fake("ddg", OSError("offline"))
        r = image_search.search("x")
        self.assertEqual(r["results"], [])
        self.assertIn("offline", r["error"])
        self.assertEqual(image_search.search("")["error"], "nothing to search for")


class Paste(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.environ["VB_DOWNLOADS"] = str(self.tmp)

    def tearDown(self):
        os.environ.pop("VB_DOWNLOADS", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pasted_picture_lands_in_downloads(self):
        name = local_images.save_pasted("data:image/png;base64," + base64.b64encode(b"\x89PNG fake").decode())
        self.assertTrue(name.endswith(".png"))
        self.assertEqual(local_images.safe_download(name).read_bytes(), b"\x89PNG fake")

    def test_only_pictures(self):
        for bad in ("data:text/html;base64,PGI+", "hello", "data:image/png,notbase64"):
            with self.subTest(bad), self.assertRaises(ValueError):
                local_images.save_pasted(bad)


if __name__ == "__main__":
    unittest.main()
