"""로그인과 소유권.

제공자로 갔다 오는 왕복(authlib)은 여기서 보지 않는다 — 그건 남의 코드다.
우리가 소유한 것은 셋이다: 세션 쿠키가 누구를 가리키는가, 로그인 안 한 요청을
막는가, 남의 데이터가 보이는가.
"""

from __future__ import annotations

from conftest import make_store
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from daedam.db import Database, User
from daedam.server.accounts import Accounts
from daedam.server.auth import SESSION_USER_KEY, configured_providers, create_auth_router


def _app(accounts: Accounts) -> TestClient:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="테스트")
    app.include_router(create_auth_router(accounts))

    @app.get("/protected")
    def protected(user_id: str = Depends(accounts.current_user_id)) -> dict[str, str]:
        return {"userId": user_id}

    # 테스트가 로그인을 흉내 내는 자리. 실제로는 OAuth 콜백이 이 줄을 한다.
    @app.post("/pretend-login/{user_id}")
    def pretend_login(user_id: str, request: Request) -> dict[str, bool]:
        request.session[SESSION_USER_KEY] = user_id
        return {"ok": True}

    return TestClient(app)


def _db(tmp_path) -> Database:
    return make_store(tmp_path / "data")[0]._db


def test_로그인_설정이_없으면_기본_사용자로_돈다(tmp_path) -> None:
    """개발자가 카카오·구글에 앱을 등록하지 않고도 서버를 띄울 수 있어야 한다."""
    accounts = Accounts(_db(tmp_path), login_required=False)
    client = _app(accounts)
    assert client.get("/protected").json()["userId"] == accounts.default_user_id()
    assert client.get("/api/auth/me").json()["name"] == "지원자"


def test_로그인이_필요하면_안_한_요청은_401(tmp_path) -> None:
    client = _app(Accounts(_db(tmp_path), login_required=True))
    assert client.get("/protected").status_code == 401
    # 화면이 랜딩을 그리도록 me는 401이 아니라 null이다.
    assert client.get("/api/auth/me").json() is None


def test_세션_쿠키가_사용자를_가리킨다(tmp_path) -> None:
    db = _db(tmp_path)
    accounts = Accounts(db, login_required=True)
    user_id = accounts.upsert(
        provider="kakao", provider_user_id="42", name="박지원", email="a@b.c"
    )

    client = _app(accounts)
    client.post(f"/pretend-login/{user_id}")
    assert client.get("/protected").json()["userId"] == user_id
    body = client.get("/api/auth/me").json()
    assert body["name"] == "박지원" and body["provider"] == "kakao"

    client.post("/api/auth/logout")
    assert client.get("/protected").status_code == 401


def test_탈퇴한_계정의_쿠키는_통하지_않는다(tmp_path) -> None:
    """쿠키는 서명만 검사한다 — 가리키는 사람이 아직 있는지는 따로 봐야 한다."""
    db = _db(tmp_path)
    accounts = Accounts(db, login_required=True)
    user_id = accounts.upsert(provider="google", provider_user_id="7")

    client = _app(accounts)
    client.post(f"/pretend-login/{user_id}")
    assert client.get("/protected").status_code == 200

    with db.session() as session:
        session.delete(session.get(User, user_id))
    assert client.get("/protected").status_code == 401


def test_재로그인은_같은_계정에_붙고_프로필을_갱신한다(tmp_path) -> None:
    accounts = Accounts(_db(tmp_path), login_required=True)
    first = accounts.upsert(provider="kakao", provider_user_id="42", name="옛 이름")
    again = accounts.upsert(
        provider="kakao", provider_user_id="42", name="새 이름", email="new@x.com"
    )
    assert first == again
    assert accounts.profile(first)["name"] == "새 이름"
    assert accounts.profile(first)["email"] == "new@x.com"


def test_제공자가_같아도_다른_계정은_다른_사람(tmp_path) -> None:
    accounts = Accounts(_db(tmp_path), login_required=True)
    a = accounts.upsert(provider="kakao", provider_user_id="1")
    b = accounts.upsert(provider="google", provider_user_id="1")
    assert a != b


def test_설정된_제공자만_노출된다(tmp_path, monkeypatch) -> None:
    """설정이 없으면 화면은 로그인 버튼을 그리지 않는다."""
    for key in ("KAKAO", "GOOGLE"):
        monkeypatch.delenv(f"{key}_CLIENT_ID", raising=False)
        monkeypatch.delenv(f"{key}_CLIENT_SECRET", raising=False)
    assert configured_providers() == []

    monkeypatch.setenv("KAKAO_CLIENT_ID", "id")
    monkeypatch.setenv("KAKAO_CLIENT_SECRET", "secret")
    assert configured_providers() == ["kakao"]
    # id만 있고 secret이 없으면 등록하지 않는다 — 반쪽 설정으로 뜨면 로그인
    # 버튼은 보이는데 눌리지 않는다.
    monkeypatch.delenv("KAKAO_CLIENT_SECRET")
    assert configured_providers() == []


def test_없는_제공자로_로그인하면_404(tmp_path) -> None:
    client = _app(Accounts(_db(tmp_path), login_required=True))
    assert client.get("/api/auth/naver/login").status_code == 404
