"""질문 풀 생성 테스트.

Grok은 대역 클라이언트로 바꾼다(실호출 0회) — 여기서 검증하는 건 프롬프트
조립과 결과 검증 로직이다. 생성 품질 자체는 실호출 검토(프롬프트 튜닝
루프)가 맡는다.
"""

from types import SimpleNamespace

import pytest

from daedam.interview.generation import (
    _GeneratedPool,
    _GeneratedQuestion,
    generate_question_pool,
    generation_prompt,
)
from daedam.interview.question_pool import QuestionPool
from daedam.knowledge.chunk import Chunk

REPORT_CHUNKS = [
    Chunk(id="blk-1-0", source="research", title="주력 사업", text="배차 자동화로 공차 거리를 18% 줄였다."),
]
APPLICATION_CHUNKS = [
    Chunk(id="app-0-0", source="application", title="자기소개서 · 프로젝트 경험", text="배송 시간을 22% 단축했다."),
]


def _question(stage: int, text: str = "질문?", ids: list[str] | None = None) -> _GeneratedQuestion:
    return _GeneratedQuestion(
        stage=stage, text=text, priority=1, tags=["태그"], source_chunk_ids=ids or []
    )


def _minimum_pool() -> list[_GeneratedQuestion]:
    """생성 대상 단계(0~2)의 최소 개수(2/3/2)를 딱 맞춘 유효 응답."""
    per_stage = (2, 3, 2)
    return [_question(stage) for stage, count in enumerate(per_stage) for _ in range(count)]


class _StubClient:
    """parse 호출을 기록하고 정해둔 응답을 돌려주는 대역."""

    def __init__(self, questions: list[_GeneratedQuestion]) -> None:
        self.kwargs: dict = {}

        def parse(**kwargs):
            self.kwargs = kwargs
            message = SimpleNamespace(parsed=_GeneratedPool(questions=questions))
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

        self.beta = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(parse=parse))
        )


def _generate(questions: list[_GeneratedQuestion]) -> list[dict]:
    return generate_question_pool(
        company="한결물류",
        role="데이터 엔지니어",
        report_chunks=REPORT_CHUNKS,
        application_chunks=APPLICATION_CHUNKS,
        client=_StubClient(questions),
    )


# ── 정상 경로 ────────────────────────────────────────────────────────────


def test_생성_결과가_풀_입력_형태가_된다() -> None:
    raw = _generate(_minimum_pool())
    pool = QuestionPool.from_dicts(raw)
    assert len(pool) == 9  # 생성 7 + 고정 마무리 2
    assert raw[0]["id"] == "q-0-0" and raw[2]["id"] == "q-1-0"


def test_마무리는_생성하지_않고_고정_질문을_붙인다() -> None:
    """정형화된 마무리는 자체 질문을 쓴다. 역질문 유도는 에이전트 몫이라 없다."""
    raw = _generate(_minimum_pool())
    closers = [question for question in raw if question["stage"] == 3]
    assert [c["id"] for c in closers] == ["q-3-0", "q-3-1"]
    assert "입사 포부" in closers[0]["tags"]


def test_유효한_근거_인용은_보존된다() -> None:
    questions = _minimum_pool()
    questions[2] = _question(1, ids=["blk-1-0", "app-0-0"])
    raw = _generate(questions)
    assert raw[2]["source_chunk_ids"] == ["blk-1-0", "app-0-0"]


def test_프롬프트에_회사와_청크가_id와_함께_실린다() -> None:
    stub = _StubClient(_minimum_pool())
    generate_question_pool(
        company="한결물류",
        role="데이터 엔지니어",
        report_chunks=REPORT_CHUNKS,
        application_chunks=APPLICATION_CHUNKS,
        client=stub,
    )
    prompt = stub.kwargs["messages"][0]["content"]
    assert "한결물류" in prompt and "데이터 엔지니어" in prompt
    assert "(blk-1-0)" in prompt and "공차 거리를 18%" in prompt
    assert "(app-0-0)" in prompt


def test_프롬프트는_생성_대상_단계만_명시한다() -> None:
    prompt = generation_prompt(
        company="A", role="B",
        report_chunks=REPORT_CHUNKS, application_chunks=APPLICATION_CHUNKS,
    )
    assert "- 0 자기소개: 3개" in prompt and "- 2 인성·컬처핏: 4개" in prompt
    assert "마무리" not in prompt  # 생성 대상이 아닌 단계는 언급하지 않는다


# ── 검증 실패 경로 — 오프라인 배치는 크게 실패해야 한다 ──────────────────


def test_실존하지_않는_근거_id는_실패한다() -> None:
    questions = _minimum_pool()
    questions[0] = _question(0, ids=["blk-99-99"])
    with pytest.raises(ValueError, match="실존하지 않는 근거"):
        _generate(questions)


def test_단계_최소_개수_미달은_실패한다() -> None:
    with pytest.raises(ValueError, match="부족"):
        _generate(_minimum_pool()[:-1])  # 인성·컬처핏 1개 부족


def test_생성_대상_밖_단계는_실패한다() -> None:
    """마무리(3)는 고정 질문 영역 — 모델이 만들어 오면 거부한다."""
    questions = _minimum_pool() + [_question(3)]
    with pytest.raises(ValueError, match="범위 밖"):
        _generate(questions)


def test_태그_없는_질문은_실패한다() -> None:
    questions = _minimum_pool()
    questions[0] = _GeneratedQuestion(
        stage=0, text="질문?", priority=1, tags=[], source_chunk_ids=[]
    )
    with pytest.raises(ValueError, match="태그"):
        _generate(questions)
