"""세션 단위 인프로세스 검색.

코퍼스가 청크 35개 안팎이라 BM25로 충분하고, 면접 중 네트워크 호출을 임계
경로에 두지 않는다. 재현율이 부족하면 `Knowledge.search` 구현만 임베딩으로
교체한다 — 호출부는 그대로 둔다.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from .chunk import Chunk, Source

#: 질의 토큰 중 이 비율 이상을 포함해야 관련 있다고 본다.
#:
#: BM25 점수만으로는 관련성을 판정할 수 없다. 코퍼스가 작으면 IDF가 0으로
#: 수렴해(N=2, df=1이면 정확히 0) 관련 문서도 0점을 받기 때문이다. 그래서
#: 순위는 BM25에 맡기고 관련성 판정은 토큰 겹침 비율로 한다.
#:
#: 0.35는 실측으로 정했다 — 관련 질의는 57~73%, 무관 질의는 0~27%였다.
_MIN_OVERLAP_RATIO = 0.35


def _tokenize(text: str) -> list[str]:
    """한국어 텍스트를 문자 bigram으로 쪼갠다.

    형태소 분석기 없이 한국어를 색인하는 표준적인 저비용 방법이다.
    공백을 제거해 "정산 서비스"와 "정산서비스"가 같게 잡히도록 한다.

    Args:
        text: 원본 문자열.

    Returns:
        길이 2 문자열 목록. 입력이 2자 미만이면 빈 목록.
    """
    squeezed = re.sub(r"\s+", "", text)
    return [squeezed[i : i + 2] for i in range(len(squeezed) - 1)]


class Knowledge:
    """리서치 리포트와 지원서를 함께 담는 세션 하나의 검색 인덱스."""

    def __init__(self, chunks: list[Chunk]) -> None:
        """인덱스를 만든다.

        Args:
            chunks: 색인할 청크 목록. 비어 있어도 된다.
        """
        self._chunks = chunks
        # 제목도 본문에 합쳐 색인한다 — 항목 제목이 질의어와 겹치는 경우가 많다.
        corpus = [_tokenize(c.title + c.text) for c in chunks]
        self._bm25 = BM25Okapi(corpus) if corpus else None
        # 겹침 판정용. 검색마다 다시 만들지 않도록 미리 집합으로 둔다.
        self._token_sets = [set(tokens) for tokens in corpus]

    def search(
        self,
        query: str,
        k: int = 3,
        source: Source | None = None,
    ) -> list[Chunk]:
        """질의와 관련된 청크를 점수 높은 순으로 돌려준다.

        Args:
            query: 자연어 질의.
            k: 최대 결과 개수.
            source: 지정하면 해당 출처의 청크만 대상으로 한다.

        Returns:
            관련 Chunk 목록. 인덱스가 비었거나 질의가 비었거나 관련 청크가
            없으면 빈 목록. 예외를 던지지 않는다.
        """
        tokens = _tokenize(query)
        if self._bm25 is None or not tokens:
            return []

        query_set = set(tokens)
        scores = self._bm25.get_scores(tokens)

        matched: list[tuple[float, int, Chunk]] = []
        for score, overlap_set, chunk in zip(scores, self._token_sets, self._chunks):
            if source is not None and chunk.source != source:
                continue
            overlap = len(query_set & overlap_set)
            if overlap / len(query_set) < _MIN_OVERLAP_RATIO:
                continue
            matched.append((score, overlap, chunk))

        # BM25 점수 우선, 동점이면 겹친 토큰 수로 가른다. 코퍼스가 작아
        # 모든 점수가 0인 경우에도 순위가 정해진다.
        matched.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [chunk for _, _, chunk in matched[:k]]
