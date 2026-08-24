"""크레딧 조회.

  GET /api/credits — 잔액과 최근 내역, 그리고 무엇이 얼마인지

가격을 화면에 하드코딩하지 않고 서버가 내려준다. 등록·면접 값을 환경변수로
조정하는데(`credits.py`), 화면이 자기 숫자를 들고 있으면 서버와 어긋난 안내를
하게 된다.

충전(결제)은 아직 없다 — 국내 PG는 사업자등록증이 있어야 계약된다.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .accounts import Accounts
from .credits import COST_INTERVIEW, COST_RESEARCH, CouponError, Credits

#: 내역 한 줄을 화면 문구로. 사용자는 "signup_grant"를 읽지 않는다.
_REASON_LABEL = {
    "signup_grant": "가입 선물",
    "research": "회사 등록",
    "interview": "면접",
    "refund": "환불",
    "purchase": "충전",
    "admin_grant": "지급",
}


class RedeemRequest(BaseModel):
    """쿠폰 코드. 손으로 치는 값이라 정규화는 서버가 한다."""

    code: str


#: 쿠폰이 안 될 때 사용자가 읽을 문구. 이유를 뭉뚱그리면 이미 쓴 코드를 다시
#: 넣은 사람이 오타를 의심하며 계속 시도한다.
_COUPON_MESSAGE = {
    "not_found": "없는 코드입니다. 다시 확인해 주세요.",
    "expired": "기한이 지난 코드입니다.",
    "exhausted": "사용 가능한 수량이 모두 소진된 코드입니다.",
    "already_used": "이미 사용하신 코드입니다.",
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

    @router.post("/redeem")
    def redeem(
        request: RedeemRequest, user_id: str = Depends(accounts.current_user_id)
    ) -> dict[str, Any]:
        """쿠폰 코드를 크레딧으로 바꾼다.

        결제(PG)가 붙기 전까지 사용자가 크레딧을 늘릴 수 있는 유일한 길이다.
        """
        try:
            granted = credits.redeem(user_id, request.code)
        except CouponError as error:
            raise HTTPException(
                status_code=400,
                detail={
                    "reason": error.reason,
                    "message": _COUPON_MESSAGE.get(error.reason, "사용할 수 없는 코드입니다."),
                },
            ) from error
        return {"granted": granted, "balance": credits.balance(user_id)}

    return router
