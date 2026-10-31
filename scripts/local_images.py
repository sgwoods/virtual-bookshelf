#!/usr/bin/env python3
"""Your own cover and spine images, kept on this Mac only.

The review page uses this to pick up images you saved to ~/Downloads (for
example from a Google Images search) and attach them to a book:

    images/<row id>/cover.<ext>        your preferred cover for this copy
    images/<row id>/spine.<ext>        your preferred spine image
    images/<row id>/<kind>.orig.<ext>  the download it was cropped from, kept so
                                       it can be re-cropped later

Cropping (and quarter-turn rotation) happens in the review page's browser,
which sends the cropped JPEG; nothing here needs an image library.

`images/` is git-ignored: these files are for your own displays (the local
site preview and, later, the spine shelf) and are never committed or
published. The public site keeps using Open Library covers.

Row ids look like "IMG_8879:far-right:1"; on disk the colons become "__".
Standard library only (HEIC is converted with macOS `sips` when present).
"""
from __future__ import annotations

import os, re, shutil, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "images"
KINDS = ("cover", "spine")
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif", ".heic"}
SHOWABLE = EXTS - {".heic"}               # what a browser can display directly
TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
         ".avif": "image/avif", ".gif": "image/gif"}


def downloads_dir() -> Path:
    return Path(os.environ.get("VB_DOWNLOADS", Path.home() / "Downloads"))


def folder(row_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+(:[A-Za-z0-9_.-]+)*", row_id or ""):
        raise ValueError("bad row id")
    return IMAGES / row_id.replace(":", "__")


def safe_download(name: str) -> Path:
    """A file directly inside Downloads with an image extension — nothing else."""
    if not name or name != Path(name).name or name.startswith("."):
        raise ValueError("bad file name")
    p = downloads_dir() / name
    if p.suffix.lower() not in EXTS or not p.is_file():
        raise ValueError("not an image in Downloads")
    return p


def recent_downloads(since: float = 0.0, hours: float = 6, limit: int = 12) -> list[dict]:
    """Image files in Downloads, newest first: those changed after `since` (a Unix
    time), or within the last `hours` when no time is given."""
    d = downloads_dir()
    if not d.is_dir():
        return []
    floor = since or (time.time() - hours * 3600)
    out = []
    for p in d.iterdir():
        try:
            st = p.stat()
        except OSError:
            continue
        if p.is_file() and p.suffix.lower() in EXTS and not p.name.startswith(".") and st.st_mtime >= floor:
            out.append({"name": p.name, "size": st.st_size, "mtime": st.st_mtime,
                        "showable": p.suffix.lower() in SHOWABLE})
    return sorted(out, key=lambda f: -f["mtime"])[:limit]


def _jpeg(data: bytes) -> bytes:
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("cropped image must be a JPEG")
    return data


def attach(row_id: str, name: str, kind: str, cropped: bytes | None = None) -> str:
    """Move a downloaded image into images/<row>/, as <kind>.orig.<ext>, and make
    <kind>.<ext> from it — the browser's crop if one was sent, else the whole
    image. Replaces any earlier image of that kind. Returns the displayed file's
    path relative to the project."""
    if kind not in KINDS:
        raise ValueError("kind must be cover or spine")
    src, dest_dir = safe_download(name), folder(row_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    for old in dest_dir.glob(f"{kind}.*"):
        old.unlink()
    ext = src.suffix.lower()
    if ext == ".heic" and shutil.which("sips"):
        orig = dest_dir / f"{kind}.orig.jpg"
        subprocess.run(["sips", "-s", "format", "jpeg", str(src), "--out", str(orig)],
                       check=True, capture_output=True)
        src.unlink()
    else:
        orig = dest_dir / f"{kind}.orig{ext}"
        shutil.move(str(src), str(orig))
    if cropped:
        final = dest_dir / f"{kind}.jpg"
        final.write_bytes(_jpeg(cropped))
    else:
        final = dest_dir / f"{kind}{orig.suffix}"
        shutil.copyfile(orig, final)
    return str(final.relative_to(ROOT))


def recrop(row_id: str, kind: str, cropped: bytes) -> str:
    """Replace <kind> with a new crop (made in the browser from the kept original)."""
    if kind not in KINDS:
        raise ValueError("kind must be cover or spine")
    d = folder(row_id)
    for old in d.glob(f"{kind}.*"):
        if ".orig." not in old.name:
            old.unlink()
    final = d / f"{kind}.jpg"
    final.write_bytes(_jpeg(cropped))
    return str(final.relative_to(ROOT))


def original(row_id: str, kind: str) -> str:
    """The kept original for re-cropping (or the current image if none was kept)."""
    d = folder(row_id)
    for p in sorted(d.glob(f"{kind}.orig.*")) if d.is_dir() else []:
        return str(p.relative_to(ROOT))
    return images_for(row_id).get(kind, "")


def detach(row_id: str, kind: str) -> None:
    if kind not in KINDS:
        raise ValueError("kind must be cover or spine")
    for old in folder(row_id).glob(f"{kind}.*"):
        old.unlink()


def images_for(row_id: str) -> dict[str, str]:
    """{'cover': 'images/…/cover.jpg', 'spine': …} for the kinds this row has."""
    d = folder(row_id)
    found = {}
    for kind in KINDS:
        for p in sorted(d.glob(f"{kind}.*")) if d.is_dir() else []:
            if ".orig." not in p.name:
                found[kind] = str(p.relative_to(ROOT))
    return found


def all_images() -> dict[str, dict[str, str]]:
    """Every row that has images of its own, keyed by row id."""
    if not IMAGES.is_dir():
        return {}
    out = {}
    for d in IMAGES.iterdir():
        if d.is_dir():
            rid = d.name.replace("__", ":")
            found = images_for(rid)
            if found:
                out[rid] = found
    return out


def serve_path(rel: str) -> Path:
    """Resolve an /images/… request to a file inside images/, or raise."""
    p = (IMAGES / rel).resolve()
    if IMAGES.resolve() not in p.parents or p.suffix.lower() not in SHOWABLE or not p.is_file():
        raise ValueError("not found")
    return p
