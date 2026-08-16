"""리서치 서비스 테스트.

fixture는 가짜 시계로 진행을 검증하고, live는 대역 클라이언트로 요청 구성과
상태 매핑만 검증한다. 실제 Deep Research는 작업당 $1~7이라 절대 호출하지
않는다.
"""

from types import SimpleNamespace

from daedam.research.service import FixtureResearch, LiveResearch


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


# ── fixture 모드 ─────────────────────────────────────────────────────────


def test_fixture_진행률이_시간에_따라_오른다() -> None:
    clock = _Clock()
    service = FixtureResearch(duration_s=10, clock=clock)
    task_id = service.start("한결물류", "데이터 엔지니어", [])

    assert service.status(task_id).pct == 0
    clock.now = 5
    status = service.status(task_id)
    assert status.state == "running" and status.pct == 50
    clock.now = 10
    status = service.status(task_id)
    assert status.state == "done" and status.pct == 100


def test_fixture_리포트에_회사와_직무가_박힌다() -> None:
    clock = _Clock()
    service = FixtureResearch(duration_s=1, clock=clock)
    task_id = service.start("한결물류", "데이터 엔지니어", [])
    clock.now = 1

    text = str(service.status(task_id).report)
    assert "한결물류" in text and "데이터 엔지니어" in text
    assert "{company}" not in text and "{role}" not in text


def test_fixture_리포트는_화면_리포트_형태다() -> None:
    """프론트 DocSection 계약 — 섹션마다 title·blocks, 블록 type은 넷 중 하나."""
    clock = _Clock()
    service = FixtureResearch(duration_s=1, clock=clock)
    task_id = service.start("A", "B", [])
    clock.now = 1

    status = service.status(task_id)
    for section in status.report:
        assert section["title"] and section["blocks"]
        for block in section["blocks"]:
            assert block["type"] in ("p", "li", "table", "refs")
    assert all({"si", "bi", "title", "reason"} <= set(u) for u in status.uncertain)


def test_없는_task는_None() -> None:
    assert FixtureResearch().status("없는 id") is None


# ── live 모드 (대역) ─────────────────────────────────────────────────────


class _StubInteractions:
    def __init__(self, interaction: SimpleNamespace) -> None:
        self.interaction = interaction
        self.created_with: dict | None = None

    def create(self, **kwargs) -> SimpleNamespace:
        self.created_with = kwargs
        return self.interaction

    def get(self, id: str) -> SimpleNamespace:  # noqa: A002 — genai 시그니처를 따른다
        return self.interaction


def _live(interaction: SimpleNamespace, clock: _Clock) -> tuple[LiveResearch, _StubInteractions]:
    stub = _StubInteractions(interaction)
    client = SimpleNamespace(interactions=stub)
    return LiveResearch(client=client, clock=clock), stub


def test_live_시작은_deep_research를_background로_만든다() -> None:
    interaction = SimpleNamespace(id="itx-1", status="queued", steps=None)
    service, stub = _live(interaction, _Clock())
    service.start("한결물류", "데이터 엔지니어", [{"part": "자소서", "items": [{"title": "지원동기", "body": "..."}]}])

    kwargs = stub.created_with
    assert kwargs["agent"] == "deep-research-preview-04-2026"
    assert kwargs["background"] is True and kwargs["store"] is True
    assert "한결물류" in kwargs["input"] and "지원동기" in kwargs["input"]


def test_live_진행중은_어림_진행률이고_95를_넘지_않는다() -> None:
    clock = _Clock()
    interaction = SimpleNamespace(id="itx-1", status="in_progress", steps=None)
    service, _ = _live(interaction, clock)
    task_id = service.start("A", "B", [])

    clock.now = 20 * 60
    assert service.status(task_id).pct == 50
    clock.now = 100 * 60
    status = service.status(task_id)
    assert status.state == "running" and status.pct == 95


def _completed(*chunks: str) -> SimpleNamespace:
    """리포트를 여러 model_output 스텝에 나눠 담은 완료 응답.

    실제 응답 모양 그대로다 — steps[0]은 우리가 보낸 프롬프트가 되돌아온
    user_input이고, 리포트는 그 뒤 스텝들에 조각으로 실린다.
    """
    steps = [
        SimpleNamespace(type="user_input", content=[SimpleNamespace(text="요청 프롬프트")])
    ]
    steps += [
        SimpleNamespace(type="model_output", content=[SimpleNamespace(text=chunk)])
        for chunk in chunks
    ]
    return SimpleNamespace(id="itx-1", status="completed", steps=steps)


def test_live_완료되면_마크다운이_섹션으로_변환된다() -> None:
    service, _ = _live(_completed("## 회사 개요\n\n본문입니다.\n\n- 항목 하나"), _Clock())
    status = service.status(service.start("A", "B", []))
    assert status.state == "done"
    assert status.report[0]["title"] == "회사 개요"
    assert [b["type"] for b in status.report[0]["blocks"]] == ["p", "li"]


def test_live_여러_조각으로_온_리포트를_모두_잇는다() -> None:
    """Deep Research는 리포트를 스텝 여러 개로 나눠 내보낸다. 마지막 조각만
    쓰면 실측에서 Executive Summary와 1~4장을 통째로 잃었다."""
    service, _ = _live(
        _completed("## 앞 장\n\n앞 본문.", "\n\n## 뒤 장\n\n뒤 본문."), _Clock()
    )
    status = service.status(service.start("A", "B", []))
    assert [s["title"] for s in status.report] == ["앞 장", "뒤 장"]


def test_live_요청_프롬프트는_리포트에_섞이지_않는다() -> None:
    """steps[0]은 우리가 보낸 입력이 되돌아온 것이다."""
    service, _ = _live(_completed("## 회사 개요\n\n본문."), _Clock())
    status = service.status(service.start("A", "B", []))
    assert all("요청 프롬프트" not in s["title"] for s in status.report)


def test_live_실패_상태가_매핑된다() -> None:
    interaction = SimpleNamespace(id="itx-1", status="budget_exceeded", steps=None)
    service, _ = _live(interaction, _Clock())
    task_id = service.start("A", "B", [])
    assert service.status(task_id).state == "failed"
