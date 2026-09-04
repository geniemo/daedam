"""면접 스냅샷을 Gemini로 판독해 "면접관에게 어떻게 보였는가"를 만든다.

**왜 근육(블렌드셰이프)이 아니라 VLM인가.** 근육은 움직임을 재고, 인상은 그림
전체에서 읽힌다. 면접의 정상 상태인 차분한 얼굴은 근육 움직임이 0에 깔려서,
근육 기반 분류는 어떤 문턱을 줘도 한 칸으로 몰렸다 — 실측에서 132초 내내 미소
0.000, "집중 100%"가 나왔고, 모델의 무표정 기준점 자체가 고개 각도 따라 세션마다
움직였다(mouthPucker 중앙값 0.01~0.88). 같은 녹화를 아래 프롬프트로 읽힌
프로브(2026-09-02)에서는 층이 생기고(집중 45~51 / 자신감 ~21 / 긴장 ~20 / 당황
~10), 같은 입력 2회의 평균 편차가 ±5 안이었으며, 실제 미소 프레임에 자신감 45,
얼굴을 만진 프레임에 당황 30이 붙었다 — 계기가 진짜 신호에 반응한다는 증거다.

**조각 병렬 호출.** 출력이 프레임당 ~50토큰이라 20분(400장)을 한 호출에 넣으면
생성만 몇 분이다. 60장씩 잘라 병렬로 부르면 벽시계가 조각 하나 값으로 떨어진다.
채점 기준이 조각마다 흔들리지 않도록 앵커 문구를 모든 조각에 똑같이 싣고,
관찰(observations)은 조각마다 받아 마지막에 한 번 합친다.

**실패는 조각 단위로 버린다.** 한 조각이 끝내 실패해도 나머지로 분포는 나온다 —
3초 표본에서 60장의 구멍은 구간 하나가 빠지는 것이지 판독 전체의 실패가 아니다.

API 확인 경로: daedam/llm.py (OpenAI 호환 `parse`). 이미지는 chat content의
`image_url`(data URL)로 싣는다 — 이 엔드포인트에서 동작하는 것과 320×240 JPEG이
장당 258토큰인 것을 프로브 실호출로 확인했다.
"""

from __future__ import annotations

import base64
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from daedam.llm import MODEL_QUALITY, text_client

logger = logging.getLogger(__name__)

#: 스냅샷이 쌓이는 디렉터리 이름. 업로드 라우트(interview_routes)가 같이 쓴다.
FRAMES_DIR = "frames"

#: 판독 결과를 남겨 두는 파일. 프레임별 원값이 있어야 프롬프트를 고친 뒤
#: 지난 면접을 다시 읽힐 수 있다 — 블렌드셰이프 시절 세기를 남겨 둔 덕에
#: 재녹화 없이 비교했던 그 이유다.
VLM_NAME = "vlm.json"

#: 인상 축. 리포트 계약의 키라 화면(web/src/video/expression.ts)과 같아야 한다.
IMPRESSIONS = ("confident", "focused", "tense", "flustered")

_MODEL = MODEL_QUALITY

#: 조각당 프레임 수. 출력 ~50토큰/장 × 60장 ≈ 3천 토큰 → 조각 하나 30초 안팎.
_CHUNK_FRAMES = 60

#: 판독 호출의 상한. 배치지만 무한정 매달리면 분석 화면이 그만큼 기다린다.
_TIMEOUT_S = 180.0

#: 동시에 나가는 조각 수. 20분 면접이 조각 7개라 이 정도면 두 바퀴로 끝난다.
_WORKERS = 4

#: 타임라인 띠의 칸 수. 시선 띠와 같은 폭이어야 화면에서 나란히 읽힌다.
_SERIES_SLOTS = 48


class FrameImpression(BaseModel):
    """스틸 한 장의 판독."""

    index: int = Field(description="받은 순서 그대로의 프레임 번호")
    confident: int = Field(ge=0, le=100)
    focused: int = Field(ge=0, le=100)
    tense: int = Field(ge=0, le=100)
    flustered: int = Field(ge=0, le=100)
    gaze: Literal["camera", "screen", "left", "right", "up", "down"] = Field(
        description="지원자 본인 기준의 시선 방향. 렌즈 응시는 camera,"
        " 카메라 아래 화면을 보는 살짝 낮은 정면은 screen, 화면 밖 아래"
        "(책상·메모)는 down, 지원자의 왼쪽·오른쪽·위는 left/right/up"
    )
    note: str = Field(description="배분의 근거 — 입·눈썹·시선·자세처럼 보이는 것 한 줄")


class ChunkReading(BaseModel):
    frames: list[FrameImpression]
    strengths: list[str] = Field(
        description="이 구간에서 화면상 잘 하고 있는 것 0~2개 — 근거가 보일 때만."
        " 없으면 빈 목록이 정직하다"
    )
    observations: list[str] = Field(
        description="이 구간에서 지원자가 다음 면접에 고칠 수 있는 것 1~3개. 구체적으로"
    )


class MergedAdvice(BaseModel):
    strengths: list[str] = Field(
        description="잘한 점 — 겹치는 항목을 합쳐 최대 2개. 각각 한 문장"
    )
    observations: list[str] = Field(
        description="고칠 점 — 겹치는 항목을 합쳐 중요한 순서로 최대 3개. 각각 한 문장"
    )


def list_frames(directory: Path) -> list[tuple[float, Path]]:
    """이름이 곧 시각(f00012.3.jpg)인 스냅샷 목록 — 시각 오름차순.

    이름을 시각으로 못 읽는 파일은 조용히 건너뛴다. 우리 클라이언트가 만든
    이름이 아니면 판독에 넣을 근거도 없다.
    """
    out: list[tuple[float, Path]] = []
    for path in directory.glob("f*.jpg"):
        try:
            at = float(path.name[1:-4])
        except ValueError:
            continue
        out.append((at, path))
    return sorted(out)


def _prompt(start: float, end: float, count: int) -> str:
    """조각 하나의 지시문. **앵커는 모든 조각에 똑같이** — 조각 사이 기준이
    흔들리면 병렬로 자른 경계가 분포에 무늬로 남는다."""
    return (
        "AI 모의면접 서비스의 리포트다. 지원자 본인이 자기 연습 영상의 분석을 요청했다.\n"
        f"아래는 면접 한 판에서 3초 간격으로 뽑은 스틸 중 경과 {start:.0f}~{end:.0f}초"
        f" 구간의 {count}장이다. 프레임마다 화상 면접관이 그 순간 받는 인상 100을"
        " 자신감·집중·긴장·당황 네 축에 배분하라(합계 100).\n"
        "- 앵커: 그 축의 근거가 프레임에 보이지 않으면 0~5로 두어라. 중앙값(25 언저리)으로 도망가지 마라.\n"
        "  자신감: 미소·여유 있는 입가·꼿꼿한 자세 같은 적극적 근거가 보일 때만 올린다.\n"
        "  집중: 차분한 무표정 + 안정된 시선. 특별한 근거가 없는 평온한 순간의 기본값이다.\n"
        "  긴장: 굳은 입·눌린 입술·경직된 어깨·얼어붙은 표정.\n"
        "  당황: 커진 눈·급격한 시선 이탈·말문이 막힌 표정.\n"
        "- gaze는 **지원자 본인 기준**의 방향이다 — 영상의 좌우가 아니라 그 사람의"
        " 왼쪽·오른쪽으로 답하라.\n"
        "- 프레임 사이 차이를 드러내라. note에 배분의 근거를 한 줄로 적어라.\n"
        "- observations에는 이 구간에서 지원자가 다음 면접에 고칠 것 1~3개 —"
        " 시선·표정·자세·손동작, 얼굴을 가리는 것, 조명·카메라 높이처럼 그 자리에서"
        " 고칠 수 있는 것만. **복장·외모 품평은 하지 마라** — 연습 도구가 회차마다"
        " 옷차림을 지적하면 코칭이 아니라 잔소리다.\n"
        "- strengths에는 화면상 잘 하고 있는 것 0~2개 — 근거가 보일 때만 적고,"
        " 없으면 비워 두어라. 억지 칭찬은 나머지 판독의 신뢰까지 깎는다.\n"
    )


def _content(chunk: list[tuple[float, Path]]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = [
        {"type": "text", "text": _prompt(chunk[0][0], chunk[-1][0], len(chunk))}
    ]
    for index, (at, path) in enumerate(chunk):
        parts.append({"type": "text", "text": f"프레임 {index} (경과 {at:.0f}초)"})
        parts.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/jpeg;base64,"
                    + base64.b64encode(path.read_bytes()).decode()
                },
            }
        )
    return parts


def _read_chunk(client: Any, chunk: list[tuple[float, Path]]) -> ChunkReading | None:
    """조각 하나를 판독한다. 한 번 더 해보고 안 되면 버린다 — 조각 단위 실패 허용."""
    for attempt in (1, 2):
        try:
            done = client.beta.chat.completions.parse(
                model=_MODEL,
                messages=[{"role": "user", "content": _content(chunk)}],
                response_format=ChunkReading,
                temperature=0,
            )
            return done.choices[0].message.parsed
        except Exception:
            if attempt == 2:
                logger.warning(
                    "스냅샷 조각 판독 실패 — %.0f~%.0f초 %d장을 버린다",
                    chunk[0][0], chunk[-1][0], len(chunk), exc_info=True,
                )
    return None


def _merge_advice(
    client: Any, strengths: list[str], fixes: list[str]
) -> tuple[list[str], list[str]]:
    """조각마다 받은 잘한 점·고칠 점을 하나로 합친다.

    조각들이 같은 것을 다른 말로 지적한다("카메라를 눈높이로" ×3). 글자
    비교로는 못 합치므로 텍스트 호출 하나로 정리한다 — 실패하면 앞에서 자르고
    산다. 겹친 채 나가는 것이지 틀린 것이 아니라서다.

    캡(잘한 점 2·고칠 점 3)은 이 목록이 종합 평가의 코칭 항목에 **합쳐지기**
    때문이다 — 내용 조언 2~3개 옆에 전달 조언이 그보다 길게 붙으면 목록이
    한쪽으로 분다(실측 지적: "보완할 점이 되게 많은데").
    """
    if len(strengths) <= 2 and len(fixes) <= 3:
        return strengths, fixes
    try:
        done = client.beta.chat.completions.parse(
            model=_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": "화상 모의면접 판독에서 구간마다 나온 코멘트다."
                    " 겹치는 항목을 합쳐 잘한 점 최대 2개, 고칠 점 최대 3개만"
                    " 남겨라.\n잘한 점:\n- "
                    + "\n- ".join(strengths or ["(없음)"])
                    + "\n고칠 점:\n- "
                    + "\n- ".join(fixes or ["(없음)"]),
                }
            ],
            response_format=MergedAdvice,
            temperature=0,
        )
        parsed = done.choices[0].message.parsed
        return parsed.strengths[:2], parsed.observations[:3]
    except Exception:
        logger.warning("관찰 취합 실패 — 그대로 자른다", exc_info=True)
        return strengths[:2], fixes[:3]


def judge(directory: Path, *, client: Any | None = None) -> dict[str, Any] | None:
    """스냅샷 디렉터리 전체를 판독해 프레임별 원값을 돌려주고 `vlm.json`으로 남긴다.

    Args:
        directory: `FRAMES_DIR` 경로.
        client: OpenAI 호환 클라이언트. 테스트가 대역을 주입한다.

    Returns:
        {"model", "frames": [{"at", confident, focused, tense, flustered, "note"}],
         "observations"} — 읽을 프레임이 없거나 전부 실패하면 None.
    """
    frames = list_frames(directory)
    if not frames:
        return None
    if client is None:
        client = text_client(timeout_s=_TIMEOUT_S)

    chunks = [frames[i : i + _CHUNK_FRAMES] for i in range(0, len(frames), _CHUNK_FRAMES)]
    with ThreadPoolExecutor(max_workers=min(_WORKERS, len(chunks))) as pool:
        readings = list(pool.map(lambda chunk: _read_chunk(client, chunk), chunks))

    rows: list[dict[str, Any]] = []
    collected: list[str] = []
    praised: list[str] = []
    for chunk, reading in zip(chunks, readings):
        if reading is None:
            continue
        for frame in reading.frames:
            # 시각은 우리가 보낸 순서에서 되찾는다. 모델이 번호를 벗어나 지어내면
            # 붙일 시각이 없으므로 버린다.
            if not 0 <= frame.index < len(chunk):
                continue
            rows.append(
                {
                    "at": chunk[frame.index][0],
                    "confident": frame.confident,
                    "focused": frame.focused,
                    "tense": frame.tense,
                    "flustered": frame.flustered,
                    "gaze": frame.gaze,
                    "note": frame.note,
                }
            )
        collected.extend(reading.observations)
        praised.extend(reading.strengths)
    if not rows:
        return None
    rows.sort(key=lambda row: row["at"])

    strengths, fixes = _merge_advice(client, praised, collected)
    payload = {
        "model": _MODEL,
        "frames": rows,
        "strengths": strengths,
        "observations": fixes,
    }
    (directory / VLM_NAME).write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    return payload


# ── 접기 (순수 계산 — 테스트는 여기만 두드려도 된다) ─────────────────────────


def _shares(row: dict[str, Any]) -> dict[str, float] | None:
    """한 프레임의 배분을 합 1로 정규화. 합이 0이면(전부 0) 잴 것이 없다."""
    total = sum(int(row.get(key) or 0) for key in IMPRESSIONS)
    if total <= 0:
        return None
    return {key: int(row.get(key) or 0) / total for key in IMPRESSIONS}


def _mean(shares: list[dict[str, float]]) -> dict[str, float]:
    count = len(shares) or 1
    return {
        key: round(sum(share[key] for share in shares) / count, 4)
        for key in IMPRESSIONS
    }


def _dominant(share: dict[str, float]) -> str:
    return max(IMPRESSIONS, key=lambda key: share[key])


def _series(rows: list[dict[str, Any]]) -> list[str]:
    """시간 순서를 잃지 않게 압축한 인상 띠. 칸마다 그 구간의 우세 인상."""
    shared = [(row["at"], _shares(row)) for row in rows]
    shared = [(at, share) for at, share in shared if share is not None]
    if not shared:
        return []
    slots = min(_SERIES_SLOTS, len(shared))
    out: list[str] = []
    for i in range(slots):
        piece = shared[i * len(shared) // slots : (i + 1) * len(shared) // slots] or shared[-1:]
        counts: dict[str, int] = {}
        for _, share in piece:
            key = _dominant(share)
            counts[key] = counts.get(key, 0) + 1
        out.append(max(counts, key=counts.get))
    return out


#: 판독의 시선 방향 → 리포트 3×3 격자 칸. **screen도 정면(4)이다** — 웹캠이
#: 화면 위에 있어서 화면 응시는 살짝 아래로 보이는 정면이고, 화상 면접에서
#: 그것이 정상적인 "면접관을 보는" 상태다. down은 화면 밖(책상·메모)만이다.
#: left/right는 지원자 기준이라, 홍채 기하가 카메라 시점 좌표로 라벨을 뒤집던
#: 문제(실측: 오른쪽 셀프뷰를 보는데 "왼쪽 58.7%")가 원리적으로 없다.
_GAZE_CELL = {"camera": 4, "screen": 4, "left": 3, "right": 5, "up": 1, "down": 7}


def _gaze_fold(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """시선 방향을 격자 비율로. 방향이 없는 행(옛 판독)뿐이면 None."""
    cells = [0] * 9
    counted = 0
    for row in rows:
        cell = _GAZE_CELL.get(row.get("gaze"))
        if cell is None:
            continue
        cells[cell] += 1
        counted += 1
    if counted == 0:
        return None
    return {
        # 3초당 한 장이므로 장수 × 3이 관찰된 시간의 근사다 — 화면의
        # "얼굴이 보인 시간" 경고가 이 눈금으로 걸린다.
        "seconds": counted * 3,
        "cells": [round(c / counted, 4) for c in cells],
        "steady": round(cells[4] / counted, 4),
        "source": "vlm",
    }


def fold(
    judgement: dict[str, Any],
    answers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """판독 원값을 리포트가 그릴 형태로 접는다 — 전체 평균 + 답변별.

    답변 경계로 자르는 일을 서버가 하는 이유: 그 경계가 면접이 끝난 뒤 오디오
    분석에서야 나온다 — 화면은 면접이 도는 동안 그 경계를 모른다.
    """
    rows = judgement.get("frames") or []
    shares = [share for row in rows if (share := _shares(row)) is not None]
    gaze = _gaze_fold(rows)
    if gaze is not None:
        gaze["answers"] = []
        for answer in answers or []:
            start = answer.get("startS")
            end = answer.get("endS")
            inside = (
                [row for row in rows if start <= row["at"] < end]
                if isinstance(start, (int, float)) and isinstance(end, (int, float))
                else []
            )
            gaze["answers"].append(
                _gaze_fold(inside)
                or {"seconds": 0, "cells": [0.0] * 9, "steady": 0.0}
            )
    payload: dict[str, Any] = {
        "gaze": gaze,
        "frames": len(shares),
        "impressions": _mean(shares) if shares else {key: 0.0 for key in IMPRESSIONS},
        "series": _series(rows),
        "strengths": list(judgement.get("strengths") or []),
        "observations": list(judgement.get("observations") or []),
        "answers": [],
    }
    for answer in answers or []:
        start = answer.get("startS")
        end = answer.get("endS")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            payload["answers"].append(
                {"frames": 0, "impressions": {key: 0.0 for key in IMPRESSIONS}}
            )
            continue
        inside = [
            share
            for row in rows
            if start <= row["at"] < end and (share := _shares(row)) is not None
        ]
        payload["answers"].append(
            {
                "frames": len(inside),
                "impressions": _mean(inside)
                if inside
                else {key: 0.0 for key in IMPRESSIONS},
            }
        )
    return payload
