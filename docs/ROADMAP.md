# Roadmap

The full plan is the Claude Doc "Virtual Bookshelf — Plan"
(https://claude.ai/artifact/AhsbdwHeufjhoLcPi5zvsy). This file tracks the
working version: what's done, what's next, and what Phase 1a taught us.
What exists today is described in [ARCHITECTURE.md](ARCHITECTURE.md); dated
results are in [STATUS.md](STATUS.md).

```
Phase 1a  photos → books.csv                      ✅ done (Oct 28)
Phase 1b  resolve → SQLite → browsable catalogue  🔨 in progress (lookup run; review next; cover grid built)
Phase 2   lists, tags, notes, reading status
Phase 3a  quotes and topics across books
Phase 3b  discovery: gaps, adjacent authors, what to buy
```

Gate from the plan still holds: **finish the Phase 1 review before starting
Phase 2.** A catalogue with wrong books in it poisons everything downstream.

---

## Phase 1b — next steps, in order

### 1. Resolve against Open Library  ✅ done — full run Oct 30: 478 matched, 26 weak, 11 none, 6 skipped
Scoring fix the same day (series naming, title notes, franchise prefixes,
non-Latin author names, long subtitles) plus `--retry`: 494 matched, 11 weak,
10 none, 6 skipped. Details in STATUS.md.

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

### 2. Review page  ✅ built — `scripts/review.py` · review not yet done (32 cards queued)
A single local page listing every row that is (a) below high confidence from
the spine read, or (b) a weak/no Open Library match. Each row shows the
spine read, a link to its shelf photo, and up to four candidates with covers;
actions are use-this / not listed / not a book / fix the spine read.
(Cropped spine images need per-spine bounding boxes, which the Phase 1a read
didn't record — a later improvement to `read_spines.py`.) Writes corrections back to `books.csv`. This is where the 12
review-queue items and the lookup misses get cleared — the 4 unreadable ones
by taking the book off the shelf.

### 2b. Public cover grid  ✅ built — `scripts/build_site.py`, deployed by `.github/workflows/pages.yml`
A static, self-contained page of every book — covers where confirmed, a titled
"Cover missing" card otherwise, All / Reading / Finished filters — tested in CI
and deployed by the workflow to https://sgwoods.github.io/virtual-bookshelf/
with a `build.json`, for the portfolio at https://sgwoods.github.io/public/
(Star Swarm's observed-project contract). This brings forward the cover-grid
part of step 5; search, facets and detail pages remain in step 5. Reading
status stays local until the open decision below is made.

**Still to do:** hub registration is `sgwoods/public` PR #18 (merged by the
hub maintainer); the optional `PUBLIC_HUB_DISPATCH_TOKEN` secret here for
immediate hub refreshes.

### 3. Covers  *(minutes, automated)*
Download covers from `covers.openlibrary.org/b/id/{cover_id}-L.jpg` into
`covers/` (git-ignored). For misses, crop the book's front from a photo
later. The site already shows a titled "Cover missing" placeholder for every
title without a confirmed cover; those are the work list.

### 4. Book metadata in the project database
Move from CSV to `bookshelf.sqlite`, and make it the one place book metadata
lives — the site is generated from it, never from the CSVs directly:
- `works` — one per title (Open Library work): title, subtitle, first year,
  description, subjects, page count, cover id, plus **manual overrides** that
  always win (year — see STATUS for the known reprint years — title, category)
- `copies` — one per physical book: work_id, shelf location, format,
  publisher, edition/ISBN, condition, notes
- `authors`, `work_authors`
- `categories` — a short curated list of major categories (see open
  decisions), each work in one primary category plus optional extras
- FTS5 index over title/author/subjects/notes

Enrichment pass: fetch the Open Library work and edition records for every
matched/confirmed book (description, subjects, page count, publisher), cached
like the lookup. `books.csv` stays the human-editable import source until the
review page can edit the database directly. The build step exports a
`books.json` from the database for the site.

### 5. Browse UI — one page, three views, one book focus
Requirements (Oct 30): everything on the same page, switching views without
losing your place, and every view able to open a book in place.

- **Covers view** — the current grid (step 2b).
- **Search view** — a search box over title, author, subject and notes, with
  facets and sort on the major categories: category, author, decade, subject,
  shelf location, format (and reading status, once Phase 2 decides what is
  public). Results as a dense list/table.
- **Shelf view** — the books as their **real spines**, cropped from the shelf
  photos (step 4b), standing in their real shelf order and grouped by case and
  shelf — a beautiful virtual bookshelf. Hover shows title and author; click
  opens the book. Shelves can be **reassembled and reordered** like a real one:
  by author, category, colour, height, year, or by hand (drag), with saved
  arrangements. A generated spine (colour, width from page count, vertical
  title) stands in only where no crop exists yet.
- **Book focus** — an in-page panel or overlay, not a jump to Open Library:
  cover, full metadata from the database, all copies and where each sits on
  the shelf, subjects as links back into Search, and the Open Library link.
  Deep-linkable (`#book/<id>`), and the URL also carries the current view,
  query, filters and sort, so any state can be bookmarked or shared.

Stays a static site on GitHub Pages: the database is exported to JSON at build
time and the page does search, sort and filtering in the browser (≈500 titles
is small). Order of work: database + enrichment (step 4) → view switcher and
book focus over the existing data → search, facets and sort → shelf view.
This is the Phase 1 finish line.

---

### 4b. Spine capture  *(needed for the shelf view; Oct 31 requirement)*
Record where every spine is in its photo, then cut it out:
- extend the spine read so each row gets a **spine outline** in its photo
  (a four-point polygon, since spines are often slightly tilted), stored in
  `data/spines.csv` keyed by row id; backfill the 521 existing rows by
  re-reading the 30 photos with that prompt and checking the outlines against
  `photo:stack:position`;
- `scripts/crop_spines.py` — straighten and crop each outline from the
  full-resolution photo into `spines/<row_id>.jpg`, with its pixel height and
  width (the shelf view uses them for true relative sizes) and dominant colour;
- a review pass for spines: the review page shows each crop beside the book so
  a bad outline is fixed by dragging its corners;
- better versions later: re-shoot individual shelves, or photograph single
  spines, and replace a crop without touching the rest.

Until then the review page shows the whole shelf photo for each book (from
Drive, or a local copy), labelled with the spine's stack and position.

## Phase 1a tooling (to make the read repeatable)

The spine read was done interactively. To make adding a new shelf a
one-command job:
- `scripts/read_spines.py` — sends each preview (and left/right halves) to a
  vision model with a fixed prompt, gets back JSON rows in the `books.csv`
  schema plus each spine's outline for `data/spines.csv` (step 4b), appends them. Claude via API is the known-good option; compare a
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
| Hosting | local + Tailscale · small cloud VM · GitHub Pages | **decided Oct 30:** public cover grid on GitHub Pages; lookup/review tools stay local |
| Highlights source | Kindle · Readwise · none | ask: does a Readwise/Kindle export exist? |
| Barcode intake for new books | yes · later | later, after Phase 1b |
| External sync | Goodreads · LibraryThing · none | none until Phase 2 |
| Repo visibility | public · private | **decided Oct 30:** public, as part of the portfolio hub |
| What reading data is public | all · status only · none | none for now: `data/reading.csv` is git-ignored; decide before Phase 2 |
| Major categories for search and sort | Open Library subjects as-is · curated list · both | curated list seeded from how the shelves are already grouped (SF by author, Sherlock Holmes, Harry Potter, politics, science/philosophy/AI, CS theory and theses, classics, recent reads), with Open Library subjects as secondary facets |
| Spine images in the shelf view | generated spines · crops from the shelf photos | **decided Oct 31: real spine crops** (step 4b), generated spines only as stand-ins. Still to decide: publish the crops on the public site (they are small parts of the private shelf photos) or keep the spine view local |
