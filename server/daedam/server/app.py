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
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import InMemoryRunner

from daedam.interview.stages import DEFAULT_PROFILE
from daedam.research.service import FixtureResearch, LiveResearch, ResearchService

from .live_bridge import create_live_router
from .preparation import InterviewPreparation
from .preparation_routes import create_preparation_router
from .store import FileInterviewStore

#: interviewer 에이전트 패키지가 들어 있는 디렉터리 (= server/).
_AGENTS_DIR = str(Path(__file__).resolve().parents[2])

# adk web은 실행 디렉터리의 .env를 스스로 읽지만 uvicorn은 아니다 — 명시적으로
# 읽지 않으면 GOOGLE_API_KEY가 없어 run_live의 Gemini 연결이 실패한다.
load_dotenv(Path(_AGENTS_DIR) / ".env")

#: vite 개발 서버 origin. 브라우저는 프록시를 거쳐도 Origin 헤더를 원래
#: 페이지(5173)로 보내는데, ADK 앱의 origin 검사가 이를 거부하면 모든 브라우저
#: POST가 403이 된다. 배포에서는 dist/를 같은 오리진에서 서빙하므로 무관하다.
_DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def _research_service() -> ResearchService:
    """RESEARCH_MODE로 백엔드를 고른다. 기본은 fixture — live는 작업당 $1~7."""
    mode = os.environ.get("RESEARCH_MODE", "fixture")
    return LiveResearch() if mode == "live" else FixtureResearch()


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
    store = FileInterviewStore(Path(_AGENTS_DIR) / "data")
    preparation = InterviewPreparation(research=_research_service(), store=store)
    app.include_router(create_preparation_router(preparation))

    # 음성 브리지는 자기 러너로 돈다. ADK 앱(dev UI) 쪽 세션 저장소와는
    # 분리돼 있다 — 제품 경로는 /ws/interview 하나다. 준비 데이터 저장소를
    # 공유해, 파이프라인이 만든 것을 브리지가 세션에 시딩한다.
    from interviewer.agent import root_agent

    app.include_router(
        create_live_router(
            InMemoryRunner(root_agent, app_name="daedam"),
            store,
            profile=_interview_profile(),
        )
    )
    return app


app = create_app()
