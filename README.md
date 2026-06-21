# autotube

해외(비-한국) K-culture/경제 자료 **한 편**을 깊게 파서, 한국어 듀얼보이스(번역자 여성 + 사설가 남성)
스크립트 → Qwen3-TTS MP3 → stock B-roll + PDF overlay + 자막 burn-in 영상 → 썸네일 → YouTube 업로드까지
자동 생성하는 회차 반복형 국뽕 콘텐츠 파이프라인. 채널명 **파이널K**.

> **harness 정본은 [AGENTS.md](AGENTS.md)** — 구조·패턴·스테이지·컨벤션·운영 함정은 거기서 `docs/`로 이어진다.
> 이 README는 빠른 개요만 담는다.

## 한눈에

```
"BTS 그래미 영향 주제로 국뽕 영상 만들어줘"   ← 대화에서 gukppong-pipeline 스킬 발동
   → 12스테이지 자동 (소스→스크립트→TTS→영상→썸네일→업로드)
   → 유일한 사용자 게이트: 세그먼트 MP3 검수 (3a 후, "합치자" 신호 대기)
   → 업로드는 dry-run preview 후 confirm
```

## 디렉토리

```
autotube/
├── AGENTS.md                 # ★ 진입점 (목차)
├── golden-principles.md      # 기계 검증 불변식  (게이트: scripts/run_check.py)
├── rubric.md                 # 회차 QA 채점표
├── learning.md               # 실패/교훈/생략 결정 (append-only)
├── docs/                     # system of record
│   ├── architecture.md       #   패턴·12스테이지 DAG·run 폴더 규약
│   ├── pipeline-stages.md    #   스테이지별 입출력/검증 런북
│   ├── tts.md                #   Qwen3-TTS·믹스 파라미터·자막 싱크
│   ├── script-conventions.md #   스크립트 톤·세그먼트 구조·sign-off·제목 톤
│   ├── thumbnail-conventions.md #  sandwich 레이아웃·헤드라인·spec.json 스키마
│   └── operations.md         #   CUDA wedge·web→PDF·faststart 등 함정 복구
├── .claude/
│   ├── agents/               # kpop-source-finder, kpop-script-writer, subtitle-normalizer, stock-query-tagger
│   └── skills/               # gukppong-pipeline(오케스트레이터), tts-fish, claude-youtube
├── scripts/                  # tts_qwen_client, build_video, build_thumbnail, stock_fetcher,
│                             #   youtube_upload, run_check.py ...
├── voices/                   # male_voice/, female_voice/ (각 ref.wav + ref.txt + LICENSE.txt)
├── models/                   # qwen3-tts-12hz-base/ (~4.3GB)
├── bgm/  research/  patches/  third-party/  output/
└── foundry-harness/          # 이 서브-하네스를 주조/진화한 메타-하네스 (/forge·/evolve)
```

## TTS 백엔드

현재 **Qwen3-TTS-12Hz-1.7B-Base** (Apache 2.0, voice clone, `f5tts-venv/`). fish-speech 1.5는 LEGACY —
컨테이너는 `build_video.py`/`build_thumbnail.py`의 in-container ffmpeg + Korean fontconfig 용도로만 일시 시동
(Qwen과 VRAM 공유 불가). 세대 이력·VRAM 제약·믹스 파라미터는 [docs/tts.md](docs/tts.md).

## 레퍼런스 음성

`voices/<name>/`에 `ref.wav`(3–10초, 깨끗한 한국어) + `ref.txt`(정확한 전사) + `LICENSE.txt`.
**실존 인물의 동의 없는 딥페이크 음성 금지.**

## 회차 검증

```bash
python3 scripts/run_check.py output/<run>/     # golden-principles 불변식 기계 검증 (exit 0 = 통과)
```

## 의존성

Python 3.10+, `qwen-tts`/`torch`(venv), 호스트 `ffmpeg`(`~/.local/bin`), `pdftoppm`(poppler-utils),
`google-chrome`(web→PDF), Docker(영상 빌드용 fontconfig). `PEXELS_API_KEY`(stock), YouTube OAuth(업로드, 1회 셋업).

## 범위 밖 (사용자가 직접 요구할 때만)

per-segment B-roll cut-between-clips, PDF 차트 auto-extraction, Ken-burns/카메라 무브, intro/outro 스팅, 다중 화자(>2).
