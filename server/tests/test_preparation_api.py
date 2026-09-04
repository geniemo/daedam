"""면접 준비 API 라우트 테스트.

무거운 ADK 앱(get_fast_api_app) 대신 맨 FastAPI에 라우터만 얹어 검증한다.
준비 파이프라인은 fixture 리서치(수십 ms) + 대역 생성으로 실제 완주시키고,
완료는 타임아웃 폴링으로 기다린다.
"""

import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from conftest import make_store

from daedam.research.service import FixtureResearch
from daedam.server.credits import COST_RESEARCH
from daedam.server.preparation import InterviewPreparation
from daedam.server.preparation_routes import create_preparation_router


def _client(tmp_path: Path, duration_s: float = 0.01) -> TestClient:
    store, accounts, _ = make_store(tmp_path / "data")
    preparation = InterviewPreparation(
        research=FixtureResearch(duration_s=duration_s),
        store=store,
        generate=lambda **kwargs: [
            {"id": "q-0-0", "stage": 0, "text": "질문?", "priority": 1, "tags": ["태그"]}
        ],
        poll_interval_s=0.01,
    )
    app = FastAPI()
    app.include_router(create_preparation_router(preparation, accounts, accounts.credits))
    return TestClient(app)


def _wait_done(client: TestClient, task_id: str, timeout_s: float = 3.0) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        body = client.get(f"/api/preparation/{task_id}").json()
        if body["status"] != "running":
            return body
        time.sleep(0.02)
    raise AssertionError("시간 안에 완료되지 않음")


def test_등록하면_task_id를_받는다(tmp_path: Path) -> None:
    response = _client(tmp_path).post(
        "/api/preparation", json={"company": "한결물류", "role": "데이터 엔지니어"}
    )
    assert response.status_code == 202
    assert response.json()["task_id"]


def test_진행_중에는_리포트가_없다(tmp_path: Path) -> None:
    client = _client(tmp_path, duration_s=10)
    task_id = client.post(
        "/api/preparation", json={"company": "A", "role": "B"}
    ).json()["task_id"]

    body = client.get(f"/api/preparation/{task_id}").json()
    assert body["status"] == "running" and body["pct"] <= 90
    assert "report" not in body


def test_완료되면_리포트와_확인_필요_목록이_온다(tmp_path: Path) -> None:
    client = _client(tmp_path)
    task_id = client.post(
        "/api/preparation",
        json={
            "company": "한결물류",
            "role": "데이터 엔지니어",
            "application": [{"part": "자소서", "items": [{"title": "지원동기", "body": "..."}]}],
        },
    ).json()["task_id"]

    body = _wait_done(client, task_id)
    assert body["status"] == "done" and body["pct"] == 100
    assert body["report"] and isinstance(body["uncertain"], list)


def test_없는_task는_404(tmp_path: Path) -> None:
    assert _client(tmp_path).get("/api/preparation/xyz").status_code == 404

# ── 차감은 리서치를 열기 전에 ─────────────────────────────────────────────


def test_등록은_리서치를_열기_전에_차감하고_그_id를_카드로_쓴다(tmp_path: Path) -> None:
    """앞서는 시작한 뒤 차감했다 — 두 탭이 동시에 등록하면 둘째의 차감이 실패해도
    리서치는 이미 돌았다. 차감이 먼저면 그 창이 없고, 환불도 같은 id를 본다."""
    store, accounts, user_id = make_store(tmp_path / "data")
    credits = accounts.credits
    before = credits.balance(user_id)
    preparation = InterviewPreparation(
        research=FixtureResearch(duration_s=10),  # 완료되지 않은 채로 잔액을 본다
        store=store,
        generate=lambda **_: [],
        poll_interval_s=0.01,
    )
    app = FastAPI()
    app.include_router(create_preparation_router(preparation, accounts, credits))
    task_id = TestClient(app).post(
        "/api/preparation", json={"company": "A", "role": "B"}
    ).json()["task_id"]

    assert credits.balance(user_id) == before - COST_RESEARCH
    assert store.load(task_id) is not None
    # 이 건을 되돌리면 정확히 그만큼 돌아온다 — ref_id가 카드 id다.
    credits.refund(user_id, "research", task_id)
    assert credits.balance(user_id) == before


def test_시작이_실패하면_차감을_되돌리고_503(tmp_path: Path) -> None:
    """유료 작업이 열리지 않았는데 요금을 물리면 안 된다."""
    store, accounts, user_id = make_store(tmp_path / "data")
    credits = accounts.credits
    before = credits.balance(user_id)

    class _Broken:
        def start(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise RuntimeError("Deep Research 열기 실패")

        def status(self, task_id):  # noqa: ANN001
            return None

    app = FastAPI()
    app.include_router(
        create_preparation_router(
            InterviewPreparation(research=_Broken(), store=store, generate=lambda **_: []),
            accounts,
            credits,
        )
    )
    response = TestClient(app).post("/api/preparation", json={"company": "A", "role": "B"})
    assert response.status_code == 503
    assert credits.balance(user_id) == before
