"""돌고 있는 Deep Research가 무엇을 내보내는지 전부 받아 적는다.

    uv run python scripts/watch_research.py [--interval 20]

왜 필요한가: 진행 화면이 보여줄 "지금 어느 단계인가"를 우리가 정하고 있는데,
그 근거가 스텝 종류 세 가지뿐이다. Deep Research가 실제로 어떤 스텝을 어떤
순서로 내는지 본 적이 없어서다 — 컬리 실행 때는 thinking_summaries가 꺼져
있어 완료 응답에 user_input과 model_output만 남았다.

작업당 20~60분이고 유료라 실행을 여러 번 할 수 없다. 그래서 한 번 돌 때
받은 것을 통째로 남긴다. 화면 설계는 이 기록을 보고 한다.

읽기만 한다 — 새 리서치를 시작하지 않는다. 진행 중인 작업은
`data/_research_tasks.json`에서 찾는다(LiveResearch가 남기는 파일).

남기는 것:
  data/_raw/steps-{interaction_id}.jsonl   스텝이 바뀔 때마다 스냅샷 한 줄
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from google.genai import Client  # noqa: E402 — .env를 먼저 읽어야 한다

_DATA = Path(__file__).resolve().parent.parent / "data"
_TASKS = _DATA / "_research_tasks.json"
_RAW = _DATA / "_raw"


def _step_view(step: Any) -> dict[str, Any]:
    """스텝 하나를 사람이 읽을 수 있는 형태로. 모르는 필드도 최대한 담는다."""
    kind = getattr(step, "type", "?")
    view: dict[str, Any] = {"type": kind}

    arguments = getattr(step, "arguments", None)
    if arguments is not None:
        # queries·urls 말고 무엇이 더 오는지 모르므로 통째로 남긴다.
        view["arguments"] = _plain(arguments)

    summary = getattr(step, "summary", None)
    if summary:
        view["summary"] = [getattr(c, "text", "") for c in summary]

    content = getattr(step, "content", None)
    if content:
        texts = [getattr(c, "text", None) for c in content]
        view["content_len"] = sum(len(t) for t in texts if t)
        view["content_kinds"] = sorted({type(c).__name__ for c in content})

    return view


def _plain(value: Any) -> Any:
    """pydantic 모델이든 뭐든 JSON에 담기는 형태로 편다."""
    for attr in ("model_dump", "dict"):
        dump = getattr(value, attr, None)
        if callable(dump):
            try:
                return dump()
            except TypeError:
                pass
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=float, default=20.0, help="폴링 간격(초)")
    parser.add_argument("--task", help="특정 task_id만 본다")
    args = parser.parse_args()

    if not _TASKS.exists():
        print(f"진행 중인 리서치 기록이 없습니다: {_TASKS}")
        return 1
    tasks = json.loads(_TASKS.read_text(encoding="utf-8"))
    if args.task:
        tasks = {args.task: tasks[args.task]}
    if not tasks:
        print("기록이 비어 있습니다")
        return 1

    client = Client()
    _RAW.mkdir(parents=True, exist_ok=True)
    seen: dict[str, int] = {}

    for task_id, entry in tasks.items():
        print(f"task {task_id} → interaction {entry['interaction_id']}")

    while True:
        alive = 0
        for task_id, entry in tasks.items():
            interaction_id = entry["interaction_id"]
            try:
                interaction = client.interactions.get(interaction_id)
            except Exception as exc:  # 조회 실패도 관측 대상이다
                print(f"  [{task_id[:8]}] 조회 실패: {type(exc).__name__}: {exc}"[:160])
                alive += 1
                continue

            steps = list(interaction.steps or [])
            status = interaction.status
            if len(steps) != seen.get(interaction_id, -1):
                seen[interaction_id] = len(steps)
                record = {
                    "at": time.strftime("%H:%M:%S"),
                    "status": status,
                    "steps": [_step_view(s) for s in steps],
                }
                with (_RAW / f"steps-{interaction_id}.jsonl").open(
                    "a", encoding="utf-8"
                ) as handle:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")

                kinds: dict[str, int] = {}
                for step in steps:
                    key = getattr(step, "type", "?")
                    kinds[key] = kinds.get(key, 0) + 1
                print(f"  {record['at']} [{task_id[:8]}] {status} {kinds}")
                for view in record["steps"][-2:]:
                    if view.get("arguments"):
                        print(f"      {view['type']}: {view['arguments']}"[:200])
                    elif view.get("summary"):
                        print(f"      {view['type']}: {view['summary'][0][:160]}")

            if status in ("queued", "in_progress", "requires_action"):
                alive += 1

        if alive == 0:
            print("모든 작업이 끝났습니다")
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
