"""시선 타임라인을 리포트가 그릴 형태로 접는다 — 순수 로직.

화면이 초당 한 줄씩 올려 둔 것(`gaze.json`)을 받아, 면접 전체와 답변마다
비율을 낸다. **자르는 일을 서버가 하는 이유**는 답변 구간이 면접이 끝난 뒤
오디오를 분석해야 나오기 때문이다 — 화면은 그때 그 경계를 모른다.

여기서도 판정은 하지 않는다. "정면 51%"는 관찰이고 "산만했다"는 주장인데,
웹캠 하나로 뒤엣것을 말할 근거가 없다(docs/specs 참고).

**표정은 여기 없다.** 앞서는 이 타임라인의 근육 세기(`s`)로 인상까지 매겼는데,
차분한 얼굴에서 근육 신호가 0에 깔려 어떤 문턱으로도 한 칸으로 몰렸다.
인상은 스냅샷을 VLM으로 읽는 eval/expression.py가 맡고, 이 모듈은 홍채
기하에서 나오는 시선만 다룬다 — 그쪽은 실측(정면 93%)으로 검증됐다.

시계에 대해: 타임라인의 `at`은 화면이 센 면접 경과 초이고, 답변 구간
(`voice.answers[].startS`)은 서버가 받은 오디오 바이트로 센 것이다. 둘 다 면접
시작을 원점으로 하지만 정밀도가 1초쯤 어긋난다. 답변이 보통 10~60초라 자르는
데는 문제가 없고, 더 정확해야 할 일이 생기면 그때 원점을 맞춰야 한다.
"""

from __future__ import annotations

from typing import Any

#: 격자 칸 수. 화면(web/src/video/gaze.ts)의 3×3과 같아야 한다.
CELLS = 9

#: 정면으로 보는 칸. 화면의 `cellOf`가 4를 정면으로 쓴다.
CENTER_CELL = 4


def _fold(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """줄들을 비율로 접는다. 빈 목록이면 전부 0이고 seconds가 0이다."""
    cells = [0] * CELLS
    wander = 0.0
    for row in rows:
        cell = row.get("cell")
        if isinstance(cell, int) and 0 <= cell < CELLS:
            cells[cell] += 1
        value = row.get("ratio")
        if isinstance(value, (int, float)):
            wander += float(value)

    total = len(rows)
    if total == 0:
        return {
            "seconds": 0,
            "cells": [0.0] * CELLS,
            "steady": 0.0,
            "wander": 0.0,
        }
    return {
        "seconds": total,
        "cells": [round(count / total, 4) for count in cells],
        "steady": round(cells[CENTER_CELL] / total, 4),
        "wander": round(wander / total, 2),
    }


def analyze(
    timeline: dict[str, Any],
    answers: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """면접 전체와 답변별 비율. 담긴 줄이 없으면 None.

    Args:
        timeline: 화면이 올린 `gaze.json` 그대로.
        answers: 음성 지표의 답변 구간(`startS`·`endS`). 없으면 전체만 낸다.

    Returns:
        리포트가 그대로 그릴 dict, 또는 잴 것이 없으면 None.
    """
    rows = timeline.get("seconds")
    if not isinstance(rows, list) or not rows:
        return None

    payload = _fold(rows)
    payload["answers"] = []
    for answer in answers or []:
        start = answer.get("startS")
        end = answer.get("endS")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            payload["answers"].append(_fold([]))
            continue
        inside = [
            row
            for row in rows
            if isinstance(row.get("at"), (int, float)) and start <= row["at"] < end
        ]
        payload["answers"].append(_fold(inside))
    return payload
