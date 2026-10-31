#!/usr/bin/env python3
"""Your own cover and spine images: picked up, cropped, sourced, published.

The review page uses this to pick up images in ~/Downloads — saved there by
you, or sent by the "Add to bookshelf" bookmark — and attach them to a book:

    images/<row id>/cover.<ext>        your preferred cover for this copy
    images/<row id>/spine.<ext>        your preferred spine image
    images/<row id>/<kind>.orig.<ext>  the download it was cropped from, kept so
                                       it can be re-cropped later
    images/<row id>/meta.json          per kind: where it came from (image and
                                       page address), whether to publish it

`images/` is git-ignored: full-size originals stay on this Mac. Where an image
came from is read automatically — from the bookmark's request, or from the
"Where from" record macOS keeps for every browser download.

Publishing (`export_published`, run by Save & push and Finish) writes a
web-sized copy of each published image to site_images/<row id>/<kind>.jpg and
a list with sources to data/images.csv; both are committed and the public
site uses them in place of missing covers, naming the source.

Cropping (and quarter-turn rotation) happens in the review page's browser,
which sends the cropped JPEG. Resizing and HEIC conversion use macOS `sips`
when present. Row ids look like "IMG_8879:far-right:1"; on disk the colons
become "__". Standard library only.
"""
from __future__ import annotations

import csv, hashlib, json, os, plistlib, re, secrets, shutil, subprocess, sys, time
import urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "images"
KINDS = ("cover", "spine")
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif", ".heic"}
SHOWABLE = EXTS - {".heic"}               # what a browser can display directly
TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
         ".avif": "image/avif", ".gif": "image/gif"}
WEB_SIZE = {"cover": 800, "spine": 1200}   # longest side, in pixels, of published copies
MAX_GRAB = 20 * 1024 * 1024
UA = "Mozilla/5.0 (Macintosh) VirtualBookshelf/0.1 (personal catalogue)"


def sources_file() -> Path:
    return IMAGES / "_sources.json"


def config_dir() -> Path:
    return Path(os.environ.get("VB_CONFIG", Path.home() / ".config/virtual-bookshelf"))


def grab_key() -> str:
    """A stable secret for the "Add to bookshelf" bookmark (created on first use)."""
    f = config_dir() / "grab_key"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(secrets.token_urlsafe(18))
        f.chmod(0o600)
    return f.read_text().strip()


def host(url: str) -> str:
    h = urllib.parse.urlparse(url or "").hostname or ""
    return h[4:] if h.startswith("www.") else h


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


def _sources() -> dict:
    f = sources_file()
    try:
        return json.loads(f.read_text()) if f.exists() else {}
    except ValueError:
        return {}


def where_from(p: Path) -> dict:
    """Where a file in Downloads came from: {'image_url', 'page_url'} (may be empty).

    Files sent by the bookmark are recorded in images/_sources.json; anything a
    browser downloaded carries macOS's kMDItemWhereFroms ([file URL, page URL])."""
    known = _sources().get(p.name)
    if known:
        return known
    if sys.platform != "darwin" or not shutil.which("xattr"):
        return {}
    r = subprocess.run(["xattr", "-px", "com.apple.metadata:kMDItemWhereFroms", str(p)],
                       capture_output=True, text=True)
    return parse_where_froms(r.stdout) if r.returncode == 0 else {}


def parse_where_froms(hex_text: str) -> dict:
    """`xattr -px com.apple.metadata:kMDItemWhereFroms` output → {'image_url', 'page_url'}."""
    try:
        urls = plistlib.loads(bytes.fromhex("".join(hex_text.split())))
    except Exception:
        return {}
    urls = [u for u in urls if isinstance(u, str) and u.startswith("http")]
    return {"image_url": urls[0] if urls else "", "page_url": urls[1] if len(urls) > 1 else ""}


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
                        "showable": p.suffix.lower() in SHOWABLE, "path": p})
    out = sorted(out, key=lambda f: -f["mtime"])[:limit]
    for f in out:
        src = where_from(f.pop("path"))
        f["source"] = host(src.get("page_url") or src.get("image_url", ""))
    return out


def grab(image_url: str, page_url: str = "") -> str:
    """Fetch an image the bookmark sent and save it in Downloads with its source.
    Returns the new file's name."""
    if urllib.parse.urlparse(image_url).scheme not in ("http", "https"):
        raise ValueError("not a web image address")
    req = urllib.request.Request(image_url, headers={"User-Agent": UA, "Referer": page_url or image_url})
    with urllib.request.urlopen(req, timeout=30) as r:
        ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        data = r.read(MAX_GRAB + 1)
    if len(data) > MAX_GRAB:
        raise ValueError("image too large")
    ext = {v: k for k, v in TYPES.items() if k != ".jpeg"}.get(ctype)
    if not ext:
        raise ValueError(f"not an image ({ctype or 'unknown type'})")
    d = downloads_dir()
    d.mkdir(parents=True, exist_ok=True)
    name = f"bookshelf-{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}{ext}"
    (d / name).write_bytes(data)
    srcs = _sources()
    srcs[name] = {"image_url": image_url, "page_url": page_url}
    IMAGES.mkdir(parents=True, exist_ok=True)
    sources_file().write_text(json.dumps(srcs, indent=1))
    return name


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
    origin = where_from(src)
    dest_dir.mkdir(parents=True, exist_ok=True)
    for old in dest_dir.glob(f"{kind}.*"):
        old.unlink()
    meta = read_meta(row_id)
    meta[kind] = {"image_url": origin.get("image_url", ""), "page_url": origin.get("page_url", ""),
                  "published": True, "added": time.strftime("%Y-%m-%d %H:%M")}
    write_meta(row_id, meta)
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
    meta = read_meta(row_id)
    if meta.pop(kind, None) is not None:
        write_meta(row_id, meta)


def read_meta(row_id: str) -> dict:
    f = folder(row_id) / "meta.json"
    try:
        return json.loads(f.read_text()) if f.exists() else {}
    except ValueError:
        return {}


def write_meta(row_id: str, meta: dict) -> None:
    d = folder(row_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "meta.json").write_text(json.dumps(meta, indent=1, sort_keys=True))


def set_published(row_id: str, kind: str, on: bool) -> None:
    meta = read_meta(row_id)
    meta.setdefault(kind, {})["published"] = bool(on)
    write_meta(row_id, meta)


def describe(row_id: str, kind: str) -> dict:
    """What the review page shows for one of your images."""
    m = read_meta(row_id).get(kind, {})
    page = m.get("page_url") or m.get("image_url") or ""
    return {"source": host(page), "source_url": page, "published": m.get("published", True)}


# ---------------------------------------------------------------- publishing
SITE_DIR = "site_images"
CSV_FIELDS = ["row_id", "kind", "file", "source", "image_url", "page_url", "sha256"]


def _web_copy(src: Path, dest: Path, longest: int) -> Path:
    """A web-sized JPEG of src at dest (macOS sips); a plain copy elsewhere."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("sips"):
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "82", "-Z", str(longest),
                        str(src), "--out", str(dest)], check=True, capture_output=True)
        return dest
    dest = dest.with_suffix(src.suffix.lower())
    shutil.copyfile(src, dest)
    return dest


def export_published(root: Path, log=print) -> int:
    """Write site_images/ and data/images.csv for every image marked published.

    Removes copies of images that were removed or unpublished. Returns the
    number of published images. `root` is the project folder."""
    images, site, listing = root / "images", root / SITE_DIR, root / "data/images.csv"
    rows, keep = [], set()
    for d in sorted(images.iterdir()) if images.is_dir() else []:
        if not d.is_dir():
            continue
        rid = d.name.replace("__", ":")
        try:
            meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
        except ValueError:
            meta = {}
        for kind in KINDS:
            cands = [p for p in sorted(d.glob(f"{kind}.*")) if ".orig." not in p.name]
            m = meta.get(kind, {})
            if not cands or not m.get("published", True):
                continue
            out = _web_copy(cands[0], site / d.name / f"{kind}.jpg", WEB_SIZE[kind])
            keep.add(out)
            page = m.get("page_url") or m.get("image_url") or ""
            rows.append({"row_id": rid, "kind": kind, "file": str(out.relative_to(root)),
                         "source": host(page), "image_url": m.get("image_url", ""),
                         "page_url": m.get("page_url", ""),
                         "sha256": hashlib.sha256(out.read_bytes()).hexdigest()})
    for old in site.rglob("*") if site.is_dir() else []:
        if old.is_file() and old not in keep:
            old.unlink()
    for empty in sorted(site.glob("*"), reverse=True) if site.is_dir() else []:
        if empty.is_dir() and not any(empty.iterdir()):
            empty.rmdir()
    if rows or listing.exists():
        listing.parent.mkdir(parents=True, exist_ok=True)
        with open(listing, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            w.writeheader()
            w.writerows(rows)
    log(f"published images: {len(rows)} → {SITE_DIR}/ and data/images.csv")
    return len(rows)


def published(root: Path) -> dict:
    """data/images.csv as {row_id: {kind: {file, source, page_url, image_url}}}."""
    listing = root / "data/images.csv"
    out = {}
    if listing.exists():
        for r in csv.DictReader(open(listing, encoding="utf-8")):
            out.setdefault(r["row_id"], {})[r["kind"]] = r
    return out


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
