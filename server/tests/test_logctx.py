"""로그 줄의 세션 표지 — 동시 면접의 로그를 가르는 단서."""

import asyncio
import logging

from daedam.logctx import SessionTag, current_session


def _record() -> logging.LogRecord:
    record = logging.LogRecord("interviewer.tools", logging.INFO, __file__, 1, "뼈대질문 배달", (), None)
    SessionTag().filter(record)
    return record


def test_면접_밖에서는_표지가_없다() -> None:
    assert _record().session_tag == ""


def test_면접_안에서는_세션_앞_8자가_붙는다() -> None:
    token = current_session.set("dddb078272074d89ac19b192fdecbba9")
    try:
        assert _record().session_tag == " [session=dddb0782]"
    finally:
        current_session.reset(token)


def test_태스크와_스레드로_따라간다() -> None:
    """브리지가 커넥션 코루틴에서 한 번 두면 펌프 태스크와 to_thread의 툴 호출까지 같은 값을 본다."""

    async def connection() -> tuple[str, str]:
        current_session.set("abcdef0123456789")
        in_task = await asyncio.create_task(_tag())
        in_thread = await asyncio.to_thread(lambda: _record().session_tag)
        return in_task, in_thread

    async def _tag() -> str:
        return _record().session_tag

    assert asyncio.run(connection()) == (" [session=abcdef01]", " [session=abcdef01]")
