#!/usr/bin/env python3
"""Match every book in data/books.csv against Open Library (Google Books fallback).

Usage:
    python3 scripts/resolve.py               # all rows, resumes where it left off
    python3 scripts/resolve.py --limit 20    # quick trial on the first 20
    python3 scripts/resolve.py --photo IMG_8884
    python3 scripts/resolve.py --refresh     # ignore previous results (cache still used)

Standard library only — no pip install needed. ~1 request/second, so a full
run is ~10–15 minutes the first time and seconds after that (responses are
cached in data/cache/, which is git-ignored).

Output: data/resolved.csv — one row per physical book with match status,
score, Open Library work id, year, cover id, ISBNs, subjects and the top
alternative candidates (used by scripts/review.py).
Manual decisions from the review page live in data/overrides.csv and always win.
"""
from __future__ import annotations

import argparse, csv, difflib, hashlib, json, re, sys, time, unicodedata
import urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "data/books.csv"
OUT = ROOT / "data/resolved.csv"
OVERRIDES = ROOT / "data/overrides.csv"
CACHE = ROOT / "data/cache"
UA = "VirtualBookshelf/0.1 (personal catalogue; sgwoods@gmail.com)"
OL_FIELDS = "key,title,author_name,first_publish_year,cover_i,subject,isbn,edition_count"

MATCH, WEAK = 0.80, 0.55          # score thresholds
SKIP_TITLE = re.compile(r"^(unknown\b|.*\bthesis\b)", re.I)

OUT_FIELDS = ["row_id", "photo", "stack", "position", "title", "author", "confidence",
              "status", "score", "source", "query",
              "work_id", "match_title", "match_author", "year", "edition_count",
              "cover_id", "cover_url", "isbns", "subjects", "gb_id", "candidates"]


# ---------------------------------------------------------------- normalising
NUMWORDS = {w: str(i) for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve".split())}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    words = [NUMWORDS.get(w, w) for w in s.split()]
    while words and words[0] in ("the", "a", "an"):
        words = words[1:]
    return " ".join(words)


def clean_title(t: str) -> str:
    t = re.sub(r"\s*\([^)]*\)", "", t)            # drop "(Star Trek #57)", "(2nd ed.)"
    t = re.sub(r"\s*\[[^\]]*\]", "", t)          # drop "[32 essays]"
    t = t.replace("…", "").replace("...", "")
    return t.strip(" :-—")


def first_author(a: str) -> str:
    a = re.sub(r"\([^)]*\)", "", a)                # "(ed.)", "(trans. Ken Liu)"
    a = re.split(r"\s+and\s+|,|/|&|\bwith\b", a)[0]
    return a.replace("?", "").replace("—", "").strip()


def surname(a: str) -> str:
    parts = [p for p in re.split(r"[\s.]+", first_author(a)) if p]
    while parts and norm(parts[-1]) in ("jr", "sr", "md", "ii", "iii"):
        parts = parts[:-1]
    return norm(parts[-1]) if parts else ""


# franchise prefixes that one side has and the other often doesn't
BRAND = re.compile(r"^(isaac asimov s|isaac asimov presents|douglas adams s)\s+")


def score(want_title: str, want_author: str, got_title: str, got_authors: list[str]) -> float:
    """Best of: candidate title as listed, and with its (…)/[…] notes and "by <author>" removed."""
    sn = surname(want_author)
    got = got_title or ""
    trimmed = clean_title(got)
    if sn:                                         # "Paycheck … Stories By Philip K. Dick"
        trimmed = re.sub(r"\s+by\s+[^:]*\b%s\b.*$" % re.escape(sn), "", trimmed, flags=re.I)
    return max(_score(want_title, sn, b, got_authors) for b in {got, trimmed})


def _score(want_title: str, sn: str, got_title: str, got_authors: list[str]) -> float:
    a_raw, b_raw = clean_title(want_title), got_title
    if not norm(a_raw) or not norm(b_raw):
        return 0.0

    def parts(s):                                  # full title, main title, subtitle
        bits = [s] + [p for p in re.split(r"\s*:\s*|\s+[-–—]\s+", s, maxsplit=1) if p != s]
        out = [norm(x) for x in bits if norm(x)]
        return out + [BRAND.sub("", x) for x in out if BRAND.match(x)]

    ratio = lambda x, y: difflib.SequenceMatcher(None, x, y).ratio()
    t = ratio(norm(a_raw), norm(b_raw))
    # "Fantastic Voyage: Microcosm" ~ "Microcosm", "Dune" ~ "Dune: Deluxe Edition";
    # but NOT "Dune" ~ "Dune Messiah" (no colon → no partial credit)
    for x in parts(a_raw):
        for y in parts(b_raw):
            if (x, y) != (norm(a_raw), norm(b_raw)) and len(min(x, y, key=len)) >= 4:
                t = max(t, 0.95 * ratio(x, y))
    if not sn:
        au = 0.5                                   # no author to check: neutral
    elif any(sn in norm(x).split() for x in got_authors or []):
        au = 1.0
    elif any(x.strip() and not norm(x) for x in got_authors or []):
        au = 0.5                                   # author listed only in non-Latin script (刘慈欣, Лев Толстой)
    else:
        au = 0.0
    s = 0.7 * t + 0.3 * au
    if t < 0.85:                    # an extra/missing word is a different book until a human says so
        s = min(s, MATCH - 0.01)
    return round(s, 3)


# ---------------------------------------------------------------- http + cache
_last = [0.0]


def get_json(url: str) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".json")
    if f.exists():
        return json.loads(f.read_text())
    wait = 1.0 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
            break
        except Exception as e:                     # network hiccup / 5xx / 429
            if attempt == 2:
                print(f"    ! {e} — {url}", file=sys.stderr)
                return {}
            time.sleep(3 * (attempt + 1))
    _last[0] = time.time()
    f.write_text(json.dumps(data))
    return data


def ol_search(**params) -> list[dict]:
    params.update(limit=8, fields=OL_FIELDS)
    url = "https://openlibrary.org/search.json?" + urllib.parse.urlencode(params)
    return get_json(url).get("docs", [])


def gb_search(title: str, author: str) -> list[dict]:
    q = f'intitle:"{title}"' + (f' inauthor:"{author}"' if author else "")
    url = ("https://www.googleapis.com/books/v1/volumes?maxResults=5&printType=books&q="
           + urllib.parse.quote(q))
    out = []
    for it in get_json(url).get("items", []):
        v = it.get("volumeInfo", {})
        out.append({
            "source": "googlebooks", "gb_id": it.get("id", ""),
            "title": v.get("title", "") + (": " + v["subtitle"] if v.get("subtitle") else ""),
            "author_name": v.get("authors", []),
            "first_publish_year": (v.get("publishedDate") or "")[:4],
            "isbn": [i["identifier"] for i in v.get("industryIdentifiers", [])
                     if i.get("type", "").startswith("ISBN")],
            "subject": v.get("categories", []),
            "cover_url": (v.get("imageLinks") or {}).get("thumbnail", "").replace("http://", "https://"),
        })
    return out


# ---------------------------------------------------------------- resolve one
def resolve(row: dict) -> dict:
    title, author = row["title"], row["author"]
    ct, fa = clean_title(title), first_author(author)
    sn = surname(author)
    attempts = []
    if fa:
        attempts.append(("ol title+author", dict(title=ct, author=fa)))
    attempts.append(("ol q", dict(q=f"{ct} {sn}".strip())))
    attempts.append(("ol title", dict(title=ct)))
    main = ct.split(":")[0].strip()
    if main != ct and len(main) >= 4:              # long subtitles can sink an OL title search
        attempts.append(("ol main title+author", dict(title=main, author=fa) if fa else dict(title=main)))

    cands, used = [], ""
    for label, params in attempts:
        for d in ol_search(**params):
            d["source"] = "openlibrary"
            d["_score"] = score(title, author, d.get("title", ""), d.get("author_name", []))
            cands.append(d)
        used = label
        if cands and max(c["_score"] for c in cands) >= MATCH:
            break

    if not cands or max(c["_score"] for c in cands) < MATCH:
        for d in gb_search(ct, fa):
            d["_score"] = score(title, author, d["title"], d["author_name"])
            cands.append(d)
        used += " + gb"

    # dedupe by (source, key/id), best first
    seen, uniq = set(), []
    for c in sorted(cands, key=lambda c: (-c["_score"], -(c.get("edition_count") or 0))):
        k = (c["source"], c.get("key") or c.get("gb_id") or c.get("title"))
        if k not in seen:
            seen.add(k); uniq.append(c)
    return pack(row, uniq, used)


def cover_url(c: dict) -> str:
    if c.get("cover_i"):
        return f"https://covers.openlibrary.org/b/id/{c['cover_i']}-M.jpg"
    return c.get("cover_url", "")


def pack(row: dict, cands: list[dict], used: str) -> dict:
    best = cands[0] if cands else {}
    s = best.get("_score", 0.0)
    status = "matched" if s >= MATCH else "weak" if s >= WEAK else "none"
    alts = [{"source": c["source"], "work_id": c.get("key", ""), "gb_id": c.get("gb_id", ""),
             "title": c.get("title", ""), "author": ", ".join(c.get("author_name", [])[:3]),
             "year": c.get("first_publish_year", ""), "cover_url": cover_url(c),
             "score": c["_score"]} for c in cands[:4]]
    return {
        **base(row), "status": status, "score": s, "source": best.get("source", ""), "query": used,
        "work_id": best.get("key", ""), "match_title": best.get("title", ""),
        "match_author": "; ".join(best.get("author_name", [])[:4]),
        "year": best.get("first_publish_year", ""), "edition_count": best.get("edition_count", ""),
        "cover_id": best.get("cover_i", ""), "cover_url": cover_url(best),
        "isbns": ";".join((best.get("isbn") or [])[:5]),
        "subjects": ";".join((best.get("subject") or [])[:10]),
        "gb_id": best.get("gb_id", ""), "candidates": json.dumps(alts, ensure_ascii=False),
    }


def base(row: dict) -> dict:
    return {"row_id": row_id(row), **{k: row[k] for k in
            ("photo", "stack", "position", "title", "author", "confidence")}}


def row_id(row: dict) -> str:
    return f"{row['photo']}:{row['stack']}:{row['position']}"


def apply_override(rec: dict, ov: dict) -> dict:
    """A manual decision from the review page always wins."""
    rec = dict(rec)
    d = ov.get("decision", "")
    if d == "accept":
        rec["status"] = "confirmed"
    elif d == "pick":
        alt = json.loads(ov.get("pick_json") or "{}")
        rec.update(status="confirmed", source=alt.get("source", ""), work_id=alt.get("work_id", ""),
                   gb_id=alt.get("gb_id", ""), match_title=alt.get("title", ""),
                   match_author=alt.get("author", ""), year=alt.get("year", ""),
                   cover_url=alt.get("cover_url", ""), cover_id="", isbns="", subjects="")
    elif d == "no-match":
        rec.update(status="confirmed-unlisted", work_id="", match_title="", cover_url="")
    elif d == "not-a-book":
        rec["status"] = "not-a-book"
    return rec


def load_overrides() -> dict:
    if not OVERRIDES.exists():
        return {}
    return {r["row_id"]: r for r in csv.DictReader(open(OVERRIDES, encoding="utf-8"))}


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--photo")
    ap.add_argument("--refresh", action="store_true", help="recompute all rows (cache still used)")
    ap.add_argument("--retry", action="store_true", help="recompute weak/none rows only (cache still used)")
    a = ap.parse_args()

    rows = [r for r in csv.DictReader(open(BOOKS, encoding="utf-8")) if r["position"] != "0"]
    if a.photo:
        rows = [r for r in rows if r["photo"] == a.photo]
    if a.limit:
        rows = rows[:a.limit]

    done = {}
    if OUT.exists() and not a.refresh:
        done = {r["row_id"]: r for r in csv.DictReader(open(OUT, encoding="utf-8"))}
    overrides = load_overrides()

    results, t0 = [], time.time()
    for i, row in enumerate(rows, 1):
        rid = row_id(row)
        prev = done.get(rid)
        retry = a.retry and prev and prev["status"] in ("weak", "none")
        if prev and not retry and prev["title"] == row["title"] and prev["author"] == row["author"]:
            rec = prev                                         # unchanged since last run
        elif SKIP_TITLE.match(row["title"]):
            rec = {**{k: "" for k in OUT_FIELDS}, **base(row), "status": "skipped", "score": 0}
        else:
            rec = resolve(row)
        rec = apply_override(rec, overrides[rid]) if rid in overrides else rec
        results.append(rec)
        mark = {"matched": "✓", "confirmed": "✓", "weak": "~", "none": "✗"}.get(rec["status"], "·")
        print(f"[{i:3d}/{len(rows)}] {mark} {float(rec['score'] or 0):.2f}  "
              f"{row['title'][:45]:45}  →  {str(rec.get('match_title',''))[:40]}", flush=True)

    # keep rows from previous runs that this (filtered) run didn't touch
    touched = {r["row_id"] for r in results}
    merged = [r for r in done.values() if r["row_id"] not in touched] + results
    order = {row_id(r): n for n, r in enumerate(csv.DictReader(open(BOOKS, encoding="utf-8")))}
    merged.sort(key=lambda r: order.get(r["row_id"], 1e9))

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS, extrasaction="ignore")
        w.writeheader(); w.writerows(merged)

    from collections import Counter
    c = Counter(r["status"] for r in merged)
    print(f"\n{len(merged)} rows → {OUT}  in {time.time()-t0:.0f}s")
    print("  " + "  ".join(f"{k}: {v}" for k, v in c.most_common()))
    print("next: python3 scripts/review.py")


if __name__ == "__main__":
    main()
