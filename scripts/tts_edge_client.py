#!/usr/bin/env python3
"""tts_edge_client.py — Microsoft Edge neural-TTS client for the 멕시코뽕 (MX) pipeline.

The MX pipeline dubs in Spanish for a Mexican audience. Qwen3-TTS cross-lingual
(Korean ref voice → Spanish) sounded off, so the Spanish channel uses Edge's
native **Mexican** neural voices instead:
  - male   → es-MX-JorgeNeural  (Friendly, Positive)
  - female → es-MX-DaliaNeural  (Friendly, Positive)

Output is byte-compatible with `tts_qwen_client.py --concat`: per-segment MP3s
named `NN_<role>_<voice>.mp3`, with the same tail-pad / fade-in treatment, so the
existing concat + build_video stages work unchanged.

Per-segment synthesis (dual voice, Spanish):
    python tts_edge_client.py \\
        --segments output/<run>/segments.json \\
        --segments-out-dir output/<run>/segments/ \\
        [--only N M ...] [--overwrite] [--rate +0%]

Concat is identical to Qwen — reuse: tts_qwen_client.py --concat <dir> --bgm ... --out ...
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# voice → Edge neural voice id. Mexican Spanish, warm register.
VOICE_MAP = {
    "male": "es-MX-JorgeNeural",
    "female": "es-MX-DaliaNeural",
}


def _ffmpeg() -> str:
    f = shutil.which("ffmpeg")
    if not f:
        raise RuntimeError("host ffmpeg not found")
    return f


def edge_synthesize(text: str, voice: str, rate: str, out_mp3: Path) -> None:
    """Call edge-tts CLI to synthesize `text` to a raw mp3."""
    cmd = [
        sys.executable, "-m", "edge_tts",
        "--voice", voice,
        "--text", text,
        "--rate", rate,
        "--write-media", str(out_mp3),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def post_process(raw_mp3: Path, out_mp3: Path, volume: float, tail_pad_sec: float) -> None:
    """Match the Qwen client's per-segment treatment: gain, 30ms fade-in,
    tail-pad silence so concat gaps and EOS clipping behave identically."""
    af = [f"volume={volume}", "afade=t=in:st=0:d=0.03"]
    if tail_pad_sec > 0:
        af.append(f"apad=pad_dur={tail_pad_sec}")
    cmd = [
        _ffmpeg(), "-y", "-i", str(raw_mp3.resolve()),
        "-af", ",".join(af),
        "-codec:a", "libmp3lame", "-q:a", "2",
        str(out_mp3.resolve()),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--segments", type=Path, required=True)
    p.add_argument("--segments-out-dir", type=Path, required=True)
    p.add_argument("--only", nargs="+", help="only these segment numbers")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--rate", default="+0%",
                   help="edge-tts speaking rate, e.g. -8%% slower, +10%% faster. Default +0%%")
    p.add_argument("--male-gain", type=float, default=1.0)
    p.add_argument("--female-gain", type=float, default=1.0)
    p.add_argument("--tail-pad", type=float, default=0.25)
    args = p.parse_args()

    if not args.segments.exists():
        print(f"ERROR: segments.json not found: {args.segments}", file=sys.stderr)
        return 2
    data = json.loads(args.segments.read_text(encoding="utf-8"))
    segments = data.get("segments")
    if not segments:
        print("ERROR: no 'segments' array", file=sys.stderr)
        return 2

    out_dir: Path = args.segments_out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    only = set(args.only) if args.only else None

    todo = []
    for seg in segments:
        n = seg["n"]
        if only is not None and str(n) not in only:
            continue
        voice = seg["voice"]
        role = seg["role"]
        out_mp3 = out_dir / f"{int(n):02d}_{role}_{voice}.mp3"
        if out_mp3.exists() and not args.overwrite:
            print(f"  [{n:>2}] SKIP (exists)")
            continue
        todo.append((seg, out_mp3))

    if not todo:
        print("Nothing to synthesize.")
        return 0

    print(f"Edge-TTS (Mexican Spanish) — {len(todo)}/{len(segments)} segments → {out_dir}/")
    with tempfile.TemporaryDirectory() as td:
        for seg, out_mp3 in todo:
            n, voice, role = seg["n"], seg["voice"], seg["role"]
            text = seg["text"].strip()
            edge_voice = VOICE_MAP.get(voice)
            if not edge_voice:
                print(f"ERROR: seg {n}: unknown voice '{voice}'", file=sys.stderr)
                return 2
            preview = text[:60].replace("\n", " ")
            print(f"  [{n:>2}] {voice:6s} {role:18s} {edge_voice} {len(text):>3}c: {preview}…")
            raw = Path(td) / f"raw_{int(n):02d}.mp3"
            edge_synthesize(text, edge_voice, args.rate, raw)
            volume = args.male_gain if voice == "male" else args.female_gain
            post_process(raw, out_mp3, volume=volume, tail_pad_sec=args.tail_pad)
            dur = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(out_mp3)],
                capture_output=True, text=True).stdout.strip()
            print(f"    → {out_mp3.name} ({dur}s)")

    print(f"Done. Review MP3s in {out_dir}/, then --concat (tts_qwen_client.py) to merge.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
