---
name: tts-fish
description: Use this skill to convert a Korean script into MP3 audio via fish-speech v1.5 running in Docker. Supports three modes — (1) single-voice script.txt → one MP3, (2) dual-voice segments.json → one MP3 per segment for human review, (3) concat reviewed segment MP3s into a final MP3. Handles chunking, msgpack API calls, WAV concatenation, and MP3 conversion (uses the container's bundled ffmpeg when host ffmpeg is missing). Also documents the one-time Docker setup. Invoke when the user wants to generate narration audio for a 국뽕 YouTube video.
---

# tts-fish — fish-speech 1.5 narration generator (Docker-based)

Converts a Korean script into a single `.mp3` (or a folder of per-segment MP3s) by calling the fish-speech 1.5 API server running in a Docker container (`autotube-fish-speech`).

Heavy lifting is done by [scripts/tts_fish_client.py](scripts/tts_fish_client.py); this skill tells Claude **when** and **how** to call it, and how to manage the container.

## Quick check before doing anything

Run all four together:

```bash
# 1. Container running?
docker ps --filter name=autotube-fish-speech --format '{{.Status}}'
# 2. API responding? (v1.5 has /v1/health under msgpack auth — easier to hit /openapi)
curl -sS -o /dev/null -w "%{http_code}\n" -m 3 http://127.0.0.1:8080/openapi || echo "API down"
# 3. Voices available?
ls /home/hjhj/autotube/voices/*/ref.wav 2>/dev/null
# 4. GPU visible to container?
docker exec autotube-fish-speech nvidia-smi -L 2>/dev/null | head -1 || echo "GPU not visible"
```

Decision tree:
- Container not running → `cd /home/hjhj/autotube && docker compose up -d`. **First boot** can take 30-60s while models load into VRAM; tail logs with `docker compose logs -f` until you see `Startup done, listening server at http://0.0.0.0:8080`.
- API down but container running → check `docker compose logs fish-speech` for crashes (OOM, missing checkpoint files, port collision).
- No voice → see [Reference voices](#reference-voices); stop and surface to user.
- No GPU → ensure `nvidia-container-toolkit` installed and Docker daemon restarted.

## Three modes

### Mode 1 — single-voice script.txt (legacy)

```bash
python3 scripts/tts_fish_client.py \
    --script output/<run>/script.txt \
    --voice voices/<name>/ref.wav \
    --voice-text "$(cat voices/<name>/ref.txt)" \
    --out output/<run>/audio.mp3
```

Splits script on Korean sentence boundaries, synthesizes each chunk with one voice, concatenates WAV → MP3. Use this for a single-narrator video (legacy structure, pre-dual-voice).

### Mode 2 — dual-voice segments.json → per-segment MP3s

This is the **current default** for the autotube pipeline (translator + commentator structure).

```bash
python3 scripts/tts_fish_client.py \
    --segments output/<run>/segments.json \
    --male-voice voices/male_voice/ref.wav \
    --male-voice-text "$(cat voices/male_voice/ref.txt)" \
    --female-voice voices/female_voice/ref.wav \
    --female-voice-text "$(cat voices/female_voice/ref.txt)" \
    --segments-out-dir output/<run>/segments/
```

Reads `segments.json` (produced by `kpop-script-writer`). Each segment is tagged with `voice` (`male` or `female`) and `role` (`intro` / `bridge` / `translation` / `commentary` / `closing`). Each segment becomes its own MP3 at:

```
output/<run>/segments/
  01_intro_male.mp3
  02_bridge_male.mp3
  03_translation_female.mp3
  04_commentary_male.mp3
  05_translation_female.mp3
  ...
  NN_closing_male.mp3
```

**No concatenation in this step** — the user reviews per-segment MP3s before commit. To re-synthesize specific segments only (after a script edit, for instance):

```bash
# Re-do segments 3, 5, 7 only
python3 scripts/tts_fish_client.py \
    --segments output/<run>/segments.json \
    --male-voice ... --male-voice-text ... \
    --female-voice ... --female-voice-text ... \
    --segments-out-dir output/<run>/segments/ \
    --only 3 5 7 \
    --overwrite
```

Without `--overwrite`, existing per-segment MP3s are skipped (idempotent).

### Mode 3 — concat reviewed segment MP3s → final MP3 (with BGM)

After the user has reviewed and approved the per-segment MP3s. **Default behavior mixes the voice with a looping BGM track, speeds the voice 1.1x, and inserts 0.3s gaps between segments** — `--bgm` is the standard final step.

```bash
python3 scripts/tts_fish_client.py \
    --concat output/<run>/segments/ \
    --bgm "bgm/거대한 문턱.mp3" \
    --out output/<run>/audio.mp3
```

Defaults (calibrated 2026-05-13):
- `--voice-gain 1.5` — voice track 1.5x
- `--bgm-gain 0.1` — BGM 0.1x (10%)
- `--voice-tempo 1.1` — voice played 1.1x faster (atempo, pitch preserved)
- `--segment-gap 0.3` — 0.3s silence inserted between each pair of segments

Override individual flags if a different track or content needs rebalancing, but **do not silently drop --bgm or zero out the gap/tempo** — they are the calibrated baseline.

Pipeline internals:
- Concatenates per-segment MP3s in filename order (the `NN_` prefix matters) using ffmpeg's concat demuxer.
- If `--segment-gap > 0`, generates a silent MP3 (`anullsrc`) once and splices it between segments in the manifest.
- If `--voice-tempo != 1.0`, applies `atempo=<factor>` to the voice filter chain.
- Stream-loops the BGM to cover the (tempo-adjusted) voice length; mixes via `amix duration=first`.

If you really need the voice-only track (debug / inspection), drop `--bgm`:

```bash
python3 scripts/tts_fish_client.py --concat output/<run>/segments/ --out output/<run>/_voice_only.mp3
```

**BGM placement.** The script auto-stages the BGM into `output/` before invoking the in-container ffmpeg (the container only mounts `voices/` and `output/`, so a BGM under `bgm/` would otherwise be unreachable). The staged file is removed after the mix.

## Optional flags (all modes)

- `--temperature 0.7` — sampling temperature (lower = more stable, 0.5-0.9 range).
- `--top-p 0.7` — nucleus sampling (lower = more deterministic).
- `--repetition-penalty 1.2` — bump up if the model repeats words; down if it sounds robotic.
- `--seed 12345` — fix the seed for reproducible takes.
- `--api http://127.0.0.1:8080/v1/tts` — override API URL.
- `--max-chunk 200` — chars per chunk (lower if you get OOM/timeout). Fish-speech caps chunk_length at 300 server-side.
- `--docker-container autotube-fish-speech` — override container name for ffmpeg fallback.

## When asked to "generate audio for the latest script"

If the user doesn't specify which run, find the most recent:

```bash
ls -dt /home/hjhj/autotube/output/*/segments.json 2>/dev/null | head -1
# or for legacy single-voice runs:
ls -dt /home/hjhj/autotube/output/*/script.txt 2>/dev/null | head -1
```

Prefer `segments.json` (the current pipeline output). Fall back to `script.txt` only if no segments file exists.

## Setup (one-time)

Already configured if the user follows this guide. Prereqs (verify before first `up`):

- Docker 24+ and `docker compose` plugin
- `nvidia-container-toolkit` (`dpkg -l | grep nvidia-container-toolkit`)
- NVIDIA driver supporting CUDA 12.4+
- ~5 GB disk for the image + ~1.4 GB for checkpoints
- 8 GB VRAM minimum (fish-speech 1.5 with `--half` flag fits comfortably on RTX 3070 Ti)

Checkpoints live at `/home/hjhj/autotube/fish_speech_checkpoints/fish-speech-1.5/`. They are NOT baked into the image and are mounted read-only via compose. Files (from HuggingFace `fishaudio/fish-speech-1.5`, CC-BY-NC-SA-4.0, gating-free):

- `model.pth` (~1.2 GB) — dual-AR LLaMA TTS backbone
- `firefly-gan-vq-fsq-8x1024-21hz-generator.pth` (~188 MB) — VQGAN decoder
- `config.json`, `special_tokens.json`, `tokenizer.tiktoken`

Then:

```bash
cd /home/hjhj/autotube
docker compose pull   # first time: ~4.6 GB image
docker compose up -d
docker compose logs -f fish-speech   # watch until "Startup done, listening server at http://0.0.0.0:8080"
```

The image is `fishaudio/fish-speech:v1.5.1` (prebuilt by upstream). Defaults are overridden in compose to run the API server (not the gradio webui) and to pass `--half` for VRAM headroom.

## Common ops

```bash
# Stop API server (frees ~3 GB VRAM)
docker compose down

# Restart after a config change
docker compose restart fish-speech

# Get a shell inside the container (debugging)
docker exec -it autotube-fish-speech bash

# Inspect API logs
docker compose logs --tail 100 fish-speech
```

## Reference voices

Each voice lives in [voices/](voices/) as a self-contained folder:

```
voices/
  male_voice/
    ref.wav        # 3-10 sec, mono, 16kHz+, clean Korean speech
    ref.txt        # EXACT transcript of ref.wav
    LICENSE.txt    # source/license of the voice
    notes.md       # optional: tone description
  female_voice/
    ref.wav
    ref.txt
    LICENSE.txt
```

**Current pipeline voices (dual-voice mode):**
- `voices/male_voice/` — commentator / 사설가 (intro, bridge, commentary, closing segments).
- `voices/female_voice/` — translator / 번역자 (translation segments). KSS dataset sample (CC-BY-NC-SA 4.0).

When the user wants to "add a voice":
1. Confirm the source is open-source / CC-licensed / user-recorded. Don't help create deepfakes of real public figures without their consent.
2. Save `ref.wav` and `ref.txt`. The transcript must match the audio precisely (a typo here degrades the whole output voice).
3. Suggest a one-line `notes.md` describing tone.

## Troubleshooting

- **`Permission denied` on `/home/hjhj/autotube/output/...`** — the container writes as a different UID. Either `chmod -R a+rw output/` or change the compose to add `user: "1000:1000"` (matching host UID).
- **`CUDA out of memory`** — `--half` is already on. If still OOM, lower max chunk via `--max-chunk 150`, or restart with `shm_size: "4g"` instead of 8g.
- **Korean reads with wrong tone** — check `voices/<name>/ref.txt` matches `ref.wav` exactly. Even one wrong syllable noticeably degrades prosody.
- **English proper nouns sound wrong** — transliterate them in the script (e.g. "BTS" → "비티에스"). The script-writer agent already handles this for common cases.
- **HTTP 401 from the API** — fish-speech `tools/api_server.py` sets `api_key=None` by default, so requests with any bearer (or none) should pass.
- **Long synth time on first chunk** — fish-speech compiles parts of the graph on first inference. The second chunk onward is much faster.
- **Concat output has audible pops/clicks at segment boundaries** — segments are independent WAVs converted to MP3 separately, so encoder boundaries don't always align. The concat mode re-encodes through libmp3lame to smooth things; if you still hear artifacts, consider switching to WAV concat first by editing the client.

## What this skill does NOT do

- Install fish-speech from scratch on host (we use Docker).
- Start the container automatically without confirmation — the user runs `docker compose up -d` once and leaves it.
- Find sources or write scripts (use `kpop-source-finder` / `kpop-script-writer` agents).
- Generate video. Not in scope yet.
