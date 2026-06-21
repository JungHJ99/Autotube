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
FONT_FILE = str(FONT_HOST)            # drawtext fontfile (host path)
FONT_FACE = "Noto Sans CJK KR"
VIDEO_W, VIDEO_H = 1920, 1080

# All ffmpeg/ffprobe runs on the HOST — fish-speech docker is no longer used
# (it needlessly held GPU VRAM and caused OOM). Host has ffmpeg 7.x + libass +
# the NotoSansCJK fonts in fontconfig, which is all we need.
FFMPEG = shutil.which("ffmpeg") or "/home/hjhj/.local/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


def verify_host_font() -> None:
    """Confirm the host fontconfig knows the Korean face used for subtitles."""
    try:
        probe = subprocess.run([shutil.which("fc-list") or "fc-list", ":lang=ko"],
                               capture_output=True, text=True)
        if FONT_FACE not in probe.stdout:
            print(f"NOTE: '{FONT_FACE}' not in host fontconfig; subtitles may use a "
                  f"fallback font. Font file present at {FONT_HOST}: {FONT_HOST.exists()}",
                  file=sys.stderr)
    except FileNotFoundError:
        pass  # fc-list missing — libass will still find the font file via fontconfig dirs


def ffprobe_duration(path: Path) -> float:
    cmd = [
        FFPROBE, "-v", "error",
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
        # Display: subtitle_text (Arabic digits + roman alphabet — reader-facing).
        # Timing: text (TTS-tuned Hangul-spelled — closer to actual speech char count).
        # English book titles like "Bound to Lead" are short in subtitle_text but
        # TTS spells them as "바운드 투 리드" (longer phonetic char count). Using
        # subtitle_text for timing under-allocates time to English-mixed sentences
        # → subtitles drift ahead of audio. Fix: text drives timing, subtitle_text
        # drives display. (2026-06-04 user reported sync from seg 6 "Bound to Lead".)
        display_src = seg.get("subtitle_text") or seg["text"]
        timing_src = seg.get("text") or display_src
        display_sents = split_korean_sentences(display_src)
        timing_sents = split_korean_sentences(timing_src)
        if len(display_sents) != len(timing_sents):
            # Fallback: use display_src for both (subtitle_normalizer should
            # preserve sentence count; if not, log and fall back gracefully).
            timing_sents = display_sents
        total_chars = sum(len(s) for s in timing_sents) or 1
        # female (translator) voice → yellow subtitle.
        is_female = seg.get("voice") == "female"
        sent_t = t
        for j, (display_sent, timing_sent) in enumerate(zip(display_sents, timing_sents)):
            # Last sentence gets the residual to avoid float drift past seg end.
            if j == len(display_sents) - 1:
                end_t = t + seg_dur
            else:
                share = seg_dur * (len(timing_sent) / total_chars)
                end_t = sent_t + share
            lines.append(str(cue_idx))
            lines.append(f"{fmt_srt_time(sent_t)} --> {fmt_srt_time(end_t)}")
            cue_text = f'<font color="#FFFF00">{display_sent}</font>' if is_female else display_sent
            lines.append(cue_text)
            lines.append("")
            cue_idx += 1
            sent_t = end_t
        t += seg_dur
        if i < len(segments) - 1:
            t += segment_gap
    return "\n".join(lines) + "\n"


def render_title_card(out_path: Path, title: str) -> None:
    """Black 1920x1080 with the title centered, via ffmpeg drawtext."""
    # Escape colons/single-quotes/backslashes for drawtext.
    safe_title = (
        title.replace("\\", "\\\\")
        .replace(":", r"\:")
        .replace("'", r"\'")
        .replace("%", r"\%")
    )
    drawtext = (
        f"drawtext=fontfile='{FONT_FILE}'"
        f":text='{safe_title}'"
        f":fontsize=64:fontcolor=white"
        f":x=(w-text_w)/2:y=(h-text_h)/2"
        f":box=1:boxcolor=black@0.0:boxborderw=20"
    )
    cmd = [
        FFMPEG, "-y",
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
    p.add_argument("--docker-container", default=None,
                   help="DEPRECATED/unused — all ffmpeg now runs on the host (no fish-speech).")
    p.add_argument("--title", type=str, default=None,
                   help="title text for the auto-generated title card. Defaults to run folder name.")
    p.add_argument("--char-dir", type=Path,
                   default=Path("/home/hjhj/autotube/characters"),
                   help="dir with {male,female}_{closed,open}.png. Used for talking-head overlay.")
    p.add_argument("--no-chars", action="store_true",
                   help="disable character corner overlay")
    p.add_argument("--char-size", type=int, default=220,
                   help="character height in px (default 220 — bottom-left corner)")
    args = p.parse_args()

    verify_host_font()

    segs_doc = json.loads(args.segments.read_text(encoding="utf-8"))
    segments = segs_doc["segments"]

    # Resolve per-segment MP3 paths in segment order.
    seg_files = sorted(args.segments_dir.glob("*.mp3"))
    if len(seg_files) != len(segments):
        print(f"WARN: {len(seg_files)} segment mp3s vs {len(segments)} entries in json — name order assumed.",
              file=sys.stderr)
    durations = [ffprobe_duration(f) for f in seg_files]
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
    # stock_mode entries: (stock_path_or_None, overlay_path_or_None, dur, is_reaction)
    # - normal seg: (stock_path, optional pdf overlay, dur, False)
    # - reaction_translation seg: (None, comment_image, dur, True) — full-screen comment image
    stock_mode: list[tuple[Path | None, Path | None, float, bool]] | None = None
    def is_reaction(seg):
        # V2: reaction_translation (Yahoo comments). V3: post_body / comment_translation (Reddit/Twitter UI cards).
        # MX: any seg carrying a `bg_image` renders that still full-screen (e.g. the
        # thumbnail shown during the intro). Keeps the seg's own voice + character.
        if seg.get("bg_image"):
            return True
        return seg.get("role") in ("reaction_translation", "post_body", "comment_translation")
    def reaction_image_field(seg):
        # Returns the field name holding the full-screen image for this reaction-style seg.
        if seg.get("bg_image"): return "bg_image"
        r = seg.get("role")
        if r == "reaction_translation": return "comment_image"
        if r == "post_body": return "post_image"
        if r == "comment_translation": return "comment_image"
        return None
    # Reaction-style segs need their UI card image. Normal segs need stock_path.
    # MX: a `motion_bg`-only seg (e.g. a dynamic intro with no card) is also valid.
    all_segs_ok = all(
        seg.get("motion_bg") or
        (is_reaction(seg) and seg.get(reaction_image_field(seg))) or
        (not is_reaction(seg) and seg.get("stock_path"))
        for seg in segments
    )
    if all_segs_ok:
        stock_mode = []
        for i, seg in enumerate(segments):
            dur = durations[i] / args.voice_tempo
            if i < len(segments) - 1:
                dur += args.segment_gap
            # MX dynamic: a `motion_bg` (stock video clip) plays behind the
            # segment. comment/video cards (panel images) float over it; bg_image
            # stills (intro thumbnail, male backdrop) are dropped when motion plays.
            motion_bg = None
            if seg.get("motion_bg"):
                mp = (run_dir / seg["motion_bg"]).resolve()
                if mp.exists():
                    motion_bg = mp
            if is_reaction(seg):
                field = reaction_image_field(seg)
                cimg = (run_dir / seg[field]).resolve()
                if not cimg.exists():
                    print(f"WARN: reaction-style seg {i+1} {field} missing: {cimg}",
                          file=sys.stderr)
                    stock_mode = None
                    break
                is_panel = field in ("comment_image", "post_image")
                # Over motion, only panel cards are inset; bg_image stills are dropped.
                card = cimg if (is_panel or motion_bg is None) else None
                stock_mode.append((None, card, dur, True, motion_bg))
                continue
            # Non-reaction seg with motion_bg but no card/stock (e.g. dynamic intro):
            # moving footage + character only.
            if motion_bg is not None and not seg.get("stock_path"):
                stock_mode.append((None, None, dur, False, motion_bg))
                continue
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
            stock_mode.append((stock_path, overlay_path, dur, False, motion_bg))
        if stock_mode is not None:
            n_overlay = sum(1 for _, o, _, r, _ in stock_mode if o is not None and not r)
            n_reaction = sum(1 for _, _, _, r, _ in stock_mode if r)
            n_motion = sum(1 for _, _, _, _, m in stock_mode if m is not None)
            print(f"Stock-clip mode: {len(stock_mode)} segments, "
                  f"{n_overlay} with PDF overlay (female voice), "
                  f"{n_reaction} reaction-style cards, "
                  f"{n_motion} with motion bg (MX dynamic)", flush=True)

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
        render_title_card(image_path, title)

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

    # Character overlay setup (bottom-left, mouth toggles every 0.3s).
    chars_ok = (not args.no_chars) and args.char_dir.is_dir() and all(
        (args.char_dir / f"{v}_{m}.png").exists()
        for v in ("male", "female") for m in ("closed", "open")
    )
    if not args.no_chars and not chars_ok:
        print(f"NOTE: char-dir incomplete at {args.char_dir} — character overlay disabled",
              file=sys.stderr)

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
        for i, (stock_path, overlay_path, dur, is_react, motion_bg) in enumerate(stock_mode, start=1):
            seg_out = tmp_dir / f"seg_{i:02d}.mp4"
            seg_mp4s.append(seg_out)
            voice = segments[i - 1].get("voice", "male")
            char_closed = args.char_dir / f"{voice}_closed.png"
            char_open = args.char_dir / f"{voice}_open.png"
            ch_w = args.char_size
            # Bottom-left corner with 30px margin. Mouth toggles each 0.3s.
            char_x, char_y = 30, f"H-h-30"

            inputs: list[list[str]] = []
            input_idx = 0

            if motion_bg is not None:
                # MX dynamic: stock video plays behind (cover-fill + darkened so the
                # card pops). A panel card (overlay_path, RGBA with transparent
                # margins) floats over it. Male connective segs have no card → just
                # moving footage + character.
                inputs.append(["-stream_loop", "-1", "-i", str(motion_bg)])
                bg_filter = (
                    f"[0:v]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
                    f"crop={VIDEO_W}:{VIDEO_H},eq=brightness=-0.16:saturation=1.12,"
                    f"setsar=1,fps=24"
                )
                stage = f"{bg_filter}[bg]"
                cur_label = "bg"
                input_idx = 1
                if overlay_path is not None:
                    inputs.append(["-loop", "1", "-i", str(overlay_path)])
                    stage += (
                        f";[{input_idx}:v]format=rgba[card];"
                        f"[{cur_label}][card]overlay=0:0:format=auto[bgc]"
                    )
                    cur_label = "bgc"
                    input_idx += 1
            elif is_react:
                # Reaction (legacy / no-motion): card fills the screen with dark pad.
                inputs.append(["-loop", "1", "-i", str(overlay_path)])
                bg_filter = (
                    f"[0:v]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=decrease,"
                    f"pad={VIDEO_W}:{VIDEO_H}:(ow-iw)/2:(oh-ih)/2:color=0x1a1a1a,"
                    f"setsar=1,fps=24"
                )
                stage = f"{bg_filter}[bg]"
                cur_label = "bg"
                input_idx = 1
            else:
                # Normal: stock clip as bg, optional PDF on the right.
                bg_filter = (
                    f"[0:v]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
                    f"crop={VIDEO_W}:{VIDEO_H},setsar=1,fps=24"
                )
                inputs.append(["-stream_loop", "-1", "-i", str(stock_path)])
                stage = f"{bg_filter}[bg]"
                cur_label = "bg"
                input_idx = 1

                if overlay_path is not None:
                    pdf_w = int(VIDEO_W * 0.38)
                    inputs.append(["-loop", "1", "-i", str(overlay_path)])
                    stage += (
                        f";[{input_idx}:v]scale={pdf_w}:-1[pdf];"
                        f"[{cur_label}][pdf]overlay=x=W-w-40:y=(H-h)/2[bg_pdf]"
                    )
                    cur_label = "bg_pdf"
                    input_idx += 1

            if chars_ok:
                inputs.append(["-loop", "1", "-i", str(char_closed)])
                cc_idx = input_idx
                input_idx += 1
                inputs.append(["-loop", "1", "-i", str(char_open)])
                co_idx = input_idx
                input_idx += 1
                stage += (
                    f";[{cc_idx}:v]scale=-1:{ch_w}[chc]"
                    f";[{co_idx}:v]scale=-1:{ch_w}[cho]"
                    # closed half of 0.6s cycle
                    f";[{cur_label}][chc]overlay=x={char_x}:y={char_y}"
                    f":enable='lt(mod(t\\,0.6)\\,0.3)'[t1]"
                    # open half
                    f";[t1][cho]overlay=x={char_x}:y={char_y}"
                    f":enable='gte(mod(t\\,0.6)\\,0.3)'[v]"
                )
            else:
                stage += f";[{cur_label}]copy[v]"

            fc = stage
            seg_cmd = [FFMPEG, "-y"]
            for inp in inputs:
                seg_cmd += inp
            seg_cmd += [
                "-filter_complex", fc,
                "-map", "[v]",
                "-t", f"{dur:.3f}",
                "-an",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-r", "24", "-s", f"{VIDEO_W}x{VIDEO_H}",
                str(seg_out.resolve()),
            ]

            char_tag = f"{voice[0]}" if chars_ok else "·"
            if motion_bg is not None:
                pdf_tag = "🎬+card" if overlay_path else "🎬 bg "
                src_name = f"{motion_bg.name}" + (f" + {overlay_path.name}" if overlay_path else "")
            elif is_react:
                pdf_tag = "💬react"
                src_name = overlay_path.name
            else:
                pdf_tag = "♀+pdf" if overlay_path else "  bg "
                src_name = stock_path.name
            print(f"  seg {i:02d} [{pdf_tag}|{char_tag}] {dur:5.2f}s ← {src_name}",
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
                [FFMPEG, "-y",
                 "-f", "concat", "-safe", "0", "-i", str(concat_list.resolve()),
                 "-c", "copy", str(vcat.resolve())],
                check=True, capture_output=True, text=True,
            )
        except subprocess.CalledProcessError as e:
            print("ffmpeg concat failed:\n" + e.stderr[-1500:], file=sys.stderr)
            return 1

        # Final mux + subtitle burn.
        cmd = [
            FFMPEG, "-y",
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
        cmd = [FFMPEG, "-y"]
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
            FFMPEG, "-y",
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

    dur = ffprobe_duration(args.out)
    print(f"Video written: {args.out} ({dur:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
