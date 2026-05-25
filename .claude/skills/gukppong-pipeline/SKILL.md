---
name: gukppong-pipeline
description: Use this skill to run the full autotube pipeline end-to-end — find a very recent (2026+) overseas K-culture source, write a Korean dual-voice script, generate per-segment MP3s for review, concat to final audio with BGM, then auto-build a 1920x1080 video with stock B-roll background + PDF page overlay on female-voice segments + burned-in subtitles. Orchestrates kpop-source-finder, kpop-script-writer, subtitle-normalizer, stock-query-tagger agents and the tts-fish skill, writing all artifacts into one dated run folder under output/. Invoke when the user says things like "국뽕 영상 만들어줘", "이 주제로 영상 한 편", "다음 영상 만들어줘", or otherwise wants the full end-to-end flow.
---

# gukppong-pipeline — end-to-end 국뽕 video pipeline (audio + video, auto)

Coordinates **11 stages** into a single run folder, with **one** human review gate (per-segment voice check after stage 3a). Everything else runs automatically.

## Stages

```
[stage 1]   kpop-source-finder agent   →  sources.json + <slug>.pdf
[stage 2]   kpop-script-writer agent   →  segments.json + script_notes.md
[stage 3a]  tts-qwen3 segments mode    →  segments/*.mp3 (one per segment)
[review gate — user listens, requests fixes if any. Only mandatory pause.]
[stage 3b]  tts concat + BGM           →  audio.mp3
[stage 4]   pdftoppm                   →  pdf_pages/page-NN.png
[stage 5]   page-map injection         →  segments.json (image field)
[stage 6]   subtitle-normalizer agent  →  segments.json (subtitle_text field)
[stage 7]   stock-query-tagger agent   →  segments.json (stock_query field)
[stage 8]   stock_fetcher.py (Pexels)  →  stock_clips/*.mp4 + manifest.json
[stage 9]   stock-path injection       →  segments.json (stock_path field)
[stage 10]  build_video.py stock mode  →  video.mp4
[stage 11]  /youtube thumbnail brief +
            build_thumbnail.py --spec  →  thumbnail_brief.md + thumbnail_spec.json
                                          + thumbnail.png
```

The single review gate sits between stages 3a and 3b. Once the user signals "합치자", stages 3b → 11 run without pause until thumbnail.png is on disk.

## Run folder convention

```
output/<YYYY-MM-DD>-<topic-slug>/
    sources.json
    <slug>.pdf                  # primary source PDF (downloaded by stage 1)
    segments.json               # accumulates fields across stages:
                                #   stage 2: youtube{title, hashtags, description}
                                #            + segments[{n,voice,role,text}]
                                #   stage 5: segments[].image
                                #   stage 6: segments[].subtitle_text
                                #   stage 7: segments[].stock_query
                                #   stage 9: segments[].stock_path
    script_notes.md
    segments/
        01_intro_male.mp3
        02_bridge_male.mp3
        03_translation_female.mp3
        ...
        NN_closing_male.mp3
    audio.mp3                   # final voice + BGM mix
    pdf_pages/
        page-01.png ... page-NN.png
    stock_clips/
        NN_<slug>_pexels_*.mp4
        manifest.json
    video.mp4                   # final video
    thumbnail_brief.md          # /youtube thumbnail brief output (human-readable)
    thumbnail_spec.json         # machine-readable render contract for stage 11
    thumbnail.png               # final 1280x720 YouTube thumbnail
```

Decide the slug from the topic (e.g. `2026-05-13-bts-cannes-impact`). Keep it short, kebab-case, ASCII. If the same date+slug exists, append `-2`, `-3`, etc.

## Workflow

1. **Clarify the topic, briefly.** If the user gave a specific angle, use it. If they said something vague like "아무거나 국뽕 영상", proceed with a fresh angle of your own — the source-finder will validate whether 2026+ evidence exists. Don't grill the user.

2. **Check voices.** Dual-voice mode requires both:
   ```bash
   ls /home/hjhj/autotube/voices/male_voice/ref.wav /home/hjhj/autotube/voices/male_voice/ref.txt
   ls /home/hjhj/autotube/voices/female_voice/ref.wav /home/hjhj/autotube/voices/female_voice/ref.txt
   ```
   If either is missing, surface the gap and stop — point to the `tts-fish` skill's "Reference voices" section.

3. **Create the run folder** at `output/<run>/`.

4. **Stage 1 — sources.** Invoke the `kpop-source-finder` agent via the Agent tool. Pass:
   - The topic / angle
   - The output path: `output/<run>/sources.json`
   - The hard constraint: **publication date must be 2026-01-01 or later**
   - The instruction to extract `key_passages_for_translation` (4-7 substantial original-language passages)
   - The instruction to stop after writing the JSON (don't let it script).

   Wait for it to finish. Verify:
   ```bash
   python3 -c "import json; d = json.load(open('output/<run>/sources.json')); print('date:', d['primary_source']['date']); print('passages:', len(d['primary_source'].get('key_passages_for_translation', [])))"
   ```
   - `date` must start with `2026-` (or later). If not, ask user whether to accept anyway or rerun.
   - `key_passages_for_translation` count must be 4-7. If fewer, the body will be too thin — rerun with broader search or accept thin output.

5. **Stage 2 — segmented script.** Invoke the `kpop-script-writer` agent. Pass:
   - The path to `sources.json`
   - The output path: `output/<run>/segments.json`
   - The instruction to also save `script_notes.md` alongside.

   Wait for it. Validate the JSON structure:
   ```bash
   python3 -c "
   import json
   d = json.load(open('output/<run>/segments.json'))
   segs = d['segments']
   roles = {}
   for s in segs:
       roles[s['role']] = roles.get(s['role'], 0) + 1
   print('total:', len(segs), 'roles:', roles)
   "
   ```
   Expected: 11-17 segments, exactly 1 intro, 1 bridge, 1 closing, plus alternating translation/commentary. Show the intro segment text to the user.

6. **Confirm script before TTS.** TTS is slow. After showing the intro + segment count, ask: "이 구조로 음성 생성할까요? (수정하고 싶으면 알려줘.)" Wait for go/no-go. If they want edits, either you edit `segments.json` directly or re-invoke `kpop-script-writer` with a feedback note. Re-confirm after edits.

7. **Stage 3a — per-segment audio.** Primary TTS as of 2026-05-21 is **Qwen3-TTS-12Hz-1.7B-Base** (Apache 2.0, voice clone). Runs locally in `f5tts-venv` — no Docker server.

   **Important: free up VRAM first.** Qwen and fish-speech container can't coexist on the 7.65GB RTX 3070 Ti. If fish-speech is up, stop it (ask the user first — `docker compose stop fish-speech` requires their explicit OK):

   ```bash
   docker ps --filter name=autotube-fish-speech --format '{{.Status}}'
   # If running, ask user: "fish-speech 컨테이너 멈춰도 돼? Qwen3-TTS 가 VRAM 을 먹어서 같이 못 돈다."
   # Once authorized:
   docker compose stop fish-speech
   ```

   Then synthesize each segment to its own MP3:

   ```bash
   source f5tts-venv/bin/activate
   python3 scripts/tts_qwen_client.py \
       --segments output/<run>/segments.json \
       --male-voice voices/male_voice/ref.wav \
       --male-voice-text "$(cat voices/male_voice/ref.txt)" \
       --female-voice voices/female_voice/ref.wav \
       --female-voice-text "$(cat voices/female_voice/ref.txt)" \
       --segments-out-dir output/<run>/segments/
   ```

   This writes `output/<run>/segments/NN_<role>_<voice>.mp3`. Defaults baked into the client:
   - `--male-gain 1.6` — male voice-clone is consistently quieter than female, +60% boost levels the mix
   - `--female-gain 1.0` — base level
   - `--tail-pad 0.25` — 250ms silence appended per segment (prevents EOS clipping the final phoneme)
   - Text padding: trailing `.` + space auto-added if missing, gives Qwen's LM a tail token to emit

   Speed: ~0.78x realtime on the 3070 Ti, so a 17-segment script (~8 min audio) takes ~10 min synth. Model load is ~5s one-shot.

   For full reference see [[reference-qwen3-tts]]. Legacy fish-speech client at `scripts/tts_fish_client.py` is kept only as a fallback.

8. **Review gate — user listens, requests fixes.** This is the new step. After stage 3a finishes:

   - List the per-segment MP3s with their text preview so the user knows what they're listening to:
     ```bash
     python3 -c "
     import json
     d = json.load(open('output/<run>/segments.json'))
     for s in d['segments']:
         print(f\"  {int(s['n']):02d}_{s['role']}_{s['voice']}.mp3  —  {s['text'][:60]}...\")
     "
     ```
   - Tell the user: "각 세그먼트 MP3 를 들어보시고, 다시 만들고 싶은 번호 알려주시면 그것만 재합성합니다. 다 OK 면 '합치자' 라고 해주세요."
   - If they request specific segments to redo:
     - Edit `segments.json` if the text needs changing.
     - Re-run with `--only N M ... --overwrite` to regenerate just those segments:
       ```bash
       source f5tts-venv/bin/activate
       python3 scripts/tts_qwen_client.py \
           --segments output/<run>/segments.json \
           --male-voice voices/male_voice/ref.wav \
           --male-voice-text "$(cat voices/male_voice/ref.txt)" \
           --female-voice voices/female_voice/ref.wav \
           --female-voice-text "$(cat voices/female_voice/ref.txt)" \
           --segments-out-dir output/<run>/segments/ \
           --only 3 7 --overwrite
       ```
     - Loop back to the review prompt.

9. **Stage 3b — concat to final MP3 (with BGM).** Once the user signals everything is OK:

   ```bash
   source f5tts-venv/bin/activate
   python3 scripts/tts_qwen_client.py \
       --concat output/<run>/segments/ \
       --bgm "bgm/거대한 문턱.mp3" \
       --out output/<run>/audio.mp3
   ```

   **BGM + segment gap is the default final-mix behavior.** The Qwen client uses host ffmpeg (`/home/hjhj/.local/bin/ffmpeg` 7.0.2) so the fish-speech container does NOT need to be running for this step. Defaults baked into the script (calibrated 2026-05-21 for Qwen3-TTS):
   - `--segment-gap 1.0` — 1.0s silence between each pair of segments (Qwen3 natural pacing; fish-speech tier was 0.3s)
   - `--voice-tempo 1.0` — **no atempo bump** (Qwen3 emits adequate cadence natively; fish-speech tier was 1.1x)
   - `--voice-gain 1.5` to the voice, `--bgm-gain 0.1` to the BGM
   - stream-loops the BGM to cover the voice, mixes via `amix duration=first`

   Do NOT silently drop `--bgm`, change the gap, or re-introduce a tempo bump unless the user explicitly asks. If a different BGM is requested, swap the path. See [[feedback-audio-mix]].

10. **Continue to video stages.** Once audio.mp3 is on disk, run stages 4-10 below **without pausing** — no further user input is needed until video.mp4 is built. The final report at the end of stage 10 wraps up the whole run.

   **Before stage 10 (build_video.py):** restart the fish-speech container — `build_video.py` `docker exec`s into it for ffmpeg/ffprobe and the Korean fontconfig:
   ```bash
   docker compose start fish-speech
   sleep 5  # wait for boot
   ```
   The container will reload its TTS model into VRAM (~1.8GB) but that's fine because Qwen is no longer running.

## Re-running just one stage

If the user wants to redo only one stage, don't recreate the whole folder — operate inside the existing `output/<run>/`:

- **Re-do source search:** overwrite `sources.json` + re-download PDF, then re-do everything from stage 2 (downstream artifacts are stale).
- **Re-do script:** overwrite `segments.json`, then re-do stage 3a + 5-10. Don't re-run sources or PDF render.
- **Re-do specific segments only:** edit `segments.json` text or re-run with `--only N --overwrite`. Then re-do stage 3b + 10 (concat + video). Stages 4-9 stay valid.
- **Re-do concat only:** just run `--concat`. Then stage 10.
- **Re-do video only:** just stage 10. Stages 1-9 stay valid.
- **Swap stock clips:** delete `stock_clips/`, re-run stages 8-9, then stage 10.

## Stage 4 — render PDF pages

The source-finder downloaded the primary PDF into the run folder (find it via the `local_pdf_path` field in sources.json, or just glob `*.pdf` in the run dir).

### 4a — when the source is already a PDF

```bash
mkdir -p output/<run>/pdf_pages
pdftoppm -r 150 -png output/<run>/<slug>.pdf output/<run>/pdf_pages/page
```

### 4b — when the source is a web article (no PDF download)

Many recent overseas sources (news sites, blogs, Imagen Radio etc.) are HTML-only. The source-finder will leave `local_pdf_path` null but populate `url`. In that case, **print the live webpage to PDF via headless Chrome**, then run pdftoppm on the produced PDF:

```bash
URL="$(python3 -c "import json; print(json.load(open('output/<run>/sources.json'))['primary_source']['url'])")"
OUT_PDF="output/<run>/<slug>.pdf"
google-chrome --headless --disable-gpu --no-sandbox \
    --no-pdf-header-footer \
    --print-to-pdf="$(realpath -m "$OUT_PDF")" \
    --virtual-time-budget=30000 \
    --run-all-compositor-stages-before-draw \
    --hide-scrollbars \
    "$URL"
# Then render pages as in 4a:
mkdir -p output/<run>/pdf_pages
pdftoppm -r 150 -png "$OUT_PDF" output/<run>/pdf_pages/page
```

Notes:
- `google-chrome` is at `/usr/bin/google-chrome` on this host. If unavailable, fall back to `chromium` or `wkhtmltopdf` with similar flags.
- `--virtual-time-budget=30000` waits 30s of virtual page time so SPAs / lazy-loaded content render before snapshot.
- Some sites need cookie/consent click — if the resulting PDF is mostly empty, retry with `--user-data-dir=...` or with `--block-new-web-contents` or curl-rendered HTML fallback. Don't loop more than 2 retries before surfacing to the user.

### 4c — zero-pad page filenames (in both cases)

`pdftoppm` writes `page-1.png`, `page-2.png` ... `page-17.png` (NOT zero-padded by default). Always normalize via Python (bash `printf %02d` interprets `08`/`09` as bad octal):

```bash
python3 - <<'PY'
import re
from pathlib import Path
d = Path("output/<run>/pdf_pages")
for f in d.glob("page-*.png"):
    m = re.match(r"page-(\d+)\.png", f.name)
    if m:
        new = d / f"page-{int(m.group(1)):02d}.png"
        if f != new:
            f.rename(new)
PY
```

If `pdftoppm` is missing on host: `sudo apt-get install -y poppler-utils`. If `google-chrome` is missing: `sudo apt-get install -y google-chrome-stable` (after adding the official repo) or install `chromium-browser` as a drop-in.

## Stage 5 — inject `image` field per segment

Per-segment PDF page mapping. The mapping doesn't have to be chart-perfect because PDF pages only show as an overlay on female-voice segments in the final video — the visual is still dominated by the stock B-roll. **Default heuristic** (good enough for most runs):

- `intro` / `bridge` / `closing` → `page-01.png`
- `translation` and `commentary` segments walk through pages 2..N round-robin in order of appearance

```bash
python3 - <<'PY'
import json, glob, os, re
from pathlib import Path
RUN = Path("output/<run>")
pages = sorted(RUN.glob("pdf_pages/page-*.png"),
               key=lambda p: int(re.search(r"page-(\d+)", p.name).group(1)))
doc = json.loads((RUN / "segments.json").read_text())
body_pages = pages[1:] or pages  # pages 2..N for body; fallback to page 1 only
body_idx = 0
for seg in doc["segments"]:
    if seg["role"] in ("intro", "bridge", "closing"):
        img = pages[0]
    else:
        img = body_pages[body_idx % len(body_pages)]
        body_idx += 1
    seg["image"] = img.relative_to(RUN).as_posix()
(RUN / "segments.json").write_text(
    json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
print("page mapping done")
PY
```

User can override one or two mappings manually if a specific chart matches a specific translation — but don't pause to ask unless they bring it up.

## Stage 6 — subtitle normalization

Invoke the `subtitle-normalizer` agent (via `general-purpose` agent, passing the agent file path). It reads each segment's `text` (TTS-tuned, Hangul-spelled numbers/English) and writes a reader-friendly `subtitle_text` field (Arabic digits, roman alphabet acronyms). See [.claude/agents/subtitle-normalizer.md](.claude/agents/subtitle-normalizer.md).

Verify after:

```bash
python3 -c "
import json
d = json.load(open('output/<run>/segments.json'))
n_with = sum(1 for s in d['segments'] if s.get('subtitle_text'))
print(f'{n_with}/{len(d[\"segments\"])} segments have subtitle_text')
"
```

Should be N-of-N.

## Stage 7 — stock B-roll query tagging

Invoke the `stock-query-tagger` agent (same pattern). It adds an English `stock_query` field to each segment suitable for Pexels Videos search. Some segments will intentionally be left untagged (PDF chart is more informative than any stock clip). See [.claude/agents/stock-query-tagger.md](.claude/agents/stock-query-tagger.md).

## Stage 8 — fetch stock clips from Pexels

Requires `PEXELS_API_KEY` env var. The user shared a key in conversation history (search session memory) — if not present in env, ask the user to export it or pass via `--pexels-key`. (`~/.bashrc` write is blocked by the harness classifier, so the key must be exported per-session unless the user adds it manually.)

```bash
mkdir -p output/<run>/stock_clips
python3 scripts/stock_fetcher.py \
    --segments output/<run>/segments.json \
    --source pexels \
    --out output/<run>/stock_clips/ \
    --max 1 --min-duration 5
```

Some queries may return zero results from Pexels (e.g. niche industrial terms). For each such miss, retry with a generic fallback query:

```bash
python3 scripts/stock_fetcher.py --query "<fallback>" \
    --source pexels --out output/<run>/stock_clips/ --max 1 --min-duration 5
# then rename downloaded mp4 to prefix with the missing segment number
mv output/<run>/stock_clips/<fallback>_pexels_*.mp4 \
   output/<run>/stock_clips/NN_<fallback>_pexels_*.mp4
```

Manifest is written automatically. Don't worry about covering every segment — stage 9 inherits from neighbors.

## Stage 9 — inject `stock_path` per segment

Match downloaded clips back to segments by filename prefix (`NN_*.mp4` → segment N). For segments without a direct clip (untagged in stage 7, or fallback failed), inherit the previous tagged segment's clip:

```bash
python3 - <<'PY'
import json, re
from pathlib import Path
RUN = Path("output/<run>")
clip_by_n = {}
for f in sorted((RUN / "stock_clips").glob("*.mp4")):
    m = re.match(r"(\d{2})_", f.name)
    if m:
        clip_by_n[int(m.group(1))] = f.relative_to(RUN).as_posix()
doc = json.loads((RUN / "segments.json").read_text())
first = next(iter(clip_by_n.values())) if clip_by_n else None
last = None
for seg in doc["segments"]:
    n = int(seg["n"])
    if n in clip_by_n:
        last = clip_by_n[n]
    seg["stock_path"] = last if last else first
(RUN / "segments.json").write_text(
    json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"stock_path injected: {sum(1 for s in doc['segments'] if s.get('stock_path'))}/{len(doc['segments'])}")
PY
```

## Stage 10 — build the video

```bash
python3 scripts/build_video.py \
    --segments output/<run>/segments.json \
    --segments-dir output/<run>/segments/ \
    --audio output/<run>/audio.mp3 \
    --out output/<run>/video.mp4
```

`build_video.py` auto-detects stock mode when every segment has a `stock_path` field. It:
- builds per-segment intermediate clips (stock bg looped + crop-fill 1920x1080)
- overlays the PDF page (`image` field) on the right side **only for female-voice segments**
- concats segments with concat demuxer
- mux's `audio.mp3` + burns subtitles via libass (yellow for female, white for male)
- ensures the Korean font is in the Docker container's fontconfig (idempotent)

Subtitle timing assumes the audio was rendered with the standard `--voice-tempo 1.1 --segment-gap 0.3`. If overridden in stage 3b, pass the same values here via `--voice-tempo` / `--segment-gap`.

Verify with a frame extraction from a female-voice segment (should show PDF overlay) and a male-voice segment (should be full-screen stock):

```bash
docker exec autotube-fish-speech ffmpeg -y \
    -i /home/hjhj/autotube/output/<run>/video.mp4 \
    -ss <t-male> -frames:v 1 \
    /home/hjhj/autotube/output/<run>/_frame_male.png
docker exec autotube-fish-speech ffmpeg -y \
    -i /home/hjhj/autotube/output/<run>/video.mp4 \
    -ss <t-female> -frames:v 1 \
    /home/hjhj/autotube/output/<run>/_frame_female.png
```

Read both PNGs to confirm the layout. Don't pause for user approval — just confirm it looks right and report.

## Stage 11 — YouTube thumbnail (spec → render)

After video.mp4 is on disk, generate the YouTube thumbnail. Two sub-steps. **No user pause** — runs straight through.

> **Design 컨벤션 (2026-05-22 바이스톰/쓸모왕 실제 썸네일 분석 후 강제 — `layout: "sandwich"` 가 default):**
>
> 바이스톰 코리아 (380K) + 쓸모왕 (781K) 의 실제 썸네일을 다운로드해서 분석한 결과, 두 채널 모두 **수직 3분할 샌드위치 구조** 를 쓴다:
> - **상단 32% 검정 띠** — 따옴표로 시작하는 큰 텍스트 2줄
> - **중간 36% imagery 영역** — 가운데 stock frame + 좌측 작은 빨간 "외신특보" 라벨 + 우측 face cutout(들)
> - **하단 32% 검정 띠** — reveal 텍스트 2줄
>
> 옛 face-overlay 레이아웃 (`face-overlay` — 가운데 큰 헤드라인 + 우측 face) 은 retain 하되 **default 는 sandwich 로 전환**. face-overlay 는 backward compatibility / 디자인 실험용으로만.
>
> sandwich 모드에선 **태극기 코너 아이콘과 "파이널K" wordmark 는 기본 false** (경쟁 채널들이 안 씀 — 텍스트 띠와 충돌). 채널 정체성은 텍스트 톤과 권위 라벨로 표현.
>
> 분석 보고서: `research/competitor_thumbnails_2026-05-21.md` (v1 → v2 face-overlay 분석), `research/headline_patterns_2026-05-22.md` (헤드라인 카피), `research/headline_patterns_bystorm_ssulmowang_2026-05-22.md` (sandwich 레이아웃 + 9개 카피 패턴).

> **헤드라인 카피 컨벤션 (2026-05-22 바이스톰 코리아 + 쓸모왕 패턴 적용):** 국뽕 commentary 정점 두 채널 (바이스톰 380K, 쓸모왕 781K) 의 제목 작법은 다음 9개 패턴으로 환원된다. 분석: `research/headline_patterns_bystorm_ssulmowang_2026-05-22.md`.
>
> **YouTube 제목 (long form) 3마디 구조:**
> `[인용/사건 1마디] + [세계/자국 반응 1마디] + [reveal 명사 1마디]`
>
> 예 (트라이얼 v4 적용본): `직장 버리고 한국行 택해버린 日 여성들, 자국 명문대 교수가 논문으로 직접 폭로한 충격적 진짜 이유`
> = [직장 버리고 한국行 택해버린 日 여성들] + [자국 명문대 교수가 논문으로 직접 폭로한] + [충격적 진짜 이유]
>
> **필수 패턴:**
> 1. **인용 prefix** — 따옴표로 영상 시작 (`"한국이 또 미친걸 공개했다" ...`)
> 2. **~버린/~깨부순/폭로한** — 완료 동사 어미 (`눈치채버린`, `되갚아버린`, `폭로해버렸다`). 단순 과거 "했다" 보다 훨씬 강함.
> 3. **한자 single-char** — `韓`, `美`, `日`, `中`, `한국行`. 한글 사이 시각 anchor.
> 4. **reveal 명사로 종료** — `이유`, `실제 상황`, `정체`, `광경`, `비밀`, `반격`. 동사로 끝내지 말 것.
> 5. **숫자 = 권위** — `66.2%`, `8억 전세계 팬덤`. 막연한 "많이" 금지.
> 6. **결국/드디어/현재/이제** — 시간성 부여 marker.
> 7. **세계 반응 동사** — 한국 = 행위자, 세계 = 반응자 (`전세계 매체들 난리났다`, `美 도시전체 풍경을 바꿔버리자`).
> 8. **자국 비판 hook** (일본/중국 영상 특화) — `일본이 제발 멈춰달라고한`, `자국 학자가 폭로한`. 비판자가 자국 본인이라는 인지부조화.
>
> **썸네일 텍스트 (2줄 short form):**
> - 노란 강조어는 **의미 단위 2-4글자** (`한국行`, `진짜 이유`, `폭로`, `66.2%`)
> - 1글자 거대 강조 (`왜?`) 와 `충격/발칵/경악` 단독은 **금지**
> - 한자 single-char (`日`, `美`) 적극 활용 — 시각 가중치 + 한 글자에 의미 압축
> - 두 줄 모두 hook 이 있어야 함 (한 줄만 강하면 약함)

> **권위 라벨 컨벤션 (2026-05-22 한국 시청자 가독성 반영):**
> - **한국어가 default.** 영어 단독은 한국인이 못 알아봄. (`"Itoi · Korea Journal 2026"` → ✗)
> - **포맷:** `[대학명/매체명] + [직함] + [형식]` — 예: `리츠메이칸大 교수 논문 심층분석`, `NYT 보도 한국 분석`, `옥스포드 교수 인용`, `BBC 다큐 심층분석`.
> - **영문은 1-2 글자 acronym 만 허용** (`NYT`, `BBC`, `WSJ` 처럼 한국인도 즉시 인식 가능한 것).
> - **한자 혼용 OK** — `리츠메이칸大`, `日 학자`, `美 교수`. 가독성 + 시각 가중치 둘 다 좋다.
> - **국기:** 저자/매체 국가의 작은 국기를 라벨 박스 좌측에 끼워넣어 (`label.flag: "JP"` 등) 출처 시그널을 강화한다.
> - **font_size:** default 36. 텍스트가 12자 이상이면 38-42 정도로 *키워서* 가독성 보강 (작게 줄이지 말 것 — 한국 시청자가 못 알아본다는 게 더 큰 손실).

### 11a — Build the spec

읽기 좋은 brief 는 선택사항. 핵심은 spec.json — `build_thumbnail.py` 가 직접 소비하는 contract. 다음 입력에서 자동 생성 가능:

- `youtube.title` (영상 제목) → 2줄로 분할 (auto_split_lines 가 해줌)
- 영상의 핵심 키워드 1-2개 (정치적 임팩트가 큰 단어, 예: "한국", "충격", "1위", "진짜") → accent_words
- 영상 angle → label 선택:
  - 학술 논문 기반 → `"심층분석"` 또는 `"해외 학계"`
  - 통계/조사 → `"1차자료"`
  - 뉴스 기반 → `"실제기사"` 또는 `"최신뉴스"`
  - 외국인 반응/리액션 → `"해외반응"`
- 사용 가능한 stock clip 중에서:
  - **배경**: 영상 주제와 가장 직결되는 광경 (예: 일본 도시 영상이면 도쿄 거리)
  - **face**: 사람이 가깝게 잡힌 클립 (예: 공항 여성, 인터뷰 얼굴). `manifest.json` 의 search query 가 "people" "face" "woman" "man" 키워드 포함하면 face 클립 후보. **사람이 없는 클립은 face 로 쓰지 말 것** — 결과가 어색해진다.

### 11b — spec.json 작성

`output/<run>/thumbnail_spec.json` — 풀 스키마 (모든 필드 optional):

```json
{
  "background": {
    "type": "stock",
    "stock_path": "stock_clips/04_japanese-young-women-city_pexels_1_8829018.mp4",
    "t": 2.5,
    "darken": 0.5,
    "bottom_band_alpha": 230,
    "bottom_band_start": 0.32
  },
  "face": {
    "clip": "stock_clips/14_young-woman-luggage-airport-travel_pexels_1_8044820.mp4",
    "t": 2.0,
    "size": 360,
    "position": "right"
  },
  "text_lines": ["직장 버리고 한국行", "日 여성들 진짜 이유"],
  "accent_words": ["한국行", "진짜 이유"],
  "accent_color_hex": "#FFD600",
  "base_text_color_hex": "#FFFFFF",
  "stroke_color_hex": "#000000",
  "stroke_width": 14,
  "text_band": {
    "fill_hex": "#000000",
    "alpha": 180,
    "pad_x": 28,
    "pad_y": 8
  },
  "label": {
    "text": "리츠메이칸大 교수 논문 심층분석",
    "fill_hex": "#DC2626",
    "text_color_hex": "#FFFFFF",
    "font_size": 42,
    "flag": "JP"
  },
  "accent_punct": {
    "text": "?!",
    "color_hex": "#FFD600",
    "rotate": -8,
    "size": 170,
    "position": "right"
  },
  "show_flag": true,
  "flag_position": "bottom-left",
  "show_wordmark": true,
  "wordmark_badge": true,
  "wordmark_position": "bottom-right"
}
```

**Field 시맨틱:**

| 필드 | 효과 | 기본값 |
|------|------|--------|
| `layout` | `"sandwich"` (바이스톰/쓸모왕 패턴, default) / `"face-overlay"` (옛 v2-v4) | `"face-overlay"` |
| `top_text_lines` | sandwich 모드 상단 띠 텍스트 (1-2줄) | `[]` |
| `bottom_text_lines` | sandwich 모드 하단 띠 텍스트 (1-2줄) | `[]` |
| `top_band_frac` | sandwich 상단 띠 높이 비율 | `0.32` |
| `bottom_band_frac` | sandwich 하단 띠 높이 비율 | `0.32` |
| `sandwich_band_alpha` | sandwich 상/하단 검정 띠 alpha | `215` |
| `sandwich_band_fill_hex` | sandwich 띠 색 | `#000000` |
| `background.type` | `"stock"` / `"split"` / `"gradient"` / `"solid"` | `"stock"` |
| `background.stock_path` | 배경에 쓸 stock clip 의 경로 (run dir 기준 상대) | segments.json 의 첫 stock_path 자동 픽 |
| `background.t` | 프레임 추출 시점 (초) | 2.0 |
| `background.darken` | 0..1 배경 어둡기 | 0.40 |
| `background.bottom_band_alpha` | 하단 검정 그라데이션 띠 최종 alpha (0-255) | 220 |
| `background.bottom_band_start` | 하단 띠 시작점 (frac of H) | 0.42 |
| `background.left_path`, `right_path` | type=split 일 때 좌/우 클립 | — |
| `background.left_t`, `right_t` | 좌/우 프레임 추출 시점 | 2.0 |
| `background.left_flag`, `right_flag` | type=split 일 때 반투명 국기 워터마크 (`"KR"` / `"JP"`) | — |
| `background.show_vs` | type=split 일 때 가운데 "VS" 글자 | true |
| `face.clip` | 얼굴 컷아웃에 쓸 클립 (run dir 기준 상대) | — (없으면 face 안 그림) |
| `face.t` | 프레임 추출 시점 (초) | 2.0 |
| `face.size` | 컷아웃 정사각 크기 (px) | 360 |
| `face.position` | `"right"` / `"left"` / `"center"` | `"right"` |
| `text_lines` | 2줄 텍스트 배열 (각 줄 한국어 5-12자) | youtube.title 자동 2분할 |
| `accent_words` | 노란색으로 칠할 단어 / 부분 문자열 리스트 | `[]` |
| `accent_color_hex` | 강조어 색 | `#FFDC00` |
| `base_text_color_hex` | 기본 텍스트 색 | `#FFFFFF` |
| `stroke_color_hex`, `stroke_width` | 텍스트 외곽선 | 검정, 12px |
| `text_band` | 텍스트 줄 뒤 반투명 박스 (true / false / object) | true (가독성 보장) |
| `text_band.fill_hex`, `alpha`, `pad_x`, `pad_y` | text_band 디테일 | 검정, 170, 28, 8 |
| `label` | 좌상단 권위 라벨 (string or object) | none |
| `label.text`, `fill_hex`, `text_color_hex` | label 디테일 | "...", `#DC2626`, `#FFFFFF` |
| `label.flag` | 라벨 박스 안 좌측 작은 국기 — **저자 또는 출처 국가**. `"JP"` / `"KR"` | none |
| `label.font_size` | 라벨 글자 크기. **줄이지 말 것** — 한국어 라벨이 길어도 36-42 유지 (시청자가 못 알아보면 손실이 더 크다). 12자 이상이면 38-42. | 36 |
| `accent_punct` | 회전 ?! sticker (string or object) | none |
| `accent_punct.text`, `color_hex`, `rotate`, `size`, `position` | punct 디테일 | "?!", yellow, -8, 160, "right" |
| `show_flag` | 작은 코너 태극기 | true |
| `flag_position` | `"top-left"` / `"bottom-left"` / `"top-right"` / `"bottom-right"` | `"bottom-left"` |
| `show_wordmark` | "파이널K" 표시 | true |
| `wordmark_badge` | true 면 둥근 배지 (검정+노란+흰테), false 면 글자만 | true |
| `wordmark_position` | 4-corner 중 하나 | `"bottom-right"` |

`_brief_source` 와 `_notes` 는 렌더러가 무시 — traceability 용으로 남겨두는 메타데이터.

### 11c — Render

```bash
python3 scripts/build_thumbnail.py \
    --segments output/<run>/segments.json \
    --spec output/<run>/thumbnail_spec.json \
    --out output/<run>/thumbnail.png
```

1280x720 PNG 생성됨. Read tool 로 inline 확인 — 다음 체크리스트:

1. 좌상단 라벨이 잘리거나 다른 요소와 안 겹치는가
2. 텍스트 2줄이 검정 띠 위에서 또렷한가 (모바일 168x94 에서도 읽혀야 함)
3. 노란 강조어가 의도된 단어인가 (substring match 라 "한국" 이 "한국行" 도 잡음)
4. face cutout 이 텍스트를 가리지 않는가 (자동 layout 이 max_text_w 를 줄여줌)
5. ?! sticker 가 face 위쪽에 있고 텍스트와 분리됐는가
6. 좌하단 태극기가 작고 (3-5% 영역), face 와 안 겹치는가
7. 우하단 "파이널K" 배지가 깔끔하게 자리잡았는가

### 비교 영상 (한일/한미/Before-After) 변형 — split bg

split 모드 — 좌우 두 stock 사진 + 슬랜티드 디바이더 + 양쪽 반투명 국기:

```json
{
  "background": {
    "type": "split",
    "left_path": "stock_clips/03_japan-tokyo-youth-street_pexels_*.mp4",
    "right_path": "stock_clips/13_seoul-gangnam-street-couple-walking_pexels_*.mp4",
    "left_flag": "JP",
    "right_flag": "KR",
    "show_vs": true,
    "darken": 0.45
  },
  "text_lines": ["같은 20대인데", "결과는 정반대"],
  "accent_words": ["20대", "정반대"],
  "label": "한일 비교",
  "show_flag": false
}
```

(split 모드에선 양쪽 반투명 국기가 이미 있으므로 작은 코너 태극기는 끄는 게 깔끔.)

### Re-runs

- **Spec tweak only**: edit `thumbnail_spec.json` 직접, 11c 만 재실행.
- **다른 face 클립으로 교체**: `face.clip` 만 바꾸고 11c.
- **stock_path 변경**: `background.stock_path` 만 바꾸고 11c.
- **Skip 11 entirely**: pipeline 의 다른 stage 는 thumbnail 을 소비하지 않음. 11 안 해도 영상은 valid.

### Backward compatibility

`build_thumbnail.py` 를 `--spec` 없이 부르면 legacy path 동작 — segments.json 의 `youtube.thumbnail_copy` 를 자동 2줄 분할해서 새 디자인 컨벤션 (stock bg + 검정 띠 + 작은 태극기 + 워드마크 배지) 으로 렌더. 옛 그라데이션 fallback 은 stock clip 이 하나도 없을 때만.

## Stage 12 — YouTube 자동 업로드

Stage 11 까지 끝나면 `output/<run>/` 에 `video.mp4`, `thumbnail.png`, `segments.json` (`youtube.*` 메타) 셋이 다 있음. 이걸로 즉시 업로드 가능.

> **1회 OAuth 셋업이 사용자 직접 액션 필요.** 가이드: `scripts/README_youtube_oauth.md` (Google Cloud Console → YouTube Data API v3 활성화 → Desktop app OAuth → client_secret.json 을 `~/.config/autotube/` 에 배치). 5-10분, 영구, 무료. 셋업 전이라면 사용자에게 안내하고 stage 12 는 skip.

### 12a — Dry-run preview (필수)

자동 업로드 직전, 무조건 dry-run 으로 메타데이터 preview 출력. 사용자가 confirm 한 다음에만 실제 업로드.

```bash
python3 scripts/youtube_upload.py --run output/<run>/ --dry-run
```

출력: title (길이), privacy, category, tags, description preview (200자). 잘못된 메타데이터 (TTS-tuned 한글 숫자 등) 발견하면 사용자에게 fix 권유.

### 12b — Upload

```bash
python3 scripts/youtube_upload.py --run output/<run>/
```

기본값:
- `--privacy unlisted` — URL 알아야만 접근. 사용자가 Studio 에서 검수 후 공개로 전환.
- `--category-id 22` — People & Blogs (commentary 채널 표준). News & Politics (25) 는 자동 분류 위험이 있어 회피.
- `defaultLanguage / defaultAudioLanguage = "ko"`
- `selfDeclaredMadeForKids = false`
- Thumbnail 도 자동 첨부 (verified 채널 한정 — 안 되면 video upload 는 성공하고 thumbnail 만 skip).

사용자가 명시적으로 `--public` 옵션 주면 즉시 공개. **autotube 의 default 는 항상 unlisted** — 자동 공개는 사용자가 매번 의도해야 함.

업로드 후 `output/<run>/upload_result.json` 에 video_id, URL, studio_url, privacy 저장.

### 12c — Final report

업로드 성공 후 final report 에 추가:
- `videoId` 와 `https://www.youtube.com/watch?v=<id>` URL
- `https://studio.youtube.com/video/<id>/edit` Studio 링크 (사용자가 공개 전환할 때 필요)
- thumbnail 첨부 성공/실패
- privacy 상태 (unlisted 면 "검수 후 Studio 에서 공개로 전환" 안내 멘트 같이)

### 한도

- 일일 quota: 10,000 units → 업로드 1건 1,600 units → **하루 최대 6개**. quota_exceeded 떨어지면 다음 날 자정 (Pacific Time) 초기화.
- 신생 채널 보호: 채널 첫 영상은 YouTube 가 1일 내외로 검토할 수도. unlisted 라서 검토 중에도 사용자 본인은 미리보기 가능.

### 알려진 이슈

- **description 의 TTS-tuned 한글 숫자** — `kpop-script-writer` 가 youtube.description 까지 TTS 톤으로 만들면 ("이천이십육년 삼월", "육십육점이 퍼센트") YouTube 에 그대로 노출됨. 정확하게는 subtitle-normalizer agent 가 segment 단위에만 normalize 하므로 description 은 별도 normalize 필요. 현재는 dry-run preview 에서 발견되면 사용자가 수동 수정.

## Final report

After stage 10, print:
- Run folder path
- Primary source: title + publisher + date
- Segment count + role breakdown
- Stock clips downloaded / inherited
- Final video path + duration + size
- YouTube title (from `youtube.title`)
- Description preview (first 150 chars of `youtube.description`)
- Hashtags
- Any segments regenerated during the review gate

## What this skill does NOT do

- ~~Upload to YouTube.~~ → Stage 12 로 추가됨 (2026-05-22). 단, OAuth 1회 셋업은 사용자 직접 액션.
- Sources older than 2026-01-01.
- Per-segment B-roll cut-between-clips (current mode is one stock clip per segment, looped).
- Chart/figure auto-extraction from PDF (the whole page is overlaid for female segments — good enough).
- Ken-burns / camera moves.
- Intro/outro stings.

If the user asks for any of these, say it's out of scope for now.
