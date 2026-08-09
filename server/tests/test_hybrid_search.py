"""하이브리드 검색 테스트.

실제 임베딩 모델은 로드하지 않는다(conftest에서 SEARCH_EMBEDDINGS=off).
의미 경로는 결정론적 대역 임베더로 검증하고, 실모델의 품질·지연은 프로브
스크립트가 잰다.
"""

import numpy as np

from daedam.knowledge.chunk import Chunk
from daedam.knowledge.search import KnowledgeIndex


class _FakeEmbedder:
    """키워드 그룹을 축으로 하는 결정론적 대역.

    같은 그룹의 키워드를 담은 텍스트는 같은 축의 단위 벡터가 된다 —
    "UX"와 "사용자 경험"이 의미 공간에서 만나는 상황의 최소 재현이다.
    """

    def __init__(self, groups: list[list[str]]) -> None:
        self._groups = groups

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), len(self._groups) + 1))
        for row, text in enumerate(texts):
            for axis, keywords in enumerate(self._groups):
                if any(keyword in text for keyword in keywords):
                    vectors[row, axis] = 1.0
                    break
            else:
                vectors[row, -1] = 1.0
        return vectors


UX_DOC = Chunk(
    id="app-0-0",
    source="application",
    title="프로젝트 경험",
    text="사용자 경험을 개선한 프로젝트를 진행했습니다.",
)
LOGISTICS_DOC = Chunk(
    id="blk-0-0",
    source="research",
    title="주력 사업",
    text="화물 배차 자동화 시스템을 운영한다.",
)
GROUPS = [["UX", "유엑스", "사용자 경험"], ["배차", "운송", "트럭"]]


def _hybrid() -> KnowledgeIndex:
    return KnowledgeIndex([UX_DOC, LOGISTICS_DOC], embedder=_FakeEmbedder(GROUPS))


def test_bm25만으로는_동의어를_못_잇는다() -> None:
    """이 한계가 임베딩을 얹은 이유다 — 기준선으로 기록해 둔다."""
    assert KnowledgeIndex([UX_DOC, LOGISTICS_DOC]).search("UX") == []


def test_동의어_질의가_의미_경로로_이어진다() -> None:
    results = _hybrid().search("UX")
    assert [chunk.id for chunk in results] == ["app-0-0"]


def test_전사_표기_변형도_이어진다() -> None:
    """음성 전사가 "유엑스"라고 적어도 같은 의미 축에 떨어진다."""
    results = _hybrid().search("유엑스")
    assert [chunk.id for chunk in results] == ["app-0-0"]


def test_무관한_질의는_여전히_빈_결과() -> None:
    """게이트 — 임베더가 있어도 아무 데나 걸리면 안 된다."""
    assert _hybrid().search("김치찌개 조리법") == []


def test_어휘_일치_검색은_그대로_동작한다() -> None:
    results = _hybrid().search("배차 자동화")
    assert results and results[0].id == "blk-0-0"


def test_source_필터는_융합_결과에도_적용된다() -> None:
    assert _hybrid().search("UX", source="research") == []
