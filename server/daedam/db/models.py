"""데이터베이스 모델 — 사용자 · 준비 데이터 · 면접 기록.

핵심은 **준비 데이터(`Application`)와 면접 기록(`InterviewSession`)의 분리**다.
준비는 리서치 한 건당 $1~3이라 재사용해야 하고, 면접은 반복하는 것이 곧 제품
가치다. 앞서 파일 저장소에서는 카드 하나에 면접 하나뿐이라 두 번째 면접이 첫
면접의 녹음·전사·피드백을 지웠다.

**오디오는 여기 없다.** 20분 녹음이 수십 MB라 디스크에 남기고
(`data/{application_id}/{session_id}/mic.wav`) DB에는 경로가 유도 가능한
id만 둔다. 전사·피드백은 JSON 칼럼으로 여기 있다 — "지난 면접들"을 질의해야
하고, 파일과 DB로 나뉘면 정합성을 두 곳에서 지켜야 한다.

JSON 칼럼은 `sqlalchemy.JSON`이다. SQLite와 PostgreSQL 양쪽에서 같은 코드로
돌아야 하기 때문이다 — 배포 시점에 `DATABASE_URL`만 바꿔 옮긴다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    """저장 시각. UTC로 통일한다 — 배포 지역이 바뀌어도 뜻이 변하지 않게."""
    return datetime.now(UTC)


def _new_id() -> str:
    """새 식별자. URL 경로와 디렉터리 이름으로 쓰이므로 하이픈 없는 hex다."""
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    """모든 모델의 뿌리. Alembic이 이 metadata를 보고 마이그레이션을 만든다."""


class User(Base):
    """가입한 사용자.

    비밀번호가 없다 — 로그인은 카카오·구글 OAuth뿐이다. 비밀번호를 받는 순간
    해싱·재설정 메일·이메일 인증·계정 잠금이 따라오는데, 국내 서비스에서
    소셜 로그인만으로 대부분 커버된다.
    """

    __tablename__ = "users"
    # 같은 제공자의 같은 계정은 하나다. 재로그인은 이 쌍으로 찾아 붙인다.
    __table_args__ = (UniqueConstraint("provider", "provider_user_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    #: "kakao" 또는 "google".
    provider: Mapped[str] = mapped_column(String(16))
    #: 제공자가 매기는 사용자 id. 제공자마다 형식이 달라 문자열로 받는다.
    provider_user_id: Mapped[str] = mapped_column(String(128))
    #: 카카오는 이메일이 선택 동의라 못 받을 수 있다.
    email: Mapped[str | None] = mapped_column(String(320), default=None)
    #: 면접관이 부르는 이름이자 전사 어휘 힌트로도 나간다 — ASR이 가장 자주
    #: 틀리는 낱말이다(실측 "박지원" → "박지훈").
    name: Mapped[str] = mapped_column(String(64), default="")
    avatar_url: Mapped[str | None] = mapped_column(String(512), default=None)
    #: 온보딩(이름 입력 + 약관·개인정보 동의) 완료 시각. null이면 미완 — 화면이
    #: 온보딩으로 보낸다. 동의 시각을 남기는 것이 목적의 절반이다: 음성·영상·
    #: 얼굴 스틸을 AI로 처리하는 서비스라 "언제 동의했는가"가 기록으로 남아야 한다.
    onboarded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    applications: Mapped[list[Application]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Application(Base):
    """면접 하나의 준비 데이터 — 회사·직무·지원서와 그 위에 만든 것들.

    화면에서는 "카드"다. id가 리서치 task_id와 같다 — 등록하는 순간 리서치가
    시작되고 그 id로 진행 상황을 조회하기 때문이다.
    """

    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    company: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(128))
    #: 지원자 이름. 가입자 이름과 다를 수 있어 여기에도 둔다(대리 작성·가명).
    applicant_name: Mapped[str] = mapped_column(String(64), default="")

    #: 지원서 파트 목록.
    application: Mapped[list[Any]] = mapped_column(JSON, default=list)
    #: 리서치 리포트 섹션 목록. 비어 있으면 리서치가 아직 안 끝난 것이다.
    report: Mapped[list[Any]] = mapped_column(JSON, default=list)
    #: 리서치가 확신하지 못한 항목 — 검토 화면이 사용자에게 확인받는다.
    uncertain: Mapped[list[Any]] = mapped_column(JSON, default=list)
    #: 질문 풀. None이면 아직 안 뽑혔다 = 면접을 시작할 수 없다.
    questions: Mapped[list[Any] | None] = mapped_column(JSON, default=None)
    #: 전사 어휘 힌트. 추출에 실패하면 None이고 브리지가 규칙 폴백을 쓴다.
    vocabulary: Mapped[list[str] | None] = mapped_column(JSON, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    user: Mapped[User] = relationship(back_populates="applications")
    sessions: Mapped[list[InterviewSession]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="InterviewSession.started_at",
    )


class InterviewSession(Base):
    """면접 한 판.

    같은 준비 데이터로 몇 번이든 면접할 수 있고, 판마다 이 행이 하나씩 생긴다.
    이 id가 세 곳에서 같이 쓰인다 — 녹음 디렉터리 이름, ADK 대화 세션 id,
    그리고 프론트가 결과를 조회하는 키. 셋이 같아야 "이 면접"이 하나로 묶인다.

    특히 ADK 세션 id로 쓰는 것이 중요하다. 앞서는 카드 id를 세션 id로 썼는데,
    면접을 여러 번 하게 되면 두 번째 면접이 첫 면접의 대화 이력을 이어받는다.
    """

    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    #: 면접이 끝난 시각. None이면 아직 진행 중이거나 끝을 못 보고 끊긴 것이다.
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    #: 누가 언제 무엇을 말했는가. 녹음이 끝날 때 브리지가 채운다.
    transcript: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    #: 음성 지표 + 코칭. 면접이 끝난 뒤 평가 파이프라인이 채운다.
    feedback: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)

    application: Mapped[Application] = relationship(back_populates="sessions")

    @property
    def score(self) -> int | None:
        """코칭 점수. 피드백이 아직 없으면 None."""
        return ((self.feedback or {}).get("coaching") or {}).get("score")


class CreditEntry(Base):
    """크레딧이 늘고 준 기록 한 줄. 잔액은 이 행들의 합이다.

    잔액을 칼럼 하나로 들고 있지 않은 이유: 언제 왜 늘고 줄었는지가 남아야
    환불·정산·문의 대응이 된다. "왜 크레딧이 줄었냐"는 물음에 답할 수 없는
    서비스는 결제를 붙일 수 없다.

    실패한 리서치처럼 되돌려야 하는 일도 지우기가 아니라 반대 부호의 행을
    더해서 처리한다 — 기록은 고치지 않는다.
    """

    __tablename__ = "credit_entries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    #: 양수면 지급, 음수면 차감.
    delta: Mapped[int] = mapped_column(Integer)
    #: signup_grant · research · interview · refund · purchase · admin_grant.
    reason: Mapped[str] = mapped_column(String(32))
    #: 무엇 때문인가 — 준비 데이터 id 또는 면접 id. 지급에는 없다.
    ref_id: Mapped[str | None] = mapped_column(String(64), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Coupon(Base):
    """크레딧을 얹어 주는 코드.

    결제(PG)가 붙기 전까지 사용자가 크레딧을 늘릴 수 있는 유일한 길이다. 국내
    PG는 사업자등록증이 있어야 계약되므로, 그전까지는 홍보 영상이나 초대 메일로
    코드를 뿌려 초기 사용자를 받는다.

    누가 언제 썼는지는 여기 세지 않고 원장(`CreditEntry`)이 안다 —
    `reason="purchase"`, `ref_id=코드`. 그래서 같은 사람이 같은 코드를 두 번
    쓰는 것도 원장 조회로 막는다. 사용 횟수(`used_count`)만 여기 둔다.
    """

    __tablename__ = "coupons"

    #: 사람이 입력하는 코드. 대문자로 정규화해 저장한다 — 손으로 치는 값이라
    #: 대소문자로 갈리면 안 된다.
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    #: 이 코드가 주는 크레딧.
    credits: Mapped[int] = mapped_column(Integer)
    #: 몇 명까지 쓸 수 있는가. 1이면 일회용, 100이면 선착순 100명.
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    #: 만료 시각. None이면 만료 없음.
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    #: 무엇 때문에 발급했는지 — "홍보영상 1차", "베타테스터" 같은 메모.
    #: 나중에 어느 경로로 들어온 사용자인지 세는 근거가 된다.
    note: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

