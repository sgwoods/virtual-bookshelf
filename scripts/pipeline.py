#!/usr/bin/env python3
"""Everyday local actions, from the command line or the review page's buttons.

Usage:
    python3 scripts/pipeline.py status    # counts, branch, unpublished data
    python3 scripts/pipeline.py update    # get the latest from GitHub (main)
    python3 scripts/pipeline.py retry     # re-run weak/none lookups (uses the network)
    python3 scripts/pipeline.py apply     # fold review decisions into data/resolved.csv
    python3 scripts/pipeline.py build     # build the site into _site/
    python3 scripts/pipeline.py test      # run the test suite
    python3 scripts/pipeline.py publish   # commit data/ on a review branch and push it
    python3 scripts/pipeline.py save      # apply, then publish
    python3 scripts/pipeline.py finish    # apply → build → test → publish, then preview

`finish` is the one command to run after a review session. It stops at the
first step that fails and says why. `publish` never commits to main: it puts
the data on a review-YYYYMMDD-HHMM branch (or the review branch you are on),
pushes it, and prints the link to open the pull request. First it writes
web-sized copies of your published images to site_images/ and their sources
to data/images.csv. It only ever adds data/books.csv, data/resolved.csv,
data/overrides.csv, data/images.csv and site_images/ — never shelf photos,
full-size originals (images/), credentials or data/reading.csv.

Standard library only.
"""
from __future__ import annotations

import csv, re, shutil, subprocess, sys, zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
REPO_URL = "https://github.com/sgwoods/virtual-bookshelf"
DATA_FILES = ("data/books.csv", "data/resolved.csv", "data/overrides.csv",
              "data/images.csv", "site_images")   # the last two: your published images
Log = Callable[[str], None]


# ---------------------------------------------------------------- helpers
def run(cmd: list[str], log: Log) -> bool:
    """Run a command in the repo, streaming its output to log. True if it succeeded."""
    log("$ " + " ".join(c if " " not in c else repr(c) for c in cmd))
    try:
        p = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, bufsize=1)
    except OSError as e:
        log(f"could not start: {e}")
        return False
    with p.stdout:
        for line in p.stdout:
            log(line.rstrip("\n"))
    return p.wait() == 0


def git(*args: str) -> str:
    """Quiet git query; returns stdout ('' on failure)."""
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def branch() -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD")


def data_changes() -> list[str]:
    """Data files with uncommitted changes (modified or new)."""
    out = git("status", "--porcelain", "--untracked-files=all", "--", *DATA_FILES)
    return [line[3:] for line in out.splitlines() if line.strip()]


def review_branch_name(now: datetime | None = None) -> str:
    return f"review-{(now or datetime.now()):%Y%m%d-%H%M}"


def compare_url(br: str) -> str:
    return f"{REPO_URL}/compare/main...{br}?expand=1"


def status() -> dict:
    """Numbers for the review page header and `pipeline.py status`."""
    res = ROOT / "data/resolved.csv"
    ov = ROOT / "data/overrides.csv"
    lookup = Counter(r.get("status") or "?" for r in csv.DictReader(open(res, encoding="utf-8"))) if res.exists() else Counter()
    decisions = sum(1 for _ in csv.DictReader(open(ov, encoding="utf-8"))) if ov.exists() else 0
    return {"lookup": dict(lookup), "decisions": decisions, "branch": branch(),
            "unpublished": data_changes()}


# ---------------------------------------------------------------- actions
def update(log: Log) -> bool:
    """Switch to main and fast-forward it from GitHub."""
    changes, br = data_changes(), branch()
    if changes:
        log(f"Not updating: review data not yet published on '{br}': {', '.join(changes)}.")
        log("Publish it first (Save & push), then update.")
        return False
    if br != "main" and not run(["git", "switch", "main"], log):
        return False
    return run(["git", "pull", "--ff-only"], log)


def behind() -> int:
    """How many commits GitHub's main has that this checkout does not (fetches first).
    -1 if GitHub could not be reached."""
    r = subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        return -1
    n = git("rev-list", "--count", "HEAD..origin/main")
    return int(n) if n.isdigit() else -1


def update_code(log: Log) -> bool:
    """Bring in the newest version from GitHub without disturbing review work.

    On main: fast-forward. On a review branch with nothing unpublished: back to
    main and fast-forward. On a review branch with unpublished data: merge main
    into it, so the data stays where it is."""
    if not run(["git", "fetch", "origin", "main"], log):
        return False
    br = branch()
    if br == "main":
        return run(["git", "merge", "--ff-only", "origin/main"], log)
    if not data_changes():
        return run(["git", "switch", "main"], log) and run(["git", "merge", "--ff-only", "origin/main"], log)
    log(f"Keeping your unpublished review data on '{br}' and bringing the new version into it.")
    return run(["git", "merge", "--no-edit", "origin/main"], log)


def retry(log: Log) -> bool:
    return run([PY, "scripts/resolve.py", "--retry"], log)


def apply(log: Log) -> bool:
    return run([PY, "scripts/resolve.py"], log)


def build(log: Log) -> bool:
    """Local preview build: includes your own images/ (CI builds without them)."""
    return run([PY, "scripts/build_site.py", "--local-images"], log)


def test(log: Log) -> bool:
    return run([PY, "-m", "unittest", "discover", "-s", "tests"], log)


def publish(log: Log, message: str = "") -> bool:
    """Publish your images (web-sized copies + sources), then commit the data
    files on a review branch and push it."""
    import local_images
    local_images.export_published(ROOT, log)
    changes = data_changes()
    if not changes:
        log("Nothing to publish: no changes in " + ", ".join(DATA_FILES) + ".")
        return True
    br = branch()
    if br in ("main", "HEAD", ""):
        br = review_branch_name()
        if not run(["git", "switch", "-c", br], log):
            return False
    s = status()
    lk = s["lookup"]
    message = message or (f"Review pass: {s['decisions']} decisions; "
                          f"matched {lk.get('matched', 0)}, confirmed {lk.get('confirmed', 0)}, "
                          f"weak {lk.get('weak', 0)}, none {lk.get('none', 0)}")
    files = [f for f in DATA_FILES if (ROOT / f).exists() or git("ls-files", "--", f)]
    ok = (run(["git", "add", "-A", "--", *files], log)
          and run(["git", "commit", "-m", message, "--", *files], log)
          and run(["git", "push", "-u", "origin", br], log))
    if ok:
        log("")
        log("Pushed. Open the pull request here:")
        log(compare_url(br))
    return ok


PHOTO_NAME = re.compile(r"^IMG_\d+\.(heic|jpe?g|png)$", re.I)


def import_photos(log: Log) -> bool:
    """Shelf photos from Downloads into photos/: the newest Drive download (a .zip
    of the folder) or loose IMG_*.HEIC files. Converts each with macOS `sips` to
    photos/jpg/NAME.jpg (for zooming) and NAME_small.jpg (1600 px, for cards).
    photos/ is git-ignored; the photos stay private."""
    import local_images
    dl, raw, jpg = local_images.downloads_dir(), ROOT / "photos/raw", ROOT / "photos/jpg"
    raw.mkdir(parents=True, exist_ok=True)
    jpg.mkdir(parents=True, exist_ok=True)
    got = 0
    zips = sorted((p for p in dl.glob("*.zip") if p.is_file()), key=lambda p: -p.stat().st_mtime) if dl.is_dir() else []
    for z in zips[:3]:
        with zipfile.ZipFile(z) as zf:
            members = [m for m in zf.namelist() if PHOTO_NAME.match(Path(m).name)]
            for m in members:
                (raw / Path(m).name).write_bytes(zf.read(m))
            if members:
                log(f"{z.name}: {len(members)} photos")
                got += len(members)
    for p in dl.glob("IMG_*") if dl.is_dir() else []:
        if PHOTO_NAME.match(p.name):
            shutil.copyfile(p, raw / p.name)
            got += 1
    if not got and not any(raw.iterdir()):
        log("No shelf photos found in Downloads. Open the Drive folder, choose Download all, "
            "and press Import shelf photos again once the .zip has arrived.")
        return False
    sips = shutil.which("sips")
    made = 0
    for p in sorted(raw.iterdir()):
        if not PHOTO_NAME.match(p.name):
            continue
        name = p.stem
        for out, size in ((jpg / f"{name}.jpg", 4000), (jpg / f"{name}_small.jpg", 1600)):
            if out.exists():
                continue
            if sips:
                r = subprocess.run([ "sips", "-s", "format", "jpeg", "-Z", str(size), str(p), "--out", str(out)],
                                   capture_output=True, text=True)
                if r.returncode != 0:
                    log(f"could not convert {p.name}: {r.stderr.strip()[:200]}")
                    continue
            elif p.suffix.lower() in (".jpg", ".jpeg"):
                shutil.copyfile(p, out)
            else:
                continue
            made += 1
    log(f"Shelf photos ready: {len(list(jpg.glob('*_small.jpg')))} (converted {made} files) in photos/jpg/")
    return True


def preview(log: Log) -> bool:
    page = ROOT / "_site/index.html"
    if sys.platform == "darwin" and page.exists():
        return run(["open", str(page)], log)
    log(f"Preview: {page}")
    return True


STEPS: dict[str, Callable[[Log], bool]] = {
    "update": update, "retry": retry, "apply": apply, "build": build,
    "test": test, "publish": publish,
}


def finish(log: Log) -> bool:
    """apply → build → test → publish, stopping at the first failure; then preview."""
    for name in ("apply", "build", "test", "publish"):
        log(f"\n== {name}")
        if not STEPS[name](log):
            log(f"\nStopped: '{name}' failed. Nothing after it ran.")
            return False
    preview(log)
    log("\nDone.")
    return True


def save(log: Log) -> bool:
    """apply → publish: fold decisions in, then commit and push the data."""
    return apply(log) and publish(log)


STEPS["finish"] = finish
STEPS["update_code"] = update_code
STEPS["import_photos"] = import_photos
STEPS["save"] = save


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in (*STEPS, "status"):
        print(__doc__)
        sys.exit(2)
    if sys.argv[1] == "status":
        s = status()
        print(f"branch: {s['branch']}")
        print("lookup: " + "  ".join(f"{k} {v}" for k, v in sorted(s["lookup"].items())))
        print(f"review decisions: {s['decisions']}")
        print("unpublished data: " + (", ".join(s["unpublished"]) or "none"))
        return
    sys.exit(0 if STEPS[sys.argv[1]](print) else 1)


if __name__ == "__main__":
    main()
