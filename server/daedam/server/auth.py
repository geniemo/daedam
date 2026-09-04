"""카카오·구글 로그인.

비밀번호를 받지 않는다. 받는 순간 해싱·재설정 메일·이메일 인증·계정 잠금이
줄줄이 따라오는데, 국내 서비스에서 소셜 로그인만으로 대부분 커버된다.

세션은 서명 쿠키다(Starlette `SessionMiddleware`). JWT를 쓰지 않는 이유는
단일 인스턴스 배포이고, 로그아웃 즉시 무효화가 쿠키 쪽이 단순하기 때문이다.
쿠키에는 사용자 id만 담는다 — 프로필은 매번 데이터베이스에서 읽는다.

**설정이 없으면 로그인 없이 돈다.** 개발자가 카카오·구글에 앱을 등록하지
않고도 서버를 띄울 수 있어야 하기 때문이다. 그때는 모든 데이터가 기본 사용자
한 명의 것이고, 기동 로그가 그 사실을 크게 남긴다.

확인 경로 (설치된 authlib 1.7.2):
  authlib/integrations/starlette_client/apps.py
    — `authorize_redirect(request, redirect_uri)` / `authorize_access_token(request)`
  authlib/integrations/base_client/registry.py `register(name, **kwargs)`

제공자 문서:
  카카오 https://developers.kakao.com/docs/latest/ko/kakaologin/rest-api
  구글   https://developers.google.com/identity/protocols/oauth2/web-server
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from fastapi.responses import RedirectResponse

from .accounts import Accounts
from .store import InterviewStore

logger = logging.getLogger(__name__)

#: 세션 쿠키에 담는 키. 값은 users.id다.
SESSION_USER_KEY = "user_id"

#: 카카오는 OpenID Connect 디스커버리 문서를 제공한다 — 엔드포인트를 하나씩
#: 적는 것보다 이쪽이 바뀌어도 따라간다.
_KAKAO_METADATA = "https://kauth.kakao.com/.well-known/openid-configuration"
_GOOGLE_METADATA = "https://accounts.google.com/.well-known/openid-configuration"

#: 제공자마다 요구하는 scope 어휘가 다르다.
#:
#: 구글은 표준 OIDC 이름(profile·email)을 쓰지만 **카카오는 자기 동의항목 ID를
#: 쓴다**(공식 문서: "scope 파라미터 값에 openid를 반드시 포함", 나머지는
#: profile_nickname·profile_image·account_email 같은 동의항목 id).
#: 카카오에 profile·email을 보내면 로그인이 통째로 실패한다.
#:
#: 여기 적은 동의항목이 **카카오 콘솔에서 켜져 있어야 한다**
#: ([카카오 로그인] > [동의항목]). 켜지지 않은 항목을 요구하면 제공자가 거절한다 —
#: 특히 이메일은 앱 상태에 따라 못 켤 수 있으므로, 그때는
#: `KAKAO_SCOPE="openid profile_nickname"`으로 낮춰서 띄운다. 이메일은
#: 선택 정보라 없어도 로그인은 성립한다(users.email이 nullable).
_DEFAULT_SCOPE = {
    "kakao": "openid profile_nickname profile_image account_email",
    "google": "openid profile email",
}


#: 토큰 교환 때 클라이언트를 증명하는 방식.
#:
#: 카카오는 `client_secret_post`만 지원한다 — 디스커버리 문서의
#: `token_endpoint_auth_methods_supported`가 그것 하나다. 그런데 authlib은
#: 시크릿이 있으면 `client_secret_basic`을 기본으로 골라(oauth2/client.py:75~77)
#: 자격증명을 Authorization 헤더에만 싣는다. 그러면 카카오가 본문에서
#: client_id를 못 찾고 이렇게 거절한다 — 실측:
#:   OAuthError: invalid_client: Not exist client_id [null]
#: 인가 코드까지는 정상이라 사용자 눈에는 "동의했는데 로그인 화면으로 돌아옴"으로만
#: 보인다.
#:
#: 구글은 둘 다 받으므로 적지 않는다 — 기본값 그대로 둔다.
_TOKEN_AUTH_METHOD = {"kakao": "client_secret_post"}


def _scope(provider: str) -> str:
    """이 제공자에게 요구할 scope. 환경변수로 덮을 수 있다."""
    return os.environ.get(f"{provider.upper()}_SCOPE") or _DEFAULT_SCOPE[provider]


def _client_kwargs(provider: str) -> dict[str, str]:
    """이 제공자용 OAuth 클라이언트 설정."""
    kwargs = {"scope": _scope(provider)}
    method = _TOKEN_AUTH_METHOD.get(provider)
    if method:
        kwargs["token_endpoint_auth_method"] = method
    return kwargs


def _callback_uri(request: Request, provider: str) -> str:
    """제공자 콘솔에 등록한 콜백 주소.

    **글자 하나까지 등록값과 같아야 한다** — 카카오는 다르면 KOE006이다.

    요청에서 유도하지 않고 `SERVER_BASE_URL`로 고정할 수 있게 둔 이유는, 유도한
    값이 **어떻게 접속했느냐에 따라 달라지기** 때문이다. 같은 서버인데도
    localhost로 들어오면 localhost, 127.0.0.1로 들어오면 127.0.0.1이 나오고
    (실측), 리버스 프록시 뒤에서는 프록시가 넘겨주는 헤더에 좌우된다. 등록값은
    하나뿐이므로 이 값도 하나로 못 박는 편이 안전하다.

    설정이 없으면 요청에서 유도한다 — 처음 띄워 보는 사람이 환경변수부터
    만나지 않도록.
    """
    base = os.environ.get("SERVER_BASE_URL")
    if base:
        return f"{base.rstrip('/')}/api/auth/{provider}/callback"
    return str(request.url_for("callback", provider=provider))


def _after_login() -> str:
    """로그인 뒤 돌아갈 화면. 프론트가 SPA라 루트로 보내면 상태를 다시 읽는다.

    배포에서는 프론트와 서버가 같은 오리진이라 "/"면 된다. 개발에서는 vite가
    5173에 따로 떠 있어서 서버의 "/"로 보내면 ADK dev UI가 뜬다 —
    `APP_BASE_URL=http://localhost:5173`으로 넘긴다.
    """
    return os.environ.get("APP_BASE_URL") or "/"


def _provider_config(
    provider: str, env: Mapping[str, str] = os.environ
) -> tuple[str, str] | None:
    """이 제공자의 client id·secret. 둘 다 있어야 등록한다."""
    client_id = env.get(f"{provider.upper()}_CLIENT_ID")
    secret = env.get(f"{provider.upper()}_CLIENT_SECRET")
    return (client_id, secret) if client_id and secret else None


def configured_providers(env: Mapping[str, str] = os.environ) -> list[str]:
    """설정이 갖춰진 제공자들. 비어 있으면 로그인 없이 도는 모드다.

    `env`를 받는 이유: 기동 전 점검(preflight)이 같은 기준으로 판정해야 하고,
    그 점검은 dict로 시험한다.
    """
    return [p for p in ("kakao", "google") if _provider_config(p, env) is not None]


def create_oauth() -> OAuth:
    """설정된 제공자만 등록한 OAuth 레지스트리."""
    oauth = OAuth()
    for provider in configured_providers():
        client_id, secret = _provider_config(provider)  # type: ignore[misc]
        oauth.register(
            name=provider,
            client_id=client_id,
            client_secret=secret,
            server_metadata_url=(
                _KAKAO_METADATA if provider == "kakao" else _GOOGLE_METADATA
            ),
            # 요구할 동의항목과 토큰 교환 인증 방식. 둘 다 제공자마다 다르다.
            client_kwargs=_client_kwargs(provider),
        )
    return oauth


def _profile_from(token: dict[str, Any], provider: str) -> dict[str, Any]:
    """토큰에 실려 온 사용자 정보를 우리 형태로.

    OpenID Connect라 두 제공자 모두 id_token의 클레임이 파싱되어
    `token["userinfo"]`에 들어온다. `sub`는 필수 클레임이라 늘 있다.
    """
    info = token.get("userinfo") or {}
    if not info.get("sub"):
        # id_token이 안 왔다는 뜻이다. 카카오라면 콘솔에서 OpenID Connect가
        # 꺼져 있을 가능성이 가장 높다([카카오 로그인] > [OpenID Connect]).
        raise HTTPException(
            status_code=502, detail="제공자가 사용자 정보를 주지 않았습니다"
        )
    # 카카오는 nickname으로, 구글은 name으로 준다.
    name = info.get("name") or info.get("nickname") or ""
    return {
        "provider": provider,
        "provider_user_id": str(info["sub"]),
        "email": info.get("email"),
        "name": name,
        "avatar_url": info.get("picture"),
    }


class OnboardBody(BaseModel):
    """온보딩 제출. 모듈 레벨인 이유: `from __future__ import annotations` 아래라
    클로저 안 클래스는 FastAPI가 힌트를 못 풀어 422가 났다(실측)."""

    name: str = Field(min_length=1, max_length=64)


def create_auth_router(accounts: Accounts, store: InterviewStore) -> APIRouter:
    """로그인·로그아웃·내 정보 라우터.

      GET    /api/auth/providers          — 화면이 그릴 로그인 버튼 목록
      GET    /api/auth/{provider}/login   — 제공자로 보낸다
      GET    /api/auth/{provider}/callback— 돌아온 것을 받아 세션을 심는다
      GET    /api/auth/me                 — 지금 누구인가 (로그인 안 했으면 null)
      POST   /api/auth/logout             — 세션을 비운다
      DELETE /api/auth/me                 — 회원 탈퇴

    Args:
        accounts: 사용자 조회·저장.
        store: 탈퇴할 때 녹음 파일을 지우려면 필요하다 — 오디오는 DB 밖이라
            외래 키가 지워 주지 않는다.
    """
    router = APIRouter(prefix="/api/auth", tags=["auth"])
    oauth = create_oauth()
    providers = configured_providers()

    @router.get("/providers")
    def list_providers() -> dict[str, Any]:
        """설정된 로그인 수단. 비어 있으면 화면은 로그인 없이 진행한다."""
        return {"providers": providers}

    @router.get("/me")
    def me(request: Request) -> dict[str, Any] | None:
        """지금 로그인한 사용자. 없으면 null — 화면이 랜딩을 그린다."""
        return accounts.profile(accounts.session_user_id(request))

    @router.get("/{provider}/login")
    async def login(provider: str, request: Request):
        if provider not in providers:
            raise HTTPException(status_code=404, detail="지원하지 않는 로그인입니다")
        redirect_uri = _callback_uri(request, provider)
        return await getattr(oauth, provider).authorize_redirect(request, redirect_uri)

    @router.get("/{provider}/callback", name="callback")
    async def callback(provider: str, request: Request):
        if provider not in providers:
            raise HTTPException(status_code=404, detail="지원하지 않는 로그인입니다")
        try:
            token = await getattr(oauth, provider).authorize_access_token(request)
        except OAuthError:
            # 사용자가 동의를 취소한 경우가 대부분이다. 에러 화면 대신 처음으로
            # 돌려보낸다 — 다시 누르면 된다.
            logger.info("%s 로그인이 완료되지 않았습니다", provider, exc_info=True)
            return RedirectResponse(_after_login(), status_code=302)
        user_id = accounts.upsert(**_profile_from(token, provider))
        request.session[SESSION_USER_KEY] = user_id
        return RedirectResponse(_after_login(), status_code=302)

    @router.post("/onboard")
    def onboard(body: OnboardBody, request: Request) -> dict[str, Any]:
        """온보딩 제출 — 이름 확정 + 약관·개인정보 동의 시각 기록.

        화면이 동의 체크 없이는 부르지 못하게 한다. 서버가 남기는 것은
        "무엇에 언제 동의했는가"다(`users.onboarded_at`).
        """
        user_id = accounts.current_user_id(request)
        try:
            profile = accounts.complete_onboarding(user_id, body.name)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        if profile is None:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다")
        return profile

    @router.post("/logout")
    def logout(request: Request) -> dict[str, bool]:
        request.session.pop(SESSION_USER_KEY, None)
        return {"ok": True}

    @router.delete("/me")
    def withdraw(request: Request) -> dict[str, bool]:
        """회원 탈퇴 — 계정과 그가 남긴 것을 전부 지운다.

        되돌릴 수 없다. 준비 데이터·면접 기록·크레딧은 외래 키가 함께 지우고,
        녹음 파일은 DB 밖이라 먼저 손으로 지운다 — 순서가 뒤바뀌면 어느 준비
        데이터가 그 사람 것이었는지 알 수 없게 된다.

        음성은 가장 민감한 개인정보이고, 탈퇴하면 지운다는 것이 개인정보
        처리방침에 적힐 약속이다.
        """
        user_id = accounts.session_user_id(request)
        if user_id is None:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다")
        removed = store.delete_user_files(user_id)
        accounts.delete(user_id)
        request.session.pop(SESSION_USER_KEY, None)
        logger.info("회원 탈퇴 (user=%s, 녹음 %d건 삭제)", user_id, removed)
        return {"ok": True}

    return router
