"""반복된 보완점 — 임베딩으로 묶어 회차를 가로질러 센다.

임베더는 대역이다. 문장마다 정해 둔 방향의 단위 벡터를 돌려주므로 코사인이
곧 우리가 정한 값이다. 진짜 임베더의 문턱(0.85)은 로컬 데이터로 실측했고
여기서는 묶는 규칙만 본다.
"""

from datetime import UTC, datetime

import numpy as np

from daedam.server.recurring import SAME_POINT, recurring_improvement
from daedam.server.store import InterviewRecord


class _Embedder:
    """문장 → 미리 정한 벡터. 모르는 문장은 저마다 직교한다."""

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors
        self.calls = 0

    def encode(self, texts: list[str], *, query: bool = False) -> np.ndarray:
        del query
        self.calls += 1
        rows = []
        for i, text in enumerate(texts):
            row = np.zeros(8, dtype=np.float32)
            if text in self._vectors:
                row[: len(self._vectors[text])] = self._vectors[text]
            else:
                row[4 + i % 4] = 1.0
            rows.append(row / np.linalg.norm(row))
        return np.asarray(rows)


def _record(session: str, n: int, *improvements: str) -> InterviewRecord:
    return InterviewRecord(
        interview_id="aaa",
        session_id=session,
        company="누리테크",
        n=n,
        started_at=datetime(2026, 9, n, tzinfo=UTC),
        score=70,
        improvements=list(improvements),
    )


# 두 문장은 0.85보다 가깝고(같은 조언, 다른 표현), 셋째는 멀다.
_CLOSE = np.cos(np.arccos(SAME_POINT) * 0.8)
_VECTORS = {
    "자기소개에 전공을 넣으십시오": [1.0, 0.0],
    "이름만 말하지 말고 전공과 관심사를 소개하기": [_CLOSE, float(np.sqrt(1 - _CLOSE**2))],
    "카메라 렌즈를 보십시오": [0.0, 0.0, 1.0],
}


def test_표현이_달라도_같은_조언이면_판_수를_센다() -> None:
    records = [
        _record("s1", 1, "자기소개에 전공을 넣으십시오", "카메라 렌즈를 보십시오"),
        _record("s2", 2, "이름만 말하지 말고 전공과 관심사를 소개하기"),
    ]
    found = recurring_improvement(records, _Embedder(_VECTORS))
    # 대표 문장은 가장 최근 것 — 마지막으로 들은 표현이 지금 고칠 것에 가깝다.
    assert found == {"text": "이름만 말하지 말고 전공과 관심사를 소개하기", "count": 2}


def test_같은_판_안의_반복은_한_번이다() -> None:
    records = [_record("s1", 1, "자기소개에 전공을 넣으십시오", "자기소개에 전공을 넣으십시오")]
    assert recurring_improvement(records, _Embedder(_VECTORS)) is None


def test_멀면_묶이지_않는다() -> None:
    records = [
        _record("s1", 1, "자기소개에 전공을 넣으십시오"),
        _record("s2", 2, "카메라 렌즈를 보십시오"),
    ]
    assert recurring_improvement(records, _Embedder(_VECTORS)) is None


def test_판이_하나면_임베딩을_부르지_않는다() -> None:
    embedder = _Embedder(_VECTORS)
    assert recurring_improvement([_record("s1", 1, "자기소개에 전공을 넣으십시오")], embedder) is None
    assert embedder.calls == 0


def test_같은_판_집합은_한_번만_계산한다() -> None:
    embedder = _Embedder(_VECTORS)
    records = [
        _record("s1", 1, "자기소개에 전공을 넣으십시오"),
        _record("s2", 2, "이름만 말하지 말고 전공과 관심사를 소개하기"),
    ]
    first = recurring_improvement(records, embedder)
    assert recurring_improvement(records, embedder) == first
    assert embedder.calls == 1


def test_임베더가_없으면_없는_것으로(monkeypatch) -> None:
    """SEARCH_EMBEDDINGS=off거나 준비에 실패한 서버 — 기록 띠가 홈을 멈추면 안 된다."""
    import daedam.server.recurring as module

    monkeypatch.setattr(module, "default_embedder", lambda: None)
    records = [_record("s1", 1, "자기소개에 전공을 넣으십시오"), _record("s2", 2, "자기소개에 전공을 넣으십시오")]
    assert recurring_improvement(records) is None


def test_임베딩이_실패해도_기록은_나간다() -> None:
    class _Broken:
        def encode(self, texts, *, query=False):
            raise RuntimeError("network")

    records = [_record("s1", 1, "자기소개에 전공을 넣으십시오"), _record("s2", 2, "자기소개에 전공을 넣으십시오")]
    assert recurring_improvement(records, _Broken()) is None
