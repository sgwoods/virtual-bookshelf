# Roadmap

The full plan is the Claude Doc "Virtual Bookshelf — Plan"
(https://claude.ai/artifact/AhsbdwHeufjhoLcPi5zvsy). This file tracks the
working version: what's done, what's next, and what Phase 1a taught us.

```
Phase 1a  photos → books.csv                      ✅ done (Oct 28)
Phase 1b  resolve → SQLite → browsable catalogue  🔨 in progress (steps 1–2 built)
Phase 2   lists, tags, notes, reading status
Phase 3a  quotes and topics across books
Phase 3b  discovery: gaps, adjacent authors, what to buy
```

Gate from the plan still holds: **finish the Phase 1 review before starting
Phase 2.** A catalogue with wrong books in it poisons everything downstream.

---

## Phase 1b — next steps, in order

### 1. Resolve against Open Library  ✅ built — `scripts/resolve.py`, awaiting first live run
`scripts/resolve.py`: for each row in `books.csv`, query the Open Library
search API (`/search.json?title=…&author=…`), pick the best work match, and
record `ol_work_id`, `first_publish_year`, `subjects`, `isbn` candidates and a
`cover_id`. Google Books as fallback for misses. Cache every response to disk
so re-runs are free and polite.

Output: `data/resolved.csv` plus a match score per row. Built with the
standard library only; tested offline against stubbed responses and 13
hand-picked hard cases (series tags, subtitles, *Dune* vs *Dune Messiah*,
diacritics, number words). Not yet run against the live API — the build
environment can't reach it — so the first `--limit 20` run on the Mac is the
real test. Expect most of the
classic SF to match cleanly; the likely misses are the CS monographs, the
theses, the exhibition catalogues and the Coteau/Red Deer small-press books.

### 2. Review page  ✅ built — `scripts/review.py`
A single local page listing every row that is (a) below high confidence from
the spine read, or (b) a weak/no Open Library match. Each row shows the
spine read, a link to its shelf photo, and up to four candidates with covers;
actions are use-this / not listed / not a book / fix the spine read.
(Cropped spine images need per-spine bounding boxes, which the Phase 1a read
didn't record — a later improvement to `read_spines.py`.) Writes corrections back to `books.csv`. This is where the 12
review-queue items and the lookup misses get cleared — the 4 unreadable ones
by taking the book off the shelf.

### 3. Covers  *(minutes, automated)*
Download covers from `covers.openlibrary.org/b/id/{cover_id}-L.jpg` into
`covers/` (git-ignored). For misses, crop the book's front from a photo
later, or leave a generated spine-colour placeholder.

### 4. SQLite schema
Move from CSV to `bookshelf.sqlite`:
- `works` — one per title (Open Library work), with subjects, year, description
- `copies` — one per physical book: work_id, location, format, publisher, condition, notes
- `authors`, `work_authors`
- FTS5 index over title/author/subjects/notes

`books.csv` stays as the human-editable import source until the review page
can edit the database directly.

### 5. Browse UI  *(the "store" view)*
FastAPI + Jinja + HTMX, served locally on the iMac. Cover grid, filter by
author / subject / shelf / decade, a book detail page, and search. Reachable
from the phone over Tailscale. This is the Phase 1 finish line.

---

## Phase 1a tooling (to make the read repeatable)

The spine read was done interactively. To make adding a new shelf a
one-command job:
- `scripts/read_spines.py` — sends each preview (and left/right halves) to a
  vision model with a fixed prompt, gets back JSON rows in the `books.csv`
  schema, appends them. Claude via API is the known-good option; compare a
  local Qwen-VL / Llama-vision on Ollama against 3 of these photos, using the
  current CSV as ground truth.
- A barcode path for new purchases: phone camera → ISBN → straight into
  `copies`, skipping spine reading entirely.

---

## Phase 2 — lists and notes (after the gate)

Reading status (read / to-read / reread), personal ratings, free-text notes,
tags, and named lists ("lend to X", "spares to give away" — the 19 flagged
duplicates are a ready-made first list). Optional one-way sync to Goodreads
or LibraryThing export format.

## Phase 3a — quotes and topics

Limited to text that's legitimately available: own Kindle/Readwise
highlights, public-domain full texts (Gutenberg / Internet Archive — a fair
amount of the classics shelf qualifies: Wells, Shelley, Dumas, Tolstoy,
Darwin, Cook's journals, Lucretius, Plato), Open Library descriptions and
subjects, and my own notes. Local embeddings (nomic-embed-text or bge-m3 via
Ollama) + sqlite-vec for "books about X" and "where did I read Y".

## Phase 3b — discovery

1. **Series and author gap reports** — the collection is author-clustered,
   which makes this unusually productive. Examples visible already: Star Trek
   Logs 6, 9, 10 missing; Blish *Star Trek* 3–7, 9–11; Rama, Foundation and
   Ender sequences have gaps; Baxter's Xeelee and Manifold sequences partial;
   Reynolds' Revelation Space universe partial.
2. Adjacent authors (co-subject and co-shelved on Open Library).
3. New-release watch for favourite authors.
4. Buy / borrow links (local library, used-book shops).

---

## Open decisions

| decision | options | leaning |
|---|---|---|
| Vision model for future reads | Claude API · local Qwen-VL | API for accuracy; test local |
| Shelf location naming | photo ID · room/case/shelf codes · free text | room/case/shelf, set during review |
| Hosting | local + Tailscale · small cloud VM | local + Tailscale |
| Highlights source | Kindle · Readwise · none | ask: does a Readwise/Kindle export exist? |
| Barcode intake for new books | yes · later | later, after Phase 1b |
| External sync | Goodreads · LibraryThing · none | none until Phase 2 |
| Repo visibility | public · private | — |
