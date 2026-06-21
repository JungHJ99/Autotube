# V3 영상 형식 — 해외 SNS 반응 (Reddit / Twitter / 등)

> 세 번째 영상 형식. 2026-06-12 사용자 발의 (V3 트리거).
> 사용자가 "V3 영상 만들어줘" 또는 "(주제) V3 영상 만들어줘" 라고 요청할 때 이 형식 사용.
> golden-principles.md 적용 위에서 — 형식 차이만 여기 기록.

## 컨셉

특정 주제 (스포츠 경기 / K-pop 무대 / 한국 뉴스 등) 에 대해 **해외 Reddit / Twitter 인기 게시물 여러 개 (~10개)** 를 수집하고, 각 게시물마다 **인기 댓글 여러 개 (~8개)** 를 함께 가져와서 통째로 번역 낭독한다. V2 (일본 반응) 가 1개 기사 + 댓글 N개 구조라면, V3 는 **N개 게시물 + 각 게시물마다 M개 댓글** 의 매트릭스 구조.

핵심 차별점:
- **다중 게시물** — Yahoo 1개 기사가 아닌 Reddit/Twitter 10여 개 게시물
- **원어 보존 + UI 모킹** — 영어/스페인어 원문을 그대로 화면에 띄움 (Reddit/Twitter UI 모킹 카드)
- **이미지 포함** — 게시물에 이미지가 있으면 카드 안에 같이 박음
- **분석 + 낭독 분리** — 게시물 분석 = 남자, 본문 + 댓글 낭독 = 여자

## 영상 구조 (전체)

```
[1]    intro (male)               — 후킹: 가장 충격적/대표적 댓글 1줄 또는 이슈 한 줄
[2]    bridge (male)              — "오늘은 레딧과 트위터에서 화제가 된 [주제] 관련 게시물 N개를 보시겠습니다. 인기 댓글도 함께 확인해보시죠."

[3..N] 게시물 블록 × N (보통 7-10개)
  각 블록 = 1 post_analysis + 1 post_body + 5-8 comment_translation
  
  [post k.1] post_analysis (male)      — 이 게시물이 어떤 맥락인지, 왜 인기인지 분석. 30-60자 짧게.
  [post k.2] post_body (female)         — 게시물 제목 + 본문 한국어 번역 낭독. 100-300자.
  [post k.3..k.K] comment_translation (female) × 5-8개  — 인기 댓글 1개당 1세그먼트. commentary 없음.

[last] closing (male)              — 전체 게시물·댓글 반응 종합 + 파이널K sign-off
```

## 세그먼트 갯수 가이드

| 항목 | 권장 |
|---|---|
| 게시물 (post) | **7-10개** (사용자가 "정도" 라고 했으면 7-10 사이 자유) |
| 댓글 / 게시물 | **5-8개** (게시물별 인기 댓글 수에 따라 조절 가능) |
| 총 segments | 게시물 N개 × (2 + 댓글 M개) + 2 (intro/closing) |
| 예: 10 posts × 8 comments | 102 segments |
| 예: 7 posts × 6 comments | 58 segments |
| 예: 5 posts × 5 comments | 37 segments |

런타임 추정: 평균 13초/세그먼트 → 50개=11분, 80개=17분, 100개=22분.

## 신규 segment role

V3 는 기존 role 외에 3개 추가:

### `post_analysis` (male)
- 이 게시물이 무엇인지, 왜 인기인지 30-60자로 짧게 짚어줌.
- 톤: 차분한 분석가. 호들갑 X.
- 매 게시물 블록의 첫 세그먼트.
- 예: "이 게시물은 레딧 r/soccer 에 1만 표를 받은 글입니다. 한국 골 장면 직후 다른 나라 팬들이 반응한 댓글이 몰렸습니다."

### `post_body` (female)
- 게시물의 제목 + 본문을 한국어 번역으로 낭독.
- 한다체 (`~다`, `~이다`).
- 제목과 본문을 자연스럽게 이어서 — 메타 표지 X ("이 게시물의 제목은...").
- 게시물에 이미지가 있으면 image 필드에 그 이미지 경로.
- 100-300자.

### `comment_translation` (female)
- 댓글 1개의 한국어 번역. 한다체 / 반말체 자연스럽게.
- 메타 prefix X — "댓글 일번:", "어떤 시청자는" 류 금지.
- 그냥 번역만.
- 30-150자 (짧은 댓글이면 짧게, 긴 댓글이면 핵심만).

## segments.json 필드 확장

### post_analysis 세그먼트
```json
{
  "n": N,
  "voice": "male",
  "role": "post_analysis",
  "text": "이 게시물은 ...",
  "subtitle_text": "...",
  "post_n": 1   // 이 게시물이 N번째 (1부터)
}
```

### post_body 세그먼트
```json
{
  "n": N,
  "voice": "female",
  "role": "post_body",
  "text": "한국 번역 텍스트",
  "subtitle_text": "...",
  "post_n": 1,
  "original_text": "원문 영어/스페인어 본문",
  "post_image": "posts/post-01.png",   // 모킹 UI 카드 (Reddit/Twitter 스타일)
  "post_url": "https://reddit.com/...",
  "post_meta": {
    "platform": "reddit" | "twitter",
    "subreddit": "soccer",
    "author": "username",
    "score": 12500,
    "comments": 320,
    "post_image_url": "https://i.redd.it/..."  // 게시물에 이미지가 있으면
  }
}
```

### comment_translation 세그먼트
```json
{
  "n": N,
  "voice": "female",
  "role": "comment_translation",
  "text": "한국 번역 댓글",
  "subtitle_text": "...",
  "post_n": 1,           // 이 댓글이 어느 게시물에 속하는지
  "comment_n": 3,         // 그 게시물 내 댓글 순서
  "original_text": "원문 영어/스페인어 댓글",
  "comment_image": "comments/post-01-comment-03.png",  // 댓글 UI 모킹 카드
  "comment_meta": {
    "platform": "reddit" | "twitter",
    "author": "username",
    "score": 1230,
    "replies": 12
  }
}
```

## UI 모킹 카드 (post_image + comment_image)

V2 가 Yahoo!ニュース 빨간 헤더 카드라면, V3 는 **Reddit / Twitter UI 모킹 카드** 를 PIL 로 생성.

### Reddit 게시물 카드
- 1920x1080 dark mode
- 상단 헤더: r/subreddit · author · "X hours ago"
- 중간 우측: 업보트 화살표 + 점수 + 다운보트 화살표
- 본문: 제목 (큰 글자) + body (작은 글자, 영문)
- 이미지가 있으면 카드 중간에 imbed
- 하단: 댓글 수 + share + save 등 아이콘

### Reddit 댓글 카드
- 1920x1080 dark mode
- 상단: 댓글 작성자 · 점수 · "X hours ago"
- 본문: 영문 원문 (큰 글자)
- 부드러운 hierarchy 표시 (왼쪽 들여쓰기 line)

### Twitter 게시물 카드
- 1920x1080 white mode (or dark)
- 상단: 프로필 (placeholder 동그라미) · @handle · 시간
- 본문: 트윗 텍스트 (큰 글자)
- 이미지가 있으면 4:3 또는 16:9 imbed
- 하단: comment / retweet / like / share 아이콘 + 카운트

### 색상 / 폰트 가이드
- Reddit dark mode bg: #1A1A1B / text: #D7DADC / accent orange: #FF4500
- Twitter dark mode bg: #15202B / text: #FFFFFF / accent blue: #1DA1F2
- 폰트: NotoSansCJK-Bold.ttc (한국어/영어 둘 다 OK)

## 데이터 수집 (Stage 0/1)

### 게시물 수집 방법
1. **Google site search**: `site:reddit.com/r/soccer "Korea" "Czech"` 류
2. **WebFetch**: 검색 결과 URL 에서 old.reddit.com 변환 후 JSON API (`/.json` 붙이기) — 댓글까지 한 번에 받음
3. **Twitter**: 검색 어려움 — Google search 로 캐시된 트윗 텍스트 + 스크린샷 사이트 (twstalker, nitter mirror 등) 시도
4. 결과 게시물 7-10개 선별 — **점수 / 인기 / 다양성** 으로 큐레이션

### 댓글 수집
- Reddit: `/.json` 응답에서 `replies[0].data.children[].data.body` + score 추출, score 순 상위 5-8개
- Twitter: 게시물 페이지의 인용/답글에서 상위 인용 트윗 추출

### sources.json 스키마

```json
{
  "mode": "overseas-sns-reaction",
  "version": "v3",
  "generated_at": "ISO",
  "topic": "한국 vs 체코 월드컵 해외 반응",
  "platforms": ["reddit", "twitter"],
  "posts": [
    {
      "n": 1,
      "platform": "reddit",
      "subreddit": "soccer",
      "author": "username",
      "post_url": "https://reddit.com/r/soccer/comments/.../",
      "post_title_original": "Korea takes the lead vs Czech Republic!",
      "post_title_ko": "한국이 체코를 상대로 선제골!",
      "post_body_original": "...",
      "post_body_ko": "...",
      "post_image_url": "https://...",  // optional
      "score": 12500,
      "n_comments_total": 320,
      "comments": [
        {
          "n": 1,
          "rank": 1,
          "author": "username",
          "score": 4200,
          "original_text": "...",
          "ko_translation": "..."
        },
        ...
      ]
    },
    ...
  ],
  "suggested_angle": "..."
}
```

## Stage 변경 사항

| Stage | 표준 | V3 |
|---|---|---|
| 1 sources | kpop-source-finder | **v3-reaction-source-finder** (Reddit/Twitter 다중 게시물 + 댓글) |
| 2 script | kpop-script-writer | **v3-reaction-script-writer** (post_analysis + post_body + comment_translation 구조) |
| 3a TTS | per-segment Qwen3 | 동일. 원문 합성 X, 한국어만. |
| 3b concat | 동일 | 동일 |
| 4 PDF | Chrome --print-to-pdf | **건너뜀** — V3 는 PDF overlay 안 씀. post_body / comment_translation 자체가 풀화면 UI 카드. |
| 5 page-map | image field | post_body 는 `post_image` 카드, comment_translation 은 `comment_image` 카드. 기타는 인트로 카드. |
| 6 subtitle-normalizer | 동일 | 동일 (원문은 손대지 않음) |
| 7 stock-query-tagger | per seg | post_analysis 만 stock_query 추가, 나머지는 "" |
| 8 stock-fetcher | Pexels | post_analysis 만 |
| 9 stock-path | 동일 | post_analysis 만 stock_path, 나머지는 null |
| 10 build_video | stock+pdf+chars | **build_video.py 분기 추가**: post_body / comment_translation 은 **풀화면 UI 카드 + 캐릭터 (여)** + 한국어 자막. post_analysis = stock + 캐릭터 (남). |
| 11 thumbnail | sandwich | "[해외 반응]" 라벨 + 충격 카피 + (BTS·서양 여자 패턴 또는 토픽 맞춤 이미지) |
| 12 upload | 동일 | 동일 |

## V3 톤 가이드

### 본문 commentary (post_analysis)
- **짧고 객관적**. 30-60자.
- 그 게시물의 출처 + 점수 + 왜 인기인지 짚기.
- 호들갑 / 사설 X — V3 의 사설은 closing 에 몰아서.

### 댓글 번역 (comment_translation)
- 톤 살림. 직역 X, 의역 O.
- "lol", "omg", "wtf", "wtf is this" — "ㅋㅋ", "ㅗㅁ", "뭐야" 류 자연스러운 한국어
- 비속어/은어 → 자연스러운 한국어 대응
- 한다체·반말체 자유 (원문 톤 따라가서)
- 영어 원문이 캐주얼하면 "~다" 보다 "~네", "~지" 가 자연스러움

### Closing (V3 시그니처)
- 본문 게시물 N개 + 댓글 K개를 종합한 1-2 문장.
- 가능하면 패턴 추출 ("열등감", "감탄", "의심", "굴복" 등 — 해외 반응이 한 방향으로 몰리는 경향).
- 마지막에 채널 sign-off (golden #4 정확).

## 첫 V3 영상 (2026-06-12 테스트)

- 토픽: **한국 vs 체코 월드컵**
- 출처: Reddit + (가능하면) Twitter
- 목표: ~7 게시물 × ~5 댓글 = ~37 세그먼트 + intro/closing = 39 세그먼트

## 변경 이력

- 2026-06-12: V3 형식 발의. 첫 영상 (한국 vs 체코) 제작.
