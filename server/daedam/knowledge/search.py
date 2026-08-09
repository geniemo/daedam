"""세션 단위 인프로세스 하이브리드 검색.

두 랭커를 함께 쓴다. BM25(문자 bigram)는 지원자가 지원서에 쓴 표현이 답변에
그대로 나올 때 강하고, 로컬 임베딩은 표현이 갈릴 때("UX" ↔ "사용자 경험",
전사 표기 흔들림) 강하다. 두 랭킹을 RRF로 합쳐 순위를 내고, 관련성 판정은
어느 한쪽 신호라도 충분하면 통과시킨다.

코퍼스가 청크 35개 안팎이라 융합 계산은 1ms 미만이고, 임베딩까지 로컬이라
면접 중 임계 경로에 네트워크 호출이 없다. 임베더가 없으면(환경 스위치 off,
모델 로드 실패) BM25 단독으로 자연히 강등된다.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from .chunk import Chunk, Source
from .embedding import LocalEmbedder

#: 질의 토큰 중 이 비율 이상을 포함해야 어휘적으로 관련 있다고 본다.
#:
#: BM25 점수만으로는 관련성을 판정할 수 없다. 코퍼스가 작으면 IDF가 0으로
#: 수렴해(N=2, df=1이면 정확히 0) 관련 문서도 0점을 받기 때문이다. 그래서
#: 순위는 BM25에 맡기고 관련성 판정은 토큰 겹침 비율로 한다.
#:
#: 0.35는 실측으로 정했다 — 관련 질의는 57~73%, 무관 질의는 0~27%였다.
_MIN_OVERLAP_RATIO = 0.35

#: 이 코사인 유사도 이상이면 의미적으로 관련 있다고 본다.
#:
#: KURE-v1 실측으로 정했다 — 동의어·패러프레이즈 질의는 이 위로("UX"↔"사용자
#: 경험" 0.56, "KPI 설정 능력"↔지표 정의 0.60, "일감 매칭 플랫폼"↔물류 중개
#: 0.57), 무관 질의는 0.44 이하로 갈렸다. 경계 사례 하나는 알고 버린다:
#: 전사 표기 변형만 남은 극단적으로 짧은 질의("유엑스 디자인" 0.43)는 무관
#: 소음의 상단(0.44)과 겹쳐 어떤 임계값으로도 깨끗이 가를 수 없다. 검색
#: 결과가 그대로 대화 컨텍스트에 실리므로 정밀도 쪽을 택한다.
_MIN_COSINE = 0.45

#: RRF 상수. 표준값 60 — 상위 몇 위 안에서의 순위 차이를 완만하게 반영한다.
_RRF_K = 60


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

    def __init__(
        self, chunks: list[Chunk], embedder: LocalEmbedder | None = None
    ) -> None:
        """인덱스를 만든다.

        Args:
            chunks: 색인할 청크 목록. 비어 있어도 된다.
            embedder: 의미 검색용 임베더. None이면 BM25 단독으로 동작한다.
                청크 벡터는 여기서 한 번 계산해 두므로, 인스턴스를 세션 동안
                재사용해야 검색마다 인코딩 비용이 다시 들지 않는다.
        """
        self._chunks = chunks
        # 제목도 본문에 합쳐 색인한다 — 항목 제목이 질의어와 겹치는 경우가 많다.
        texts = [c.title + c.text for c in chunks]
        corpus = [_tokenize(t) for t in texts]
        self._bm25 = BM25Okapi(corpus) if corpus else None
        # 겹침 판정용. 검색마다 다시 만들지 않도록 미리 집합으로 둔다.
        self._token_sets = [set(tokens) for tokens in corpus]
        self._embedder = embedder
        self._vectors = (
            embedder.encode(texts) if embedder is not None and texts else None
        )

    def search(
        self,
        query: str,
        k: int = 3,
        source: Source | None = None,
    ) -> list[Chunk]:
        """질의와 관련된 청크를 융합 순위로 돌려준다.

        Args:
            query: 자연어 질의.
            k: 최대 결과 개수.
            source: 지정하면 해당 출처의 청크만 대상으로 한다.

        Returns:
            관련 Chunk 목록. 인덱스가 비었거나 질의가 비었거나 관련 청크가
            없으면 빈 목록. 예외를 던지지 않는다.
        """
        tokens = _tokenize(query)
        if not self._chunks or (not tokens and self._vectors is None):
            return []

        candidates = [
            index
            for index, chunk in enumerate(self._chunks)
            if source is None or chunk.source == source
        ]
        if not candidates:
            return []

        query_set = set(tokens)
        overlaps = (
            {i: len(query_set & self._token_sets[i]) for i in candidates}
            if tokens
            else {}
        )
        bm25_scores = (
            self._bm25.get_scores(tokens)
            if self._bm25 is not None and tokens
            else None
        )
        cosines = None
        if self._embedder is not None and self._vectors is not None:
            query_vector = self._embedder.encode([query])[0]
            cosines = self._vectors @ query_vector

        # 관련성 게이트 — 어휘·의미 어느 한쪽이라도 신호가 충분하면 통과.
        # 두 신호를 다 요구하면 임베딩을 얹은 이유(어휘가 갈리는 경우)가 죽는다.
        gated = []
        for index in candidates:
            lexical_ok = (
                bool(tokens)
                and overlaps[index] / len(query_set) >= _MIN_OVERLAP_RATIO
            )
            semantic_ok = cosines is not None and cosines[index] >= _MIN_COSINE
            if lexical_ok or semantic_ok:
                gated.append(index)
        if not gated:
            return []

        # RRF 융합 — 점수 스케일이 다른 두 랭킹을 순위만으로 합친다.
        rankings = []
        if bm25_scores is not None:
            rankings.append(
                sorted(
                    candidates,
                    key=lambda i: (bm25_scores[i], overlaps.get(i, 0)),
                    reverse=True,
                )
            )
        if cosines is not None:
            rankings.append(sorted(candidates, key=lambda i: cosines[i], reverse=True))
        positions = [
            {index: rank for rank, index in enumerate(ranking)}
            for ranking in rankings
        ]

        def fused(index: int) -> float:
            return sum(1.0 / (_RRF_K + ranks[index]) for ranks in positions)

        gated.sort(key=fused, reverse=True)
        return [self._chunks[index] for index in gated[:k]]
