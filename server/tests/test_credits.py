"""크레딧 — 지급·차감·환불과 막는 자리.

돈이 걸린 코드라 경계를 촘촘히 본다: 잔액이 딱 맞을 때, 하나 모자랄 때,
같은 건을 두 번 되돌릴 때.
"""

from __future__ import annotations

import pytest
from conftest import make_store

from daedam.server.credits import (
    COST_INTERVIEW,
    COST_RESEARCH,
    SIGNUP_GRANT,
    Credits,
    InsufficientCredits,
)


@pytest.fixture
def bundle(tmp_path):
    store, accounts, user_id = make_store(tmp_path / "data")
    return store, accounts.credits, user_id


def test_가입하면_선물을_받는다(bundle) -> None:
    """등록 한 번 + 면접 몇 번을 해 봐야 결제를 판단할 수 있다."""
    _, credits, user_id = bundle
    assert credits.balance(user_id) == SIGNUP_GRANT
    assert SIGNUP_GRANT >= COST_RESEARCH + COST_INTERVIEW


def test_새_사용자에게만_한_번_준다(tmp_path) -> None:
    store, accounts, _ = make_store(tmp_path / "data")
    credits: Credits = accounts.credits
    first = accounts.upsert(provider="kakao", provider_user_id="1", name="박지원")
    again = accounts.upsert(provider="kakao", provider_user_id="1", name="박지원")
    assert first == again
    assert credits.balance(first) == SIGNUP_GRANT


def test_쓰면_줄고_내역이_남는다(bundle) -> None:
    _, credits, user_id = bundle
    credits.charge(user_id, COST_INTERVIEW, "interview", "s1")
    assert credits.balance(user_id) == SIGNUP_GRANT - COST_INTERVIEW
    [latest, *_] = credits.history(user_id)
    assert latest.delta == -COST_INTERVIEW and latest.ref_id == "s1"


def test_잔액이_딱_맞으면_통과하고_하나_모자라면_막는다(tmp_path) -> None:
    _, accounts, user_id = make_store(tmp_path / "data")
    credits: Credits = accounts.credits
    # 잔액을 정확히 2로 만든다.
    credits.charge(user_id, SIGNUP_GRANT, "interview", "비우기")
    credits.grant(user_id, 2, "admin_grant")

    credits.charge(user_id, 2, "interview", "s1")
    assert credits.balance(user_id) == 0
    with pytest.raises(InsufficientCredits) as raised:
        credits.charge(user_id, 1, "interview", "s2")
    assert raised.value.needed == 1 and raised.value.balance == 0
    # 막힌 차감은 원장에 남지 않는다.
    assert credits.balance(user_id) == 0


def test_확인만_하는_ensure는_쓰지_않는다(bundle) -> None:
    """리서치는 시작해야 id가 나오는데 시작하면 취소할 수 없다 — 그 전에 본다."""
    _, credits, user_id = bundle
    credits.ensure(user_id, COST_RESEARCH)
    assert credits.balance(user_id) == SIGNUP_GRANT
    with pytest.raises(InsufficientCredits):
        credits.ensure(user_id, SIGNUP_GRANT + 1)


def test_실패한_건은_되돌리고_두_번_되돌리지_않는다(bundle) -> None:
    """실패한 작업에 요금을 물리면 다시 시도할 수도 없다."""
    _, credits, user_id = bundle
    credits.charge(user_id, COST_RESEARCH, "research", "task-1")
    credits.refund(user_id, "research", "task-1")
    assert credits.balance(user_id) == SIGNUP_GRANT

    credits.refund(user_id, "research", "task-1")  # 두 번째는 아무 일도 없다
    assert credits.balance(user_id) == SIGNUP_GRANT


def test_쓴_적_없는_건은_되돌릴_것이_없다(bundle) -> None:
    _, credits, user_id = bundle
    credits.refund(user_id, "research", "없는건")
    assert credits.balance(user_id) == SIGNUP_GRANT


# ── 라우트에서 막히는가 ─────────────────────────────────────────────────


def test_크레딧이_없으면_등록이_402(tmp_path) -> None:
    """Deep Research는 시작하면 취소할 수 없다 — 시작 전에 막아야 한다."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from daedam.server.preparation import InterviewPreparation
    from daedam.server.preparation_routes import create_preparation_router

    store, accounts, user_id = make_store(tmp_path / "data")
    credits: Credits = accounts.credits
    credits.charge(user_id, SIGNUP_GRANT, "interview", "비우기")

    started: list[str] = []

    class _Research:
        def start(self, company, role, application, posting=""):  # noqa: ANN001
            started.append(company)
            return "task-1"

        def status(self, task_id):  # noqa: ANN001
            return None

    app = FastAPI()
    app.include_router(
        create_preparation_router(
            InterviewPreparation(
                research=_Research(), store=store, generate=lambda **_: []
            ),
            accounts,
            credits,
        )
    )
    response = TestClient(app).post(
        "/api/preparation", json={"company": "한결물류", "role": "데이터"}
    )
    assert response.status_code == 402
    assert response.json()["detail"]["needed"] == COST_RESEARCH
    # 리서치가 시작되지 않았다 — 이것이 이 테스트의 요지다.
    assert started == []


def test_크레딧이_없으면_면접_소켓이_닫힌다(tmp_path) -> None:
    from test_live_bridge import _client, _seeded_store  # noqa: PLC0415

    store = _seeded_store(tmp_path, "card")
    credits: Credits = store.accounts.credits
    user_id = store.accounts.default_user_id()
    credits.charge(user_id, credits.balance(user_id), "interview", "비우기")

    from fastapi.websockets import WebSocketDisconnect

    from test_live_bridge import _FakeRunner  # noqa: PLC0415

    client = _client(_FakeRunner(), store)
    with client.websocket_connect("/ws/interview?card=card") as websocket:
        # 진행 상태(session)를 보내기도 전에 끝난다 — 크레딧 판정이 면접을
        # 여는 것보다 앞이라 화면이 면접 준비를 시작하지 않는다.
        assert websocket.receive_json() == {"type": "ended", "reason": "credits"}
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_bytes()
    # 열다 만 판을 닫아 둔다 — 안 닫으면 다음 접속이 이어받아 공짜 면접이 된다.
    assert store.resume_or_abandon("card", stale_after_s=3600)[0] is None


def test_재접속에는_다시_물리지_않는다(tmp_path) -> None:
    """커넥션 수명이 ~10분이라 15~20분 면접은 반드시 재접속한다. 재접속마다
    물리면 한 판에 요금이 여러 번 나간다."""
    from test_live_bridge import _FakeRunner, _client, _seeded_store  # noqa: PLC0415

    store = _seeded_store(tmp_path, "card")
    credits: Credits = store.accounts.credits
    user_id = store.accounts.default_user_id()
    before = credits.balance(user_id)

    # 앞 커넥션이 열어 둔 면접 한 판 — 끊겼을 뿐 끝나지는 않았다.
    ongoing = store.start_session("card")

    client = _client(_FakeRunner(), store)
    with client.websocket_connect("/ws/interview?card=card") as websocket:
        websocket.receive_json()
        websocket.send_bytes(b"\x00")
        websocket.receive_bytes()

    assert credits.balance(user_id) == before
    # 새 판을 열지도 않았다 — 같은 면접을 이어받았다.
    assert [s.id for s in store.list_sessions("card")] == [ongoing]


def test_새_면접마다_물린다(tmp_path) -> None:
    """앞 판이 끝난 뒤의 접속은 새 면접이다."""
    from test_live_bridge import _FakeRunner, _client, _seeded_store  # noqa: PLC0415

    store = _seeded_store(tmp_path, "card")
    credits: Credits = store.accounts.credits
    user_id = store.accounts.default_user_id()

    client = _client(_FakeRunner(), store)
    for _ in range(2):
        # 대역 러너는 이벤트를 다 내고 끝내므로 커넥션마다 면접이 끝난다.
        with client.websocket_connect("/ws/interview?card=card") as websocket:
            websocket.receive_json()
            websocket.send_bytes(b"\x00")
            websocket.receive_bytes()

    assert credits.balance(user_id) == SIGNUP_GRANT - 2 * COST_INTERVIEW
    assert len(store.list_sessions("card")) == 2
