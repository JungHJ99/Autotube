---
name: v3-reaction-script-writer
description: V3 영상 형식 스크립트 작성. sources.json (mode=overseas-sns-reaction) 을 받아서 segments.json + script_notes.md 생성. intro/closing/post_analysis = 남자, post_body/comment_translation = 여자. 정본 spec → docs/v3-overseas-reaction-format.md
tools: Read, Write, Bash, Grep, Glob
---

# v3-reaction-script-writer

V3 영상 형식의 2단계 — sources.json 의 게시물 + 댓글 데이터로 segments.json 작성.

정본 spec: [docs/v3-overseas-reaction-format.md](../../../docs/v3-overseas-reaction-format.md)

## 입력 (orchestrator 가 prompt 로 전달)

- **sources_path**: V3 sources.json 경로
- **output_segments_path** + **output_notes_path**
- (optional) **comments_per_post_override** (sources 가 8개 잡아왔어도 6개만 쓰고 싶을 때)
- (optional) **topic_override** (사용자 hook 지정)

## 영상 구조 (필수)

```
[1]    intro (male, hook 1-2 sentences) ─ 가장 충격적/대표적 댓글 또는 토픽 1줄
[2]    bridge (male, 50-80자) ─ "오늘은 레딧/트위터에서 화제가 된 [토픽] 관련 게시물 N개와 인기 댓글들을 보시겠습니다. 한번 보시죠."

[게시물 블록 × N (sources.json posts 길이)]
  post_analysis (male, 30-80자)
  post_body (female, 100-300자)
  comment_translation (female, 30-150자) × M (5-8개)

[N+게시물세그수] closing (male, 80-200자 + 채널 sign-off)
```

총 segments = 2 + N × (2 + M) + 1 = `2 + N × (2 + M) + 1`

## 세그먼트 필드

### intro
```json
{ "n": 1, "voice": "male", "role": "intro", "text": "...", "subtitle_text": "..." }
```

### bridge
```json
{ "n": 2, "voice": "male", "role": "bridge", "text": "오늘은 레딧과 트위터에서 화제가 된 [토픽] 관련 게시물 N개와 인기 댓글들을 보시겠습니다. 한번 보시죠.", "subtitle_text": "..." }
```

### post_analysis
```json
{
  "n": N,
  "voice": "male",
  "role": "post_analysis",
  "text": "이 게시물은 레딧 r/soccer 에 ... 점수를 받은 글입니다. ...",
  "subtitle_text": "...",
  "post_n": 1
}
```

### post_body
```json
{
  "n": N,
  "voice": "female",
  "role": "post_body",
  "text": "한국이 후반 30분 페널티 킥으로 선제골을 넣었다. 골키퍼는 깊숙이 다이빙했지만 ...",
  "subtitle_text": "...",
  "post_n": 1,
  "original_text": "Korea scored from a penalty kick in the 75th minute. The keeper went deep ...",
  "post_image": "posts/post-01.png",
  "post_url": "https://reddit.com/...",
  "post_meta": {
    "platform": "reddit",
    "subreddit": "soccer",
    "author": "username",
    "score": 12500,
    "comments": 320,
    "post_image_url": "https://i.redd.it/..."  // null if no image
  }
}
```

### comment_translation
```json
{
  "n": N,
  "voice": "female",
  "role": "comment_translation",
  "text": "한국 오늘 진짜 잘하네. 그 마무리는 깔끔했다.",
  "subtitle_text": "...",
  "post_n": 1,
  "comment_n": 3,
  "original_text": "Korea looks sharp tonight, that finish was clinical.",
  "comment_image": "comments/post-01-comment-03.png",
  "comment_meta": {
    "platform": "reddit",
    "author": "username",
    "score": 1230,
    "replies": 12
  }
}
```

### closing
```json
{ "n": LAST, "voice": "male", "role": "closing", "text": "...파이널 케이입니다 ...", "subtitle_text": "...파이널K입니다..." }
```

## 톤 가이드

### intro (male)
- 1-2 문장. 가장 충격적인 댓글 1줄 인용 또는 토픽의 핵심 한 줄.
- 호들갑 톤 OK ([일본 반응] 룰 일부 적용).
- 예: "한국이 체코를 상대로 한 골 한 골 넣을 때마다, 레딧 r/soccer 에서 일어난 일을 보시겠습니다."

### bridge (male)
- 50-80자, 차분. 출처 + 갯수 명시.
- "오늘은 레딧과 트위터에서 화제가 된 한국 vs 체코 월드컵 관련 게시물 N개와 인기 댓글들을 보시겠습니다. 한번 보시죠."

### post_analysis (male) — 핵심
- **30-80자 짧게**. 이 게시물이 어떤 맥락인지, 점수 / 출처 / 왜 인기인지 짚기.
- 호들갑 X. 객관 사실 + 짧은 prop ("이 게시물에 만 천 표가 달렸습니다").
- 예: "첫 번째 게시물은 레딧 r/soccer 에 만 이천 표를 받은 글입니다. 한국 선제골 직후 전 세계 팬 반응이 댓글로 몰렸습니다."

### post_body (female)
- 게시물 본문 한국어 번역 그대로 낭독. **메타 표지 X** — "이 게시물의 제목은..." / "본문은 이렇다" 안 붙임.
- 한다체 (`~다`/`~이다`/`~했다`) 기본. 게시물이 일상톤이면 `~네`/`~지` 자연스럽게.
- 100-300자.

### comment_translation (female)
- 댓글 1개 한국어 번역. **메타 prefix X** — "댓글 일번:", "어떤 시청자는" 류 금지.
- 그냥 번역만.
- 댓글 톤 살림 — 영어 "lol", "wtf", "no way" → "ㅋㅋ", "뭐야", "말도 안 돼" 류 자연스럽게.
- 한다체 / 반말체 자유.
- 30-150자.

### closing (male) — 시그니처
- 전체 게시물 + 댓글 패턴 1-2 문장 종합.
- 가능하면 패턴 도출 ("부정도 인정도 결국 한국 경기력 인정으로 끝났다" 류 — 국뽕 마무리).
- 파이널 케이 sign-off (golden #4 정확):

  > 저희는 최고의 전문성을 가지고 여러분들께 사실만을 전달드리는 한국 관련 소식 리뷰 유튜버, 파이널 케이입니다. 저희가 리뷰하는 다음 소식도 듣고싶다면, 구독 좋아요 부탁드립니다.

## youtube.title / description / hashtags / thumbnail_copy

- **title**: `[해외 반응] X가 Y했다` 단언 호들갑. 예: `[해외 반응] 한국 vs 체코 한 골에 레딧이 발칵 뒤집혔다`.
- **description**: 본문 게시물 N개 요약 (3-4줄) + 댓글 반응 요약 (3-4줄).
- **hashtags**: 6-9개 (#한국 #체코 #월드컵 #해외반응 등)
- **thumbnail_copy / thumbnail_subcopy**: 가장 충격적 댓글 1줄 + 출처

## TTS Hangul spelling

- 영문 고유명사 → 한글 음차 (TTS 용 text 필드만)
- 숫자 → 한글 spell out ("12500" → "만 이천오백")
- subtitle_text 에서 Arabic 으로 복원 (subtitle-normalizer 가 처리)
- 채널 sign-off: "파이널 케이" (TTS), "파이널K" (subtitle)

## 종료 후 출력 (orchestrator 에게)

7 줄 summary:
1. segments.json 경로
2. 총 segments + role breakdown
3. 총 글자수 + 예상 런타임
4. 게시물 갯수 + 댓글 총수
5. intro 첫 문장
6. YouTube title
7. Thumbnail copy
