#!/usr/bin/env python3
"""Download the shelf photos listed in data/drive_files.tsv into photos/raw/.

The photos are NOT in git (≈250 MB). They live in the Google Drive folder
  https://drive.google.com/drive/folders/1JzdleTTMrVzkyHPjlxewpk4VbQcn1uo0

Two ways to get them locally:

  1. Easiest on the iMac: open the folder in Drive, select all, Download,
     unzip into photos/raw/.  Done.

  2. Scripted, with the Drive CLI `gdrive` or `rclone` configured:
       rclone copy gdrive:"<folder>" photos/raw/ --include "*.HEIC"

This script implements option 3: direct download via the Drive API using
google-api-python-client, if you've set up OAuth credentials at
~/.config/virtual-bookshelf/credentials.json.  It's here so the pipeline is
reproducible end to end, but for 31 files option 1 is fine.
"""
import csv, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "photos/raw"
LIST = ROOT / "data/drive_files.tsv"
CREDS = Path.home() / ".config/virtual-bookshelf/credentials.json"
TOKEN = Path.home() / ".config/virtual-bookshelf/token.json"


def main():
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload
    except ImportError:
        sys.exit("pip install google-api-python-client google-auth-oauthlib  "
                 "(or just download the Drive folder by hand into photos/raw/)")

    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    creds = Credentials.from_authorized_user_file(TOKEN, scopes) if TOKEN.exists() else None
    if not creds or not creds.valid:
        if not CREDS.exists():
            sys.exit(f"no OAuth client at {CREDS}; see docstring")
        creds = InstalledAppFlow.from_client_secrets_file(str(CREDS), scopes).run_local_server(port=0)
        TOKEN.parent.mkdir(parents=True, exist_ok=True)
        TOKEN.write_text(creds.to_json())

    svc = build("drive", "v3", credentials=creds)
    RAW.mkdir(parents=True, exist_ok=True)
    rows = list(csv.reader(open(LIST), delimiter="\t"))
    for name, file_id in rows:
        out = RAW / f"{name}.HEIC"
        if out.exists():
            print("have", name); continue
        req = svc.files().get_media(fileId=file_id)
        with open(out, "wb") as f:
            dl = MediaIoBaseDownload(f, req)
            done = False
            while not done:
                _, done = dl.next_chunk()
        print("got ", name)


if __name__ == "__main__":
    main()
