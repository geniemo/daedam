"""단계별 뼈대질문 풀.

풀은 세션 시작 전에 오프라인에서 만들어진다(리서치 리포트 + 지원서 → 질문 생성).
런타임에는 조회만 하며, 한 번에 질문 하나만 돌려준다 — 고르지 않은 후보가 대화
컨텍스트에 남는 것을 막기 위해서다. 대신 모델은 태그로 원하는 주제를 지정한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Iterable

from .stages import STAGE_NAMES


@dataclass(frozen=True)
class Question:
    """뼈대질문 하나.

    Attributes:
        id: 풀 안에서 고유한 식별자.
        stage: 이 질문이 속한 단계 인덱스(0~3).
        text: 면접관이 읽을 질문 문장.
        priority: 낮을수록 먼저 낸다.
        tags: 질문 주제 태그. 고정 어휘가 아니라 질문 생성 시 질문과 함께
            만들어지며, 풀에 실린 태그가 곧 그 세션의 어휘가 된다.
        source_chunk_ids: 이 질문의 근거가 된 청크 id(지원서 항목·리서치 블록).
            질문을 배달할 때 함께 붙여 보내면 면접 중 검색 호출이 줄어든다.
    """

    id: str
    stage: int
    text: str
    priority: int
    tags: tuple[str, ...] = field(default=())
    source_chunk_ids: tuple[str, ...] = field(default=())

    def as_result(self) -> dict[str, str]:
        """모델에게 넘길 형태로 직렬화한다.

        Returns:
            id와 text만 담은 dict. 우선순위와 근거 청크 id는 서버 내부용이다.
        """
        return {"id": self.id, "text": self.text}


class QuestionPool:
    """한 세션의 뼈대질문 모음."""

    def __init__(self, questions: Iterable[Question]) -> None:
        """풀을 만든다.

        Args:
            questions: 질문 목록.

        Raises:
            ValueError: 단계가 범위를 벗어나거나 id가 중복되면.
        """
        self._questions = list(questions)
        self._by_id: dict[str, Question] = {}
        for question in self._questions:
            if not 0 <= question.stage < len(STAGE_NAMES):
                raise ValueError(f"단계가 범위를 벗어남: {question.id} → {question.stage}")
            if question.id in self._by_id:
                raise ValueError(f"질문 id 중복: {question.id}")
            self._by_id[question.id] = question

    @classmethod
    def from_dicts(cls, raw: list[dict[str, Any]]) -> QuestionPool:
        """오프라인 생성 결과(JSON)를 풀로 읽어들인다.

        Args:
            raw: `{"id", "stage", "text", "priority", "tags"?,
                "source_chunk_ids"?}` 형태의 dict 목록.

        Returns:
            QuestionPool 인스턴스.

        Raises:
            ValueError: 단계가 범위를 벗어나거나 id가 중복되면.
        """
        return cls(
            Question(
                id=item["id"],
                stage=item["stage"],
                text=item["text"],
                priority=item["priority"],
                tags=tuple(item.get("tags") or ()),
                source_chunk_ids=tuple(item.get("source_chunk_ids") or ()),
            )
            for item in raw
        )

    def __len__(self) -> int:
        return len(self._questions)

    def by_id(self, question_id: str) -> Question | None:
        """id로 질문을 찾는다.

        Args:
            question_id: 찾을 질문의 id.

        Returns:
            해당 Question. 없으면 None.
        """
        return self._by_id.get(question_id)

    def tags(self) -> list[str]:
        """풀 전체의 태그 어휘를 단계·우선순위 순으로 돌려준다.

        툴 선언의 파라미터 enum에 실린다. Live 커넥션 하나가 여러 단계에
        걸쳐 유지되고 툴 선언은 커넥션을 열 때 한 번 실리므로, enum은
        현재 단계가 아니라 풀 전체 어휘여야 한다.

        Returns:
            중복을 제거한 태그 목록.
        """
        ordered = sorted(
            self._questions, key=lambda question: (question.stage, question.priority)
        )
        return list(dict.fromkeys(tag for question in ordered for tag in question.tags))

    def tags_for(self, stage: int) -> list[str]:
        """해당 단계 질문들에 붙은 태그를 우선순위 순으로 돌려준다.

        질문을 배달할 때 진행 안내(note)에 실어 다음 선택지를 좁혀 준다.

        Args:
            stage: 단계 인덱스(0~3). 범위를 벗어나면 빈 목록.

        Returns:
            중복을 제거한 태그 목록.
        """
        ordered = sorted(
            (question for question in self._questions if question.stage == stage),
            key=lambda question: question.priority,
        )
        return list(dict.fromkeys(tag for question in ordered for tag in question.tags))

    def next(
        self,
        stage: int,
        tag: str | None = None,
        exclude: Collection[str] = (),
    ) -> Question | None:
        """해당 단계에서 아직 내지 않은 질문 하나를 고른다.

        태그가 주어지면 그 주제의 질문을 우선하고, 없으면 같은 단계의 다음
        우선순위 질문으로 대체한다. 모델이 잘못된 태그를 넣어도 면접이 멈추지
        않게 하기 위해서다. 단계 경계는 태그보다 우선한다.

        Args:
            stage: 단계 인덱스(0~3). 범위를 벗어나면 None.
            tag: 원하는 주제 태그. None이면 우선순위만 본다.
            exclude: 이미 낸 질문 id 모음.

        Returns:
            선택된 Question. 남은 질문이 없으면 None.
        """
        available = [
            question
            for question in self._questions
            if question.stage == stage and question.id not in exclude
        ]
        if not available:
            return None

        if tag:
            tagged = [question for question in available if tag in question.tags]
            if tagged:
                available = tagged

        return min(available, key=lambda question: question.priority)
