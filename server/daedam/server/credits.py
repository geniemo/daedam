"""크레딧 — 지급하고, 차감하고, 모자라면 막는다.

이 서비스의 원가는 둘로 나뉜다. 회사 등록은 Deep Research 한 건이라 무겁고
한 번뿐이고, 면접은 Live API 오디오라 반복된다. 그래서 크레딧도 두 곳에서
빠진다 — 면접에만 물리면 등록만 잔뜩 하고 면접을 안 하는 사용 패턴이 그대로
손실이 된다.

**단위는 면접 한 판이다.** 사용자가 세는 방식이 그것이라("몇 번 더 볼 수
있나") 1 크레딧 = 면접 1회로 두고, 등록은 그 몇 배로 매긴다.

**실제 결제(PG)는 여기 없다.** 국내 PG는 사업자등록증이 있어야 계약되므로
지금은 지급·차감·잔액만 만든다. 결제가 붙으면 `grant(reason="purchase")`를
부르는 라우트 하나가 는다.

잔액은 원장의 합이다(`CreditEntry`). 되돌릴 일도 지우기가 아니라 반대 부호의
행을 더해서 처리한다 — 기록은 고치지 않는다.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select

from daedam.db import CreditEntry, Database

logger = logging.getLogger(__name__)

#: 값의 근거는 docs/specs/2026-08-23-credit-pricing.md에 있다. 1크레딧을 990원
#: 으로 잡으면 등록 5,940원 · 면접 3,960원이고 마진이 각각 53%다.

#: 가입 선물 = 면접 한 판. 프리셋 기업(리서치가 이미 있는 회사)과 함께 쓰면
#: 완주 한 바퀴를 체험시키면서 우리 원가는 1,865원으로 막힌다. 등록까지 공짜로
#: 주면 1인당 4,665원이라 유입을 예측할 수 없는 상황에서는 위험하다.
SIGNUP_GRANT = int(os.environ.get("CREDITS_SIGNUP_GRANT", "4"))

#: 회사 등록 한 건 — 원가 약 2,800원. 95%가 Deep Research이고 변동폭도 거기서
#: 온다($1~3). 실원가가 오르면 이 숫자만 올리면 되고 결제 상품은 그대로다.
COST_RESEARCH = int(os.environ.get("CREDITS_PER_RESEARCH", "6"))

#: 면접 한 판 — 평가·리포트까지 포함해 원가 약 1,800원(폭 920~2,940원). 폭이
#: 넓은 이유는 Live API가 턴마다 누적 맥락을 다시 과금해서다 — 원가가 통화
#: 길이가 아니라 "길이 × 턴 수"에 비례한다. 코칭은 44~94원이라 따로 물리지
#: 않고 여기 포함시킨다.
COST_INTERVIEW = int(os.environ.get("CREDITS_PER_INTERVIEW", "4"))


class InsufficientCredits(Exception):
    """잔액이 모자라 막았다. 라우트가 402로 옮긴다."""

    def __init__(self, needed: int, balance: int) -> None:
        super().__init__(f"크레딧이 부족합니다 (필요 {needed}, 잔액 {balance})")
        self.needed = needed
        self.balance = balance


@dataclass(frozen=True)
class CreditEvent:
    """크레딧 내역 한 줄 — 사용자가 "왜 줄었지"를 확인하는 자리."""

    delta: int
    reason: str
    ref_id: str | None
    created_at: datetime


class Credits:
    """크레딧 원장. 앱 조립 시점에 하나 만들어 라우터들이 나눠 쓴다."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def balance(self, user_id: str) -> int:
        """지금 잔액 — 원장의 합."""
        with self._db.session() as session:
            total = session.scalar(
                select(func.coalesce(func.sum(CreditEntry.delta), 0)).where(
                    CreditEntry.user_id == user_id
                )
            )
            return int(total or 0)

    def ensure(self, user_id: str, amount: int) -> None:
        """잔액이 되는지만 본다. 모자라면 `InsufficientCredits`.

        차감할 대상 id를 아직 모를 때 쓴다 — 리서치는 시작해야 task_id가
        나오는데, 시작하면 취소할 수 없는 유료 작업이라 그 전에 막아야 한다.
        확인과 차감 사이에 잔액이 바뀔 수 있지만, 그 창은 한 사용자가 두 탭에서
        동시에 등록하는 경우뿐이고 실제 차감은 `charge`가 다시 확인한다.
        """
        balance = self.balance(user_id)
        if balance < amount:
            raise InsufficientCredits(needed=amount, balance=balance)

    def grant(
        self, user_id: str, amount: int, reason: str, ref_id: str | None = None
    ) -> None:
        """크레딧을 준다. 가입 선물·결제·환불이 모두 이 길로 온다."""
        if amount <= 0:
            return
        with self._db.session() as session:
            session.add(
                CreditEntry(
                    user_id=user_id, delta=amount, reason=reason, ref_id=ref_id
                )
            )
        logger.info("크레딧 %+d (%s, user=%s)", amount, reason, user_id)

    def charge(self, user_id: str, amount: int, reason: str, ref_id: str) -> None:
        """크레딧을 쓴다. 모자라면 `InsufficientCredits`.

        확인과 차감이 한 트랜잭션 안에 있어야 두 번 눌러 두 번 쓰는 일이
        없다. SQLite는 쓰기를 직렬화하므로 이것으로 충분하다. PostgreSQL로
        옮기면 사용자 행을 `SELECT ... FOR UPDATE`로 잠가야 한다.
        """
        if amount <= 0:
            return
        with self._db.session() as session:
            total = int(
                session.scalar(
                    select(func.coalesce(func.sum(CreditEntry.delta), 0)).where(
                        CreditEntry.user_id == user_id
                    )
                )
                or 0
            )
            if total < amount:
                raise InsufficientCredits(needed=amount, balance=total)
            session.add(
                CreditEntry(
                    user_id=user_id, delta=-amount, reason=reason, ref_id=ref_id
                )
            )
        logger.info("크레딧 -%d (%s, user=%s, ref=%s)", amount, reason, user_id, ref_id)

    def refund(self, user_id: str, reason: str, ref_id: str) -> None:
        """이 건으로 빠져나간 만큼 되돌린다. 이미 되돌렸으면 아무것도 안 한다.

        리서치가 실패하면 사용자 잘못이 아니다 — 실패한 작업에 크레딧을
        물리면 다시 시도할 수도 없다.
        """
        with self._db.session() as session:
            rows = session.scalars(
                select(CreditEntry).where(
                    CreditEntry.user_id == user_id, CreditEntry.ref_id == ref_id
                )
            ).all()
            spent = -sum(row.delta for row in rows if row.delta < 0)
            already = sum(row.delta for row in rows if row.reason == "refund")
            amount = spent - already
            if amount <= 0:
                return
            session.add(
                CreditEntry(
                    user_id=user_id, delta=amount, reason="refund", ref_id=ref_id
                )
            )
        logger.info("크레딧 환불 +%d (%s, user=%s)", amount, reason, user_id)

    def history(self, user_id: str, limit: int = 50) -> list[CreditEvent]:
        """최근 내역 — 최신이 앞에 온다."""
        with self._db.session() as session:
            rows = session.scalars(
                select(CreditEntry)
                .where(CreditEntry.user_id == user_id)
                .order_by(CreditEntry.created_at.desc(), CreditEntry.id.desc())
                .limit(limit)
            ).all()
            return [
                CreditEvent(
                    delta=row.delta,
                    reason=row.reason,
                    ref_id=row.ref_id,
                    created_at=row.created_at,
                )
                for row in rows
            ]
