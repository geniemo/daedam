"""로컬 임베딩 — 의미 검색 백엔드.

키워드(BM25)만으로는 "UX"와 "사용자 경험"이 만나지 못하고, 음성 전사가
표기를 흔들면("유엑스") 정확 일치는 더 깨진다. 그래서 질의 임베딩을 로컬
GPU에서 돌려 네트워크 없이 의미 매칭을 얹는다 — 검색이 면접 발화가 멈추는
임계 경로에 있어, 질의마다 외부 API를 부르는 설계는 피한다.

모델은 KURE-v1(BGE-M3의 한국어 검색 특화 파인튜닝, 공개 모델)이다. 로드에
수 초가 걸리므로 서버 기동 시점에 `default_embedder()`를 한 번 불러 예열한다.
"""

from __future__ import annotations

import logging
import os
import threading

import numpy as np

logger = logging.getLogger(__name__)

_MODEL_NAME = "nlpai-lab/KURE-v1"

#: 끄기 스위치. off면 BM25 단독으로 동작한다(테스트·CPU 전용 배포).
_ENV_SWITCH = "SEARCH_EMBEDDINGS"


class LocalEmbedder:
    """sentence-transformers 모델을 감싼 임베더."""

    def __init__(self, model_name: str = _MODEL_NAME) -> None:
        # 지연 임포트 — torch가 없는 환경에서도 이 모듈 임포트는 성립해야 한다.
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> np.ndarray:
        """텍스트를 정규화된 벡터로 인코딩한다. 내적이 곧 코사인 유사도다."""
        return self._model.encode(texts, normalize_embeddings=True)


_lock = threading.Lock()
_embedder: LocalEmbedder | None = None
_load_failed = False


def default_embedder() -> LocalEmbedder | None:
    """공유 임베더를 돌려준다.

    SEARCH_EMBEDDINGS=off거나 모델 로드가 실패하면 None — 호출부는 BM25만
    쓰는 것으로 자연히 강등된다. 실패는 한 번만 기록하고 다시 시도하지
    않는다(면접 중 반복 재시도로 지연을 만들지 않기 위해).
    """
    global _embedder, _load_failed
    if os.environ.get(_ENV_SWITCH, "local") == "off" or _load_failed:
        return None
    with _lock:
        if _embedder is None and not _load_failed:
            try:
                _embedder = LocalEmbedder()
            except Exception:
                logger.exception("임베딩 모델 로드 실패 — BM25 단독으로 동작합니다")
                _load_failed = True
    return _embedder
