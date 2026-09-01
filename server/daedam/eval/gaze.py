"""시선·표정 타임라인을 리포트가 그릴 형태로 접는다 — 순수 로직.

화면이 초당 한 줄씩 올려 둔 것(`gaze.json`)을 받아, 면접 전체와 답변마다
비율을 낸다. **자르는 일을 서버가 하는 이유**는 답변 구간이 면접이 끝난 뒤
오디오를 분석해야 나오기 때문이다 — 화면은 그때 그 경계를 모른다.

여기서도 판정은 하지 않는다. "정면 51%"는 관찰이고 "산만했다"는 주장인데,
웹캠 하나로 뒤엣것을 말할 근거가 없다(docs/specs 참고).

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

#: 인상 분류. 화면의 `IMPRESSIONS`와 키가 같아야 한다.
IMPRESSIONS = ("confident", "focused", "tense", "flustered")


#: 근육 세기 배열의 순서 — 화면(useGazeLog)이 넣는 순서와 같아야 한다.
SMILE, WORRY, WIDE = 0, 1, 2

#: 이 아래는 움직이지 않은 것으로 본다.
#:
#: 사람마다 분포로 기준을 잡되(아래 `_thresholds`), 아무도 표정을 짓지 않은
#: 면접에서까지 상위 몇 %를 억지로 "미소"라고 부르지 않으려면 바닥이 필요하다.
#: 실측에서 무표정한 사람의 미소가 0.000, 눈크게가 0.002였다.
_FLOOR = 0.01

#: 이 분위수를 넘으면 그 표정으로 센다. 85면 한 표정이 최대 15%다.
_QUANTILE = 0.85


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def _thresholds(rows: list[dict[str, Any]]) -> list[float]:
    """근육마다 "이 사람 기준으로 두드러진" 경계.

    **절댓값을 못 박지 않는 이유가 실측이다.** 아바타를 움직이려고 만든
    블렌드셰이프의 눈금에서, 면접 중의 표정은 0.00~0.09에 깔린다. 처음에 0.14~0.22로
    잡았더니 132초 내내 아무것도 안 걸려 집중 100%가 나왔다. 그렇다고 0.04처럼
    낮춰 박으면 조명이 다르거나 얼굴이 다른 다음 사람에게서 또 틀린다.

    그래서 그 면접의 분포에서 뽑는다. 바닥(`_FLOOR`)을 같이 두는 것은, 아무도
    표정을 짓지 않은 면접에서 상위 15%를 억지로 "미소"라고 부르지 않기 위해서다.
    """
    out = []
    for index in (SMILE, WORRY, WIDE):
        values = [
            row["s"][index]
            for row in rows
            if isinstance(row.get("s"), list) and len(row["s"]) > index
        ]
        out.append(max(_quantile(values, _QUANTILE), _FLOOR))
    return out


def _impression(strengths: list[float], limits: list[float], steady: bool) -> str:
    """이 초가 어떻게 보였는가. 경계를 넘은 것 중 가장 크게 넘은 것을 고른다."""
    scores = [
        (strengths[i] / limits[i], i)
        for i in (WIDE, WORRY, SMILE)
        if limits[i] > 0 and strengths[i] >= limits[i]
    ]
    if not scores:
        return "focused"
    _, which = max(scores)
    if which == WIDE:
        return "flustered"
    if which == WORRY:
        return "tense"
    return "confident" if steady else "focused"


def _reclassify(rows: list[dict[str, Any]]) -> None:
    """기록된 근육 세기로 인상을 다시 매긴다.

    화면도 프레임마다 분류하지만 그때는 이 면접의 분포를 모른다 — 전체를 본 뒤에야
    "이 사람 기준으로 두드러진 표정"을 정할 수 있어서 여기서 덮어쓴다. 세기를
    기록해 둔 덕분에 지난 면접도 다시 계산된다.
    """
    usable = [r for r in rows if isinstance(r.get("s"), list) and len(r["s"]) >= 3]
    if not usable:
        return
    limits = _thresholds(usable)
    for row in usable:
        ratio = row.get("ratio")
        steady = isinstance(ratio, (int, float)) and ratio < 3
        row["impression"] = _impression(row["s"], limits, steady)


def _fold(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """줄들을 비율로 접는다. 빈 목록이면 전부 0이고 frames가 0이다."""
    cells = [0] * CELLS
    impressions = {key: 0 for key in IMPRESSIONS}
    wander = 0.0
    for row in rows:
        cell = row.get("cell")
        if isinstance(cell, int) and 0 <= cell < CELLS:
            cells[cell] += 1
        key = row.get("impression")
        if key in impressions:
            impressions[key] += 1
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
            "impressions": {key: 0.0 for key in IMPRESSIONS},
        }
    return {
        "seconds": total,
        "cells": [round(count / total, 4) for count in cells],
        "steady": round(cells[CENTER_CELL] / total, 4),
        "wander": round(wander / total, 2),
        "impressions": {
            key: round(count / total, 4) for key, count in impressions.items()
        },
    }


#: 타임라인 띠에 그릴 칸 수. 20분이든 5분이든 같은 폭에 담기게 접는다.
_SERIES_SLOTS = 48


def _series(rows: list[dict[str, Any]]) -> list[str]:
    """시간 순서를 잃지 않게 압축한 인상 띠.

    비율만 보여주면 "언제" 그랬는지가 사라진다 — 긴장이 20%라도 첫 답변에
    몰렸는지 내내 흩어져 있었는지는 다른 이야기다. 칸마다 그 구간에서 가장
    많았던 인상을 넣는다.
    """
    if not rows:
        return []
    slots = min(_SERIES_SLOTS, len(rows))
    out: list[str] = []
    for i in range(slots):
        chunk = rows[i * len(rows) // slots : (i + 1) * len(rows) // slots] or rows[-1:]
        counts: dict[str, int] = {}
        for row in chunk:
            key = row.get("impression")
            if key in IMPRESSIONS:
                counts[key] = counts.get(key, 0) + 1
        out.append(max(counts, key=counts.get) if counts else "focused")
    return out


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

    # 인상은 전체 분포를 본 뒤에 다시 매긴다 — 화면은 그때 분포를 모른다.
    _reclassify(rows)

    payload = _fold(rows)
    payload["series"] = _series(rows)
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
