"""태그 enum 툴 선언 테스트.

선언 주입은 네트워크 없이 LlmRequest에 대해 검증한다.
"""

import asyncio
from typing import Any

import pytest
from conftest import ContextStub
from google.adk.models.llm_request import LlmRequest
from google.genai import types

from interviewer.tools import STATE_QUESTION_POOL, NextQuestionTool, get_next_question

POOL_RAW = [
    {"id": "a", "stage": 0, "text": "자기소개 부탁드립니다.", "priority": 1,
     "tags": ["자기소개"]},
    {"id": "b", "stage": 1, "text": "맡으신 역할을 설명해 주세요.", "priority": 1,
     "tags": ["경험상세"]},
    {"id": "c", "stage": 1, "text": "가장 어려웠던 판단은 무엇이었나요?", "priority": 2,
     "tags": ["문제해결"]},
]


def _inject(state: dict[str, Any] | None = None) -> LlmRequest:
    request = LlmRequest()
    asyncio.run(
        NextQuestionTool().process_llm_request(
            tool_context=ContextStub(state), llm_request=request
        )
    )
    return request


def _declaration(request: LlmRequest) -> types.FunctionDeclaration:
    (tool,) = request.config.tools
    (declaration,) = tool.function_declarations
    return declaration


# ── 선언 주입 ────────────────────────────────────────────────────────────


def test_세션_풀의_태그가_enum으로_실린다() -> None:
    request = _inject({STATE_QUESTION_POOL: POOL_RAW})
    prop = _declaration(request).parameters_json_schema["properties"]["tag"]
    assert prop["enum"] == ["자기소개", "경험상세", "문제해결"]
    assert prop["type"] == "string"
    assert "anyOf" not in prop


def test_tag는_필수가_아니다() -> None:
    """태그가 마땅치 않으면 모델이 생략할 수 있어야 한다."""
    schema = _declaration(_inject({STATE_QUESTION_POOL: POOL_RAW})).parameters_json_schema
    assert "tag" not in schema.get("required", [])


def test_시딩_안_된_세션은_크게_실패한다() -> None:
    """폴백으로 가리면 엉뚱한 데이터로 면접이 그럴듯하게 돌아버린다."""
    with pytest.raises(ValueError, match="시딩"):
        _inject()


def test_선언과_등록은_한_번만_된다() -> None:
    """super() 호출 뒤의 패치가 이중 등록을 만들면 안 된다."""
    request = _inject({STATE_QUESTION_POOL: POOL_RAW})
    _declaration(request)  # 툴 하나, 선언 하나가 아니면 여기서 언패킹이 깨진다
    assert list(request.tools_dict) == ["get_next_question"]


# ── 툴 실행 ──────────────────────────────────────────────────────────────


def test_tag로_해당_주제의_질문을_고른다() -> None:
    context = ContextStub({STATE_QUESTION_POOL: POOL_RAW, "stage": 1})
    result = get_next_question(tool_context=context, tag="문제해결")
    assert result["question"] == "가장 어려웠던 판단은 무엇이었나요?"
    assert context.state["asked"] == ["c"]


def test_note에_단계_태그가_실린다() -> None:
    """모델이 다음 호출에서 고를 태그를 note로 안내받는다."""
    context = ContextStub({STATE_QUESTION_POOL: POOL_RAW, "stage": 1})
    result = get_next_question(tool_context=context)
    assert "경험상세" in result["note"] and "문제해결" in result["note"]
