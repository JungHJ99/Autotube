# Learning — autotube 하네스 작업 메모리

> 운영 중 막힌 점·교훈·일부러 안 만든 것을 **append-only**로 쌓는다(진화 루프 `/evolve`의 입력).
> 관례: `[failure]` 관찰된 실패 · `[pruned]` 제거한 하네스 요소+사유 · `[skipped]` 일부러 안 만든 것+사유.
> 프로젝트 특수 교훈은 여기 남기고, 일반화 가능한 것만 `foundry-harness/patterns`로 역류 제안(헌법 제7원칙).

## 주조 시 결정 (2026-06-01, foundry `/forge` 적용)

- `[skipped]` **MANUAL.md / nightwatch / manual-writer / manual-check.sh** — autotube는 클릭형 UI가 없는
  CLI 파이프라인이라 "매뉴얼대로 눌러보는 야간 QA"가 적용될 표면이 없음. 관찰된 실패 없는 세금(maze-auditor ④).
  대신 `scripts/run_check.py`가 결정적 게이트 역할을 한다.
- `[skipped]` **sprint-contract.md** — 회차 반복 생산이지 스프린트 단위 개발이 아님. "착수 전 done 협상" 양식이 매 영상에 과함.
- `[skipped]` **supervisor / hierarchical 패턴, 신규 에이전트** — 선형 파이프라인이고 자율 작업 보드 없음(헌법 제2원칙).
  기존 4개 에이전트로 충분(maze-auditor ② 선택 부담 회피).
- `[pruned]` **README의 GPT-SoVITS/tts-sovits/script.txt 서술** — 3세대 전(SoVITS→fish→Qwen3) 내용이라
  신규 세션을 오도. 현 상태로 재작성. 사유: 죽은/모순 정보(maze-auditor ④).
- `[pruned]` **SKILL stage 11의 썸네일/헤드라인 컨벤션 블록 + spec 스키마 테이블** — 700줄 SKILL의 분량 부담(maze-auditor ①).
  `docs/thumbnail-conventions.md`로 이관하고 포인터만 남김. 절차(11a/b/c 명령)는 보존.

## 관찰된 실패 (failures) — 과거 사례 (docs로 인코딩 완료, 재발 방지용 기록)

- `[failure]` Qwen 오디오에 build_video 기본값(tempo 1.1/gap 0.3) 적용 → 자막 50초 드리프트. 또 명목 1.0s 갭이
  concat 후 실효 ~0.82s로 줄어 ~3초 잔여 드리프트. → 실효 갭 역산(2026-05-22). 정본: [docs/tts.md](docs/tts.md).
- `[failure]` 첫 풀체인 영상이 moov-at-end + root:root 소유라 YouTube 업로드 멈춤(2026-05-13). → `+faststart`+chown. [docs/operations.md](docs/operations.md).
- `[failure]` OECD 보고서 page-02/03이 빈 표지라 여성 세그먼트 overlay가 흰 박스(2026-05-22). → ink-density 스킵. [docs/operations.md](docs/operations.md).
- `[failure]` Cloudflare/wp.com 사이트가 Chrome --print-to-pdf로 challenge 페이지만 받음(iea.org, musically.com). → <100KB면 PIL 카드. [docs/operations.md](docs/operations.md).
- `[failure]` closing sign-off 누락 → 세그먼트 재합성. → script-writer/subtitle-normalizer/docs 3중 박기. [docs/script-conventions.md](docs/script-conventions.md).
- `[failure]` commentary에 "이게 진짜 한국이 한 거다" 매 영상 박혀 구려짐(2026-06-01). → 금지 표현 명시. [docs/script-conventions.md](docs/script-conventions.md).
- `[abandoned]` OpenAudio S1-mini 이주(2026-05-18) — 8GB GPU에서 codec 디코더 OOM. 12GB+ 전까지 보류. 패치는 `patches/`. [docs/tts.md](docs/tts.md).

## 앞으로

- 새 실패는 이 파일에 `[failure] <증상> — <원인/처방>`로 즉시 append. 처방이 반복되면 해당 docs로 승격.
- 모델 세대가 올라가면(`/evolve` 업그레이드 트리거) maze-auditor의 "모델 세대 점검"으로 옛 비계를 가지치기.
