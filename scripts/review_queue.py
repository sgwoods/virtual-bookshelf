#!/usr/bin/env python3
"""The review queue behind the one-book-at-a-time page.

Every catalogued book is in exactly one of four states:

    to review          needs a person (weak/none lookup, unsure spine read,
                       or a match that dropped the spine's subtitle) and has
                       no decision yet
    check in hand      set aside to look at the book itself (decision "in-hand")
    ready to publish   decided on this Mac, not yet pushed to GitHub
    published          its decision is in GitHub's copy (or it never needed one)

A decision is applied to data/resolved.csv the moment it is made, so the book
leaves the queue at once; Publish then pushes the data. Books skipped in this
session go to the back of the queue.

Standard library only.
"""
from __future__ import annotations

import csv, io, json, subprocess, threading, time
from pathlib import Path

import resolve
from resolve import clean_title, norm

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "data/books.csv"
RESOLVED = ROOT / "data/resolved.csv"
OVERRIDES = ROOT / "data/overrides.csv"
LOCK = threading.RLock()
SKIPPED: list[str] = []            # this session's "skip for now", in order
UNDO: dict[str, dict] = {}         # row id -> its resolved.csv row before the last decision


def rid(r: dict) -> str:
    return f"{r['photo']}:{r['stack']}:{r['position']}"


def read_csv(path: Path) -> list[dict]:
    return list(csv.DictReader(open(path, encoding="utf-8"))) if path.exists() else []


def subtitle_dropped(spine_title: str, match_title: str) -> bool:
    ct = clean_title(spine_title or "")
    if ":" not in ct or not match_title:
        return False
    sub = norm(ct.split(":", 1)[1])
    return len(sub) >= 4 and sub not in norm(clean_title(match_title))


def why(b: dict, r: dict | None) -> str:
    """Why this book needs a person, in plain words ('' if it doesn't)."""
    if b["position"] == "0":
        return ""
    status = (r or {}).get("status") or ""
    if status in ("confirmed", "confirmed-unlisted", "not-a-book"):
        return ""
    if b["title"].lower().startswith("unknown") or status == "skipped":
        return "The spine couldn't be read — this one needs the book in hand."
    if status in ("none", ""):
        return "No match found yet."
    if status == "weak":
        return "Only a possible match — which one is it?"
    if b["confidence"] not in ("high", "checked"):
        return "The spine was hard to read — check the details."
    if status == "matched" and subtitle_dropped(b["title"], r.get("match_title", "")):
        return "Matched without the subtitle on the spine — same book?"
    return ""


def published_decisions() -> dict[str, str]:
    """GitHub's copy of the decisions as of this checkout (row id -> decision + details)."""
    r = subprocess.run(["git", "show", "HEAD:data/overrides.csv"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        return {}
    return {x["row_id"]: x["decision"] + "|" + x.get("pick_json", "")
            for x in csv.DictReader(io.StringIO(r.stdout))}


def state() -> dict:
    """The queue in order, plus the three counts."""
    books = [b for b in read_csv(BOOKS) if b["position"] != "0"]
    res = {r["row_id"]: r for r in read_csv(RESOLVED)}
    ov = {r["row_id"]: r for r in read_csv(OVERRIDES)}
    head = published_decisions()
    todo = [rid(b) for b in books if rid(b) not in ov and why(b, res.get(rid(b)))]
    later = [x for x in SKIPPED if x in todo]
    order = [x for x in todo if x not in later] + later
    in_hand = [rid(b) for b in books if ov.get(rid(b), {}).get("decision") == "in-hand"]
    ready = [k for k, o in ov.items() if o["decision"] != "in-hand"
             and head.get(k) != o["decision"] + "|" + o.get("pick_json", "")]
    return {"order": order, "in_hand_ids": in_hand, "ready_ids": ready,
            "to_review": len(order), "in_hand": len(in_hand), "ready": len(ready),
            "published": len(books) - len(order) - len(ready) - len(in_hand), "total": len(books)}


def listing(bucket: str = "to_review", q: str = "", limit: int = 400) -> list[dict]:
    """Books for the queue rail: one bucket, or a search over every book."""
    books = [b for b in read_csv(BOOKS) if b["position"] != "0"]
    res = {r["row_id"]: r for r in read_csv(RESOLVED)}
    st = state()
    if q.strip():
        words = norm(q).split()
        pick = [b for b in books if all(w in norm(b["title"] + " " + b["author"] + " " +
                                                  (res.get(rid(b)) or {}).get("match_title", "")) for w in words)]
        ids = [rid(b) for b in pick]
    elif bucket == "in_hand":
        ids = st["in_hand_ids"]
    elif bucket == "ready":
        ids = st["ready_ids"]
    elif bucket == "all":
        ids = [rid(b) for b in books]
    else:
        ids = st["order"]
    by = {rid(b): b for b in books}
    where = {**{k: "to review" for k in st["order"]}, **{k: "check in hand" for k in st["in_hand_ids"]},
             **{k: "ready to publish" for k in st["ready_ids"]}}
    out = []
    for k in ids[:limit]:
        b, r = by.get(k), res.get(k) or {}
        if b:
            out.append({"row_id": k, "title": r.get("match_title") or b["title"], "author": b["author"],
                        "state": where.get(k, "published"), "cover_url": r.get("cover_url", "")})
    return out


def book(row_id: str) -> dict:
    """Everything the page needs to show one book."""
    b = next((x for x in read_csv(BOOKS) if rid(x) == row_id), None)
    if not b:
        raise KeyError(row_id)
    r = next((x for x in read_csv(RESOLVED) if x["row_id"] == row_id), {}) or {}
    cands = json.loads(r.get("candidates") or "[]")
    key = lambda c: c.get("work_id") or c.get("gb_id") or c.get("title")
    current = False
    if r.get("status") == "matched" and r.get("match_title"):
        want = r.get("work_id") or r.get("gb_id") or r.get("match_title")
        cands.sort(key=lambda c: key(c) != want)
        current = bool(cands) and key(cands[0]) == want
    ov = next((x for x in read_csv(OVERRIDES) if x["row_id"] == row_id), None)
    decided = None
    if ov:
        try:
            decided = {"decision": ov["decision"], "pick": json.loads(ov.get("pick_json") or "{}")}
        except ValueError:
            decided = {"decision": ov["decision"], "pick": {}}
    return {"row_id": row_id, "title": b["title"], "author": b["author"], "notes": b.get("notes", ""),
            "decided": decided, "confidence": b.get("confidence", ""),
            "resolved": {k: r.get(k, "") for k in ("status", "match_title", "match_author", "year", "isbns",
                                                    "cover_url", "source")},
            "photo": b["photo"], "stack": b["stack"], "position": b["position"],
            "why": why(b, r), "status": r.get("status", ""), "current": current,
            "unreadable": b["title"].lower().startswith("unknown"),
            "candidates": cands}


def decide(row_id: str, decision: str, pick_json: str = "") -> None:
    """Record a decision and apply it to data/resolved.csv straight away."""
    if decision not in ("pick", "accept", "no-match", "not-a-book", "in-hand"):
        raise ValueError("bad decision")
    with LOCK:
        rows = {x["row_id"]: x for x in read_csv(OVERRIDES)}
        rows[row_id] = {"row_id": row_id, "decision": decision, "pick_json": pick_json, "note": "",
                        "decided_at": time.strftime("%Y-%m-%d %H:%M")}
        _write(OVERRIDES, rows.values(), ["row_id", "decision", "pick_json", "note", "decided_at"])
        res = read_csv(RESOLVED)
        fields = list(res[0].keys()) if res else resolve.OUT_FIELDS
        for i, rec in enumerate(res):
            if rec["row_id"] == row_id:
                UNDO[row_id] = dict(rec)
                res[i] = {k: v for k, v in resolve.apply_override(rec, rows[row_id]).items() if k in fields}
        _write(RESOLVED, res, fields)
        if row_id in SKIPPED:
            SKIPPED.remove(row_id)


def undo(row_id: str) -> None:
    """Take back the last decision on this book: it returns to the queue."""
    with LOCK:
        rows = {x["row_id"]: x for x in read_csv(OVERRIDES)}
        rows.pop(row_id, None)
        _write(OVERRIDES, rows.values(), ["row_id", "decision", "pick_json", "note", "decided_at"])
        before = UNDO.pop(row_id, None)
        if before:
            res = read_csv(RESOLVED)
            fields = list(res[0].keys())
            res = [before if x["row_id"] == row_id else x for x in res]
            _write(RESOLVED, res, fields)


def skip(row_id: str) -> None:
    with LOCK:
        if row_id in SKIPPED:
            SKIPPED.remove(row_id)
        SKIPPED.append(row_id)


def _write(path: Path, rows, fields) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)
