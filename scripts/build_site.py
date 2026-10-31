#!/usr/bin/env python3
"""Build the cover-grid page from the catalogue.

Usage:
    python3 scripts/build_site.py              # → _site/index.html
    python3 scripts/build_site.py --out DIR    # → DIR/index.html
    python3 scripts/build_site.py --local-images   # also use your own images/ (local preview only)
    open _site/index.html                      # preview locally

Reads data/books.csv (every physical item) and data/resolved.csv (covers),
plus the optional data/reading.csv (title,status,progress) for reading
status, and fills site/template.html. The result is one self-contained
index.html — no build tools; it works opened straight from disk.

Publishing is done by .github/workflows/pages.yml, which runs this script on
every push to main, adds build.json (the deployed commit, for the portfolio
hub at sgwoods.github.io/public) and deploys _site/ to GitHub Pages.
_site/ is git-ignored: never commit it.

Your own images: the public build uses the published ones listed in
data/images.csv (web-sized copies in site_images/, copied into the site),
with a small credit naming each image's source. With --local-images (what the
review page's Rebuild and Finish use), all of your images in images/ are used
instead, published or not — that is a local preview only; CI never passes it.

Every book in books.csv appears. A cover is shown only when the lookup is
matched or confirmed; everything else gets a title placeholder marked
"Cover missing". Physical copies of the same title share one card ("2 copies").
Standard library only.
"""
from __future__ import annotations

import argparse, csv, json, shutil, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve import norm, row_id, surname          # same normalising as the lookup

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "data/books.csv"
RESOLVED = ROOT / "data/resolved.csv"
READING = ROOT / "data/reading.csv"
TEMPLATE = ROOT / "site/template.html"
OUT_DIR = ROOT / "_site"

GOOD = {"matched", "confirmed"}


def cover(rec: dict) -> str:
    if not rec or rec.get("status") not in GOOD:
        return ""
    url = rec.get("cover_url") or ""
    if "covers.openlibrary.org" in url:
        url = url.replace("-M.jpg", "-L.jpg")
    return url


def build(out_dir: Path = OUT_DIR, local_images: bool = False) -> dict:
    """Write out_dir/index.html; return counts (used by the tests)."""
    import local_images as li
    own, credit = {}, {}           # row id → {kind: path relative to the site}, row id → source
    if local_images:
        for rid, kinds in li.all_images().items():
            own[rid] = {k: "../" + v for k, v in kinds.items()}
            d = li.describe(rid, "cover") if "cover" in kinds else {}
            if d.get("source"):
                credit[rid] = {"is": d["source"], "iu": d["source_url"]}
    else:
        for rid, kinds in li.published(ROOT).items():
            own[rid] = {k: v["file"] for k, v in kinds.items()}
            cv = kinds.get("cover")
            if cv and cv.get("source"):
                credit[rid] = {"is": cv["source"], "iu": cv.get("page_url") or cv.get("image_url", "")}
    books = [r for r in csv.DictReader(open(BOOKS, encoding="utf-8")) if r["position"] != "0"]
    res = {r["row_id"]: r for r in csv.DictReader(open(RESOLVED, encoding="utf-8"))} if RESOLVED.exists() else {}
    reading = {}
    if READING.exists():
        for r in csv.DictReader(open(READING, encoding="utf-8")):
            reading[norm(r["title"])] = (r.get("status") or "unread").strip(), int(r.get("progress") or 0)

    cards: dict[tuple, dict] = {}
    for b in books:
        rec = res.get(row_id(b), {})
        if rec.get("status") == "not-a-book":
            continue
        title = b["title"].strip()
        author = b["author"].strip().strip("?").strip()
        if author in ("", "—"):
            author = "Unknown author"
        key = (norm(title), surname(b["author"]))
        mine = own.get(row_id(b), {})
        c = cards.get(key)
        if c:
            if mine.get("cover"):
                c["c"] = mine["cover"]
                c.pop("is", None); c.pop("iu", None)
                c.update(credit.get(row_id(b), {}))
            if mine.get("spine"):
                c["sp"] = mine["spine"]
            c["n"] += 1
            c["c"] = c["c"] or cover(rec)
            continue
        s, p = reading.get(norm(title), ("unread", 0))
        cards[key] = {"t": title, "a": author, "c": mine.get("cover") or cover(rec), "n": 1, "s": s, "p": p,
                      **({"sp": mine["spine"]} if mine.get("spine") else {}),
                      **(credit.get(row_id(b), {}) if mine.get("cover") else {}),
                      "_sort": (surname(b["author"]) or "~", norm(title))}

    out = sorted(cards.values(), key=lambda c: c.pop("_sort"))
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("/*BOOKS*/[]", json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("/*BUILT*/", time.strftime("%Y-%m-%d"))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    site_images = ROOT / li.SITE_DIR
    if not local_images and site_images.is_dir():
        shutil.copytree(site_images, out_dir / li.SITE_DIR, dirs_exist_ok=True)
    return {"rows": len(books), "copies": sum(c["n"] for c in out), "titles": len(out),
            "covers_missing": sum(1 for c in out if not c["c"]), "cards": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT_DIR, help="output directory (default: _site/)")
    ap.add_argument("--local-images", action="store_true",
                    help="use your own images/ for covers (local preview only; never in CI)")
    a = ap.parse_args()
    n = build(a.out, a.local_images)
    print(f"{n['copies']} books · {n['titles']} titles · {n['covers_missing']} covers missing "
          f"→ {a.out / 'index.html'}")


if __name__ == "__main__":
    main()
