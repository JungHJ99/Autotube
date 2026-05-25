#!/usr/bin/env python3
"""
Fish-Speech 1.5 API client for autotube.

Two modes:

1. Single-voice script mode (legacy):
    python tts_fish_client.py \
        --script output/<run>/script.txt \
        --voice voices/<name>/ref.wav \
        --voice-text "$(cat voices/<name>/ref.txt)" \
        --out output/<run>/audio.mp3

   Reads a Korean script file, splits into TTS-friendly chunks, synthesizes
   each chunk with one voice, concatenates the returned WAVs, converts to MP3.

2. Dual-voice segmented mode:
    python tts_fish_client.py \
        --segments output/<run>/segments.json \
        --male-voice voices/male_voice/ref.wav \
        --male-voice-text "$(cat voices/male_voice/ref.txt)" \
        --female-voice voices/female_voice/ref.wav \
        --female-voice-text "$(cat voices/female_voice/ref.txt)" \
        --segments-out-dir output/<run>/segments/

   Reads a segments.json (produced by kpop-script-writer). Each segment is
   tagged with voice (male/female) and synthesized into its own MP3 at
   <segments-out-dir>/NN_<role>_<voice>.mp3 . No concatenation in this step —
   that happens after human review via --concat below.

3. Concat mode (after segment review):
    python tts_fish_client.py \
        --concat output/<run>/segments/ \
        --bgm "bgm/거대한 문턱.mp3" \
        --out output/<run>/audio.mp3

   Concatenates the per-segment MP3s (sorted by filename, i.e. by segment
   number prefix) into one MP3 using ffmpeg's concat demuxer. If --bgm is
   provided, the BGM track is stream-looped to cover the voice and mixed
   under it. Default gains: voice x1.5, BGM x0.2 (see --voice-gain /
   --bgm-gain to override). BGM file must live somewhere ffmpeg can read —
   inside the Docker container that's `/home/hjhj/autotube/output/` or
   `/home/hjhj/autotube/voices/` (the only mounted paths). If your BGM lives
   in `bgm/`, copy or symlink it under `output/` first.

The fish-speech API expects an ormsgpack-encoded ServeTTSRequest body posted
to /v1/tts with `?format=msgpack`. References (ref.wav + ref.txt) are sent
inline as bytes so the server can do zero-shot voice cloning.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

try:
    import ormsgpack
except ImportError:
    print("ERROR: `ormsgpack` not installed. Run: pip install ormsgpack", file=sys.stderr)
    sys.exit(1)
try:
    import requests
except ImportError:
    print("ERROR: `requests` not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)


# Fish-speech v1.5 ServeTTSRequest caps chunk_length at 300 (server-side
# pydantic validator). We chunk on Korean sentence boundaries first so the
# voice doesn't slur across periods.
MAX_CHUNK_CHARS = 200
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]
    chunks: list[str] = []
    buf = ""
    for s in sentences:
        if len(s) > max_chars:
            parts = [p.strip() for p in re.split(r"(?<=[,;])\s+", s) if p.strip()]
            for p in parts:
                if not buf:
                    buf = p
                elif len(buf) + 1 + len(p) <= max_chars:
                    buf += " " + p
                else:
                    chunks.append(buf)
                    buf = p
        elif not buf:
            buf = s
        elif len(buf) + 1 + len(s) <= max_chars:
            buf += " " + s
        else:
            chunks.append(buf)
            buf = s
    if buf:
        chunks.append(buf)
    return chunks


def synthesize_chunk(
    api_url: str,
    text: str,
    ref_audio_bytes: bytes,
    ref_text: str,
    timeout: int = 600,
    temperature: float = 0.7,
    top_p: float = 0.7,
    repetition_penalty: float = 1.5,
    chunk_length: int = 200,
    max_new_tokens: int = 1024,
    seed: int | None = None,
    end_pad: str = "",
) -> bytes:
    # Append end-pad after chunking so the model has buffer tokens past the
    # last real syllable. Mitigates premature EOS clipping the final phoneme.
    text = text + end_pad
    body = {
        "text": text,
        "chunk_length": chunk_length,
        "format": "wav",
        "references": [{"audio": ref_audio_bytes, "text": ref_text}],
        "reference_id": None,
        "seed": seed,
        "use_memory_cache": "on",  # cache reference encoding across chunks
        "normalize": True,
        "streaming": False,
        "max_new_tokens": max_new_tokens,
        "top_p": top_p,
        "repetition_penalty": repetition_penalty,
        "temperature": temperature,
    }
    packed = ormsgpack.packb(body)
    r = requests.post(
        api_url,
        params={"format": "msgpack"},
        data=packed,
        headers={
            "content-type": "application/msgpack",
            "authorization": "Bearer dummy",
        },
        timeout=timeout,
    )
    if r.status_code != 200:
        try:
            err = r.json()
        except Exception:
            err = r.text[:500]
        raise RuntimeError(f"TTS request failed (HTTP {r.status_code}): {err}")
    return r.content


def concat_wavs(wav_blobs: list[bytes], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    first = wave.open(io.BytesIO(wav_blobs[0]), "rb")
    params = first.getparams()
    first.close()

    with wave.open(str(out_path), "wb") as w:
        w.setparams(params)
        for blob in wav_blobs:
            r = wave.open(io.BytesIO(blob), "rb")
            if r.getparams()[:3] != params[:3]:
                print(
                    f"WARNING: WAV params differ across chunks: "
                    f"first={params[:3]} this={r.getparams()[:3]}",
                    file=sys.stderr,
                )
            w.writeframes(r.readframes(r.getnframes()))
            r.close()


def _ffmpeg_binary(container_name: str | None) -> list[str]:
    host_ffmpeg = shutil.which("ffmpeg")
    if host_ffmpeg:
        return [host_ffmpeg]
    if container_name:
        return ["docker", "exec", container_name, "ffmpeg"]
    raise RuntimeError("No host ffmpeg and no container name given. Install ffmpeg or pass --docker-container.")


def wav_to_mp3(wav_path: Path, mp3_path: Path, container_name: str | None) -> None:
    wav_abs = str(wav_path.resolve())
    mp3_abs = str(mp3_path.resolve())
    ffmpeg = _ffmpeg_binary(container_name)
    # fish-speech zero-shot occasionally emits a transient glitch in the first
    # ~50-100ms of each chunk (reference-voice priming residue). Trim the first
    # 40ms, then prepend 80ms silence so segment cues line up cleanly, then
    # apply a 180ms fade-in so the start is energy-ramped instead of cold-cut.
    af = "atrim=start=0.04,asetpts=PTS-STARTPTS,adelay=80:all=1,afade=t=in:st=0:d=0.18"
    cmd = [*ffmpeg, "-y", "-i", wav_abs, "-af", af, "-codec:a", "libmp3lame", "-q:a", "2", mp3_abs]
    subprocess.run(cmd, check=True, capture_output=True)


def concat_mp3s(
    mp3_paths: list[Path],
    out_path: Path,
    container_name: str | None,
    bgm_path: Path | None = None,
    voice_gain: float = 1.0,
    bgm_gain: float = 1.0,
    segment_gap_sec: float = 0.0,
    voice_tempo: float = 1.0,
) -> None:
    """Concatenate per-segment MP3s into one MP3.

    If `bgm_path` is given, the concatenated voice track is mixed with the
    BGM track (looped to cover the voice length, then cropped to voice
    duration). `voice_gain` / `bgm_gain` are linear amplitude multipliers.

    `segment_gap_sec`: silence inserted between each pair of segments via a
    pre-generated silent MP3 spliced into the concat manifest.

    `voice_tempo`: ffmpeg `atempo` factor applied to the voice track (1.0 =
    unchanged, 1.1 = 10% faster). Pitch is preserved.

    The concat manifest must live somewhere the ffmpeg process can read.
    When ffmpeg runs inside a Docker container, /tmp is not mounted, so we
    place the manifest next to the output MP3 (which lives under output/,
    which IS mounted).
    """
    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = _ffmpeg_binary(container_name)

    # If a gap is requested, pre-render a silence MP3 next to the output and
    # interleave it between segments. The silence file gets cleaned up after.
    silence_path: Path | None = None
    if segment_gap_sec > 0 and len(mp3_paths) > 1:
        silence_path = out_path.parent / f".silence_{int(segment_gap_sec*1000)}ms.mp3"
        sil_cmd = [
            *ffmpeg, "-y",
            "-f", "lavfi", "-i", f"anullsrc=channel_layout=mono:sample_rate=44100",
            "-t", str(segment_gap_sec),
            "-codec:a", "libmp3lame", "-q:a", "2",
            str(silence_path),
        ]
        subprocess.run(sil_cmd, check=True, capture_output=True)

    # Manifest sibling of out_path so it's reachable from inside the container.
    manifest = out_path.parent / f".concat_manifest_{out_path.stem}.txt"
    with open(manifest, "w") as f:
        for i, p in enumerate(mp3_paths):
            abs_str = str(p.resolve()).replace("'", r"'\''")
            f.write(f"file '{abs_str}'\n")
            if silence_path is not None and i < len(mp3_paths) - 1:
                sil_abs = str(silence_path.resolve()).replace("'", r"'\''")
                f.write(f"file '{sil_abs}'\n")

    # Build voice filter chain (atempo + volume).
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
            # Voice = concatenated segments (+atempo, +gain); BGM = stream-looped & gained;
            # amix with duration=first keeps the mix as long as the (tempo-adjusted) voice.
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


def synthesize_text_to_mp3(
    api_url: str,
    text: str,
    ref_audio_bytes: bytes,
    ref_text: str,
    out_mp3: Path,
    max_chunk: int,
    temperature: float,
    top_p: float,
    repetition_penalty: float,
    seed: int | None,
    container_name: str | None,
    end_pad: str = "",
    max_new_tokens: int = 1024,
) -> None:
    """Chunk text → synth each chunk → concat WAV → MP3. Used by both modes."""
    chunks = chunk_text(text, max_chars=max_chunk)
    wav_blobs: list[bytes] = []
    for i, chunk in enumerate(chunks, 1):
        preview = chunk[:50].replace("\n", " ")
        print(f"    chunk [{i}/{len(chunks)}] {len(chunk):>3} chars: {preview}…")
        blob = synthesize_chunk(
            api_url, chunk, ref_audio_bytes, ref_text,
            temperature=temperature,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
            seed=seed,
            end_pad=end_pad,
            max_new_tokens=max_new_tokens,
        )
        wav_blobs.append(blob)
    wav_path = out_mp3.with_suffix(".wav")
    concat_wavs(wav_blobs, wav_path)
    wav_to_mp3(wav_path, out_mp3, container_name)
    wav_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Mode handlers
# ---------------------------------------------------------------------------

def run_script_mode(args: argparse.Namespace) -> int:
    if not args.script.exists():
        print(f"ERROR: script not found: {args.script}", file=sys.stderr)
        return 2
    if not args.voice.exists():
        print(f"ERROR: voice wav not found: {args.voice}", file=sys.stderr)
        return 2

    script_text = args.script.read_text(encoding="utf-8").strip()
    if not script_text:
        print("ERROR: script is empty.", file=sys.stderr)
        return 2

    ref_audio_bytes = args.voice.read_bytes()
    chunks = chunk_text(script_text, max_chars=args.max_chunk)
    print(f"Script: {len(script_text)} chars → {len(chunks)} chunks")

    wav_blobs: list[bytes] = []
    for i, chunk in enumerate(chunks, 1):
        preview = chunk[:50].replace("\n", " ")
        print(f"  [{i}/{len(chunks)}] {len(chunk):>3} chars: {preview}…")
        blob = synthesize_chunk(
            args.api, chunk, ref_audio_bytes, args.voice_text,
            temperature=args.temperature,
            top_p=args.top_p,
            repetition_penalty=args.repetition_penalty,
            seed=args.seed,
            end_pad=args.end_pad,
            max_new_tokens=args.max_new_tokens,
        )
        wav_blobs.append(blob)

    wav_path = args.out.with_suffix(".wav")
    concat_wavs(wav_blobs, wav_path)
    print(f"WAV written: {wav_path}")

    wav_to_mp3(wav_path, args.out, args.docker_container)
    print(f"MP3 written: {args.out}")
    return 0


def run_segments_mode(args: argparse.Namespace) -> int:
    if not args.segments.exists():
        print(f"ERROR: segments.json not found: {args.segments}", file=sys.stderr)
        return 2
    if not args.male_voice or not args.male_voice.exists():
        print(f"ERROR: male voice wav missing: {args.male_voice}", file=sys.stderr)
        return 2
    if not args.female_voice or not args.female_voice.exists():
        print(f"ERROR: female voice wav missing: {args.female_voice}", file=sys.stderr)
        return 2
    if not args.male_voice_text:
        print("ERROR: --male-voice-text is required.", file=sys.stderr)
        return 2
    if not args.female_voice_text:
        print("ERROR: --female-voice-text is required.", file=sys.stderr)
        return 2

    data = json.loads(args.segments.read_text(encoding="utf-8"))
    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        print("ERROR: segments.json has no 'segments' array.", file=sys.stderr)
        return 2

    out_dir: Path = args.segments_out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    voice_bytes = {
        "male": args.male_voice.read_bytes(),
        "female": args.female_voice.read_bytes(),
    }
    voice_text = {
        "male": args.male_voice_text,
        "female": args.female_voice_text,
    }

    only = set(args.only) if args.only else None

    print(f"Segments: {len(segments)} total → writing to {out_dir}/")
    for seg in segments:
        n = seg["n"]
        voice = seg["voice"]
        role = seg["role"]
        text = seg["text"].strip()
        if voice not in voice_bytes:
            print(f"ERROR: segment {n}: unknown voice '{voice}'", file=sys.stderr)
            return 2
        if only is not None and str(n) not in only:
            continue
        filename = f"{int(n):02d}_{role}_{voice}.mp3"
        out_mp3 = out_dir / filename
        if out_mp3.exists() and not args.overwrite:
            print(f"  [{n:>2}] SKIP (exists): {filename}")
            continue
        preview = text[:60].replace("\n", " ")
        print(f"  [{n:>2}] {voice:6s} {role:11s} {len(text):>3} chars: {preview}…")
        synthesize_text_to_mp3(
            args.api, text, voice_bytes[voice], voice_text[voice],
            out_mp3=out_mp3,
            max_chunk=args.max_chunk,
            temperature=args.temperature,
            top_p=args.top_p,
            repetition_penalty=args.repetition_penalty,
            seed=args.seed,
            container_name=args.docker_container,
            end_pad=args.end_pad,
            max_new_tokens=args.max_new_tokens,
        )
        print(f"    → {out_mp3}")
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
        # The container only mounts /home/hjhj/autotube/{voices,output}.
        # If the BGM lives outside those, copy it into output/ so the
        # in-container ffmpeg can read it. Cleaned up after.
        bgm_abs = bgm_path.resolve()
        out_abs = args.out.resolve()
        mounted_roots = [
            Path("/home/hjhj/autotube/output").resolve(),
            Path("/home/hjhj/autotube/voices").resolve(),
        ]
        in_mounted = any(
            str(bgm_abs).startswith(str(r) + "/") for r in mounted_roots
        )
        if not in_mounted:
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
    # Mode-selecting args (mutually exclusive logical groups, validated below).
    p.add_argument("--script", type=Path, help="single-voice script file (mode 1)")
    p.add_argument("--segments", type=Path, help="segments.json file (mode 2)")
    p.add_argument("--concat", type=Path, help="directory of per-segment MP3s to concat (mode 3)")

    # Mode 1 (script) voice args.
    p.add_argument("--voice", type=Path, help="(mode 1) ref.wav path")
    p.add_argument("--voice-text", type=str, help="(mode 1) exact transcript of ref.wav")

    # Mode 2 (segments) voice args.
    p.add_argument("--male-voice", type=Path, help="(mode 2) male ref.wav path")
    p.add_argument("--male-voice-text", type=str, help="(mode 2) exact transcript of male ref.wav")
    p.add_argument("--female-voice", type=Path, help="(mode 2) female ref.wav path")
    p.add_argument("--female-voice-text", type=str, help="(mode 2) exact transcript of female ref.wav")
    p.add_argument("--segments-out-dir", type=Path, help="(mode 2) output dir for per-segment mp3s")
    p.add_argument("--only", nargs="+", help="(mode 2) only synthesize these segment numbers, e.g. --only 3 5")
    p.add_argument("--overwrite", action="store_true", help="(mode 2) overwrite existing per-segment mp3s")

    # Shared output.
    p.add_argument("--out", type=Path, help="(mode 1, 3) output mp3 path")

    # Shared API & TTS params.
    p.add_argument("--api", default="http://127.0.0.1:8080/v1/tts")
    p.add_argument("--max-chunk", type=int, default=MAX_CHUNK_CHARS)
    p.add_argument("--docker-container", default="autotube-fish-speech")
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--top-p", type=float, default=0.7)
    p.add_argument("--repetition-penalty", type=float, default=1.5)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--end-pad", type=str, default="",
                   help="appended to each text chunk before TTS; e.g. ' .' to avoid premature EOS clipping the final phoneme")
    p.add_argument("--max-new-tokens", type=int, default=1024,
                   help="generation budget per chunk; raise to 2048 if endings get clipped")

    # Mode 3 (concat) BGM mixing args.
    p.add_argument("--bgm", type=Path, default=None,
                   help="(mode 3) BGM mp3 to mix under the concatenated voice; looped to voice length")
    p.add_argument("--voice-gain", type=float, default=1.5,
                   help="(mode 3) linear gain applied to the voice track. Default 1.5x (voice over bgm)")
    p.add_argument("--bgm-gain", type=float, default=0.1,
                   help="(mode 3) linear gain applied to the BGM track. Default 0.1x")
    p.add_argument("--segment-gap", type=float, default=0.3,
                   help="(mode 3) silence inserted between segments, in seconds. Default 0.3s")
    p.add_argument("--voice-tempo", type=float, default=1.1,
                   help="(mode 3) ffmpeg atempo factor for the voice track (pitch preserved). Default 1.1 (10%% faster)")
    args = p.parse_args()

    mode_flags = [bool(args.script), bool(args.segments), bool(args.concat)]
    if sum(mode_flags) != 1:
        print("ERROR: pick exactly one of --script, --segments, --concat", file=sys.stderr)
        return 2

    if args.script:
        for need in ("voice", "voice_text", "out"):
            if not getattr(args, need):
                print(f"ERROR: --{need.replace('_', '-')} required for --script mode", file=sys.stderr)
                return 2
        return run_script_mode(args)

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
