---
name: mexico-pipeline
description: Use this skill to run the full MX (멕시코뽕) pipeline end-to-end — find a Korean YouTube video that praises/cheers Mexico, fetch its real top comments via the YouTube Data API, write a SPANISH dual-voice script (Korean-original cards + Spanish dub/subtitles), generate Qwen3-TTS Spanish per-segment MP3s for review, concat with BGM, render YouTube-style Korean comment cards, build a 1920x1080 video with the THUMBNAIL inserted as the first frame (intro background), and produce the YouTube thumbnail. Targets a separate Mexican-audience channel. Orchestrates mx-source-finder + mx-script-writer agents and the Qwen TTS client. Invoke when the user says "멕시코 영상 만들어줘", "멕시코뽕 영상", "MX 영상", or wants a Korean-reaction-for-Mexico video. Upload is deferred (channel not ready) — stop after video.mp4 + thumbnail.png.
---

# mexico-pipeline — end-to-end 멕시코뽕 video (Spanish dub, Korean cards)

> **이 스킬은 오케스트레이터다. 도메인 정본은 [docs/mexico-reaction-format.md](../../../docs/mexico-reaction-format.md).**
> 공통 인프라(아키텍처/TTS믹스/자막싱크/썸네일스키마)는 V3 와 공유 → [docs/architecture.md](../../../docs/architecture.md) ·
> [docs/tts.md](../../../docs/tts.md) · [docs/thumbnail-conventions.md](../../../docs/thumbnail-conventions.md).

V3 의 거울 형식. 방향이 반대다: **한국 인터넷 반응 → 멕시코인 자긍심**, 스페인어 더빙/자막.
사람이 멈추는 곳은 **딱 한 곳**: 세그먼트 MP3 검수(stage 3a 후). 나머지는 자동.

## Stages

```
[1]   mx-source-finder agent     →  sources.json + video_thumb.jpg
[2]   mx-script-writer agent      →  segments.json + script_notes.md  (모든 text = 스페인어)
[3a]  Qwen3-TTS Spanish 합성       →  segments/*.mp3   [검수 게이트 — 유일한 정지]
[3b]  concat + BGM                →  audio.mp3
[4]   (PDF skip)
[5]   build_mx_cards.py + 카드매핑 →  video/video-card.png, comments/comment-NN.png + segments.json image 필드
[6]   (subtitle-normalizer skip — text 이미 깔끔한 스페인어)
[7]   stock-query-tagger (male segs only) → segments.json stock_query
[8]   stock_fetcher.py (Pexels)   →  stock_clips/*.mp4
[9]   stock-path 주입 (male segs) →  segments.json stock_path
[11]  썸네일 먼저!  thumbnail.png  →  intro.bg_image = "thumbnail.png" 주입
[10]  build_video.py              →  video.mp4   (썸네일이 첫 프레임/intro 배경)
```

> **순서 핵심:** 썸네일(11)을 build_video(10) **전에** 만든다 — intro 배경으로 들어가야 하므로.
> **업로드(12) 없음** — 멕시코 채널/전화번호 인증 준비 후 별도 진행. 지금은 video.mp4 + thumbnail.png 까지.

## Run folder
`output/<YYYY-MM-DD>-<topic-slug>-mx-<n>/` (예: `2026-06-20-mexico-korea-love-mx-1`).
sources.json · video_thumb.jpg · segments.json · script_notes.md · segments/ · audio.mp3 ·
video/video-card.png · comments/comment-NN.png · stock_clips/ · thumbnail.png · video.mp4.

## Workflow

1. **토픽 확인(간단).** 사용자가 angle 주면 그걸로. 막연하면 "한국-멕시코 우정/한국인의 멕시코 칭찬" 디폴트.

2. **보이스 확인.** 기존 한국어 ref 로 크로스링구얼 스페인어 합성(1차 결정):
   ```bash
   ls voices/male_voice/ref.wav voices/male_voice/ref.txt voices/female_voice/ref.wav voices/female_voice/ref.txt
   ```

3. **run 폴더 생성.**

4. **Stage 1 — mx-source-finder agent.** 전달: topic, output `output/<run>/sources.json`, real-data-only 룰, 썸네일을 `output/<run>/video_thumb.jpg` 로 다운로드. 완료 후 검증:
   ```bash
   python3 -c "import json;d=json.load(open('output/<run>/sources.json'));print('video:',d['video']['title_ko']);print('comments:',len(d['comments']))"
   ls -la output/<run>/video_thumb.jpg
   ```
   댓글 8개 미만이거나 thumb 없으면 사용자에 보고.

5. **Stage 2 — mx-script-writer agent.** 전달: sources_path, output segments/notes 경로. 검증:
   ```bash
   python3 -c "import json;d=json.load(open('output/<run>/segments.json'));segs=d['segments'];import collections;print(len(segs),dict(collections.Counter(s['role'] for s in segs)));print('langs:',set(s.get('language') for s in segs))"
   ```
   기대: intro1·bridge1·post_body1·comment_translation N·closing1, **모든 language=Spanish**. intro 스페인어 문장 보여주고 confirm.

6. **Stage 3a — edge-tts 멕시코 Spanish.** **GPU 불필요** (온라인 엔드포인트). fish-speech 안 멈춰도 됨.
   ```bash
   source f5tts-venv/bin/activate
   pip install edge-tts  # 한 번만
   python3 scripts/tts_edge_client.py \
     --segments output/<run>/segments.json \
     --segments-out-dir output/<run>/segments/
   # male→es-MX-JorgeNeural, female→es-MX-DaliaNeural. NN_role_voice.mp3 출력(Qwen 과 동일 포맷).
   ```
   ⚠️ **Qwen 크로스링구얼은 폐기됨** (억양 어색, 사용자 거부 2026-06-20). edge-tts 가 정본.
   **첫 회차는 `--only 1 5`로 male/female 1개씩 먼저 뽑아** 억양 확인 후 전체.

7. **검수 게이트.** MP3 리스트 + 텍스트 미리보기 출력. 사용자가 재합성할 번호 주면 `--only N --overwrite`. 다 OK → "합치자".

8. **Stage 3b — concat + BGM.**
   ```bash
   source f5tts-venv/bin/activate
   python3 scripts/tts_qwen_client.py --concat output/<run>/segments/ --bgm "bgm/거대한 문턱.mp3" --out output/<run>/audio.mp3
   ```

9. **Stage 5 — 카드 렌더 + 매핑.**
   ```bash
   python3 scripts/build_mx_cards.py output/<run>/
   ```
   그다음 segments.json 에 image 필드 주입(스크립트라이터가 이미 넣었으면 검증만):
   - post_body 세그 → `post_image = "video/video-card.png"`
   - comment_translation 세그(순서대로) → `comment_image = "comments/comment-NN.png"`
   매핑 확인:
   ```bash
   python3 -c "import json;d=json.load(open('output/<run>/segments.json'));
   miss=[s['n'] for s in d['segments'] if s['role']=='comment_translation' and not s.get('comment_image')];print('missing comment_image:',miss)"
   ```

10. **Stage 7-9 — 다이내믹 모션 배경 (정식, 2026-06-21).** 풀스크린 정적 카드 = 슬라이드쇼 → 사용자 거부. 대신 **모든 세그먼트(intro 제외)에 움직이는 스톡 영상 배경 + 떠있는 카드 패널**.
    - **Pexels 키**: `~/.config/autotube/pexels_api_key.txt` (영구 저장됨). `KEY=$(cat ~/.config/autotube/pexels_api_key.txt)`. (Pixabay 도 가능: `stock_fetcher.py --source pixabay --pixabay-key ...`.)
    - 관련 클립 fetch (멕시코 팬/축하/경기장/국기/불꽃):
      ```bash
      for q in "mexican football fans celebrating" "mexico flag crowd" "soccer fans stadium cheering" "world cup celebration crowd" "fireworks crowd night"; do
        python3 scripts/stock_fetcher.py --query "$q" --source pexels --pexels-key "$KEY" --out output/<run>/stock_clips/ --max 2 --min-duration 6
      done
      ```
    - 각 세그먼트에 `motion_bg`(stock_clips/*.mp4) 배정 — comment/video=축하 클립, commentary/bridge=경기장, closing=불꽃. intro 는 motion 없이 썸네일 첫프레임 유지.
    - 카드는 `build_mx_cards.py` 가 자동으로 **떠있는 패널**(둥근모서리+그림자+투명마진)로 렌더 → build_video 가 motion_bg 위에 합성. (`MX_FLAT=1` 이면 레거시 풀스크린.)
    - build_video 로그에 **"N with motion bg (MX dynamic)"** 떠야 정상.

> ⚠️ **MX 썸네일 = 영상 첫 프레임 (정식 방식, 사용자 확정 2026-06-21).** MexiKorea 채널이 **전화번호 미인증**이라 커스텀 썸네일 업로드가 항상 403. 그래서 **별도 썸네일 업로드 안 함** — 대신 "좋은 썸네일 디자인"을 만들어 **intro 의 첫 프레임(bg_image)** 으로 넣어 유튜브 자동 썸네일이 그 화면을 잡게 한다. → 썸네일 디자인은 [docs/mexico-title-thumbnail-conventions.md](../../../docs/mexico-title-thumbnail-conventions.md) 의 4요소(큰2-4단어+노란강조+**감정표정얼굴**+키커)를 그대로 적용. 채널 인증 풀리면 그때부터 커스텀 업로드 가능.

11. **Stage 11 — 썸네일 먼저 (= 첫 프레임 디자인).** 멕시코 톤 카피로 `thumbnail_spec.json` 작성 → 렌더:
    ```bash
    python3 scripts/build_thumbnail.py --segments output/<run>/segments.json --spec output/<run>/thumbnail_spec.json --out output/<run>/thumbnail.png
    ```
    카피는 스페인어(예: 상단 "Los coreanos quedaron en shock", 강조 "México"). 국기 KR/MX 양옆. (build_thumbnail label.flag 는 KR/JP 만 허용하니 MX 국기는 flag 아닌 이미지로 처리하거나 라벨 생략.)
    렌더 후 Read 로 확인.

12. **intro 에 썸네일 주입.**
    ```bash
    python3 -c "import json,os;p='output/<run>/segments.json';d=json.load(open(p));
    [s.__setitem__('bg_image','thumbnail.png') for s in d['segments'] if s['role']=='intro'];
    json.dump(d,open(p,'w'),ensure_ascii=False,indent=2)"
    ```
    (썸네일이 run 폴더 루트에 thumbnail.png 로 있어야 함. build_video 가 `run_dir/bg_image` 로 resolve.)

13. **Stage 10 — build_video.**
    ⚠️ **빌드 전 필수 가드** — 모든 세그먼트가 비주얼을 갖는지 검사(없으면 build_video 가 단색 타이틀카드 폴백으로 빠져 영상이 망가짐, 2026-06-20 실측). male 연결 세그(bridge/transition/commentary/closing)에 비주얼 없으면 `male_backdrop.png` 자동 주입:
    ```bash
    python3 - <<'PY'
    import json
    p="output/<run>/segments.json"; d=json.load(open(p)); react={'reaction_translation','post_body','comment_translation'}
    fixed=[]
    for s in d["segments"]:
        has_vis = s.get('bg_image') or s.get('post_image') or s.get('comment_image') or s.get('stock_path')
        if not has_vis:
            s['bg_image']='male_backdrop.png'; fixed.append(s['n'])
    json.dump(d,open(p,'w'),ensure_ascii=False,indent=2); print('auto-fixed bg_image:',fixed or 'none')
    PY
    ```
    그리고 build_video 로그에 **"Stock-clip mode: N segments"** 가 떠야 정상(안 뜨고 "title card" 면 폴백 — 위 가드 누락).
    **build_video 는 이제 host ffmpeg 로 돈다 — fish-speech docker 불필요(2026-06-21 GPU OOM 때문에 제거).**
    ```bash
    python3 scripts/build_video.py \
      --segments output/<run>/segments.json --segments-dir output/<run>/segments/ \
      --audio output/<run>/audio.mp3 --out output/<run>/video.mp4 \
      --voice-tempo 1.0 --segment-gap <effective_gap>
    ```
    effective_gap = (audio.mp3 길이 − Σ segments/*.mp3 길이)/(세그수−1). 빌드 후 video.mp4 ↔ audio.mp3 ±0.2s 확인.
    프레임 추출로 검증: 시작(intro)=썸네일 풀스크린, video_card=영상카드, comment=댓글카드(여, 노랑 자막), male=stock+캐릭터.

14. **Final report.** run 경로 · 영상/채널/조회수 · 세그먼트수 · 댓글수 · video.mp4 길이/크기 · youtube.title(ES) · "업로드는 채널 준비 후" 안내.

## 재실행
gukppong-pipeline "Re-running just one stage" 패턴과 동일. 카드만 다시: build_mx_cards.py 재실행 → stage 10. 썸네일만: spec edit → build_thumbnail → intro bg_image 그대로 → stage 10.

## Stage 12 — 업로드 (MexiKorea 채널, 검증됨)

> **채널 = MexiKorea** (재활용 채널 id UC3PYm67mgOWcq3kYDquSqEA, 구독5, **전화번호 인증됨 → 커스텀 썸네일 OK**).
> 토큰 = **`~/.config/autotube/token_mxmain.json`**. ⚠️ `token.json` 기본값은 파이널K 라 멕시코 업로드는 반드시 `--token-file` 명시.
> (`token_mexikorea.json` 는 폐기된 첫 신규 채널 — 계정 삭제됨, 쓰지 말 것.)

```bash
source f5tts-venv/bin/activate
TK=~/.config/autotube/token_mxmain.json
python3 scripts/youtube_upload.py --run output/<run>/ --dry-run --token-file $TK --lang es-MX
# confirm 후
python3 scripts/youtube_upload.py --run output/<run>/ --privacy unlisted --token-file $TK --lang es-MX
```
- `--lang es-MX` 필수. 카테고리 22. **커스텀 썸네일 thumbnail.png 자동 첨부됨**(검증 채널이라 403 안 남).
- 새 채널 OAuth: ① OAuth consent(프로젝트 autotube-497103) "테스트 사용자"에 그 계정 이메일 추가 → ② `python3 scripts/youtube_auth_channel.py --token <경로>` (브라우저, 채널 확인).

## 이 스킬이 안 하는 것
- 에펨/더쿠/인스티즈 자동 fetch(Cloudflare — 사용자 스크린샷 제공 시 별도). 2026-01-01 룰은 MX 엔 미적용(유튜브 댓글은 최신성보다 따뜻함 우선).
