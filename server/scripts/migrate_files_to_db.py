"""파일 저장소에 있던 준비 데이터·면접 기록을 데이터베이스로 옮긴다 — 일회성.

    cd server && uv run python scripts/migrate_files_to_db.py [--dry-run]

앞선 구조는 `data/{면접 id}/*.json`이었다. 카드 하나에 면접 하나뿐이라
녹음·전사·피드백이 준비 데이터와 같은 디렉터리에 섞여 있었다. 새 구조는
준비 데이터 하나에 면접이 여러 판 붙고, 녹음은 판마다 나뉜다:

    data/{준비 id}/{면접 id}/mic.pcm|wav|transcript.json

옮기는 것:
  meta·application·report·uncertain·questions·vocabulary → applications 행
  transcript·feedback + mic.*                            → interview_sessions 행 하나

**파일을 지우지 않는다.** 옮긴 뒤에도 원본은 그대로 두고, 녹음만 면접
디렉터리로 복사한다. 리서치는 작업당 $1~3이라 옮기다 잘못돼도 되돌릴 수
있어야 한다. 확인이 끝나면 사람이 직접 지운다.

이미 옮겨진 준비 데이터는 건너뛴다 — 여러 번 돌려도 안전하다.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from daedam.db import Database, database_url  # noqa: E402
from daedam.db.migrate import upgrade_to_head  # noqa: E402
from daedam.server.accounts import Accounts  # noqa: E402
from daedam.server.store import InterviewStore  # noqa: E402
from daedam.settings import data_root  # noqa: E402

#: 준비 데이터를 이루는 파일들. meta.json이 있는 디렉터리만 면접으로 본다.
_RECORD_FILES = ("mic.pcm", "mic.wav", "transcript.json")


def _read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        print(f"  ! 읽지 못했습니다: {path.name}")
        return None


def _migrate_one(
    store: InterviewStore, directory: Path, user_id: str, dry_run: bool
) -> str:
    """디렉터리 하나를 옮긴다. 무엇을 했는지 한 줄로 돌려준다."""
    application_id = directory.name
    meta = _read_json(directory / "meta.json") or {}
    if store.load(application_id) is not None:
        return "이미 옮겨져 있음 — 건너뜀"

    if dry_run:
        has_record = any((directory / name).exists() for name in _RECORD_FILES)
        return f"옮길 예정 (면접 기록 {'있음' if has_record else '없음'})"

    store.save(
        application_id,
        user_id=user_id,
        company=meta.get("company", ""),
        role=meta.get("role", ""),
        name=meta.get("name", ""),
        application=_read_json(directory / "application.json") or [],
        report=_read_json(directory / "report.json") or [],
        uncertain=_read_json(directory / "uncertain.json") or [],
    )
    if (questions := _read_json(directory / "questions.json")) is not None:
        store.save_questions(application_id, questions)
    if (vocabulary := _read_json(directory / "vocabulary.json")) is not None:
        store.save_vocabulary(application_id, vocabulary)

    transcript = _read_json(directory / "transcript.json")
    feedback = _read_json(directory / "feedback.json")
    if transcript is None and feedback is None:
        return "준비 데이터만 옮김 (면접 기록 없음)"

    # 앞 구조에서는 카드당 면접이 하나였다 — 그 하나를 첫 판으로 만든다.
    session_id = store.start_session(application_id)
    if transcript is not None:
        store.save_transcript(session_id, transcript)
    if feedback is not None:
        store.save_feedback(session_id, feedback)
    store.end_session(session_id)

    session_dir = store.session_directory(application_id, session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    moved = []
    for name in _RECORD_FILES:
        source = directory / name
        if source.exists():
            shutil.copy2(source, session_dir / name)
            moved.append(name)
    return f"준비 데이터 + 면접 1판 옮김 (녹음 {len(moved)}개 복사)"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="무엇을 옮길지만 보여주고 쓰지 않는다"
    )
    args = parser.parse_args()

    root = data_root()
    directories = sorted(p for p in root.iterdir() if (p / "meta.json").exists())
    if not directories:
        print(f"옮길 것이 없습니다 ({root})")
        return

    # 스키마는 --dry-run에서도 올린다. 빈 테이블을 만드는 것뿐이고, 그래야
    # "이미 옮겨져 있는가"를 조회할 수 있다. 데이터는 아래에서만 쓴다.
    upgrade_to_head()
    db = Database(database_url(root))
    store = InterviewStore(db, root)
    user_id = Accounts(db).default_user_id()

    print(f"{root} — 면접 {len(directories)}건\n")
    for directory in directories:
        meta = _read_json(directory / "meta.json") or {}
        label = f"{meta.get('company', '?')} · {meta.get('role', '?')}"
        print(f"  {directory.name}  {label}")
        print(f"    {_migrate_one(store, directory, user_id, args.dry_run)}")

    if args.dry_run:
        print("\n(--dry-run — 아무것도 쓰지 않았습니다)")
    else:
        print("\n원본 파일은 그대로 두었습니다. 확인한 뒤 직접 지우십시오.")


if __name__ == "__main__":
    main()
