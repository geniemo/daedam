"""뼈대질문 배달 툴 테스트.

선언 주입은 네트워크 없이 LlmRequest에 대해 검증한다. 시간 예산은 세션의
시작 시각을 과거로 밀어 만든다 — 툴이 벽시계를 읽으므로 시계를 재는 대신
면접이 언제 시작했는지를 바꾼다.
"""

import asyncio
import time
from typing import Any

import pytest
from conftest import ContextStub
from google.adk.models.llm_request import LlmRequest
from google.genai import types

from interviewer.tools import (
    STATE_PROFILE,
    STATE_QUESTION_POOL,
    STATE_STARTED_AT,
    NextQuestionTool,
    get_next_question,
)

POOL_RAW = [
    {"id": "a", "stage": 0, "text": "자기소개 부탁드립니다.", "priority": 1,
     "tags": ["자기소개"]},
    {"id": "b", "stage": 1, "text": "맡으신 역할을 설명해 주세요.", "priority": 1,
     "tags": ["경험상세"]},
    {"id": "c", "stage": 1, "text": "가장 어려웠던 판단은 무엇이었나요?", "priority": 2,
     "tags": ["문제해결"]},
]

#: demo 프로필 단계 경계: 90 / 270 / 420 / 480초, 하드캡 540초.
PROFILE = "demo"


def _state(started_s_ago: float = 0.0, **overrides: Any) -> dict[str, Any]:
    """시딩된 세션 state. started_s_ago만큼 면접이 이미 진행된 상태가 된다."""
    return {
        STATE_QUESTION_POOL: POOL_RAW,
        STATE_STARTED_AT: time.time() - started_s_ago,
        STATE_PROFILE: PROFILE,
        **overrides,
    }


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
    prop = _declaration(_inject(_state())).parameters_json_schema["properties"]["tag"]
    assert prop["enum"] == ["자기소개", "경험상세", "문제해결"]
    assert prop["type"] == "string"
    assert "anyOf" not in prop


def test_tag는_필수가_아니다() -> None:
    """태그가 마땅치 않으면 모델이 생략할 수 있어야 한다."""
    schema = _declaration(_inject(_state())).parameters_json_schema
    assert "tag" not in schema.get("required", [])


def test_시딩_안_된_세션은_크게_실패한다() -> None:
    """폴백으로 가리면 엉뚱한 데이터로 면접이 그럴듯하게 돌아버린다."""
    with pytest.raises(ValueError, match="시딩"):
        _inject()


def test_선언과_등록은_한_번만_된다() -> None:
    """super() 호출 뒤의 패치가 이중 등록을 만들면 안 된다."""
    request = _inject(_state())
    _declaration(request)  # 툴 하나, 선언 하나가 아니면 여기서 언패킹이 깨진다
    assert list(request.tools_dict) == ["get_next_question"]


# ── 툴 실행 ──────────────────────────────────────────────────────────────


def test_tag로_해당_주제의_질문을_고른다() -> None:
    context = ContextStub(_state(stage=1))
    result = get_next_question(tool_context=context, tag="문제해결")
    assert result["question"] == "가장 어려웠던 판단은 무엇이었나요?"
    assert context.state["asked"] == ["c"]


def test_note에_단계_태그가_실린다() -> None:
    """모델이 다음 호출에서 고를 태그를 note로 안내받는다."""
    result = get_next_question(tool_context=ContextStub(_state(stage=1)))
    assert "경험상세" in result["note"] and "문제해결" in result["note"]


def test_시작_시각_없는_세션은_크게_실패한다() -> None:
    """시간 예산 없이 도는 면접은 단계가 영영 안 넘어간다 — 조용히 두지 않는다."""
    with pytest.raises(ValueError, match="시딩"):
        get_next_question(tool_context=ContextStub({STATE_QUESTION_POOL: POOL_RAW}))


# ── 시간 예산 ────────────────────────────────────────────────────────────


def test_시간이_지나면_단계를_건너뛴다() -> None:
    """1단계에 질문이 남아 있어도 예산을 넘겼으면 2단계로 간다."""
    context = ContextStub(_state(100.0, stage=0))
    result = get_next_question(tool_context=context)
    assert result["stage"] == "직무역량"
    assert context.state["stage"] == 1


def test_예산보다_앞서_가는_것은_막지_않는다() -> None:
    """질문을 빨리 소진해 앞서 간 단계를 시간이 되돌리지는 않는다."""
    context = ContextStub(_state(0.0, stage=1))
    result = get_next_question(tool_context=context)
    assert result["stage"] == "직무역량"


def test_하드캡을_넘으면_마무리를_지시한다() -> None:
    """종료 판정은 남은 질문 수가 아니라 시간이 한다."""
    result = get_next_question(tool_context=ContextStub(_state(600.0)))
    assert result["done"] is True
    assert "마무리" in result["note"]


def test_note는_모델에게_시간을_알리지_않는다() -> None:
    """시계는 서버만 본다 — 남은 시간을 알려 봐야 늘어질 때는 툴을 안 부르고,
    꼬리질문의 필요는 시간이 아니라 답변 내용이 정한다."""
    result = get_next_question(tool_context=ContextStub(_state(60.0)))
    assert "남았습니다" not in result["note"]
    assert "분" not in result["note"]
