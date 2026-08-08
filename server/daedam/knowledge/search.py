"""세션 단위 인프로세스 검색.

코퍼스가 청크 35개 안팎이라 BM25로 충분하고, 면접 중 네트워크 호출을 임계
경로에 두지 않는다. 재현율이 부족하면 `Knowledge.search` 구현만 임베딩으로
교체한다 — 호출부는 그대로 둔다.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from .chunk import Chunk, Source

#: BM25 점수가 이 값 이하인 결과는 무관한 것으로 보고 버린다.
_MIN_SCORE = 0.0


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

        scores = self._bm25.get_scores(tokens)
        ranked = sorted(
            (
                (score, chunk)
                for score, chunk in zip(scores, self._chunks)
                if score > _MIN_SCORE and (source is None or chunk.source == source)
            ),
            key=lambda pair: pair[0],
            reverse=True,
        )
        return [chunk for _, chunk in ranked[:k]]
