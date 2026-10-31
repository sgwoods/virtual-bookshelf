# Status — 2026-10-30

This is the dated log of work and results. What exists and how it works is in
[ARCHITECTURE.md](ARCHITECTURE.md); what comes next is in [ROADMAP.md](ROADMAP.md).

## Latest (Oct 31)

- **Spines outlined, auto-crop, Google in a side window.** The review card
  outlines the book's spine on its shelf photo (from `data/spines.csv`) and
  opens just that spine on click, with **Turn to read**. Downloaded images are
  cropped automatically (margins trimmed; one spine picked out of several) —
  accept with Save these. Google Images opens in a side window that the
  bookmark closes after sending. **Import shelf photos** brings the Drive
  photos onto the Mac; outlining all 521 spines is next. 73 tests.

- **No more Terminal for updates.** The review page shows a banner when a new
  version is on GitHub; **Update & restart** brings it in (keeping
  unpublished review data) and restarts the page in place. **Restart** is
  always in the bar. 66 tests.

- **Your images on the public site.** Each image records where it came from
  automatically (macOS's "Where from" for downloads, or the new **📚 Add to
  bookshelf** bookmark, which sends the clicked picture on Google Images
  straight to the card). An **On public site** switch per image (on by
  default); Save & push / Finish publish web-sized copies to `site_images/`
  with sources in `data/images.csv`, and the public page shows them with a
  small "image · source" credit. 59 tests.

- **Your own images.** Images saved to Downloads (e.g. from the Google Images
  link) appear on the card you were working on; crop to just this book
  (one spine out of several, or just the cover), rotate, label Cover or Spine,
  save. Kept in `images/` on the Mac with the original for re-cropping; shown
  on review cards and in the local preview. Publishing them on the public
  site is planned as ROADMAP step 4c. 49 tests.

- **Review cards for real decisions** (from the first review session): covers
  about three times larger and click-to-enlarge; the shelf photo on every card
  with the spine's stack and position; **Search harder** and **search by text
  or ISBN** when no candidate is right (e.g. Sawyer's *Wake* came back only
  as Gaiman's *The Wake*); **Edit & use** to correct a candidate's details;
  **Not listed — add details**. 33 tests.
- **Spines are now a core requirement**: the shelf view will be built from
  real spine crops that can be rearranged like a real shelf. ROADMAP step 4b
  plans spine outlines in `data/spines.csv` and the crops.

- **Review page is now the control panel.** Buttons for get latest, retry
  lookups, apply decisions, rebuild and preview the site, run tests, save &
  push (on a review branch, never `main`) and Finish (all of it in order);
  the same steps from Terminal with `python3 scripts/pipeline.py finish`.
  Requests need the page's per-session token, so other websites cannot use it.
- **Quick checks:** 31 confident matches leave out the spine's subtitle; they
  now appear after the main queue for a one-click "Looks right". Found by the
  networked `--retry` on Oct 30, which lifted matches to 498 but matched
  *Serenity: Better Days* to plain *Serenity*.
- **Lookup now:** 498 matched · 11 weak · 6 none · 6 skipped (MacBook, after a
  networked `--retry`; not yet pushed). Review: 3 decisions made so far.
- Tests: 26 (added review-page guard and quick checks, publish/update git
  steps against a throwaway repository, and a parse check of the page script).

## Oct 30, evening

**Full Open Library lookup run** (MacBook, all 521 items):

```
matched 478 (92%) · weak 26 · none 11 · skipped 6 (4 unreadable spines, 2 theses)
```

- **Spot check:** 15 random `matched` rows were all the right work. Two had
  wrong years (*Legacy* 1960, really 1995; *Hunchback* 1968, a reprint). The
  lookup matches works, not editions, so editions were not checked.
- **Why the 37 weak/none rows missed:**

  | cause | n | handled by |
  |---|---|---|
  | series naming ("Star Trek - Ishmael" vs "Ishmael (Star Trek #23)") | 3 | resolve.py fix |
  | notes in Open Library's title ("[32 essays]", "(Von Neuman)", "…By Philip K. Dick") | 6 | resolve.py fix |
  | "Isaac Asimov's …" prefix on one side only | 1 | resolve.py fix |
  | author listed only in Chinese/Cyrillic (刘慈欣, Лев Толстой) | 4 | resolve.py fix |
  | long subtitle sinks the search (*Computers and Intractability*, *Redemption of Time*) | 2 | resolve.py fix (needs live run) |
  | same title, different book ranked first (*Wake*, *Dark Forest*, *Three-Body Problem*, *Other Minds*, *Death's End*) | 5 | review |
  | co-author / pen name / translation (*Sphereland*, *Tom Sawyer*, *Measure of Reality*) | 3 | review |
  | series volumes (*Great SF Stories 5*, *Chinese Horoscopes: Snake*, *Semantics of Spec. Languages*) | 3 | review |
  | small press, exhibition catalogue, magazine, comic | 6 | review — most aren't listed anywhere |
  | CS monographs (incl. *Constraint-Based Design Recovery*) | 2 | review |
  | spine misread / partly hidden (*Best of Trek 2*, *We Built This Vol 1*) | 2 | review |

- **resolve.py scoring fix** (patterns above) plus a `--retry` flag that
  re-scores only weak/none rows. Applied on the MacBook from the response
  cache: **494 matched · 11 weak · 10 none · 6 skipped**, no existing match
  lost (two more than the offline estimate: *The Dark Forest* and *Death's
  End* now match Cixin Liu's series volumes). New requests — the main-title
  retry and some Google Books fallbacks — could not be made from that session,
  so those rows keep their earlier result; a networked `--retry` may lift a
  few more.
- **Years that look wrong** (Open Library `first_publish_year`; not fixable in
  code — plan a manual year column with the SQLite step):
  - impossible: *The Folk of the Fringe* 1777 (1989), *Letters to a Young Poet*
    1656 (1929), *The Prestige* 1901 (1995), *Legacy* 1960 (1995)
  - reprint years: *Children of the Lens* 2017, *Skylark Three* 2013,
    *Childhood's End* 1995 (both copies), *Frankenstein* 2017, *Origin of
    Species* 2013, *Don Quixote* 2015, *Flatland* 2018, *One Hundred Years of
    Solitude* 2007, *Three Musketeers* 1933, *Hunchback* 1968, *Bicentennial
    Man* 1999, *Otherland* 2021
  - year or match suspect, re-check after review: *The God Delusion* 2001,
    *Origin* (Brown) 2013, *The Rift* 1968, *Demons* 2000, *Dwellers in the
    Crucible* 2000, *Space Odyssey* 2018
- **Review:** not yet done. **32 cards** are queued (low-confidence spine
  reads, weak/none lookups, skipped rows). Outcome to be recorded here.

**Cover grid site** — `scripts/build_site.py` builds a single static page of
every book: 521 items, 499 titles; titles without a confirmed cover show a
titled "Cover missing" card. Reading status is not published:
`data/reading.csv` is local and git-ignored until the owner approves what
reading data goes public, so every book shows as unread.

**Portfolio integration** — this repo follows the hub's observed-project
contract (Star Swarm pattern: a deployed `build.json`, `docs/ARCHITECTURE.md`
checked by tests, `docs/ROADMAP.md`). Hub-side registration is
`sgwoods/public` PR #18, reviewed and merged there.

**Where each piece stands**

| | state |
|---|---|
| lookup run, scoring fix, `--retry` | done (numbers above) |
| review of the 32 queued cards | not started |
| cover-grid page, tests (`python3 -m unittest discover -s tests`, 12 tests) | built and passing locally; CI runs them on every push and PR |
| deployment to GitHub Pages | by `.github/workflows/pages.yml` on push to `main`; needs repository Settings → Pages → Source set to **GitHub Actions**. The live commit is whatever `build.json` names |
| hub notification | `notify-hub` job; needs the optional `PUBLIC_HUB_DISPATCH_TOKEN` secret, otherwise the hub's daily run picks the build up |
| covers download, SQLite, search/detail pages, Phase 2 reading data | planned (ROADMAP) |

**Next:** review (`python3 scripts/review.py`, then `python3 scripts/resolve.py`),
commit `data/`, push.

## Earlier (Oct 30, afternoon)

- Repo created and pushed: github.com/sgwoods/virtual-bookshelf. Working
  copy on the MacBook at `~/Developer/virtual-bookshelf`.
- Phase 1b steps 1–2 built: `scripts/resolve.py` (Open Library lookup,
  Google Books fallback) and `scripts/review.py` (local review page).
- **20-book live trial: 20/20 matched** (Gor, Lensman/Skylark, Star Trek
  Blish and Log volumes). Watch-out: Open Library's `first_publish_year`
  is sometimes a reprint year (*Children of the Lens* → 2017, *Skylark
  Three* → 2013) — sanity-check years before relying on them.
- Next was the full run — done the same day, see above.

## Summary

Phase 1a (photo → first-pass catalogue) is complete. 31 shelf photos were
taken on Oct 27–28, read on Oct 28, and the result is `data/books.csv`:
**521 physical items, ~500 distinct titles, 509 of them read with high
confidence.** The earlier estimate of 600–900 titles was high; the stacks are
shallower than the first two sample photos suggested.

(At the end of Phase 1a nothing was built on the CSV yet; Phase 1b since added
the lookup, review page and cover grid — see Latest.)

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
