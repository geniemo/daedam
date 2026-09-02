"""면접 기록만 지워 "면접 안 한 상태"로 되돌린다 — 개발용.

    uv run python scripts/reset_interview.py <면접 id | 회사명 일부> [...]
    uv run python scripts/reset_interview.py --all

준비 데이터(리서치 리포트·질문 풀·지원서)는 건드리지 않는다. 리서치는 작업당
$1~3·10~15분이라 다시 돌리게 만들면 안 된다. 지우는 것은 면접 판들 —
녹음·전사·피드백이다.

**진행 중인 대화 세션은 여기서 못 지운다.** ADK 대화 세션은 데이터베이스에
있지만 그 테이블은 ADK가 소유한다. 지금 면접이 돌고 있는 중이면 서버를
재기동하고 다시 실행하십시오.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from daedam.db import Application, Database, InterviewSession, database_url  # noqa: E402
from daedam.server.store import InterviewStore  # noqa: E402
from daedam.settings import data_root  # noqa: E402


def _matches(row: Application, needle: str) -> bool:
    needle = needle.lower()
    return needle in row.id.lower() or needle in f"{row.company} {row.role}".lower()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="*", help="면접 id 또는 회사명 일부")
    parser.add_argument("--all", action="store_true", help="모든 면접의 기록을 지운다")
    args = parser.parse_args()
    if not args.targets and not args.all:
        parser.error("면접을 지정하거나 --all을 주십시오")

    root = data_root()
    db = Database(database_url(root))
    store = InterviewStore(db, root)

    with db.session() as session:
        applications = list(session.scalars(select(Application)))
        for row in applications:
            if not args.all and not any(_matches(row, t) for t in args.targets):
                continue
            sessions = list(
                session.scalars(
                    select(InterviewSession).where(
                        InterviewSession.application_id == row.id
                    )
                )
            )
            label = f"{row.company} · {row.role}"
            if not sessions:
                print(f"없음  {label}  ({row.id})")
                continue
            for interview in sessions:
                directory = store.session_directory(row.id, interview.id)
                if directory.exists():
                    shutil.rmtree(directory, ignore_errors=True)
                session.delete(interview)
            print(f"지움  {label}  — 면접 {len(sessions)}판  ({row.id})")

    print("\n면접이 진행 중이었다면 서버를 재기동하십시오 — 대화 세션은 ADK가 쥐고 있습니다.")


if __name__ == "__main__":
    main()
