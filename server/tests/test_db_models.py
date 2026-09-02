"""DB 모델·엔진 — 관계와 SQLite 설정.

인메모리가 아니라 임시 파일 SQLite를 쓴다. 실제 기동에서 켜는 PRAGMA(WAL·
외래 키)가 파일 데이터베이스에서만 뜻을 갖고, 다중 스레드 접속도 파일에서만
재현되기 때문이다.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from daedam.db import Application, Database, InterviewSession, User
from daedam.db.engine import async_url, database_url


@pytest.fixture
def db(tmp_path) -> Database:
    database = Database(f"sqlite:///{tmp_path / 'test.db'}")
    database.create_all()
    return database


def _user(session, name: str = "박지원") -> User:
    user = User(provider="kakao", provider_user_id="1", name=name)
    session.add(user)
    session.flush()
    return user


def test_준비_데이터_하나에_면접이_여러_판_붙는다(db: Database) -> None:
    """카드 하나에 면접 하나였던 것이 바뀐 자리 — 두 번째 면접이 첫 면접을
    지우지 않는다."""
    with db.session() as session:
        user = _user(session)
        application = Application(
            id="card-1", user_id=user.id, company="SK 하이닉스", role="기반기술"
        )
        session.add(application)
        session.add_all(
            [
                InterviewSession(application_id="card-1"),
                InterviewSession(application_id="card-1"),
            ]
        )

    with db.session() as session:
        application = session.get(Application, "card-1")
        assert len(application.sessions) == 2
        assert {s.application_id for s in application.sessions} == {"card-1"}


def test_피드백이_없으면_점수도_없다(db: Database) -> None:
    with db.session() as session:
        user = _user(session)
        session.add(Application(id="card-1", user_id=user.id, company="c", role="r"))
        interview = InterviewSession(application_id="card-1")
        session.add(interview)
        session.flush()
        assert interview.score is None
        interview.feedback = {"coaching": {"score": 63}}
        assert interview.score == 63


def test_같은_제공자의_같은_계정은_하나다(db: Database) -> None:
    from sqlalchemy.exc import IntegrityError

    with db.session() as session:
        session.add(User(provider="kakao", provider_user_id="1"))
    with pytest.raises(IntegrityError):
        with db.session() as session:
            session.add(User(provider="kakao", provider_user_id="1"))
    # 제공자가 다르면 같은 id라도 다른 사람이다.
    with db.session() as session:
        session.add(User(provider="google", provider_user_id="1"))


def test_사용자를_지우면_준비_데이터와_면접도_지워진다(db: Database) -> None:
    """SQLite는 외래 키 제약이 기본으로 꺼져 있어, PRAGMA를 켜지 않으면
    이 테스트가 조용히 실패한다."""
    with db.session() as session:
        user = _user(session)
        session.add(Application(id="card-1", user_id=user.id, company="c", role="r"))
        session.add(InterviewSession(id="s1", application_id="card-1"))

    with db.session() as session:
        session.delete(session.get(User, session.scalars(select(User)).one().id))

    with db.session() as session:
        assert session.get(Application, "card-1") is None
        assert session.get(InterviewSession, "s1") is None


def test_기본_url은_데이터_디렉터리의_sqlite_파일(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert database_url(tmp_path).endswith("daedam.db")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    assert database_url(tmp_path) == "postgresql://x/y"


def test_async_url은_드라이버만_바꾼다() -> None:
    assert async_url("sqlite:////tmp/a.db") == "sqlite+aiosqlite:////tmp/a.db"
    assert async_url("postgresql://u@h/d") == "postgresql+asyncpg://u@h/d"
    assert async_url("postgresql+asyncpg://u@h/d") == "postgresql+asyncpg://u@h/d"
