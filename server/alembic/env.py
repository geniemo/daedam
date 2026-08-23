"""Alembic 실행 환경.

URL은 alembic.ini가 아니라 앱과 같은 경로에서 가져온다(`daedam.db.database_url`)
— 두 곳에 적어 두면 마이그레이션을 엉뚱한 데이터베이스에 돌리게 된다.
`DATABASE_URL`을 설정하면 그것이 우선이므로 배포에서도 같은 명령이 통한다.

    cd server && uv run alembic upgrade head

SQLite에는 `render_as_batch`가 필요하다. SQLite는 칼럼 변경·삭제를 위한 ALTER
TABLE을 대부분 지원하지 않아서, Alembic이 임시 테이블을 만들어 옮기는 방식으로
우회한다. 이 옵션이 없으면 첫 스키마 변경에서 막힌다.
"""

from logging.config import fileConfig

from alembic import context

from daedam.db import database_url
from daedam.db.engine import create_db_engine
from daedam.db.models import Base
from daedam.settings import data_root

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

url = database_url(data_root())
config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))

target_metadata = Base.metadata
_batch = url.startswith("sqlite")


def run_migrations_offline() -> None:
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_batch,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # 앱과 같은 경로로 엔진을 만든다 — SQLite PRAGMA(외래 키 등)와 디렉터리
    # 생성이 마이그레이션에도 똑같이 적용되어야 한다.
    with create_db_engine(url).connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=_batch,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
