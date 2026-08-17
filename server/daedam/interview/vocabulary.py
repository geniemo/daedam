"""면접에서 나올 말들을 모아 전사에 힌트로 준다.

실측에서 이름과 기술 용어가 계속 깨졌다.

    박지원          → "박지훈"
    Jetson AGX Orin → "Jeston Ajax 올인"
    부족한           → "zan된"

이런 낱말은 면접 전에 이미 손에 있다 — 회사·직무·지원서·질문 태그가 그대로
그날 나올 말이다. `AudioTranscriptionConfig.custom_vocabulary`에 실으면
ASR이 그쪽으로 기울어진다.

**지원서 본문에서 영문 토막을 따로 뽑는 이유**: 가장 많이 깨지는 것이
기술 용어인데(TensorRT, Jetson, YOLO) 그것들은 항목 제목이 아니라 본문에
있다. 한글은 전사가 대체로 맞히므로 영문만 건진다.
"""

from __future__ import annotations

import re
from typing import Any

#: 어휘 힌트 상한. 많이 넣을수록 좋은 것이 아니라, 흔한 말까지 넣으면
#: 엉뚱한 곳에서 그 낱말로 끌려간다.
_MAX_TERMS = 60

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


def interview_vocabulary(
    *,
    company: str,
    role: str,
    name: str = "",
    application: list[dict[str, Any]],
    questions: list[dict[str, Any]] | None = None,
) -> list[str]:
    """전사에 힌트로 줄 낱말 목록. 중복 없이 등장 순서를 지킨다.

    Args:
        company: 회사 이름.
        role: 직무 이름.
        name: 지원자 이름.
        application: 지원서 파트 목록.
        questions: 질문 풀. 태그가 그날의 주제어다.

    Returns:
        `custom_vocabulary`에 그대로 넣을 목록. 상한을 넘으면 앞에서 자른다 —
        앞쪽이 회사·직무·지원서 제목이라 값이 큰 순서다.
    """
    terms: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        value = value.strip()
        if not value or len(value) > _MAX_PHRASE or value.lower() in seen:
            return
        seen.add(value.lower())
        terms.append(value)

    # 이름이 맨 앞이다 — ASR이 가장 자주 틀리는 낱말이고(실측 "박지원" →
    # "박지훈"), 면접 내내 반복해서 나온다.
    add(name)
    add(company)
    for piece in role.split("·"):
        add(piece)

    for part in application:
        add(part.get("part", ""))
        for item in part.get("items", []):
            add(item.get("title", ""))

    # 본문의 영문 용어를 태그보다 먼저 넣는다 — 가장 많이 깨지는 것들이고,
    # 상한에 걸리면 뒤가 잘리기 때문이다.
    for part in application:
        for item in part.get("items", []):
            for found in _ASCII_TERM.findall(item.get("body", "")):
                if found.lower() not in _STOPWORDS:
                    add(found)

    for question in questions or []:
        for tag in question.get("tags", []):
            add(tag)

    return terms[:_MAX_TERMS]
