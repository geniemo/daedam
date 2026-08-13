"""면접관 instruction 조립.

세션 state의 회사·직무·지원자·지원서로 시스템 프롬프트를 만든다. state가
비어 있으면(adk web 직접 실행) 일반 면접관 프롬프트로 자연히 줄어든다.

InstructionProvider 확인 경로 (설치된 ADK 2.6.3 소스):
  google/adk/utils/instructions_utils.py
    — Callable[[ReadonlyContext], str | Awaitable[str]]
  google/adk/agents/llm_agent.py  `canonical_instruction`
    — 콜러블이면 세션마다 호출해 결과를 그대로 쓴다({var} state 주입 우회)
"""

from __future__ import annotations

from google.adk.agents.readonly_context import ReadonlyContext

from daedam.knowledge.chunk import application_outline

from .tools import STATE_APPLICATION, STATE_RESEARCH_REPORT

#: 세션 생성 시 서버가 심는 면접 컨텍스트 state 키.
STATE_COMPANY = "company"
STATE_ROLE = "role"
STATE_CANDIDATE = "candidate"

#: 말투와 진행 규칙. 회사가 누구든, 면접 어느 지점이든 변하지 않는 부분만 둔다.
#: "첫 턴에는" 같은 조건부 지시는 여기 두지 않는다 — 이 글은 매 턴 다시 읽히므로
#: 모델이 턴마다 조건을 판정해야 한다. 개시 지시는 개시 신호가 나르고
#: (daedam/server/live_bridge.py), 툴 사용법은 툴 설명이 소유한다.
#:
#: 짧은 반응을 먼저 말하게 하는 것은 툴이 도는 동안의 침묵을 메우기 위해서다
#: (Live API 함수 호출은 순차 전용이라 그 사이 소리가 끊긴다). 모델이 방금
#: 말을 마친 뒤에는 필요 없으므로 답변을 들은 경우로 한정한다.
_STYLE = """\
- 존댓말로, 담담하고 정중하게. 한 번에 질문은 하나만.
- 문장을 짧게 끊으세요. 음성이라 긴 문장은 알아듣기 어렵습니다.
- 답변을 평가하는 말("좋은 답변이네요")은 하지 마세요.

지원자의 답변을 들은 뒤 다음 질문으로 넘어갈 때는 상황에 맞는 짧은 반응을 먼저
말하세요."""


def build_instruction(context: ReadonlyContext) -> str:
    """세션 state로 면접관 instruction을 조립한다.

    "모의면접"이라는 사실은 어디에도 넣지 않는다 — 에이전트는 자신을 실제
    면접관으로 알아야 캐릭터가 유지된다. 리포트와 지원서는 목차만 싣는다 —
    본문은 검색으로 가져오게 해서 프롬프트를 짧게 유지한다(보이스 에이전트는
    컨텍스트 유지력이 약점이다). 목차는 무엇이 준비돼 있는지 알리는 동시에,
    모델의 검색 질의 어휘를 코퍼스 어휘 쪽으로 끌어당기는 앵커다.
    """
    state = context.state
    company = state.get(STATE_COMPANY)
    role = state.get(STATE_ROLE)
    candidate = state.get(STATE_CANDIDATE)
    report = state.get(STATE_RESEARCH_REPORT)
    parts = state.get(STATE_APPLICATION)

    opening = (
        f"당신은 {company}의 신입 채용 면접관입니다."
        if company
        else "당신은 신입 채용 면접관입니다."
    )
    subject = f"지원자 {candidate}님과" if candidate else "지원자와"
    scope = f" {role} 직무" if role else ""
    opening += f" {subject} 한국어 음성으로{scope} 면접을 진행합니다."

    sections = [opening, _STYLE]
    if report:
        titles = " / ".join(
            section["title"] for section in report if section.get("title")
        )
        if titles:
            sections.append(f"회사 조사 자료의 목차: {titles}")
    if parts:
        sections.append(f"지원자가 제출한 지원서 목차:\n{application_outline(parts)}")
    return "\n\n".join(sections)
