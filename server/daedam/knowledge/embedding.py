"""의미 검색용 임베더.

**기본은 Gemini 임베딩 API다.** 앞서는 로컬 모델(KURE-v1)을 올렸는데, 배포
대상인 2 vCPU·GPU 없는 VM에서 값이 감당되지 않았다 — 실측으로 청크 100개
인덱스가 **50초**, 질의 하나가 0.82초였고, 프로세스 메모리도 1.15 GB 늘었다.
같은 일을 API로 하면 인덱스 2.2초, 질의 0.47초이고 메모리는 0이다. 개발
머신에 GPU가 있어서 이 비용이 오래 보이지 않았다.

`SEARCH_EMBEDDINGS`로 고른다.
  gemini  Gemini 임베딩 API. 기본값.
  local   로컬 sentence-transformers 모델. 외부 호출을 피해야 하거나
          오프라인일 때. torch·sentence-transformers가 설치돼 있어야 한다.
  off     BM25 단독. 테스트와, 키가 없는 환경.

어느 쪽이든 실패하면 None을 돌려주고 호출부는 BM25 단독으로 자연히 강등된다 —
검색이 면접을 멈출 권리는 없다.

확인 경로 (설치된 google-genai):
  google/genai/models.py:6409 `embed_content(model=, contents=, config=)`
    — contents가 리스트면 배치로 돌아온다(실측 100개 2.2초)
  google/genai/types.py `EmbedContentConfig`
    — task_type · output_dimensionality
"""

from __future__ import annotations

import logging
import os
import threading

import numpy as np

logger = logging.getLogger(__name__)

#: 면접 중에 쓸 수 있는 유일한 임베딩 모델. 최신인 gemini-embedding-2는
#: 질의 하나에 2.16초가 걸려(실측) 면접이 멈춘다. 001은 0.47초다.
_GEMINI_MODEL = "gemini-embedding-001"

#: 로컬 폴백 모델 — BGE-M3의 한국어 검색 특화 파인튜닝.
_LOCAL_MODEL = "nlpai-lab/KURE-v1"

#: 벡터 차원. 기본 3072은 청크 100개 코퍼스에 과하고 저장·계산만 늘린다.
#: 768은 Google이 권장하는 축소 차원 중 하나다.
_DIMENSIONS = 768

#: 한 번에 보낼 청크 수. 코퍼스가 100개 안팎이라 대개 한 번에 끝나지만,
#: 요청이 너무 커지지 않게 나눈다.
_BATCH = 100

_ENV_SWITCH = "SEARCH_EMBEDDINGS"


def _normalize(vectors: np.ndarray) -> np.ndarray:
    """길이 1로 맞춘다 — 그래야 내적이 곧 코사인 유사도다.

    로컬 모델은 normalize_embeddings=True로 받지만 API 응답은 정규화돼 있지
    않다. 검색 쪽 계산이 내적 하나이므로 여기서 통일한다.
    """
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1.0, norms)


class GeminiEmbedder:
    """Gemini 임베딩 API를 감싼 임베더."""

    def __init__(self, model: str = _GEMINI_MODEL) -> None:
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client()
        self._model = model

    def encode(self, texts: list[str], *, query: bool = False) -> np.ndarray:
        """텍스트를 정규화된 벡터로.

        Args:
            texts: 인코딩할 문자열들.
            query: 질의면 True. 문서와 질의에 다른 task_type을 주는 것이
                비대칭 검색의 권장 사용법이다.
        """
        if not texts:
            return np.zeros((0, _DIMENSIONS), dtype=np.float32)
        config = self._types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY" if query else "RETRIEVAL_DOCUMENT",
            output_dimensionality=_DIMENSIONS,
        )
        rows: list[list[float]] = []
        for start in range(0, len(texts), _BATCH):
            response = self._client.models.embed_content(
                model=self._model, contents=texts[start : start + _BATCH], config=config
            )
            rows.extend(item.values for item in response.embeddings)
        return _normalize(np.asarray(rows, dtype=np.float32))


class LocalEmbedder:
    """sentence-transformers 모델을 감싼 임베더 — 외부 호출을 피할 때."""

    def __init__(self, model_name: str = _LOCAL_MODEL) -> None:
        # 지연 임포트 — torch가 없는 환경에서도 이 모듈 임포트는 성립해야 한다.
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def encode(self, texts: list[str], *, query: bool = False) -> np.ndarray:
        """텍스트를 정규화된 벡터로. 이 모델은 질의와 문서를 가르지 않는다."""
        del query
        return self._model.encode(texts, normalize_embeddings=True)


Embedder = GeminiEmbedder | LocalEmbedder

_lock = threading.Lock()
_embedder: Embedder | None = None
_load_failed = False


def default_embedder() -> Embedder | None:
    """공유 임베더를 돌려준다. 프로세스에 하나뿐이다.

    off거나 준비에 실패하면 None — 호출부는 BM25만 쓰는 것으로 자연히
    강등된다. 실패는 한 번만 기록하고 다시 시도하지 않는다(면접 중 반복
    재시도로 지연을 만들지 않기 위해).
    """
    global _embedder, _load_failed
    mode = os.environ.get(_ENV_SWITCH, "gemini")
    if mode == "off" or _load_failed:
        return None
    with _lock:
        if _embedder is None and not _load_failed:
            try:
                _embedder = LocalEmbedder() if mode == "local" else GeminiEmbedder()
                logger.info("의미 검색 임베더: %s", mode)
            except Exception:
                logger.exception("임베더 준비 실패 — BM25 단독으로 동작합니다")
                _load_failed = True
    return _embedder


def reset_for_tests() -> None:
    """모듈 전역 캐시를 비운다. 테스트가 모드를 바꿔 가며 볼 때 쓴다."""
    global _embedder, _load_failed
    with _lock:
        _embedder, _load_failed = None, False
