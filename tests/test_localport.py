"""The shared localhost agreement: stay in the block, one copy at a time, never
touch another project's server, keep the shared registry.

Run:  python3 -m unittest discover -s tests
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import localport  # noqa: E402

FAKE = textwrap.dedent("""
    import json, os, sys
    from http.server import BaseHTTPRequestHandler, HTTPServer
    project, port = sys.argv[1], int(sys.argv[2])
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            b = json.dumps({"project": project, "port": port, "pid": os.getpid()}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers()
            self.wfile.write(b)
    s = HTTPServer(("127.0.0.1", port), H)
    print("ready", flush=True)
    s.serve_forever()
""")


def free_port_outside_block():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    return p


class Agreement(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.environ["VB_CONFIG"] = str(self.tmp / "cfg")
        os.environ["LOCAL_PORTS"] = str(self.tmp / "local-ports.tsv")
        self.saved = (localport.BLOCK, localport.DEFAULT)
        self.procs = []
        self.log = []

    def tearDown(self):
        localport.BLOCK, localport.DEFAULT = self.saved
        for p in self.procs:
            if p.poll() is None:
                p.kill(); p.wait()
        os.environ.pop("LOCAL_PORTS", None)

    def use_block(self, n=3):
        """A block of n free ports, so the tests never meet real servers."""
        for _ in range(50):
            start = free_port_outside_block()
            block = range(start, start + n)
            if all(localport.port_free(p) for p in block):
                localport.BLOCK, localport.DEFAULT = (start, start + n - 1), start
                return list(block)
        self.skipTest("no free block")

    def fake(self, project, port):
        p = subprocess.Popen([sys.executable, "-c", FAKE, project, str(port)], stdout=subprocess.PIPE, text=True)
        self.procs.append(p)
        p.stdout.readline()
        return p

    def test_ports_never_leave_the_block(self):
        self.assertEqual(localport.ports((8760, 8769), 8765), [8765, 8760, 8761, 8762, 8763, 8764, 8766, 8767, 8768, 8769])
        block = self.use_block(2)
        socks = []
        for port in block:                       # whole block busy
            s = socket.socket(); s.bind(("127.0.0.1", port)); s.listen(); socks.append(s)
        tried = []
        def make(port):
            tried.append(port)
            raise OSError("busy")
        with self.assertRaises(SystemExit):
            localport.bind(make, self.log.append)
        self.assertEqual(sorted(tried), block)
        for s in socks:
            s.close()

    def test_replaces_its_own_older_copy(self):
        port = self.use_block()[0]
        old = self.fake(localport.PROJECT, port)
        localport.state_file().parent.mkdir(parents=True)
        localport.state_file().write_text(json.dumps({"pid": old.pid, "port": port}))
        localport.stop_older_copies(self.log.append)
        old.wait(timeout=10)
        self.assertTrue(localport.port_free(port))

    def test_finds_its_own_copy_without_a_state_file(self):
        port = self.use_block()[1]
        old = self.fake(localport.PROJECT, port)
        localport.stop_older_copies(self.log.append)
        old.wait(timeout=10)

    def test_never_stops_another_projects_server(self):
        port = self.use_block()[0]
        other = self.fake("aurora", port)
        localport.state_file().parent.mkdir(parents=True)
        localport.state_file().write_text(json.dumps({"pid": other.pid, "port": port}))   # even if the file says so
        localport.stop_older_copies(self.log.append)
        time.sleep(0.3)
        self.assertIsNone(other.poll(), "another project's server must keep running")
        self.assertIn("aurora", "\n".join(self.log))

    def test_registry_adds_only_our_line_and_warns_on_overlap(self):
        rf = localport.registry_file()
        rf.write_text("name\tports\tdefault\trepo\naurora\t8780-8789\t8785\t\nnews\t8765-8774\t8770\t\n")
        localport.BLOCK = (8760, 8769)
        localport.ensure_registry(self.log.append)
        lines = rf.read_text().splitlines()
        self.assertEqual(lines[1:3], ["aurora\t8780-8789\t8785\t", "news\t8765-8774\t8770\t"])
        self.assertTrue(lines[3].startswith("virtual-bookshelf\t8760-8769\t8765"))
        self.assertIn("news", "\n".join(self.log))
        localport.ensure_registry(self.log.append)
        self.assertEqual(len(rf.read_text().splitlines()), 4, "added once")

    def test_status_reports_who_runs_where(self):
        port = self.use_block()[0]
        self.fake(localport.PROJECT, port)
        localport.registry_file().write_text(
            f"name\tports\tdefault\trepo\n{localport.PROJECT}\t{localport.BLOCK[0]}-{localport.BLOCK[1]}\t{port}\t\n")
        self.assertIn(f"running on {port}", localport.status())


if __name__ == "__main__":
    unittest.main()
