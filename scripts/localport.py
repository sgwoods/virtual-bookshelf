"""The shared localhost agreement between Steven's projects.

Each project owns a block of ten ports and runs one copy at a time:

    8760–8769  virtual-bookshelf   (default 8765)
    8770–8779  news pipeline       (default 8775)
    8780–8789  aurora              (default 8785)
    8790–8799  Star Swarm (game)   (default 8795)

On start, the review page (1) stops an older copy of itself — found from
~/.config/virtual-bookshelf/server.json and confirmed by its /whoami, or, for
copies from before this agreement, by being this repository's review.py — and
never touches another project's server; (2) binds only inside its block,
default first; (3) records itself in server.json and makes sure the shared
registry ~/.config/local-ports.tsv lists it, warning if blocks overlap.

    python3 scripts/review.py --status    # which of the projects are running, where

Standard library only.
"""
from __future__ import annotations

import json, os, signal, socket, subprocess, time, urllib.request
from pathlib import Path

PROJECT = "virtual-bookshelf"
BLOCK = (8760, 8769)
DEFAULT = 8765
ROOT = Path(__file__).resolve().parent.parent
REGISTRY_HEADER = "name\tports\tdefault\trepo"
LINE = (PROJECT, f"{BLOCK[0]}-{BLOCK[1]}", str(DEFAULT), "github.com/sgwoods/virtual-bookshelf")


def config_dir() -> Path:
    return Path(os.environ.get("VB_CONFIG") or Path.home() / ".config/virtual-bookshelf")


def state_file() -> Path:
    return config_dir() / "server.json"


def registry_file() -> Path:
    return Path(os.environ.get("LOCAL_PORTS") or Path.home() / ".config/local-ports.tsv")


def ports(block=None, default=None) -> list[int]:
    """The ports to try, default first, never outside the block."""
    block, default = block or BLOCK, default or DEFAULT
    return [default] + [p for p in range(block[0], block[1] + 1) if p != default]


def whoami(port: int, timeout: float = 1.0) -> dict | None:
    """What a local server on this port says it is (None if nothing, or no /whoami)."""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/whoami")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=timeout) as r:
            d = json.load(r)
        return d if isinstance(d, dict) and d.get("project") else None
    except Exception:
        return None


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def port_free(port: int) -> bool:
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)     # as the servers bind (ignores TIME_WAIT)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def listener_pid(port: int) -> int:
    """The process listening on this port (macOS/Linux lsof), or 0."""
    try:
        out = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
                             capture_output=True, text=True, timeout=5).stdout.split()
        return int(out[0]) if out else 0
    except Exception:
        return 0


def is_our_old_copy(pid: int) -> bool:
    """A copy of this repository's review.py from before /whoami existed:
    its command runs scripts/review.py and its working folder is this repo."""
    try:
        cmd = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True,
                             timeout=5).stdout
        if "scripts/review.py" not in cmd and str(ROOT / "scripts/review.py") not in cmd:
            return False
        cwd = subprocess.run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"], capture_output=True, text=True,
                             timeout=5).stdout
        return any(line[1:] and Path(line[1:]).resolve() == ROOT for line in cwd.splitlines() if line.startswith("n"))
    except Exception:
        return False


def stop(pid: int, port: int, log=print, wait: float = 5.0) -> bool:
    """Ask a process to stop (SIGTERM), then insist (SIGKILL); wait for its port."""
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    end = time.time() + wait
    while time.time() < end and alive(pid):
        time.sleep(0.1)
    if alive(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        time.sleep(0.3)
    end = time.time() + wait
    while time.time() < end and not port_free(port):
        time.sleep(0.1)
    return port_free(port)


def stop_older_copies(log=print) -> None:
    """Stop any older copy of this project; never anything else."""
    me = os.getpid()
    seen = set()
    sf = state_file()
    if sf.exists():
        try:
            d = json.loads(sf.read_text())
            pid, port = int(d.get("pid", 0)), int(d.get("port", 0))
        except Exception:
            pid, port = 0, 0
        if pid and pid != me and alive(pid) and port:
            w = whoami(port)
            if w and w.get("project") == PROJECT and int(w.get("pid", 0)) == pid:
                log(f"Stopping the older {PROJECT} page (pid {pid}, port {port})…")
                stop(pid, port, log)
                seen.add(port)
    for port in ports():
        if port in seen or port_free(port):
            continue
        w = whoami(port)
        if w:
            pid = int(w.get("pid", 0))
            if w.get("project") == PROJECT and pid and pid != me:
                log(f"Stopping the older {PROJECT} page (pid {pid}, port {port})…")
                stop(pid, port, log)
            elif w.get("project") != PROJECT:
                log(f"Port {port} is used by {w.get('project')} — leaving it alone.")
            continue
        pid = listener_pid(port)
        if pid and pid != me and is_our_old_copy(pid):
            log(f"Stopping an older review page from before the port agreement (pid {pid}, port {port})…")
            stop(pid, port, log)


def bind(make_server, log=print):
    """Bind inside the block, default first. Returns (server, port) or raises SystemExit."""
    for port in ports():
        try:
            return make_server(port), port
        except OSError:
            w = whoami(port)
            log(f"Port {port} is busy" + (f" ({w['project']})" if w else "") + " — trying the next one in the block.")
    held = []
    for port in ports():
        w = whoami(port)
        pid = listener_pid(port)
        held.append(f"  {port}: " + (w["project"] if w else "unknown program") + (f" (pid {pid})" if pid else ""))
    raise SystemExit(f"All {PROJECT} ports {BLOCK[0]}–{BLOCK[1]} are busy:\n" + "\n".join(held))


def record(port: int, version: str = "") -> None:
    sf = state_file()
    sf.parent.mkdir(parents=True, exist_ok=True)
    sf.write_text(json.dumps({"project": PROJECT, "pid": os.getpid(), "port": port,
                              "started": time.strftime("%Y-%m-%d %H:%M:%S"), "version": version}))


def forget() -> None:
    """Remove server.json on a clean exit (only if it is still ours)."""
    sf = state_file()
    try:
        if json.loads(sf.read_text()).get("pid") == os.getpid():
            sf.unlink()
    except Exception:
        pass


def read_registry() -> list[list[str]]:
    rf = registry_file()
    if not rf.exists():
        return []
    rows = [l.split("\t") for l in rf.read_text().splitlines() if l.strip() and not l.startswith("name\t")]
    return [r for r in rows if len(r) >= 2]


def ensure_registry(log=print) -> None:
    """Add this project's line (each project adds its own); never change other
    projects' lines; warn about overlaps."""
    rf = registry_file()
    rows = read_registry()
    if not rf.exists():
        rf.parent.mkdir(parents=True, exist_ok=True)
        rf.write_text(REGISTRY_HEADER + "\n" + "\t".join(LINE) + "\n")
        rows = read_registry()
    elif PROJECT not in {r[0] for r in rows}:
        text = rf.read_text()
        rf.write_text(text + ("" if text.endswith("\n") or not text else "\n") + "\t".join(LINE) + "\n")
        rows = read_registry()
    for r in rows:
        if r[0] == PROJECT:
            continue
        try:
            a, b = (int(x) for x in r[1].split("-"))
        except ValueError:
            continue
        if a <= BLOCK[1] and b >= BLOCK[0]:
            log(f"Warning: {r[0]}'s ports {r[1]} overlap {PROJECT}'s {BLOCK[0]}-{BLOCK[1]} in {rf}.")


def status() -> str:
    """Which registered projects are running, on which port, which version."""
    rows = read_registry() or [list(LINE)]
    out = []
    for r in rows:
        try:
            a, b = (int(x) for x in r[1].split("-"))
        except ValueError:
            continue
        dflt = int(r[2]) if len(r) > 2 and r[2].isdigit() else a
        found = []
        for port in ports((a, b), dflt):
            if port_free(port):
                continue
            w = whoami(port, 0.5)
            if w and w.get("project") == r[0]:
                found.append(f"running on {port} (pid {w.get('pid')}, version {w.get('version') or '?'})")
            elif w:
                found.append(f"port {port} held by {w.get('project')}!")
            else:
                found.append(f"port {port} busy (no /whoami — an older copy or another program)")
        out.append(f"{r[0]:<18} {r[1]:<10} " + ("; ".join(found) if found else "not running"))
    return "\n".join(out)
