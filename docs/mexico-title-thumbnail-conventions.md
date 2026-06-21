# MX 제목·썸네일 컨벤션 (경쟁 채널 데이터 분석 기반)

> 2026-06-21 작성. 멕시코/스페인어권 **Corea-México 반응 채널 80개 영상 + 12개 썸네일**을 YouTube Data API 로 실측 분석해 도출.
> 데이터: `research/mx_competitors/titles.json`, `research/mx_competitors/thumbs/`.
> MX 파이프라인의 `mx-script-writer`(youtube.title/thumbnail_copy) 와 stage 11 썸네일 spec 에 반영.

## 벤치마크 채널 (우리 포맷과 가장 유사)

| 채널 | 성격 | 대표 영상 (조회수) |
|---|---|---|
| **CHINGONES MX** | 한-멕 우정/환대 클립 (정확히 우리 포맷) | "Reportaje en TV de Corea del Sur sobre México 🇲🇽🤝🇰🇷" (1.68M) |
| **Liry Onni** | 한국 거주, 한-멕 관계 감성 | "México defendió a los coreanos 🥺❤️" (545K), "Ahora a México le toca ayudar a Corea 🙏" (404K) |
| **Tony Gol** | 축구 썰/질문형 | "¿Por qué los mexicanos aman a los coreanos?" (2.6M) |
| **Sin Montaje MX / DALEALPLAY / FAMILIA MEXIRUSA** | 반응(reaction) 썸네일 정석 | "Coreanos ROMPEN A LLORAR con lo que les Hizo MÉXICO", "¡COREANOS ENLOQUECEN CON MÉXICO!" |

(참고: Chingu amiga·Ji Moon·CoreAmigo 는 조회수 최상위지만 **쇼츠/개인 일상** 포맷이라 제목·썸네일 룰이 우리와 다름 → 벤치마크에서 제외.)

## 제목 공식 (실측 패턴, 빈도순)

1. **질문 후킹** — 가장 강력. `¿Por qué Corea llama a México "país hermano"?` / `¿Quién ganará según los coreanos?` (Tony Gol 2.6M, Liry 다수)
2. **감정 동사 + 충격** — `Coreanos ROMPEN A LLORAR…`, `¡Coreanos ENLOQUECEN con México!`, `México LOS HIZO LLORAR` (동사 대문자 강조)
3. **폭로형** — `LO QUE DIJERON los coreanos sobre México… SORPRENDIÓ` (앞은 미끼, 뒤에 반전어)
4. **충격 오프너** — `¡Insólito!`, `¡Increíble!` 문두
5. **상호성/형제애 서사** — `hermandad`, `país hermano`, `México defendió/ayudó a los coreanos` (멕시코를 주어로 = 자긍심)
6. **국기 + 해시태그** — 🇲🇽🤝🇰🇷 / 🇲🇽❤️🇰🇷 + `#Mundial2026`
7. **길이**: 대부분 **40-70자, 6-12 단어**. 우리 기존(98자)보다 짧게.

### ⚠️ 회차마다 제목 패턴 바꾸기 (2026-06-21 사용자 피드백 "제목 너무 비슷")
연속 회차에서 **같은 골격·같은 핵심어 반복 금지**. 패턴을 돌려써라:
- 1회 질문형 `¿Por qué Corea llama a México "país hermano"?`
- 2회 감정형 `Un coreano LLORÓ viendo a México y no fue el único`
- 3회 폭로형 `LO QUE DIJERON los coreanos de México te va a sorprender`
- 4회 상호성 `México los salvó, y Corea NUNCA lo olvidó`
"país hermano" 같은 시그니처 문구는 **한 회차에만**. 썸네일 카피와 제목도 서로 다른 앵글로.

### MX 제목 골격 (권장)
```
[질문 ¿…? | 감정동사 대문자 | LO QUE…SORPRENDIÓ] + México + país hermano/hermandad + 🇲🇽🇰🇷 + (선택 #Mundial2026)
```
- 핵심 강조어는 **대문자**(ROMPEN, ENLOQUECEN, EMOCIONAR, HERMANOS) 1-2개.
- 멕시코를 **주어/수혜자**로 ("Corea llama a México…", "lo que dijeron de México") → 멕시코인 자긍심.
- 이모지 1-3개, 국기쌍 필수.

## 썸네일 공식 (12개 실측 — 반응 썸네일 정석)

핵심 4요소 (고성과 썸네일 공통):
1. **거대한 2-4단어 텍스트** — 두꺼운 외곽선(검/흰), 화면의 30-45% 차지. 우리 기존은 글자수 많고 작음 → **단어 줄이고 키우기**.
2. **노란색(#FFD600) 강조어 1개** — ENLOQUECEN/MÉXICO/HERMANOS 등 핵심어만 노랑, 나머지 흰색.
3. **감정 표정의 얼굴** ⭐ 가장 큰 차별점 — 눈 크게 뜨거나/우는/환호하는 사람 얼굴. (DALEALPLAY·Sin Montaje·Xoque 전부 사용). 우리 기존엔 **없음 → 추가 필요**.
4. **호기심 키커 1줄** — "NADIE ESPERABA ESTO" 류 작은 부제. 본문 큰 텍스트 아래.

추가:
- 고채도·고대비. 멕시코+한국 둘 다 빨강 → 빨강 배너/악센트 잘 어울림.
- 국기 🇲🇽🇰🇷 보조 요소(작게).
- 배경 = 환호하는 군중/감정 장면(우리 video_thumb 가 이미 적합).

### ⚠️ 썸네일 멘트 = 과장 + 여러 표현 + 회차마다 다르게 (2026-06-21 사용자 피드백)
- **짧고 단순 X.** 호들갑 강동사·감탄사 풀로: `¡ROMPEN A LLORAR!`, `¡NO LO PUEDEN CREER!`, `¡COREA ENTERA LLORANDO!`, `JAMÁS`, `INCREÍBLE`.
- **3단 구성 권장**: 상단 큰 멘트(2줄) + **kicker(중간 band 작은 한 줄, spec `kicker`)** + 하단 멘트. → `build_thumbnail.py` sandwich 가 `kicker` 필드 지원.
- 회차마다 멘트 골격·핵심어 바꾸기 (제목과 동일 룰). `país hermano`/`hermanos`/`lloró` 등 시그니처 반복 금지.
- 이모지는 NotoSansCJK 가 tofu 박스로 깨뜨림 → **썸네일 텍스트엔 이모지 넣지 말 것** (제목·설명엔 OK).

### 우리 썸네일에 반영할 것 (gap)
- ✅ 이미 있음: 큰 텍스트 + 노랑 강조 + 군중 배경 + 국기
- ❌ 보강: (a) **얼굴**(환호/감격 표정 — video_thumb 군중에서 크롭 or face 요소), (b) **단어 수 줄이고 더 크게**, (c) **키커 부제 1줄**("lo que comentaron…"), (d) 멕시코 국기 강조

## mx-script-writer 반영 지침

- `youtube.title`: 위 골격. 질문형 또는 감정동사형 우선. 40-70자. 강조어 대문자.
- `youtube.thumbnail_copy`(상단 큰 글자, 2-4단어) + `thumbnail_subcopy`(키커 1줄).
- 예시 세트:
  - title `¿Por qué Corea llama a México "país hermano"? 🇲🇽🤝🇰🇷` / copy `"PAÍS HERMANO"` / kicker `Lo que dicen los coreanos`
  - title `Coreanos NO PARAN de hablar de México… y te va a EMOCIONAR 🇲🇽❤️🇰🇷` / copy `MÉXICO LOS` + `EMOCIONÓ` / kicker `Comentarios reales`

## 변경 이력
- 2026-06-21: 경쟁 채널 80영상/12썸네일 실측 분석 → 컨벤션 신설.
