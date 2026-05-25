#!/usr/bin/env python3
"""Qwen3-TTS-12Hz-1.7B-Base client for autotube.

Drop-in replacement for `tts_fish_client.py` segments + concat modes.
Loads the model locally (no HTTP server), iterates the segments.json, and
voice-clones each segment from `voices/<male|female>/ref.wav + ref.txt`.

Modes:

1. Per-segment synthesis (dual voice):
    python tts_qwen_client.py \\
        --segments output/<run>/segments.json \\
        --male-voice voices/male_voice/ref.wav \\
        --male-voice-text "$(cat voices/male_voice/ref.txt)" \\
        --female-voice voices/female_voice/ref.wav \\
        --female-voice-text "$(cat voices/female_voice/ref.txt)" \\
        --segments-out-dir output/<run>/segments/ \\
        [--only N M ...] [--overwrite]

2. Concat per-segment MP3s + BGM mix (identical to fish):
    python tts_qwen_client.py \\
        --concat output/<run>/segments/ \\
        --bgm "bgm/거대한 문턱.mp3" \\
        --out output/<run>/audio.mp3

Synthesis runs on CUDA. Requires Qwen3-TTS-12Hz-1.7B-Base under
models/qwen3-tts-12hz-base/ (its `speech_tokenizer/` subfolder is bundled).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_MODEL_DIR = Path("/home/hjhj/autotube/models/qwen3-tts-12hz-base")


def _ffmpeg_binary(container_name: str | None) -> list[str]:
    host_ffmpeg = shutil.which("ffmpeg")
    if host_ffmpeg:
        return [host_ffmpeg]
    if container_name:
        return ["docker", "exec", container_name, "ffmpeg"]
    raise RuntimeError(
        "No host ffmpeg and no container name given. Install ffmpeg or pass --docker-container."
    )


def wav_to_mp3(
    wav_path: Path,
    mp3_path: Path,
    container_name: str | None,
    volume: float = 1.0,
    tail_pad_sec: float = 0.25,
) -> None:
    """Encode WAV → MP3 with per-segment treatment.

    - `volume`: linear gain (used to even out male-vs-female loudness from
      voice-clone; Qwen tends to make male clones quieter than the female ref).
    - `tail_pad_sec`: silence appended to the end so the final phoneme isn't
      clipped if Qwen's EOS fires a hair early. Also gives the next segment
      breathing room.
    - Tiny 30ms fade-in avoids digital clicks at segment start.
    - 80ms fade-out across the pad blends the silence cleanly.
    """
    ffmpeg = _ffmpeg_binary(container_name)
    af_chain = [
        f"volume={volume}",
        "afade=t=in:st=0:d=0.03",
    ]
    if tail_pad_sec > 0:
        af_chain.append(f"apad=pad_dur={tail_pad_sec}")
    af = ",".join(af_chain)
    cmd = [
        *ffmpeg, "-y", "-i", str(wav_path.resolve()),
        "-af", af,
        "-codec:a", "libmp3lame", "-q:a", "2",
        str(mp3_path.resolve()),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def concat_mp3s(
    mp3_paths: list[Path],
    out_path: Path,
    container_name: str | None,
    bgm_path: Path | None = None,
    voice_gain: float = 1.5,
    bgm_gain: float = 0.1,
    segment_gap_sec: float = 1.0,
    voice_tempo: float = 1.0,
) -> None:
    """Concat per-segment MP3s into one MP3 + optional BGM mix.

    Mirrors the fish-speech client behavior: silence gaps between segments,
    voice tempo bump, voice gain, BGM stream-looped under the voice.
    """
    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = _ffmpeg_binary(container_name)

    silence_path: Path | None = None
    if segment_gap_sec > 0 and len(mp3_paths) > 1:
        silence_path = out_path.parent / f".silence_{int(segment_gap_sec*1000)}ms.mp3"
        sil_cmd = [
            *ffmpeg, "-y",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=44100",
            "-t", str(segment_gap_sec),
            "-codec:a", "libmp3lame", "-q:a", "2",
            str(silence_path),
        ]
        subprocess.run(sil_cmd, check=True, capture_output=True)

    manifest = out_path.parent / f".concat_manifest_{out_path.stem}.txt"
    with open(manifest, "w") as f:
        for i, p in enumerate(mp3_paths):
            abs_str = str(p.resolve()).replace("'", r"'\''")
            f.write(f"file '{abs_str}'\n")
            if silence_path is not None and i < len(mp3_paths) - 1:
                sil_abs = str(silence_path.resolve()).replace("'", r"'\''")
                f.write(f"file '{sil_abs}'\n")

    voice_chain = []
    if voice_tempo != 1.0:
        voice_chain.append(f"atempo={voice_tempo}")
    voice_chain.append(f"volume={voice_gain}")
    voice_filter = ",".join(voice_chain)

    try:
        if bgm_path is None:
            cmd = [
                *ffmpeg, "-y",
                "-f", "concat", "-safe", "0", "-i", str(manifest),
                "-filter:a", voice_filter,
                "-codec:a", "libmp3lame", "-q:a", "2",
                str(out_path),
            ]
        else:
            filt = (
                f"[0:a]{voice_filter}[voice];"
                f"[1:a]volume={bgm_gain}[bgm];"
                f"[voice][bgm]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[out]"
            )
            cmd = [
                *ffmpeg, "-y",
                "-f", "concat", "-safe", "0", "-i", str(manifest),
                "-stream_loop", "-1", "-i", str(bgm_path.resolve()),
                "-filter_complex", filt,
                "-map", "[out]",
                "-codec:a", "libmp3lame", "-q:a", "2",
                str(out_path),
            ]
        subprocess.run(cmd, check=True, capture_output=True)
    finally:
        manifest.unlink(missing_ok=True)
        if silence_path is not None:
            silence_path.unlink(missing_ok=True)


def run_segments_mode(args: argparse.Namespace) -> int:
    if not args.segments.exists():
        print(f"ERROR: segments.json not found: {args.segments}", file=sys.stderr)
        return 2
    for tag, p in [
        ("male voice wav", args.male_voice),
        ("female voice wav", args.female_voice),
    ]:
        if not p or not p.exists():
            print(f"ERROR: {tag} missing: {p}", file=sys.stderr)
            return 2
    if not args.male_voice_text or not args.female_voice_text:
        print("ERROR: --male-voice-text and --female-voice-text are required.", file=sys.stderr)
        return 2

    data = json.loads(args.segments.read_text(encoding="utf-8"))
    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        print("ERROR: segments.json has no 'segments' array.", file=sys.stderr)
        return 2

    out_dir: Path = args.segments_out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    only = set(args.only) if args.only else None

    # Figure out what we actually need to synthesize before loading the model.
    todo = []
    for seg in segments:
        n = seg["n"]
        if only is not None and str(n) not in only:
            continue
        voice = seg["voice"]
        role = seg["role"]
        filename = f"{int(n):02d}_{role}_{voice}.mp3"
        out_mp3 = out_dir / filename
        if out_mp3.exists() and not args.overwrite:
            print(f"  [{n:>2}] SKIP (exists): {filename}")
            continue
        todo.append((seg, out_mp3))

    if not todo:
        print("Nothing to synthesize.")
        return 0

    print(f"Loading Qwen3-TTS from {args.model_dir}...")
    t0 = time.time()
    import torch
    import soundfile as sf
    from qwen_tts import Qwen3TTSModel

    model = Qwen3TTSModel.from_pretrained(
        str(args.model_dir),
        device_map=args.device,
        dtype=torch.bfloat16,
    )
    print(f"Loaded in {time.time()-t0:.1f}s")

    voice_ref = {
        "male": (str(args.male_voice.resolve()), args.male_voice_text),
        "female": (str(args.female_voice.resolve()), args.female_voice_text),
    }

    print(f"Synthesizing {len(todo)}/{len(segments)} segments to {out_dir}/")
    for seg, out_mp3 in todo:
        n = seg["n"]
        voice = seg["voice"]
        role = seg["role"]
        text = seg["text"].strip()
        if voice not in voice_ref:
            print(f"ERROR: segment {n}: unknown voice '{voice}'", file=sys.stderr)
            return 2

        ref_path, ref_text = voice_ref[voice]
        preview = text[:60].replace("\n", " ")
        print(f"  [{n:>2}] {voice:6s} {role:11s} {len(text):>3} chars: {preview}…")

        # Pad the input text so Qwen's LM doesn't EOS too aggressively on the
        # final syllable — a trailing period + space gives the model a tail
        # token to emit before stopping, so the last phoneme survives.
        synth_text = text
        if synth_text and synth_text[-1] not in ".!?。!?…":
            synth_text = synth_text + "."
        synth_text = synth_text + "  "

        t1 = time.time()
        wavs, sr = model.generate_voice_clone(
            text=synth_text,
            language="Korean",
            ref_audio=ref_path,
            ref_text=ref_text,
        )
        wav = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
        wav_path = out_mp3.with_suffix(".wav")
        sf.write(str(wav_path), wav, sr)
        volume = args.male_gain if voice == "male" else args.female_gain
        wav_to_mp3(
            wav_path, out_mp3, args.docker_container,
            volume=volume, tail_pad_sec=args.tail_pad,
        )
        wav_path.unlink(missing_ok=True)
        dur = len(wav) / sr
        dt = time.time() - t1
        print(f"    → {out_mp3.name} ({dur:.1f}s audio, synth {dt:.1f}s, {dur/dt:.2f}x rt)")

    print(f"Done. Review individual MP3s in {out_dir}/, then run --concat to merge.")
    return 0


def run_concat_mode(args: argparse.Namespace) -> int:
    segs_dir: Path = args.concat
    if not segs_dir.is_dir():
        print(f"ERROR: not a directory: {segs_dir}", file=sys.stderr)
        return 2
    mp3s = sorted(segs_dir.glob("*.mp3"))
    if not mp3s:
        print(f"ERROR: no .mp3 files in {segs_dir}", file=sys.stderr)
        return 2
    print(f"Concatenating {len(mp3s)} segment MP3s:")
    for p in mp3s:
        print(f"  {p.name}")

    bgm_path = args.bgm
    staged_bgm: Path | None = None
    if bgm_path is not None:
        bgm_abs = bgm_path.resolve()
        out_abs = args.out.resolve()
        mounted_roots = [
            Path("/home/hjhj/autotube/output").resolve(),
            Path("/home/hjhj/autotube/voices").resolve(),
        ]
        in_mounted = any(
            str(bgm_abs).startswith(str(r) + "/") for r in mounted_roots
        )
        # Only stage into output/ if we'll be running inside the Docker container.
        # With host ffmpeg, we can read from anywhere.
        if not in_mounted and not shutil.which("ffmpeg"):
            staged_bgm = out_abs.parent / f"._bgm_staged{bgm_abs.suffix}"
            shutil.copyfile(bgm_abs, staged_bgm)
            bgm_path = staged_bgm
        print(f"Mixing with BGM: {bgm_path} (voice x{args.voice_gain}, bgm x{args.bgm_gain})")

    try:
        concat_mp3s(
            mp3s, args.out, args.docker_container,
            bgm_path=bgm_path,
            voice_gain=args.voice_gain,
            bgm_gain=args.bgm_gain,
            segment_gap_sec=args.segment_gap,
            voice_tempo=args.voice_tempo,
        )
    finally:
        if staged_bgm is not None:
            staged_bgm.unlink(missing_ok=True)
    print(f"MP3 written: {args.out}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--segments", type=Path, help="segments.json file (mode: per-segment synth)")
    p.add_argument("--concat", type=Path, help="directory of per-segment MP3s to concat")

    # Synth-mode voice args.
    p.add_argument("--male-voice", type=Path)
    p.add_argument("--male-voice-text", type=str)
    p.add_argument("--female-voice", type=Path)
    p.add_argument("--female-voice-text", type=str)
    p.add_argument("--segments-out-dir", type=Path)
    p.add_argument("--only", nargs="+",
                   help="only synthesize these segment numbers, e.g. --only 3 5")
    p.add_argument("--overwrite", action="store_true",
                   help="overwrite existing per-segment mp3s")

    # Shared output.
    p.add_argument("--out", type=Path, help="output mp3 path (concat mode)")

    # Model + device.
    p.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR,
                   help=f"local Qwen3-TTS model dir (default: {DEFAULT_MODEL_DIR})")
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--docker-container", default="autotube-fish-speech",
                   help="fallback ffmpeg container if host ffmpeg missing")

    # Per-segment synthesis tuning. Qwen voice-clone makes male output
    # consistently quieter than female; bump male gain to level the mix.
    p.add_argument("--male-gain", type=float, default=1.6,
                   help="(synth) volume multiplier applied to male segments. Default 1.6")
    p.add_argument("--female-gain", type=float, default=1.0,
                   help="(synth) volume multiplier applied to female segments. Default 1.0")
    p.add_argument("--tail-pad", type=float, default=0.25,
                   help="(synth) seconds of silence appended to each segment to prevent EOS clipping. Default 0.25s")

    # Concat mode BGM mixing args. Qwen tempo is natural enough that we run
    # 1.0x (no atempo bump), and the gap between segments is ~1s for breathing.
    p.add_argument("--bgm", type=Path, default=None)
    p.add_argument("--voice-gain", type=float, default=1.5)
    p.add_argument("--bgm-gain", type=float, default=0.1)
    p.add_argument("--segment-gap", type=float, default=1.0)
    p.add_argument("--voice-tempo", type=float, default=1.0)

    args = p.parse_args()

    mode_flags = [bool(args.segments), bool(args.concat)]
    if sum(mode_flags) != 1:
        print("ERROR: pick exactly one of --segments, --concat", file=sys.stderr)
        return 2

    if args.segments:
        if not args.segments_out_dir:
            print("ERROR: --segments-out-dir required for --segments mode", file=sys.stderr)
            return 2
        return run_segments_mode(args)

    if args.concat:
        if not args.out:
            print("ERROR: --out required for --concat mode", file=sys.stderr)
            return 2
        return run_concat_mode(args)

    return 2


if __name__ == "__main__":
    sys.exit(main())
