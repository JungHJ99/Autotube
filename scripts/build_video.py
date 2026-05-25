#!/usr/bin/env python3
"""
Stage-1 video builder for autotube.

Takes a finished segments.json + per-segment MP3s + final audio.mp3
and produces a simple talking-paper style mp4:

    [static background image, looped to audio length]
    + audio.mp3 as the soundtrack
    + Korean subtitles (burned in, sentence-level), synced to the per-segment
      MP3 durations and the concat parameters (voice_tempo, segment_gap)

Usage:
    python3 scripts/build_video.py \\
        --segments output/<run>/segments.json \\
        --segments-dir output/<run>/segments/ \\
        --audio output/<run>/audio.mp3 \\
        --image output/<run>/bg.jpg \\
        --out output/<run>/video.mp4

If --image is omitted, a black 1920x1080 title card is generated with the
first segment's text (or the topic slug) as the title.

The subtitle timeline assumes the audio.mp3 was rendered with the standard
concat defaults (--voice-tempo 1.1 --segment-gap 0.3). Override via flags
if you used different mix parameters.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


FONT_HOST = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")
FONT_IN_CONTAINER = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_FACE = "Noto Sans CJK KR"
DOCKER_CONTAINER = "autotube-fish-speech"
VIDEO_W, VIDEO_H = 1920, 1080


def ensure_korean_font_in_container(container: str) -> None:
    """Make sure the container's fontconfig knows about a Korean face.

    Container filesystem is ephemeral; restart wipes /usr/share/fonts additions.
    Idempotent: fast path is one fc-list call.
    """
    probe = subprocess.run(
        ["docker", "exec", container, "fc-list", ":lang=ko"],
        capture_output=True, text=True,
    )
    if FONT_FACE in probe.stdout:
        return
    print(f"Container missing '{FONT_FACE}' — copying font + rebuilding fc-cache...",
          flush=True)
    subprocess.run(
        ["docker", "exec", container, "mkdir", "-p",
         str(Path(FONT_IN_CONTAINER).parent)],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["docker", "cp", str(FONT_HOST), f"{container}:{FONT_IN_CONTAINER}"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["docker", "exec", container, "fc-cache", "-f", "/usr/share/fonts"],
        check=True, capture_output=True,
    )
    verify = subprocess.run(
        ["docker", "exec", container, "fc-list", ":lang=ko"],
        capture_output=True, text=True,
    )
    if FONT_FACE not in verify.stdout:
        raise RuntimeError(
            f"Korean font still not visible inside {container} after fc-cache. "
            f"Got:\n{verify.stdout[:500]}"
        )


def ffprobe_duration(path: Path, container: str) -> float:
    cmd = [
        "docker", "exec", container, "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path.resolve()),
    ]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    return float(out.strip())


def split_korean_sentences(text: str) -> list[str]:
    """Split Korean text on .!? boundaries while keeping the punctuation."""
    # Split, then re-attach trailing punctuation to the preceding sentence.
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def fmt_srt_time(t: float) -> str:
    ms = int(round((t - int(t)) * 1000))
    s = int(t) % 60
    m = (int(t) // 60) % 60
    h = int(t) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(
    segments: list[dict],
    seg_durations: list[float],
    voice_tempo: float,
    segment_gap: float,
) -> str:
    """Build an SRT string. Each Korean sentence becomes one cue.

    Within a segment, sentences are allotted time proportional to char count.
    Across segments, the gap silence is real (no subtitle during the gap).
    """
    lines: list[str] = []
    cue_idx = 1
    t = 0.0
    for i, seg in enumerate(segments):
        seg_dur = seg_durations[i] / voice_tempo  # tempo squeezes the audio
        # Prefer reader-facing subtitle_text (Arabic digits + roman alphabet)
        # over the TTS-tuned text (Hangul-spelled numbers + transliterations).
        subtitle_src = seg.get("subtitle_text") or seg["text"]
        sentences = split_korean_sentences(subtitle_src)
        total_chars = sum(len(s) for s in sentences) or 1
        # female (translator) voice → yellow subtitle.
        # SRT-extension <font color> tag is the most portable across parsers.
        is_female = seg.get("voice") == "female"
        sent_t = t
        for j, sent in enumerate(sentences):
            # Last sentence gets the residual to avoid float drift past seg end.
            if j == len(sentences) - 1:
                end_t = t + seg_dur
            else:
                share = seg_dur * (len(sent) / total_chars)
                end_t = sent_t + share
            lines.append(str(cue_idx))
            lines.append(f"{fmt_srt_time(sent_t)} --> {fmt_srt_time(end_t)}")
            cue_text = f'<font color="#FFFF00">{sent}</font>' if is_female else sent
            lines.append(cue_text)
            lines.append("")
            cue_idx += 1
            sent_t = end_t
        t += seg_dur
        if i < len(segments) - 1:
            t += segment_gap
    return "\n".join(lines) + "\n"


def render_title_card(out_path: Path, title: str, container: str) -> None:
    """Black 1920x1080 with the title centered, via ffmpeg drawtext."""
    # Escape colons/single-quotes/backslashes for drawtext.
    safe_title = (
        title.replace("\\", "\\\\")
        .replace(":", r"\:")
        .replace("'", r"\'")
        .replace("%", r"\%")
    )
    drawtext = (
        f"drawtext=fontfile='{FONT_IN_CONTAINER}'"
        f":text='{safe_title}'"
        f":fontsize=64:fontcolor=white"
        f":x=(w-text_w)/2:y=(h-text_h)/2"
        f":box=1:boxcolor=black@0.0:boxborderw=20"
    )
    cmd = [
        "docker", "exec", container, "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s={VIDEO_W}x{VIDEO_H}:d=1",
        "-frames:v", "1",
        "-vf", drawtext,
        str(out_path.resolve()),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--segments", type=Path, required=True)
    p.add_argument("--segments-dir", type=Path, required=True)
    p.add_argument("--audio", type=Path, required=True)
    p.add_argument("--image", type=Path, default=None,
                   help="static bg image. If omitted, a black title card is generated.")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--voice-tempo", type=float, default=1.1,
                   help="match the concat call's --voice-tempo. Default 1.1")
    p.add_argument("--segment-gap", type=float, default=0.3,
                   help="match the concat call's --segment-gap. Default 0.3")
    p.add_argument("--docker-container", default=DOCKER_CONTAINER)
    p.add_argument("--title", type=str, default=None,
                   help="title text for the auto-generated title card. Defaults to run folder name.")
    args = p.parse_args()

    ensure_korean_font_in_container(args.docker_container)

    segs_doc = json.loads(args.segments.read_text(encoding="utf-8"))
    segments = segs_doc["segments"]

    # Resolve per-segment MP3 paths in segment order.
    seg_files = sorted(args.segments_dir.glob("*.mp3"))
    if len(seg_files) != len(segments):
        print(f"WARN: {len(seg_files)} segment mp3s vs {len(segments)} entries in json — name order assumed.",
              file=sys.stderr)
    durations = [ffprobe_duration(f, args.docker_container) for f in seg_files]
    print(f"Per-segment durations (sec, pre-tempo): "
          f"sum={sum(durations):.1f}, tempo={args.voice_tempo}, gap={args.segment_gap}",
          flush=True)

    # SRT next to the output.
    out_dir = args.out.parent.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    srt_path = out_dir / f".{args.out.stem}.srt"
    srt_text = build_srt(segments, durations, args.voice_tempo, args.segment_gap)
    srt_path.write_text(srt_text, encoding="utf-8")
    print(f"SRT cues: {srt_text.count(' --> ')} → {srt_path.name}")

    # Decide visual mode: stock-clip + optional PDF overlay (highest priority,
    # triggered by `stock_path` field on every segment), per-segment images,
    # or single static image / title card.
    run_dir = args.segments.parent.resolve()
    stock_mode: list[tuple[Path, Path | None, float]] | None = None
    if all(seg.get("stock_path") for seg in segments):
        stock_mode = []
        for i, seg in enumerate(segments):
            stock_path = (run_dir / seg["stock_path"]).resolve()
            if not stock_path.exists():
                print(f"WARN: segment {i+1} stock_path missing: {stock_path}",
                      file=sys.stderr)
                stock_mode = None
                break
            overlay_path: Path | None = None
            if seg.get("voice") == "female" and seg.get("image"):
                p = (run_dir / seg["image"]).resolve()
                if p.exists():
                    overlay_path = p
            dur = durations[i] / args.voice_tempo
            if i < len(segments) - 1:
                dur += args.segment_gap
            stock_mode.append((stock_path, overlay_path, dur))
        if stock_mode is not None:
            n_overlay = sum(1 for _, o, _ in stock_mode if o is not None)
            print(f"Stock-clip mode: {len(stock_mode)} segments, "
                  f"{n_overlay} with PDF overlay (female voice)", flush=True)

    per_seg_images: list[tuple[Path, float]] | None = None
    if stock_mode is None and all(seg.get("image") for seg in segments):
        per_seg_images = []
        for i, seg in enumerate(segments):
            img_rel = seg["image"]
            img_path = (run_dir / img_rel).resolve()
            if not img_path.exists():
                print(f"WARN: segment {i+1} image missing: {img_path}", file=sys.stderr)
                per_seg_images = None
                break
            dur = durations[i] / args.voice_tempo
            if i < len(segments) - 1:
                dur += args.segment_gap
            per_seg_images.append((img_path, dur))
        if per_seg_images is not None:
            print(f"Per-segment image mode: {len(per_seg_images)} images", flush=True)

    # Image: provided or generated title card. Skipped in stock_mode (the visual
    # comes from per-segment clips, not a static bg).
    staged_image: Path | None = None
    image_path: Path | None = None
    if stock_mode is not None:
        pass
    elif args.image is not None:
        # If image is outside the output/voices mount, stage it.
        img_abs = args.image.resolve()
        mounted_roots = [
            Path("/home/hjhj/autotube/output").resolve(),
            Path("/home/hjhj/autotube/voices").resolve(),
        ]
        in_mount = any(str(img_abs).startswith(str(r) + "/") for r in mounted_roots)
        if not in_mount:
            staged_image = out_dir / f".bg_staged{img_abs.suffix or '.jpg'}"
            shutil.copyfile(img_abs, staged_image)
            image_path = staged_image
        else:
            image_path = img_abs
    else:
        title = args.title or args.out.parent.name
        image_path = out_dir / f".title_card_{args.out.stem}.png"
        render_title_card(image_path, title, args.docker_container)

    # Build the ffmpeg command:
    #   -loop image  -> infinite video stream
    #   -i audio      -> audio
    #   -shortest     -> stop at audio end
    #   -vf scale + subtitles overlay
    # libass `force_style` controls the burned-in look.
    style = (
        "FontName=Noto Sans CJK KR,FontSize=28,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,"
        "Alignment=2,MarginV=70"
    )
    # libass picks the font from the container's fontconfig (ensured above).
    # Escape commas/colons in the subtitle path per ffmpeg's filter syntax.
    srt_filter_arg = str(srt_path.resolve()).replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")
    scale_pad = (
        f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=decrease,"
        f"pad={VIDEO_W}:{VIDEO_H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
    )
    subs_filter = f"subtitles='{srt_filter_arg}':force_style='{style}'"

    if stock_mode is not None:
        # Per-segment build: stock clip (looped) as bg, optional PDF overlay
        # on right side for female-voice segments. Then concat → mux audio +
        # burn subtitles.
        tmp_dir = run_dir / ".build_video_tmp"
        tmp_dir.mkdir(exist_ok=True)
        # Clean previous segment files (keep tmp dir to reuse across runs is OK
        # but stale files from different segment counts cause confusion).
        for old in tmp_dir.glob("seg_*.mp4"):
            old.unlink()

        seg_mp4s: list[Path] = []
        for i, (stock_path, overlay_path, dur) in enumerate(stock_mode, start=1):
            seg_out = tmp_dir / f"seg_{i:02d}.mp4"
            seg_mp4s.append(seg_out)
            bg_filter = (
                f"[0:v]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
                f"crop={VIDEO_W}:{VIDEO_H},setsar=1,fps=24"
            )
            if overlay_path is not None:
                # PDF page on the right, ~38% screen width, vertically centered.
                pdf_w = int(VIDEO_W * 0.38)
                fc = (
                    f"{bg_filter}[bg];"
                    f"[1:v]scale={pdf_w}:-1[pdf];"
                    f"[bg][pdf]overlay=x=W-w-40:y=(H-h)/2[v]"
                )
                seg_cmd = [
                    "docker", "exec", args.docker_container, "ffmpeg", "-y",
                    "-stream_loop", "-1", "-i", str(stock_path),
                    "-loop", "1", "-i", str(overlay_path),
                    "-filter_complex", fc,
                    "-map", "[v]",
                    "-t", f"{dur:.3f}",
                    "-an",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-r", "24", "-s", f"{VIDEO_W}x{VIDEO_H}",
                    str(seg_out.resolve()),
                ]
            else:
                fc = f"{bg_filter}[v]"
                seg_cmd = [
                    "docker", "exec", args.docker_container, "ffmpeg", "-y",
                    "-stream_loop", "-1", "-i", str(stock_path),
                    "-filter_complex", fc,
                    "-map", "[v]",
                    "-t", f"{dur:.3f}",
                    "-an",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-r", "24", "-s", f"{VIDEO_W}x{VIDEO_H}",
                    str(seg_out.resolve()),
                ]
            tag = "♀+pdf" if overlay_path else "  bg "
            print(f"  seg {i:02d} [{tag}] {dur:5.2f}s ← {stock_path.name}",
                  flush=True)
            try:
                subprocess.run(seg_cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                print(f"ffmpeg seg {i} failed:\n" + e.stderr[-1500:], file=sys.stderr)
                return 1

        # Concat list.
        concat_list = tmp_dir / "concat.txt"
        concat_list.write_text(
            "".join(f"file '{p.resolve()}'\n" for p in seg_mp4s),
            encoding="utf-8",
        )
        vcat = tmp_dir / "vcat.mp4"
        try:
            subprocess.run(
                ["docker", "exec", args.docker_container, "ffmpeg", "-y",
                 "-f", "concat", "-safe", "0", "-i", str(concat_list.resolve()),
                 "-c", "copy", str(vcat.resolve())],
                check=True, capture_output=True, text=True,
            )
        except subprocess.CalledProcessError as e:
            print("ffmpeg concat failed:\n" + e.stderr[-1500:], file=sys.stderr)
            return 1

        # Final mux + subtitle burn.
        cmd = [
            "docker", "exec", args.docker_container, "ffmpeg", "-y",
            "-i", str(vcat.resolve()),
            "-i", str(args.audio.resolve()),
            "-vf", subs_filter,
            "-af", "apad",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-shortest", "-r", "24",
            "-movflags", "+faststart",
            str(args.out.resolve()),
        ]
    elif per_seg_images is not None:
        # Multi-input ffmpeg: each segment is its own looped-image input, then
        # concat into one video stream and burn subtitles on the result.
        cmd = ["docker", "exec", args.docker_container, "ffmpeg", "-y"]
        for img_path, dur in per_seg_images:
            cmd += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(img_path)]
        audio_idx = len(per_seg_images)
        cmd += ["-i", str(args.audio.resolve())]
        # filter graph: scale each input → concat → subtitles
        parts = []
        for i in range(len(per_seg_images)):
            parts.append(f"[{i}:v]{scale_pad}[v{i}]")
        concat_inputs = "".join(f"[v{i}]" for i in range(len(per_seg_images)))
        parts.append(f"{concat_inputs}concat=n={len(per_seg_images)}:v=1:a=0[vcat]")
        parts.append(f"[vcat]{subs_filter}[outv]")
        cmd += [
            "-filter_complex", ";".join(parts),
            "-af", "apad",
            "-map", "[outv]", "-map", f"{audio_idx}:a",
            "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-shortest", "-r", "24",
            "-movflags", "+faststart",
            str(args.out.resolve()),
        ]
    else:
        vf = f"{scale_pad},{subs_filter}"
        cmd = [
            "docker", "exec", args.docker_container, "ffmpeg", "-y",
            "-loop", "1", "-i", str(image_path.resolve()),
            "-i", str(args.audio.resolve()),
            "-vf", vf,
            "-af", "apad",
            "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-shortest", "-r", "24",
            "-movflags", "+faststart",
            str(args.out.resolve()),
        ]
    print("ffmpeg compose...", flush=True)
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print("ffmpeg failed:\n" + e.stderr[-2000:], file=sys.stderr)
        return 1
    finally:
        # Keep the SRT around for debugging — easy to inspect cue timing.
        if staged_image is not None:
            staged_image.unlink(missing_ok=True)

    dur = ffprobe_duration(args.out, args.docker_container)
    print(f"Video written: {args.out} ({dur:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
