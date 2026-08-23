"""크레딧 조회.

  GET /api/credits — 잔액과 최근 내역, 그리고 무엇이 얼마인지

가격을 화면에 하드코딩하지 않고 서버가 내려준다. 등록·면접 값을 환경변수로
조정하는데(`credits.py`), 화면이 자기 숫자를 들고 있으면 서버와 어긋난 안내를
하게 된다.

충전(결제)은 아직 없다 — 국내 PG는 사업자등록증이 있어야 계약된다.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from .accounts import Accounts
from .credits import COST_INTERVIEW, COST_RESEARCH, Credits

#: 내역 한 줄을 화면 문구로. 사용자는 "signup_grant"를 읽지 않는다.
_REASON_LABEL = {
    "signup_grant": "가입 선물",
    "research": "회사 등록",
    "interview": "면접",
    "refund": "환불",
    "purchase": "충전",
    "admin_grant": "지급",
}


def create_credit_router(accounts: Accounts, credits: Credits) -> APIRouter:
    router = APIRouter(prefix="/api/credits", tags=["credits"])

    @router.get("")
    def my_credits(user_id: str = Depends(accounts.current_user_id)) -> dict[str, Any]:
        return {
            "balance": credits.balance(user_id),
            "costs": {"research": COST_RESEARCH, "interview": COST_INTERVIEW},
            "history": [
                {
                    "delta": event.delta,
                    "reason": event.reason,
                    "label": _REASON_LABEL.get(event.reason, event.reason),
                    "at": event.created_at.isoformat(),
                }
                for event in credits.history(user_id)
            ],
        }

    return router
