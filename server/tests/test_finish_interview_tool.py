"""면접 종료 툴 테스트.

이 툴이 있는 이유가 곧 검증 대상이다 — 면접관이 마무리 인사를 하고 대화를
끝내도, 그 판단이 state에 남지 않으면 서버는 하드캡까지 면접이 끝난 줄 모른다.
"""

import time
from typing import Any

import pytest
from conftest import ContextStub

from interviewer.tools import (
    STATE_ASKED,
    STATE_CLOSING,
    STATE_PROFILE,
    STATE_QUESTION_POOL,
    STATE_STAGE,
    STATE_STARTED_AT,
    finish_interview,
)

POOL_RAW = [
    {"id": "a", "stage": 0, "text": "자기소개 부탁드립니다.", "priority": 1, "tags": []},
]


def _state(stage: int, **overrides: Any) -> dict[str, Any]:
    return {
        STATE_QUESTION_POOL: POOL_RAW,
        STATE_STARTED_AT: time.time() - 60.0,
        STATE_PROFILE: "demo",
        STATE_STAGE: stage,
        **overrides,
    }


def test_마무리_단계에서는_종료_표시를_세운다() -> None:
    """브리지가 이 표시를 읽고 ended를 보낸 뒤 소켓을 닫는다."""
    context = ContextStub(_state(3, **{STATE_ASKED: ["a", "b"]}))
    result = finish_interview(tool_context=context)
    assert result["done"] is True
    assert context.state[STATE_CLOSING] is True


def test_마무리_단계가_아니면_반려한다() -> None:
    """모델이 분위기로 끝내버리면 준비된 단계가 통째로 날아간다."""
    context = ContextStub(_state(1))
    result = finish_interview(tool_context=context)
    assert result["done"] is False
    assert STATE_CLOSING not in context.state
    # 반려로 끝내지 않고 이어갈 방법을 알려준다 — 모델이 다시 시도할 곳이 있어야 한다.
    assert "get_next_question" in result["note"]


def test_하드캡을_넘었으면_단계와_무관하게_받는다() -> None:
    """이 시점엔 브리지가 이미 마무리를 지시한 뒤다. 여기서 반려하면 서버가
    한 입으로 "끝내라"와 "계속하라"를 같이 말하게 된다."""
    context = ContextStub(_state(0, **{STATE_STARTED_AT: time.time() - 600.0}))
    result = finish_interview(tool_context=context)
    assert result["done"] is True
    assert context.state[STATE_CLOSING] is True


def test_시작_시각_없는_세션은_크게_실패한다() -> None:
    """뼈대질문 툴과 같은 원칙 — 시딩 실패를 조용히 넘기지 않는다."""
    with pytest.raises(ValueError, match="시딩"):
        finish_interview(tool_context=ContextStub({STATE_STAGE: 3}))
