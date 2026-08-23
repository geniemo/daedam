"""데이터베이스 엔진과 세션 팩토리.

**동기 SQLAlchemy를 쓴다.** 준비·평가 파이프라인이 전담 스레드로 돌고
(`preparation.py`·`evaluation.py`) FastAPI 라우트도 동기 함수라 스레드풀에서
실행된다. 여기에 async를 끼우면 스레드마다 이벤트 루프를 세워야 한다 —
얻는 것 없이 복잡해진다.

ADK의 대화 세션 저장소만 async를 요구하므로(`DatabaseSessionService`가
`create_async_engine`을 쓴다), 그쪽에는 `async_url`로 같은 데이터베이스를
가리키는 async URL을 준다. 엔진 둘이 한 데이터베이스를 보는 형태이고,
서로의 테이블을 건드리지 않는다.

`DATABASE_URL`로 갈아 끼운다. 기본은 데이터 디렉터리의 SQLite 파일이고,
배포에서 PostgreSQL로 옮길 때 이 환경변수만 바꾼다 — 드라이버(`asyncpg`)는
미리 넣어 두었다.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

#: SQLite 파일 이름. 데이터 디렉터리에 녹음과 나란히 놓인다.
_SQLITE_NAME = "daedam.db"


def database_url(data_root: Path) -> str:
    """이 서버가 쓸 데이터베이스 URL. `DATABASE_URL`이 있으면 그것이 우선이다."""
    configured = os.environ.get("DATABASE_URL")
    if configured:
        return configured
    return f"sqlite:///{(data_root / _SQLITE_NAME).resolve()}"


def async_url(url: str) -> str:
    """같은 데이터베이스를 가리키는 async 드라이버 URL.

    ADK의 `DatabaseSessionService`가 async 엔진을 만들기 때문에 필요하다.
    동기 드라이버 이름만 바꿔 준다 — 그 외에는 같은 URL이다.
    """
    for sync_driver, async_driver in (
        ("sqlite://", "sqlite+aiosqlite://"),
        ("postgresql+psycopg2://", "postgresql+asyncpg://"),
        ("postgresql://", "postgresql+asyncpg://"),
    ):
        if url.startswith(sync_driver):
            return async_driver + url[len(sync_driver) :]
    return url


def create_db_engine(url: str) -> Engine:
    """엔진을 만든다. SQLite면 다중 스레드에서 쓸 수 있게 손본다."""
    if url.startswith("sqlite"):
        # SQLite는 없는 디렉터리에 파일을 만들지 못한다. 첫 기동이나 새로 잡은
        # DAEDAM_DATA_DIR에서 여기 걸린다.
        path = url.split("///", 1)[-1]
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            url,
            # 준비·평가 워커가 각자 스레드에서 접속한다. SQLite 드라이버의
            # 기본값은 커넥션을 만든 스레드에서만 쓰게 막는데, SQLAlchemy가
            # 커넥션 풀로 스레드 안전성을 보장하므로 이 검사를 끈다.
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(connection, _record):  # type: ignore[no-untyped-def]
            cursor = connection.cursor()
            # WAL이 아니면 쓰기 하나가 모든 읽기를 막는다. 면접이 도는 동안
            # 녹음 저장과 홈 목록 조회가 겹치므로 필요하다.
            cursor.execute("PRAGMA journal_mode=WAL")
            # 잠금이 풀릴 때까지 5초 기다린다 — 기본값은 즉시 실패다.
            cursor.execute("PRAGMA busy_timeout=5000")
            # 외래 키 제약은 SQLite에서 기본이 꺼져 있다. 켜지 않으면
            # ondelete=CASCADE가 조용히 무시된다.
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    return create_engine(url, pool_pre_ping=True)


class Database:
    """엔진 하나와 그 위의 세션 팩토리.

    앱 조립 시점에 하나 만들어 저장소·인증·크레딧이 나눠 쓴다. 테스트는
    인메모리 SQLite로 만들어 끼운다.
    """

    def __init__(self, url: str) -> None:
        self.url = url
        self.engine = create_db_engine(url)
        self._session_factory = sessionmaker(
            bind=self.engine, expire_on_commit=False, class_=Session
        )

    def create_all(self) -> None:
        """테이블을 만든다 — 테스트와 첫 기동용.

        운영 스키마 변경은 Alembic이 맡는다. 여기서 만든 스키마와 마이그레이션이
        어긋나지 않도록, 모델을 고치면 마이그레이션도 함께 만들 것.
        """
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """트랜잭션 하나. 빠져나올 때 커밋하고, 예외가 나면 되돌린다."""
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
