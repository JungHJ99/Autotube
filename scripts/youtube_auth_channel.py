#!/usr/bin/env python3
"""One-off: authorize a NEW YouTube channel and save its token.

Opens a browser OAuth flow, writes the token to the given path, then prints
which channel the token actually maps to (so we can confirm it's the intended
channel BEFORE any upload). Does NOT touch any existing token unless --token
points at it.

Usage:
  python3 scripts/youtube_auth_channel.py --token ~/.config/autotube/token.json
"""
import argparse
import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube",
          "https://www.googleapis.com/auth/youtube.readonly"]
CONFIG = Path.home() / ".config" / "autotube"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-secret", type=Path, default=CONFIG / "client_secret.json")
    ap.add_argument("--token", type=Path, default=CONFIG / "token.json")
    args = ap.parse_args()

    if not args.client_secret.exists():
        print(f"ERROR: client_secret.json not found: {args.client_secret}", file=sys.stderr)
        return 2

    print("브라우저가 열립니다. **새 멕시코 채널을 소유한 Google 계정**으로 로그인하고,")
    print("(브랜드 채널 선택 화면이 나오면 멕시코 채널을 고른 뒤) 권한을 승인하세요.")
    flow = InstalledAppFlow.from_client_secrets_file(str(args.client_secret), SCOPES)
    creds = flow.run_local_server(
        port=0,
        authorization_prompt_message="브라우저에서 Google 로그인 후 승인하세요.",
        success_message="인증 완료. 이 탭은 닫아도 됩니다.",
        open_browser=True,
    )
    args.token.parent.mkdir(parents=True, exist_ok=True)
    args.token.write_text(creds.to_json(), encoding="utf-8")
    args.token.chmod(0o600)
    print(f"[oauth] token saved → {args.token}")

    yt = build("youtube", "v3", credentials=creds)
    resp = yt.channels().list(part="snippet,statistics", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        print("WARNING: token maps to NO channel.")
        return 1
    for it in items:
        s = it["snippet"]; st = it.get("statistics", {})
        print("\n==> AUTHORIZED CHANNEL:")
        print(f"    title : {s['title']}")
        print(f"    id    : {it['id']}")
        print(f"    subs  : {st.get('subscriberCount')}  videos: {st.get('videoCount')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
