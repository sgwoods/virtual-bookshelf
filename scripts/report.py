#!/usr/bin/env python3
"""Summarise data/books.csv: counts, confidence, top authors, review queue.

Usage:  python3 scripts/report.py [--review] [--authors N]
"""
import argparse, collections, csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data/books.csv"
DUP_MARKERS = ("second copy", "duplicate", "same copy", "overlap")


def load():
    rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
    books = [r for r in rows if r["position"] != "0"]
    nonbooks = [r for r in rows if r["position"] == "0"]
    return rows, books, nonbooks


def is_dup(r):
    n = r["notes"].lower()
    return any(m in n for m in DUP_MARKERS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--review", action="store_true", help="list rows below high confidence")
    ap.add_argument("--authors", type=int, default=12)
    a = ap.parse_args()

    rows, books, nonbooks = load()
    conf = collections.Counter(r["confidence"] for r in books)
    dups = [r for r in books if is_dup(r)]
    distinct = len({(r["title"].lower(), r["author"].lower()) for r in books})
    photos = sorted({r["photo"] for r in rows})

    print(f"photos read      : {len(photos)}  ({photos[0]} … {photos[-1]})")
    print(f"physical items   : {len(books)}")
    print(f"distinct titles  : ~{distinct}")
    print(f"flagged dup/overlap copies : {len(dups)}")
    print(f"non-book items   : {len(nonbooks)}")
    print("confidence       : " + ", ".join(f"{k} {v}" for k, v in sorted(conf.items())))
    print()
    au = collections.Counter(r["author"].split(" (")[0] for r in books)
    print(f"top {a.authors} authors:")
    for name, n in au.most_common(a.authors):
        print(f"  {n:3d}  {name}")

    if a.review:
        print("\nreview queue (confidence != high):")
        for r in books:
            if r["confidence"] != "high":
                print(f"  {r['photo']} {r['stack']}#{r['position']:>2}  [{r['confidence']:6}] "
                      f"{r['title']} — {r['author']}   ({r['notes']})")


if __name__ == "__main__":
    main()
