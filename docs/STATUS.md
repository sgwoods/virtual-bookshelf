# Status — 2026-10-30

## Latest (Oct 30, afternoon)

- Repo created and pushed: github.com/sgwoods/virtual-bookshelf. Working
  copy on the MacBook at `~/Developer/virtual-bookshelf`.
- Phase 1b steps 1–2 built: `scripts/resolve.py` (Open Library lookup,
  Google Books fallback) and `scripts/review.py` (local review page).
- **20-book live trial: 20/20 matched** (Gor, Lensman/Skylark, Star Trek
  Blish and Log volumes). Watch-out: Open Library's `first_publish_year`
  is sometimes a reprint year (*Children of the Lens* → 2017, *Skylark
  Three* → 2013) — sanity-check years before relying on them.
- **Next command:** `python3 scripts/resolve.py` (full run, ~10–15 min,
  resumes from the trial), then `python3 scripts/review.py`, then
  `python3 scripts/resolve.py` again to apply decisions, then commit `data/`.
- `data/resolved.csv` from the trial exists on the MacBook but is not
  committed yet — it will be after the full run + review.

## Summary

Phase 1a (photo → first-pass catalogue) is complete. 31 shelf photos were
taken on Oct 27–28, read on Oct 28, and the result is `data/books.csv`:
**521 physical items, ~500 distinct titles, 509 of them read with high
confidence.** The earlier estimate of 600–900 titles was high; the stacks are
shallower than the first two sample photos suggested.

Nothing has been built on top of the CSV yet — no database, no metadata
lookups, no covers, no web view.

## What was done, in order

1. **Photos inventoried.** 31 HEIC files (2–4 MB each) in the Drive folder.
   IDs saved to `data/drive_files.tsv`. IMG_8883 turned out to be a re-shoot
   of IMG_8882 (the Asimov shelf) and was skipped, so 30 photos carry data.
2. **HEIC decoding.** The cloud workspace had no HEVC decoder (`pillow-heif`
   uninstallable, ImageMagick's libheif lacked the codec). Wrote
   `scripts/heic2jpg.py`, which parses the HEIF container directly, extracts
   the 45 HEVC tiles that iPhone photos are stored as, decodes each with
   ffmpeg, and stitches them back into the 5712×4284 frame. Slow (~2 min per
   photo on 2 cores) but dependency-free. On the iMac, `sips` does this in a
   second — the script exists for reproducibility, not speed.
3. **Spine reading.** A vision model read each 1600px preview and transcribed
   title/author per spine, in shelf order. For anything ambiguous it cropped
   the full-resolution JPEG and re-read the crop; that resolved every case
   where any text was physically present (e.g. *N-Space*, *Wyrms*, *Moonseed*,
   *The Winds of Altair*, *Princes in Waiting*). What remained unreadable is
   unreadable on the shelf too (worn blank spines, hidden behind other books).
4. **CSV assembled and validated.** Parsed cleanly, 526 rows, one stray comma
   fixed. Duplicate copies and overlapping frames flagged in `notes`.

## Results

```
photos read      : 30
physical items   : 521
distinct titles  : ~499
duplicate/overlap copies flagged : 19
non-book items   : 5   (Matrix DVD, War of the Worlds CDs, X-Files DVD set, Marco Polo guide…)
confidence       : high 509 · medium 8 · low 4

top authors:  Asimov 26 · Clarke 22 · Card 17 · Foster 15 · Bear 14 ·
              Rowling 12 · Benford 11 · Heinlein 11 · Sawyer 10 · Baxter 10 ·
              Bova 9 · E. E. "Doc" Smith 8
```

Roughly: two-thirds classic and contemporary SF (heavily author-clustered —
the shelves are already organised by author), a Sherlock Holmes shelf, a
Harry Potter shelf (two full sets), a Chomsky/politics shelf, a
science/philosophy/AI shelf, a CS-theory and thesis shelf, a classics shelf,
and a small recent-reads shelf (Three-Body, Attia, Metz, Mack).

## Review queue (12 rows)

Run `python3 scripts/report.py --review` for the live list. As of this commit:

| photo | item | issue |
|---|---|---|
| IMG_8879 | *The Best of Trek 2* | partly hidden at frame edge |
| IMG_8882 | *Robots in Time: Predator* | author (Wu) inferred, not on spine |
| IMG_8882 | *The Gods Themselves* (hardcover) | partly hidden |
| IMG_8882 | unknown, "…the Mind" | only back-cover text visible — pull it off the shelf |
| IMG_8893 | *The Swords Trilogy* | author (Moorcock) inferred |
| IMG_8893 | unknown, worn black spine | illegible — pull it off the shelf |
| IMG_8895 | *Space Odyssey* | which edition? |
| IMG_8896 | *Great SF Stories 5* | volume number partly obscured |
| IMG_8898 | *Robots and Spaceships* | author inferred |
| IMG_8899 | unknown, blue clothbound | no spine text — pull it |
| IMG_8900 | unknown, old leather-bound | spine damaged — pull it |
| IMG_8908 | *We Built This Vol 1* | title only |

Four of these need a hand on the physical book; the rest will likely resolve
themselves during the metadata lookup.

## Known gaps and caveats

- **Edition/publisher** is recorded only where the spine showed it; it's a
  hint for ISBN matching, not authoritative.
- **Series titles** like "Star Trek Log Two" or "Harry Potter and…" are
  written out in full so they search well; series numbers are in the title
  where printed on the spine.
- **Shelf location** is currently `photo + stack + position`. That's stable
  only until books move. A real scheme is an open decision (ROADMAP).
- **Books not photographed** (if any shelves were missed) are obviously
  absent; a second photo pass can be appended the same way.
- `books_unique.csv` is a convenience derivative; `books.csv` is the source
  of truth and the only one to edit.

## Decisions taken

- Read spines with a vision model rather than OCR + fuzzy match. Correct call:
  one pass got 98% high-confidence, with no post-processing.
- Keep the photos out of git; they stay in Drive and the repo stays small.
- Write the catalogue as plain CSV first. SQLite comes in Phase 1b when
  there's more than one table's worth of data.
- Keep one row per *physical copy*, flag duplicates, rather than collapsing
  up front — the "work vs copy" split from the plan is preserved.
