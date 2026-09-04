"""면접 준비 HTTP 라우트.

핸드오프 "서버 연동이 필요한 지점" 1·2·3에 대응한다:
  POST /api/preparation        — 회사 등록 + 준비 파이프라인 시작 → task_id
  GET  /api/preparation/{id}   — 진행률 폴링. 완료(질문까지 준비)되면 리포트와
                              '확인 필요' 목록
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Callable

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from daedam.interview.application_import import MAX_PDF_BYTES, extract_application

from .accounts import Accounts
from .credits import COST_RESEARCH, Credits, InsufficientCredits
from .preparation import InterviewPreparation

logger = logging.getLogger(__name__)


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
    preparation: InterviewPreparation,
    accounts: Accounts,
    credits: Credits,
    import_application: Callable[[bytes], list[dict[str, Any]]] = extract_application,
) -> APIRouter:
    """준비 파이프라인을 라우터로 감싼다.

    Args:
        preparation: 리서치 → 저장 → 질문 생성을 완주하는 오케스트레이터.
        accounts: 등록되는 준비 데이터의 주인을 정해 준다.
        credits: 등록 한 건의 크레딧을 미리 차감한다. Deep Research는 시작하면
            취소할 수 없으므로 돈이 나가기 전에 막아야 한다.
        import_application: 지원서 PDF를 파트·항목으로 옮기는 함수. 테스트가
            대역을 주입한다.

    Returns:
        /api/preparation 라우터.
    """
    router = APIRouter(prefix="/api/preparation", tags=["preparation"])

    @router.post("", status_code=202)
    def start_preparation(
        request: PreparationRequest,
        user_id: str = Depends(accounts.current_user_id),
    ) -> dict[str, str]:
        # 유료 작업을 열기 **전에** 차감한다. Deep Research는 시작하면 취소할 수
        # 없어서, 앞서처럼 잔액만 보고 시작한 뒤 차감하면 그 사이에 같은
        # 사용자의 다른 요청이 잔액을 써 버린 경우 리서치는 돌고 요금은 안
        # 물리는 건이 생긴다(두 탭 동시 등록으로 재현). 차감은 원자적이라
        # (`Credits.charge`) 먼저 하면 그 창이 없다.
        #
        # id를 여기서 만든다 — 차감의 근거(ref_id)가 있어야 실패 시 같은 id로
        # 되돌릴 수 있고(`InterviewPreparation`의 on_failed), 파이프라인은 그
        # id로 리서치를 연다.
        task_id = uuid.uuid4().hex
        try:
            credits.charge(user_id, COST_RESEARCH, "research", task_id)
        except InsufficientCredits as insufficient:
            raise HTTPException(
                status_code=402,
                detail={
                    "message": "크레딧이 부족합니다",
                    "needed": insufficient.needed,
                    "balance": insufficient.balance,
                },
            ) from insufficient
        try:
            preparation.start(
                request.company,
                request.role,
                request.application,
                request.posting,
                request.name,
                user_id=user_id,
                task_id=task_id,
            )
        except Exception as exc:
            # 시작 자체가 실패했다 — 유료 작업은 열리지 않았다. 차감을 되돌린다.
            logger.exception("준비 시작 실패 (interview=%s) — 크레딧을 되돌립니다", task_id)
            credits.refund(user_id, "research", task_id)
            raise HTTPException(
                status_code=503,
                detail="리서치를 시작하지 못했습니다. 크레딧은 돌려드렸습니다. 잠시 뒤 다시 시도해 주세요",
            ) from exc
        return {"task_id": task_id}

    @router.post("/import")
    def import_from_pdf(
        file: UploadFile = File(...),
        user_id: str = Depends(accounts.current_user_id),
    ) -> dict[str, Any]:
        """지원서 PDF → 파트·항목. 저장하지 않는다 — 화면이 받아 폼에 채우고,
        사용자가 검토한 뒤 등록으로 낸다.

        파일은 메모리에서만 다룬다. 지원 사이트 export에는 인적사항이 통째로
        들어 있어서, 우리가 쓰는 부분(문항과 답변)만 뽑고 원본은 남기지 않는다.
        """
        data = file.file.read(MAX_PDF_BYTES + 1)
        if len(data) > MAX_PDF_BYTES:
            raise HTTPException(status_code=413, detail="PDF가 너무 큽니다 (10MB까지)")
        if not data.startswith(b"%PDF"):
            raise HTTPException(status_code=400, detail="PDF 파일만 올릴 수 있습니다")
        try:
            parts = import_application(data)
        except Exception as exc:
            logger.exception("지원서 PDF 읽기 실패 (user=%s)", user_id)
            raise HTTPException(
                status_code=502,
                detail="PDF에서 지원서를 읽지 못했습니다. 잠시 뒤 다시 시도하거나 직접 입력해 주세요",
            ) from exc
        return {"parts": parts}

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
