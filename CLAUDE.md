# 대담 (daedam) — AI 모의면접 voice agent

회사·직무·지원서 입력 → 사전 리서치 → 실시간 한국어 음성 면접(10–12분, 친절/압박 모드, 아바타) → 정량 피드백 리포트. KindredPM 부트캠프 캡스톤.

기획 단일 기준(SSOT): [설계서 v2 (Notion)](https://app.notion.com/p/3a3f3d78237a8192ae5eda8862681dba) — 설계 결정 로그(D1–D12)·열린 항목 체크리스트는 여기서 관리

## 스택 (변경은 반드시 사용자와 상의)
- 음성: xAI Grok. Phase A = 캐스케이드(Grok STT→LLM→TTS + Silero VAD), Phase B = RealtimeModel(네이티브)로 스왑
- 프레임워크: LiveKit Agents(Python) + livekit-plugins-xai + livekit-plugins-silero — requirements.txt에 버전 고정
- 미디어: LiveKit Cloud(SFU만 사용). 워커·백엔드는 자체 운영, 워커는 아웃바운드 접속만
- 백엔드: FastAPI + SQLite. 답변별 녹음은 로컬 디스크
- 리서치: Gemini Deep Research — 오프라인 배치로 5개 회사 사전 실행 후 영속화. 라이브 세션 중 호출 금지
- 평가: 답변별 녹음 → Grok STT 배치(단어 타임스탬프) + librosa 음향 특징 + Grok Chat 내용 평가
- 프론트: React + Vite + Tailwind + LiveKit Client SDK. 아바타는 Web Audio AnalyserNode 진폭 반응
- 배포: Azure VM Korea Central, Docker Compose + Nginx + Let's Encrypt. 인바운드는 443만

## 아키텍처 원칙 (위반 금지)
1. 계층 분리: `interview/` = 순수 Python 대화·평가 로직(LiveKit import 금지) / `agent/` = LiveKit 어댑터 / `server/` = FastAPI / `research/` = 오프라인 배치
2. 게임 규칙(질문 풀·시간 강제·평가)은 전부 서버 코드에. 모델의 내부 시계·자율 판단에 시간 관리를 맡기지 않는다 — `get_next_question` tool이 경과 시간을 확인해 다음 질문 또는 마무리 지시를 반환
3. 질문 풀은 세션 시작 전에 초과 생성 + 우선순위 정렬. 세션 중 tool은 조회만 하며 즉시 반환해야 한다(리서치·생성 호출 금지 — 침묵 방지)
4. Phase A(캐스케이드)에서 barge-in, 문장 단위 TTS 스트리밍을 구현하지 않는다 — Phase B에서 무의미해지는 투자
5. 면접 모드(친절/압박)는 세션 시작 시 system instruction으로 고정. 세션 중 변경 없음

## 작업 규칙
- LiveKit/xAI/Gemini의 API·플러그인 시그니처는 훈련 지식으로 쓰지 말 것. 코드 작성 전 docs.livekit.io / docs.x.ai / ai.google.dev 최신 문서를 웹으로 확인하고, 확인한 URL을 주석으로 남긴다
- 아키텍처급 결정(스택 교체, 계층 구조 변경, 새 외부 의존성 추가)은 구현 전에 사용자에게 질문
- E2E 지연 계측은 구간별(턴 감지 / API 호출별 / 재생 시작)로 기록. 기준선: Grok 네이티브 TTFA ~0.78s
- 커밋은 작은 단위로 자주. `.env`·키·녹음 파일 커밋 금지(.gitignore 유지)
- 한국어 UX가 기본. 프롬프트·TTS 확인은 한국어 기준으로

## 커밋 컨벤션 (Conventional Commits)
- 형식: `<type>(<scope>): <제목>` — 제목은 한국어, 명사형 종결(~추가/수정/분리), 50자 내외, 마침표 없음
- type: feat | fix | docs | chore | refactor | test | perf
- scope: interview | agent | server | research | web | infra — 계층 디렉토리와 일치, 해당 없으면 생략
- 본문은 "왜"가 필요할 때만 작성. footer·트레일러는 쓰지 않는다
- 예: `feat(agent): 캐스케이드 음성 루프 뼈대 추가` / `fix(server): 토큰 발급 시 room 이름 충돌 수정`

## 실행·검증 (개발 환경: Azure VM, tmux 세션 내에서 작업)
- 기본 개발 루프: VM에서 `python agent/main.py dev` 실행 → Windows Chrome에서 LiveKit Cloud 대시보드의 Agent Console(구 Agents Playground) 접속해 대화. 워커는 아웃바운드만 사용 — 인바운드 포트·오디오 장치 불필요
- 워커·Claude Code는 tmux 세션에서 실행 (SSH 끊김 대비). 세션명: dev
- 순수 로직 테스트: `pytest interview/` — 음성 없이 실행 가능해야 함
- xAI 스모크 테스트: `python scripts/smoke_xai.py` (TTS 한국어 생성 → WAV 저장 → STT 왕복 확인). WAV는 로컬로 내려받아 재생 확인 (`scp` 또는 VS Code Remote)
- VM 디스크를 원본으로 취급하지 말 것 — 작은 커밋, 자주 push. 프론트 dev 서버는 SSH 터널(`-L 5173:localhost:5173`)로 확인
