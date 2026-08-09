"""뼈대질문 풀 테스트.

풀은 세션 시작 전에 오프라인에서 초과 생성된다. 런타임에는 조회만 하며,
**한 번에 질문 하나만** 돌려준다 — 고르지 않은 후보가 대화 컨텍스트에 쌓이는
것을 막기 위해서다. 모델의 선택은 태그로 표현된다.
"""

import pytest

from daedam.interview.question_pool import Question, QuestionPool

RAW = [
    # 자기소개(0)
    {"id": "q-0-1", "stage": 0, "text": "간단히 자기소개 부탁드립니다.", "priority": 1,
     "tags": ["자기소개"]},
    {"id": "q-0-2", "stage": 0, "text": "저희에 지원하신 이유가 무엇인가요?", "priority": 2,
     "tags": ["지원동기", "회사이해"], "source_chunk_ids": ["blk-1-0"]},
    # 직무역량(1) — 우선순위를 일부러 뒤섞어 둔다
    {"id": "q-1-2", "stage": 1, "text": "가장 어려웠던 판단은 무엇이었나요?", "priority": 5,
     "tags": ["문제해결"], "source_chunk_ids": ["app-0-0"]},
    {"id": "q-1-1", "stage": 1, "text": "물류 프로젝트에서 맡은 역할을 설명해 주세요.", "priority": 1,
     "tags": ["경험상세"], "source_chunk_ids": ["app-0-0", "blk-4-0"]},
    {"id": "q-1-3", "stage": 1, "text": "SQL을 어느 수준까지 쓰시나요?", "priority": 3,
     "tags": ["기술역량"]},
    # 마무리(3)
    {"id": "q-3-1", "stage": 3, "text": "마지막으로 하고 싶은 말씀이 있으신가요?", "priority": 1,
     "tags": ["역질문"]},
]


@pytest.fixture
def pool() -> QuestionPool:
    return QuestionPool.from_dicts(RAW)


# ── 로딩 ─────────────────────────────────────────────────────────────────


def test_dict에서_풀을_만든다(pool: QuestionPool) -> None:
    assert len(pool) == 6


def test_근거_청크_id를_보존한다(pool: QuestionPool) -> None:
    """원칙 3 — 질문과 함께 근거를 배달해야 런타임 검색이 줄어든다."""
    question = pool.by_id("q-1-1")
    assert question is not None
    assert question.source_chunk_ids == ("app-0-0", "blk-4-0")


def test_태그와_근거가_없어도_로딩된다() -> None:
    minimal = QuestionPool.from_dicts([{"id": "x", "stage": 0, "text": "?", "priority": 1}])
    question = minimal.by_id("x")
    assert question is not None
    assert question.tags == () and question.source_chunk_ids == ()


def test_없는_id는_None(pool: QuestionPool) -> None:
    assert pool.by_id("존재하지 않음") is None


def test_단계가_범위를_벗어나면_로딩에서_실패한다() -> None:
    """런타임이 아니라 로딩 시점에 잡는다."""
    with pytest.raises(ValueError, match="단계"):
        QuestionPool.from_dicts([{"id": "x", "stage": 9, "text": "?", "priority": 1}])


def test_id가_중복되면_로딩에서_실패한다() -> None:
    dup = [
        {"id": "same", "stage": 0, "text": "a", "priority": 1},
        {"id": "same", "stage": 1, "text": "b", "priority": 1},
    ]
    with pytest.raises(ValueError, match="중복"):
        QuestionPool.from_dicts(dup)


# ── 질문 선택 ────────────────────────────────────────────────────────────


def test_한_번에_질문_하나만_돌려준다(pool: QuestionPool) -> None:
    """고르지 않은 후보가 대화 컨텍스트에 쌓이면 안 된다."""
    assert isinstance(pool.next(stage=1), Question)


def test_태그를_안_주면_우선순위가_가장_높은_질문(pool: QuestionPool) -> None:
    question = pool.next(stage=1)
    assert question is not None and question.id == "q-1-1"


def test_태그로_원하는_주제의_질문을_고른다(pool: QuestionPool) -> None:
    question = pool.next(stage=1, tag="문제해결")
    assert question is not None and question.id == "q-1-2"


def test_태그가_여러_개인_질문도_걸린다(pool: QuestionPool) -> None:
    question = pool.next(stage=0, tag="회사이해")
    assert question is not None and question.id == "q-0-2"


def test_이미_낸_질문은_다시_주지_않는다(pool: QuestionPool) -> None:
    question = pool.next(stage=1, exclude={"q-1-1"})
    assert question is not None and question.id == "q-1-3"


def test_요청한_태그가_없으면_우선순위로_대체한다(pool: QuestionPool) -> None:
    """모델이 엉뚱한 태그를 넣어도 면접이 멈추면 안 된다."""
    question = pool.next(stage=1, tag="그런태그없음")
    assert question is not None and question.id == "q-1-1"


def test_해당_단계_밖의_질문은_절대_주지_않는다(pool: QuestionPool) -> None:
    """태그가 다른 단계에 있어도 단계 경계를 넘지 않는다."""
    question = pool.next(stage=3, tag="경험상세")
    assert question is not None and question.stage == 3


def test_질문이_없는_단계는_None(pool: QuestionPool) -> None:
    assert pool.next(stage=2) is None


def test_범위_밖_단계는_예외_대신_None(pool: QuestionPool) -> None:
    """면접 중 조회는 어떤 입력에도 죽지 않아야 한다."""
    assert pool.next(stage=99) is None


def test_모두_소진하면_None(pool: QuestionPool) -> None:
    assert pool.next(stage=1, exclude={"q-1-1", "q-1-2", "q-1-3"}) is None


# ── 태그 어휘 ────────────────────────────────────────────────────────────


def test_풀_전체_태그를_단계와_우선순위_순으로_모은다(pool: QuestionPool) -> None:
    """툴 선언의 파라미터 enum에 그대로 실리는 어휘다."""
    assert pool.tags() == [
        "자기소개", "지원동기", "회사이해", "경험상세", "기술역량", "문제해결", "역질문",
    ]


def test_단계별_태그를_우선순위_순으로_모은다(pool: QuestionPool) -> None:
    """질문을 배달할 때 진행 안내(note)에 실려 다음 선택지를 좁힌다."""
    assert pool.tags_for(1) == ["경험상세", "기술역량", "문제해결"]


def test_같은_태그는_한_번만_나온다() -> None:
    dup = QuestionPool.from_dicts([
        {"id": "a", "stage": 0, "text": "?", "priority": 1, "tags": ["협업"]},
        {"id": "b", "stage": 0, "text": "?", "priority": 2, "tags": ["협업", "갈등해결"]},
    ])
    assert dup.tags() == ["협업", "갈등해결"]


def test_질문이_없는_단계의_태그는_빈_목록(pool: QuestionPool) -> None:
    assert pool.tags_for(2) == []


# ── 직렬화 ───────────────────────────────────────────────────────────────


def test_질문은_모델에게_넘길_형태로_직렬화된다(pool: QuestionPool) -> None:
    """근거 청크 id와 우선순위는 서버 내부용이라 노출하지 않는다."""
    result = pool.by_id("q-1-1").as_result()  # type: ignore[union-attr]
    assert result == {"id": "q-1-1", "text": "물류 프로젝트에서 맡은 역할을 설명해 주세요."}


def test_Question은_불변이다() -> None:
    question = Question(id="q", stage=0, text="t", priority=1)
    with pytest.raises(Exception):
        question.text = "바꿀 수 없음"  # type: ignore[misc]
