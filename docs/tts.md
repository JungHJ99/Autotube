# TTS & 오디오 믹스 — autotube

> 음성 합성 백엔드 이력 + 현재 Qwen3-TTS 셋업 + 최종 믹스 파라미터 + 자막 싱크의 정본.
> 실행 명령은 [pipeline-stages.md](pipeline-stages.md) 스테이지 3 참고.

## 백엔드 세대 이력 (왜 지금 Qwen3인가)

| 세대 | 엔진 | 상태 | 교체 이유 |
|---|---|---|---|
| 1 | GPT-SoVITS (docker, api_v2 :9880) | OBSOLETE | "GPT TTS가 거슬린다, SOTA로" (2026-05-12) |
| 2 | fish-speech 1.5.1 (+rep_penalty 1.5) | LEGACY | Qwen 음질 우위 + 라이선스 (2026-05-21) |
| 3 | **Qwen3-TTS-12Hz-1.7B-Base** | **CURRENT** | A/B "월등히 좋다" + **Apache 2.0(상업 OK)** |

**S1-mini 이주는 폐기(2026-05-18).** OpenAudio S1-mini/S2-Pro는 codec 디코더가 청크마다 ~200MB를
추가로 요구하는데, RTX 3070 Ti 8GB + 데스크톱 GPU 컨텍스트(~700MB 상시 점유) 환경에서 OOM.
GPU가 12GB+로 업그레이드되기 전엔 재시도하지 않는다. 패치는 `patches/`에 보존(dac_inference / tokenizer /
vq_manager / text2semantic_inference). 사용자가 "S1-mini / OpenAudio / 더 좋은 TTS"를 다시 꺼내면
GPU 업그레이드 없이는 같은 벽이라는 점부터 안내. 품질 개선은 ref WAV 교체/튜닝 우선.

## 현재 백엔드: Qwen3-TTS

- **모델:** `Qwen/Qwen3-TTS-12Hz-1.7B-Base` (HF, gated 아님). 라이선스 **Apache 2.0 → 수익화 가능.**
- **로컬 경로:** `models/qwen3-tts-12hz-base/` (~4.3GB). `speech_tokenizer/` 동봉 — 별도 토크나이저 다운로드 불필요.
- **Python 환경:** `f5tts-venv/` (이름은 옛 F5-TTS 잔존). `qwen-tts==0.1.1`, `torch==2.12.0+cu130`.
  시스템 `python3`로 실행 X — venv 활성화 필요.
- **인터페이스:** `model.generate_voice_clone(text, language="Korean", ref_audio, ref_text)` — fish의
  zero-shot과 1:1 호환. ref WAV ~3초 + 정확한 전사면 됨(학습 불필요, zero-shot 결정 2026-05-12).
- **VRAM:** bf16 ~4.5GB. **fish-speech 컨테이너와 동시 실행 시 OOM**(fish 1.8GB 점유 → Qwen codec decode 터짐).
  Qwen 합성 전 `docker compose stop fish-speech` 필수, video build 직전 `docker compose start fish-speech`.
- **속도:** ~0.78x realtime (5분 audio → ~6.5분). flash-attn 미설치(cu130 호환 이슈).
- **무시해도 되는 경고:** import 시 "SoX could not be found" — 25Hz codepath용, 우리는 12Hz라 무관.
- **클라이언트:** `scripts/tts_qwen_client.py` (`--segments` 합성 / `--concat` 합치기). 레거시 `tts_fish_client.py`는 fallback.

## 보이스

- `voices/male_voice/` — 사설가(앵커 톤): intro/bridge/commentary/closing.
- `voices/female_voice/` — 번역자: translation 세그먼트. KSS 데이터셋 샘플(CC-BY-NC-SA 4.0).
- 각 폴더에 `ref.wav`(3–10초 깨끗한 한국어) + `ref.txt`(정확한 전사. 오타=음질 저하) + `LICENSE.txt`.
- **실존 인물의 동의 없는 딥페이크 음성 금지.**

## 믹스 파라미터 (Qwen3 기준, 2026-05-21 재calibrate · 사용자 승인)

`tts_qwen_client.py --segments` (per-segment 합성):
- `--male-gain 1.6` — 남자 voice clone이 일관되게 작음 → +60% boost
- `--female-gain 1.0` — base
- `--tail-pad 0.25` — 세그먼트 끝 0.25초 silence (EOS clipping 방지)
- 텍스트 끝 자동 padding: 마지막 char가 문장부호 아니면 `.` + trailing space (마지막 음절 잘림 완화)

`tts_qwen_client.py --concat` (최종 믹스):
- `--voice-gain 1.5` · `--bgm-gain 0.1` (BGM은 원본의 10%)
- `--voice-tempo 1.0` — **배속 없음** (fish 시절 1.1과 다름. Qwen은 자연 속도 적정)
- `--segment-gap 1.0` — 세그먼트 사이 1초 (fish 시절 0.3과 다름)
- BGM `-stream_loop -1`로 보이스 길이까지 늘려 `amix duration=first`로 자름
- **기본 BGM:** `bgm/거대한 문턱.mp3`

**룰:** `--concat`은 항상 `--bgm`과 함께(사용자가 "voice only" 명시 안 하면 BGM 드롭 금지). voice-only면
`--bgm` 생략 + 파일명에 `_voice_only`. 끝 씹힘 재발 시 `--tail-pad 0.4` 또는 end-pad 2글자. 호스트 ffmpeg
(`/home/hjhj/.local/bin/ffmpeg` 7.0.2)가 있어 Qwen 경로는 컨테이너 없이 동작.

## ⚠️ 자막 싱크 — 명목 갭 ≠ 실효 갭 (스테이지 10 함정)

`build_video.py`의 자막(SRT) 타이밍은 `--voice-tempo`/`--segment-gap`으로 타임라인을 계산한다.
이 값이 실제 `audio.mp3`와 다르면 자막이 누적 드리프트한다. 함정 두 개(둘 다 2026-05-22):

1. `build_video.py` 기본값은 옛 fish 칼리브레이션(tempo 1.1 / gap 0.3) → Qwen 오디오와 50초씩 어긋남.
2. `--segment-gap 1.0`으로 맞춰도 ~3초 잔여 드리프트. `--concat`이 만드는 1.0s 무음 MP3가 concat
   재인코딩 후 **실효 ~0.82s**로 줄기 때문(MP3 프레임 경계/패딩). 명목 갭 ≠ 실효 갭.

**처방:** 스테이지 10에서 `--voice-tempo 1.0` 유지, `--segment-gap`은 **오디오에서 역산한 실효 갭**을 넘긴다:

```
effective_gap = (audio.mp3 길이 − Σ(segments/*.mp3 길이)) / (세그먼트수 − 1)
```

실측 예: 조선업 0.8231, itoi 0.8187 — **런마다 다르니 매번 역산.** 빌드 후 `video.mp4` 길이가
`audio.mp3` 길이와 ±0.2s 안이면 OK.
