# Architecture — autotube

> autotube의 **system of record**. 이 문서가 파이프라인 구조의 정본이다.
> 스테이지별 실행 명령은 [pipeline-stages.md](pipeline-stages.md), 도메인 컨벤션은 같은 폴더의
> `tts.md` / `script-conventions.md` / `thumbnail-conventions.md` / `operations.md` 참고.

## 한 줄 정의

해외(비-한국) K-culture/경제 자료 **한 편**을 깊게 파서, 한국어 듀얼보이스(번역자 여성 + 사설가 남성)
스크립트 → TTS MP3 → stock B-roll + PDF overlay + 자막 burn-in 영상 → 썸네일 → YouTube 업로드까지
자동 생성하는 **회차 반복형 국뽕 콘텐츠 파이프라인** (채널명: 파이널K).

## 선택한 패턴과 근거

`foundry-harness/patterns/` 어휘로:

| 패턴 | 어디에 | 근거 |
|---|---|---|
| **pipeline** (주) | 12스테이지 선형 DAG, 각 단계 산출물이 다음 입력 | 작업이 선형이고 단계 경계가 명확 (헌법 제2원칙 — 가장 단순한 안) |
| **expert-pool** | 4개 도메인 에이전트 (source-finder / script-writer / subtitle-normalizer / stock-query-tagger) | 단계마다 요구 전문성이 이질적 |
| **generate-validate** | 단일 리뷰 게이트(세그먼트 MP3 검수) + dry-run(업로드) + 프레임 검증(영상) + `run_check.py` | 품질 중요, 생성↔검증 분리 (헌법 제6원칙) |

**불채택:** `supervisor`/`hierarchical` — 선형이고 장기 자율 작업 보드가 없음. 복잡 패턴은 단순안 실패
근거가 있을 때만(헌법 제2원칙). `learning.md`의 `[skipped]` 참고.

## 12-스테이지 DAG

```
[1]  kpop-source-finder agent   →  sources.json + <slug>.pdf       (2026+ 해외 1차 문서)
[2]  kpop-script-writer agent   →  segments.json + script_notes.md (듀얼보이스 11–17 세그먼트)
[3a] tts_qwen_client --segments →  segments/NN_role_voice.mp3
   ── ★ 단 하나의 사용자 게이트: 세그먼트 MP3 검수 ("합치자" 신호 대기) ──
[3b] tts_qwen_client --concat   →  audio.mp3                        (voice + BGM 믹스)
[4]  pdftoppm / web→PDF 폴백     →  pdf_pages/page-NN.png
[5]  page-map 주입 (ink-density) →  segments.json .image
[6]  subtitle-normalizer agent  →  segments.json .subtitle_text
[7]  stock-query-tagger agent   →  segments.json .stock_query
[8]  stock_fetcher.py (Pexels)  →  stock_clips/*.mp4 + manifest.json
[9]  stock-path 주입            →  segments.json .stock_path
[10] build_video.py (stock 모드) →  video.mp4
[11] thumbnail spec → build_thumbnail.py → thumbnail.png
[12] youtube_upload.py (dry-run → upload) → upload_result.json
```

스테이지 3a 후 한 번만 멈춘다(MP3 검수). "합치자" 떨어지면 3b→11은 사용자 입력 없이 진행.
12(업로드)는 dry-run preview 후 사용자 confirm 필요. 오케스트레이션은 `gukppong-pipeline` skill.

## run 폴더 규약

```
output/<YYYY-MM-DD>-<topic-slug>/      # slug: 짧은 kebab-case ASCII, 충돌 시 -2/-3
    sources.json                       # primary_source{date, url, key_passages_for_translation[], ...}
    <slug>.pdf
    segments.json                      # 스테이지별 필드 누적:
                                        #   2: youtube{title,hashtags,description} + segments[{n,voice,role,text}]
                                        #   5: .image  6: .subtitle_text  7: .stock_query  9: .stock_path
    script_notes.md
    segments/NN_<role>_<voice>.mp3
    audio.mp3
    pdf_pages/page-NN.png
    stock_clips/*.mp4 + manifest.json
    video.mp4
    thumbnail_brief.md / thumbnail_spec.json / thumbnail.png
    upload_result.json
```

## 에이전트 & 스킬 (expert-pool)

- **에이전트** (`.claude/agents/`): `kpop-source-finder`, `kpop-script-writer`,
  `subtitle-normalizer`, `stock-query-tagger`. 전부 단일 책임 — 새 에이전트 추가는 maze-auditor ②(선택 부담)
  관점에서 관찰된 필요가 있을 때만.
- **스킬** (`.claude/skills/`): `gukppong-pipeline`(오케스트레이터), `tts-fish`(TTS 셋업).

## 외부 의존

- **`claude-youtube` 스킬** — `third-party/claude-youtube/` 풀 클론(MIT)의 symlink. `/youtube thumbnail`(스테이지 11),
  `/youtube ideate`(다음 토픽), `/youtube repurpose`(발행 후 Shorts/블로그). 외부 API(DataForSEO/YouTube API/NanoBanana)는
  모두 optional — 없어도 WebSearch 폴백으로 동작. script/seo/hook/metadata sub-skill은 `kpop-script-writer`와 중복이라 미사용.
- **TTS 백엔드** — 현재 Qwen3-TTS-12Hz-1.7B-Base (Apache 2.0). 세대 이력·VRAM 제약은 [tts.md](tts.md).
- **Docker** — `autotube-fish-speech` 컨테이너는 LEGACY TTS가 아니라 `build_video.py`/`build_thumbnail.py`의
  in-container ffmpeg + Korean fontconfig 용도로만 일시 시동. Qwen과 VRAM 공유 불가 → [tts.md](tts.md) 참고.

## 기계 검증 게이트

`golden-principles.md`의 불변식은 `scripts/run_check.py output/<run>/`로 검증한다(말이 아니라 환경으로 강제 — 헌법 제3·4원칙).
스테이지 진행 중/완료 후 호출해 회차 산출물이 규약을 지켰는지 확인.
