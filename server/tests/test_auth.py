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


def _app(accounts: Accounts, store=None) -> TestClient:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="테스트")
    app.include_router(create_auth_router(accounts, store or _NoFiles()))

    @app.get("/protected")
    def protected(user_id: str = Depends(accounts.current_user_id)) -> dict[str, str]:
        return {"userId": user_id}

    # 테스트가 로그인을 흉내 내는 자리. 실제로는 OAuth 콜백이 이 줄을 한다.
    @app.post("/pretend-login/{user_id}")
    def pretend_login(user_id: str, request: Request) -> dict[str, bool]:
        request.session[SESSION_USER_KEY] = user_id
        return {"ok": True}

    return TestClient(app)


class _NoFiles:
    """녹음이 없는 저장소 대역. 탈퇴를 안 보는 테스트가 쓴다."""

    def delete_user_files(self, user_id: str) -> int:
        return 0


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


def test_제공자마다_scope_어휘가_다르다(monkeypatch) -> None:
    """카카오는 표준 OIDC 이름(profile·email)을 받지 않고 자기 동의항목 ID를
    쓴다. 같은 문자열을 둘 다에 보내면 카카오 로그인이 통째로 실패한다."""
    from daedam.server.auth import _scope

    monkeypatch.delenv("KAKAO_SCOPE", raising=False)
    monkeypatch.delenv("GOOGLE_SCOPE", raising=False)

    kakao = _scope("kakao")
    assert kakao.startswith("openid ")  # 없으면 ID 토큰이 안 온다
    assert "profile_nickname" in kakao
    assert " profile " not in f" {kakao} " and " email " not in f" {kakao} "

    assert _scope("google") == "openid profile email"

    # 콘솔에서 못 켠 동의항목이 있으면 낮춰서 띄울 수 있어야 한다.
    monkeypatch.setenv("KAKAO_SCOPE", "openid profile_nickname")
    assert _scope("kakao") == "openid profile_nickname"


def test_콜백_주소는_설정으로_못_박을_수_있다(monkeypatch) -> None:
    """제공자 콘솔의 등록값은 하나인데, 요청에서 유도하면 접속 경로에 따라
    localhost와 127.0.0.1이 갈린다(실측). 다르면 카카오는 KOE006이다."""
    from starlette.datastructures import URL

    from daedam.server.auth import _callback_uri

    class _Request:
        def url_for(self, name: str, **kwargs: str) -> URL:
            return URL(f"http://127.0.0.1:8000/api/auth/{kwargs['provider']}/callback")

    monkeypatch.delenv("SERVER_BASE_URL", raising=False)
    assert _callback_uri(_Request(), "kakao").startswith("http://127.0.0.1:8000/")

    monkeypatch.setenv("SERVER_BASE_URL", "http://localhost:8000")
    assert (
        _callback_uri(_Request(), "kakao")
        == "http://localhost:8000/api/auth/kakao/callback"
    )
    # 끝의 슬래시가 있어도 콜백 주소는 같아야 한다.
    monkeypatch.setenv("SERVER_BASE_URL", "https://daedam.example.com/")
    assert (
        _callback_uri(_Request(), "google")
        == "https://daedam.example.com/api/auth/google/callback"
    )


def test_카카오는_토큰_교환에_client_secret_post를_쓴다(monkeypatch) -> None:
    """카카오 토큰 엔드포인트는 client_secret_post만 지원하는데 authlib은
    시크릿이 있으면 client_secret_basic을 기본으로 고른다. 그대로 두면 요청
    본문에 client_id가 안 실려 "Not exist client_id [null]"로 거절당한다 —
    인가 코드까지는 정상이라 화면에는 그냥 로그인 화면으로 돌아온 것처럼 보인다.
    """
    from daedam.server.auth import _client_kwargs

    monkeypatch.delenv("KAKAO_SCOPE", raising=False)
    assert _client_kwargs("kakao")["token_endpoint_auth_method"] == "client_secret_post"
    # 구글은 둘 다 받으므로 지정하지 않는다.
    assert "token_endpoint_auth_method" not in _client_kwargs("google")


# ── 회원 탈퇴 ────────────────────────────────────────────────────────────


def test_탈퇴하면_계정과_남긴_것이_전부_사라진다(tmp_path) -> None:
    """음성은 가장 민감한 개인정보다 — DB 행뿐 아니라 녹음 파일까지 지워야
    개인정보처리방침에 적을 약속이 참이 된다."""
    from daedam.db import Application, InterviewSession

    store, accounts, _ = make_store(tmp_path / "data")
    accounts._login_required = True
    user_id = accounts.upsert(provider="kakao", provider_user_id="42")
    store.save(
        "card", user_id=user_id, company="c", role="r",
        application=[], report=[], uncertain=[],
    )
    session_id = store.start_session("card")
    directory = store.session_directory("card", session_id)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "mic.wav").write_bytes(b"\x00\x01")  # 녹음 대역

    client = _app(accounts, store)
    client.post(f"/pretend-login/{user_id}")
    assert client.delete("/api/auth/me").json() == {"ok": True}

    # 녹음 파일이 남으면 안 된다.
    assert not directory.exists()
    with store._db.session() as db_session:
        assert db_session.get(Application, "card") is None
        assert db_session.get(InterviewSession, session_id) is None
        assert db_session.get(User, user_id) is None
    # 세션도 비워져 다음 요청은 로그인 안 한 상태다.
    assert client.get("/protected").status_code == 401


def test_로그인하지_않으면_탈퇴할_수_없다(tmp_path) -> None:
    client = _app(Accounts(_db(tmp_path), login_required=True))
    assert client.delete("/api/auth/me").status_code == 401
