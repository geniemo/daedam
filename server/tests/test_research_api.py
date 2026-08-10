"""리서치 API 라우트 테스트.

무거운 ADK 앱(get_fast_api_app) 대신 맨 FastAPI에 라우터만 얹어 검증한다.
앱 조립은 daedam/server/app.py가 맡고, 여기서는 라우트 계약만 본다.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from daedam.research.service import FixtureResearch
from daedam.server.research_routes import create_research_router


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _client(clock: _Clock) -> TestClient:
    app = FastAPI()
    app.include_router(
        create_research_router(FixtureResearch(duration_s=10, clock=clock))
    )
    return TestClient(app)


def test_등록하면_task_id를_받는다() -> None:
    response = _client(_Clock()).post(
        "/api/research", json={"company": "한결물류", "role": "데이터 엔지니어"}
    )
    assert response.status_code == 202
    assert response.json()["task_id"]


def test_지원서를_함께_보낼_수_있다() -> None:
    response = _client(_Clock()).post(
        "/api/research",
        json={
            "company": "한결물류",
            "role": "데이터 엔지니어",
            "application": [{"part": "자소서", "items": [{"title": "지원동기", "body": "..."}]}],
        },
    )
    assert response.status_code == 202


def test_진행_중에는_리포트가_없다() -> None:
    clock = _Clock()
    client = _client(clock)
    task_id = client.post("/api/research", json={"company": "A", "role": "B"}).json()["task_id"]

    clock.now = 5
    body = client.get(f"/api/research/{task_id}").json()
    assert body["status"] == "running" and body["pct"] == 50
    assert "report" not in body


def test_완료되면_리포트와_확인_필요_목록이_온다() -> None:
    clock = _Clock()
    client = _client(clock)
    task_id = client.post("/api/research", json={"company": "A", "role": "B"}).json()["task_id"]

    clock.now = 10
    body = client.get(f"/api/research/{task_id}").json()
    assert body["status"] == "done" and body["pct"] == 100
    assert body["report"] and body["uncertain"]


def test_없는_task는_404() -> None:
    assert _client(_Clock()).get("/api/research/없는id").status_code == 404
