"""크레딧 쿠폰을 발급한다 — 운영용.

    uv run python scripts/issue_coupon.py --credits 10 --note "홍보영상 1차"
    uv run python scripts/issue_coupon.py --credits 10 --uses 100 --days 30 --note "베타"
    uv run python scripts/issue_coupon.py --list

결제(PG)가 붙기 전까지 사용자가 크레딧을 늘릴 수 있는 유일한 길이다. 국내
PG는 사업자등록증이 있어야 계약되므로, 그전까지는 여기서 만든 코드를 홍보
영상이나 초대 메일로 뿌린다.

관리자 화면을 만들지 않은 이유: 코드를 발급하는 사람이 서버에 접속할 수 있는
한 사람뿐이라, 화면을 만들면 그 화면을 지키는 일이 더 커진다.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from daedam.db import Coupon, Database, database_url  # noqa: E402
from daedam.db.migrate import upgrade_to_head  # noqa: E402
from daedam.settings import data_root  # noqa: E402

#: 코드에 쓰는 글자. 헷갈리는 것(0/O, 1/I/L)을 빼서 손으로 옮겨 적을 때
#: 틀리지 않게 한다 — 영상 자막으로 뿌릴 값이다.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _new_code(length: int = 8) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credits", type=int, help="이 코드가 주는 크레딧")
    parser.add_argument("--uses", type=int, default=1, help="몇 명까지 쓸 수 있는가")
    parser.add_argument("--days", type=int, default=0, help="며칠 뒤 만료 (0이면 무기한)")
    parser.add_argument("--note", default="", help="무엇 때문에 발급했는지")
    parser.add_argument("--code", help="코드를 직접 지정 (생략하면 자동 생성)")
    parser.add_argument("--list", action="store_true", help="발급된 코드를 본다")
    args = parser.parse_args()

    upgrade_to_head()
    db = Database(database_url(data_root()))

    if args.list:
        with db.session() as session:
            rows = session.scalars(select(Coupon).order_by(Coupon.created_at.desc())).all()
            if not rows:
                print("발급된 코드가 없습니다")
                return
            print(f"{'코드':<12} {'크레딧':>5} {'사용':>9}  만료         메모")
            for row in rows:
                expires = row.expires_at.strftime("%Y-%m-%d") if row.expires_at else "무기한"
                used = f"{row.used_count}/{row.max_uses}"
                print(f"{row.code:<12} {row.credits:>5} {used:>9}  {expires:<12} {row.note}")
        return

    if not args.credits or args.credits <= 0:
        parser.error("--credits를 1 이상으로 주십시오")

    code = (args.code or _new_code()).strip().upper()
    expires = datetime.now(UTC) + timedelta(days=args.days) if args.days else None
    with db.session() as session:
        if session.get(Coupon, code) is not None:
            parser.error(f"이미 있는 코드입니다: {code}")
        session.add(
            Coupon(
                code=code,
                credits=args.credits,
                max_uses=args.uses,
                expires_at=expires,
                note=args.note,
            )
        )

    print(f"\n  코드   {code}")
    print(f"  크레딧 {args.credits}  (등록 1건 + 면접 1회 = 10크레딧)")
    print(f"  수량   {args.uses}명")
    print(f"  만료   {expires.strftime('%Y-%m-%d') if expires else '무기한'}")
    if args.note:
        print(f"  메모   {args.note}")


if __name__ == "__main__":
    main()
