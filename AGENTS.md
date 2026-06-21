# AGENTS.md — autotube (파이널K 국뽕 파이프라인)

> 이 파일은 **목차**다. 백과사전이 아니다. 자세한 내용은 항상 `docs/`(system of record)를 가리킨다.

## 이 프로젝트는

해외(비-한국) K-culture/경제 자료 **한 편**을 깊게 파서, 한국어 듀얼보이스(번역자 여성 + 사설가 남성)
스크립트 → Qwen3-TTS MP3 → stock B-roll + PDF overlay + 자막 burn-in 영상 → 썸네일 → YouTube 업로드까지
자동 생성하는 회차 반복형 콘텐츠 파이프라인. 채널명 **파이널K**.

## 시작점

- 무엇이 "완성"인가 / 회차 QA 기준 → [`rubric.md`](rubric.md)
- 반드시 지킬 (기계 검증) 규칙 → [`golden-principles.md`](golden-principles.md), 게이트 `scripts/run_check.py`
- 막힌 점·교훈·생략 결정 → [`learning.md`](learning.md)

## 지식 위치 (포인터만 — 정본은 docs/)

- 전체 구조·패턴·12스테이지 DAG·run 폴더 규약 → [`docs/architecture.md`](docs/architecture.md)
- 스테이지별 입력/출력/검증 런북 → [`docs/pipeline-stages.md`](docs/pipeline-stages.md)
- TTS 백엔드·믹스 파라미터·자막 싱크 → [`docs/tts.md`](docs/tts.md)
- 스크립트 톤·세그먼트 구조·sign-off·제목 톤 → [`docs/script-conventions.md`](docs/script-conventions.md)
- 썸네일 레이아웃·헤드라인·spec.json 스키마 → [`docs/thumbnail-conventions.md`](docs/thumbnail-conventions.md)
- 환경 함정 복구(CUDA wedge·web→PDF·faststart 등) → [`docs/operations.md`](docs/operations.md)
- **두 번째 영상 형식 [일본 반응]** (야후 재팬 기사 + 댓글 번역) → [`docs/japanese-reaction-format.md`](docs/japanese-reaction-format.md)
- **세 번째 영상 형식 V3 [해외 SNS 반응]** (Reddit/Twitter 다중 게시물 + 댓글) → [`docs/v3-overseas-reaction-format.md`](docs/v3-overseas-reaction-format.md)
- **네 번째 영상 형식 MX [멕시코뽕]** (한국 유튜브 영상+댓글 → 멕시코 시청자, 스페인어 더빙/자막, 별도 채널) → [`docs/mexico-reaction-format.md`](docs/mexico-reaction-format.md)
- **MX 제목·썸네일 컨벤션** (경쟁 채널 실측 분석 → 제목 공식·썸네일 4요소) → [`docs/mexico-title-thumbnail-conventions.md`](docs/mexico-title-thumbnail-conventions.md)

## 작업 방식

- **패턴:** pipeline(주) + expert-pool + generate-validate (근거: `docs/architecture.md`).
- **에이전트** (`.claude/agents/`): `kpop-source-finder` · `kpop-script-writer` · `subtitle-normalizer` · `stock-query-tagger` · `v3-reaction-source-finder` · `v3-reaction-script-writer` · `mx-source-finder` · `mx-script-writer`.
- **스킬** (`.claude/skills/`): `gukppong-pipeline`(국뽕 오케스트레이터, "국뽕 영상 만들어줘") · `mexico-pipeline`(멕시코뽕 오케스트레이터, "멕시코 영상 만들어줘") · `tts-fish` · `claude-youtube`(외부, optional).
- **유일한 사용자 게이트:** 세그먼트 MP3 검수(스테이지 3a 후). "합치자" 신호 후 3b→11 자동 진행. 업로드(12)는 dry-run 후 confirm.

## 학습

막힌 점/교훈은 [`learning.md`](learning.md)에 누적(append-only). 하네스 개선·가지치기는 `foundry-harness`의 `/evolve`로.
