"""반복된 보완점 — 회차를 가로질러 같은 말을 한 코칭 문장 찾기.

코칭은 매번 새 문장을 쓴다. 로컬 24판·78문장에서 글자 그대로 겹친 문장은
**0건**이었다 — 문자열로 세면 홈의 기록 띠에 아무것도 뜨지 않는다. 그래서 의미
검색과 같은 임베더(knowledge/embedding.py)로 묶는다. 코사인 0.85에서
"자기소개에 역량 포함"(11판) · "지원 동기 구체화"(10판) · "카메라 렌즈 응시"(8판)가
따로따로 잡혔고, 0.8부터는 서로 다른 조언이 한 묶음으로 뭉쳤다(실측 2026-09-10).

판 집합이 같은 동안은 다시 계산하지 않는다 — 홈은 자주 열리고 문장은 판이 늘
때만 는다. 임베더가 없거나 실패하면 None이다. 기록 띠가 홈을 멈출 권리는 없다.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from daedam.knowledge.embedding import Embedder, default_embedder

from .store import InterviewRecord

logger = logging.getLogger(__name__)

#: 같은 보완점으로 볼 코사인 유사도. 위 실측 — 이보다 낮추면 다른 조언이 섞인다.
SAME_POINT = 0.85


def recurring_improvement(
    records: list[InterviewRecord], embedder: Embedder | None = None
) -> dict[str, Any] | None:
    """리포트 2건 이상에서 반복된 보완점 — 가장 최근 문장과 판 수.

    같은 판 안에서 두 번 나온 것은 한 번으로 센다. "반복"은 회차를 가로지르는
    것이다.

    Args:
        records: 시간순 면접 기록. 문장은 각 기록의 improvements에서 온다.
        embedder: 테스트가 주입한다. 없으면 공유 임베더(SEARCH_EMBEDDINGS).

    Returns:
        {"text", "count"} 또는 None — 반복이 없거나 임베더를 쓸 수 없을 때.
    """
    sentences = tuple(
        (record.session_id, text)
        for record in records
        for text in dict.fromkeys(record.improvements)
    )
    # 판이 둘은 돼야 반복이 있다 — 첫 면접 뒤에 임베딩을 부르지 않는다.
    if len({session for session, _ in sentences}) < 2:
        return None
    embedder = embedder or default_embedder()
    if embedder is None:
        return None
    try:
        return _grouped(sentences, embedder)
    except Exception:
        logger.warning("보완점 임베딩 실패 — 반복된 보완점 없이 갑니다", exc_info=True)
        return None


@lru_cache(maxsize=256)
def _grouped(
    sentences: tuple[tuple[str, str], ...], embedder: Embedder
) -> dict[str, Any] | None:
    """문장을 씨앗 기준으로 탐욕스럽게 묶고, 가장 많은 판에 걸친 묶음을 고른다.

    씨앗은 시간순 첫 문장이다. 묶음의 대표 문장은 가장 최근 것 — 지원자가
    마지막으로 들은 표현이 지금 고칠 것에 가장 가깝다.
    """
    vectors = embedder.encode([text for _, text in sentences])
    seeds: list[int] = []
    groups: list[list[int]] = []
    for i in range(len(sentences)):
        for group, seed in zip(groups, seeds):
            # 임베더가 길이를 1로 맞추므로 내적이 곧 코사인이다.
            if float(vectors[i] @ vectors[seed]) >= SAME_POINT:
                group.append(i)
                break
        else:
            seeds.append(i)
            groups.append([i])

    def sessions(group: list[int]) -> int:
        return len({sentences[j][0] for j in group})

    best = max(groups, key=lambda group: (sessions(group), group[-1]))
    count = sessions(best)
    if count < 2:
        return None
    return {"text": sentences[best[-1]][1], "count": count}
