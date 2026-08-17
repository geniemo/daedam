"""면접관 에이전트.

instruction은 세션 state(회사·직무·지원자·지원서 목차)로 조립된다 —
`build_instruction` 참고. 질문 게이트는 `AskQuestionTool`이, 회사 지식 검색은
`search_knowledge`가, 면접을 끝내겠다는 통보는 `finish_interview`가 맡는다.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent

from .instruction import build_instruction
from .tools import AskQuestionTool, finish_interview, search_knowledge

#: 네이티브 오디오 모델. 함수 호출이 순차 전용이라 툴이 도는 동안 발화가 멈춘다.
#: 문제가 있으면 gemini-2.5-flash-native-audio-preview-12-2025로 폴백한다.
MODEL = "gemini-3.1-flash-live-preview"

root_agent = LlmAgent(
    name="interviewer",
    model=MODEL,
    description="한국어 음성 모의면접관",
    instruction=build_instruction,
    # AskQuestionTool만 서브클래스인 이유는 tag enum을 세션 풀에서 주입하기
    # 위해서다. 나머지 둘은 선언이 정적이라 콜러블 그대로 넘기면 ADK가
    # FunctionTool로 감싼다
    # (google/adk/agents/llm_agent.py의 _convert_tool_union_to_tools).
    tools=[AskQuestionTool(), search_knowledge, finish_interview],
)
