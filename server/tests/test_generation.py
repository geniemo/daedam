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
    """생성 대상 단계(1·2)의 최소 개수(3/3)를 딱 맞춘 유효 응답."""
    per_stage = {1: 3, 2: 3}
    return [_question(stage) for stage, count in per_stage.items() for _ in range(count)]


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
    assert len(pool) == 10  # 고정 자기소개 2 + 생성 6 + 고정 마무리 2
    assert raw[0]["id"] == "q-open-0" and raw[2]["id"] == "q-1-0"


def test_자기소개와_마무리는_고정_질문이_채운다() -> None:
    """자료를 근거로 만들 것이 없는 단계는 생성하지 않는다. 역질문 유도는
    에이전트 몫이라 마무리에도 없다."""
    raw = _generate(_minimum_pool())
    openers = [q for q in raw if q["stage"] == 0]
    closers = [q for q in raw if q["stage"] == 3]
    assert [q["id"] for q in openers] == ["q-open-0", "q-open-1"]
    assert [q["id"] for q in closers] == ["q-close-0", "q-close-1"]
    assert "자기소개" in openers[0]["tags"] and "지원 동기" in openers[1]["tags"]
    assert "입사 포부" in closers[0]["tags"]


def test_여는_질문은_자기소개가_먼저다() -> None:
    """중요도가 순서를 정한다 — 지원 동기보다 자기소개가 앞이다."""
    raw = _generate(_minimum_pool())
    openers = [q for q in raw if q["stage"] == 0]
    assert openers[0]["priority"] < openers[1]["priority"]


def test_고정_질문의_중요도가_척도_안에_있다() -> None:
    """면접 중 모델이 매기는 값과 같은 자로 비교되므로 1~5를 벗어나면 안 된다."""
    raw = _generate(_minimum_pool())
    fixed = [q for q in raw if q["stage"] in (0, 3)]
    assert all(1 <= q["priority"] <= 5 for q in fixed)
    # 마무리 문항은 합격 판단을 가르지 않는다 — 여는 문항보다 뒤다.
    assert max(q["priority"] for q in fixed if q["stage"] == 0) < min(
        q["priority"] for q in fixed if q["stage"] == 3
    )


def test_유효한_근거_인용은_보존된다() -> None:
    questions = _minimum_pool()
    questions[0] = _question(1, ids=["blk-1-0", "app-0-0"])
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
    assert "- 1 직무역량: 5개" in prompt and "- 2 인성·컬처핏: 6개" in prompt
    # 생성 대상이 아닌 단계는 지시에 등장하지 않는다 — 구조로 이미 막혀 있다.
    # ("자기소개"는 지원서 청크 제목에 있을 수 있으므로 단계 표기로 확인한다.)
    assert "0 자기소개" not in prompt and "마무리" not in prompt


# ── 검증 실패 경로 — 오프라인 배치는 크게 실패해야 한다 ──────────────────


def test_실존하지_않는_근거_id는_실패한다() -> None:
    questions = _minimum_pool()
    questions[0] = _question(1, ids=["blk-99-99"])
    with pytest.raises(ValueError, match="실존하지 않는 근거"):
        _generate(questions)


def test_단계_최소_개수_미달은_실패한다() -> None:
    with pytest.raises(ValueError, match="부족"):
        _generate(_minimum_pool()[:-1])  # 인성·컬처핏 1개 부족


@pytest.mark.parametrize("stage", [0, 3])
def test_생성_대상_밖_단계는_실패한다(stage: int) -> None:
    """자기소개(0)와 마무리(3)는 고정 질문 영역 — 만들어 오면 거부한다."""
    questions = _minimum_pool() + [_question(stage)]
    with pytest.raises(ValueError, match="생성 대상이 아닌 단계"):
        _generate(questions)


@pytest.mark.parametrize("priority", [0, 6])
def test_척도를_벗어난_중요도는_실패한다(priority: int) -> None:
    """면접 중 문턱 계산이 이 값을 그대로 쓴다 — 범위를 벗어나면 판정이 깨진다."""
    questions = _minimum_pool()
    questions[0] = _GeneratedQuestion(
        stage=1, text="질문?", priority=priority, tags=["태그"], source_chunk_ids=[]
    )
    with pytest.raises(ValueError, match="1~5를 벗어남"):
        _generate(questions)


def test_같은_중요도가_겹쳐도_통과한다() -> None:
    """순서 번호가 아니라 기여도다 — 실제로 같은 무게인 질문이 있을 수 있다."""
    raw = _generate(_minimum_pool())
    assert len([q for q in raw if q["stage"] == 1]) == 3


def test_태그_없는_질문은_실패한다() -> None:
    questions = _minimum_pool()
    questions[0] = _GeneratedQuestion(
        stage=1, text="질문?", priority=1, tags=[], source_chunk_ids=[]
    )
    with pytest.raises(ValueError, match="태그"):
        _generate(questions)
