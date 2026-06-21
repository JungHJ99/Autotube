# 썸네일 컨벤션 — autotube (스테이지 11)

> 디자인 컨벤션 + `thumbnail_spec.json` 스키마(= `build_thumbnail.py`가 소비하는 contract)의 정본.
> 렌더 명령은 [pipeline-stages.md](pipeline-stages.md) 스테이지 11. 제목/본문 톤은 [script-conventions.md](script-conventions.md).
> 원본 분석: `research/competitor_thumbnails_2026-05-21.md`, `research/headline_patterns_*_2026-05-22.md`.

## 레이아웃 — sandwich가 default (2026-05-22)

바이스톰 코리아(380K) + 쓸모왕(781K) 실제 썸네일 분석 결과, 둘 다 **수직 3분할 샌드위치**:
- **상단 ~38% 검정 띠** — 따옴표로 시작하는 큰 텍스트 2줄 (setup)
- **중간 imagery** — stock frame + 좌측 빨간 권위 라벨 + 우측 face cutout(들)
- **하단 ~38% 검정 띠** — reveal 텍스트 2줄

옛 `face-overlay`(가운데 헤드라인 + 우측 face)는 retain하되 backward-compat/실험용. sandwich 모드에선
**코너 태극기·"파이널K" 워드마크 기본 false**(경쟁 채널이 안 씀 — 텍스트 띠와 충돌). 채널 정체성은 텍스트 톤+권위 라벨로.

## 헤드라인 9패턴 (바이스톰/쓸모왕 환원)

**YouTube 제목 3마디:** `[인용/사건] + [세계/자국 반응] + [reveal 명사]`.
예: `직장 버리고 한국行 택해버린 日 여성들 + 자국 명문대 교수가 논문으로 직접 폭로한 + 충격적 진짜 이유`

1. **인용 prefix** — 따옴표로 시작 (`"한국이 또 미친걸 공개했다" ...`)
2. **~버린/~깨부순/폭로한** — 완료 동사 어미(단순 "했다"보다 강함)
3. **한자 single-char** — `韓` `美` `日` `中` `한국行` (한글 사이 시각 anchor)
4. **reveal 명사로 종료** — 이유/실제 상황/정체/광경/비밀/반격 (동사로 끝내지 말 것)
5. **숫자=권위** — `66.2%`, `8억 팬덤` (막연한 "많이" 금지)
6. **시간성 marker** — 결국/드디어/현재/이제
7. **세계 반응 동사** — 한국=행위자, 세계=반응자 (`전세계 매체들 난리났다`)
8. **자국 비판 hook** (일/중 영상) — `자국 학자가 폭로한` (비판자가 자국 본인이라는 인지부조화)

**썸네일 텍스트:** 노란 강조어는 의미 단위 2–4글자(`한국行`,`진짜 이유`,`66.2%`). 1글자 거대 강조(`왜?`)와
`충격/발칵/경악` 단독은 금지. 두 줄 모두 hook이 있어야 함.

## 호들갑 미사여구 (2026-05-28, 썸네일/제목 양쪽)

기본 글씨가 작고(start_size 72) 점잖아 클릭이 안 됨 → `build_thumbnail.py` 디폴트 변경:
`top/bottom_band_frac` 0.32→**0.38**, 텍스트 `start_size` 72→**130**, `min_size` 38→**64**.

**미사여구 사전** (spec에 최소 2개 박기, accent_words로 노랑 강조):
- 충격류: 충격/충격적인/경악  · 미친류: 미쳐버린/미친/역대급  · 소름류: 소름돋는/소름/전율
- 단언류: 말도 안 되는/믿기지 않는/현실이 된  · 결과류: 결국/끝내/마침내/드디어  · 강도류: 전세계가/지구가/외신이 발칵
- 강동사(하단 reveal): 무너졌다/항복/점령/석권/돌파/지배

**⚠️ 다양성 룰:** 같은 hook을 두 영상 연속 사용 금지(충격↔경악↔발칵, 미쳐버린↔역대급, 소름돋는↔전율로 교체).
**토픽 고유 단어**(테일러 스위프트→"팝의 황제", SK하이닉스→"엔비디아도 줄섰다")가 일반 호들갑보다 강함.

## 권위 라벨 (한국어 default — 2026-05-22)

- **한국어가 default.** 영어 단독은 한국인이 못 알아봄.
- 포맷: `[대학/매체명] + [직함] + [형식]` — 예 `리츠메이칸大 교수 논문 심층분석`, `NYT 보도 한국 분석`.
- 영문은 한국인도 즉시 아는 1–2글자 acronym만(`NYT`,`BBC`,`WSJ`). 한자 혼용 OK(`리츠메이칸大`,`美 교수`).
- `label.flag`에 출처 국가 국기. **`get_flag()`는 `KR`/`JP`만 지원** — `US` 등을 주면 ValueError로 죽으니
  한/일 외 출처는 flag 필드를 빼야 함.
- `label.font_size` default 36. 길어도 줄이지 말 것(12자↑면 38–42) — 한국 시청자가 못 알아보는 게 더 큰 손실.

## thumbnail_spec.json 스키마 (모든 필드 optional)

`_brief_source`/`_notes`는 렌더러가 무시(traceability용).

| 필드 | 효과 | 기본값 |
|------|------|--------|
| `layout` | `"sandwich"`(default 권장) / `"face-overlay"`(옛) | `"face-overlay"` |
| `top_text_lines` / `bottom_text_lines` | sandwich 상/하단 띠 텍스트(1–2줄) | `[]` |
| `top_band_frac` / `bottom_band_frac` | sandwich 띠 높이 비율 | `0.38` |
| `text_start_size` / `text_min_size` | sandwich 텍스트 크기 | `130` / `64` |
| `sandwich_band_alpha` / `sandwich_band_fill_hex` | 띠 alpha / 색 | `215` / `#000000` |
| `background.type` | `"stock"`/`"split"`/`"gradient"`/`"solid"` | `"stock"` |
| `background.stock_path` | 배경 클립(run dir 상대) | segments.json 첫 stock_path |
| `background.t` / `darken` | 프레임 추출 시점(초) / 어둡기 0..1 | `2.0` / `0.40` |
| `background.bottom_band_alpha` / `bottom_band_start` | 하단 그라데이션 띠 | `220` / `0.42` |
| `background.left_path`/`right_path`/`left_flag`/`right_flag`/`show_vs` | type=split 좌우 클립·국기·VS | — |
| `face.clip` / `t` / `size` / `position` | 얼굴 컷아웃(없으면 안 그림) | — / `2.0` / `360` / `"right"` |
| `text_lines` | (face-overlay) 2줄 텍스트 | youtube.title 자동 2분할 |
| `accent_words` | 노랑 강조 substring 리스트 | `[]` |
| `accent_color_hex` / `base_text_color_hex` | 강조/기본 색 | `#FFDC00` / `#FFFFFF` |
| `stroke_color_hex` / `stroke_width` | 외곽선 | 검정 / `12` |
| `text_band` | 텍스트 뒤 반투명 박스(true/false/obj) | true |
| `label` | 권위 라벨(string/obj: text·fill_hex·text_color_hex·font_size·flag) | none |
| `accent_punct` | 회전 ?! 스티커(text·color_hex·rotate·size·position) | none |
| `show_flag` / `flag_position` | 코너 태극기 | sandwich=false |
| `show_wordmark` / `wordmark_badge` / `wordmark_position` | "파이널K" | sandwich=false |

**split 모드** (한일/한미/Before-After 비교): 좌우 두 클립 + 슬랜티드 디바이더 + 양쪽 반투명 국기(`left_flag`/`right_flag`)
+ 가운데 "VS". 양쪽 국기가 이미 있으므로 코너 태극기는 off가 깔끔.

## 렌더 후 체크리스트 (Read tool로 inline 확인, 모바일 168×94에서도 읽혀야)

1. 좌상단 라벨이 안 잘리고 안 겹침  2. 텍스트 2줄이 검정 띠 위에서 또렷  3. 노란 강조가 의도된 단어인가
(substring이라 "한국"이 "한국行"도 잡음)  4. face가 텍스트를 안 가림  5. ?! 스티커가 텍스트와 분리
6. 코너 태극기가 작고(3–5%) face와 안 겹침  7. 우하단 워드마크 깔끔.

## ⚠️ docker 의존 (조용한 폴백 함정)

`build_thumbnail.py`의 `extract_frame()`는 `docker exec autotube-fish-speech ffmpeg`로 배경 프레임을 뽑는다.
컨테이너가 정지면 **조용히 gradient 배경으로 폴백**(에러 없이 `bg: gradient fallback`만). TTS 중(컨테이너 정지)
썸네일을 미리 만들면 이 함정. 우회: 호스트 ffmpeg로 프레임을 미리 뽑아 `--bg <png>`로 넘김(`pick_bg_from_run` 우회).
split은 bg 2장이라 우회 불가 → 컨테이너를 켤 것.
