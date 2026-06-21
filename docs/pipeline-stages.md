# 파이프라인 스테이지 런북 — autotube

> 12스테이지의 입력→출력→검증 인덱스. **상세 실행 명령은 오케스트레이터
> `.claude/skills/gukppong-pipeline/SKILL.md`** 에 그대로 있고, 도메인 컨벤션은 같은 폴더의 도메인 docs로 분리돼 있다.
> 이 문서는 "어느 스테이지가 무엇을 만들고 무엇으로 검증하는가"의 지도다.

## 전제 — 보이스 확인 (시작 전)
`voices/{male,female}_voice/ref.wav`+`ref.txt` 둘 다 있어야 듀얼보이스 가능. 없으면 중단하고 `tts-fish` 스킬의
"Reference voices" 섹션을 가리킨다. 음성 백엔드 전반은 [tts.md](tts.md).

| # | 스테이지 | 행위자 | 입력 → 출력 | 검증 / 함정 |
|---|---|---|---|---|
| 1 | 소스 탐색 | `kpop-source-finder` agent | 토픽 → `sources.json` + `<slug>.pdf` | `primary_source.date` ≥ 2026-01-01; `key_passages_for_translation` 4–7개 |
| 2 | 듀얼보이스 스크립트 | `kpop-script-writer` agent | sources.json → `segments.json`(youtube{} + segments[]) + `script_notes.md` | 11–17 세그먼트, intro/bridge/closing 각 1개. 톤·sign-off은 [script-conventions.md](script-conventions.md) |
| 3a | 세그먼트 합성 | `tts_qwen_client.py --segments` | segments.json → `segments/NN_role_voice.mp3` | Qwen 합성 전 fish 컨테이너 stop(VRAM). 믹스는 [tts.md](tts.md) |
| — | **★ 리뷰 게이트** | 사용자 | MP3 검수 | 재합성: `--only N --overwrite`. "합치자" 신호 대기 — **유일한 필수 일시정지** |
| 3b | 최종 믹스 | `tts_qwen_client.py --concat` | segments/ + BGM → `audio.mp3` | 항상 `--bgm`(기본 `bgm/거대한 문턱.mp3`). 파라미터 [tts.md](tts.md) |
| 4 | PDF 렌더 | `pdftoppm` / 폴백 | PDF 또는 web URL → `pdf_pages/page-NN.png` | web→PDF·Cloudflare/wp.com·zero-pad 함정 → [operations.md](operations.md) |
| 5 | 페이지 매핑 | python | pdf_pages → segments.json `.image` | ink-density 빈 페이지 스킵 → [operations.md](operations.md) |
| 6 | 자막 정규화 | `subtitle-normalizer` agent | segments.json → `.subtitle_text` | N-of-N 세그먼트가 채워졌는지 |
| 7 | stock 태깅 | `stock-query-tagger` agent | segments.json → `.stock_query` | 일부 세그먼트는 의도적 미태깅(PDF 차트가 더 유용) |
| 8 | stock 다운로드 | `stock_fetcher.py` (Pexels) | stock_query → `stock_clips/*.mp4` + manifest | `PEXELS_API_KEY` 필요. 0건이면 generic 폴백 쿼리 |
| 9 | stock-path 주입 | python | stock_clips → segments.json `.stock_path` | 직접 클립 없는 세그먼트는 이웃 추종 |
| 10 | 영상 빌드 | `build_video.py` (stock 모드) | segments.json + audio.mp3 → `video.mp4` | `+faststart`·chown·**실효 갭** → [operations.md](operations.md)·[tts.md](tts.md) |
| 11 | 썸네일 | spec → `build_thumbnail.py` | → `thumbnail_spec.json` + `thumbnail.png` | sandwich 레이아웃·spec 스키마·docker 함정 → [thumbnail-conventions.md](thumbnail-conventions.md) |
| 12 | 업로드 | `youtube_upload.py` | run/ → `upload_result.json` | dry-run preview 먼저 → 사용자 confirm. **default privacy=unlisted** |

## 스테이지 10 build_video.py 동작 요약
stock_path가 모든 세그먼트에 있으면 stock 모드 자동 발동: 세그먼트별 stock 클립 looped bg(crop-fill 1920×1080) +
**female 보이스 세그먼트에만** PDF 페이지 오른쪽 overlay + concat + audio mux + libass 자막 burn-in(여자=노랑, 남자=흰색).
자막 타이밍은 `--voice-tempo 1.0` + 오디오 역산 실효 `--segment-gap`을 넘겨야 안 밀린다 → [tts.md](tts.md).

## 한 스테이지만 재실행 (다운스트림 무효화 주의)
- 소스 재탐색 → 2부터 전부 재실행  · 스크립트 재작성 → 3a + 5–10  · 특정 세그먼트만 → `--only N --overwrite` 후 3b + 10
- concat만 → `--concat` 후 10  · 영상만 → 10  · stock 교체 → stock_clips 삭제 후 8–9 → 10

## 업로드(스테이지 12) 기본값 & 한도
`--privacy unlisted`(자동 공개 금지 — `--public`은 사용자가 매번 명시), `--category-id 22`(People & Blogs;
News&Politics 25는 자동분류 위험 회피), `defaultLanguage/AudioLanguage=ko`, `madeForKids=false`, 썸네일 자동 첨부.
일일 quota 10,000 units, 업로드 1건 1,600 → **하루 최대 6개**. OAuth 1회 셋업: `scripts/README_youtube_oauth.md`.
**알려진 이슈:** description의 TTS-tuned 한글 숫자("육십육점이 퍼센트")가 그대로 노출될 수 있음 — dry-run에서 발견 시 수동 수정.

## 범위 밖 (사용자가 직접 요구할 때만)
per-segment B-roll cut-between-clips, PDF 차트 auto-extraction, Ken-burns/카메라 무브, intro/outro 스팅, 다중 화자(>2).
