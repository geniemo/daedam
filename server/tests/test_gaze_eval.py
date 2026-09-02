"""시선 타임라인 접기 테스트.

화면이 초당 한 줄로 올린 것을 면접 전체와 답변별 비율로 접는다. 자르는 일이
서버에 있는 이유는 답변 구간이 면접이 끝난 뒤에야 나오기 때문이다.

표정은 여기 없다 — eval/expression.py(스냅샷 VLM 판독)로 옮겨 갔다.
"""

from daedam.eval.gaze import CENTER_CELL, analyze


def _row(at: float, cell: int, ratio: float = 1.0) -> dict:
    return {"at": at, "cell": cell, "ratio": ratio}


def test_담긴_줄이_없으면_None() -> None:
    """정면 기준을 안 잡았거나 얼굴이 한 번도 안 잡힌 면접이다 —
    0%로 채우면 "정면을 한 번도 안 봤다"는 없는 사실이 된다."""
    assert analyze({"seconds": []}) is None
    assert analyze({}) is None


def test_전체_비율을_낸다() -> None:
    rows = [_row(i, CENTER_CELL) for i in range(6)]
    rows += [_row(i, 1, 5.0) for i in range(6, 10)]
    got = analyze({"seconds": rows})

    assert got["seconds"] == 10
    assert got["steady"] == 0.6                      # 정면 6/10
    assert got["cells"][CENTER_CELL] == 0.6
    assert got["cells"][1] == 0.4                    # 위 4/10
    assert got["wander"] == 2.6                      # (6×1 + 4×5) / 10
    assert sum(got["cells"]) == 1.0


def test_답변_구간으로_자른다() -> None:
    """같은 면접에서도 답변마다 다르게 나와야 쓸모가 있다."""
    rows = [_row(i, CENTER_CELL) for i in range(0, 10)]
    rows += [_row(i, 7, 6.0) for i in range(10, 20)]
    got = analyze(
        {"seconds": rows},
        [{"startS": 0.0, "endS": 10.0}, {"startS": 10.0, "endS": 20.0}],
    )

    first, second = got["answers"]
    assert first["seconds"] == 10 and first["steady"] == 1.0
    assert second["seconds"] == 10 and second["steady"] == 0.0
    assert second["wander"] == 6.0


def test_답변_구간에_담긴_줄이_없으면_0이다() -> None:
    """얼굴을 못 찾은 동안의 답변이다. 빈 값으로 두고 화면이 그렇게 말한다."""
    got = analyze(
        {"seconds": [_row(1, CENTER_CELL)]},
        [{"startS": 50.0, "endS": 60.0}],
    )
    (only,) = got["answers"]
    assert only["seconds"] == 0 and only["steady"] == 0.0


def test_모르는_칸은_세지_않는다() -> None:
    """화면과 서버의 격자 규약이 어긋나도 비율이 깨지지 않아야 한다."""
    rows = [_row(0, CENTER_CELL), _row(1, 99)]
    got = analyze({"seconds": rows})
    assert got["seconds"] == 2
    assert got["steady"] == 0.5                       # 아는 것만 셌다
