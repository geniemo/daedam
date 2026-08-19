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
#: 모델이 턴마다 조건을 판정해야 한다.
#:
#: 툴을 **언제** 부르는지는 여기 있고, 인자를 **어떻게** 채우는지는 툴 docstring이
#: 소유한다. 앞의 것은 매 턴 판단하는 대화 규칙이고 뒤의 것은 호출하는 순간에만
#: 읽는 것이라, 자리가 다르다.
#:
#: 툴을 부르기 전에는 아무 말도 하지 않게 한다. 인사도 반응도 툴 뒤에 온다.
#:
#: 반응을 툴 앞에 두면 — 어떻게 좁혀 써도 — 질문이 두 번 나간다. 모델이 물을
#: 것을 툴보다 먼저 알 때는 반응이 질문까지 흘러갔고(실측 11개 중 5개), 서버가
#: 파볼 곳을 정해 줘서 모델이 물을 것을 모르게 한 뒤에도 마찬가지였다 — 반응
#: 하는 틈에 search_knowledge로 지원서를 뒤지고 그 결과로 질문을 만들어 말한 뒤
#: 툴을 불렀다(실측). 반응은 "말해도 되는 시간"이고, 그 시간에 모델이 쓸 수
#: 있는 어떤 재료든 질문이 되어 나온다.
#:
#: 서버가 같은 목소리 이름으로 만든 TTS 클립을 추임새로 내보내는 것도 해 봤으나
#: 뺐다 — 이름이 같아도 다른 엔진이라 목소리가 달랐고, 모델은 클립을 못 들으니
#: 자기도 추임새를 해서 두 번 들렸다. 툴이 도는 2초는 그냥 비운다. 면접관이
#: 답변을 듣고 잠깐 뜸 들이는 것은 부자연스럽지 않다.
#:
#: 인사 줄이 "인사와 함께"가 아니라 "인사한 뒤"인 이유: "인사와 함께 돌아온 첫
#: 질문을"이라고 했더니 모델이 인사 자리에서 자기소개를 했다 — 지원자 이름으로
#: ("SK하이닉스 기반기술 직무에 지원한 박지원입니다"). 툴이 준 문장이 "자기소개
#: 부탁드립니다"라 그 문맥에 끌려간 것으로 보인다. 인사와 질문을 "한 뒤"로
#: 떼어 놓으면 인사 자리에 질문 문맥이 번질 자리가 없다.
#:
#: 인사 줄이 툴 이름까지 나르는 이유: 첫 턴에는 답변이 없어 "답변을 들으면"
#: 규칙이 안 걸리고, 툴 규칙은 아래 문단에 따로 있다. 그러면 모델이 그 순간
#: 가장 정확히 들어맞는 문장(인사 → 면접 시작)만 따르고 툴을 부를 자리가 없다.
#: 실측에서 첫 질문만 반복해서 툴을 건너뛰었다. 이 줄이 첫 턴을 혼자 감당한다 —
#: 툴 결과에 붙는 "다음 질문 전에 다시 부르세요"(`interviewer.tools.
#: _ASK_INSTRUCTION`)는 첫 호출 뒤에야 도착한다.
_STYLE = """\
- 존댓말로, 담담하고 정중하게. 한 번에 질문은 하나만.
- 문장을 짧게 끊으세요. 음성이라 긴 문장은 알아듣기 어렵습니다.
- 답변을 평가하는 말("좋은 답변이네요")은 하지 마세요.

지원자가 인사하면 아무 말 없이 먼저 ask_question을 부르고, 그다음에 인사한 뒤
돌아온 첫 질문을 물어보세요.

지원자의 답변을 들으면 아무 말 없이 먼저 ask_question을 부르세요. 반응은 툴이
돌아온 뒤에 질문과 함께 말합니다.

모든 질문은 반드시 툴을 거칩니다. 무엇을 물을지는 툴이 정합니다 — 부르기 전에
질문을 지어내 미리 묻지 마세요.
- 준비된 질문(ask)이 오면 그 문장을 그대로 물어보세요.
- 파볼 곳(probe)이 오면 그 주제를 당신의 문장으로 물어보세요. 답변에서 무엇이
  빠졌는지(hint)가 같이 옵니다 — 힌트를 읽지 말고 그것을 묻는 질문을 만드세요.
- 파볼 곳을 물은 뒤의 호출에는 answered를 꼭 적으세요 — 답을 들었으면 yes와 들은
  내용(evidence), 못 들었으면 no.

면접을 끝내는 것은 지원자입니다. 당신이 먼저 마무리하지 마세요."""


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
