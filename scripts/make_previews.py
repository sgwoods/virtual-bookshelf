#!/usr/bin/env python3
"""Convert every HEIC in photos/raw/ to a full-size JPEG plus a 1600px preview.

Usage:  python3 scripts/make_previews.py [--workers N]

Skips files already converted. Uses heic2jpg.py (ffmpeg + Pillow only) so it
runs anywhere ffmpeg exists; on a Mac you can instead run
`sips -s format jpeg photos/raw/*.HEIC --out photos/jpg/` which is much faster.
"""
import argparse, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW, JPG = ROOT / "photos/raw", ROOT / "photos/jpg"
HEIC2JPG = Path(__file__).with_name("heic2jpg.py")


def convert(heic: Path) -> str:
    stem = heic.stem
    full, small = JPG / f"{stem}.jpg", JPG / f"{stem}_small.jpg"
    if not full.exists():
        r = subprocess.run([sys.executable, "-I", str(HEIC2JPG), str(heic), str(full)],
                           capture_output=True, text=True)
        if r.returncode:
            return f"FAIL {stem}: {r.stderr.strip().splitlines()[-1] if r.stderr else '?'}"
    if not small.exists():
        im = Image.open(full)
        im.thumbnail((1600, 1600))
        im.save(small, quality=85)
    return f"ok   {stem}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    JPG.mkdir(parents=True, exist_ok=True)
    heics = sorted(RAW.glob("*.HEIC")) + sorted(RAW.glob("*.heic"))
    if not heics:
        sys.exit(f"no HEIC files in {RAW} — run fetch_photos.py first")
    with ThreadPoolExecutor(args.workers) as ex:
        for line in ex.map(convert, heics):
            print(line, flush=True)


if __name__ == "__main__":
    main()
