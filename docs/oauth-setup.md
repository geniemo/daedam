# 카카오·구글 로그인 붙이기

콘솔에서 앱을 등록하고 `.env`에 키를 넣는 절차. 한 번만 하면 된다.

키가 하나도 없으면 서버는 로그인 없이 돈다 — 모든 데이터가 기본 사용자 한 명의
것이고 기동 로그가 그 사실을 남긴다. **키를 하나라도 넣는 순간 로그인이 강제된다.**

## 먼저 정할 것 — 서비스 주소

콜백(Redirect URI)이 콘솔에 등록한 값과 **글자 하나까지 같아야** 한다. 형식은
이렇다.

```
{서버 주소}/api/auth/kakao/callback
{서버 주소}/api/auth/google/callback
```

| 환경 | 서버 주소 |
|---|---|
| 로컬 개발 | `http://localhost:8000` |
| Azure VM | `https://{도메인 또는 공인 IP}` |

로컬에서 `8000`인 이유: 브라우저는 vite(5173)를 보지만 로그인 요청은 프록시를
지나 서버로 가고, 서버가 자기 주소로 콜백을 만든다. 그래서 콘솔에는 **8000**을
등록하고, 로그인 뒤 SPA로 돌아오도록 `.env`에 `APP_BASE_URL=http://localhost:5173`을
넣는다.

로컬과 배포를 함께 쓰려면 콘솔에 **두 개 다 등록**하면 된다. 여러 개를 넣을 수
있다.

---

## 카카오

콘솔: <https://developers.kakao.com/console/app>

### 1. 애플리케이션 추가
[내 애플리케이션] > [애플리케이션 추가하기]. 앱 이름 "대담", 회사명은 아무거나.
카카오 계정으로 로그인해야 한다.

### 2. [플랫폼 키] > [REST API 키] — 여기서 세 가지를 한 번에

콘솔이 개편되면서 예전 **[앱 키]** 메뉴가 **[플랫폼 키]**로 바뀌었고, 예전
**[카카오 로그인] > [보안]**에 있던 클라이언트 시크릿도 이 아래로 들어왔다.
([앱과 앱 키 변경 사항](https://developers.kakao.com/docs/ko/getting-started/app-key-migration))
그래서 이 화면 하나에서 다음 셋을 끝낸다.

**(a) REST API 키** — 이 값이 `KAKAO_CLIENT_ID`다.
(JavaScript 키·네이티브 앱 키·어드민 키가 아니다.)

**(b) Redirect URI** — 위에서 정한 주소를 넣는다. 틀리면 `KOE006`이다.

```
http://localhost:8000/api/auth/kakao/callback
```

**(c) 클라이언트 시크릿** — 이 값이 `KAKAO_CLIENT_SECRET`이다. REST API 키는
시크릿 기능이 **켜진 상태로 생성**되므로 대개 값을 복사하기만 하면 된다.
활성화 여부가 따로 보이면 "사용함"인지 확인한다.

### 3. 카카오 로그인 켜기
[카카오 로그인] > [일반]에서 활성화 설정을 **ON**으로. 이걸 안 켜면 로그인
요청이 `KOE004` 오류로 떨어진다.

### 4. OpenID Connect 켜기 ★
[카카오 로그인] > [OpenID Connect]를 **ON**으로.

**이걸 빠뜨리면 로그인이 됐다가 마지막에 실패한다.** 우리 코드는 ID 토큰에서
사용자 정보를 읽는데, OIDC가 꺼져 있으면 ID 토큰이 아예 안 온다. 그때 서버는
502와 함께 "제공자가 사용자 정보를 주지 않았습니다"를 낸다 — 이 메시지가 보이면
십중팔구 여기다.

### 5. 동의항목 설정
[카카오 로그인] > [동의항목]에서 우리가 요구하는 것을 켠다.

| 동의항목 | scope id | 쓰는 곳 |
|---|---|---|
| 닉네임 | `profile_nickname` | 면접관이 부르는 이름 · 전사 어휘 힌트 |
| 프로필 사진 | `profile_image` | 헤더 아바타 |
| 카카오계정(이메일) | `account_email` | 계정 식별 보조 |

**이메일은 앱 상태에 따라 못 켤 수 있다.** 비즈니스 앱 전환이 필요하다고 나오면
지금은 건너뛰고 `.env`에 이렇게 낮춰 둔다.

```
KAKAO_SCOPE=openid profile_nickname profile_image
```

이메일은 선택 정보라 없어도 로그인은 성립한다(`users.email`이 nullable).
**콘솔에서 안 켠 항목을 요구하면 제공자가 로그인을 통째로 거절한다** — 켠 것만
적어야 한다.

---

## 구글

콘솔: <https://console.cloud.google.com/auth/clients>

### 1. 프로젝트 만들기
없으면 상단에서 새 프로젝트를 만든다. 기존 프로젝트를 재사용해도 된다.

### 2. OAuth 동의 화면 구성
클라이언트를 만들기 전에 동의 화면이 있어야 한다.
[Google 인증 플랫폼] > [브랜딩]에서 앱 이름·지원 이메일을 채운다.

**User type을 External로** 두면 아무나 로그인할 수 있다. Internal은 같은 조직
계정만 된다.

### 3. 대상(Audience) — 테스트 사용자
게시 상태가 **테스트(Testing)**면 [대상] > [테스트 사용자]에 등록한 계정만
로그인된다. 처음에는 본인 구글 계정을 넣어 두고, 홍보 영상으로 사람을 받을
때 **[앱 게시(Publish)]**로 올린다.

> 게시하지 않은 채로 사용자를 받으면 "이 앱은 확인되지 않았습니다" 화면에서
> 막힌다. 영상 촬영 전에 반드시 확인할 것.

### 4. 클라이언트 만들기
[클라이언트] > [클라이언트 만들기] > 애플리케이션 유형 **웹 애플리케이션**.

**승인된 리디렉션 URI**에 위에서 정한 주소를 넣는다.

```
http://localhost:8000/api/auth/google/callback
```

정확히 일치해야 한다 — 끝의 슬래시 하나도 다르면 안 된다.

만들면 **클라이언트 ID**와 **클라이언트 보안 비밀번호**가 나온다. 각각
`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`이다.

---

## .env 채우기

`server/.env`에 넣는다. 없으면 `cp .env.example .env`.

```bash
KAKAO_CLIENT_ID=<REST API 키>
KAKAO_CLIENT_SECRET=<클라이언트 시크릿>
GOOGLE_CLIENT_ID=<클라이언트 ID>
GOOGLE_CLIENT_SECRET=<클라이언트 보안 비밀번호>

# 세션 쿠키 서명 키. 비우면 기동할 때마다 모두 로그아웃된다.
SESSION_SECRET=<아래 명령으로 생성>

# 이 서버의 공개 주소. 콘솔에 등록한 콜백에서 /api/auth/... 앞부분이다.
SERVER_BASE_URL=http://localhost:8000

# 로그인 뒤 돌아갈 곳. 개발에서만 필요하다(vite가 5173에 따로 뜬다).
APP_BASE_URL=http://localhost:5173
```

**한쪽만 채우면 그 제공자는 등록되지 않는다.** `CLIENT_ID`와 `CLIENT_SECRET`이
둘 다 있어야 한다 — 반쪽 설정으로 뜨면 버튼은 보이는데 눌리지 않는다. 그래서
카카오만 먼저 붙이고 구글은 비워 둔 채로 테스트할 수 있다.

`SERVER_BASE_URL`을 비우면 콜백 주소를 요청 헤더에서 유도하는데, 그러면 같은
서버인데도 `localhost`로 들어왔는지 `127.0.0.1`로 들어왔는지에 따라 값이 갈린다
(실측). 등록값은 하나뿐이므로 못 박아 두는 편이 안전하고, 리버스 프록시 뒤에서는
필수다.

`SESSION_SECRET` 생성:

```bash
cd server && uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

배포(HTTPS)에서는 `COOKIE_SECURE=1`도 켠다.

**`.env`는 커밋하지 않는다.** 이미 gitignore에 있다.

---

## 확인

서버를 재기동하고 기동 로그를 본다.

```
INFO daedam.server.app: 로그인: kakao · google
```

이 줄이 뜨면 붙은 것이다. "로그인 설정이 없어 인증 없이 돕니다"가 뜨면 키가
안 읽힌 것이다(`.env` 위치나 오타).

```bash
curl -s localhost:8000/api/auth/providers
# {"providers":["kakao","google"]}
```

그다음 브라우저에서 `http://localhost:5173`을 열면 랜딩 화면에 로그인 버튼이
그려진다. 눌러서 끝까지 통과하면 헤더에 이름과 크레딧이 뜬다.

### 잘 안 될 때

| 증상 | 원인 |
|---|---|
| `KOE004` | 카카오 로그인 활성화가 꺼져 있다 (3번) |
| `KOE006` | Redirect URI가 콘솔 등록값과 다르다 (2-b) |
| "제공자가 사용자 정보를 주지 않았습니다" (502) | 카카오 OpenID Connect가 꺼져 있다 (4번) |
| 동의 화면에서 거절당함 | 콘솔에서 안 켠 동의항목을 요구했다 — `KAKAO_SCOPE`를 낮춘다 (5번) |
| "이 앱은 확인되지 않았습니다" | 구글 게시 상태가 테스트인데 테스트 사용자에 없다 (3번) |
| 로그인 뒤 ADK dev UI가 뜬다 | `APP_BASE_URL`이 비어 있다 |
| 로그인 버튼이 안 보인다 | `CLIENT_ID`·`CLIENT_SECRET` 중 한쪽만 찼다 |
| 재시작할 때마다 로그아웃된다 | `SESSION_SECRET`이 비어 있다 |

---

## 어디까지 실제로 돌려 봤나

**카카오는 통과했다.** redirect → 동의 → 콜백 → 토큰 → 프로필 파싱까지 실제
로그인으로 확인했다. 그 과정에서 문서만 보고는 알 수 없던 것 셋이 나왔고, 위
본문에 반영돼 있다 — 동의항목 id를 scope로 써야 하는 것, OpenID Connect를 따로
켜야 하는 것, 토큰 교환이 `client_secret_post`여야 하는 것.

**구글은 아직 왕복해 본 적이 없다.** 다만 카카오에서 데였던 세 지점은 미리
확인해 두었다 (2026-08-29, discovery 문서 직접 조회):

```
$ curl -s https://accounts.google.com/.well-known/openid-configuration
token_endpoint_auth_methods_supported: ['client_secret_post', 'client_secret_basic']
scopes_supported:                      ['openid', 'email', 'profile']
```

- `client_secret_basic`을 지원하므로 authlib 기본값 그대로 된다. 카카오처럼
  `_TOKEN_AUTH_METHOD`에 넣을 것이 없다.
- scope가 표준 이름 그대로다. 카카오의 동의항목 id 같은 예외가 없다.
- 프로필은 표준 OIDC 클레임(`sub`·`name`·`email`·`picture`)이라
  `_profile_from`이 손댈 것 없이 받는다.

남은 위험은 콘솔 쪽이다 — 게시 상태와 리디렉션 URI 일치. 둘 다 위에 적어 뒀다.
