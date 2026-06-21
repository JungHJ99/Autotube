# 운영 & 함정 복구 — autotube

> 파이프라인 중 반복적으로 부딪힌 환경 함정과 그 결정적 처방. 스테이지 명령은 [pipeline-stages.md](pipeline-stages.md).

## CUDA wedge — `cuInit returns 999`

**증상:** `torch.cuda.is_available()` → False인데 `nvidia-smi`는 정상, `/dev/nvidia*`·`nvidia_uvm` 모듈도 정상,
도커 안 CUDA는 동작(호스트 컨텍스트만 깨짐). 깊이 보면 `cuInit(0)`가 999(CUDA_ERROR_UNKNOWN).
RTX 3070 Ti / driver 580.142 / CUDA 13.0 + torch 2.12.0+cu130에서 가끔(직전 CUDA 프로세스 비정상 종료 등).

**복구:** 한 줄이면 됨.
```bash
sudo rmmod nvidia_uvm && sudo modprobe nvidia_uvm   # 또는 sudo nvidia-smi -r
```
**처방:** `is_available()` False + `nvidia-smi` 정상이면 wedge로 단정(다른 원인 안 찾아도 됨). `sudo`는 Claude Code
classifier가 막으므로 **사용자에게 한 줄 부탁** — AskUserQuestion 첫 옵션 "수동 리셋 후 재시도(Recommended)".
리셋 후 `python3 -c "import torch; print(torch.cuda.is_available())"`로 즉시 검증. 폴백 불필요.

## 스테이지 4 — 웹 기사 → PDF (PIL 카드 직접 X)

`sources.json`의 primary_source가 PDF가 아닌 웹 URL이면 **PIL로 placeholder 카드를 직접 그리지 말고**
라이브 페이지를 PDF로 인쇄 후 렌더:
```bash
google-chrome --headless --disable-gpu --no-sandbox --no-pdf-header-footer \
  --print-to-pdf=OUT.pdf --virtual-time-budget=30000 --run-all-compositor-stages-before-draw "$URL"
pdftoppm -r 150 -png OUT.pdf pdf_pages/page    # 이후 zero-pad 정규화(아래)
```
`local_pdf_path`가 null이고 `url`이 있으면 자동 폴백. 호스트 chrome: `/usr/bin/google-chrome`.
**Why:** 실제 기사 페이지(사진/레이아웃/국기 이미지)가 PIL 카드보다 정보량·시각 우위(2026-05-13 사용자 명시).

### zero-pad 정규화 (둘 다 공통)
`pdftoppm`은 `page-1.png`…`page-17.png`(non zero-padded). **bash `printf %02d`는 `08`/`09`를 invalid octal로
인식해 실패** → Python으로 정규화:
```python
import re; from pathlib import Path
d = Path("output/<run>/pdf_pages")
for f in d.glob("page-*.png"):
    m = re.match(r"page-(\d+)\.png", f.name)
    if m: f.rename(d / f"page-{int(m.group(1)):02d}.png")
```

## 스테이지 4 — Cloudflare / WordPress.com bot challenge → PIL 폴백

Chrome `--print-to-pdf` 결과가 **20–100KB로 비정상적으로 작으면** challenge 페이지("Checking your browser" /
"Secured by wp.com")로 단정. 확인된 사이트: iea.org(Cloudflare), musically.com(wp.com). real UA /
`--disable-blink-features=AutomationControlled` / `--virtual-time-budget=60000` **전부 실패** — headless detection.

**처방:** PDF < 100KB거나 pdftoppm 단일 페이지면 즉시 PIL 카드 폴백(사용자에게 안 묻고 진행, UA 변형 재시도 1회까지만).
`sources.json`의 `key_passages_for_translation` + `key_findings`에서 4–7개 fact를 뽑아 1240×1754 A4 카드 4–5장 생성
(헤더 띠 + 제목 + bullet 본문 + 출처 푸터). 폰트 `/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc`(한글 OK).
카드별 다른 주제(hook stat / secondary data / industry response / policy / outlook).
**Why:** Selenium+undetected-chromedriver는 의존성 비대화. 5분 PIL 카드가 깔끔하고 화질도 우위(실제 페이지는 사이드바/광고도 인쇄됨).

## 스테이지 5 — PDF 빈 페이지 스킵 (ink density)

기본 휴리스틱은 본문 세그먼트를 `pages[1:]`에 라운드로빈 매핑하는데, OECD 보고서·학술 논문은 page-02/03이
표지 뒷면/판권/빈 페이지라 여성 번역 세그먼트 overlay가 새하얀 빈 박스로 나온다(2026-05-22 조선업).

**처방:** 스테이지 5 직전 PIL로 각 페이지 ink density(밝기 230 미만 픽셀 비율) 측정 → `ink < 0.06` 빈 페이지를
본문 풀에서 제외하고 ink 높은 콘텐츠 페이지만 매핑. intro/bridge/closing은 page-01(표지) 유지.
빌드 후 프레임 검증에서야 발견되는 문제라, 사전 필터로 영상 재빌드(~5분) 한 번 아낀다.

## 스테이지 10 — video.mp4 faststart + 소유권

- **`-movflags +faststart` 필수.** moov atom이 파일 끝에 있으면 YouTube 웹 업로더(및 X/Drive 프리뷰)가
  메타데이터를 못 읽어 검증/프리뷰에서 멈춘다. `build_video.py`의 모든 최종 ffmpeg 출력(stock/per_seg/single
  image 모드)에 들어있는지 확인. 기존 파일 빠른 수정: `ffmpeg -i in.mp4 -c copy -movflags +faststart out.mp4`(재인코딩 X).
- **소유권:** `autotube-fish-speech` 컨테이너가 root로 돌아 `video.mp4`가 `root:root`로 생성됨. 일부 업로드 툴/브라우저가
  거부할 수 있으니 빌드 후 `docker exec ... chown 1000:1000 ...`으로 hjhj 소유로. 빌드 후 `ls -la video.mp4` 확인.

> 이 두 가지(faststart·소유권)와 자막 싱크(실효 갭)는 `scripts/run_check.py`가 기계 검증한다.
