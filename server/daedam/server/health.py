"""외부 감시가 두드릴 상태 확인.

SPA catch-all(app.py `_mount_frontend`)이 아무 GET에나 index.html을 200으로
돌려주므로, `/`를 보는 감시는 데이터베이스가 잠겼든 디스크가 찼든 늘 정상으로
읽는다. 여기는 실제로 일을 해 본다 — 데이터베이스에 질의 하나, 데이터
디렉터리에 파일 하나.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from daedam.db import Database

logger = logging.getLogger(__name__)


def create_health_router(db: Database, data_root: Path) -> APIRouter:
    router = APIRouter()

    # 감시 도구는 HEAD를 쓰기도 한다 — get만 두면 405가 나 "죽었다"로 읽힌다.
    @router.api_route("/api/health", methods=["GET", "HEAD"])
    def health() -> JSONResponse:
        try:
            with db.session() as session:
                session.execute(text("SELECT 1"))
            probe = data_root / ".health"
            probe.write_text(str(os.getpid()), encoding="utf-8")
            probe.unlink()
        except Exception as exc:  # noqa: BLE001 — 무엇이든 감시가 알아야 한다
            logger.error("상태 확인 실패: %s", exc)
            return JSONResponse(
                status_code=503, content={"status": "fail", "reason": type(exc).__name__}
            )
        return JSONResponse(content={"status": "ok"})

    return router
