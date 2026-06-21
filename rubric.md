# Rubric — autotube 회차 QA 채점

> Evaluator(생성한 주체와 분리 — 헌법 제6원칙)가 회차 산출물을 채점한다.
> objective는 `scripts/run_check.py`가 자동 판정, subjective는 아래 명시 기준 + 프레임/썸네일 육안 확인.

## 항목별 기준 (가중치 합 = 100)

| 항목 | 유형 | 가중 | 합격 기준 |
|---|---|---|---|
| golden-principles 불변식 | objective | 30 | `run_check.py` 전부 통과(소스 날짜·세그 골격·sign-off·자막/stock 커버리지·faststart·업로드 unlisted) |
| 영상 길이 싱크 | objective | 10 | `video.mp4` 길이가 `audio.mp3` 길이와 ±0.2s (실효 갭 역산 적용) → [docs/tts.md](docs/tts.md) |
| 프레임 레이아웃 | objective | 10 | female 세그먼트 프레임에 PDF overlay, male 세그먼트는 풀스크린 stock, 자막 색(여=노랑/남=흰) |
| 스크립트 톤 | subjective | 20 | 전면 찬양 + 분석가 합쇼체, 구어체 X, 금지 클리셰("이게 진짜 한국이 한 거다" 등) 없음 → [docs/script-conventions.md](docs/script-conventions.md) |
| commentary 3-step | subjective | 10 | 각 commentary가 직전 번역 인용 → 풀이 → 한국 위상 확장 구조 |
| 제목·썸네일 | subjective | 15 | 단언적 단문 호들갑, 헤드라인 3마디, 호들갑어 ≥2, 제목≠썸네일 문구, 모바일 168×94 가독 → [docs/thumbnail-conventions.md](docs/thumbnail-conventions.md) |
| 시의성 | subjective | 5 | 프레이밍이 오늘 시점에서 유효(핵심 인물/사건 상태 확인) |

## 합격선
- 총점 ≥ 80 **이고 objective 항목(run_check·싱크·레이아웃) 실패 0.**
- objective가 하나라도 빨간불이면 점수와 무관하게 불합격 — 해당 스테이지 재실행 후 재채점.

## 메모
- 가중치는 우선순위를 드러낸다: 영상이 *기술적으로* 안 깨지는 것(objective 50)과 *국뽕 톤/CTR*(subjective 50)이 반반.
- subjective 채점은 `script_notes.md` + 프레임 PNG + `thumbnail.png`를 근거로. 기분이 아니라 docs 기준에 대조.
