"""필러 재생 — 게이트 판정·풀 선택·로테이션·등록 수명.

클립 파일은 대역으로 바꾼다(`_clips` monkeypatch) — 테스트는 재생될 바이트가
아니라 언제·어느 것이 나가는지를 본다.
"""

import asyncio
from types import SimpleNamespace

import pytest
from conftest import ContextStub

from daedam.server import fillers
from interviewer.tools import (
    STATE_ANSWER_MARKER,
    STATE_ASKED,
    STATE_PROBES,
    STATE_PROBES_FOR,
    STATE_STAGE,
)

_CARD = "card-1"


@pytest.fixture(autouse=True)
def stub_clips(monkeypatch):
    """모든 풀 이름에 가짜 PCM을 준다. 파일 시스템을 읽지 않는다."""
    names = fillers._ACCEPT_POOL + fillers._DEFAULT_POOL
    monkeypatch.setattr(
        fillers, "_clips", lambda: {name: name.encode() for name in names}
    )
    yield
    fillers._connections.clear()


def _extraction_pending_context(answer: str = "저는 이렇게 했습니다.") -> ContextStub:
    """뼈대질문 답변이 쌓였고 파볼 곳은 아직 안 뽑은 상태 — 추출 직전."""
    context = ContextStub(
        state={
            STATE_ASKED: ["q1"],
            STATE_PROBES: [],
            STATE_PROBES_FOR: "q1",
            STATE_ANSWER_MARKER: 0,
            STATE_STAGE: 1,
        },
        said=[answer],
    )
    context.session.id = _CARD
    return context


def _sent(context: ContextStub, tool_name: str = "ask_question") -> list[bytes]:
    """콜백을 한 번 돌리고, 이 커넥션으로 나간 클립 바이트를 돌려준다."""
    sent: list[bytes] = []

    async def send(data: bytes) -> None:
        sent.append(data)

    connection = fillers.register(_CARD, send)
    asyncio.run(
        fillers.play_filler_before_tool(
            SimpleNamespace(name=tool_name), {}, context
        )
    )
    fillers.unregister(_CARD, connection)
    return sent


def test_추출_호출이면_클립이_나간다():
    assert _sent(_extraction_pending_context()) == [b"jal-deureosseumnida"]


def test_다른_툴이면_안_나간다():
    assert _sent(_extraction_pending_context(), tool_name="search_knowledge") == []


def test_오프닝_호출에는_안_나간다():
    # 아직 낸 질문이 없다 — 인사 전에 "잘 들었습니다"가 나가면 안 된다.
    context = _extraction_pending_context()
    context.state[STATE_ASKED] = []
    assert _sent(context) == []


def test_파볼_곳이_열려_있으면_안_나간다():
    # probe 신고 호출 — 추출이 없는 빠른 호출이다.
    context = _extraction_pending_context()
    context.state[STATE_PROBES] = [
        {"topic": "t", "hint": "h", "status": "open", "asked": True, "attempts": 0}
    ]
    assert _sent(context) == []


def test_마무리_단계에는_안_나간다():
    context = _extraction_pending_context()
    context.state[STATE_STAGE] = 3
    assert _sent(context) == []


def test_답변이_없으면_안_나간다():
    context = _extraction_pending_context()
    context.session.events.clear()
    assert _sent(context) == []


def test_등록이_없으면_안_나간다():
    context = _extraction_pending_context()
    asyncio.run(
        fillers.play_filler_before_tool(SimpleNamespace(name="ask_question"), {}, context)
    )
    # 보낼 곳이 없을 뿐 예외 없이 지나가야 한다.


def test_모르겠다는_답변에는_수용_풀이_나간다():
    context = _extraction_pending_context(
        answer="정확한 수치는 지금 잘 기억이 안 납니다."
    )
    assert _sent(context) == [b"gwaenchanseumnida"]


def test_모르겠다는_판정은_꼬리만_본다():
    # 중간에 "몰랐다"가 나와도 끝에서 제대로 답했으면 기본 풀이다.
    context = _extraction_pending_context(
        answer="처음에는 원인을 잘 모르겠어서 헤맸는데, 결국 로그 수집 주기 문제로"
        " 확인해서 배포 지연을 30% 줄였습니다. 지표로도 검증했습니다."
    )
    assert _sent(context) == [b"jal-deureosseumnida"]


def test_같은_풀에서_돌아가며_나간다():
    sent: list[bytes] = []

    async def send(data: bytes) -> None:
        sent.append(data)

    connection = fillers.register(_CARD, send)
    for _ in range(3):
        asyncio.run(
            fillers.play_filler_before_tool(
                SimpleNamespace(name="ask_question"), {}, _extraction_pending_context()
            )
        )
    fillers.unregister(_CARD, connection)
    assert sent == [b"jal-deureosseumnida", b"ne-geureokunyo", b"geureokunyo"]
    assert len(set(sent)) == 3


def test_전송_실패는_삼킨다():
    async def send(data: bytes) -> None:
        raise RuntimeError("소켓 닫힘")

    connection = fillers.register(_CARD, send)
    asyncio.run(
        fillers.play_filler_before_tool(
            SimpleNamespace(name="ask_question"), {}, _extraction_pending_context()
        )
    )
    fillers.unregister(_CARD, connection)


def test_해제는_내_등록일_때만():
    # 재접속이 먼저 등록한 뒤 이전 커넥션이 정리되는 순서 — 새 등록이 남아야 한다.
    async def send(data: bytes) -> None:
        pass

    old = fillers.register(_CARD, send)
    new = fillers.register(_CARD, send)
    fillers.unregister(_CARD, old)
    assert fillers._connections[_CARD] is new
    fillers.unregister(_CARD, new)
    assert _CARD not in fillers._connections
