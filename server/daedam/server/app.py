"""FastAPI 앱 조립.

실행: `cd server && uv run uvicorn daedam.server.app:app`

**ADK의 `get_fast_api_app`을 쓰지 않는다.** 그것은 에이전트 API와 dev UI를
통째로 얹어 주는데, 우리는 그중 아무것도 쓰지 않으면서 위험만 물었다 —
인증 없는 `/run`·`/run_sse`·`/run_live`와 세션 조회·삭제 API가 열려 있어서
누구나 에이전트를 돌려 우리 돈을 쓰고 남의 면접 대화를 읽을 수 있었다.
제품 경로는 `/ws/interview` 하나이고, 음성 브리지는 자기 Runner로 돈다.

개발 중 에이전트를 직접 찔러 보려면 `adk web`을 따로 띄우면 된다 — 그건
로컬에서만 열리고 이 앱과 무관하다.
"""

from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from starlette.middleware.sessions import SessionMiddleware

from daedam.db import Database, async_url, database_url
from daedam.db.migrate import upgrade_to_head
from daedam.interview.stages import DEFAULT_PROFILE
from daedam.research.service import FixtureResearch, LiveResearch, ResearchService
from daedam.settings import SERVER_DIR
from daedam.settings import data_root as default_data_root

from . import preflight
from .accounts import Accounts
from .auth import configured_providers, create_auth_router
from .credit_routes import create_credit_router
from .credits import Credits
from .evaluation import InterviewEvaluation
from .health import create_health_router
from .interview_routes import create_interviews_router
from .live_bridge import create_live_router
from .preparation import InterviewPreparation
from .preparation_routes import create_preparation_router
from .retention import start_retention_timer
from .store import InterviewStore

# uvicorn은 .env를 스스로 읽지 않는다 — 명시적으로 읽지 않으면 GOOGLE_API_KEY가
# 없어 run_live의 Gemini 연결이 실패한다.
load_dotenv(SERVER_DIR / ".env")

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


class _ImmutableAssets(StaticFiles):
    """해시가 붙은 빌드 자산(`/assets/index-XXXX.js`) — 1년 캐시.

    파일 이름에 내용 해시가 들어 있어 같은 이름이면 같은 내용이다. 캐시 헤더가
    없으면 브라우저 휴리스틱에 맡겨지는데, 재배포로 옛 해시가 사라진 뒤에도
    캐시된 index.html이 옛 자산을 찾다 404 → 흰 화면이 된다. 자산은 영원히,
    index.html은 매번 확인(`_mount_frontend`의 no-cache)이 정답이다.

    확인 경로: starlette 1.4.1 staticfiles.py:175 `file_response(...)`가
    FileResponse를 만들어 돌려준다 — 그 헤더에 얹는다.
    """

    def file_response(self, *args, **kwargs):  # type: ignore[override]
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def _mount_frontend(app: FastAPI) -> None:
    """빌드된 프론트(`web/dist/`)를 같은 오리진에서 서빙한다.

    이렇게 해야 배포가 컨테이너 하나·프로세스 하나로 끝난다 — 프론트를 따로
    띄우면 CORS·쿠키·OAuth 콜백이 전부 두 오리진 문제가 된다. 개발에서는
    vite가 5173에 따로 뜨고 `/api`를 프록시하므로 이 마운트가 쓰이지 않는다.

    SPA라 서버에 없는 경로(`/account`, `/report` …)도 index.html을 돌려주고
    그 뒤는 react-router가 맡아야 한다. `StaticFiles(html=True)`만으로는 안
    된다 — 그건 디렉터리에 대해서만 index.html을 주고 임의 경로는 404다.
    그래서 자산은 마운트로, 나머지는 catch-all로 받는다.

    **API 라우터를 다 등록한 뒤에 불러야 한다.** catch-all은 앞선 라우트가
    아무것도 안 맞을 때만 걸리므로 등록 순서가 곧 우선순위다.

    빌드가 없으면 조용히 건너뛴다 — `npm run build`를 안 한 개발 환경에서
    서버가 안 뜨면 안 된다.
    """
    dist = SERVER_DIR.parent / "web" / "dist"
    index = dist / "index.html"
    if not index.exists():
        logger.info("프론트 빌드가 없어 정적 서빙을 건너뜁니다 (%s)", dist)
        return

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", _ImmutableAssets(directory=assets), name="assets")

    # 해시 없는 파일(index.html · worklets · favicon)은 매번 서버에 확인한다.
    # ETag가 있어 바뀌지 않았으면 304로 끝난다.
    revalidate = {"Cache-Control": "no-cache"}

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        # 파일이 실제로 있으면 그것을(favicon 등), 없으면 SPA 진입점을.
        candidate = (dist / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(dist.resolve()):
            return FileResponse(candidate, headers=revalidate)
        return FileResponse(index, headers=revalidate)

    logger.info("프론트를 같은 오리진에서 서빙합니다 (%s)", dist)


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

    # 운영이면 설정이 갖춰졌는지 **먼저** 본다 — 빠졌으면 여기서 끝난다. 임베더
    # 준비나 마이그레이션보다 앞이어야 잘못 뜬 서버가 아무것도 건드리지 않는다.
    preflight.enforce()

    # 임베더를 기동 시점에 준비한다 — 첫 검색이 면접 한가운데서 준비 비용을
    # 물면 안 된다. 기본(Gemini API)은 클라이언트 하나라 즉시 끝나고,
    # SEARCH_EMBEDDINGS=local이면 여기서 모델을 내려받고 올린다(수 초~수 분).
    from daedam.knowledge.embedding import default_embedder

    default_embedder()

    app = FastAPI(title="대담")
    # 브라우저는 vite 프록시를 거쳐도 Origin 헤더를 원래 페이지(5173)로 보낸다.
    # 배포에서는 프론트를 같은 오리진에서 서빙하므로 이 목록이 쓰이지 않는다.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_DEV_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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
    credits = Credits(db)
    accounts = Accounts(db, login_required=bool(providers), credits=credits)

    # 세션 쿠키. OAuth 흐름의 state와 로그인 상태가 여기 담긴다. 비밀키가 바뀌면
    # 모두 로그아웃되므로 배포에서는 반드시 고정 값을 준다.
    app.add_middleware(
        SessionMiddleware,
        secret_key=_session_secret(),
        same_site="lax",
        https_only=os.environ.get("COOKIE_SECURE") == "1",
    )
    app.include_router(create_auth_router(accounts, store))
    app.include_router(create_credit_router(accounts, credits))
    # live는 20~60분짜리 작업이라 1초 폴링이면 조회 API를 수천 번 두드린다.
    # fixture는 12초 안에 끝나므로 촘촘히 봐야 진행 화면이 자연스럽다.
    live = os.environ.get("RESEARCH_MODE") == "live"
    preparation = InterviewPreparation(
        research=_research_service(data_root),
        store=store,
        poll_interval_s=30.0 if live else 1.0,
        # 준비가 실패하면 크레딧을 되돌린다. 실패한 작업에 요금을 물리면
        # 다시 시도할 수도 없다.
        on_failed=lambda user_id, task_id: credits.refund(
            user_id, "research", task_id
        ),
    )
    app.include_router(create_preparation_router(preparation, accounts, credits))
    # 홈 화면이 그릴 카드 목록. 프론트가 자기 메모리로 들고 있으면 새로고침에
    # 사라지고, 준비 안 된 면접을 시작하려다 브리지에서 거절당한다.
    # 면접이 끝나면 브리지가 이걸 깨우고, 분석 화면이 결과를 기다린다.
    evaluation = InterviewEvaluation(store)
    app.include_router(
        create_interviews_router(store, preparation, accounts, evaluation, credits)
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
            credits,
            profile=_interview_profile(),
            evaluation=evaluation,
        )
    )
    # 감시용. catch-all보다 앞에 있어야 한다 — 뒤에 두면 index.html이 200으로 답한다.
    app.include_router(create_health_router(db, data_root))

    # 녹음 보관 기한. 비우면 지우지 않는다 — 기한은 개인정보처리방침의 값이다.
    retention_days = int(os.environ.get("RECORDING_RETENTION_DAYS") or 0)
    if retention_days > 0:
        start_retention_timer(store, retention_days)
        logger.info("녹음 보관 기한 %d일 — 하루 한 번 정리합니다", retention_days)

    _mount_frontend(app)
    return app


app = create_app()
