"""면접 준비 HTTP 라우트.

핸드오프 "서버 연동이 필요한 지점" 1·2·3에 대응한다:
  POST /api/preparation        — 회사 등록 + 준비 파이프라인 시작 → task_id
  GET  /api/preparation/{id}   — 진행률 폴링. 완료(질문까지 준비)되면 리포트와
                              '확인 필요' 목록
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .preparation import InterviewPreparation


class PreparationRequest(BaseModel):
    """회사 등록 요청. application은 chunks_from_application 형태의 파트 목록."""

    company: str
    role: str
    application: list[dict[str, Any]] = Field(default_factory=list)


def create_preparation_router(preparation: InterviewPreparation) -> APIRouter:
    """준비 파이프라인을 라우터로 감싼다.

    Args:
        preparation: 리서치 → 저장 → 질문 생성을 완주하는 오케스트레이터.

    Returns:
        /api/preparation 라우터.
    """
    router = APIRouter(prefix="/api/preparation", tags=["preparation"])

    @router.post("", status_code=202)
    def start_preparation(request: PreparationRequest) -> dict[str, str]:
        task_id = preparation.start(
            request.company, request.role, request.application
        )
        return {"task_id": task_id}

    @router.get("/{task_id}")
    def preparation_status(task_id: str) -> dict[str, Any]:
        status = preparation.status(task_id)
        if status is None:
            raise HTTPException(status_code=404, detail="리서치 작업이 없습니다")
        payload: dict[str, Any] = {"status": status.state, "pct": status.pct}
        if status.report is not None:
            payload["report"] = status.report
            payload["uncertain"] = status.uncertain or []
        return payload

    return router
