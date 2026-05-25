#!/usr/bin/env python3
"""Qwen3-TTS-12Hz-1.7B-Base voice-clone smoke test.

Synthesizes a known-problematic Korean sentence (numbers-heavy) using the
existing female reference voice, so we can A/B against the matching
fish-speech segment from the most recent run.

Usage:
    python3 scripts/qwen_tts_smoketest.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import soundfile as sf
import torch

from qwen_tts import Qwen3TTSModel

ROOT = Path("/home/hjhj/autotube")
BASE_DIR = ROOT / "models" / "qwen3-tts-12hz-base"
TOK_DIR = ROOT / "models" / "qwen3-tts-12hz-tokenizer"
REF_F_WAV = ROOT / "voices" / "female_voice" / "ref.wav"
REF_F_TXT = ROOT / "voices" / "female_voice" / "ref.txt"
REF_M_WAV = ROOT / "voices" / "male_voice" / "ref.wav"
REF_M_TXT = ROOT / "voices" / "male_voice" / "ref.txt"

OUT_DIR = ROOT / "qwen_tts_test"
OUT_DIR.mkdir(exist_ok=True)

# Pulled from the latest run, segment 3 (female translation) — heavy numbers.
TEST_TEXT_FEMALE = (
    "이천이십삼년 일본 내각부가 실시한 공식 외교 여론조사에 따르면, "
    "응답자의 오십이점팔 퍼센트가 한국에 친근감을 느낀다고 답했다. "
    "여성의 경우 오십팔점일 퍼센트, 십팔세에서 이십구세 사이 청년층에서는 "
    "육십육점이 퍼센트에 달했다."
)

# Segment 4 male commentary — long-form prose with rhetorical structure.
TEST_TEXT_MALE = (
    "육십육점이 퍼센트. 이 숫자를 다시 한번 짚겠습니다. "
    "한국에 대해 복잡한 역사적 시각을 가진 일본에서, "
    "십팔에서 이십구 세 청년의 셋 중 둘이 한국에 친근감을 느낀다는 겁니다."
)


def main() -> int:
    print(f"[boot] CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        free, total = torch.cuda.mem_get_info()
        print(f"[boot] GPU free: {free/1024**3:.2f}GB / {total/1024**3:.2f}GB")

    t0 = time.time()
    print(f"[load] {BASE_DIR}")
    model = Qwen3TTSModel.from_pretrained(
        str(BASE_DIR),
        device_map="cuda:0",
        dtype=torch.bfloat16,
    )
    print(f"[load] done in {time.time()-t0:.1f}s")

    ref_f_text = REF_F_TXT.read_text(encoding="utf-8").strip()
    ref_m_text = REF_M_TXT.read_text(encoding="utf-8").strip()

    for tag, text, ref_wav, ref_text in [
        ("female", TEST_TEXT_FEMALE, REF_F_WAV, ref_f_text),
        ("male", TEST_TEXT_MALE, REF_M_WAV, ref_m_text),
    ]:
        print(f"\n[gen:{tag}] text={text[:60]}...")
        t1 = time.time()
        wavs, sr = model.generate_voice_clone(
            text=text,
            language="Korean",
            ref_audio=str(ref_wav),
            ref_text=ref_text,
        )
        dt = time.time() - t1
        wav = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
        out_path = OUT_DIR / f"qwen_{tag}.wav"
        sf.write(str(out_path), wav, sr)
        dur_s = len(wav) / sr
        print(f"[gen:{tag}] wrote {out_path} dur={dur_s:.2f}s sr={sr} "
              f"(synth {dt:.2f}s, {dur_s/dt:.2f}x realtime)")

    print(f"\n[done] outputs in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
