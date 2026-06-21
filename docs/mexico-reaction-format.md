# MX 영상 형식 — 멕시코뽕 (한국 반응 → 멕시코 시청자)

> 네 번째 영상 형식. 2026-06-20 사용자 발의 (MX 트리거 / "멕시코 영상 만들어줘").
> **별도 채널**용. golden-principles.md 위에서 — 형식 차이만 여기 기록.
> 정본(이 파일)이 우선. 충돌 시 이 문서가 source of record.

## 컨셉 (V3 의 거울)

V3 가 **해외 SNS → 한국인 국뽕**이라면, MX 는 **한국 인터넷 반응 → 멕시코인 자긍심**.
멕시코를 칭찬·응원하는 **한국 커뮤니티/유튜브 댓글**을 모아, 멕시코 시청자에게 **스페인어 더빙 + 스페인어 자막**으로 보여준다.

| | V3 (국뽕) | MX (멕시코뽕) |
|---|---|---|
| 방향 | 해외 → 한국인 | 한국 → 멕시코인 |
| 화면 카드 원문 | 영어/스페인어 | **한국어** (Koreans가 실제로 썼다는 증거) |
| 더빙 | 한국어 | **스페인어** |
| 자막 | 한국어 | **스페인어** |
| 카드 UI | Reddit/Twitter | **YouTube 다크모드** (유튜브 댓글) / 추후 에펨·더쿠·인스티즈 |
| 썸네일 | 별도 PNG | **영상 첫 프레임(intro 배경)으로 삽입** + 별도 PNG도 생성 |
| 채널 | 파이널K | (신규 멕시코 채널 — 미정) |
| 업로드 | 자동 | **당분간 보류** (채널/전화번호 인증 준비 후) |

핵심: 카드에는 한국어 원문 그대로. 멕시코인은 "한국 사람들이 우리를 이렇게 본다고?" 라는 자긍심을 느낀다.

## 첫 영상 소스 결정 (2026-06-20, 사용자)

- **소스 타입**: 한국 유튜브 영상 1개 + 그 영상의 실제 인기 댓글 N개 (YouTube Data API fetch)
- **데이터**: arctic-shift 같은 archive 없음. **YouTube Data API v3** (`~/.config/autotube/youtube_api_key.txt`) 로 commentThreads.list (공개 데이터, OAuth 불필요).
- **2차 소스 타입(추후)**: 에펨코리아/더쿠/인스티즈 — **Cloudflare 차단**이라 자동 fetch 불안정. 필요 시 사용자 스크린샷/본문 텍스트 제공.
- **real-data-only 룰 그대로 적용**: 댓글 날조 금지. fetch 실패 시 STOP.

## 콘텐츠 가이드 (멕시코 자긍심 자극)

좋은 토픽 = 한국인이 멕시코를 **진심으로 칭찬/감사/존중**하는 반응이 풍부한 것:
- 2018 러시아 월드컵 한국-멕시코 우정 (한국이 독일 꺾어 멕시코 16강 진출 → 멕시코의 한국 사랑 → 한국의 보답)
- 멕시코 음식/문화/사람들의 따뜻함에 대한 한국 반응
- 멕시코 선수/팀 스포츠맨십에 대한 한국 댓글
필터: 한국 댓글이 **멕시코를 깎아내리거나 조롱하는 것 제외**. 따뜻함·존중·감사·감탄만.

## 영상 구조 (전체)

```
[1]    intro (male, ES)        — 후킹 1-2문장. 가장 따뜻한/대표적 한국 댓글 1줄. 배경 = 썸네일 이미지(bg_image).
[2]    bridge (male, ES)       — "오늘은 한국인들이 멕시코에 대해 남긴 댓글들을 보겠다" 류. 출처(유튜브 영상) 명시.
[3]    video_card (female, ES)  — 그 한국 유튜브 영상이 무엇인지 + 한국어 제목 번역 낭독. 화면 = 유튜브 영상 카드.
[4..N] comment_translation (female, ES) × N  — 한국어 인기 댓글 1개당 1세그먼트. 화면 = 유튜브 댓글 카드.
[last] closing (male, ES)       — 전체 한국 반응 종합 + 채널 sign-off.
```

- 보통 **1 영상 + 8-15 댓글** → 12-19 세그먼트. (V2 의 "1 기사 + N 댓글" 구조에 가까움. V3 의 N-posts 매트릭스 아님.)
- 런타임 추정: 평균 ~12초/세그먼트 → 15세그=~3분, 19세그=~4분. (스페인어는 한국어보다 길어질 수 있어 여유)

## segment role → build_video.py 매핑 (중요: 기존 머신 재사용)

`build_video.py` 가 이미 처리하는 role 을 그대로 빌려쓴다 (코드 분기 추가 불필요):

| role | voice | 화면 | build_video 처리 | image 필드 |
|---|---|---|---|---|
| `intro` | male | **썸네일 풀스크린** + 캐릭터(남) | `bg_image` → full-screen still | `bg_image: "thumbnail.png"` |
| `bridge` | male | stock B-roll + 캐릭터(남) | normal (stock) | `stock_path` |
| `video_card` | female | 유튜브 영상 카드 풀스크린 | **role=post_body 로 출력** → `post_image` | `post_image: "video/video-card.png"` |
| `comment_translation` | female | 유튜브 댓글 카드 풀스크린 | 그대로 처리됨 | `comment_image: "comments/comment-NN.png"` |
| `closing` | male | stock B-roll + 캐릭터(남) | normal (stock) | `stock_path` |

> **구현 메모:** build_video 의 reaction-role 집합은 `reaction_translation / post_body / comment_translation`.
> video_card 세그먼트는 **role 을 `post_body` 로** 써서 `post_image` 카드로 렌더한다 (별도 코드 불필요).
> intro 의 썸네일 삽입은 build_video 에 새로 추가한 **`bg_image`** 필드로 동작 (어느 세그든 bg_image 있으면 그 정지이미지 풀스크린).

## 언어 / TTS — **edge-tts 멕시코 네이티브 보이스 (정본)**

- **모든 text 는 스페인어** (멕시코 스페인어 톤).
- **엔진 = Microsoft Edge neural TTS** (`scripts/tts_edge_client.py`):
  - male → `es-MX-JorgeNeural`, female → `es-MX-DaliaNeural` (둘 다 Friendly/Positive, 따뜻한 톤)
  - 출력 포맷이 Qwen 과 동일(`NN_<role>_<voice>.mp3` + tail-pad/fade) → **concat·build_video 그대로 재사용**.
  - concat 은 기존 `tts_qwen_client.py --concat <dir> --bgm ... --out ...` 그대로.
  - `pip install edge-tts` 필요. 온라인 엔드포인트 사용(무료). GPU 불필요.
- ⚠️ **Qwen3-TTS 크로스링구얼(한국어 ref→스페인어)은 폐기**. 2026-06-20 첫 영상에서 시도했으나 억양이 어색하다고 사용자 거부. Qwen 은 spanish 지원하고 `tts_qwen_client.py --language Spanish` 로 동작은 하지만, **멕시코 시청자용 네이티브 억양은 edge-tts 가 월등**. (Qwen `--language` 코드는 보존 — 다른 용도/폴백용.)
- 숫자/영문: edge-tts 가 스페인어 digit·약어 자연 처리. `text`=낭독용, `subtitle_text`=자막용(아라비아 OK).
- 속도 조절 필요시 `tts_edge_client.py --rate -8%` 등. male/female gain 기본 1.0 (edge 볼륨 일관).
- 채널 sign-off: 멕시코 채널용 스페인어 boilerplate. 채널명 확정 전까지 placeholder.

## sources.json 스키마 (mode=korean-reaction-for-mexico)

```json
{
  "mode": "korean-reaction-for-mexico",
  "version": "mx-v1",
  "generated_at": "ISO",
  "topic": "한국인들이 멕시코를 칭찬하다",
  "topic_es": "Los coreanos elogian a México",
  "source_label": "유튜브 인기 댓글",
  "notes": "REAL DATA — YouTube Data API commentThreads.list fetched on <ISO>. videoId=... . N comments fetched, top M by relevance/likes. No composite.",
  "video": {
    "video_id": "XPsn132ds44",
    "url": "https://www.youtube.com/watch?v=XPsn132ds44",
    "title_ko": "한국vs멕시코 경기… 멕시코 팬들이 한국인을 응원하기 시작했습니다",
    "title_es": "Corea vs México… los aficionados mexicanos empezaron a animar a los coreanos",
    "channel": "드로잉트립",
    "published_at": "2026-06-..",
    "published_human": "3일 전",
    "view_count": 152000,
    "description_ko": "...",
    "thumbnail_url": "https://i.ytimg.com/vi/XPsn132ds44/maxresdefault.jpg"
  },
  "comments": [
    {
      "n": 1,
      "rank": 1,
      "author": "초코라떼",
      "like_count": 4200,
      "published_at": "2026-06-..",
      "original_text": "한국어 원문 그대로 (verbatim)",
      "es_translation": "Traducción al español natural (mexicano)"
    }
  ],
  "suggested_angle": "..."
}
```

- `original_text` = **유튜브 댓글 textOriginal 그대로** (hallucination 금지).
- `es_translation` = 멕시코 스페인어 자연 의역 (직역 X). 한국 인터넷 톤(ㅋㅋ/와/대박)은 스페인어 구어(jaja/wow/qué crack)로.

## 데이터 수집 (Stage 1) — YouTube Data API

```bash
KEY=$(cat ~/.config/autotube/youtube_api_key.txt)
# 1) 영상 검색
curl -sG "https://www.googleapis.com/youtube/v3/search" \
  --data-urlencode "key=$KEY" --data-urlencode "part=snippet" \
  --data-urlencode "q=멕시코 한국 반응" --data-urlencode "type=video" \
  --data-urlencode "relevanceLanguage=ko" --data-urlencode "maxResults=10"
# 2) 영상 메타 (조회수/제목/썸네일)
curl -sG "https://www.googleapis.com/youtube/v3/videos" \
  --data-urlencode "key=$KEY" --data-urlencode "part=snippet,statistics" \
  --data-urlencode "id=VIDEO_ID"
# 3) 인기 댓글 (order=relevance 가 유튜브 '인기순')
curl -sG "https://www.googleapis.com/youtube/v3/commentThreads" \
  --data-urlencode "key=$KEY" --data-urlencode "part=snippet" \
  --data-urlencode "videoId=VIDEO_ID" --data-urlencode "order=relevance" \
  --data-urlencode "maxResults=50"
# 4) 썸네일 다운로드 → output/<run>/video_thumb.jpg
curl -sL "https://i.ytimg.com/vi/VIDEO_ID/maxresdefault.jpg" -o output/<run>/video_thumb.jpg
```

댓글 필터: `textOriginal` 비어있지 않음, 멕시코를 **긍정적으로** 언급, like 순/relevance 순 상위, 너무 짧은 것(<8자) 제외, 중복 제외. 8-15개 큐레이션.

## 카드 렌더 (Stage 5) — build_mx_cards.py

```bash
python3 scripts/build_mx_cards.py output/<run>/
# → output/<run>/video/video-card.png
#   output/<run>/comments/comment-NN.png
```

YouTube 다크모드 카드. `video_thumb.jpg` 있으면 영상카드에 박음. 한국어 원문 표시.

## 파이프라인 스테이지 (V3 대비 변경점)

| Stage | 표준/V3 | MX |
|---|---|---|
| 1 sources | v3-reaction-source-finder | **mx-source-finder** (YouTube Data API: 영상+댓글+썸네일) |
| 2 script | v3-reaction-script-writer | **mx-script-writer** (스페인어 듀얼보이스, video_card+comment_translation) |
| 3a TTS | Qwen Korean | Qwen **Spanish** (`--language Spanish`) |
| 3b concat | 동일 | 동일 (BGM) |
| 4 PDF | (V3 skip) | **skip** |
| 5 cards | build_cards.py (run-local) | **build_mx_cards.py** (스크립트화됨) + 썸네일 다운로드 |
| 6 subtitle-normalizer | Korean normalize | **skip** (text 가 이미 깔끔한 스페인어; subtitle_text=스페인어) |
| 7 stock-query-tagger | per seg | intro/bridge/closing 만 (male, stock). video_card/comment 는 "" |
| 8 stock-fetcher | Pexels | intro/bridge/closing 만 |
| 9 stock-path | 동일 | male 세그먼트만 stock_path |
| 10 build_video | stock+card | 동일 머신. **썸네일 먼저 만들고** intro.bg_image 주입 후 빌드 |
| 11 thumbnail | sandwich | **먼저** 생성 (stage 10 전). 멕시코 톤 카피. + intro 배경으로 재사용 |
| 12 upload | 자동 | **보류** — 채널/OAuth 준비 후. 지금은 video.mp4 + thumbnail.png 까지만. |

**순서 주의:** MX 는 썸네일(11)을 **build_video(10) 전에** 만든다 — intro 배경으로 넣어야 하므로.

## 자막 싱크

V3/표준과 동일. `--voice-tempo 1.0`, `--segment-gap` 은 오디오에서 역산한 실효 갭. 스페인어는 음절수가 많아 세그먼트가 길어질 수 있으니 빌드 후 video.mp4 ↔ audio.mp3 ±0.2s 확인.

## mx-v2 확장 — 멀티 영상 + 남자 해설 (긴 영상, 10-12분)

3:55 가 짧다는 피드백(2026-06-20) → **여러 영상 블록 + 남자 해설 인터젝션**으로 길이·몰입 확장.

### sources.json (mx-v2, `videos` 배열)
```json
{
  "mode": "korean-reaction-for-mexico", "version": "mx-v2",
  "topic": "...", "topic_es": "...",
  "videos": [
    {
      "video_n": 1,
      "video_id": "...", "url": "...", "title_ko": "...", "title_es": "...",
      "channel": "...", "view_count": 179311, "published_human": "8일 전",
      "thumbnail_url": "...", "thumb_file": "video_thumb_01.jpg",
      "comments": [ { "n":1,"rank":1,"author":"...","like_count":457,
                      "original_text":"한국어 verbatim","es_translation":"..." } ]
    },
    { "video_n": 2, "thumb_file": "video_thumb_02.jpg", "comments":[ ... ] }
  ]
}
```
- 영상별 썸네일은 `video_thumb_{NN}.jpg` 로 다운로드.
- 댓글 총합 **~50-60개 권장** (영상당 25-35). 2026-06-21 사용자 "댓글 너무 적다" → 상향. commentThreads `nextPageToken` 으로 후보 200-300개 받아 큐레이션. (단일영상 mx-v1 이면 1영상에 25-40개.)

### 카드 파일명 (build_mx_cards.py 자동)
- 영상 카드: `video/video-card-{NN}.png`
- 댓글 카드: `comments/v{VV}-comment-{CC}.png`
- (mx-v1 단일영상은 기존 `video-card.png` / `comment-NN.png` 유지)

### 신규 role `commentary` (male)
- 남자(Jorge)가 댓글 묶음 사이에서 **따뜻하게 받아치는 해설**. V1/V2 의 "자긍심 자극 + 직전 내용 언팩" 패턴을 멕시코뽕으로.
- 화면 = `bg_image: "male_backdrop.png"` (build_video 가 bg_image 정지이미지로 처리 — 추가 코드 불필요).
- 톤: 멕시코 시청자 자긍심 자극 ("멕시코인들의 이런 마음을 한국인이 이렇게 받아들인다", 출처 맥락 짚기). 댓글 3-5개마다 1개.
- 길이 20-40초.

### mx-v2 영상 구조
```
intro(male) → bridge(male)
[영상1] video_card(post_body,female) → [comment(female)×4-5 → commentary(male)] 반복 → 
transition(male, 영상2 예고)
[영상2] video_card(post_body,female) → [comment(female)×4-5 → commentary(male)] 반복 →
closing(male, 긴 종합 + sign-off)
```
- 세그먼트 총 ~45-50개 → edge-tts 페이싱 ~13s/seg → **10-12분**.
- video_card 2개: post_body 로 출력, `post_image`=`video/video-card-{NN}.png`, `post_n`=영상번호.
- comment: `comment_image`=`comments/v{VV}-comment-{CC}.png`, `post_n`=영상번호, `comment_n`=댓글번호.

## 변경 이력

- 2026-06-20: MX 형식 발의. 첫 영상(한국-멕시코 우정) 제작. tts `--language` + build_video `bg_image` + build_mx_cards.py 추가. 스페인어 더빙 = **edge-tts es-MX**(Qwen 크로스링구얼 폐기).
- 2026-06-20: mx-v2 — 멀티 영상 + 남자 commentary 인터젝션(10-12분). build_mx_cards.py 멀티영상 지원.
