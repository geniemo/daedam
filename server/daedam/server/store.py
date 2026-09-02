"""면접 준비 데이터와 면접 기록 저장소.

앞서는 `{data}/{면접 id}/*.json` 파일 구조였다. 단일 사용자 로컬 앱이라 파일이
곧 데이터베이스였고, 그 파일의 첫 주석이 전환 조건을 적어 두었다 — "동시
사용자, 목록 질의, 다중 인스턴스 배포". 회원제로 가면서 셋 다 왔다.

**구조가 하나 바뀌었다.** 준비 데이터(`Application`) 하나에 면접
(`InterviewSession`)이 여러 판 붙는다. 앞서는 카드 하나에 면접 하나뿐이라
다시 면접하면 앞 판의 녹음·전사·피드백을 지웠는데, 반복이 곧 제품 가치라
쌓이는 쪽이 맞다.

**오디오만 파일로 남는다** — `{data}/{준비 id}/{면접 id}/mic.pcm|wav`.
20분 녹음이 수십 MB라 DB에 넣지 않는다. 전사는 녹음이 재접속을 넘겨 이어
쓰려고 같은 디렉터리에 작업 파일로 두고(`recording.py`), 면접이 끝나면 그
전문이 DB로 올라와 질의 대상이 된다.
"""

from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from daedam.db import Application, Database, InterviewSession

logger = logging.getLogger(__name__)

#: 준비·면접 id 허용 형식. URL 경로 조각과 디렉터리 이름으로 쓰이므로
#: 디렉터리 탈출을 막는다.
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass(frozen=True)
class InterviewData:
    """면접 하나의 준비 데이터 묶음.

    DB 행을 그대로 내보내지 않고 이 형태로 옮기는 이유는, 세션이 닫힌 뒤에도
    읽을 수 있어야 하고 순수 로직 계층(`daedam.interview` 등)이 ORM을 몰라야
    하기 때문이다.
    """

    company: str
    role: str
    #: 지원자 이름. 면접관이 부르고 전사 어휘 힌트로도 나간다.
    name: str
    application: list[dict[str, Any]]
    report: list[dict[str, Any]]
    uncertain: list[dict[str, Any]]
    questions: list[dict[str, Any]] | None = None
    #: 전사에 힌트로 줄 낱말. 추출이 실패했으면 None — 브리지가 규칙 폴백을 쓴다.
    vocabulary: list[str] | None = None


@dataclass(frozen=True)
class ApplicationSummary:
    """홈 목록 한 줄."""

    id: str
    company: str
    role: str
    #: 질문 풀까지 있어야 면접을 시작할 수 있다.
    ready: bool
    #: 지금까지 본 면접 수. 지원자가 한 마디도 안 한 것은 세지 않는다.
    interview_count: int
    #: 가장 최근 면접의 점수. **None인 이유가 둘이다** — 아직 분석 전이거나,
    #: 분석은 끝났는데 채점할 답변이 없었거나(지원자가 한 마디도 안 한 면접).
    #: 둘을 가르는 것이 `latest_analyzed`다.
    latest_score: int | None
    #: 가장 최근 면접의 분석이 끝났는가. 화면이 "분석 중"과 "점수 없음"을
    #: 구분하려면 필요하다 — 점수만 보면 끝난 분석을 계속 기다리게 된다.
    latest_analyzed: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class SessionRecord:
    """면접 한 판이 남긴 것 전부 — 전사와 피드백까지."""

    id: str
    application_id: str
    transcript: dict[str, Any] | None
    feedback: dict[str, Any] | None
    ended_at: datetime | None


@dataclass(frozen=True)
class SessionSummary:
    """면접 한 판의 요약 — 이력 목록에 쓴다."""

    id: str
    application_id: str
    started_at: datetime
    ended_at: datetime | None
    score: int | None
    #: 피드백이 만들어졌는가. 없으면 아직 분석 중이거나 실패한 것이다.
    has_feedback: bool
    #: 지원자가 한 마디라도 했는가. 거짓이면 이건 면접 회차가 아니다.
    has_answer: bool


def has_answer(transcript: dict[str, Any] | None) -> bool:
    """이 면접에 지원자의 답변이 하나라도 있는가 — "면접을 봤다"의 기준.

    **면접관 발화는 세지 않는다.** 면접관은 시작하자마자 인사와 첫 질문을
    하므로, 전사가 비어 있지 않다는 것만으로는 아무것도 알 수 없다. 시작하고
    3초 만에 나온 면접도 전사에는 "안녕하세요, 자기소개 부탁드립니다"가 남는다.

    브리지가 크레딧을 되돌릴 때 쓰는 기준과 같아야 한다 — 돌려준 면접이
    이력에 회차로 남으면 앞뒤가 안 맞는다.
    """
    return any(
        u.get("speaker") == "applicant"
        for u in (transcript or {}).get("utterances", [])
    )


def _as_utc(value: datetime | None) -> datetime | None:
    """저장된 시각을 UTC 인식 datetime으로.

    SQLite는 타임존을 보존하지 않아 naive datetime이 돌아온다. 그대로 두면
    `.timestamp()`가 로컬 시간대로 해석해 시각이 어긋난다 — 우리는 늘 UTC로
    쓰므로 여기서 되붙인다. PostgreSQL은 이미 UTC 인식이라 무해하다.
    """
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _to_data(row: Application) -> InterviewData:
    return InterviewData(
        company=row.company,
        role=row.role,
        name=row.applicant_name,
        application=row.application or [],
        report=row.report or [],
        uncertain=row.uncertain or [],
        questions=row.questions,
        vocabulary=row.vocabulary,
    )


def _to_session_summary(row: InterviewSession) -> SessionSummary:
    return SessionSummary(
        id=row.id,
        application_id=row.application_id,
        started_at=_as_utc(row.started_at),
        ended_at=_as_utc(row.ended_at),
        score=row.score,
        has_feedback=row.feedback is not None,
        has_answer=has_answer(row.transcript),
    )


class InterviewStore:
    """준비 데이터·면접 기록의 데이터베이스 저장소."""

    def __init__(self, db: Database, data_root: Path) -> None:
        """
        Args:
            db: 엔진과 세션 팩토리.
            data_root: 녹음이 놓이는 뿌리 디렉터리.
        """
        self._db = db
        self._root = Path(data_root)

    # ── 준비 데이터 ──────────────────────────────────────────────────────

    def save(
        self,
        application_id: str,
        *,
        user_id: str,
        company: str,
        role: str,
        application: list[dict[str, Any]],
        report: list[dict[str, Any]],
        uncertain: list[dict[str, Any]],
        name: str = "",
    ) -> None:
        """준비 데이터를 만들거나 갱신한다.

        등록 직후에도 한 번, 리서치가 끝난 뒤에도 한 번 불린다. 처음에는
        리포트가 비어 있고 그 비어 있음이 "리서치 진행 중"의 표시다 —
        등록되는 순간 저장해야 방금 등록한 카드가 새로고침에 사라지지 않는다.
        """
        self._check_id(application_id)
        with self._db.session() as session:
            row = session.get(Application, application_id)
            if row is None:
                row = Application(id=application_id, user_id=user_id)
                session.add(row)
            row.company = company
            row.role = role
            row.applicant_name = name
            row.application = application
            row.report = report
            row.uncertain = uncertain

    def save_questions(
        self, application_id: str, questions: list[dict[str, Any]]
    ) -> None:
        """생성된 질문 풀을 저장한다. 검토 후 재생성하면 덮어쓴다."""
        self._update(application_id, questions=questions)

    def save_vocabulary(self, application_id: str, vocabulary: list[str]) -> None:
        """전사 어휘 힌트를 저장한다. 질문을 다시 뽑으면 이것도 다시 뽑는다."""
        self._update(application_id, vocabulary=vocabulary)

    def save_report(self, application_id: str, report: list[dict[str, Any]]) -> None:
        """검토·정정이 반영된 리포트로 교체한다."""
        self._update(application_id, report=report)

    def load(self, application_id: str) -> InterviewData | None:
        """준비 데이터를 읽는다. 없거나 id 형식이 어긋나면 None.

        id는 URL에서 오므로 예외 대신 None이다 — 조회 경로에서 이상한 id는
        "없는 면접"과 같은 404로 끝나야 한다. 쓰기는 여전히 거부한다.
        """
        if not _SAFE_ID.match(application_id):
            return None
        with self._db.session() as session:
            row = session.get(Application, application_id)
            return None if row is None else _to_data(row)

    def owner_of(self, application_id: str) -> str | None:
        """이 준비 데이터의 주인. 없으면 None.

        2단계의 소유권 검사가 이걸 쓴다. 지금은 주인이 늘 기본 사용자다.
        """
        if not _SAFE_ID.match(application_id):
            return None
        with self._db.session() as session:
            row = session.get(Application, application_id)
            return None if row is None else row.user_id

    def list_ids(self) -> list[str]:
        """모든 준비 데이터 id — 기동 시 끊긴 준비를 이어받는 복원 스캔용.

        사용자로 나누지 않는다. 복원은 서버가 자기 일을 이어 하는 것이라
        누구의 것인지와 무관하다.
        """
        with self._db.session() as session:
            return list(session.scalars(select(Application.id).order_by(Application.id)))

    def list_for_user(self, user_id: str) -> list[ApplicationSummary]:
        """홈 목록. 최근에 손댄 것이 앞에 온다."""
        with self._db.session() as session:
            rows = session.scalars(
                select(Application)
                .where(Application.user_id == user_id)
                # 목록 한 줄마다 면접 수와 최근 점수가 필요하다. 미리 같이
                # 읽지 않으면 카드 수만큼 추가 질의가 나간다.
                .options(selectinload(Application.sessions))
                .order_by(Application.updated_at.desc())
            ).all()
            return [self._summary(row) for row in rows]

    # ── 면접 기록 ────────────────────────────────────────────────────────

    def start_session(self, application_id: str) -> str:
        """면접 한 판을 연다. 돌려주는 id가 녹음 디렉터리이자 대화 세션 id다."""
        self._check_id(application_id)
        with self._db.session() as session:
            row = InterviewSession(application_id=application_id)
            session.add(row)
            session.flush()
            return row.id

    def resume_or_abandon(
        self, application_id: str, stale_after_s: float
    ) -> tuple[str | None, list[str]]:
        """이어받을 면접 하나와, 오래돼서 닫아 버린 면접들.

        커넥션이 끊긴 것과 면접이 끝난 것은 다르다 — Live 커넥션 수명이 ~10분
        이라 15~20분 면접은 반드시 재접속하고, 그 사이에도 같은 판이 이어져야
        한다. 그래서 "끝나지 않은 면접"은 곧 "진행 중인 면접"이다.

        다만 창을 닫고 다시 오지 않은 면접은 영영 끝나지 않은 채 남는다.
        `stale_after_s`보다 오래된 것은 여기서 닫는다 — 그러지 않으면 며칠 뒤의
        새 면접이 옛 대화를 이어받는다. 닫은 id를 돌려주는 것은 그 면접들도
        피드백을 받아야 하기 때문이다(중간에 끊겼어도 답변은 남아 있다).

        Returns:
            (이어받을 면접 id 또는 None, 방금 닫은 면접 id 목록)
        """
        if not _SAFE_ID.match(application_id):
            return None, []
        now = datetime.now(UTC)
        abandoned: list[str] = []
        resumable: str | None = None
        with self._db.session() as session:
            rows = session.scalars(
                select(InterviewSession)
                .where(
                    InterviewSession.application_id == application_id,
                    InterviewSession.ended_at.is_(None),
                )
                .order_by(InterviewSession.started_at.desc())
            ).all()
            for index, row in enumerate(rows):
                fresh = (now - _as_utc(row.started_at)).total_seconds() <= stale_after_s
                # 가장 최근 것만 이어받는다. 그 앞의 미완들은 어차피 버려진
                # 것이라 함께 닫는다.
                if index == 0 and fresh:
                    resumable = row.id
                    continue
                row.ended_at = now
                abandoned.append(row.id)
        return resumable, abandoned

    def save_transcript(self, session_id: str, transcript: dict[str, Any]) -> None:
        """전사 전문을 올린다. 커넥션이 끊길 때마다 불려 최신본으로 덮는다."""
        with self._db.session() as session:
            row = session.get(InterviewSession, session_id)
            if row is not None:
                row.transcript = transcript

    def end_session(self, session_id: str) -> None:
        """면접이 끝났다 — 이 판은 다시 이어받지 않는다.

        커넥션이 끊긴 것과는 구분한다. 여기까지 와야 다음 접속이 새 면접이 된다.
        """
        with self._db.session() as session:
            row = session.get(InterviewSession, session_id)
            if row is not None and row.ended_at is None:
                row.ended_at = datetime.now(UTC)

    def save_feedback(self, session_id: str, feedback: dict[str, Any]) -> None:
        """면접이 끝난 뒤 만든 피드백을 저장한다."""
        with self._db.session() as session:
            row = session.get(InterviewSession, session_id)
            if row is not None:
                row.feedback = feedback

    def load_session(self, session_id: str) -> SessionRecord | None:
        """면접 한 판. 전사·피드백까지 실려 온다."""
        if not _SAFE_ID.match(session_id):
            return None
        with self._db.session() as session:
            row = session.get(InterviewSession, session_id)
            if row is None:
                return None
            return SessionRecord(
                id=row.id,
                application_id=row.application_id,
                transcript=row.transcript,
                feedback=row.feedback,
                ended_at=_as_utc(row.ended_at),
            )

    def latest_session(self, application_id: str) -> SessionSummary | None:
        """이 준비 데이터로 본 가장 최근 면접. 한 번도 안 봤으면 None."""
        if not _SAFE_ID.match(application_id):
            return None
        with self._db.session() as session:
            row = session.scalars(
                select(InterviewSession)
                .where(InterviewSession.application_id == application_id)
                .order_by(InterviewSession.started_at.desc())
                .limit(1)
            ).first()
            return None if row is None else _to_session_summary(row)

    def list_sessions(self, application_id: str) -> list[SessionSummary]:
        """면접 이력 — 최근 것이 앞에 온다."""
        if not _SAFE_ID.match(application_id):
            return []
        with self._db.session() as session:
            rows = session.scalars(
                select(InterviewSession)
                .where(InterviewSession.application_id == application_id)
                .order_by(InterviewSession.started_at.desc())
            ).all()
            return [_to_session_summary(row) for row in rows]

    # ── 파일 ─────────────────────────────────────────────────────────────

    def session_directory(self, application_id: str, session_id: str) -> Path:
        """면접 한 판의 녹음이 놓이는 곳.

        준비 데이터 아래에 두어 같은 카드의 면접들이 한자리에 모이게 한다 —
        디렉터리를 눈으로 훑을 때 "이 회사의 몇 번째 면접"이 보여야 한다.
        """
        self._check_id(application_id)
        self._check_id(session_id)
        return self._root / application_id / session_id

    def delete_user_files(self, user_id: str) -> int:
        """이 사용자의 녹음을 디스크에서 지운다. 돌려주는 것은 지운 디렉터리 수.

        DB 행은 외래 키가 지우지만 오디오는 파일이라 여기서 지워야 한다.
        **계정을 지우기 전에 부른다** — 지우고 나면 어느 준비 데이터가 그
        사람 것이었는지 알 수 없다.

        음성은 가장 민감한 개인정보라, 실패해도 조용히 넘어가지 않고 남긴다.
        """
        removed = 0
        for item in self.list_for_user(user_id):
            directory = self._root / item.id
            if not directory.exists():
                continue
            try:
                shutil.rmtree(directory)
                removed += 1
            except OSError:
                logger.exception("녹음 삭제 실패 (%s)", directory)
        return removed

    # ── 내부 ─────────────────────────────────────────────────────────────

    def _summary(self, row: Application) -> ApplicationSummary:
        # 지원자가 한 마디도 안 한 것은 세지 않는다 — 시작만 하고 나온 것은
        # "면접을 봤다"가 아니다. 세면 카드가 없던 일의 결과를 보여준다.
        answered = [s for s in row.sessions if has_answer(s.transcript)]
        latest = max(answered, key=lambda s: s.started_at, default=None)
        return ApplicationSummary(
            id=row.id,
            company=row.company,
            role=row.role,
            ready=row.questions is not None,
            interview_count=len(answered),
            latest_score=None if latest is None else latest.score,
            latest_analyzed=latest is not None and latest.feedback is not None,
            created_at=_as_utc(row.created_at),
            updated_at=_as_utc(row.updated_at),
        )

    def _update(self, application_id: str, **fields: Any) -> None:
        self._check_id(application_id)
        with self._db.session() as session:
            row = session.get(Application, application_id)
            if row is None:
                raise ValueError(f"준비 데이터가 없습니다: {application_id}")
            for key, value in fields.items():
                setattr(row, key, value)

    @staticmethod
    def _check_id(value: str) -> None:
        if not _SAFE_ID.match(value):
            raise ValueError(f"허용되지 않는 id: {value!r}")
