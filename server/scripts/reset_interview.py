"""면접 기록만 지워 "면접 안 한 상태"로 되돌린다 — 개발용.

    uv run python scripts/reset_interview.py <면접 id | 회사명 일부> [...]
    uv run python scripts/reset_interview.py --all

리서치 결과(report.json · questions.json · application.json · meta.json)는
건드리지 않는다. 작업당 20~60분·$1~7이라 다시 돌리게 만들면 안 된다.

**대화 세션은 여기서 못 지운다.** ADK 세션은 서버 프로세스 메모리에 있어서
서버 자신만 지울 수 있다. 지우지 않으면 브리지가 다음 접속을 재접속으로 보아
시간 예산과 진행 단계를 이어받는다 — 두 번째 면접이 첫 면접의 뒷부분이 된다.
그래서 이 스크립트를 돌린 뒤에는 서버를 재기동해야 한다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from daedam.server.recording import InterviewRecording  # noqa: E402

_DATA = Path(__file__).resolve().parent.parent / "data"


def _interviews() -> list[tuple[str, str]]:
    """(면접 id, "회사 · 직무") 목록. meta.json이 있는 디렉터리만."""
    found: list[tuple[str, str]] = []
    for directory in sorted(_DATA.iterdir()) if _DATA.exists() else []:
        meta_path = directory / "meta.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        found.append((directory.name, f"{meta['company']} · {meta['role']}"))
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("targets", nargs="*", help="면접 id 또는 회사명 일부")
    parser.add_argument("--all", action="store_true", help="전부 되돌린다")
    args = parser.parse_args()

    interviews = _interviews()
    if not interviews:
        print(f"면접이 없습니다: {_DATA}")
        return 1

    if args.all:
        chosen = interviews
    elif args.targets:
        chosen = [
            (interview_id, label)
            for interview_id, label in interviews
            if any(t == interview_id or t in label for t in args.targets)
        ]
    else:
        print("무엇을 되돌릴지 고르십시오:\n")
        for interview_id, label in interviews:
            recorded = (_DATA / interview_id / "transcript.json").exists()
            print(f"  {label:34} {interview_id}  {'[면접 기록 있음]' if recorded else ''}")
        print("\n사용: reset_interview.py <id 또는 회사명> [...] | --all")
        return 0

    if not chosen:
        print(f"맞는 면접이 없습니다: {args.targets}")
        return 1

    for interview_id, label in chosen:
        removed = InterviewRecording.discard(_DATA / interview_id)
        print(f"{'지움  ' if removed else '없음  '}{label}  ({interview_id})")

    print("\n서버를 재기동하십시오 — 대화 세션은 서버 메모리에 있어 여기서 못 지웁니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
