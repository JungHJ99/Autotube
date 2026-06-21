# Golden Principles — autotube

> **기계적으로 검증 가능한 불변식만** 적는다. "좋게 만들어라" 같은 훈계는 금지(그건 도메인 docs로).
> 각 규칙에 *왜* + *위반 감지법*을 붙인다. 규칙은 세금이다 — 실제 실패 사례가 있는 것만 남긴다.
> 회차 산출물 검증은 `python3 scripts/run_check.py output/<run>/` 한 줄로 강제(말이 아니라 환경 — 헌법 제3·4원칙).

## 불변식

1. **소스는 2026-01-01 이후.** `sources.json` → `primary_source.date ≥ "2026-01-01"`.
   왜: 채널 정체성=최신 해외 자료. 위반 감지: run_check #1.
2. **번역 발췌 4–7개.** `primary_source.key_passages_for_translation` 길이 4–7.
   왜: 미만이면 본문이 너무 얇다(여성 번역 세그먼트 부족). 위반 감지: run_check #2.
3. **세그먼트 11–17개 + 골격.** `segments` 11–17개, `role`이 intro/bridge/closing 각 정확히 1개,
   나머지는 translation/commentary. 왜: 듀얼보이스 비디오 에세이 구조. 위반 감지: run_check #3.
4. **closing에 파이널K sign-off.** closing 세그먼트 `text`는 "파이널 케이입니다"로, `subtitle_text`는
   "파이널K입니다"로 끝나는 고정 멘트 포함. 왜: 채널 보일러플레이트(누락해 재합성한 사례 있음).
   위반 감지: run_check #4. 정본 문구 → [docs/script-conventions.md](docs/script-conventions.md) §6.
5. **자막 N-of-N.** 스테이지 6 이후 모든 세그먼트에 비어있지 않은 `subtitle_text`.
   왜: 자막 트랙이 빠진 세그먼트는 화면에 자막이 안 뜬다. 위반 감지: run_check #5.
6. **stock_path N-of-N.** 스테이지 10 전 모든 세그먼트에 `stock_path`.
   왜: 없으면 build_video가 stock 모드로 안 들어가거나 검은 배경. 위반 감지: run_check #6.
7. **video.mp4 faststart.** 최종 `video.mp4`의 moov atom이 앞쪽(faststart).
   왜: 끝에 있으면 YouTube/X/Drive 업로드·프리뷰가 멈춘다. 위반 감지: run_check #7(`ffprobe`/atom 순서).
   소유권이 `root:root`면 `chown 1000:1000` 필요(경고). → [docs/operations.md](docs/operations.md).
8. **업로드 기본 unlisted.** `youtube_upload.py` 기본 `--privacy unlisted`. 자동 public 금지 —
   `--public`은 사용자가 매번 명시. 왜: 미검수 자동 공개 방지. 위반 감지: 코드 기본값 + dry-run preview.

> 참고(도메인 불변식, run_check 범위 밖): 믹스 male-gain 1.6/female 1.0, 자막 싱크는 명목 갭이 아니라
> 오디오 역산 실효 갭 — `tts_qwen_client.py`/스크립트 기본값과 [docs/tts.md](docs/tts.md)에 인코딩됨.

## 검증

- `python3 scripts/run_check.py output/<run>/` → 모든 불변식 통과 시 `exit 0`, 위반 시 `exit≠0` + 위반 목록.
- 스테이지가 아직 안 끝난 회차는 해당 후행 규칙(5·6·7)을 `SKIP`으로 표기(미존재 파일은 위반 아님).

## 변경 이력

- 규칙 추가/제거 시 사유를 [`learning.md`](learning.md)에 남긴다(특히 `[pruned]`). 죽은 규칙은 즉시 제거(헌법 제1원칙).
