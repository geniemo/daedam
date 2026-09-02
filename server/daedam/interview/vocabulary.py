"""면접에서 나올 말들을 모아 전사에 힌트로 준다.

실측에서 이름과 용어가 계속 깨졌다.

    박지원          → "박지훈"
    Jetson AGX Orin → "Jeston Ajax 올인"
    산학협력         → "산악인력"
    주최 측          → "주재식이"

이런 낱말은 면접 전에 이미 손에 있다 — 회사·직무·지원서·질문이 그대로 그날
나올 말이다. `AudioTranscriptionConfig.custom_vocabulary`에 실으면 ASR이
그쪽으로 기울어진다.

**뽑는 일은 Grok이 한다.** 규칙으로 긁으면 영문 약어까지가 한계다. 한글은
조사가 붙어 오는 데다("산학협력을", "산학협력에서") 어느 것이 고유명사이고
어느 것이 흔한 말인지는 문맥이 정한다 — 조사 목록과 불용어 목록을 손으로
쌓는 길은 지원서가 바뀔 때마다 새로 깨진다.

**면접 시작이 아니라 준비 단계에서 부른다.** 커넥션을 열 때 부르면 면접
시작마다 몇 초가 붙고, 그 한 번이 실패하면 면접이 시작되지 않는다. 리서치와
질문 생성이 끝난 뒤 한 번 뽑아 파일로 두고, 면접은 읽기만 한다.

xAI API 확인 경로: `daedam.interview.generation` 모듈 docstring과 같다.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field
from daedam.llm import MODEL_QUALITY, text_client

_MODEL = MODEL_QUALITY

#: 어휘 힌트 상한. 많이 넣을수록 좋은 것이 아니라, 흔한 말까지 넣으면
#: 엉뚱한 곳에서 그 낱말로 끌려간다. 폴백은 규칙으로 긁는 것이라 더 좁게 둔다.
_MAX_TERMS = 150
_MAX_FALLBACK_TERMS = 60

#: 낱말 하나로 볼 최대 길이. 지원서 문항 제목은 통째로 한 문장이라("지원하신
#: 직무 분야의 전문성을 키우기 위해…") 어휘 힌트가 못 되고 상한만 잡아먹는다.
_MAX_PHRASE = 25

#: 지원서 본문에서 건질 영문 토막. 두 글자 이상이라야 약어로서 뜻이 있다.
_ASCII_TERM = re.compile(r"[A-Za-z][A-Za-z0-9.+-]{1,}")

#: 영문이지만 힌트로서 값이 없는 흔한 말. 넣으면 상한만 잡아먹는다.
_STOPWORDS = frozenset(
    {"ai", "it", "the", "and", "for", "with", "of", "in", "on", "to", "is",
     "data", "app", "web", "api", "team", "project", "system"}
)


class _ExtractedVocabulary(BaseModel):
    """Grok이 돌려줄 어휘 목록. 필드 설명이 곧 모델에게 주는 지시다."""

    terms: list[str] = Field(
        description="전사가 틀리기 쉬운 낱말들. 한글은 조사를 뗀 표제어로"
        " ('품질관리를'이 아니라 '품질관리'), 영문과 외래어는 자료에 적힌 표기"
        " 그대로. 한 낱말이나 짧은 구로, 문장을 넣지 마십시오"
    )


def generate_vocabulary(
    *,
    company: str,
    role: str,
    name: str = "",
    application: list[dict[str, Any]],
    questions: list[dict[str, Any]] | None = None,
    client: Any | None = None,
) -> list[str]:
    """전사에 힌트로 줄 낱말 목록을 Grok으로 뽑는다.

    이름·회사·직무는 확실하므로 Grok에 맡기지 않고 앞에 그대로 둔다. 가장 자주
    나오고 가장 자주 깨지는 낱말이라, 추출이 어떻게 나오든 빠지면 안 된다.

    Args:
        company: 회사 이름.
        role: 직무 이름.
        name: 지원자 이름.
        application: 지원서 파트 목록.
        questions: 질문 풀. 면접관이 실제로 읽을 문장이다.
        client: OpenAI 호환 클라이언트. 기본값은 GOOGLE_API_KEY로 만든 실제
            클라이언트고, 테스트는 대역을 주입한다.

    Returns:
        `custom_vocabulary`에 그대로 넣을 목록. 중복 없이 순서를 지킨다.
    """
    if client is None:
        client = text_client()

    completion = client.beta.chat.completions.parse(
        model=_MODEL,
        messages=[
            {
                "role": "user",
                "content": vocabulary_prompt(
                    company=company,
                    role=role,
                    name=name,
                    application=application,
                    questions=questions,
                ),
            }
        ],
        response_format=_ExtractedVocabulary,
    )
    extracted = completion.choices[0].message.parsed
    return _merged(
        _seed_terms(company=company, role=role, name=name),
        extracted.terms if extracted else [],
        limit=_MAX_TERMS,
    )


def vocabulary_prompt(
    *,
    company: str,
    role: str,
    name: str = "",
    application: list[dict[str, Any]],
    questions: list[dict[str, Any]] | None = None,
) -> str:
    """추출 지시문을 조립한다. 지원서 전문과 질문 문장을 그대로 싣는다."""
    body = "\n\n".join(
        f"[{part.get('part', '')} · {item.get('title', '')}]\n{item.get('body', '')}"
        for part in application
        for item in part.get("items", [])
    )
    asked = "\n".join(f"- {q.get('text', '')}" for q in questions or [])
    return f"""\
아래는 곧 있을 면접의 자료입니다. 이 면접의 음성을 받아쓸 음성 인식 모델에게
미리 알려 줄 낱말을 뽑으십시오. 알려 준 낱말은 인식이 그쪽으로 기울어집니다.

고르는 기준은 분야가 아니라 **흔한 말인가**입니다. 어느 직무의 지원서든 같은
자로 보십시오 — 흔하지 않아서 잘못 들릴 만한 낱말을 고르는 일입니다.

뽑을 것:
- 이름. 사람·조직·제품·서비스·프로젝트·대회·기관·학교·자격 등 고유한 것의 이름
- 그 일을 하는 사람들끼리 쓰는 말. 분야가 무엇이든, 바깥 사람은 잘 안 쓰는 말
- 소리가 비슷한 흔한 말이 있어 그쪽으로 잘못 들릴 만한 낱말

뽑지 말 것:
- 흔한 일반 명사와 서술어. 이미 잘 인식됩니다. 자리만 잡아먹고, 흔한 말을
  편들면 정작 드문 낱말이 밀립니다
- 문장이나 긴 구. 낱말과 짧은 구만 넣으십시오

쓰는 방식:
- 한글은 조사를 뗀 표제어로. "품질관리를"이 아니라 "품질관리"
- 영문과 외래어는 자료에 적힌 표기 그대로. 임의로 풀어쓰거나 줄이지 마십시오
- 한글과 영문 표기가 둘 다 자료에 있으면 둘 다 넣으십시오
- 같은 것을 두 번 넣지 마십시오

면접 자리에서 실제로 소리 내어 말해질 낱말인지로 고르십시오. 자료에 있어도
대화에 나올 일이 없는 것은 빼십시오.

[면접] {company} · {role}{f" · 지원자 {name}" if name else ""}

[지원서]
{body}

[면접관이 물을 질문]
{asked}"""


def interview_vocabulary(
    *,
    company: str,
    role: str,
    name: str = "",
    application: list[dict[str, Any]],
    questions: list[dict[str, Any]] | None = None,
    stored: list[str] | None = None,
) -> list[str]:
    """면접에 실을 어휘 힌트 — 확실한 키워드에 저장된 추출 어휘를 합친다.

    앞서는 저장된 추출 어휘가 있으면 그것만 썼는데, 추출은 LLM이라 확실한
    낱말을 빠뜨릴 수 있다 — 실측에서 이름이 힌트에 빠진 채 면접이 돌아
    전사가 깨졌다. 키워드(이름·회사·직무·지원서 제목·영문 용어·질문 태그)는
    규칙이라 절대 빠지지 않고, 추출 어휘는 그 위에 얹는다.

    한글 일반 용어까지 가는 것은 여전히 추출의 몫이다 — 조사가 붙어 와서
    규칙으로는 못 가른다("산학협력을", "산학협력에서").

    Args:
        company: 회사 이름.
        role: 직무 이름.
        name: 지원자 이름.
        application: 지원서 파트 목록.
        questions: 질문 풀. 태그가 그날의 주제어다.
        stored: 준비 단계에서 뽑아 둔 추출 어휘. 없으면 키워드만 싣는다.

    Returns:
        `custom_vocabulary`에 그대로 넣을 목록. 상한을 넘으면 앞에서 자른다 —
        앞쪽이 이름·회사·추출 어휘라 값이 큰 순서다.
    """
    titles = [
        title
        for part in application
        for title in (
            part.get("part", ""),
            *(item.get("title", "") for item in part.get("items", [])),
        )
    ]
    # 본문의 영문 용어를 태그보다 먼저 넣는다 — 가장 많이 깨지는 것들이고,
    # 상한에 걸리면 뒤가 잘리기 때문이다.
    ascii_terms = [
        found
        for part in application
        for item in part.get("items", [])
        for found in _ASCII_TERM.findall(item.get("body", ""))
        if found.lower() not in _STOPWORDS
    ]
    tags = [tag for question in questions or [] for tag in question.get("tags", [])]
    return _merged(
        _seed_terms(company=company, role=role, name=name),
        list(stored or []),
        [*titles, *ascii_terms, *tags],
        # 추출 어휘가 있으면 넉넉한 상한을 쓴다 — 정제된 목록이라서다.
        # 키워드만일 때는 좁게 둔다(규칙으로 긁은 것이라 잡음이 섞인다).
        limit=_MAX_TERMS if stored else _MAX_FALLBACK_TERMS,
    )


def _seed_terms(*, company: str, role: str, name: str) -> list[str]:
    """무슨 일이 있어도 실려야 하는 낱말.

    이름이 맨 앞이다 — ASR이 가장 자주 틀리는 낱말이고(실측 "박지원" →
    "박지훈"), 면접 내내 반복해서 나온다.
    """
    return [name, company, *role.split("·")]


def _merged(*groups: list[str], limit: int) -> list[str]:
    """여러 묶음을 순서대로 잇고, 중복과 문장 길이의 항목을 걷어낸다.

    지원서 문항 제목은 통째로 한 문장이라("지원하신 직무 분야의 전문성을 키우기
    위해…") 어휘 힌트가 못 되고 상한만 잡아먹는다.
    """
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for value in group:
            value = value.strip()
            if not value or len(value) > _MAX_PHRASE or value.lower() in seen:
                continue
            seen.add(value.lower())
            merged.append(value)
    return merged[:limit]
