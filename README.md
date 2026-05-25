# autotube

해외 K-pop/K-culture 자료를 모아 한국어 썰풀이 스크립트로 변환하고 TTS로 음성까지 만드는 국뽕 YouTube 콘텐츠 자동화 파이프라인.

영상 합성(편집·자막·업로드)은 아직 범위 밖. **소스 탐색 → 스크립트 → MP3** 까지가 현재 구현 범위.

## 구조

```
autotube/
├── .claude/
│   ├── agents/
│   │   ├── kpop-source-finder.md   # 해외 논문/리포트/뉴스 탐색
│   │   └── kpop-script-writer.md   # 썰풀이 한국어 스크립트 생성
│   └── skills/
│       ├── gukppong-pipeline/      # 1→2→3 전체 파이프라인 오케스트레이션
│       └── tts-sovits/             # GPT-SoVITS 호출 (MP3 생성)
├── scripts/
│   └── tts_sovits_client.py        # GPT-SoVITS API 클라이언트
├── voices/                          # 레퍼런스 음성 (각 폴더에 ref.wav + ref.txt)
└── output/                          # 회차별 결과물
    └── <YYYY-MM-DD>-<topic-slug>/
        ├── sources.json
        ├── script.txt
        ├── script_notes.md
        └── audio.mp3
```

## 사용

### 전체 파이프라인

Claude 대화에서:
> "BTS 그래미 영향 주제로 국뽕 영상 만들어줘"

→ `gukppong-pipeline` skill이 발동되어 소스 탐색 → 스크립트 → (음성 확인) → TTS 까지 진행. TTS 직전에 한 번 컨펌 받음.

### 단계별

- 소스만: "BTS 그래미 관련 해외 자료 찾아줘" → `kpop-source-finder` agent
- 스크립트만: "이 sources.json으로 스크립트 써줘" → `kpop-script-writer` agent
- 음성만: "이 script.txt로 음성 만들어줘" → `tts-sovits` skill

## TTS 셋업 (한 번만)

GPT-SoVITS는 도커로 돌림. 이미지에 사전학습 모델·G2PW·NLTK·JTalk 사전 다 포함되어 있어서 별도 다운로드 없음.

**전제조건:** Docker 24+, `docker compose` 플러그인, `nvidia-container-toolkit`, NVIDIA 드라이버 525+, 디스크 ~15GB.

```bash
cd /home/hjhj/autotube
docker compose pull       # 최초 1회: ~10-15GB 다운로드
docker compose up -d      # API 서버 시작 (백그라운드)
docker compose logs -f gpt-sovits   # "Uvicorn running on http://0.0.0.0:9880" 뜰 때까지
```

설치 후 운영 명령:
- `docker compose down` — API 서버 중지 (VRAM 해제)
- `docker compose restart gpt-sovits` — 재시작
- `docker exec -it autotube-gpt-sovits bash` — 컨테이너 셸 진입 (디버깅)

자세한 트러블슈팅은 [.claude/skills/tts-sovits/SKILL.md](.claude/skills/tts-sovits/SKILL.md).

호스트에 `ffmpeg` 없어도 됨 — 클라이언트가 자동으로 컨테이너의 ffmpeg를 `docker exec`로 호출.

## 레퍼런스 음성

`voices/<name>/` 폴더에:
- `ref.wav` — 3~10초, 깨끗한 한국어 발화 (배경음·잡음 없음)
- `ref.txt` — ref.wav의 정확한 전사 (오타 = 음질 저하)
- `LICENSE.txt` — 오픈소스/CC 라이선스 또는 본인 녹음임을 명시

**중요:** 실존 인물의 동의 없는 딥페이크 음성은 사용 금지.

## 의존성

- Python 3.10+
- `requests` (TTS 클라이언트)
- `ffmpeg` (WAV → MP3)
- GPT-SoVITS (별도 설치)

## 범위 밖 (TODO)

- 영상 합성 (스틸 이미지 + 자막 + 음성 → mp4)
- 자동 자막 (Whisper 등)
- YouTube 업로드 자동화
- 다중 화자 / 대화형 스크립트
