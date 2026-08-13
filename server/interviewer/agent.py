"""면접관 에이전트.

instruction은 세션 state(회사·직무·지원자·지원서 목차)로 조립된다 —
`build_instruction` 참고. 뼈대질문 배달은 `NextQuestionTool`이, 회사 지식
검색은 `search_knowledge`가, 면접을 끝내겠다는 통보는 `finish_interview`가
맡는다.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent

from .instruction import build_instruction
from .tools import NextQuestionTool, finish_interview, search_knowledge

#: 네이티브 오디오 모델. 함수 호출이 순차 전용이라 툴이 도는 동안 발화가 멈춘다.
#: 문제가 있으면 gemini-2.5-flash-native-audio-preview-12-2025로 폴백한다.
MODEL = "gemini-3.1-flash-live-preview"

root_agent = LlmAgent(
    name="interviewer",
    model=MODEL,
    description="한국어 음성 모의면접관",
    instruction=build_instruction,
    # search_knowledge·finish_interview는 선언이 정적이라(전자는 enum이
    # Literal에서 나오고 후자는 파라미터가 없다) 서브클래스 없이 콜러블 그대로
    # 넘긴다. ADK가 FunctionTool로 감싼다
    # (google/adk/agents/llm_agent.py의 _convert_tool_union_to_tools).
    tools=[NextQuestionTool(), search_knowledge, finish_interview],
)
