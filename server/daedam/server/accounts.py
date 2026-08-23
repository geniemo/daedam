"""사용자 조회 — 라우트가 "지금 누구인가"를 묻는 자리.

지금은 인증이 없어서 모든 데이터가 한 사람의 것이다. 그 한 사람을 여기서
만든다 — 스키마는 이미 다중 사용자인데 그 자리를 채울 사람이 아직 없기
때문이다. 2단계에서 카카오·구글 로그인이 붙으면 `current_user_id`가 요청의
세션 쿠키를 읽도록 바뀌고, 그것을 부르는 라우트들은 그대로다.

스키마를 먼저 다 세우는 이유는 단계마다 데모가 되어야 하기 때문이다. 인증
단계의 diff가 작아지고, 기존 행에 NOT NULL 외래 키를 추가하는 마이그레이션도
피할 수 있다.
"""

from __future__ import annotations

import logging
import threading

from sqlalchemy import select

from daedam.db import Database, User

logger = logging.getLogger(__name__)

#: 인증 없이 도는 동안 쓰는 가상 제공자. 실제 OAuth 제공자("kakao"·"google")와
#: 겹치지 않으므로 나중에 진짜 계정이 생겨도 이 행과 충돌하지 않는다.
LOCAL_PROVIDER = "local"
_LOCAL_USER_ID = "single-user"


class Accounts:
    """사용자 조회. 앱 조립 시점에 하나 만들어 라우터들이 나눠 쓴다."""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._local_id: str | None = None
        self._lock = threading.Lock()

    def current_user_id(self) -> str:
        """이 요청의 사용자.

        FastAPI 의존성으로 쓰인다(`Depends(accounts.current_user_id)`).
        인증이 붙기 전까지는 늘 기본 사용자다.
        """
        return self.default_user_id()

    def default_user_id(self) -> str:
        """인증이 붙기 전까지 모든 데이터의 주인. 없으면 만든다.

        프로세스마다 한 번만 조회한다 — 값이 바뀌지 않는데 요청마다 DB를
        두드릴 이유가 없다. 준비·평가 워커도 스레드에서 부르므로 잠근다.
        """
        if self._local_id is not None:
            return self._local_id
        with self._lock:
            if self._local_id is None:
                self._local_id = self._ensure_local_user()
        return self._local_id

    def _ensure_local_user(self) -> str:
        with self._db.session() as session:
            found = session.scalar(
                select(User).where(
                    User.provider == LOCAL_PROVIDER,
                    User.provider_user_id == _LOCAL_USER_ID,
                )
            )
            if found is not None:
                return found.id
            user = User(
                provider=LOCAL_PROVIDER, provider_user_id=_LOCAL_USER_ID, name="지원자"
            )
            session.add(user)
            session.flush()
            logger.info("기본 사용자를 만들었습니다 (id=%s)", user.id)
            return user.id
