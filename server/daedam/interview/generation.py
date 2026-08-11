"""뼈대질문 풀 생성 — Grok 오프라인 배치.

검토가 끝난 리서치 리포트와 지원서를 청크 형태로 받아, 4단계 면접의 질문
풀을 만든다. 질문마다 태그(세션별 동적 어휘 — 툴 선언 enum에 실린다)와
근거 청크 id(오프라인 품질 점검용)를 붙인다. 면접 중에는 호출되지 않는다 —
검토 제출 시점의 배치 작업이다.

xAI API 확인 경로 (docs.x.ai, 2026-08 확인):
  - OpenAI 호환: base_url https://api.x.ai/v1, 모델 grok-4.5
  - 구조화 출력: client.beta.chat.completions.parse(response_format=<pydantic
    모델>) → choices[0].message.parsed
"""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any

from pydantic import BaseModel, Field

from daedam.interview.question_pool import QuestionPool
from daedam.interview.stages import STAGE_NAMES
from daedam.knowledge.chunk import Chunk

_MODEL = "grok-4.5"
_BASE_URL = "https://api.x.ai/v1"

#: 생성 대상 단계(0~2)의 목표 개수. 실제로 나가는 수(2/3/2)보다 넉넉하게
#: 만들어 모델이 면접 맥락에 맞는 질문을 고를 여지를 준다.
_TARGET_COUNTS = (3, 5, 4)

#: 단계별 최소 개수 — 실전에서 나가는 수. 이보다 적으면 생성 실패로 본다.
_MINIMUM_COUNTS = (2, 3, 2)

#: 마무리 단계는 정형화돼 있어 생성하지 않는다 — 고정 질문을 그대로 쓴다.
#: 역질문 유도("궁금한 점")는 면접 에이전트가 현장에서 처리한다.
_CLOSING_QUESTIONS: list[dict[str, Any]] = [
    {"id": "q-3-0", "stage": 3, "text": "입사하시면 가장 해보고 싶은 일은 무엇인가요?",
     "priority": 1, "tags": ["입사 포부"], "source_chunk_ids": []},
    {"id": "q-3-1", "stage": 3, "text": "마지막으로 하고 싶은 말씀이 있으신가요?",
     "priority": 2, "tags": ["마지막 한마디"], "source_chunk_ids": []},
]


class _GeneratedQuestion(BaseModel):
    """Grok이 돌려줄 질문 하나. 필드 설명이 곧 모델에게 주는 지시다."""

    stage: int = Field(
        description="이 질문이 나갈 단계 인덱스. 0 자기소개, 1 직무역량, 2 인성·컬처핏"
    )
    text: str = Field(
        description="면접관이 음성으로 그대로 읽을 한국어 질문. 물음표 하나로 끝나는 존댓말 한 문장,"
        " 공백 포함 40자 안팎. 괄호·따옴표·줄임표를 쓰지 않고, 예/아니오로 답이 끝나지 않게"
    )
    priority: int = Field(
        description="단계 안에서 나가는 순서. 1부터 1씩 올리고 같은 단계 안에서 중복 없이."
        " 대답의 폭이 넓어 뒤이어 파고들 여지가 큰 질문일수록 낮은 숫자"
    )
    tags: list[str] = Field(
        description="이 질문의 주제 이름 1~2개. 2~6자 한국어 명사구로 쓰고 복합어는 띄어 씁니다"
        "(수치 검증, 협업 방식, 기술 선택). 질문을 요약하지 말고 주제를 명명하며,"
        " 같은 단계 안의 다른 질문과 겹치지 않게. 면접 에이전트가 다음 질문 주제를 고르는 선택지가 됩니다"
    )
    source_chunk_ids: list[str] = Field(
        description="근거로 삼은 청크 id를 자료에 적힌 그대로. 회사 자료와 지원서를 함께 썼으면 둘 다."
        " 자료의 사실 없이 만든 일반 질문이면 빈 목록 — 추측한 id를 적지 마십시오"
    )


class _GeneratedPool(BaseModel):
    questions: list[_GeneratedQuestion]


def generate_question_pool(
    *,
    company: str,
    role: str,
    report_chunks: list[Chunk],
    application_chunks: list[Chunk],
    client: Any | None = None,
) -> list[dict[str, Any]]:
    """질문 풀을 생성해 `QuestionPool.from_dicts` 입력 형태로 돌려준다.

    Args:
        company: 회사 이름.
        role: 직무 이름.
        report_chunks: 검토 반영된 리서치 리포트의 검색 청크.
        application_chunks: 지원서의 검색 청크.
        client: OpenAI 호환 클라이언트. 기본값은 XAI_API_KEY로 만든 실제
            클라이언트고, 테스트는 대역을 주입한다.

    Returns:
        id·stage·text·priority·tags·source_chunk_ids를 담은 dict 목록.

    Raises:
        ValueError: 생성 결과가 검증(단계 개수·태그·근거 id 실존)을 통과하지
            못하면. 오프라인 배치라 조용히 넘어가지 않고 크게 실패한다.
    """
    if client is None:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["XAI_API_KEY"], base_url=_BASE_URL)

    completion = client.beta.chat.completions.parse(
        model=_MODEL,
        messages=[
            {
                "role": "user",
                "content": generation_prompt(
                    company=company,
                    role=role,
                    report_chunks=report_chunks,
                    application_chunks=application_chunks,
                ),
            }
        ],
        response_format=_GeneratedPool,
    )
    generated = completion.choices[0].message.parsed
    known_ids = {chunk.id for chunk in report_chunks + application_chunks}
    raw = _validated(generated.questions, known_ids) + deepcopy(_CLOSING_QUESTIONS)
    QuestionPool.from_dicts(raw)  # 로딩 검증까지 통과해야 저장할 자격이 있다
    return raw


def generation_prompt(
    *,
    company: str,
    role: str,
    report_chunks: list[Chunk],
    application_chunks: list[Chunk],
) -> str:
    """생성 지시문을 조립한다.

    정적 규칙을 앞에, 세션 가변 데이터(회사·직무·청크)를 뒤에 둔다 — 세션이
    바뀌어도 프롬프트 캐시 prefix가 유지되게(xAI 캐시 best-practice, 2026-08
    확인). 청크는 id와 함께 나열해 근거 인용이 가능하게 한다.
    """
    counts = "\n".join(
        f"- {index} {name}: {count}개"
        for index, (name, count) in enumerate(zip(STAGE_NAMES, _TARGET_COUNTS))
    )
    report_lines = "\n".join(
        f"({chunk.id}) [{chunk.title}] {chunk.text}" for chunk in report_chunks
    )
    application_lines = "\n".join(
        f"({chunk.id}) [{chunk.title}] {chunk.text}" for chunk in application_chunks
    )
    return f"""\
당신은 신입 채용 면접의 질문을 설계하는 면접관입니다.

뼈대질문은 완결된 문답이 아니라 파고들 입구입니다. 면접 중 꼬리질문은 실시간 음성
에이전트가 대답을 듣고 즉석에서 만듭니다. 그러니 각 질문은 지원자가 자기 경험을
펼쳐놓게 만들고, 그 대답 안에 되물을 거리가 남아 있어야 합니다.

단계와 개수:
{counts}

개수는 정확히 맞추십시오.

단계별 성격:
- 0 자기소개: 지원서에 적힌 사실 하나를 집어 말문을 열게 합니다. 검증이 아니라 진입입니다.
- 1 직무역량: 지원서의 프로젝트·수치·기술 선택을 파고듭니다. 결과가 아니라 과정과
  판단을 묻습니다.
- 2 인성·컬처핏: 회사 자료에 드러난 일하는 방식·가치·재직자 발언을 지원자의 경험과
  맞댑니다.

질문 원칙:
- 근거. 아래 자료의 구체적 사실에서 출발하고, 근거로 쓴 청크 id를 source_chunk_ids에
  적으십시오. 자료에 없는 사실을 지어내지 마십시오.
- 검증. 수치와 성과는 결과를 확인하지 말고, 측정 기준·본인이 맡은 범위·그렇게 판단한
  이유를 묻습니다.
- 열림. 예/아니오나 한 단어로 답이 끝나는 질문, 답을 정해두고 확인만 받는 질문은
  만들지 마십시오.
- 겹침 금지. 같은 사실을 두 질문이 각도만 바꿔 묻지 않게 합니다.

말하는 방식 — 이 문장은 사람이 소리 내어 읽습니다:
- 물음표 하나로 끝나는 한 문장. 배경 설명을 앞 문장으로 덧붙이지 마십시오.
- 공백 포함 40자 안팎. 길어지면 근거를 하나만 남기고 잘라내십시오.
- 어미를 굴리십시오. 풀 전체에서 같은 어미가 세 번 넘게 반복되면 다시 쓰십시오.
  (~어떻게 하셨나요 / ~무엇이었나요 / ~어떤 기준으로 고르셨어요 / ~어떤 점이 달랐나요)
- 괄호·따옴표·슬래시·줄임표·목록 기호를 쓰지 마십시오. 숫자와 영문 약어는 소리 내
  읽기 쉬운 형태로 씁니다.

예시 — 다른 업종이니 내용을 가져다 쓰지 마십시오:
- 나쁨: "이탈률을 12% 낮추셨네요. 그 과정에서 본인이 맡은 범위와 측정 방법을 말씀해
  주시겠어요?" — 두 문장이고 너무 깁니다.
- 좋음: "이탈률 12% 감소는 어떤 지표로 확인하셨나요?"

출력 순서는 stage 오름차순, 같은 단계 안에서는 priority 오름차순으로 넣으십시오.

[회사 리서치 청크]
{report_lines}

[지원서 청크]
{application_lines}

위 자료는 {company}의 {role} 직무 신입 채용 건입니다. 원칙대로 뼈대질문 풀을
만드십시오."""


def _validated(
    questions: list[_GeneratedQuestion], known_chunk_ids: set[str]
) -> list[dict[str, Any]]:
    """생성 결과를 검증하고 id를 부여해 풀 입력 형태로 만든다."""
    counters = [0] * len(_TARGET_COUNTS)
    raw: list[dict[str, Any]] = []
    for question in questions:
        if not 0 <= question.stage < len(_TARGET_COUNTS):
            raise ValueError(f"단계가 범위 밖: {question.stage} — {question.text}")
        if not question.tags:
            raise ValueError(f"태그 없는 질문: {question.text}")
        unknown = set(question.source_chunk_ids) - known_chunk_ids
        if unknown:
            raise ValueError(f"실존하지 않는 근거 청크 {unknown} — {question.text}")
        raw.append(
            {
                "id": f"q-{question.stage}-{counters[question.stage]}",
                "stage": question.stage,
                "text": question.text,
                "priority": question.priority,
                "tags": question.tags,
                "source_chunk_ids": question.source_chunk_ids,
            }
        )
        counters[question.stage] += 1

    for stage, (count, minimum) in enumerate(zip(counters, _MINIMUM_COUNTS)):
        if count < minimum:
            raise ValueError(
                f"{STAGE_NAMES[stage]} 단계 질문 부족: {count}개 (최소 {minimum})"
            )
    return raw
