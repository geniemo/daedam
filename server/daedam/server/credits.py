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
from datetime import UTC, datetime

from sqlalchemy import func, select

from daedam.db import Coupon, CreditEntry, Database

logger = logging.getLogger(__name__)

#: 값의 근거는 docs/specs/2026-08-23-credit-pricing.md에 있다. 1크레딧을 990원
#: 으로 잡으면 등록 5,940원 · 면접 3,960원이고 마진이 각각 53%다.

#: 가입 선물 = 면접 한 판. 프리셋 기업(리서치가 이미 있는 회사)과 함께 쓰면
#: 완주 한 바퀴를 체험시키면서 우리 원가는 1,865원으로 막힌다. 등록까지 공짜로
#: 주면 1인당 4,665원이라 유입을 예측할 수 없는 상황에서는 위험하다.
SIGNUP_GRANT = int(os.environ.get("CREDITS_SIGNUP_GRANT", "4"))

#: 가입 선물을 몇 명까지 주는가. 0이면 무제한(개발 기본). 홍보 뒤 유입은
#: 예측할 수 없고 소셜 계정은 무한히 만들 수 있다 — 무료 지급 총량에 천장이
#: 없으면 가입 폭주 하나가 그대로 청구서가 된다(docs/specs 크레딧 정책의 권고).
SIGNUP_CAP = int(os.environ.get("CREDITS_SIGNUP_CAP", "0"))

#: 회사 등록 한 건 — 원가 약 2,800원. 95%가 Deep Research이고 변동폭도 거기서
#: 온다($1~3). 실원가가 오르면 이 숫자만 올리면 되고 결제 상품은 그대로다.
COST_RESEARCH = int(os.environ.get("CREDITS_PER_RESEARCH", "6"))

#: 면접 한 판 — 평가·리포트까지 포함해 원가 약 1,800원(폭 920~2,940원). 폭이
#: 넓은 이유는 Live API가 턴마다 누적 맥락을 다시 과금해서다 — 원가가 통화
#: 길이가 아니라 "길이 × 턴 수"에 비례한다. 코칭은 44~94원이라 따로 물리지
#: 않고 여기 포함시킨다.
COST_INTERVIEW = int(os.environ.get("CREDITS_PER_INTERVIEW", "4"))


#: 쿠폰 사용을 원장에 남길 때 쓰는 reason. 결제가 붙어도 같은 값을 쓴다 —
#: 사용자에게는 둘 다 "충전"이다.
PURCHASE_REASON = "purchase"

#: 되돌린 건을 원장에 남길 때 쓰는 reason. 조회 쪽(`refunded`)이 이 값으로
#: 찾으므로 문자열을 양쪽에 흩어 두지 않는다.
REFUND_REASON = "refund"


def normalize_code(code: str) -> str:
    """손으로 치는 값이라 대소문자·앞뒤 공백으로 갈리지 않게 한다."""
    return code.strip().upper()


class CouponError(Exception):
    """쿠폰을 쓸 수 없다. `reason`으로 무엇이 문제인지 가른다.

    이유를 뭉뚱그리지 않는 이유: "코드가 잘못됐습니다" 하나로 처리하면
    이미 쓴 코드를 다시 넣은 사람이 오타를 의심하며 계속 시도한다.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        #: not_found · expired · exhausted · already_used
        self.reason = reason


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

        확인과 차감 사이에 잔액이 바뀔 수 있으므로 유료 작업의 문지기로는 쓰지
        않는다 — 등록도 이제 id를 미리 만들어 `charge`를 먼저 한다. 화면 안내처럼
        "될까"만 볼 때 쓴다.
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

    def grant_signup(self, user_id: str) -> bool:
        """가입 선물. 총량 상한(`CREDITS_SIGNUP_CAP`)에 닿았으면 주지 않는다.

        상한은 "지급된 사람 수"다. 세는 것과 주는 것 사이에 창이 있어 동시 가입
        둘이 상한을 하나 넘길 수 있다 — 청구서 관점에서 오차다.

        Returns:
            줬으면 True.
        """
        if SIGNUP_CAP > 0 and self.signup_grants_given() >= SIGNUP_CAP:
            logger.warning(
                "가입 선물 총량 상한(%d명)에 닿아 주지 않습니다 (user=%s)", SIGNUP_CAP, user_id
            )
            return False
        self.grant(user_id, SIGNUP_GRANT, "signup_grant")
        return True

    def signup_grants_given(self) -> int:
        """지금까지 가입 선물을 받은 사람 수."""
        with self._db.session() as session:
            return int(
                session.scalar(
                    select(func.count(CreditEntry.id)).where(
                        CreditEntry.reason == "signup_grant"
                    )
                )
                or 0
            )

    def charge(self, user_id: str, amount: int, reason: str, ref_id: str) -> None:
        """크레딧을 쓴다. 모자라면 `InsufficientCredits`.

        확인과 차감이 **쓰기 잠금을 쥔 채로** 일어나야 한다. 그러지 않으면 두
        탭에서 동시에 시작한 요청이 둘 다 같은 옛 잔액을 읽고 둘 다 통과한다 —
        SQLite의 기본 트랜잭션은 지연이라 SELECT가 잠금을 잡지 않는다.
        `exclusive=True`가 `BEGIN IMMEDIATE`로 그 창을 없앤다.
        """
        if amount <= 0:
            return
        with self._db.session(exclusive=True) as session:
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
            already = sum(row.delta for row in rows if row.reason == REFUND_REASON)
            amount = spent - already
            if amount <= 0:
                return
            session.add(
                CreditEntry(
                    user_id=user_id, delta=amount, reason=REFUND_REASON, ref_id=ref_id
                )
            )
        logger.info("크레딧 환불 +%d (%s, user=%s)", amount, reason, user_id)

    def refunded(self, user_id: str, ref_id: str) -> bool:
        """이 건을 되돌린 적이 있는가.

        화면이 "크레딧은 돌려드렸습니다"라고 말해도 되는지 판정한다. 돈 이야기라
        추측하지 않는다 — 되돌리는 경로가 하나가 아니라서(무응답 면접, 실패한
        리서치) 원장을 보는 것만이 늘 맞다.
        """
        with self._db.session() as session:
            found = session.scalar(
                select(CreditEntry.id).where(
                    CreditEntry.user_id == user_id,
                    CreditEntry.ref_id == ref_id,
                    CreditEntry.reason == REFUND_REASON,
                )
            )
        return found is not None

    def redeem(self, user_id: str, code: str) -> int:
        """쿠폰 코드를 크레딧으로 바꾼다. 돌려주는 것은 얹힌 크레딧 수.

        확인·사용 수 증가·지급이 한 트랜잭션 안에 있어야 선착순 코드가
        정원을 넘지 않는다. SQLite는 쓰기를 직렬화하므로 이것으로 충분하고,
        PostgreSQL로 옮기면 쿠폰 행을 `SELECT ... FOR UPDATE`로 잠가야 한다.

        Raises:
            CouponError: 없거나(not_found) 만료됐거나(expired) 정원이 찼거나
                (exhausted) 이 사람이 이미 쓴(already_used) 코드.
        """
        code = normalize_code(code)
        # 선착순 코드가 정원을 넘지 않으려면 확인과 사용 수 증가가 잠금 안에
        # 있어야 한다 — `charge`와 같은 이유다.
        with self._db.session(exclusive=True) as session:
            coupon = session.get(Coupon, code)
            if coupon is None:
                raise CouponError("not_found")
            if coupon.expires_at is not None:
                expires = coupon.expires_at
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=UTC)
                if expires <= datetime.now(UTC):
                    raise CouponError("expired")
            if coupon.used_count >= coupon.max_uses:
                raise CouponError("exhausted")
            # 같은 사람이 두 번 쓰는 것은 원장으로 막는다 — 사용 이력을 쿠폰
            # 쪽에 또 두면 진실이 두 곳이 된다.
            already = session.scalar(
                select(func.count())
                .select_from(CreditEntry)
                .where(
                    CreditEntry.user_id == user_id,
                    CreditEntry.reason == PURCHASE_REASON,
                    CreditEntry.ref_id == code,
                )
            )
            if already:
                raise CouponError("already_used")

            coupon.used_count += 1
            session.add(
                CreditEntry(
                    user_id=user_id,
                    delta=coupon.credits,
                    reason=PURCHASE_REASON,
                    ref_id=code,
                )
            )
            granted = coupon.credits
        logger.info("쿠폰 사용 %s (+%d, user=%s)", code, granted, user_id)
        return granted

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
