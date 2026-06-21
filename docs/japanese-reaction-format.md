# [일본 반응] 영상 형식 — system of record

> 두 번째 영상 형식. 2026-06-06 사용자 발의.
> 트리거: 사용자가 "[일본 반응]" / "야후 재팬 반응" / "일본 댓글 반응 영상" 같은 문구로 요청할 때.
> 골든 프린서플 (golden-principles.md) 은 그대로 적용 — 그 위에 형식 차이만 여기 기록.

## 컨셉

야후 재팬(news.yahoo.co.jp) 의 한국 관련 뉴스/칼럼 한 편을 잡아서,
1) 본문을 듀얼 보이스로 번역+분석하고
2) 마지막에 일본 시청자의 실제 댓글 5-10개를 번역하여 여성 보이스가 통째로 낭독.

핵심 차별점: **댓글 섹션은 commentary 없이 여성이 쭉 읽음.** 시청자가 일본 댓글의 톤·맥락을 그대로 흡수하게 두는 게 의도. 댓글마다 원문 일본어 스크린샷을 화면에 띄움.

## 영상 구조 (전체)

```
[1]  intro (male)             — 후킹: 가장 충격적인 댓글 1개 또는 기사 핵심 인용
[2]  bridge (male)            — "오늘은 야후 재팬에 올라온 [기사 제목] 기사를 보시겠습니다. 일본 시청자들의 실제 반응까지 함께 확인해보시죠."
[3-N] translation/commentary  — 본문 4-6 패시지 번역 + 사설 (Paper Mode 의 Grounded Hyperbole 톤 적용)
[N+1] reaction_bridge (male)  — "그럼 이제 일본 시청자들이 직접 단 댓글들을 그대로 들어보시겠습니다. 번역만 했고, 별도 해석은 붙이지 않았습니다."
[N+2..N+K] reaction_translation (female only)  — 댓글 1개씩 = 1 세그먼트. commentary 없음.
[N+K+1] closing (male)        — 일본 반응 전체 감상 1-2문장 + 파이널K sign-off
```

## 세그먼트 갯수

- **본문 번역**: 4-6 패시지 (기사 분량에 따라)
- **본문 commentary**: 4-6
- **댓글 번역(reaction_translation)**: **5-10개**. 댓글이 적으면 5개, 풍부하면 10개. 짧고 강렬한 댓글 우선 — 긴 글타래는 핵심 2-3문장만 발췌 후 표시.
- 총 segments: **18-26개** (일반 영상 11-17 + 댓글 5-10).
- 총 글자수: **3000-4500자**, 런타임 **10-15분**.

## 새 segment role

기존 `intro / bridge / translation / commentary / closing` 외에 두 종류 추가:

### `reaction_bridge` (male)
- 본문 marathon 끝나고 댓글 섹션으로 넘어가는 single male segment.
- 톤: 차분한 전환. "그럼 이제 일본 시청자들이..." 류. 호들갑 X.
- 길이: 50-100자 짧게.

### `reaction_translation` (female)
- 댓글 1개의 한국어 번역. 한다체 (`~다`, `~이다`, `~했다`).
- 댓글 앞에 화자/번호 prefix **금지** — "댓글 일번:" 같은 메타 표지 X. 그냥 번역 텍스트만.
- 댓글 길이별 처리:
  - 짧은 댓글 (1-2문장): 그대로 번역
  - 긴 댓글 (3+문장): 핵심 2-3문장만 발췌, 나머지 생략 표시 X (자연스럽게 발췌)
- **commentary 사이에 끼우지 말 것.** 모든 reaction_translation 세그먼트는 본문 끝난 뒤 연속으로 배치.

### segments.json 추가 필드

`reaction_translation` 세그먼트는 다음 필드 필수:
- `comment_image`: 원문 일본어 댓글 캡처 PNG 경로 (run 폴더 상대 경로).
- `original_jp`: 원문 일본어 댓글 텍스트 (subtitle-normalizer / build_video 가 사용).
- `source_url`: 댓글이 달린 야후 재팬 기사 URL.

예시:
```json
{
  "n": 17,
  "voice": "female",
  "role": "reaction_translation",
  "text": "한국 가수가 일본 차트에서 일등을 했다는 게 충격이다. 십 년 전이라면 상상도 못했을 일이다.",
  "subtitle_text": "한국 가수가 일본 차트에서 1위를 했다는 게 충격이다. 10년 전이라면 상상도 못했을 일이다.",
  "original_jp": "韓国の歌手が日本のチャートで1位を取るなんて衝撃。10年前なら想像もできなかった。",
  "comment_image": "comments/comment-01.png",
  "source_url": "https://news.yahoo.co.jp/articles/..."
}
```

## 댓글 캡처 (Stage 4 의 댓글 모드)

야후 재팬 기사 페이지 끝에 붙은 댓글 섹션을 **각 댓글 단위로 잘라서** PNG 저장.

### 방법 A — Chrome headless 전체 페이지 캡처 후 crop
```bash
google-chrome --headless --disable-gpu --no-sandbox \
    --window-size=1280,2400 --screenshot=output/<run>/_full_page.png \
    "<article_url>"
# 그 후 PIL 로 댓글 영역 좌표를 잘라 comment-NN.png 로 저장
```

문제: 야후 재팬 댓글 영역은 무한 스크롤이라 첫 화면에 5개 정도만 보임. 더 끌어오려면 JS execution 필요 → Playwright 같은 것 도입 부담.

### 방법 B (권장) — 사용자가 직접 댓글 스크롤·캡처
야후 재팬 댓글은 lazy-load + Cloudflare-ish 보호 → 자동화 어려움. 사용자가:
1. 기사 URL 브라우저로 열기
2. 댓글 영역 스크롤하여 캡처할 댓글 노출
3. 댓글 1개씩 OS 캡처 도구 (스크린샷) 로 저장
4. `output/<run>/comments/comment-01.png ... comment-NN.png` 로 드랍

`AskUserQuestion` 으로 "댓글 자동 캡처 실패 → 수동 캡처 부탁" 분기로 진행.

### 방법 C — yahoo.co.jp 의 일반 텍스트 API (있다면)
야후 재팬은 코멘트 API 공식 없음. RSS/Atom 도 댓글 미포함. 무리.

### 권장 흐름
1. 시도 A. 5개 보이면 그걸로 진행.
2. 부족하면 사용자에게 추가 댓글 수동 캡처 요청 (`AskUserQuestion`).
3. 캡처 안 되면 댓글 섹션은 텍스트만 사용 (이미지 없이 자막만) — 폴백.

## Stage 변경 사항 (12-stage 파이프라인 대비)

| Stage | 표준 영상 | [일본 반응] 영상 |
|---|---|---|
| 1 sources | kpop-source-finder (논문/뉴스) | **kpop-source-finder 가 야후 재팬 URL 받음** — `primary_source.url` 이 news.yahoo.co.jp 면 일본 모드. 추가로 `primary_source.comments[]` 배열(각 항목 `original_jp` + `comment_image`)을 채움. |
| 2 script | kpop-script-writer (Paper/News Mode) | **Reaction Mode** (kpop-script-writer 확장) — 본문 + 댓글 섹션 함께 생성. 댓글 5-10개를 reaction_translation 세그먼트로. |
| 3a TTS | per-segment Qwen3-TTS | 동일. 일본어 원문은 합성 X, 한국어 번역 텍스트만 합성. |
| 3b concat | tts_qwen_client --concat | 동일. |
| 4 PDF | Chrome --print-to-pdf 기사 | **추가**: 기사 PDF 1장 + 댓글 캡처 N장 (`comments/comment-NN.png`). |
| 5 page-map | image field on each seg | 일반 세그먼트 = 기사 PDF 페이지. reaction_translation = `comment_image` 의 PNG. |
| 6 subtitle-normalizer | 한자 → 한글 / 영문 → roman | 동일. 단 reaction_translation 의 `original_jp` 는 손대지 않음. |
| 7 stock-query-tagger | per seg stock_query | 일반 세그먼트만. **reaction_translation 은 stock_query="" 강제** — 화면은 댓글 캡처가 풀화면. |
| 8 stock-fetcher | Pexels per query | 일반 세그먼트만. |
| 9 stock-path | inject stock_path | 일반 세그먼트만. reaction_translation 은 stock_path null. |
| 10 build_video | stock+pdf overlay + chars | **reaction_translation 분기 추가**: 풀화면 `comment_image` + 한국어 자막 burn-in. 캐릭터 (여성) 만 코너. stock 영상 X. |
| 11 thumbnail | sandwich layout | "[일본 반응]" 라벨 추가. 메인 카피 = 가장 충격적 댓글 1줄 (혹은 그 요약). |
| 12 upload | youtube_upload | 동일. title prefix `[일본 반응]` 권장. |

## 댓글 번역 톤 가이드

야후 재팬 댓글은 일본 인터넷 특유의 톤이 있음:
- 짧고 직설적, 종종 비꼬는 톤
- 약어/은어 자주 사용 (例: "草" = ㅋㅋ)
- 한국에 대한 의외의 호의/존경 vs 의외의 비판 모두 등장 — **둘 다 자연스럽게 번역**, 숨기지 않음
- 번역가는 톤을 살림. 직역 X 의역 OK. "韓国すごいな" → "한국 진짜 대단하네" (NOT "한국이 대단합니다")
- 한다체 유지 (`~다`, `~네`, `~지`, `~잖아`).
- 비속어/은어는 자연스러운 한국어 대응 — "草" → "ㅋㅋ" / "이게 뭐야 ㅋㅋ" 식.

## 댓글 선정 규칙 (orchestrator 가 선별)

야후 재팬 인기 댓글 (좋아요 순) 상위 30-50개에서 **5-10개** 선별. 기준:
1. 한국·BTS·K-콘텐츠에 대한 **호의적 반응** 50-70%
2. **놀라움/충격** 20-30% ("이걸 일본이 못 한다고?", "한국 무서워" 류)
3. **냉소적/비판** 0-20% — 너무 적대적이면 제외, 적당히 입체적인 톤 1-2개 포함
4. 댓글이 **구체적**일 것 — "대단하다" 만 있는 것은 제외, 구체적 비교나 일화 포함된 것 우선
5. 너무 긴 글타래 (5+문장) 은 핵심 2-3문장만 발췌

## 첫 번째 영상 (테스트) — 트리거 메모

사용자가 처음 이 형식 요청한 시점: 2026-06-06.
첫 영상 토픽: BTS 관련 야후 재팬 기사.
검증 포인트:
- [ ] reaction_translation 세그먼트가 commentary 없이 연속 배치
- [ ] 각 reaction_translation 이 comment_image 를 가짐
- [ ] build_video 가 reaction 모드에서 풀화면 댓글 캡처 + 자막
- [ ] 마지막 closing 이 본문/댓글 종합 1-2문장 + sign-off

## 변경 이력

- 2026-06-06: 형식 발의. 첫 테스트 영상 진행 중.
