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
from typing import Any

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from .accounts import Accounts

logger = logging.getLogger(__name__)

#: 세션 쿠키에 담는 키. 값은 users.id다.
SESSION_USER_KEY = "user_id"

#: 카카오는 OpenID Connect 디스커버리 문서를 제공한다 — 엔드포인트를 하나씩
#: 적는 것보다 이쪽이 바뀌어도 따라간다.
_KAKAO_METADATA = "https://kauth.kakao.com/.well-known/openid-configuration"
_GOOGLE_METADATA = "https://accounts.google.com/.well-known/openid-configuration"

#: 로그인 뒤 돌아갈 화면. 프론트가 SPA라 루트로 보내면 상태를 다시 읽는다.
_AFTER_LOGIN = "/"


def _provider_config(provider: str) -> tuple[str, str] | None:
    """이 제공자의 client id·secret. 둘 다 있어야 등록한다."""
    client_id = os.environ.get(f"{provider.upper()}_CLIENT_ID")
    secret = os.environ.get(f"{provider.upper()}_CLIENT_SECRET")
    return (client_id, secret) if client_id and secret else None


def configured_providers() -> list[str]:
    """설정이 갖춰진 제공자들. 비어 있으면 로그인 없이 도는 모드다."""
    return [p for p in ("kakao", "google") if _provider_config(p) is not None]


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
            # 이름과 이메일만 받는다. 카카오는 이메일이 선택 동의라 사용자가
            # 거부할 수 있고, 그때도 로그인은 되어야 한다.
            client_kwargs={"scope": "openid profile email"},
        )
    return oauth


def _profile_from(token: dict[str, Any], provider: str) -> dict[str, Any]:
    """토큰에 실려 온 사용자 정보를 우리 형태로.

    OpenID Connect라 두 제공자 모두 id_token의 클레임이 파싱되어
    `token["userinfo"]`에 들어온다. `sub`는 필수 클레임이라 늘 있다.
    """
    info = token.get("userinfo") or {}
    if not info.get("sub"):
        raise HTTPException(status_code=502, detail="제공자가 사용자 정보를 주지 않았습니다")
    # 카카오는 nickname으로, 구글은 name으로 준다.
    name = info.get("name") or info.get("nickname") or ""
    return {
        "provider": provider,
        "provider_user_id": str(info["sub"]),
        "email": info.get("email"),
        "name": name,
        "avatar_url": info.get("picture"),
    }


def create_auth_router(accounts: Accounts) -> APIRouter:
    """로그인·로그아웃·내 정보 라우터.

      GET /api/auth/providers          — 화면이 그릴 로그인 버튼 목록
      GET /api/auth/{provider}/login   — 제공자로 보낸다
      GET /api/auth/{provider}/callback— 돌아온 것을 받아 세션을 심는다
      GET /api/auth/me                 — 지금 누구인가 (로그인 안 했으면 null)
      POST /api/auth/logout            — 세션을 비운다
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
        # 콜백 주소는 지금 요청의 오리진에서 만든다. 로컬·배포에서 따로
        # 설정하지 않아도 맞고, 제공자 콘솔에 등록한 값과 같아야 한다.
        redirect_uri = request.url_for("callback", provider=provider)
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
            return RedirectResponse(_AFTER_LOGIN, status_code=302)
        user_id = accounts.upsert(**_profile_from(token, provider))
        request.session[SESSION_USER_KEY] = user_id
        return RedirectResponse(_AFTER_LOGIN, status_code=302)

    @router.post("/logout")
    def logout(request: Request) -> dict[str, bool]:
        request.session.pop(SESSION_USER_KEY, None)
        return {"ok": True}

    return router
