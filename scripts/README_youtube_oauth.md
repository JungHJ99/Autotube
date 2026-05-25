# YouTube 자동 업로드 OAuth 1회 셋업

`scripts/youtube_upload.py` 가 작동하려면 한 번만 Google Cloud Console 에서 OAuth credentials 를 발급받아야 함. **5-10분, 영구, 무료.**

## 단계 1: Google Cloud 프로젝트 + API 활성화

1. [console.cloud.google.com](https://console.cloud.google.com/) 접속 (업로드할 YouTube 채널의 Google 계정으로 로그인).
2. 상단 **프로젝트 선택** → **새 프로젝트** → 이름 `autotube` (또는 아무거나) → 만들기.
3. 좌측 메뉴 **API 및 서비스** → **라이브러리** → `YouTube Data API v3` 검색 → **사용 설정** 클릭.

## 단계 2: OAuth 동의 화면 구성

API 사용 설정 직후 "사용자 인증 정보 만들기" 안내가 나오는데 거기서 안 하고 좌측 메뉴 그대로 진행:

1. **API 및 서비스** → **OAuth 동의 화면**
2. **사용자 유형: 외부** 선택 → 만들기
3. 필수 입력:
   - **앱 이름**: `autotube` (혹은 아무거나, 사용자만 봄)
   - **사용자 지원 이메일**: 본인 Gmail
   - **개발자 연락처 정보**: 본인 Gmail
4. **저장 후 계속** → 범위 페이지에서 **저장 후 계속** (범위는 코드에서 동적으로 요청하므로 여기선 안 추가해도 됨)
5. **테스트 사용자** 페이지에서 **+ 사용자 추가** → 본인 Gmail 추가. (이게 없으면 "이 앱이 확인되지 않았습니다" 단계에서 안 넘어감)
6. **저장 후 계속** → 요약 → **대시보드로 돌아가기**

> 앱이 "테스트 모드" 인 동안은 본인 + 등록한 테스트 사용자만 사용 가능 (충분).
> 일반 사용자에게도 공개하려면 Google verification 필요한데 우리 용도엔 불필요.

## 단계 3: OAuth client ID 발급

1. **API 및 서비스** → **사용자 인증 정보** → **+ 사용자 인증 정보 만들기** → **OAuth 클라이언트 ID**
2. **애플리케이션 유형: 데스크톱 앱** 선택. (이게 핵심 — Web 이나 다른 거 고르면 안 됨)
3. 이름은 아무거나 (`autotube-cli`).
4. **만들기** → JSON 다운로드 버튼 클릭.

다운로드된 파일은 `client_secret_XXXXX.json` 같은 이름. 이걸 다음 경로로 옮겨야 함:

```bash
mkdir -p ~/.config/autotube
mv ~/다운로드/client_secret_220326120776-qi0iaqs74jtot4hr713r2be1u6etvttb.apps.googleusercontent.com.json ~/.config/autotube/client_secret.json
chmod 600 ~/.config/autotube/client_secret.json
```

## 단계 4: 첫 실행 (1회만 브라우저 인증)

```bash
python3 scripts/youtube_upload.py --run output/<some-run>/ --dry-run
```

`--dry-run` 은 API 호출 안 하므로 인증 안 뜸. 진짜 인증은 첫 실제 업로드 시:

```bash
python3 scripts/youtube_upload.py --run output/<some-run>/
```

자동으로:
1. 로컬 서버 (random port) 가 켜짐
2. 브라우저 탭이 열림 → Google 로그인
3. **"이 앱이 확인되지 않았습니다"** 경고 → **고급** → **autotube(안전하지 않음)로 이동** 클릭 (본인이 만든 앱이라 안전)
4. YouTube 권한 승인 (`youtube.upload`)
5. 인증 완료, 브라우저 탭은 닫아도 됨
6. `~/.config/autotube/token.json` 자동 저장

**이후 모든 업로드는 사용자 개입 0**. 토큰이 만료돼도 refresh_token 으로 자동 갱신.

## 트러블슈팅

### "이 앱은 Google 인증 절차를 완료하지 않았습니다"
정상. **고급** → **(앱 이름)로 이동** 클릭. 본인이 만든 OAuth 앱이므로 안전.

### `quotaExceeded` 에러
일일 quota (10,000 units) 소진. 업로드 1건 = 1,600 units → 하루 최대 6개. 다음 날 자정 (Pacific Time) 초기화.

### `accessNotConfigured`
YouTube Data API v3 가 프로젝트에서 활성화 안 됨. 단계 1 확인.

### 토큰 만료/손상
```bash
rm ~/.config/autotube/token.json
python3 scripts/youtube_upload.py --run output/<run>/  # 재인증
```

### 채널이 여러 개일 때
하나의 Google 계정이 여러 YouTube 채널 (브랜드 채널) 을 가질 수 있음. OAuth 동의 화면에서 어느 채널로 업로드할지 선택 가능. 잘못 골랐으면 token.json 지우고 재인증.

## 보안

- `client_secret.json` 과 `token.json` 둘 다 `chmod 600` 으로 본인만 읽기 가능.
- 절대 git 에 커밋하지 말 것 (둘 다 `~/.config/autotube/` 에 두는 이유).
- token.json 이 유출되면 그 토큰으로 본인 채널에 업로드 가능 → 즉시 [Google Account Security](https://myaccount.google.com/permissions) 에서 `autotube` 앱 액세스 취소.

## 채널 verification (썸네일 업로드)

YouTube 는 **사용자 정의 썸네일** 업로드를 verified 채널에만 허용. Verification 은 전화번호 인증 한 번이면 끝 — [youtube.com/verify](https://www.youtube.com/verify).

verified 안 된 상태에서도 영상 업로드는 됨. 다만 자동 thumbnail 설정은 실패 (스크립트가 알아서 skip) → YouTube 가 자동 생성한 프레임 중 하나가 썸네일로 잡힘. Studio 에서 나중에 수동 업로드 가능.
