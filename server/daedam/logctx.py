"""로그 줄에 면접 세션 id를 붙인다.

면접 둘이 동시에 돌면 브리지·툴의 로그가 한 줄씩 섞인다. 줄마다 어느 면접인지
적혀 있지 않으면 사후에 가를 수 없다 — 실측: 동시 2건의 로그를 지표 스크립트가
한 면접으로 읽어 게이트 준수율이 엉뚱하게 나왔다.

브리지가 커넥션의 컨텍스트에 세션 id를 두면(`current_session.set`), 그 태스크에서
나온 모든 로그 레코드에 필터가 ` [session=앞8자]`를 단다. 툴은 서버를 모르는
채로 그대로 찍고, 컨텍스트가 asyncio 태스크와 `asyncio.to_thread`로 따라간다
(contextvars — 태스크 생성·to_thread 모두 현재 컨텍스트를 복사한다).
"""

from __future__ import annotations

import logging
from contextvars import ContextVar

#: 지금 이 태스크가 다루는 면접 세션 id. 면접 밖에서는 빈 문자열.
current_session: ContextVar[str] = ContextVar("current_session", default="")


class SessionTag(logging.Filter):
    """레코드에 `session_tag`를 붙인다 — 포맷 문자열이 `%(session_tag)s`로 읽는다."""

    def filter(self, record: logging.LogRecord) -> bool:
        session = current_session.get()
        record.session_tag = f" [session={session[:8]}]" if session else ""
        return True
