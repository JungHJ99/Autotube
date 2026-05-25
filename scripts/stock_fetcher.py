#!/usr/bin/env python3
"""Fetch stock/B-roll video clips for autotube segments.

Sources:
  - Pexels Videos API     (CC0, free; needs PEXELS_API_KEY)
  - DVIDS Hub             (US military, public domain; needs DVIDS_API_KEY)

Usage:
    # one-off query
    python3 scripts/stock_fetcher.py \\
        --query "tank firing" \\
        --source pexels \\
        --out output/<run>/stock_clips/ \\
        --max 3

    # batch: read `stock_query` field per segment in segments.json
    python3 scripts/stock_fetcher.py \\
        --segments output/<run>/segments.json \\
        --source both \\
        --out output/<run>/stock_clips/

A `manifest.json` is written under --out listing every clip's source URL,
author, license info, and matching segment number (for later attribution).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path


PEXELS_API = "https://api.pexels.com/videos/search"
DVIDS_API = "https://api.dvidshub.net/search"


def http_get_json(url: str, headers: dict, timeout: int = 20) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download(url: str, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "autotube/1.0"})
    n = 0
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
        while True:
            chunk = resp.read(128 * 1024)
            if not chunk:
                break
            f.write(chunk)
            n += len(chunk)
    return n


def slugify(s: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-")[:40]


# ---------------- Pexels ----------------

def pexels_search(query: str, api_key: str, per_page: int,
                  min_dur: float, quality: str) -> list[dict]:
    qs = urllib.parse.urlencode({
        "query": query,
        "per_page": per_page,
        "orientation": "landscape",
    })
    data = http_get_json(
        f"{PEXELS_API}?{qs}",
        {"Authorization": api_key, "User-Agent": "autotube/1.0"},
    )
    wanted_order = {
        "sd": ["sd"],
        "hd": ["hd", "sd"],
        "uhd": ["uhd", "hd", "sd"],
    }.get(quality, ["hd", "sd"])

    out = []
    for v in data.get("videos", []):
        if v.get("duration", 0) < min_dur:
            continue
        picked = None
        for q in wanted_order:
            for f in v.get("video_files", []):
                if f.get("quality") == q and f.get("file_type") == "video/mp4":
                    picked = f
                    break
            if picked:
                break
        if picked is None:
            continue
        out.append({
            "source": "pexels",
            "source_id": v["id"],
            "duration_sec": v["duration"],
            "width": picked["width"],
            "height": picked["height"],
            "download_url": picked["link"],
            "page_url": v["url"],
            "author": v.get("user", {}).get("name"),
            "author_url": v.get("user", {}).get("url"),
            "license": "Pexels License (free, no attribution required but appreciated)",
        })
    return out


# ---------------- DVIDS Hub ----------------

def dvids_search(query: str, api_key: str, per_page: int,
                 min_dur: float) -> list[dict]:
    qs = urllib.parse.urlencode({
        "q": query,
        "type": "video",
        "api_key": api_key,
        "max_results": per_page,
    })
    data = http_get_json(f"{DVIDS_API}?{qs}", {"User-Agent": "autotube/1.0"})

    out = []
    for r in data.get("results", []):
        # DVIDS returns various download options; prefer mp4 source video.
        download_url = r.get("source") or r.get("video_hd") or r.get("video")
        if not download_url:
            continue
        dur = r.get("duration") or 0
        # DVIDS duration is often "HH:MM:SS" string — try to coerce.
        if isinstance(dur, str) and ":" in dur:
            parts = [float(x) for x in dur.split(":")]
            dur = sum(p * 60 ** (len(parts) - i - 1) for i, p in enumerate(parts))
        if dur and dur < min_dur:
            continue
        out.append({
            "source": "dvids",
            "source_id": r.get("id"),
            "duration_sec": dur,
            "width": r.get("width"),
            "height": r.get("height"),
            "download_url": download_url,
            "page_url": r.get("url"),
            "author": r.get("credit") or "U.S. Department of Defense",
            "author_url": None,
            "license": "Public Domain (US Federal Government work)",
        })
    return out


# ---------------- Orchestration ----------------

def fetch_for_query(query: str, source: str, out_dir: Path,
                    max_clips: int, min_dur: float, quality: str,
                    keys: dict, prefix: str = "") -> list[dict]:
    print(f"\n=== query: {query!r} (source={source}) ===", flush=True)
    candidates: list[dict] = []

    sources = ["pexels", "dvids"] if source == "both" else [source]
    for s in sources:
        try:
            if s == "pexels":
                if not keys.get("pexels"):
                    print("  [pexels] no API key — skip", flush=True)
                    continue
                candidates += pexels_search(query, keys["pexels"], per_page=10,
                                            min_dur=min_dur, quality=quality)
            elif s == "dvids":
                if not keys.get("dvids"):
                    print("  [dvids] no API key — skip", flush=True)
                    continue
                candidates += dvids_search(query, keys["dvids"], per_page=10,
                                           min_dur=min_dur)
        except Exception as e:
            print(f"  [{s}] search failed: {e}", file=sys.stderr)

    picked = candidates[:max_clips]
    saved = []
    for i, c in enumerate(picked, 1):
        fname = f"{prefix}{slugify(query)}_{c['source']}_{i}_{c['source_id']}.mp4"
        dest = out_dir / fname
        if dest.exists():
            print(f"  skip (exists): {fname}", flush=True)
        else:
            print(f"  download [{c['source']}]: {fname} "
                  f"({c.get('duration_sec','?')}s {c.get('width','?')}x{c.get('height','?')})",
                  flush=True)
            try:
                size = download(c["download_url"], dest)
                print(f"    {size/1024/1024:.1f} MB", flush=True)
            except Exception as e:
                print(f"    ERR: {e}", file=sys.stderr)
                continue
        saved.append({**c, "path": str(dest), "query": query})
    return saved


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--query", type=str, default=None,
                   help="single search query")
    p.add_argument("--segments", type=Path, default=None,
                   help="segments.json with `stock_query` fields per segment")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--source", choices=["pexels", "dvids", "both"], default="both")
    p.add_argument("--max", type=int, default=3,
                   help="max clips per query (default 3)")
    p.add_argument("--min-duration", type=float, default=4.0,
                   help="filter out clips shorter than N sec (default 4)")
    p.add_argument("--quality", choices=["sd", "hd", "uhd"], default="hd",
                   help="Pexels quality preference (default hd)")
    p.add_argument("--pexels-key", type=str,
                   default=os.environ.get("PEXELS_API_KEY"))
    p.add_argument("--dvids-key", type=str,
                   default=os.environ.get("DVIDS_API_KEY"))
    p.add_argument("--manifest", type=Path, default=None,
                   help="manifest output (default: <out>/manifest.json)")
    args = p.parse_args()

    keys = {"pexels": args.pexels_key, "dvids": args.dvids_key}

    needed = {"pexels", "dvids"} if args.source == "both" else {args.source}
    missing = [k for k in needed if not keys.get(k)]
    if missing == list(needed):
        print(
            "ERR: no API keys provided. Set at least one of:\n"
            "  Pexels (free, https://www.pexels.com/api/ ): export PEXELS_API_KEY=...\n"
            "  DVIDS  (free, https://api.dvidshub.net/    ): export DVIDS_API_KEY=...",
            file=sys.stderr,
        )
        return 2
    if missing:
        print(f"WARN: {missing} key missing — those sources will be skipped.",
              file=sys.stderr)

    if not args.query and not args.segments:
        print("ERR: --query or --segments required.", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    manifest_path = args.manifest or (args.out / "manifest.json")

    all_saved: list[dict] = []
    if args.query:
        all_saved.extend(fetch_for_query(
            args.query, args.source, args.out,
            args.max, args.min_duration, args.quality, keys,
        ))
    else:
        segs_doc = json.loads(args.segments.read_text(encoding="utf-8"))
        for seg in segs_doc["segments"]:
            q = seg.get("stock_query")
            if not q:
                continue
            prefix = f"{int(seg['n']):02d}_"
            saved = fetch_for_query(
                q, args.source, args.out,
                args.max, args.min_duration, args.quality, keys,
                prefix=prefix,
            )
            for s in saved:
                s["segment_n"] = seg["n"]
            all_saved.extend(saved)

    manifest_path.write_text(
        json.dumps(all_saved, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nDone. {len(all_saved)} clips saved. Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
