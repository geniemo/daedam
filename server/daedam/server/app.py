"""FastAPI 앱 조립.

ADK의 get_fast_api_app이 에이전트 API와 dev UI를 제공하고, 그 위에 리서치
라우트를 얹는다. 실행: `cd server && uv run uvicorn daedam.server.app:app`

확인 경로 (설치된 ADK 2.6.3 소스):
  google/adk/cli/fast_api.py  `get_fast_api_app(*, agents_dir, web, ...)`
    — FastAPI 인스턴스를 돌려주므로 include_router로 확장할 수 있다
"""

from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from starlette.middleware.sessions import SessionMiddleware

from daedam.db import Database, async_url, database_url
from daedam.db.migrate import upgrade_to_head
from daedam.interview.stages import DEFAULT_PROFILE
from daedam.research.service import FixtureResearch, LiveResearch, ResearchService
from daedam.settings import data_root as default_data_root

from .accounts import Accounts
from .auth import configured_providers, create_auth_router
from .evaluation import InterviewEvaluation
from .interview_routes import create_interviews_router
from .live_bridge import create_live_router
from .preparation import InterviewPreparation
from .preparation_routes import create_preparation_router
from .store import InterviewStore

#: interviewer 에이전트 패키지가 들어 있는 디렉터리 (= server/).
_AGENTS_DIR = str(Path(__file__).resolve().parents[2])

# adk web은 실행 디렉터리의 .env를 스스로 읽지만 uvicorn은 아니다 — 명시적으로
# 읽지 않으면 GOOGLE_API_KEY가 없어 run_live의 Gemini 연결이 실패한다.
load_dotenv(Path(_AGENTS_DIR) / ".env")

#: vite 개발 서버 origin. 브라우저는 프록시를 거쳐도 Origin 헤더를 원래
#: 페이지(5173)로 보내는데, ADK 앱의 origin 검사가 이를 거부하면 모든 브라우저
#: POST가 403이 된다. 배포에서는 dist/를 같은 오리진에서 서빙하므로 무관하다.
_DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

logger = logging.getLogger(__name__)


def _research_service(data_root: Path) -> ResearchService:
    """RESEARCH_MODE로 백엔드를 고른다. 기본은 fixture — live는 작업당 $1~7.

    live는 두 가지를 파일에 남긴다. 리포트 원문은 `_raw/`에 파싱 전에 —
    파싱이 틀려도 원문은 남아야 한다. 진행 중인 인터랙션 id는
    `_research_tasks.json`에 — 이게 없으면 20~60분 도는 리서치가 서버 재시작을
    못 넘고, 데모 직전 재기동 한 번에 준비가 통째로 사라진다.
    """
    mode = os.environ.get("RESEARCH_MODE", "fixture")
    if mode != "live":
        logger.info("리서치 백엔드: fixture — 등록해도 실제 조사는 돌지 않습니다")
        return FixtureResearch()
    # 어느 모드로 떠 있는지 로그만 보고 알 수 있어야 한다. 등록 버튼 한 번이
    # 20~60분짜리 유료 작업을 시작하는데, 그걸 화면에서도 로그에서도 구분할 수
    # 없으면 fixture인 줄 알고 누르거나 그 반대가 된다.
    logger.warning(
        "리서치 백엔드: LIVE — 회사 등록 한 건마다 실제 Deep Research가 돕니다"
    )
    return LiveResearch(
        raw_dir=data_root / "_raw",
        state_path=data_root / "_research_tasks.json",
    )


def _session_secret() -> str:
    """세션 쿠키 서명 키.

    설정하지 않으면 프로세스마다 새로 만든다 — 개발에서는 편하지만 재시작마다
    모두 로그아웃되므로, 배포에서는 SESSION_SECRET을 반드시 고정한다.
    """
    secret = os.environ.get("SESSION_SECRET")
    if secret:
        return secret
    logger.warning(
        "SESSION_SECRET이 없어 임시 키를 씁니다 — 재시작하면 모두 로그아웃됩니다"
    )
    return secrets.token_urlsafe(32)


def _interview_profile() -> str:
    """INTERVIEW_PROFILE로 면접 시간 예산을 고른다.

    기본은 demo — 하드캡 9분이라 Live 커넥션 수명(~10분) 안쪽이고, 개발 중
    한 판 돌리는 비용이 작다. 제품 길이(15~20분)는 full이다.
    """
    return os.environ.get("INTERVIEW_PROFILE", DEFAULT_PROFILE)


def create_app() -> FastAPI:
    """ADK 앱에 대담 라우트를 얹어 돌려준다."""
    # 면접 진행 로그(단계 이동·뼈대질문 배달)가 보이게 한다. uvicorn은 자기
    # 로거만 설정하고 루트에는 핸들러를 달지 않아서, 핸들러를 세운 뒤 우리
    # 패키지만 INFO로 올린다 — 서드파티 INFO까지 켜면 로그가 묻힌다.
    # 시각이 없으면 로그로 간격을 못 읽는다 — 재연결 루프와 사용자가 직접
    # 들락거린 것을 구분하지 못한다.
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    for package in ("daedam", "interviewer"):
        logging.getLogger(package).setLevel(logging.INFO)

    # 임베딩 모델(수 초)을 기동 시점에 예열한다 — 첫 검색이 면접 한가운데서
    # 모델 로드로 멈추면 안 된다.
    from daedam.knowledge.embedding import default_embedder

    default_embedder()

    app = get_fast_api_app(
        agents_dir=_AGENTS_DIR, web=True, allow_origins=_DEV_ORIGINS
    )

    # 준비 파이프라인: 리서치 → 파일 저장 → 질문 생성. 완료 산출물은
    # server/data/에 남아 재시작·재데모에서 리서치를 다시 돌리지 않는다.
    #
    # DAEDAM_DATA_DIR로 옮길 수 있다. 시험용 서버를 따로 띄울 때 쓴다 —
    # 데모용 면접이 든 디렉터리에 시험 등록이 섞이면 지우다 실수한다.
    data_root = default_data_root()

    # 스키마를 최신으로 올린 뒤 엔진을 잡는다. 단일 인스턴스 배포라 기동 시
    # 마이그레이션이 안전하다 — 서버를 띄우는 것 말고 할 일이 없어야 한다.
    upgrade_to_head()
    db = Database(database_url(data_root))
    store = InterviewStore(db, data_root)

    # 카카오·구글 설정이 하나라도 있으면 로그인을 요구한다. 없으면 기본 사용자
    # 한 명으로 도는 개발 모드다 — 앱 등록 없이도 서버를 띄울 수 있어야 한다.
    providers = configured_providers()
    if providers:
        logger.info("로그인: %s", " · ".join(providers))
    else:
        logger.warning(
            "로그인 설정이 없어 인증 없이 돕니다 — 모든 데이터가 한 사용자의 것입니다. "
            "KAKAO_CLIENT_ID/SECRET 또는 GOOGLE_CLIENT_ID/SECRET을 설정하십시오."
        )
    accounts = Accounts(db, login_required=bool(providers))

    # 세션 쿠키. OAuth 흐름의 state와 로그인 상태가 여기 담긴다. 비밀키가 바뀌면
    # 모두 로그아웃되므로 배포에서는 반드시 고정 값을 준다.
    app.add_middleware(
        SessionMiddleware,
        secret_key=_session_secret(),
        same_site="lax",
        https_only=os.environ.get("COOKIE_SECURE") == "1",
    )
    app.include_router(create_auth_router(accounts))
    # live는 20~60분짜리 작업이라 1초 폴링이면 조회 API를 수천 번 두드린다.
    # fixture는 12초 안에 끝나므로 촘촘히 봐야 진행 화면이 자연스럽다.
    live = os.environ.get("RESEARCH_MODE") == "live"
    preparation = InterviewPreparation(
        research=_research_service(data_root),
        store=store,
        poll_interval_s=30.0 if live else 1.0,
    )
    app.include_router(create_preparation_router(preparation, accounts))
    # 홈 화면이 그릴 카드 목록. 프론트가 자기 메모리로 들고 있으면 새로고침에
    # 사라지고, 준비 안 된 면접을 시작하려다 브리지에서 거절당한다.
    # 면접이 끝나면 브리지가 이걸 깨우고, 분석 화면이 결과를 기다린다.
    evaluation = InterviewEvaluation(store)
    app.include_router(
        create_interviews_router(store, preparation, accounts, evaluation)
    )

    # 음성 브리지는 자기 러너로 돈다. ADK 앱(dev UI) 쪽 세션 저장소와는
    # 분리돼 있다 — 제품 경로는 /ws/interview 하나다. 준비 데이터 저장소를
    # 공유해, 파이프라인이 만든 것을 브리지가 세션에 시딩한다.
    from interviewer.agent import root_agent

    from . import fillers

    # 추출(Grok, ~2초)이 도는 동안 면접관 목소리 클립으로 침묵을 메운다.
    # 여기(조립)에서 거는 이유: interviewer 패키지는 서버(웹소켓)를 몰라야
    # 하고, 콜백의 전송 상대는 브리지가 커넥션마다 등록한다.
    root_agent.before_tool_callback = fillers.play_filler_before_tool

    # 대화 세션도 데이터베이스에 둔다. 프로세스 메모리에 있으면 서버가
    # 재시작될 때 진행 중인 면접이 통째로 끊긴다 — 15~20분짜리라 실제로
    # 겪는다. ADK가 async 엔진을 만들므로 같은 데이터베이스의 async URL을 준다.
    runner = Runner(
        app_name="daedam",
        agent=root_agent,
        session_service=DatabaseSessionService(db_url=async_url(db.url)),
        artifact_service=InMemoryArtifactService(),
        memory_service=InMemoryMemoryService(),
    )
    app.include_router(
        create_live_router(
            runner,
            store,
            accounts,
            profile=_interview_profile(),
            evaluation=evaluation,
        )
    )
    return app


app = create_app()
