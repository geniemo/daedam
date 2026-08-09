"""면접관 에이전트.

instruction은 아직 정적 스모크 프롬프트다 — 동적 instruction(회사·직무·지원서
목차)은 다음 단계에서 붙는다. 뼈대질문 배달은 `NextQuestionTool`이, 회사 지식
검색은 `search_knowledge`가 맡는다.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent

from .tools import NextQuestionTool, search_knowledge

#: 네이티브 오디오 모델. 함수 호출이 순차 전용이라 툴이 도는 동안 발화가 멈춘다.
#: 문제가 있으면 gemini-2.5-flash-native-audio-preview-12-2025로 폴백한다.
MODEL = "gemini-3.1-flash-live-preview"

root_agent = LlmAgent(
    name="interviewer",
    model=MODEL,
    description="한국어 음성 모의면접관",
    instruction="""\
당신은 신입 채용 면접관입니다. 지원자와 한국어 음성으로 면접을 진행합니다.

- 존댓말로, 담담하고 정중하게. 한 번에 질문은 하나만.
- 문장을 짧게 끊으세요. 음성이라 긴 문장은 알아듣기 어렵습니다.
- 답변을 평가하는 말("좋은 답변이네요")은 하지 마세요.

툴을 호출하기 직전에는 "네, 말씀 잘 들었습니다" 같은 짧은 중립 반응을 먼저
말하세요. 그 말이 나가는 동안 툴 결과가 준비됩니다.

첫 턴에는 짧게 인사하고 바로 첫 질문으로 시작하세요.
""",
    # search_knowledge는 선언이 정적(enum이 Literal에서 나옴)이라 서브클래스
    # 없이 콜러블 그대로 넘긴다. ADK가 FunctionTool로 감싼다
    # (google/adk/agents/llm_agent.py의 _convert_tool_union_to_tools).
    tools=[NextQuestionTool(), search_knowledge],
)
