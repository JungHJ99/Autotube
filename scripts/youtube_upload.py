#!/usr/bin/env python3
"""
youtube_upload.py — Stage 12 of gukppong-pipeline.

Uploads output/<run>/video.mp4 to YouTube using metadata from segments.json
(youtube.{title, description, hashtags}) and the rendered thumbnail.png.

Auth: OAuth 2.0 (Desktop app type). One-time browser consent saves a refresh
token; subsequent uploads run non-interactively.

Safe defaults:
- privacyStatus = "unlisted" (user must promote to public via Studio)
- madeForKids = false
- categoryId = 22 (People & Blogs)
- defaultLanguage / defaultAudioLanguage = "ko"

Usage (typical):
  python3 scripts/youtube_upload.py --run output/<run>/
  python3 scripts/youtube_upload.py --run output/<run>/ --public   # publish immediately
  python3 scripts/youtube_upload.py --run output/<run>/ --dry-run  # print only

OAuth setup: see scripts/README_youtube_oauth.md
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

# Google API
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube",
          "https://www.googleapis.com/auth/youtube.readonly"]

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "autotube"
DEFAULT_CLIENT_SECRET = DEFAULT_CONFIG_DIR / "client_secret.json"
DEFAULT_TOKEN = DEFAULT_CONFIG_DIR / "token.json"

CHUNK_SIZE = 1024 * 1024 * 4  # 4 MB chunks for resumable upload


def get_credentials(client_secret_path: Path, token_path: Path) -> Credentials:
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[oauth] refreshing token...")
            creds.refresh(Request())
        else:
            if not client_secret_path.exists():
                print(f"ERROR: client_secret.json not found at {client_secret_path}", file=sys.stderr)
                print("\nOne-time OAuth setup required. See scripts/README_youtube_oauth.md\n", file=sys.stderr)
                sys.exit(2)
            print(f"[oauth] running first-time browser auth flow ({client_secret_path})")
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
            # run_local_server: opens browser, captures auth code on localhost
            creds = flow.run_local_server(port=0,
                                          authorization_prompt_message="브라우저가 열렸을 거임. Google 로그인 후 권한 승인 클릭.",
                                          success_message="인증 완료. 이 탭은 닫아도 됨.")

        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        os.chmod(token_path, 0o600)
        print(f"[oauth] token saved → {token_path}")

    return creds


def load_meta(run_dir: Path) -> dict:
    """Pull youtube.{title, description, hashtags} from segments.json."""
    seg_path = run_dir / "segments.json"
    if not seg_path.exists():
        raise SystemExit(f"segments.json not found: {seg_path}")
    doc = json.loads(seg_path.read_text(encoding="utf-8"))
    y = doc.get("youtube") or {}
    title = (y.get("title") or "").strip()
    desc = (y.get("description") or "").strip()
    hashtags = y.get("hashtags") or []
    if not title:
        raise SystemExit("youtube.title is empty in segments.json")
    return {"title": title, "description": desc, "hashtags": list(hashtags)}


def build_description(desc: str, hashtags: list[str]) -> str:
    """Append hashtags to the description (YouTube uses first 3 above-title).

    Hashtags can be either '#word' or 'word'; we always emit them as '#word'.
    """
    tags = [t.lstrip("#").strip() for t in hashtags if t and t.strip()]
    if not tags:
        return desc
    hash_block = " ".join(f"#{t}" for t in tags)
    if desc:
        return f"{desc}\n\n{hash_block}"
    return hash_block


def build_tags(hashtags: list[str]) -> list[str]:
    """YouTube tags field — strip '#', max 500 chars combined.

    Distinct from in-description hashtags; tags are an internal search signal.
    """
    out, total = [], 0
    for t in hashtags:
        clean = t.lstrip("#").strip()
        if not clean:
            continue
        # account for the comma separator YouTube counts between tags
        cost = len(clean) + (1 if out else 0)
        if total + cost > 480:  # leave headroom
            break
        out.append(clean)
        total += cost
    return out


def truncate_title(title: str, limit: int = 100) -> str:
    if len(title) <= limit:
        return title
    # truncate on word boundary
    cut = title[:limit - 1]
    sp = cut.rfind(" ")
    if sp > limit * 0.6:
        cut = cut[:sp]
    return cut + "…"


def upload_video(service, video_path: Path, meta: dict,
                 privacy: str, category_id: str,
                 dry_run: bool, lang: str = "ko") -> str | None:
    title = truncate_title(meta["title"], 100)
    description = build_description(meta["description"], meta["hashtags"])
    tags = build_tags(meta["hashtags"])

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
            "defaultLanguage": lang,
            "defaultAudioLanguage": lang,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
            "embeddable": True,
        },
    }

    print("\n=== UPLOAD PREVIEW ===")
    print(f"  file:       {video_path} ({video_path.stat().st_size / 1e6:.1f} MB)")
    print(f"  title:      {title}  ({len(title)} chars)")
    print(f"  privacy:    {privacy}")
    print(f"  category:   {category_id} (22=People&Blogs, 24=Entertainment, 25=News&Politics)")
    print(f"  tags:       {tags}  ({sum(len(t) for t in tags) + len(tags) - 1} chars)")
    print(f"  description ({len(description)} chars, first 200):")
    print("    " + description[:200].replace("\n", "\n    "))
    print("======================\n")

    if dry_run:
        print("[dry-run] skipping actual upload.")
        return None

    media = MediaFileUpload(str(video_path), chunksize=CHUNK_SIZE,
                            resumable=True, mimetype="video/mp4")
    req = service.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    last_pct = -1
    started = time.time()
    while response is None:
        try:
            status, response = req.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                if pct != last_pct:
                    print(f"  upload: {pct:3d}%  (elapsed {time.time()-started:.1f}s)")
                    last_pct = pct
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504):
                print(f"  retriable error {e.resp.status}, retrying in 5s...")
                time.sleep(5)
                continue
            raise

    vid = response["id"]
    elapsed = time.time() - started
    print(f"[upload] done in {elapsed:.1f}s — videoId={vid}")
    return vid


def upload_thumbnail(service, video_id: str, thumb_path: Path) -> bool:
    if not thumb_path.exists():
        print(f"[thumbnail] not found: {thumb_path} (skipping)")
        return False
    size = thumb_path.stat().st_size
    if size > 2 * 1024 * 1024:
        print(f"[thumbnail] WARNING: {size} bytes > 2 MB YouTube limit")
    print(f"[thumbnail] uploading {thumb_path} ({size // 1024} KB)...")
    media = MediaFileUpload(str(thumb_path), mimetype="image/png")
    try:
        service.thumbnails().set(videoId=video_id, media_body=media).execute()
        print("[thumbnail] set OK")
        return True
    except HttpError as e:
        # Thumbnail upload requires verified channel for non-default thumbnails.
        # Don't fail the whole pipeline — the video is already uploaded.
        print(f"[thumbnail] FAILED ({e}). Set manually in Studio.")
        return False


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path,
                   help="output/<run>/ directory (uses video.mp4 + segments.json + thumbnail.png)")
    p.add_argument("--video", type=Path,
                   help="explicit video file (overrides --run/video.mp4)")
    p.add_argument("--thumbnail", type=Path,
                   help="explicit thumbnail file (overrides --run/thumbnail.png)")
    p.add_argument("--segments", type=Path,
                   help="explicit segments.json (overrides --run/segments.json)")

    p.add_argument("--privacy", choices=["private", "unlisted", "public"],
                   default="unlisted",
                   help="privacy status (default: unlisted — promote via Studio later)")
    p.add_argument("--public", action="store_true",
                   help="shortcut for --privacy public")
    p.add_argument("--lang", default="ko",
                   help="defaultLanguage/defaultAudioLanguage (BCP-47). 'ko' for 파이널K, "
                        "'es-MX' for the MexiKorea (멕시코뽕) channel. Default ko.")
    p.add_argument("--category-id", default="22",
                   help="YouTube category ID. 22=People&Blogs (default), 24=Entertainment, 25=News&Politics")

    p.add_argument("--client-secret", type=Path, default=DEFAULT_CLIENT_SECRET,
                   help=f"OAuth client_secret.json (default: {DEFAULT_CLIENT_SECRET})")
    p.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN,
                   help=f"OAuth token cache (default: {DEFAULT_TOKEN})")

    p.add_argument("--dry-run", action="store_true",
                   help="print preview without uploading (no API call made)")
    p.add_argument("--no-thumbnail", action="store_true",
                   help="skip thumbnail upload")
    p.add_argument("--out-result", type=Path,
                   help="where to save upload_result.json (default: <run>/upload_result.json)")
    args = p.parse_args()

    # resolve paths
    if args.run:
        run = args.run
        video_path = args.video or (run / "video.mp4")
        seg_path = args.segments or (run / "segments.json")
        thumb_path = args.thumbnail or (run / "thumbnail.png")
        result_path = args.out_result or (run / "upload_result.json")
    else:
        if not (args.video and args.segments):
            print("ERROR: provide --run, OR both --video and --segments", file=sys.stderr)
            return 2
        video_path = args.video
        seg_path = args.segments
        thumb_path = args.thumbnail or video_path.parent / "thumbnail.png"
        result_path = args.out_result or video_path.parent / "upload_result.json"

    if not video_path.exists():
        print(f"ERROR: video not found: {video_path}", file=sys.stderr)
        return 2

    # load metadata via segments.json (we always read it via run/segments dirs)
    meta = load_meta(seg_path.parent)

    privacy = "public" if args.public else args.privacy

    # auth (skipped in dry-run since we don't make API calls)
    service = None
    if not args.dry_run:
        creds = get_credentials(args.client_secret, args.token_file)
        service = build("youtube", "v3", credentials=creds, cache_discovery=False)

    vid = upload_video(service, video_path, meta,
                       privacy=privacy, category_id=args.category_id,
                       dry_run=args.dry_run, lang=args.lang)

    if args.dry_run:
        return 0

    thumb_ok = False
    if not args.no_thumbnail:
        thumb_ok = upload_thumbnail(service, vid, thumb_path)

    url = f"https://www.youtube.com/watch?v={vid}"
    studio_url = f"https://studio.youtube.com/video/{vid}/edit"
    result = {
        "video_id": vid,
        "url": url,
        "studio_url": studio_url,
        "privacy": privacy,
        "title": meta["title"],
        "thumbnail_uploaded": thumb_ok,
        "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    print()
    print(f"=== UPLOAD COMPLETE ===")
    print(f"  videoId:    {vid}")
    print(f"  URL:        {url}")
    print(f"  Studio:     {studio_url}")
    print(f"  privacy:    {privacy}")
    print(f"  thumbnail:  {'set' if thumb_ok else 'manual'}")
    print(f"  result:     {result_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
