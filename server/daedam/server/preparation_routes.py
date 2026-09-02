"""면접 준비 HTTP 라우트.

핸드오프 "서버 연동이 필요한 지점" 1·2·3에 대응한다:
  POST /api/preparation        — 회사 등록 + 준비 파이프라인 시작 → task_id
  GET  /api/preparation/{id}   — 진행률 폴링. 완료(질문까지 준비)되면 리포트와
                              '확인 필요' 목록
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .accounts import Accounts
from .credits import COST_RESEARCH, Credits, InsufficientCredits
from .preparation import InterviewPreparation


class PreparationRequest(BaseModel):
    """회사 등록 요청. application은 chunks_from_application 형태의 파트 목록."""

    company: str
    role: str
    application: list[dict[str, Any]] = Field(default_factory=list)
    #: 채용공고 링크 또는 본문. 파싱하지 않고 리서치 프롬프트에 그대로 실린다.
    posting: str = ""
    #: 지원자 이름. 면접관이 부르고 전사 어휘 힌트로도 나간다.
    name: str = ""


def create_preparation_router(
    preparation: InterviewPreparation, accounts: Accounts, credits: Credits
) -> APIRouter:
    """준비 파이프라인을 라우터로 감싼다.

    Args:
        preparation: 리서치 → 저장 → 질문 생성을 완주하는 오케스트레이터.
        accounts: 등록되는 준비 데이터의 주인을 정해 준다.
        credits: 등록 한 건의 크레딧을 미리 차감한다. Deep Research는 시작하면
            취소할 수 없으므로 돈이 나가기 전에 막아야 한다.

    Returns:
        /api/preparation 라우터.
    """
    router = APIRouter(prefix="/api/preparation", tags=["preparation"])

    @router.post("", status_code=202)
    def start_preparation(
        request: PreparationRequest,
        user_id: str = Depends(accounts.current_user_id),
    ) -> dict[str, str]:
        # 잔액을 **먼저** 본다. Deep Research는 시작하면 취소할 수 없는 유료
        # 작업이라, 시작한 뒤에 막으면 돈은 이미 나간 뒤다.
        try:
            credits.ensure(user_id, COST_RESEARCH)
        except InsufficientCredits as insufficient:
            raise HTTPException(
                status_code=402,
                detail={
                    "message": "크레딧이 부족합니다",
                    "needed": insufficient.needed,
                    "balance": insufficient.balance,
                },
            ) from insufficient
        task_id = preparation.start(
            request.company,
            request.role,
            request.application,
            request.posting,
            request.name,
            user_id=user_id,
        )
        # 차감의 근거는 이 작업이다. 실패하면 같은 ref_id로 되돌린다
        # (`InterviewPreparation`의 on_failed).
        credits.charge(user_id, COST_RESEARCH, "research", task_id)
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
