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

from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app

from daedam.research.service import FixtureResearch, LiveResearch, ResearchService

from .research_routes import create_research_router

#: interviewer 에이전트 패키지가 들어 있는 디렉터리 (= server/).
_AGENTS_DIR = str(Path(__file__).resolve().parents[2])


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

    app = get_fast_api_app(agents_dir=_AGENTS_DIR, web=True)
    app.include_router(create_research_router(_research_service()))
    return app


app = create_app()
