"""질문 게이트 툴 테스트.

선언 주입은 네트워크 없이 LlmRequest에 대해 검증한다. 시간 예산은 세션의
시작 시각을 과거로 밀어 만든다 — 툴이 벽시계를 읽으므로 시계를 재는 대신
면접이 언제 시작했는지를 바꾼다.

문턱은 `남은 것 중 최고 중요도 + 2 − 누적 꼬리질문 수`다. 아래 풀에서 1단계의
최고 중요도는 1(b)이라 아무것도 안 나갔을 때 문턱은 3에서 시작한다.
"""

import asyncio
import time
from typing import Any

import pytest
from conftest import ContextStub
from google.adk.models.llm_request import LlmRequest
from google.genai import types

from interviewer.tools import (
    STATE_ASKED,
    STATE_FREE_QUESTIONS,
    STATE_PROFILE,
    STATE_QUESTION_POOL,
    STATE_STAGE,
    STATE_STARTED_AT,
    AskQuestionTool,
    ask_question,
)

POOL_RAW = [
    {"id": "a", "stage": 0, "text": "자기소개 부탁드립니다.", "priority": 1,
     "tags": ["자기소개"]},
    {"id": "b", "stage": 1, "text": "맡으신 역할을 설명해 주세요.", "priority": 1,
     "tags": ["경험상세"]},
    {"id": "c", "stage": 1, "text": "가장 어려웠던 판단은 무엇이었나요?", "priority": 4,
     "tags": ["문제해결"]},
]

DRAFT = "그 18%는 어떤 기준으로 재셨나요?"

#: demo 프로필 단계 경계: 90 / 270 / 420 / 480초.
PROFILE = "demo"


def _state(started_s_ago: float = 0.0, **overrides: Any) -> dict[str, Any]:
    """시딩된 세션 state. started_s_ago만큼 면접이 이미 진행된 상태가 된다."""
    return {
        STATE_QUESTION_POOL: POOL_RAW,
        STATE_STARTED_AT: time.time() - started_s_ago,
        STATE_PROFILE: PROFILE,
        **overrides,
    }


def _new_topic(context: ContextStub, tag: str = "경험상세") -> dict:
    """draft_question을 비우면 이 주제는 끝났다는 뜻이다."""
    return ask_question(tool_context=context, tag=tag, priority=1)


def _follow_up(context: ContextStub, priority: int, tag: str = "경험상세") -> dict:
    return ask_question(
        tool_context=context, tag=tag, priority=priority, draft_question=DRAFT
    )


def _approved(result: dict) -> bool:
    """허가면 초안이 그대로 ask에 실려 온다. 반려면 준비된 다른 문장이 온다."""
    return result.get("ask") == DRAFT


def _inject(state: dict[str, Any] | None = None) -> LlmRequest:
    request = LlmRequest()
    asyncio.run(
        AskQuestionTool().process_llm_request(
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


def test_draft_question은_필수가_아니다() -> None:
    """비어 있는 것이 "이 주제는 끝났다"는 신호다 — 필수로 두면 모델이 부르기
    전에 질문을 지어내고, 지어낸 것을 말해버려 툴이 준 질문과 겹친다."""
    schema = _declaration(_inject(_state())).parameters_json_schema
    assert set(schema["required"]) == {"tag", "priority"}


def test_중요도_척도가_모델에게_실린다() -> None:
    """모델이 자기 질문에 값을 매길 때 읽는 곳은 선언뿐이다. ADK는 docstring
    전문을 함수 description에 싣고 파라미터 스키마에는 설명을 넣지 않는다."""
    described = _declaration(_inject(_state())).description
    assert "핵심 검증" in described and "곁가지" in described


def test_시딩_안_된_세션은_크게_실패한다() -> None:
    """폴백으로 가리면 엉뚱한 데이터로 면접이 그럴듯하게 돌아버린다."""
    with pytest.raises(ValueError, match="시딩"):
        _inject()


def test_선언과_등록은_한_번만_된다() -> None:
    """super() 호출 뒤의 패치가 이중 등록을 만들면 안 된다."""
    request = _inject(_state())
    _declaration(request)  # 툴 하나, 선언 하나가 아니면 여기서 언패킹이 깨진다
    assert list(request.tools_dict) == ["ask_question"]


# ── 새 주제 (draft_question 비움) ────────────────────────────────────────


def test_준비된_질문이_ask로_나간다() -> None:
    context = ContextStub(_state(stage=1))
    assert _new_topic(context)["ask"] == "맡으신 역할을 설명해 주세요."
    assert context.state[STATE_ASKED] == ["b"]


def test_tag로_해당_주제의_질문을_고른다() -> None:
    result = _new_topic(ContextStub(_state(stage=1)), tag="문제해결")
    assert result["ask"] == "가장 어려웠던 판단은 무엇이었나요?"


def test_배달하면_꼬리질문_카운터가_풀린다() -> None:
    context = ContextStub(_state(stage=1, **{STATE_FREE_QUESTIONS: 2}))
    _new_topic(context)
    assert context.state[STATE_FREE_QUESTIONS] == 0


def test_응답은_문장과_다음_행동뿐이다() -> None:
    """단계 이름·태그 목록·횟수는 모델의 다음 행동을 못 바꾼다 — 입으로 새는
    통로일 뿐이다. 태그는 이미 선언 enum에 있다."""
    result = _new_topic(ContextStub(_state(stage=1)))
    assert set(result) == {"ask", "instruction"}
    assert "물어보세요" in result["instruction"]
    assert "경험상세" not in result["instruction"]
    assert "단계" not in result["instruction"]


# ── 꼬리질문 게이트 ──────────────────────────────────────────────────────


def test_허가는_초안을_그대로_돌려준다() -> None:
    """어느 경로든 응답은 "이 문장을 물어보라" 하나다. 모델이 툴 뒤에 말하는
    지금 순서에서는 되돌려줘도 두 번 말할 것이 없다."""
    result = _follow_up(ContextStub(_state(stage=1)), priority=3)
    assert result["ask"] == DRAFT
    assert set(result) == {"ask", "instruction"}


def test_문턱을_넘으면_카운터가_오른다() -> None:
    context = ContextStub(_state(stage=1))
    _follow_up(context, priority=3)  # 문턱 3
    assert context.state[STATE_FREE_QUESTIONS] == 1


def test_반려는_준비된_질문을_같은_모양으로_준다() -> None:
    """초안 대신 다른 문장이 왔으면 그걸 물으라는 뜻이다 — 전환 멘트는 싣지
    않는다. 왕복이 한 번 줄어 침묵이 절반이 된다."""
    context = ContextStub(_state(stage=1))
    result = _follow_up(context, priority=4)  # 문턱 3
    assert result["ask"] == "맡으신 역할을 설명해 주세요."
    assert set(result) == {"ask", "instruction"}
    assert context.state[STATE_FREE_QUESTIONS] == 0


def test_한_번_더_물을수록_문턱이_엄해진다() -> None:
    context = ContextStub(_state(stage=1))
    assert _approved(_follow_up(context, priority=3))  # 문턱 3
    assert not _approved(_follow_up(context, priority=3))  # 문턱 2 — 반려


def test_중요한_꼬리질문은_한_번_더_버틴다() -> None:
    context = ContextStub(_state(stage=1, **{STATE_FREE_QUESTIONS: 2}))
    assert _approved(_follow_up(context, priority=1))  # 문턱 1


def test_남은_질문이_곁가지뿐이면_문턱이_낮아진다() -> None:
    """중요한 질문이 이미 나갔으면 파던 자리를 더 파는 편이 낫다.
    남은 것이 중요도 4뿐이면 문턱은 6이다."""
    context = ContextStub(_state(stage=1, **{STATE_ASKED: ["b"]}))
    assert _approved(_follow_up(context, priority=5))


def test_꼬리질문은_세_개를_못_넘는다() -> None:
    """문턱이 아무리 느슨해도 준비된 질문 사이에 자작 질문이 길게 끼면 안 된다."""
    context = ContextStub(
        _state(stage=1, **{STATE_ASKED: ["b"], STATE_FREE_QUESTIONS: 3})
    )
    assert not _approved(_follow_up(context, priority=1))


def test_비교_대상이_없으면_허가한다() -> None:
    """풀이 비었으면 밀어낼 곳이 없다."""
    context = ContextStub(_state(stage=1, **{STATE_ASKED: ["a", "b", "c"]}))
    assert _approved(_follow_up(context, priority=5))


def test_비교_대상은_태그를_무시한다() -> None:
    """기회비용은 모델이 어느 주제를 파든 같다 — 이 단계에서 못 하고 있는 것 중
    가장 중요한 질문이다. 태그로 뽑으면 모델이 문턱을 스스로 정하게 된다."""
    context = ContextStub(_state(stage=1))
    # b(중요도 1)가 남아 있으므로 문턱은 3. c(중요도 4)와 비교했다면 6이 된다.
    assert not _approved(_follow_up(context, priority=4, tag="문제해결"))


# ── 시간 예산 ────────────────────────────────────────────────────────────


def test_시간이_지나면_단계를_건너뛴다() -> None:
    """1단계에 질문이 남아 있어도 예산을 넘겼으면 2단계로 간다."""
    context = ContextStub(_state(100.0, stage=0))
    assert _new_topic(context)["ask"] == "맡으신 역할을 설명해 주세요."
    assert context.state[STATE_STAGE] == 1


def test_예산보다_앞서_가는_것은_막지_않는다() -> None:
    """질문을 빨리 소진해 앞서 간 단계를 시간이 되돌리지는 않는다."""
    context = ContextStub(_state(0.0, stage=1))
    _new_topic(context)
    assert context.state[STATE_STAGE] == 1


def test_시간이_다_지나도_면접을_끝내지_않는다() -> None:
    """끝내는 것은 지원자의 종료 버튼이다. 시간 예산은 단계를 옮기는 데만 쓴다 —
    하드캡이 지나도 질문은 계속 나간다."""
    result = _follow_up(ContextStub(_state(600.0)), priority=1)
    assert "done" not in result
    assert "ask" in result


def test_질문을_다_쓰면_꼬리질문으로_이어가라고_한다() -> None:
    """준비된 것이 바닥나도 면접은 안 끝난다 — 모델이 제 문장으로 이어간다."""
    context = ContextStub(_state(stage=1, **{STATE_ASKED: ["a", "b", "c"]}))
    result = _new_topic(context)
    assert "done" not in result and "ask" not in result
    assert "꼬리질문" in result["instruction"]


def test_지시는_모델에게_시간을_알리지_않는다() -> None:
    """시계는 서버만 본다 — 남은 시간을 알려 봐야 늘어질 때는 툴을 안 부르고,
    꼬리질문의 필요는 시간이 아니라 답변 내용이 정한다."""
    result = _new_topic(ContextStub(_state(60.0, stage=1)))
    assert "남았습니다" not in result["instruction"] and "분" not in result["instruction"]


def test_시작_시각_없는_세션은_크게_실패한다() -> None:
    """시간 예산 없이 도는 면접은 단계가 영영 안 넘어간다 — 조용히 두지 않는다."""
    with pytest.raises(ValueError, match="시딩"):
        _new_topic(ContextStub({STATE_QUESTION_POOL: POOL_RAW}))
