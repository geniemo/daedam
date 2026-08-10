"""FastAPI 앱 조립.

ADK의 get_fast_api_app이 에이전트 API와 dev UI를 제공하고, 그 위에 리서치
라우트를 얹는다. 실행: `cd server && uv run uvicorn daedam.server.app:app`

확인 경로 (설치된 ADK 2.6.3 소스):
  google/adk/cli/fast_api.py  `get_fast_api_app(*, agents_dir, web, ...)`
    — FastAPI 인스턴스를 돌려주므로 include_router로 확장할 수 있다
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import InMemoryRunner

from daedam.research.service import FixtureResearch, LiveResearch, ResearchService

from .live_bridge import create_live_router
from .research_routes import create_research_router

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


def create_app() -> FastAPI:
    """ADK 앱에 대담 라우트를 얹어 돌려준다."""
    # 임베딩 모델(수 초)을 기동 시점에 예열한다 — 첫 검색이 면접 한가운데서
    # 모델 로드로 멈추면 안 된다.
    from daedam.knowledge.embedding import default_embedder

    default_embedder()

    app = get_fast_api_app(
        agents_dir=_AGENTS_DIR, web=True, allow_origins=_DEV_ORIGINS
    )
    app.include_router(create_research_router(_research_service()))

    # 음성 브리지는 자기 러너로 돈다. ADK 앱(dev UI) 쪽 세션 저장소와는
    # 분리돼 있다 — 제품 경로는 /ws/interview 하나다.
    from interviewer.agent import root_agent

    app.include_router(create_live_router(InMemoryRunner(root_agent, app_name="daedam")))
    return app


app = create_app()
