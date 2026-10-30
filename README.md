# Virtual Bookshelf

A browsable, searchable catalogue of my physical books, built from photos of
the shelves. Starts as a store-style library view (covers, author, details);
grows into reading lists, cross-book quote and topic search, and a way to find
the next book to read or buy.

Runs locally on the iMac with open-source tools. Nothing leaves the machine
except lookups to public book-metadata APIs.

**Where things stand:** Phase 1a is done — the spines have been read and
`data/books.csv` holds a first-pass catalogue of 521 items. See
[docs/STATUS.md](docs/STATUS.md) for the numbers and
[docs/ROADMAP.md](docs/ROADMAP.md) for what comes next.

## Layout

```
data/
  books.csv          one row per physical book: photo, stack, position,
                     title, author, confidence, notes   ← the catalogue
  books_unique.csv   same, with flagged duplicate copies collapsed
  drive_files.tsv    Drive file IDs for the 31 shelf photos
scripts/
  fetch_photos.py    get the HEICs from Google Drive into photos/raw/
  heic2jpg.py        HEIC → JPEG using only ffmpeg + Pillow (no libheif needed)
  make_previews.py   batch-convert photos/raw/ → photos/jpg/ (+1600px previews)
  report.py          counts, top authors, review queue from books.csv
docs/
  STATUS.md          what has been done, results, known gaps
  ROADMAP.md         phases, next steps, open decisions
photos/              (git-ignored) raw/ HEICs and jpg/ conversions
```

## Setup

```bash
git clone https://github.com/sgwoods/virtual-bookshelf.git
cd virtual-bookshelf
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg            # only needed for heic2jpg.py; macOS can use sips instead
```

## Reproducing Phase 1a

1. **Photos.** Download the Drive folder into `photos/raw/`
   (see the docstring in `scripts/fetch_photos.py` for three ways).
2. **Convert.** `python3 scripts/make_previews.py --workers 4`
   On a Mac, `sips -s format jpeg photos/raw/*.HEIC --out photos/jpg/` is faster.
3. **Read spines.** This pass was done by a vision model looking at each
   1600px preview and transcribing title/author per spine, zooming into the
   full-resolution JPEG for anything ambiguous. The result is `data/books.csv`.
   To re-run or extend it, see ROADMAP → "Phase 1a tooling".
4. **Check.** `python3 scripts/report.py --review`

## Data conventions (`books.csv`)

| column       | meaning |
|--------------|---------|
| `photo`      | source frame, e.g. `IMG_8884` — doubles as a shelf location |
| `stack`      | which group in the frame: `left`/`middle`/`right`/`far-right`/`stack`/`shelf` |
| `position`   | order within the stack, top-to-bottom or left-to-right; `0` = not a book (DVD, CD, guide) |
| `title`, `author` | as read from the spine; `(ed.)`, `(trans.)` kept in the author field |
| `confidence` | `high` = legible; `medium` = inferred or partly hidden; `low` = needs a look at the shelf |
| `notes`      | publisher/format when visible; `second copy`, `overlap`, or `same copy` flags duplicates |

The `photo + stack + position` triple is the book's shelf address until a
proper location scheme replaces it (see ROADMAP, open decisions).

## License

MIT — see [LICENSE](LICENSE).
