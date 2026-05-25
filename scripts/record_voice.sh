#!/usr/bin/env bash
# Capture a GPT-SoVITS reference voice via arecord (ALSA).
#
# Usage:
#   scripts/record_voice.sh <voice-name>
#
# Env overrides:
#   RECORD_DEVICE=plughw:1,0   # arecord device, see `arecord -l`
#   RECORD_DURATION=8          # seconds
#
# Produces:
#   voices/<voice-name>/ref.wav       (mono, 22050 Hz, 16-bit PCM)
#   voices/<voice-name>/ref.txt       (placeholder — fill in transcript)
#   voices/<voice-name>/LICENSE.txt   (defaults to self-recorded note)

set -euo pipefail

DEVICE="${RECORD_DEVICE:-plughw:1,0}"
DURATION="${RECORD_DURATION:-8}"
NAME="${1:-}"

if [[ -z "$NAME" ]]; then
  echo "사용법: $0 <voice-name>"
  echo "예시:   $0 myvoice"
  echo ""
  echo "[arecord -l 의 capture devices]"
  arecord -l 2>&1 | sed -n '/^카드\|^card/p'
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT/voices/$NAME"
mkdir -p "$OUT_DIR"

cat <<EOF

==================================================
 GPT-SoVITS 레퍼런스 음성 녹음
   이름:   $NAME
   장치:   $DEVICE   (변경: RECORD_DEVICE=plughw:X,Y)
   길이:   ${DURATION}초   (변경: RECORD_DURATION=N)
   형식:   mono / 22050 Hz / 16-bit PCM
   출력:   $OUT_DIR/ref.wav
==================================================

[권장 샘플 문장 — 8초 안에 또박또박, 평소 톤으로]

  "안녕하세요. 오늘은 한국 문화가 해외에서
   어떻게 평가받는지, 흥미로운 자료들을 가지고
   이야기해볼게요."

녹음 팁:
  - 입에서 마이크까지 15-20cm, 약간 비스듬히 (파열음 방지)
  - 조용한 방, 에어컨/팬 OFF
  - 평소 말하는 톤 (속삭임·과장 X)
  - 끝까지 톤 유지 (마지막 5글자에서 힘 빠지지 않게)
EOF

while true; do
  read -rp $'\n[Enter] 누르면 3초 카운트 후 녹음 시작 (q: 취소): ' answer
  if [[ "$answer" =~ ^[Qq]$ ]]; then
    echo "취소됨."
    exit 0
  fi

  for i in 3 2 1; do
    printf "  %d... " "$i"
    sleep 1
  done
  echo "● REC"

  arecord -q -D "$DEVICE" -c 1 -f S16_LE -r 22050 -d "$DURATION" \
    "$OUT_DIR/ref.wav.tmp"
  mv "$OUT_DIR/ref.wav.tmp" "$OUT_DIR/ref.wav"

  echo ""
  echo "✓ 녹음됨: $OUT_DIR/ref.wav ($(du -h "$OUT_DIR/ref.wav" | cut -f1))"
  read -rp "[Enter] 재생 / s 건너뛰기: " skip
  if [[ ! "$skip" =~ ^[Ss]$ ]]; then
    aplay -q "$OUT_DIR/ref.wav" 2>/dev/null || true
  fi

  echo ""
  read -rp "이걸로 확정? [y=쓴다 / r=재녹음 / q=취소]: " yn
  case "$yn" in
    [Yy]*) break ;;
    [Qq]*) exit 0 ;;
    *) echo "재녹음으로." ;;
  esac
done

if [[ ! -f "$OUT_DIR/ref.txt" ]]; then
  cat > "$OUT_DIR/ref.txt" <<'EOF'
TODO: 위 ref.wav 의 정확한 전사를 한 줄로 작성하세요.
오타·생략·문장부호 누락은 합성 품질(prosody)을 떨어뜨립니다.
직접 들으며 받아쓰는 게 가장 정확합니다.
EOF
  echo ""
  echo "⚠ ref.txt 템플릿 생성: $OUT_DIR/ref.txt"
  echo "  → 이 파일을 열어 녹음 내용을 정확히 받아쓰기 해주세요."
fi

if [[ ! -f "$OUT_DIR/LICENSE.txt" ]]; then
  cat > "$OUT_DIR/LICENSE.txt" <<EOF
Source: self-recorded by $(whoami) on $(date +%Y-%m-%d)
License: Owner-recorded, used as TTS reference voice for autotube project.
EOF
fi

cat <<EOF

==================================================
 완료. 다음 단계:
   1. $OUT_DIR/ref.txt 열어 전사 작성
   2. autotube 루트에서 첫 합성 시도 (예시):

      python3 scripts/tts_sovits_client.py \\
        --script output/<run>/script.txt \\
        --voice voices/$NAME/ref.wav \\
        --voice-text "\$(cat voices/$NAME/ref.txt)" \\
        --out output/<run>/audio.mp3

==================================================
EOF
