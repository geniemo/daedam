"""리서치 서비스 테스트.

fixture는 가짜 시계로 진행을 검증하고, live는 대역 클라이언트로 요청 구성과
상태 매핑만 검증한다. 실제 Deep Research는 작업당 $1~7이라 절대 호출하지
않는다.
"""

import json
import time
from types import SimpleNamespace

from daedam.research.service import FixtureResearch, LiveResearch, research_prompt


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
    def __init__(self, interaction: SimpleNamespace, events: list | None = None) -> None:
        self.interaction = interaction
        self.events = events or []
        self.created_with: dict | None = None

    def create(self, **kwargs) -> SimpleNamespace:
        self.created_with = kwargs
        return self.interaction

    def get(self, id: str = "", stream: bool = False, **_):  # noqa: A002 — genai 시그니처
        # stream=True면 이벤트 목록을 돌려준다. 조사 서술은 이 경로로만 온다.
        return list(self.events) if stream else self.interaction


def _settle(condition, timeout_s: float = 2.0) -> None:
    """스트림은 별도 스레드가 소비한다. 조건이 참이 될 때까지 잠깐 기다린다."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline and not condition():
        time.sleep(0.01)


def _live(
    interaction: SimpleNamespace, clock: _Clock, events: list | None = None
) -> tuple[LiveResearch, _StubInteractions]:
    stub = _StubInteractions(interaction, events)
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


def test_live_진행중은_퍼센트를_지어내지_않는다() -> None:
    """Deep Research는 진행률을 주지 않는다. 경과 시간으로 나눈 숫자를
    진행률이라 부르면 화면이 매 회차 어긋난 값을 보여준다."""
    clock = _Clock()
    interaction = SimpleNamespace(id="itx-1", status="in_progress", steps=None)
    service, _ = _live(interaction, clock)
    task_id = service.start("A", "B", [])

    clock.now = 20 * 60
    status = service.status(task_id)
    assert status.state == "running"
    assert status.pct is None
    assert status.elapsed_s == 20 * 60
    assert status.phase == "자료 조사 중"


def test_live_단계는_스텝에서_읽는다() -> None:
    """model_output이 나타났다는 것은 조사를 마치고 쓰기 시작했다는 뜻이다."""
    clock = _Clock()
    writing = SimpleNamespace(
        id="itx-1",
        status="in_progress",
        steps=[SimpleNamespace(type="model_output", content=[])],
    )
    service, _ = _live(writing, clock)
    task_id = service.start("A", "B", [])
    assert service.status(task_id).phase == "리포트 작성 중"


def test_live_대기열에_있으면_그렇게_말한다() -> None:
    clock = _Clock()
    queued = SimpleNamespace(id="itx-1", status="queued", steps=None)
    service, _ = _live(queued, clock)
    task_id = service.start("A", "B", [])
    assert service.status(task_id).phase == "차례를 기다리는 중"


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


# ── 진행 중 조사 내용 (§2 실시간 진행 표시) ──────────────────────────


def _searching(*steps: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(id="itx-1", status="in_progress", steps=list(steps))


def _search(*queries: str) -> SimpleNamespace:
    return SimpleNamespace(
        type="google_search_call", arguments=SimpleNamespace(queries=list(queries))
    )


def test_live_생각_요약을_켜고_시작한다() -> None:
    """끄면 완료 응답에 user_input과 model_output만 남아 보여줄 사실이 없다."""
    service, stub = _live(SimpleNamespace(id="itx-1", status="queued", steps=None), _Clock())
    service.start("A", "B", [])
    assert stub.created_with["agent_config"]["thinking_summaries"] == "auto"


def _delta(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        data=SimpleNamespace(
            event_type="step.delta",
            delta=SimpleNamespace(content=SimpleNamespace(text=text)),
        )
    )


def test_live_조사_서술은_스트림으로_들어온다() -> None:
    """폴링은 완료 전까지 user_input 하나만 준다 — 실측. 서술은 스트림에만 있다."""
    events = [
        SimpleNamespace(data=SimpleNamespace(event_type="interaction.created")),
        _delta("***Generating research plan***\n\nTo best answer your request..."),
        _delta("\n\n**Defining the Scope of Base Technology**\n\nI am currently..."),
    ]
    service, _ = _live(
        SimpleNamespace(id="itx-1", status="in_progress", steps=None), _Clock(), events
    )
    task_id = service.start("SK하이닉스", "기반기술", [])
    _settle(lambda: len(service.status(task_id).activity) == 2)
    assert service.status(task_id).activity == (
        "Generating research plan",
        "Defining the Scope of Base Technology",
    )


def test_live_같은_제목이_두_번_와도_한_줄이다() -> None:
    events = [_delta("**Mapping Technical Competencies**\n\n앞"), _delta("**Mapping Technical Competencies**\n\n뒤")]
    service, _ = _live(
        SimpleNamespace(id="itx-1", status="in_progress", steps=None), _Clock(), events
    )
    task_id = service.start("A", "B", [])
    _settle(lambda: len(service.status(task_id).activity) == 1)
    assert service.status(task_id).activity == ("Mapping Technical Competencies",)


def test_live_스트림이_비면_조사_목록도_비어_있다() -> None:
    """단계를 지어내지 않는다 — 그게 미리 적어둔 5단계가 하던 일이다."""
    service, _ = _live(SimpleNamespace(id="itx-1", status="in_progress", steps=None), _Clock())
    task_id = service.start("A", "B", [])
    assert service.status(task_id).activity == ()


def test_fixture는_검색어를_지어내지_않는다() -> None:
    clock = _Clock()
    service = FixtureResearch(duration_s=10.0, clock=clock)
    task_id = service.start("A", "B", [])
    clock.now = 5.0
    (line,) = service.status(task_id).activity
    assert "fixture" in line


# ── 재시작을 넘기는 작업 기록 (데모 직전 재기동 대비) ────────────────


def test_인터랙션_id를_파일에_남긴다(tmp_path) -> None:
    state = tmp_path / "_research_tasks.json"
    interaction = SimpleNamespace(id="itx-42", status="in_progress", steps=None)
    stub = _StubInteractions(interaction)
    service = LiveResearch(
        client=SimpleNamespace(interactions=stub), clock=_Clock(), state_path=state
    )
    task_id = service.start("컬리", "서비스기획", [])

    saved = json.loads(state.read_text(encoding="utf-8"))
    assert saved[task_id]["interaction_id"] == "itx-42"


def test_재시작해도_돌던_리서치를_이어받는다(tmp_path) -> None:
    """이 기록이 없으면 20~60분짜리 리서치가 재기동 한 번에 사라진다."""
    state = tmp_path / "_research_tasks.json"
    interaction = SimpleNamespace(id="itx-42", status="in_progress", steps=None)
    stub = _StubInteractions(interaction)
    clock = _Clock()
    first = LiveResearch(
        client=SimpleNamespace(interactions=stub), clock=clock, state_path=state
    )
    task_id = first.start("컬리", "서비스기획", [])

    # 서버 재기동 — 새 인스턴스는 메모리를 물려받지 못한다.
    revived = LiveResearch(
        client=SimpleNamespace(interactions=stub), clock=clock, state_path=state
    )
    clock.now = 20 * 60
    status = revived.status(task_id)
    assert status is not None and status.state == "running"
    assert status.elapsed_s == 20 * 60  # 시작 시각이 파일에서 복원됐다


def test_기록_파일이_깨져도_기동은_된다(tmp_path) -> None:
    state = tmp_path / "_research_tasks.json"
    state.write_text("{망가진 JSON", encoding="utf-8")
    service = LiveResearch(
        client=SimpleNamespace(interactions=_StubInteractions(None)),
        clock=_Clock(),
        state_path=state,
    )
    assert service.status("아무거나") is None


def test_기록이_없으면_아무것도_모른다() -> None:
    service = LiveResearch(
        client=SimpleNamespace(interactions=_StubInteractions(None)), clock=_Clock()
    )
    assert service.status("itx-없음") is None


# ── 채용공고 반영 ────────────────────────────────────────────────


def test_직무에_신입이_들어_있어도_신입을_덧붙이지_않는다() -> None:
    prompt = research_prompt("컬리", "서비스기획 · 신입", [])
    assert "서비스기획 · 신입 채용 면접" in prompt
    assert "직무 신입 채용" not in prompt


def test_채용공고를_주면_프롬프트에_그대로_실린다() -> None:
    """파싱하지 않는다. 링크면 에이전트가 열어 보고 본문이면 본문대로 읽는다."""
    posting = "https://career.kurly.com/o/12345"
    prompt = research_prompt("컬리", "서비스기획", [], posting)
    assert posting in prompt
    assert "이 공고를 우선 근거로" in prompt


def test_채용공고가_없으면_그_문단도_없다() -> None:
    prompt = research_prompt("컬리", "서비스기획", [], "   ")
    assert "우선 근거로" not in prompt


def test_채용공고가_리서치_요청에_실린다() -> None:
    interaction = SimpleNamespace(id="itx-1", status="queued", steps=None)
    service, stub = _live(interaction, _Clock())
    service.start("컬리", "서비스기획", [], "https://career.kurly.com/o/12345")
    assert "https://career.kurly.com/o/12345" in stub.created_with["input"]


# ── 스트림이 끊겨도 다시 붙는다 ──────────────────────────────────


class _BreakingInteractions(_StubInteractions):
    """첫 스트림은 도중에 끊기고, 두 번째부터는 이어서 준다."""

    def __init__(self, interaction, first, rest) -> None:
        super().__init__(interaction)
        self._first = first
        self._rest = rest
        self.stream_calls: list[str | None] = []

    def get(self, id: str = "", stream: bool = False, last_event_id=None, **_):  # noqa: A002
        if not stream:
            return self.interaction
        self.stream_calls.append(last_event_id)
        if len(self.stream_calls) == 1:
            def broken():
                yield from self._first
                raise RuntimeError("연결이 끊겼습니다")
            return broken()
        return list(self._rest)


def _delta_with_id(text: str, event_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        data=SimpleNamespace(
            event_type="step.delta",
            event_id=event_id,
            delta=SimpleNamespace(content=SimpleNamespace(text=text)),
        )
    )


def test_스트림이_끊기면_끊긴_지점부터_다시_붙는다(monkeypatch) -> None:
    """40분짜리 작업에서 한 번의 끊김으로 포기하면 나머지 서술을 통째로 잃는다."""
    monkeypatch.setattr("daedam.research.service._STREAM_BACKOFF_S", 0.0)
    stub = _BreakingInteractions(
        SimpleNamespace(id="itx-1", status="in_progress", steps=None),
        first=[_delta_with_id("**첫 단계**\n\n본문", "e1")],
        rest=[
            _delta_with_id("**둘째 단계**\n\n본문", "e2"),
            SimpleNamespace(data=SimpleNamespace(event_type="interaction.completed")),
        ],
    )
    service = LiveResearch(client=SimpleNamespace(interactions=stub), clock=_Clock())
    task_id = service.start("A", "B", [])

    _settle(lambda: len(service.status(task_id).activity) == 2)
    assert service.status(task_id).activity == ("첫 단계", "둘째 단계")
    # 두 번째 연결은 마지막으로 받은 event_id에서 이어받는다.
    assert stub.stream_calls == [None, "e1"]


def test_완료_이벤트를_보면_다시_붙지_않는다(monkeypatch) -> None:
    """완료된 인터랙션도 전체를 재생해 주므로, 안 멈추면 영원히 다시 받는다."""
    monkeypatch.setattr("daedam.research.service._STREAM_BACKOFF_S", 0.0)
    stub = _BreakingInteractions(
        SimpleNamespace(id="itx-1", status="in_progress", steps=None),
        first=[],
        rest=[],
    )
    stub.stream_calls = []

    events = [
        _delta_with_id("**단계**\n\n본문", "e1"),
        SimpleNamespace(data=SimpleNamespace(event_type="interaction.completed")),
    ]
    calls = {"n": 0}

    def get(id: str = "", stream: bool = False, last_event_id=None, **_):  # noqa: A002
        if not stream:
            return stub.interaction
        calls["n"] += 1
        return list(events)

    stub.get = get  # type: ignore[method-assign]
    service = LiveResearch(client=SimpleNamespace(interactions=stub), clock=_Clock())
    task_id = service.start("A", "B", [])
    _settle(lambda: len(service.status(task_id).activity) == 1)
    time.sleep(0.05)
    assert calls["n"] == 1
