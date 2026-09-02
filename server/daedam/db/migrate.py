"""기동 시 스키마를 최신으로 올린다.

서버를 띄우는 것 말고 따로 할 일이 없어야 한다는 요구에서 나왔다 — 배포가
단일 인스턴스라 기동 시 마이그레이션이 안전하다. 여러 인스턴스를 띄우게 되면
이 호출을 빼고 배포 파이프라인에서 `alembic upgrade head`를 한 번만 돌려야
한다(동시에 여러 프로세스가 올리면 서로 막는다).

확인 경로: alembic 1.x 공식 API — `alembic.config.Config` + `alembic.command`.
"""

from __future__ import annotations

import logging

from alembic import command
from alembic.config import Config

from daedam.settings import SERVER_DIR

logger = logging.getLogger(__name__)


def upgrade_to_head() -> None:
    """마이그레이션을 끝까지 적용한다.

    URL은 alembic/env.py가 앱과 같은 경로에서 가져오므로 여기서 넘기지 않는다.
    """
    config = Config(str(SERVER_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(SERVER_DIR / "alembic"))
    # 앱의 로깅 설정을 건드리지 말라는 표시. alembic/env.py가 이걸 본다 —
    # 그러지 않으면 마이그레이션 한 번에 앱 로거가 전부 죽는다.
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")
    logger.info("데이터베이스 스키마를 최신으로 올렸습니다")
