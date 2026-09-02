"""답변에서 파볼 곳 뽑기 — 면접 중 Grok 호출.

뼈대질문에 대한 답변이 들어오면, 그 답변에서 더 파고들 곳을 둘 고른다.
면접관 모델이 꼬리질문으로 무엇을 물을지를 모델 혼자 즉석에서 정하게 두면
답변에 붙지 않는다 — "직접 눈으로 보고 분류했다"를 듣고도 다음 키워드로
넘어간다(실측). 서버가 답변을 읽고 방향을 정해주면 꼬리질문이 답변에 붙는다.

**모델은 가벼운 것을 쓴다.** 면접 중 턴 사이에 돌아야 해서 지연이 곧 침묵이다.
실측(같은 프롬프트, 중앙값): gemini-3.5-flash-lite 1.2초, gemini-3.7-flash
4.2초, gemini-2.5-flash 7.4초. 1초대는 면접관의 짧은 추임새 하나로 덮이고
4초는 면접이 멈춘 것으로 들린다. 앞서 쓰던 grok-4.20-non-reasoning이 2초였다.

**실패해도 면접은 돈다.** 타임아웃이든 에러든 빈 목록으로 돌아오고, 호출자는
파볼 곳이 없는 것으로 보고 다음 뼈대질문으로 간다. 면접 중 LLM 호출은 면접을
멈출 권리가 없다.

xAI API 확인 경로: `daedam.interview.generation` 모듈 docstring과 같다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from daedam.llm import MODEL_FAST, text_client

logger = logging.getLogger(__name__)

#: 추론 없이 바로 답하는 모델. 면접 중이라 속도가 품질보다 앞선다.
_MODEL = MODEL_FAST

#: 이보다 오래 걸리면 포기한다. 그 사이 면접관은 반응 한마디로 버티는데,
#: 그보다 길어지면 침묵이 된다.
_TIMEOUT_S = 4.0

#: 뼈대질문 하나에서 파볼 곳의 수. 셋이면 한 주제에 너무 오래 머문다.
PROBE_COUNT = 2


class _Probe(BaseModel):
    """Grok이 돌려줄 파볼 곳 하나. 필드 설명이 곧 모델에게 주는 지시다."""

    topic: str = Field(
        description="파볼 주제. 2~6자 한국어 명사구 (예: 분류 기준, 본인 역할, 측정 방법)"
    )
    hint: str = Field(
        description="답변에서 무엇이 빠졌는지 한 문장, 공백 포함 30자 안팎."
        " 면접관이 이 한 줄만 보고 질문을 만듭니다. 괄호·나열·문어체를 쓰지 말고"
        " 말하듯이 (예: 기준이 무엇이었는지 안 나왔다)"
    )


class _Probes(BaseModel):
    probes: list[_Probe]
    leads_with: str = Field(
        default="",
        description="지원자가 이 답변에서 가장 비중 있게 말한 경험. [이어갈 경험 후보]에"
        " 적힌 문장 중 하나를 **그대로** 옮겨 적으십시오. 어느 것도 아니거나 후보가"
        " 없으면 빈 문자열",
    )


@dataclass(frozen=True)
class Probe:
    """파볼 곳 하나 — 주제와 왜 파는지."""

    topic: str
    hint: str

    def as_dict(self) -> dict[str, str]:
        return {"topic": self.topic, "hint": self.hint}


@dataclass(frozen=True)
class Extraction:
    """답변 하나에서 뽑은 것 — 파볼 곳들과, 이어갈 경험."""

    probes: list[Probe]
    #: 지원자가 방금 답변에서 비중 있게 말한 경험. 후보 중 하나를 그대로, 없으면 "".
    #: 다음 뼈대질문을 고를 때 이 경험부터 간다 — 자기소개에서 딥페이크 얘기를
    #: 길게 했는데 디밀리언부터 물으면 주제가 튄다(실측).
    leads_with: str = ""


def extract_probes(
    *,
    question: str,
    answer: str,
    experiences: list[str] | None = None,
    client: Any | None = None,
) -> Extraction:
    """답변에서 파볼 곳을 뽑는다. 실패하면 빈 결과.

    Args:
        question: 면접관이 물은 뼈대질문.
        answer: 지원자의 답변 전문. 여러 조각이면 이어 붙여서.
        experiences: 이어갈 경험 후보 — 아직 안 물은 뼈대질문이 딛고 선 경험마다
            대표 문장 하나. 주면 답변이 어느 경험을 비중 있게 말했는지 같이 고른다.
        client: OpenAI 호환 클라이언트. 기본값은 GOOGLE_API_KEY로 만든 실제
            클라이언트고, 테스트는 대역을 주입한다.

    Returns:
        파볼 곳(중요한 것 먼저, 최대 PROBE_COUNT개)과 이어갈 경험. 실패·타임아웃이면
        빈 결과 — 호출자는 파볼 곳이 없는 것으로 보고 진행한다.
    """
    if not answer.strip():
        return Extraction(probes=[])
    if client is None:
        client = text_client(timeout_s=_TIMEOUT_S)
    try:
        completion = client.beta.chat.completions.parse(
            model=_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": probe_prompt(
                        question=question, answer=answer, experiences=experiences
                    ),
                }
            ],
            response_format=_Probes,
        )
    except Exception:  # noqa: BLE001 — 면접 중 LLM 호출은 면접을 멈출 권리가 없다
        logger.warning("파볼 곳 추출 실패 — 빈 목록으로 진행합니다", exc_info=True)
        return Extraction(probes=[])
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        return Extraction(probes=[])
    # 빈 것을 거른 뒤 자른다. 먼저 자르면 빈 항목이 자리를 잡아먹는다.
    probes = [
        Probe(topic=p.topic.strip(), hint=p.hint.strip())
        for p in parsed.probes
        if p.topic.strip() and p.hint.strip()
    ]
    # 후보에 없는 것을 적었으면 버린다 — 그대로 옮기라고 했는데 안 맞으면 지어낸
    # 것이다. 호출자는 빈 값을 "못 골랐다"로 본다.
    leads_with = parsed.leads_with.strip()
    if experiences and leads_with not in experiences:
        leads_with = ""
    return Extraction(probes=probes[:PROBE_COUNT], leads_with=leads_with)


def probe_prompt(
    *, question: str, answer: str, experiences: list[str] | None = None
) -> str:
    """추출 지시문. 정적 규칙을 앞에, 질문·답변을 뒤에 둔다."""
    candidates = ""
    if experiences:
        listed = "\n".join(f"- {e}" for e in experiences)
        candidates = f"""

[이어갈 경험 후보]
아래는 아직 안 물은 질문들이 딛고 선 경험입니다. 지원자가 위 답변에서 이 중 어느
경험을 가장 비중 있게 말했으면 leads_with에 그 문장을 그대로 옮기십시오. 스친
정도면 비우십시오.
{listed}"""
    return f"""\
당신은 신입 채용 면접관입니다. 방금 지원자의 답변을 들었습니다.
이 답변에서 더 파고들 곳을 정확히 {PROBE_COUNT}곳 고르십시오.

고르는 기준:
- 주장만 있고 근거가 없는 곳. 수치·방법·그렇게 판단한 이유가 빠진 곳
- 본인이 한 일과 남이 한 일이 안 갈린 곳
- 말은 했는데 구체적이지 않은 곳. "잘 했다", "열심히 했다", "직접 했다"

고르지 말 것:
- 답변에 이미 충분히 설명된 것
- 답변과 무관한 새 주제. 파볼 곳은 이 답변 안에서 나와야 합니다
- "왜 기억이 안 나는지", "왜 모르는지" 같은 것. 지원자가 모른다고 하면 그 이유를
  캐는 것이 아니라 같은 것을 다른 각도로 묻거나(예: 기억나는 범위 안에서) 놓아
  주는 것입니다

답변이 너무 짧아 파볼 곳이 하나뿐이면 하나만 내십시오. 억지로 채우지 마십시오.
모른다·기억 안 난다고 했으면 다른 각도 하나만 내거나, 그것도 없으면 비우십시오.
둘 중 하나가 더 중요하면 그것을 먼저 두십시오.

[질문]
{question}

[답변]
{answer}{candidates}"""
