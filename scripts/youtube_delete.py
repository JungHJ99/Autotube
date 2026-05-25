#!/usr/bin/env python3
"""youtube_delete.py — delete YouTube videos by ID.

Companion to youtube_upload.py. Reuses the same OAuth token
(~/.config/autotube/token.json). The youtube.upload scope is not enough to
delete; the cached token also carries the broader youtube scope, which is.

Usage:
  python3 scripts/youtube_delete.py <videoId> [<videoId> ...]
  python3 scripts/youtube_delete.py --dry-run <videoId>
"""
import argparse
import sys

from youtube_upload import get_credentials, DEFAULT_CLIENT_SECRET, DEFAULT_TOKEN
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("video_ids", nargs="+", help="YouTube video IDs to delete")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--client-secret", default=DEFAULT_CLIENT_SECRET)
    p.add_argument("--token-file", default=DEFAULT_TOKEN)
    args = p.parse_args()

    if args.dry_run:
        for vid in args.video_ids:
            print(f"[dry-run] would delete {vid}")
        return 0

    creds = get_credentials(args.client_secret, args.token_file)
    service = build("youtube", "v3", credentials=creds, cache_discovery=False)

    rc = 0
    for vid in args.video_ids:
        try:
            service.videos().delete(id=vid).execute()
            print(f"[deleted] {vid}")
        except HttpError as e:
            print(f"[error] {vid}: {e}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
