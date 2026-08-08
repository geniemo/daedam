"""스모크용 최소 에이전트.

`adk web`에서 세 가지를 확인하기 위한 것이다.
  1. `gemini-3.1-flash-live-preview`가 ADK를 통해 연결되는가
  2. 한국어 음성 품질이 쓸 만한가
  3. 전환 지점마다 툴이 실제로 호출되는가

동적 프롬프트·태그 enum·검색 툴은 아직 붙이지 않는다.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.tools import ToolContext

from daedam.interview.question_pool import QuestionPool
from daedam.interview.stages import STAGE_NAMES

#: 네이티브 오디오 모델. 함수 호출이 순차 전용이라 툴이 도는 동안 발화가 멈춘다.
#: 문제가 있으면 gemini-2.5-flash-native-audio-preview-12-2025로 폴백한다.
MODEL = "gemini-3.1-flash-live-preview"

#: 스모크용 최소 질문 풀. 실제 풀은 리서치 리포트와 지원서로부터 오프라인 생성된다.
_POOL = QuestionPool.from_dicts(
    [
        {"id": "q0", "stage": 0, "text": "먼저 간단히 자기소개 부탁드립니다.",
         "priority": 1, "tags": ["자기소개"]},
        {"id": "q1", "stage": 0, "text": "저희 회사에 지원하신 이유가 무엇인가요?",
         "priority": 2, "tags": ["지원동기"]},
        {"id": "q2", "stage": 1, "text": "지원서에 적으신 프로젝트에서 맡으신 역할을 설명해 주세요.",
         "priority": 1, "tags": ["경험상세"]},
        {"id": "q3", "stage": 1, "text": "그 과정에서 가장 어려웠던 판단은 무엇이었나요?",
         "priority": 2, "tags": ["문제해결"]},
        {"id": "q4", "stage": 2, "text": "동료와 의견이 부딪혔을 때 어떻게 풀어가시나요?",
         "priority": 1, "tags": ["협업"]},
        {"id": "q5", "stage": 3, "text": "마지막으로 궁금한 점이 있으신가요?",
         "priority": 1, "tags": ["역질문"]},
    ]
)


def get_next_question(tool_context: ToolContext) -> dict:
    """다음 면접 질문을 가져옵니다. 새 주제로 넘어갈 때마다 호출하세요.

    Returns:
        question(질문 문장), stage(현재 단계 이름), note(진행 안내)를 담은 dict.
        남은 질문이 없으면 done이 True.
    """
    state = tool_context.state
    asked: list[str] = list(state.get("asked", []))
    stage: int = int(state.get("stage", 0))

    # 현재 단계가 소진되면 다음 단계로 넘긴다. 단계 전환의 최종 판단은 서버에 있다.
    question = _POOL.next(stage=stage, exclude=asked)
    while question is None and stage < len(STAGE_NAMES) - 1:
        stage += 1
        question = _POOL.next(stage=stage, exclude=asked)

    if question is None:
        state["stage"] = stage
        return {"done": True, "note": "질문이 모두 끝났습니다. 면접을 마무리해 주세요."}

    asked.append(question.id)
    state["asked"] = asked
    state["stage"] = stage
    return {
        "question": question.text,
        "stage": STAGE_NAMES[stage],
        "note": f"지금은 {STAGE_NAMES[stage]} 단계입니다. 이 질문을 그대로 읽지 말고 자연스럽게 물어보세요.",
    }


root_agent = LlmAgent(
    name="interviewer",
    model=MODEL,
    description="한국어 음성 모의면접관",
    instruction="""\
당신은 신입 채용 면접관입니다. 지원자와 한국어 음성으로 면접을 진행합니다.

- 존댓말로, 담담하고 정중하게. 한 번에 질문은 하나만.
- 문장을 짧게 끊으세요. 음성이라 긴 문장은 알아듣기 어렵습니다.

**새 주제로 넘어갈 때마다 `get_next_question`을 호출하세요.**
방금 들은 답변을 파고드는 꼬리질문은 툴 없이 바로 하시면 됩니다.

툴을 호출하기 직전에 "네, 말씀 잘 들었습니다" 같은 짧은 중립 반응을 먼저
말하세요. 그 말이 나가는 동안 다음 질문이 준비됩니다.
답변을 평가하는 말("좋은 답변이네요")은 하지 마세요.

첫 턴에는 짧게 인사하고 바로 `get_next_question`으로 첫 질문을 받으세요.
""",
    tools=[get_next_question],
)
