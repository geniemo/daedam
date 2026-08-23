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
# 로깅 설정은 `alembic` 명령으로 직접 돌릴 때만 한다. 앱이 기동 중에 부를
# 때는(`daedam.db.migrate`) 건드리면 안 된다 — fileConfig가 기존 로거를
# 끄고 루트 포매터까지 갈아 치워서, 그 뒤의 면접 로그가 사라지고 남은 것도
# 시각을 잃는다(실측). 시각이 없으면 재연결 루프와 사용자가 직접 들락거린
# 것을 구분할 수 없다.
if config.config_file_name is not None and config.attributes.get(
    "configure_logger", True
):
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
