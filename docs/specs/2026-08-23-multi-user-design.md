# 다중 사용자 전환 설계

단일 사용자 로컬 앱을 회원제 서비스로 바꾼다. 세 단계로 나누고, 각 단계가
끝날 때마다 데모 가능한 상태를 유지한다.

## 지금 상태와 문제

| 사실 | 근거 | 서비스에서의 문제 |
|---|---|---|
| 인증 개념이 없다 | `_USER_ID = "user"` 상수 하나 | — |
| 모든 리소스가 면접 id로만 열린다 | `GET /api/interviews/{id}/audio`가 파일을 그대로 반환 | id만 알면 남의 녹음·지원서를 읽는다 |
| 면접 소켓도 id만으로 붙는다 | `/ws/interview?card=`, 붙는 쪽이 기존 커넥션을 끊는다 | 남의 면접에 들어가 밀어낼 수 있다 |
| 카드 1개 = 면접 1회 | 새 면접 시작 시 `InterviewRecording.discard` | 두 번째 면접이 첫 면접을 지운다 |
| 데이터가 `data/{id}/` 평면 구조 | `FileInterviewStore` | 사용자 스코프가 없다 |
| ADK 세션이 프로세스 메모리 | `InMemoryRunner` | 재시작하면 진행 중 면접이 끊긴다 |

`store.py` 첫 주석이 이 전환을 이미 예고해 두었다 — "전환 트리거(동시 사용자,
목록 질의, 다중 인스턴스 배포)가 실제로 오면 SQLite로 갈아 끼운다."

## 데이터 모델

핵심 변화는 **준비 데이터와 면접 기록의 분리**다. 준비(리서치)는 비싸고
재사용해야 하며, 면접은 반복이 곧 제품 가치다.

```
User                      사용자
  id, provider(kakao|google), provider_user_id
  email, name, avatar_url          -- 카카오는 이메일이 선택 동의라 nullable
  created_at

Application               준비 데이터 (지금의 "카드")
  id                               -- 리서치 task_id를 그대로 쓴다
  user_id → User
  company, role, applicant_name
  application, report, uncertain   -- JSON
  questions, vocabulary            -- JSON, null이면 아직 준비 중
  created_at, updated_at

InterviewSession          면접 1회
  id, application_id → Application
  started_at, ended_at             -- ended_at이 null이면 아직 진행 중
  transcript, feedback             -- JSON, null이면 아직 없음

CreditLedger              크레딧 원장 (3단계)
  id, user_id, delta, reason, ref_id, created_at
  잔액 = SUM(delta)
```

**오디오만 디스크에 남긴다** — `data/{application_id}/{session_id}/mic.pcm|wav`.
전사·피드백은 DB의 JSON 칼럼이다. "지난 면접들"을 질의해야 하고, 파일과 DB로
나뉘면 정합성을 두 곳에서 지켜야 한다. 오디오는 20분에 수십 MB라 DB에 넣지
않는다.

**크레딧을 잔액 칼럼이 아니라 원장으로 두는 이유**: 언제 왜 늘고 줄었는지가
남아야 환불·정산·문의 대응이 된다. 잔액은 합으로 계산한다.

## 인증

- Authlib의 Starlette 통합으로 카카오·구글 OAuth 2.0 authorization code flow
- 서버 세션은 Starlette `SessionMiddleware`(서명 쿠키). JWT를 쓰지 않는 이유는
  단일 인스턴스이고, 로그아웃 즉시 무효화가 쿠키 쪽이 단순하기 때문이다
- WebSocket도 같은 쿠키를 읽는다 — 면접 소켓이 인증의 구멍이 되면 안 된다

**소유권 검사는 조회를 사용자로 스코프하는 방식**이다. 남의 리소스는 403이
아니라 **404**로 답한다 — 존재 여부 자체를 흘리지 않는다.

## 단계

각 단계 끝에서 데모가 되어야 한다. 스키마는 1단계에서 한 번에 세우되(User
포함), 인증 없이 도는 동안은 기본 사용자 한 명을 자동 생성해 기존 흐름을
유지한다. 2단계는 그 자리에 진짜 사용자를 끼우는 작은 diff가 된다.

### 1단계 — 저장소 DB 전환 + 면접 1:N

- SQLAlchemy + Alembic 도입, SQLite로 시작
- `FileInterviewStore` → DB 저장소. 인터페이스를 유지해 preparation·evaluation의
  변경을 최소화한다
- `InterviewSession` 도입 — 면접마다 새 행. 기록을 지우지 않고 쌓는다
- ADK 세션을 `DatabaseSessionService`로. **세션 id를 카드 id가 아니라 면접
  세션 id로 바꾼다** — 안 그러면 두 번째 면접이 첫 면접 대화를 이어받는다
- 기존 `data/` 파일을 DB로 옮기는 마이그레이션 스크립트
- 프론트: 면접 이력 표시

### 2단계 — 인증

- 카카오·구글 OAuth, 세션 쿠키, `current_user` 의존성
- 모든 라우트와 WebSocket에 소유권 검사
- 프론트: 랜딩·로그인·로그아웃, 헤더의 사용자 정보
  (`APPLICANT_NAME` 하드코딩 상수가 여기서 없어진다)

### 3단계 — 크레딧

- 원장 테이블, 가입 시 무료 크레딧 지급
- 등록(리서치 시작 전)과 면접(세션 시작 시) 차감, 잔액 부족 시 차단
- 프론트: 잔액 표시, 소진 안내
- 실제 결제(PG) 연동은 범위 밖 — 사업자등록이 선행되어야 한다

## 구현하며 달라진 것

설계와 코드가 갈린 곳만 적는다. 나머지는 위 그대로다.

**동기 SQLAlchemy를 쓴다.** 준비·평가 파이프라인이 전담 스레드로 돌고
(`preparation.py`·`evaluation.py`) 라우트도 동기 함수라 스레드풀에서 실행된다.
async를 끼우면 스레드마다 이벤트 루프를 세워야 하는데 얻는 것이 없다. ADK의
대화 세션 저장소만 async를 요구하므로 그쪽에는 같은 데이터베이스의 async URL을
준다(`daedam.db.engine.async_url`) — 엔진 둘이 한 데이터베이스를 보고 서로의
테이블을 건드리지 않는다.

**재접속과 새 면접을 가르는 기준.** "끝나지 않은 판이 있는가"다. 커넥션이 끊긴
것과 면접이 끝난 것은 다르다 — Live 커넥션 수명이 ~10분이라 15~20분 면접은
반드시 재접속한다. 창을 닫고 돌아오지 않은 판은 한 시간 뒤 닫고 피드백만
만든다(`InterviewStore.resume_or_abandon`).

**피드백 생성을 면접이 끝난 뒤에만 깨운다.** 앞서는 커넥션이 끊길 때마다
깨웠는데, 재접속이 정상 경로라 한 판에 Grok 호출이 여러 번 나갔다.

**전사는 두 곳에 있다.** 디스크의 `transcript.json`은 녹음이 재접속을 넘겨
이어 쓰기 위한 작업 파일이고, 데이터베이스의 사본이 질의 대상이다.

**Alembic이 앱 로거를 끄는 문제.** 기동 시 마이그레이션을 돌리는데, alembic의
`fileConfig`가 기존 로거를 끄고 루트 포매터까지 갈아 치웠다 — 그 뒤 면접 로그가
통째로 사라지고 남은 줄은 시각을 잃었다(실측). `config.attributes
["configure_logger"] = False`로 막았다. 시각이 없으면 재연결 루프와 사용자가
직접 들락거린 것을 구분할 수 없다.

## 배포 전제

Azure VM 단일 인스턴스. 그래서 1단계는 SQLite로 충분하고, 기동 시 예열하는
임베딩 모델(수 GB)도 한 번만 로드된다. Postgres 전환은 `DATABASE_URL`만 바꾸면
되도록 SQLAlchemy 위에 세운다 — 드라이버(`asyncpg`)를 지금 함께 넣어 전환
시점에 의존성 작업이 없게 한다.

기동할 때 스키마를 최신으로 올린다(`daedam.db.migrate`). 서버를 띄우는 것 말고
할 일이 없어야 한다는 요구에서 나왔고, 단일 인스턴스라 안전하다. **인스턴스를
늘리면 그 호출을 빼고 배포 파이프라인에서 `alembic upgrade head`를 한 번만
돌려야 한다** — 여러 프로세스가 동시에 올리면 서로 막는다.

개발에서는 vite가 5173에 따로 뜨므로 로그인 뒤 돌아갈 곳을 지정해야 한다
(`APP_BASE_URL=http://localhost:5173`). 배포에서는 같은 오리진이라 비워 둔다.

## 범위 밖

- 실제 결제 연동 (사업자등록 선행)
- 이용약관·개인정보처리방침과 동의 흐름 (사용자와 함께 확인하기로 함)
- 면접을 반복할 때 질문을 달리하는 것 — 지금은 뽑아 둔 질문 풀을 그대로 쓴다
- 리서치의 지원서 개인화 심화. 현재 리서치 프롬프트는 지원서 **항목 제목만**
  넘긴다(`research/service.py`) — 같은 회사·직무에 문항이 비슷하면 실질적으로
  같은 리포트가 나온다. 별건으로 다룬다
- 준비 데이터(카드) 삭제. 지금은 지우는 길이 없어, 잘못 등록하면 목록에 남는다
- 크레딧 가격의 근거. 지금 값(가입 5 / 등록 3 / 면접 1)은 자리를 잡아 둔 것이고,
  실제 원가 조사 위에서 정해야 한다
