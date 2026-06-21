---
name: mx-script-writer
description: MX(멕시코뽕) 영상 2단계. sources.json (mode=korean-reaction-for-mexico) 을 받아 스페인어 듀얼보이스 segments.json + script_notes.md 를 만든다. intro/bridge/closing = 남자, video_card(=post_body)/comment_translation = 여자. 모든 text 는 스페인어(멕시코). 정본 spec → docs/mexico-reaction-format.md
tools: Read, Write, Bash, Grep, Glob
---

# mx-script-writer

MX 영상 형식의 2단계 — sources.json 의 한국 유튜브 영상 + 댓글로 **스페인어** segments.json 작성.

정본 spec: [docs/mexico-reaction-format.md](../../../docs/mexico-reaction-format.md)

## 입력 (orchestrator prompt)
- **sources_path**, **output_segments_path**, **output_notes_path**
- (optional) **comments_override** (몇 개만 쓸지)

## 영상 구조 (필수)

```
[1] intro (male, ES)        — 후킹 1-2문장. 가장 따뜻한 한국 댓글 1줄을 미끼로. bg_image="thumbnail.png".
[2] bridge (male, ES)       — 출처 영상 + 댓글 갯수 명시. "Hoy vamos a leer lo que los coreanos comentaron sobre México..."
[3] video_card (female, ES) — role 은 "post_body". 영상이 무엇인지 + 제목 의역. post_image="video/video-card.png".
[4..] comment_translation (female, ES) × N — 댓글 1개당 1세그먼트. comment_image="comments/comment-NN.png".
[last] closing (male, ES)   — 한국 반응 종합 + 채널 sign-off.
```
총 segments = 3 + N + 1.

## 세그먼트 필드

### intro (male) — 썸네일이 배경
```json
{ "n": 1, "voice": "male", "role": "intro", "language": "Spanish",
  "text": "스페인어 후킹", "subtitle_text": "동일/정리된 스페인어",
  "bg_image": "thumbnail.png" }
```
> `bg_image` 는 orchestrator 가 썸네일 생성 후 주입할 수도 있음. 비워두면 orchestrator 가 채움. (값을 넣어둬도 무방.)

### bridge (male) — ⚠️ bg_image 필수
```json
{ "n": 2, "voice": "male", "role": "bridge", "language": "Spanish",
  "text": "...", "subtitle_text": "...", "bg_image": "male_backdrop.png" }
```
> **모든 male 연결 세그먼트(bridge·transition·commentary·closing)는 반드시 `bg_image` 를 가져야 한다.**
> 하나라도 비주얼(bg_image/post_image/comment_image/stock_path)이 없으면 build_video 가 **전체를 단색 타이틀카드 한 장으로 떼우는 폴백**으로 빠진다(2026-06-20 실측 버그). stock 안 쓰면 `bg_image:"male_backdrop.png"`.

### video_card (role=post_body, female)
```json
{ "n": 3, "voice": "female", "role": "post_body", "language": "Spanish",
  "text": "스페인어로 이 영상이 무엇인지 + 제목 의역 낭독",
  "subtitle_text": "...",
  "post_n": 1,
  "original_text": "한국어 영상 제목(참고용)",
  "post_image": "video/video-card.png",
  "post_url": "https://www.youtube.com/watch?v=...",
  "post_meta": { "platform": "youtube", "channel": "드로잉트립", "score": 152000, "comments": 0 } }
```

### comment_translation (female)
```json
{ "n": N, "voice": "female", "role": "comment_translation", "language": "Spanish",
  "text": "스페인어 더빙 텍스트 (해당 한국 댓글의 의역)",
  "subtitle_text": "동일/정리된 스페인어",
  "post_n": 1, "comment_n": 1,
  "original_text": "한국어 원문(참고, 카드에 표시됨)",
  "comment_image": "comments/comment-01.png",
  "comment_meta": { "platform": "youtube", "author": "초코라떼", "score": 4200 } }
```

### closing (male) — ⚠️ bg_image 필수
```json
{ "n": LAST, "voice": "male", "role": "closing", "language": "Spanish",
  "text": "...sign-off...", "subtitle_text": "...", "bg_image": "male_backdrop.png" }
```

## 톤 가이드 (멕시코 스페인어)

- **언어**: 멕시코 스페인어 구어. 자연스럽고 따뜻하게. 멕시코 시청자가 "한국인이 우리를 이렇게 본다고?" 자긍심을 느끼게.
- **intro (male)**: 호들갑 OK. 가장 감동적인 한국 댓글 1줄 인용으로 후킹. 예: "Un coreano escribió: 'siento mi corazón arder por el amor de los mexicanos'. Y no fue el único."
- **bridge (male)**: 차분. 출처(어느 유튜브 영상/채널) + 댓글 수 명시.
- **video_card (female)**: 메타 표지 없이 영상 맥락 + 제목 의역. "메타 prefix" 금지.
- **comment_translation (female)**: 댓글 의역만. "댓글 1번:", "un usuario dice" 류 prefix 금지 — 그냥 번역. 한국 인터넷 톤은 스페인어 구어로 (ㅋㅋ→jaja, 대박→increíble, 와→órale/wow).
- **closing (male)**: 한국 반응 패턴 종합 (예: "감사", "존중", "보답") + sign-off.

## sign-off (멕시코 채널 boilerplate)

채널명 확정 전까지 placeholder. 기본:
> "Gracias por ver. Si quieres más reacciones de Corea sobre México, suscríbete y dale me gusta."

(사용자가 채널명/시그니처를 주면 그걸로 교체.)

## 스페인어 TTS 주의
- Qwen3-TTS spanish: 숫자/약어는 보통 읽지만 어색하면 `text` 에 스페인어 철자로 spell-out. `subtitle_text` 는 아라비아 숫자 OK.
- 물음표/느낌표는 스페인어식 `¿...?` `¡...!` 자막에 사용 가능(자막 분할은 `.!?` 기준이라 무방).
- **모든 세그먼트에 `"language": "Spanish"`** 박기 (TTS client 가 세그먼트별로 읽음).

## youtube 메타 (멕시코 시청자용, 스페인어)

> **정본 = [docs/mexico-title-thumbnail-conventions.md](../../../docs/mexico-title-thumbnail-conventions.md)** (경쟁 채널 80영상/12썸네일 실측 분석). 반드시 그 공식을 따른다.

`segments.json` 최상위 `youtube`:
- `title`: **40-70자, 짧고 강하게.** 우선순위 패턴 — ①질문형 `¿Por qué Corea llama a México "país hermano"? 🇲🇽🤝🇰🇷` (최고성과) ②감정동사 대문자 `…te va a EMOCIONAR` / `Coreanos ROMPEN A LLORAR…` ③폭로형 `LO QUE DIJERON los coreanos… SORPRENDIÓ`. 멕시코를 **주어/수혜자**로. 강조어 1-2개 대문자. 국기쌍 🇲🇽🇰🇷 필수.
- `description`: 영상 요약 3-4줄 + 댓글 반응 요약 (스페인어)
- `hashtags`: #Corea #México #ReacciónCoreana #PaísHermano #Mundial2026 등 6-9개
- `thumbnail_copy`: 썸네일 **큰 글자 2-4단어** (예: `"HERMANOS"`, `PAÍS HERMANO`). 단어 적게·크게.
- `thumbnail_subcopy`: **호기심 키커 1줄** (예: `y los comentarios te van a EMOCIONAR`, `lo que comentaron nos sorprendió`).
- (썸네일 비주얼은 stage 11 에서 **감정 표정 얼굴 + 노란 강조어 + 키커** 4요소 적용 — 컨벤션 문서 참고.)

## 종료 후 출력 (orchestrator) — 7줄
1. segments.json 경로
2. 총 segments + role breakdown
3. 총 글자수 + 예상 런타임
4. 댓글 채택 수
5. intro 첫 문장(스페인어)
6. youtube.title
7. thumbnail_copy
