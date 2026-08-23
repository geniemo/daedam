"""사용자 조회 — 라우트가 "지금 누구인가"를 묻는 자리.

세션 쿠키에 담긴 사용자 id를 읽어 그 사람의 데이터만 보이게 한다. 소셜
로그인의 실제 흐름은 `auth.py`에 있고, 여기는 그 결과를 저장하고 되찾는
쪽이다.

**로그인 설정이 없으면 기본 사용자 한 명으로 돈다.** 개발자가 카카오·구글에
앱을 등록하지 않고도 서버를 띄울 수 있어야 하기 때문이다. 그때는 모든 데이터가
그 한 사람의 것이고, 기동 로그가 그 사실을 크게 남긴다.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import select
from starlette.websockets import WebSocket

from daedam.db import Database, User

from .credits import SIGNUP_GRANT, Credits

logger = logging.getLogger(__name__)

#: 로그인 없이 도는 동안 쓰는 가상 제공자. 실제 OAuth 제공자("kakao"·"google")와
#: 겹치지 않으므로 나중에 진짜 계정이 생겨도 이 행과 충돌하지 않는다.
LOCAL_PROVIDER = "local"
_LOCAL_USER_ID = "single-user"

#: 세션 쿠키에 담는 키. `auth.py`와 같은 값을 봐야 한다.
_SESSION_KEY = "user_id"


class Accounts:
    """사용자 조회. 앱 조립 시점에 하나 만들어 라우터들이 나눠 쓴다."""

    def __init__(
        self,
        db: Database,
        *,
        login_required: bool = False,
        credits: Credits | None = None,
    ) -> None:
        """
        Args:
            db: 엔진과 세션 팩토리.
            login_required: 로그인을 강제할 것인가. 카카오·구글 설정이 하나도
                없으면 False로 두어 기본 사용자로 돈다.
            credits: 있으면 새 계정에 가입 크레딧을 준다. 가입 선물은 계정이
                생기는 사실에 딸린 것이라 여기서 준다.
        """
        self._db = db
        self._login_required = login_required
        self._credits = credits
        self._local_id: str | None = None
        self._lock = threading.Lock()

    # ── 요청에서 사용자 알아내기 ─────────────────────────────────────────

    def current_user_id(self, request: Request) -> str:
        """이 요청의 사용자. FastAPI 의존성으로 쓴다.

        로그인이 필요한데 안 했으면 401 — 화면은 이걸 받고 랜딩으로 간다.
        """
        user_id = self.session_user_id(request)
        if user_id is None:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다")
        return user_id

    def session_user_id(self, connection: Request | WebSocket) -> str | None:
        """세션 쿠키가 가리키는 사용자. 없으면 None.

        WebSocket도 같은 쿠키를 읽는다 — 면접 소켓이 인증의 구멍이 되면 안 된다
        (Starlette SessionMiddleware가 http·websocket 스코프를 모두 다룬다).
        """
        if not self._login_required:
            return self.default_user_id()
        user_id = connection.session.get(_SESSION_KEY)
        if not user_id:
            return None
        # 탈퇴한 계정의 쿠키가 남아 있을 수 있다 — 실재를 확인한다.
        with self._db.session() as session:
            return user_id if session.get(User, user_id) is not None else None

    # ── 저장·조회 ────────────────────────────────────────────────────────

    def upsert(
        self,
        *,
        provider: str,
        provider_user_id: str,
        email: str | None = None,
        name: str = "",
        avatar_url: str | None = None,
    ) -> str:
        """로그인한 사람을 찾거나 만든다. 돌려주는 것은 users.id.

        재로그인마다 프로필을 갱신한다 — 이름이나 사진을 바꿨을 수 있다.
        """
        created = False
        with self._db.session() as session:
            found = session.scalar(
                select(User).where(
                    User.provider == provider,
                    User.provider_user_id == provider_user_id,
                )
            )
            if found is None:
                found = User(provider=provider, provider_user_id=provider_user_id)
                session.add(found)
                created = True
                logger.info("새 사용자 (%s)", provider)
            found.email = email
            found.name = name or found.name
            found.avatar_url = avatar_url
            session.flush()
            user_id = found.id
        if created and self._credits is not None:
            self._credits.grant(user_id, SIGNUP_GRANT, "signup_grant")
        return user_id

    def profile(self, user_id: str | None) -> dict[str, Any] | None:
        """화면이 헤더에 그릴 사용자 정보. 로그인 안 했으면 None."""
        if user_id is None:
            return None
        with self._db.session() as session:
            user = session.get(User, user_id)
            if user is None:
                return None
            return {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "avatarUrl": user.avatar_url,
                "provider": user.provider,
            }

    def default_user_id(self) -> str:
        """로그인 없이 도는 동안 모든 데이터의 주인. 없으면 만든다.

        프로세스마다 한 번만 조회한다 — 값이 바뀌지 않는데 요청마다 데이터베이스를
        두드릴 이유가 없다. 준비·평가 워커도 스레드에서 부르므로 잠근다.
        """
        if self._local_id is not None:
            return self._local_id
        with self._lock:
            if self._local_id is None:
                self._local_id = self.upsert(
                    provider=LOCAL_PROVIDER,
                    provider_user_id=_LOCAL_USER_ID,
                    name="지원자",
                )
        return self._local_id
