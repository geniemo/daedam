# 대담 (Daedam)

AI 음성 모의면접 서비스. KindredPM voice AI agent 부트캠프 프로젝트 —
**평가 대상은 voice agent**이고 나머지는 그것을 받쳐주는 구조입니다.

## 레퍼런스 — 웹 검색보다 여기를 먼저 보세요

| 경로 | 내용 |
|---|---|
| `~/refs/adk-docs/docs/` | **ADK 공식 문서 전문** (google/adk-docs, 마크다운 232개) |
| `~/refs/adk-docs/docs/live/` | Live API 툴킷 — `dev-guide/part1~5.md`가 핵심 |
| `design_handoff_daedam/README.md` | 디자인 핸드오프 616줄. 화면 10개 스펙 + 디자인 토큰 |

ADK 관련 질문은 `~/refs/adk-docs`를 grep하십시오. adk.dev는 리다이렉트가 많고
WebFetch가 요약하면서 코드 예제를 잘라먹습니다. 로컬 마크다운에는 소스 링크까지
그대로 있습니다.

문서와 실제 동작이 다르면 **설치된 패키지가 정답**입니다 —
`server/.venv/lib/python3.12/site-packages/google/adk/`. 문서는 버전이 밀릴 수 있지만
그건 지금 돌아가는 코드입니다.

업데이트: `cd ~/refs/adk-docs && git pull`

## 구조

```
web/                     Vite + React 프론트엔드 (완성)
design_handoff_daedam/   디자인 핸드오프 (읽기 전용, 수정하지 말 것)
server/                  ADK 백엔드 (미착수)
```

`web/`의 상세는 `web/README.md` 참고.

## 모델 스택

| 용도 | 모델 | 비고 |
|---|---|---|
| 실시간 음성 면접 | `gemini-3.1-flash-live-preview` | 네이티브 오디오. 함수 호출은 **순차 전용** |
| 회사 리서치 | Gemini Deep Research | 비동기 전용, 10~15분, 작업당 $1~3 |
| 의미 검색 임베딩 | `gemini-embedding-001` | 768차원. 로컬 모델은 폴백(`SEARCH_EMBEDDINGS=local`) |
| 파볼 곳 추출 (면접 중) | `gemini-3.5-flash-lite` | 실측 1.2초 — 지연이 곧 침묵이다 |
| 질문 생성·어휘·코칭 | `gemini-3.7-flash` | 오프라인 배치. 질이 우선 |

**전부 Gemini입니다.** 앞서 오프라인 작업은 Grok(xAI)이었는데(부트캠프 협찬
토큰) 벤더를 하나로 줄였습니다 — 키도 하나, 장애 지점도 하나입니다. 호출 형태가
`chat.completions.parse` + Pydantic으로 같아서 Gemini의 OpenAI 호환 엔드포인트로
그대로 옮겼습니다. 모델 선택은 `server/daedam/llm.py` 한 곳에 있습니다.

## 확정된 결정

- **Python 환경은 uv** (conda 아님). ADK 스택이 순수 파이썬이라 conda의 이점이 없고,
  Cloud Run 컨테이너 배포에서 uv가 유리합니다. Python 3.12.
- **프론트는 Vite SPA** (Next.js 아님). 백엔드가 Python이라 Next.js의 서버 절반이
  쓰이지 않고, `dist/`를 FastAPI에 mount하면 컨테이너 하나로 끝납니다.
- **Deep Research는 백엔드 전용.** 비동기 전용(`background=True`)이고 20~60분,
  작업당 $1~7입니다. 프론트에 두면 키 노출 = 금전 손실.

## 반드시 지켜야 하는 제약

**오디오 규격은 협상 대상이 아닙니다.** ADK는 포맷 변환을 하지 않습니다.
입력 16-bit PCM/16kHz/mono, 출력 24kHz/mono. 그래서 AudioContext가 2개입니다.

**면접(15~20분)이 모든 관련 한도보다 깁니다.**

| 한도 | 값 |
|---|---|
| Live API audio-only 세션 | 15분 (`contextWindowCompression` 없이) |
| Live API 커넥션 수명 | ~10분 |
| Cloud Run 요청 타임아웃 | 기본 **5분** → `--timeout=3600` 필수 |

재연결 + `sessionResumption`은 에러 처리가 아니라 **정상 동작 경로**입니다.

**비용 통제.** Deep Research는 개발 중 반복 호출하면 금방 수십 달러입니다.
`RESEARCH_MODE=fixture|live` 스위치를 서버에 두고 기본값은 fixture.
데모도 미리 돌려둔 결과를 씁니다 (라이브는 40분 걸려서 현장에서 못 돌립니다).

## Git

### 커밋

형식: `<type>(<scope>): <제목>`

- 제목은 **한국어**, 명사형 종결(~추가 / ~수정 / ~분리), 50자 내외, 마침표 없음
- type: `feat` `fix` `docs` `chore` `refactor` `test` `perf`
- 본문은 **"왜"가 필요할 때만.** 무엇을 했는지는 diff가 말합니다
- **트레일러·서명 줄을 쓰지 않습니다** (`Co-Authored-By`, `Generated with` 등)
- 예: `feat(agent): 뼈대질문 배달 툴 추가` / `fix(web): barge-in 시 재생 버퍼 플러시 누락 수정`

| scope | 대상 |
|---|---|
| `web` | 프론트엔드 (Vite/React) |
| `agent` | ADK 에이전트·툴·프롬프트 |
| `interview` | 순수 면접 로직 (질문 풀, 단계·시간 예산) |
| `research` | Deep Research 배치·청킹 |
| `server` | FastAPI 라우트·WebSocket·세션 |
| `eval` | 평가 파이프라인 (배치 STT, 음향 지표) |
| `infra` | 빌드·의존성·도구 설정 |

여러 계층에 걸치면 scope를 생략합니다. 계층을 넘나드는 커밋이 잦다면 그건 커밋을 쪼개라는 신호입니다.

### 커밋 단위

의미 있는 개발 단위가 완성될 때 커밋합니다. 로그 라벨·주석·오타 같은 잔손질은 별도 커밋하지 말고 다음 기능 커밋에 묶습니다. 단 미완성 상태로 오래 쌓아두지도 않습니다.

### 브랜치

- **`main`은 항상 데모 가능한 상태를 유지합니다.** 주간 시연은 main에서 합니다
- 브랜치 이름은 `<type>/<슬러그>` — 커밋 type과 같은 어휘 (`feat/question-tool`)
- **예외**: 첫 데모 가능 상태(음성 면접 E2E 동작)에 도달하기 전까지는 main 직행을 허용합니다. 뼈대를 세우는 단계에 PR 규율은 비용만 됩니다
- 그 이후의 기능·수정 작업은 브랜치에서

### PR

- 제목은 커밋 컨벤션 형식
- 본문에 **"왜"와 "어떻게 검증했는지"**를 짧게. PR 본문이 주간 보고 재료를 겸합니다
- 머지는 `--no-ff` — PR 경계를 이력에 남기고 내부의 의미 단위 커밋을 보존합니다. 머지 후 브랜치 삭제

### 실행 규칙

- **커밋·푸시·머지 실행은 사용자 승인 후에만.** 시점과 메시지는 내가 능동적으로 제안합니다
- `.env`, API 키, 녹음 파일, `dist/`, `.venv/`, `node_modules/`는 커밋하지 않습니다

## 작업 규칙

- **ADK·Gemini·genai의 API 시그니처를 훈련 지식으로 쓰지 마십시오.** 코드 작성 전
  `~/refs/adk-docs` 또는 설치된 패키지 소스로 확인하고, **확인한 경로/URL을 주석으로 남깁니다.**
- 아키텍처급 결정(스택 교체, 계층 구조 변경, 새 외부 의존성)은 구현 전에 사용자에게 질문합니다.
- 오디오 레이트 값(파형 진폭, 링 스케일)은 **React state에 넣지 마십시오.**
  ref → `style` 직접 쓰기. `web/src/screens/Interview.tsx` 참고.
- 디자인 값은 핸드오프 README의 hex/px를 그대로 씁니다. 반올림 금지.
- 프론트 변경 후 `cd web && npm run build && npm run smoke` — smoke가 브라우저 없이
  10개 화면을 실제 렌더해서 런타임 에러를 잡습니다.
