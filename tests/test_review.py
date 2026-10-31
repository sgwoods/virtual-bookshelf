"""Review page: quick-check rule, and that only this page can drive its actions.

Run:  python3 -m unittest discover -s tests
"""
import http.client
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import review  # noqa: E402


class QuickChecks(unittest.TestCase):
    def test_subtitle_dropped(self):
        self.assertTrue(review.subtitle_dropped("Serenity: Better Days", "Serenity"))
        self.assertTrue(review.subtitle_dropped("Manifold: Time", "Manifold"))
        self.assertTrue(review.subtitle_dropped("Outliers: The Story of Success", "Outliers"))

    def test_subtitle_kept_or_absent(self):
        self.assertFalse(review.subtitle_dropped("Outliers: The Story of Success",
                                                 "Outliers: The Story of Success"))
        self.assertFalse(review.subtitle_dropped("Dune", "Dune"))
        self.assertFalse(review.subtitle_dropped("Ishmael (Star Trek #23)", "Star Trek - Ishmael"))
        self.assertFalse(review.subtitle_dropped("Serenity: Better Days", ""))

    def test_quick_check_only_for_confident_matches(self):
        b = {"position": "1", "confidence": "high", "title": "Serenity: Better Days"}
        self.assertTrue(review.quick_check(b, {"status": "matched", "match_title": "Serenity"}))
        self.assertFalse(review.quick_check(b, {"status": "weak", "match_title": "Serenity"}))
        self.assertFalse(review.quick_check(dict(b, confidence="medium"),
                                            {"status": "matched", "match_title": "Serenity"}))


class AutoFind(unittest.TestCase):
    b = {"title": "Wake", "author": "Robert J. Sawyer"}

    def test_weak_and_none_look_further_on_their_own(self):
        self.assertTrue(review.auto_find(self.b, {"status": "weak"}, None))
        self.assertTrue(review.auto_find(self.b, {"status": "none"}, None))

    def test_not_when_decided_matched_quick_check_or_unreadable(self):
        self.assertFalse(review.auto_find(self.b, {"status": "weak"}, {"decision": "pick"}))
        self.assertFalse(review.auto_find(self.b, {"status": "matched"}, None))
        self.assertFalse(review.auto_find(self.b, {"status": "matched"}, None, check=True))
        self.assertFalse(review.auto_find({"title": "unknown (worn black spine)", "author": "?"},
                                          {"status": "none"}, None))


class ImageSearch(unittest.TestCase):
    def test_link_searches_title_and_first_author(self):
        url = review.image_search_url({"title": "The Best of Trek 2", "author": "Walter Irwin and G. B. Love (eds.)"})
        self.assertEqual(url, "https://www.google.com/search?udm=2&q=The+Best+of+Trek+2+Walter+Irwin")


class Restart(unittest.TestCase):
    def test_restart_keeps_options_and_does_not_open_another_tab(self):
        args = review.restart_args(["scripts/review.py", "--port", "8766"])
        self.assertEqual(args[1:], ["scripts/review.py", "--port", "8766", "--no-browser"])
        self.assertEqual(review.restart_args(["scripts/review.py", "--no-browser"])[2:], ["--no-browser"])


class PageScript(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_script_parses(self):
        # A syntax error anywhere disables every button on the page.
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(review.JS)
        r = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
        Path(f.name).unlink()
        self.assertEqual(r.returncode, 0, r.stderr)


class Guard(unittest.TestCase):
    """Other websites open in the browser must not be able to press the buttons."""

    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), review.H)
        cls.port = cls.srv.server_address[1]
        review.PORT = cls.port
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def request(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = {"Host": f"127.0.0.1:{self.port}", "Content-Type": "application/json"}
        h.update(headers or {})
        c.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
        r = c.getresponse()
        out = r.status, r.read().decode()
        c.close()
        return out

    def test_post_without_token_is_refused(self):
        code, _ = self.request("POST", "/run", {"action": "test"})
        self.assertEqual(code, 403)

    def test_post_with_wrong_token_is_refused(self):
        code, _ = self.request("POST", "/decide", {"row_id": "x", "decision": "undo"},
                               {"X-Review-Token": "not-the-token"})
        self.assertEqual(code, 403)

    def test_foreign_host_is_refused(self):
        code, _ = self.request("GET", "/job", headers={"Host": "evil.example:80"})
        self.assertEqual(code, 403)
        code, _ = self.request("POST", "/run", {"action": "test"},
                               {"Host": "evil.example:80", "X-Review-Token": review.TOKEN})
        self.assertEqual(code, 403)

    def test_search_needs_the_token(self):
        code, _ = self.request("POST", "/search", {"row_id": "x"})
        self.assertEqual(code, 403)

    def test_image_actions_need_the_token(self):
        for path in ("/downloads", "/attach", "/recrop", "/detach"):
            with self.subTest(path):
                code, _ = self.request("POST", path, {"row_id": "x", "name": "a.jpg", "kind": "cover"})
                self.assertEqual(code, 403)

    def test_publish_switch_needs_the_token(self):
        code, _ = self.request("POST", "/publish", {"row_id": "x", "kind": "cover", "on": False})
        self.assertEqual(code, 403)

    def test_bookmark_needs_its_key(self):
        import os
        os.environ.setdefault("VB_CONFIG", tempfile.mkdtemp())
        code, body = self.request("GET", "/grab?k=wrong&img=https%3A%2F%2Fexample.com%2Fa.jpg")
        self.assertEqual(code, 403)
        self.assertIn("out of date", body)

    def test_downloads_serve_only_images_there(self):
        code, _ = self.request("GET", "/downloads/..%2Fsecret.jpg")
        self.assertEqual(code, 404)

    def test_unknown_action_is_refused(self):
        code, body = self.request("POST", "/run", {"action": "rm -rf"},
                                  {"X-Review-Token": review.TOKEN})
        self.assertEqual(code, 409)
        self.assertIn("unknown", body)

    def test_restart_needs_the_token(self):
        code, _ = self.request("POST", "/restart", {})
        self.assertEqual(code, 403)

    def test_version_is_readable(self):
        review.VERSION.update(checked=__import__("time").time())     # no network in tests
        code, body = self.request("GET", "/version")
        self.assertEqual(code, 200)
        v = json.loads(body)
        self.assertEqual(set(v), {"behind", "restart_needed", "run"})

    def test_job_status_is_readable(self):
        code, body = self.request("GET", "/job")
        self.assertEqual(code, 200)
        self.assertIn("running", json.loads(body))


if __name__ == "__main__":
    unittest.main()
