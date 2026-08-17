"""답변 내용 평가·코칭 — Grok 오프라인 배치.

면접이 끝난 뒤 전사를 받아 답변마다 코칭을 붙이고 총평을 낸다. 면접 중에는
호출되지 않는다 — 리포트를 만드는 시점의 배치 작업이다.

**점수는 답변 점수의 평균이다.** 총점을 따로 매기게 하면 그 숫자가 어디서
나왔는지 아무도 설명할 수 없다. 답변마다 매기고 평균 내면 "3번 답변이 낮아서
총점이 낮다"까지 화면에서 짚을 수 있다.

**백분위(상위 몇 %)는 내지 않는다.** 비교할 모집단이 없다. 지어내면 리포트
전체의 신뢰가 거기서 무너진다.

**근거 없는 칭찬·지적을 막는 장치**: 평가는 지원자가 실제로 한 말만 근거로
쓰게 한다. 말하지 않은 것을 두고 "이런 점이 좋았다"가 나오면 코칭이 아니라
소설이다.

**필러 워드는 목록이 아니라 문맥으로 센다.** "그 프로젝트"의 "그"와 "어… 그러니까"의
"그"는 같은 글자다. 정규식으로는 못 가르므로 평가에 함께 맡기고, 개수만이 아니라
찾은 낱말을 받아 화면에서 짚을 수 있게 한다.

**짧은 답변도 평가한다.** 답변이 짧았다는 것 자체가 해줘야 할 피드백이다 —
빼면 코칭이 그 얘기를 못 한다. 거르는 것은 전사 잡음뿐이다.

xAI API 확인 경로: daedam/interview/generation.py 첫 주석과 같다
  (OpenAI 호환 / base_url https://api.x.ai/v1 / grok-4.5 / .parse)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

_MODEL = "grok-4.5"
_BASE_URL = "https://api.x.ai/v1"

#: 전사 잡음을 거르는 하한. 기침이나 헛기침이 "어" 한 글자로 잡히는 것을
#: 빼려는 것이지 짧은 답변을 빼려는 것이 아니다 — 답변이 짧았다는 것 자체가
#: 해줘야 할 피드백이다(실측 "안녕하세요. 박지원입니다." 13자).
_MIN_ANSWER_CHARS = 4


@dataclass(frozen=True)
class Exchange:
    """면접관의 질문과 그에 대한 답변 한 쌍."""

    question: str
    answer: str


def exchanges_from(transcript: dict[str, Any]) -> list[Exchange]:
    """전사를 질문·답변 쌍으로 묶는다.

    면접관 발화 뒤에 오는 지원자 발화가 그 질문의 답이다. 면접관이 연달아
    말했으면 마지막 것을 질문으로 본다 — 인사와 질문이 한 턴에 오는 경우가
    있어서(실측: "안녕하세요 … 먼저 자기소개 부탁드립니다") 첫 번째를 잡으면
    질문이 아니라 인사가 붙는다.

    **지원자 발화가 연달아 오면 이어 붙인다.** 한 답변이 전사 여러 조각으로
    온다 — 말하다 잠깐 쉬면 Live API가 거기서 발화가 끝난 것으로 보고
    finished를 낸다(실측: "안녕하십니까? 음" 다음에 "어, 박지호입니다. 음.").
    첫 조각만 쓰면 코칭이 반쪽 답변을 채점한다.
    """
    pairs: list[Exchange] = []
    question: str | None = None
    parts: list[str] = []

    def flush() -> None:
        if question is not None and parts:
            pairs.append(Exchange(question=question, answer=" ".join(parts)))
        parts.clear()

    for utterance in transcript.get("utterances", []):
        if utterance.get("speaker") == "interviewer":
            flush()
            question = utterance.get("text", "")
            continue
        if question is None:
            continue  # 질문 없이 나온 말 — 첫 인사 같은 것
        parts.append(utterance.get("text", ""))
    flush()
    return pairs


class AnswerReview(BaseModel):
    """답변 하나에 대한 코칭."""

    question: str = Field(description="평가한 질문. 받은 문장 그대로 옮기십시오.")
    score: int = Field(
        ge=0,
        le=100,
        description="이 답변만 놓고 매긴 점수. 60은 무난, 80은 근거와 수치가"
        " 분명함, 40은 질문에 답하지 않음. 총점은 이 값들의 평균이 됩니다.",
    )
    strength: str = Field(
        description="이 답변에서 실제로 잘한 대목. 지원자가 말한 표현을 인용해"
        " 짚으십시오. 없으면 빈 문자열로 두십시오 — 지어내지 마십시오."
    )
    gap: str = Field(
        description="면접관이 더 듣고 싶었을 것. 무엇이 빠졌는지 한 가지만"
        " 구체적으로."
    )
    suggestion: str = Field(
        description="다시 답한다면 어떻게 할지. 지원자가 실제로 가진 경험 안에서"
        " 제안하십시오. 없는 경력을 가정하지 마십시오."
    )
    fillers: list[str] = Field(
        default_factory=list,
        description="이 답변에서 **필러 워드로** 쓰인 낱말을 나온 순서대로."
        " 음·어·그·저기·um·uh 같은 것입니다. 다만 뜻을 가지고 쓰였으면 빼십시오"
        " — '그 프로젝트'의 '그'는 지시어이고 '아, 네'의 '아'는 대답입니다."
        " 없으면 빈 목록으로 두십시오.",
    )


class InterviewReview(BaseModel):
    """면접 한 판에 대한 코칭 전체."""

    answers: list[AnswerReview]
    summary: str = Field(description="면접 전체 총평 두세 문장. 점수가 아니라 인상.")
    strengths: list[str] = Field(description="전체에서 반복적으로 드러난 강점 2~3개.")
    improvements: list[str] = Field(
        description="다음 면접까지 고칠 것 2~3개. 실행할 수 있는 형태로."
    )


@dataclass(frozen=True)
class Coaching:
    """리포트 화면이 그대로 읽는 평가 결과."""

    review: InterviewReview
    #: 답변 점수의 평균. 평가 대상이 없으면 None — 0점과 다르다.
    score: int | None

    @property
    def fillers(self) -> int:
        """필러 워드로 쓴 낱말의 총 개수."""
        return sum(len(answer.fillers) for answer in self.review.answers)

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "fillers": self.fillers,
            "summary": self.review.summary,
            "strengths": list(self.review.strengths),
            "improvements": list(self.review.improvements),
            "answers": [answer.model_dump() for answer in self.review.answers],
        }


def coaching_prompt(
    *, company: str, role: str, exchanges: list[Exchange]
) -> str:
    """평가 지시문을 조립한다."""
    lines = [
        f"{company} {role} 채용 면접이 방금 끝났습니다. 지원자가 다음 면접을"
        " 더 잘 보도록 코칭하십시오.",
        "",
        "원칙:",
        "- 근거. 지원자가 실제로 한 말만 근거로 쓰십시오. 말하지 않은 것을 두고"
        " 좋았다거나 부족했다고 하지 마십시오.",
        "- 구체. '더 구체적으로 말하세요' 같은 지적은 코칭이 아닙니다. 어느"
        " 대목에 무엇이 빠졌는지 짚으십시오.",
        "- 실행. 제안은 지원자가 가진 경험 안에서 하십시오. 없는 경력을"
        " 가정하면 다음 면접에서 쓸 수 없습니다.",
        "- 존중. 사람이 읽습니다. 평가하되 깎아내리지 마십시오.",
        "",
        "주고받은 내용:",
    ]
    for index, exchange in enumerate(exchanges, start=1):
        lines += [
            "",
            f"[{index}] 면접관: {exchange.question}",
            f"    지원자: {exchange.answer}",
        ]
    return "\n".join(lines)


def evaluate(
    *,
    company: str,
    role: str,
    transcript: dict[str, Any],
    client: Any | None = None,
) -> Coaching:
    """전사를 평가해 코칭을 만든다.

    Args:
        company: 회사 이름.
        role: 직무 이름.
        transcript: `InterviewRecording`이 남긴 전사.
        client: OpenAI 호환 클라이언트. 기본값은 XAI_API_KEY로 만든 실제
            클라이언트고, 테스트는 대역을 주입한다.

    Returns:
        평가 결과. 평가할 답변이 하나도 없으면 빈 결과(점수 None)를 돌려준다 —
        면접을 시작만 하고 끝낸 경우가 실제로 있다.
    """
    scored = [
        exchange
        for exchange in exchanges_from(transcript)
        if len(exchange.answer.strip()) >= _MIN_ANSWER_CHARS
    ]
    if not scored:
        return Coaching(
            review=InterviewReview(
                answers=[],
                summary="평가할 답변이 없습니다. 면접을 끝까지 진행해 주세요.",
                strengths=[],
                improvements=[],
            ),
            score=None,
        )

    if client is None:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["XAI_API_KEY"], base_url=_BASE_URL)

    completion = client.beta.chat.completions.parse(
        model=_MODEL,
        messages=[
            {
                "role": "user",
                "content": coaching_prompt(
                    company=company, role=role, exchanges=scored
                ),
            }
        ],
        response_format=InterviewReview,
    )
    review = completion.choices[0].message.parsed
    scores = [answer.score for answer in review.answers]
    # 총점을 따로 받지 않는다 — 답변 점수의 평균이라야 어디서 나온 숫자인지
    # 화면에서 짚을 수 있다.
    return Coaching(review=review, score=round(sum(scores) / len(scores)) if scores else None)
