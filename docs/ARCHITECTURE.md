# Virtual Bookshelf — architecture

What exists in this repository today, and how the pieces connect. It describes
the code as it stands, not the plan: what comes next is in
[ROADMAP.md](ROADMAP.md), and the dated log of work and results is in
[STATUS.md](STATUS.md).

> This is the one document here that makes claims about what exists, so it is
> checked. `tests/test_docs.py` fails if a path named here in backticks is
> missing, a relative link is broken, or a command names a script that does not
> exist. Counts are not checked here; STATUS.md records them with their date.

The site is published to <https://sgwoods.github.io/virtual-bookshelf/> by
the workflow in §5; which commit is live is whatever its `build.json` names.
The portfolio hub at <https://sgwoods.github.io/public/> reads that file to
build this project's entry (registration: `sgwoods/public` PR #18).

## 1. What this is

A catalogue of Steven's physical books, built from photos of the shelves, and a
cover-first page to browse it. Three stages, each a plain script reading and
writing files in `data/`:

```
shelf photos (Google Drive, not in git)
   │  spine read by a vision model (Phase 1a, done by hand-run session)
   ▼
data/books.csv ──── scripts/resolve.py ───▶ data/resolved.csv
   ▲   the catalogue    Open Library lookup      status, score, work id,
   │   (source of        + Google Books           year, cover, ISBNs,
   │    truth)            fallback                 subjects, candidates
   │                                                    │
   └── scripts/review.py ◀──────────────────────────────┘
        local review page → data/overrides.csv (+ fixes into books.csv)

data/books.csv + data/resolved.csv + data/reading.csv
   │  scripts/build_site.py, filling site/template.html
   ▼
_site/index.html (+ build.json in CI) ──▶ GitHub Pages
```

Everything is Python standard library plus one static HTML page. Nothing needs
installing to run the lookup, review or site build; `requirements.txt` lists
Pillow, used only by the Phase 1a photo tools.

## 2. Data

| file | role | edited by |
|---|---|---|
| `data/books.csv` | one row per physical item, as read from the spine. **Source of truth.** | spine read; review page corrections |
| `data/books_unique.csv` | convenience copy with flagged duplicates collapsed | derived |
| `data/resolved.csv` | lookup result per row (see §3) | `scripts/resolve.py` only |
| `data/overrides.csv` | review decisions; always win over the lookup | `scripts/review.py` |
| `data/reading.csv` | optional reading status for the site: `title,status,progress`. **Git-ignored and never published** until the owner approves what reading data goes public | by hand, locally |
| `data/drive_files.tsv` | Drive file id per shelf photo, used for photo links | Phase 1a |
| `data/cache/` | raw API responses, so re-runs are free (git-ignored) | `scripts/resolve.py` |

Rows are keyed by `photo:stack:position`. Position `0` marks a non-book item
(DVD, CDs, a guide); those rows are skipped by every later stage. The README's
"Data conventions" section defines each `books.csv` column.

## 3. Lookup — `scripts/resolve.py`

For each row: an Open Library title+author search, then a free-text search, a
title-only search, and — when the title has a subtitle — a main-title search;
Google Books is tried only if none of those reach a match. Every candidate is
scored:

- **title** similarity after normalising (case, accents, punctuation, leading
  articles, number words). The candidate is scored both as listed and with its
  `(…)` / `[…]` notes and a trailing "by *author*" removed, keeping the better
  score. Main title and subtitle are compared separately, splitting on `:` or a
  spaced dash (so *Ishmael (Star Trek #23)* meets *Star Trek - Ishmael*), and
  the prefixes "Isaac Asimov's", "Isaac Asimov Presents" and "Douglas Adams's"
  may be dropped from either side.
- **author**: full credit if the spine surname appears among the candidate's
  authors; half credit if the candidate's author is written only in a
  non-Latin script; otherwise none.

`score = 0.7 × title + 0.3 × author`. `matched` ≥ 0.80, `weak` ≥ 0.55,
otherwise `none`. A title below 85 % similarity can never be `matched`, so
*Dune* is never silently filed as *Dune Messiah*. Unknown spines and theses are
`skipped`. After review, decisions give `confirmed`, `confirmed-unlisted` or
`not-a-book`.

The match is to an Open Library **work**, not an edition: `isbns` lists ISBNs
from several editions, and `year` is Open Library's `first_publish_year`,
which is sometimes a reprint year (STATUS.md lists the known cases).

Run modes: `python3 scripts/resolve.py` (new and changed rows; resumes),
`--retry` (re-score weak and none rows from cache), `--refresh` (everything),
`--limit N`, `--photo IMG_xxxx`.

## 4. Review and everyday actions — `scripts/review.py`, `scripts/pipeline.py`

`python3 scripts/review.py` serves a local page at `http://127.0.0.1:8765/`.

**Cards.** First, every row whose spine read is below high confidence or whose
lookup is weak, none or skipped. Then **quick checks**: confident matches whose
title leaves out the spine's subtitle ("Manifold: Time" → "Manifold") — usually
the same book, sometimes not (*Serenity: Better Days* is not *Serenity*), so a
person decides; nothing is demoted automatically. Each card shows the spine
read, a link to its shelf photo, and up to four candidates with covers.
Decisions — use this candidate, best guess is right / looks right, not listed,
not a book, fix the spine read — are written to `data/overrides.csv`, and
spine corrections into `data/books.csv`.

Covers are shown large; click any cover for the full-size image. Each card
also shows the **shelf photo** the book was read from, labelled with its stack
and position — a local copy from `photos/` if present, otherwise Drive's
thumbnail of the private photo (it loads because the browser is signed in to
Google; nothing is downloaded or published). Click to enlarge, click again to
zoom.

Each card also links to a **Google Images** search for the spine read, opened
in a new tab for a person to look at: seller photos often show the ISBN,
publisher and catalogue number. Nothing is fetched automatically, and those
images are never used as covers.

When no candidate is right: **Search harder** runs wider Open Library and
Google Books searches with more results; **Search by text or ISBN** searches
for exactly what is typed, or looks an ISBN up directly (the surest route for a
book in hand). **Edit & use** confirms a candidate with corrected title,
author, year or ISBN (e.g. a reprint year); **Not listed — add details**
records year, publisher and ISBN for books no catalogue has. Edited details
travel in the decision (`pick_json` in `data/overrides.csv`) and win in
`data/resolved.csv`.

**Actions bar.** The header shows lookup counts, the git branch, the number of
decisions and whether any data is not yet pushed, and buttons for the steps in
`scripts/pipeline.py`, run one at a time with their output in a log panel:

| button | step | what it does |
|---|---|---|
| Get latest | `update` | switch to `main` and fast-forward from GitHub; refuses while review data is unpublished |
| Retry lookups | `retry` | `resolve.py --retry` (uses the network) |
| Apply decisions | `apply` | `resolve.py`: fold `data/overrides.csv` into `data/resolved.csv` |
| Rebuild site | `build` | `build_site.py`, then opens the preview at `/site/` |
| Run tests | `test` | the unit tests |
| Save & push | `save` | apply, then commit the data files on a `review-YYYYMMDD-HHMM` branch (never `main`) and push it; the log links to the pull request |
| Finish | `finish` | apply → build → test → push, stopping at the first failure, then preview |

The same steps run from Terminal: `python3 scripts/pipeline.py finish` (or
`status`, `update`, `retry`, `apply`, `build`, `test`, `publish`, `save`).
Publishing only ever adds `data/books.csv`, `data/resolved.csv` and
`data/overrides.csv`.

**Who can use it.** The server binds to 127.0.0.1 and answers only requests
whose Host header is its own address; every POST must carry the per-session
token embedded in the page. Another website open in the same browser therefore
cannot record decisions or start a push.

## 5. The site and how it is published

`python3 scripts/build_site.py` writes `_site/index.html`: one self-contained
page (inline CSS and JavaScript, data embedded as JSON) built from
`site/template.html`. Open it straight from disk to preview.

- **Every book in `data/books.csv` appears.** Copies of the same title share one
  card ("2 copies").
- **Covers** come from Open Library and are shown only for `matched` or
  `confirmed` rows. Any other book gets a coloured title card marked
  **Cover missing**; a known cover that cannot be fetched (offline) is marked
  **Cover offline**.
- **Filters**: All / Currently Reading / Finished, from `data/reading.csv`
  when it exists locally; books not listed are `unread`. A thin bar at the
  foot of the cover shows progress for books being read. Because that file is
  git-ignored, the published page has every book `unread` and the two status
  filters are empty.
- Cards link to an Open Library search; the footer links back to the portfolio
  hub, this document and the roadmap.

`.github/workflows/pages.yml` publishes it, in the same three-job shape as
Star Swarm's CI:

1. **check** — compiles the scripts, runs `python3 -m unittest discover -s tests`,
   builds `_site/`, and writes `_site/build.json`:
   `{"commit", "dirty", "mode", "builtAt", "builtAtMs"}`, with `mode` `release`
   only on `main`. The tested bundle is packaged as is.
2. **deploy** — publishes that bundle to GitHub Pages (main only).
3. **notify-hub** — waits until the live `build.json` names this commit, then
   dispatches `render-public-index.yml` in `sgwoods/public` using the
   `PUBLIC_HUB_DISPATCH_TOKEN` secret. Without the secret it warns and succeeds;
   the hub's daily run picks the build up instead.

The hub owns the portfolio record and project page for this repository; nothing
here writes to it.

## 6. Tests — `tests/`

Standard library `unittest`, no network:

- `tests/test_resolve.py` — scoring cases that must match (series naming,
  bracketed notes, franchise prefixes, non-Latin authors) and look-alikes that
  must not (*Dune* / *Dune Messiah*, same title by another author).
- `tests/test_site.py` — every catalogued book is on the page, the data is
  embedded and well-formed, and no external scripts or stylesheets are loaded.
- `tests/test_review.py` — the quick-check rule, that the page script parses,
  and that requests without the token or from another host are refused.
- `tests/test_pipeline.py` — against a throwaway repository with a local
  origin: publishing goes to a review branch, commits only the data files and
  never moves `main`; updating refuses over unpublished data.
- `tests/test_docs.py` — this document against the tree.

## 7. Phase 1a tools

`scripts/fetch_photos.py`, `scripts/heic2jpg.py` and `scripts/make_previews.py`
fetch and convert the shelf photos; `scripts/report.py` prints counts, top
authors and the review queue from `data/books.csv`. Photos stay in Drive and in
the git-ignored `photos/` folder.

## 8. Not here yet

No database, no downloaded covers, no search box, no per-book detail page, no
shelf-location scheme beyond `photo:stack:position`, and no published reading
data (the local `data/reading.csv` is all there is). ROADMAP.md orders these.
