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
    #: 채용공고 링크 또는 본문. 파싱하지 않고 리서치 프롬프트에 그대로 실린다.
    posting: str = ""


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
            request.company, request.role, request.application, request.posting
        )
        return {"task_id": task_id}

    @router.get("/{task_id}")
    def preparation_status(task_id: str) -> dict[str, Any]:
        status = preparation.status(task_id)
        if status is None:
            raise HTTPException(status_code=404, detail="리서치 작업이 없습니다")
        payload: dict[str, Any] = {
            "status": status.state,
            # null일 수 있다 — Deep Research는 진행률을 주지 않는다. 그때 화면은
            # 막대 대신 단계와 경과 시간을 보여준다.
            "pct": status.pct,
            # 진행 화면이 그리는 조사 목록. 빈 목록이면 화면은 아무 단계도
            # 지어내지 않고 "리서치를 시작하고 있습니다"만 둔다.
            "activity": list(status.activity),
            "phase": status.phase,
            "elapsedS": status.elapsed_s,
        }
        if status.report is not None:
            payload["report"] = status.report
            payload["uncertain"] = status.uncertain or []
        return payload

    return router
