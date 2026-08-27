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
    """저장소·원장·사용자. 사용자는 conftest가 넉넉히 얹어 둔 상태다."""
    store, accounts, user_id = make_store(tmp_path / "data")
    return store, accounts.credits, user_id


def _drain(credits: Credits, user_id: str) -> None:
    """잔액을 0으로. 경계를 보는 테스트가 여기서 시작한다."""
    credits.charge(user_id, credits.balance(user_id), "interview", "비우기")


def test_가입_선물은_면접_한_판이다(tmp_path) -> None:
    """등록까지 덮지는 않는다 — 등록 원가가 면접보다 크고, 무료 체험은 리서치가
    이미 있는 프리셋 기업으로 받는다는 전제다."""
    store, accounts, _ = make_store(tmp_path / "data")
    credits: Credits = accounts.credits
    new_user = accounts.upsert(provider="kakao", provider_user_id="42")
    assert credits.balance(new_user) == SIGNUP_GRANT
    assert SIGNUP_GRANT >= COST_INTERVIEW
    assert SIGNUP_GRANT < COST_RESEARCH


def test_새_사용자에게만_한_번_준다(tmp_path) -> None:
    store, accounts, _ = make_store(tmp_path / "data")
    credits: Credits = accounts.credits
    first = accounts.upsert(provider="kakao", provider_user_id="1", name="박지원")
    again = accounts.upsert(provider="kakao", provider_user_id="1", name="박지원")
    assert first == again
    assert credits.balance(first) == SIGNUP_GRANT


def test_쓰면_줄고_내역이_남는다(bundle) -> None:
    _, credits, user_id = bundle
    before = credits.balance(user_id)
    credits.charge(user_id, COST_INTERVIEW, "interview", "s1")
    assert credits.balance(user_id) == before - COST_INTERVIEW
    [latest, *_] = credits.history(user_id)
    assert latest.delta == -COST_INTERVIEW and latest.ref_id == "s1"


def test_잔액이_딱_맞으면_통과하고_하나_모자라면_막는다(tmp_path) -> None:
    _, accounts, user_id = make_store(tmp_path / "data")
    credits: Credits = accounts.credits
    # 잔액을 정확히 2로 만든다.
    _drain(credits, user_id)
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
    before = credits.balance(user_id)
    credits.ensure(user_id, COST_RESEARCH)
    assert credits.balance(user_id) == before
    with pytest.raises(InsufficientCredits):
        credits.ensure(user_id, before + 1)


def test_실패한_건은_되돌리고_두_번_되돌리지_않는다(bundle) -> None:
    """실패한 작업에 요금을 물리면 다시 시도할 수도 없다."""
    _, credits, user_id = bundle
    before = credits.balance(user_id)
    credits.charge(user_id, COST_RESEARCH, "research", "task-1")
    credits.refund(user_id, "research", "task-1")
    assert credits.balance(user_id) == before

    credits.refund(user_id, "research", "task-1")  # 두 번째는 아무 일도 없다
    assert credits.balance(user_id) == before


def test_쓴_적_없는_건은_되돌릴_것이_없다(bundle) -> None:
    _, credits, user_id = bundle
    before = credits.balance(user_id)
    credits.refund(user_id, "research", "없는건")
    assert credits.balance(user_id) == before


# ── 라우트에서 막히는가 ─────────────────────────────────────────────────


def test_크레딧이_없으면_등록이_402(tmp_path) -> None:
    """Deep Research는 시작하면 취소할 수 없다 — 시작 전에 막아야 한다."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from daedam.server.preparation import InterviewPreparation
    from daedam.server.preparation_routes import create_preparation_router

    store, accounts, user_id = make_store(tmp_path / "data")
    credits: Credits = accounts.credits
    _drain(credits, user_id)

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
    _drain(credits, user_id)

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


def test_답변이_하나도_없으면_되돌린다(tmp_path) -> None:
    """실수로 시작하고 바로 나온 경우. 실제 원가는 몇 초치라 거의 0인데
    "잘못 눌렀는데 크레딧이 날아갔다"는 첫인상은 비싸다."""
    from test_live_bridge import _FakeRunner, _client, _seeded_store  # noqa: PLC0415

    store = _seeded_store(tmp_path, "card")
    credits: Credits = store.accounts.credits
    user_id = store.accounts.default_user_id()
    before = credits.balance(user_id)

    # 대역 러너는 면접관 쪽만 말하고 끝낸다 — 지원자 발화가 없다.
    client = _client(_FakeRunner(), store)
    with client.websocket_connect("/ws/interview?card=card") as websocket:
        websocket.receive_json()
        websocket.send_bytes(b"\x00")
        websocket.receive_bytes()

    assert credits.balance(user_id) == before
    # 차감과 환불이 둘 다 원장에 남는다 — 기록은 고치지 않는다.
    reasons = [e.reason for e in credits.history(user_id)[:2]]
    assert reasons == ["refund", "interview"]
    # 면접 판 자체는 남는다. 돈만 되돌린 것이다.
    assert len(store.list_sessions("card")) == 1


def test_답변이_있으면_그대로_물린다(tmp_path) -> None:
    """말을 한 면접은 환불 대상이 아니다."""
    from test_live_bridge import _TranscribingRunner, _client, _seeded_store  # noqa: PLC0415

    store = _seeded_store(tmp_path, "card")
    credits: Credits = store.accounts.credits
    user_id = store.accounts.default_user_id()
    before = credits.balance(user_id)

    # 이 대역은 지원자 전사까지 흘린다.
    client = _client(_TranscribingRunner(), store)
    with client.websocket_connect("/ws/interview?card=card") as websocket:
        websocket.receive_json()
        websocket.send_bytes(b"\x00\x01" * 16_000)
        while websocket.receive_json()["type"] != "ended":
            pass

    assert credits.balance(user_id) == before - COST_INTERVIEW


# ── 쿠폰 ─────────────────────────────────────────────────────────────────


def _coupon(store, code: str, credits: int = 10, **kwargs):
    from daedam.db import Coupon

    with store._db.session() as session:
        session.add(Coupon(code=code, credits=credits, **kwargs))


def test_쿠폰을_쓰면_크레딧이_는다(bundle) -> None:
    store, credits, user_id = bundle
    _coupon(store, "WELCOME10", 10, max_uses=5)
    before = credits.balance(user_id)

    assert credits.redeem(user_id, "WELCOME10") == 10
    assert credits.balance(user_id) == before + 10
    # 원장에 "충전"으로 남고, 어느 코드였는지도 남는다.
    [latest, *_] = credits.history(user_id)
    assert latest.reason == "purchase" and latest.ref_id == "WELCOME10"


def test_코드는_대소문자와_공백을_가리지_않는다(bundle) -> None:
    """영상 자막을 보고 손으로 치는 값이다."""
    store, credits, user_id = bundle
    _coupon(store, "WELCOME10", 10)
    assert credits.redeem(user_id, "  welcome10 ") == 10


def test_같은_사람이_두_번_쓸_수_없다(bundle) -> None:
    from daedam.server.credits import CouponError

    store, credits, user_id = bundle
    _coupon(store, "WELCOME10", 10, max_uses=100)
    credits.redeem(user_id, "WELCOME10")
    before = credits.balance(user_id)

    with pytest.raises(CouponError) as raised:
        credits.redeem(user_id, "WELCOME10")
    assert raised.value.reason == "already_used"
    assert credits.balance(user_id) == before


def test_정원이_차면_막힌다(tmp_path) -> None:
    from daedam.server.credits import CouponError

    store, accounts, first = make_store(tmp_path / "data")
    credits: Credits = accounts.credits
    second = accounts.upsert(provider="kakao", provider_user_id="2")
    _coupon(store, "ONLYONE", 10, max_uses=1)

    credits.redeem(first, "ONLYONE")
    with pytest.raises(CouponError) as raised:
        credits.redeem(second, "ONLYONE")
    assert raised.value.reason == "exhausted"


def test_만료된_코드는_막힌다(bundle) -> None:
    from datetime import UTC, datetime, timedelta

    from daedam.server.credits import CouponError

    store, credits, user_id = bundle
    _coupon(store, "OLD", 10, expires_at=datetime.now(UTC) - timedelta(days=1))
    with pytest.raises(CouponError) as raised:
        credits.redeem(user_id, "OLD")
    assert raised.value.reason == "expired"


def test_없는_코드는_없다고_한다(bundle) -> None:
    from daedam.server.credits import CouponError

    _, credits, user_id = bundle
    with pytest.raises(CouponError) as raised:
        credits.redeem(user_id, "NOPE")
    assert raised.value.reason == "not_found"


def test_동시에_두_번_차감해도_한_번만_나간다(tmp_path) -> None:
    """두 탭에서 동시에 면접을 시작하는 경우. SQLite의 기본 트랜잭션은
    지연이라 SELECT가 잠금을 잡지 않고, 그러면 둘 다 같은 옛 잔액을 읽고 둘 다
    통과한다 — 돈이 새는 자리다."""
    import threading

    _, accounts, user_id = make_store(tmp_path / "data")
    credits: Credits = accounts.credits
    _drain(credits, user_id)
    credits.grant(user_id, 4, "admin_grant")  # 면접 딱 한 번치

    results: list[str] = []
    barrier = threading.Barrier(2)

    def attempt(ref: str) -> None:
        barrier.wait()  # 둘이 정확히 같이 출발한다
        try:
            credits.charge(user_id, 4, "interview", ref)
            results.append("통과")
        except InsufficientCredits:
            results.append("막힘")

    threads = [threading.Thread(target=attempt, args=(f"s{i}",)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == ["막힘", "통과"], results
    assert credits.balance(user_id) == 0
