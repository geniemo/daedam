"""상태 확인 라우트 테스트."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from daedam.db import Database
from daedam.server.health import create_health_router


def _client(tmp_path, data_root=None):
    db = Database(f"sqlite:///{tmp_path / 'h.db'}")
    db.create_all()
    app = FastAPI()
    app.include_router(create_health_router(db, data_root or tmp_path))
    return TestClient(app)


def test_정상이면_ok(tmp_path) -> None:
    response = _client(tmp_path).get("/api/health")
    assert response.status_code == 200 and response.json() == {"status": "ok"}
    assert not (tmp_path / ".health").exists()  # 탐침 파일은 남기지 않는다


def test_데이터_디렉터리에_못_쓰면_503(tmp_path) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("파일이라 그 아래에 쓸 수 없다")
    response = _client(tmp_path, data_root=blocked).get("/api/health")
    assert response.status_code == 503 and response.json()["status"] == "fail"


def test_HEAD도_받는다(tmp_path) -> None:
    """감시 도구가 HEAD로 두드린다. get만 두면 405가 나 죽은 것으로 읽힌다."""
    assert _client(tmp_path).head("/api/health").status_code == 200
