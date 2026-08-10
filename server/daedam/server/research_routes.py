"""리서치 HTTP 라우트.

핸드오프 "서버 연동이 필요한 지점" 1·2·3에 대응한다:
  POST /api/research        — 회사 등록 + 리서치 시작 → task_id
  GET  /api/research/{id}   — 진행률 폴링. 완료되면 리포트와 '확인 필요' 목록
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from daedam.research.service import ResearchService


class ResearchRequest(BaseModel):
    """회사 등록 요청. application은 chunks_from_application 형태의 파트 목록."""

    company: str
    role: str
    application: list[dict[str, Any]] = Field(default_factory=list)


def create_research_router(service: ResearchService) -> APIRouter:
    """리서치 백엔드를 라우터로 감싼다.

    Args:
        service: RESEARCH_MODE에 따라 고른 fixture 또는 live 백엔드.

    Returns:
        /api/research 라우터.
    """
    router = APIRouter(prefix="/api/research", tags=["research"])

    @router.post("", status_code=202)
    def start_research(request: ResearchRequest) -> dict[str, str]:
        task_id = service.start(request.company, request.role, request.application)
        return {"task_id": task_id}

    @router.get("/{task_id}")
    def research_status(task_id: str) -> dict[str, Any]:
        status = service.status(task_id)
        if status is None:
            raise HTTPException(status_code=404, detail="리서치 작업이 없습니다")
        payload: dict[str, Any] = {"status": status.state, "pct": status.pct}
        if status.report is not None:
            payload["report"] = status.report
            payload["uncertain"] = status.uncertain or []
        return payload

    return router
