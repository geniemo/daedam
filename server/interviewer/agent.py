"""면접관 에이전트.

instruction은 세션 state(회사·직무·지원자·지원서 목차)로 조립된다 —
`build_instruction` 참고. 질문 게이트는 `AskQuestionTool`이, 회사 지식 검색은
`search_knowledge`가 맡는다. 면접을 끝내는 툴은 없다 — 끝내는 것은 지원자의
종료 버튼이다.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent

from .instruction import build_instruction
from .tools import AskQuestionTool, search_knowledge

#: 네이티브 오디오 모델. 함수 호출이 순차 전용이라 툴이 도는 동안 발화가 멈춘다.
#: 문제가 있으면 gemini-2.5-flash-native-audio-preview-12-2025로 폴백한다.
MODEL = "gemini-3.1-flash-live-preview"

#: 면접관 목소리 — 프리빌트 8종(Puck·Charon·Kore·Fenrir·Aoede·Leda·Orus·Zephyr,
#: ~/refs/adk-docs/docs/live/dev-guide/part5.md:633) 중 하나로 고정한다. 세션마다
#: 목소리가 바뀌지 않게. 브리지가 RunConfig의 speech_config로 싣고 ADK가 Live
#: 연결로 넘긴다(adk/flows/llm_flows/basic.py:111).
#:
#: 같은 이름으로 TTS 클립을 만들어 추임새로 쓰려 했으나 뺐다 — 이름이 같아도
#: TTS와 Live는 다른 음성 엔진이라 같은 목소리로 들리지 않았고(실측: 기계음),
#: 모델은 클립을 못 들으니 자기도 추임새를 해서 "알겠습니다. 알겠습니다"가 됐다.
VOICE = "Aoede"

root_agent = LlmAgent(
    name="interviewer",
    model=MODEL,
    description="한국어 음성 모의면접관",
    instruction=build_instruction,
    # AskQuestionTool만 서브클래스인 이유는 tag enum을 세션 풀에서 주입하기
    # 위해서다. search_knowledge는 선언이 정적이라 콜러블 그대로 넘기면 ADK가
    # FunctionTool로 감싼다
    # (google/adk/agents/llm_agent.py의 _convert_tool_union_to_tools).
    tools=[AskQuestionTool(), search_knowledge],
)
