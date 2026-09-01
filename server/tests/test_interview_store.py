"""준비 데이터·면접 기록 저장소 테스트."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from conftest import make_store

from daedam.db import InterviewSession

REPORT = [{"title": "개요", "blocks": [{"type": "p", "text": "본문"}]}]
APPLICATION = [{"part": "자소서", "items": [{"title": "지원동기", "body": "본문"}]}]
UNCERTAIN = [{"si": 0, "bi": 0, "title": "확인", "reason": "근거 부족"}]
QUESTIONS = [{"id": "q-0-0", "stage": 0, "text": "질문?", "priority": 1, "tags": ["태그"]}]


@pytest.fixture
def store_bundle(tmp_path: Path):
    return make_store(tmp_path / "data")


def _save(store, user_id: str, application_id: str = "abc") -> None:
    store.save(
        application_id,
        user_id=user_id,
        company="한결물류",
        role="데이터 엔지니어",
        application=APPLICATION,
        report=REPORT,
        uncertain=UNCERTAIN,
    )


def test_저장하고_그대로_읽는다(store_bundle) -> None:
    store, _, user_id = store_bundle
    _save(store, user_id)

    data = store.load("abc")
    assert data.company == "한결물류" and data.role == "데이터 엔지니어"
    assert data.report == REPORT and data.application == APPLICATION
    assert data.uncertain == UNCERTAIN
    assert data.questions is None  # 질문은 생성 뒤에 온다


def test_질문은_나중에_붙는다(store_bundle) -> None:
    store, _, user_id = store_bundle
    _save(store, user_id)
    store.save_questions("abc", QUESTIONS)
    assert store.load("abc").questions == QUESTIONS


def test_검토된_리포트로_교체된다(store_bundle) -> None:
    store, _, user_id = store_bundle
    _save(store, user_id)
    corrected = [{"title": "개요", "blocks": [{"type": "p", "text": "정정된 본문"}]}]
    store.save_report("abc", corrected)
    assert store.load("abc").report == corrected


def test_저장된_적_없으면_None(store_bundle) -> None:
    store, _, _ = store_bundle
    assert store.load("없는것") is None


def test_저장된_면접_id_목록(store_bundle) -> None:
    store, _, user_id = store_bundle
    _save(store, user_id, "b")
    _save(store, user_id, "a")
    assert store.list_ids() == ["a", "b"]


def test_남의_목록에는_안_보인다(store_bundle) -> None:
    store, _, user_id = store_bundle
    _save(store, user_id)
    assert [item.id for item in store.list_for_user(user_id)] == ["abc"]
    assert store.list_for_user("남") == []
    assert store.owner_of("abc") == user_id


def test_경로_탈출_id는_차단된다(store_bundle) -> None:
    """면접 id는 URL에서 오므로 디렉터리 탈출을 막아야 한다.

    조회는 조용히 None(→404), 쓰기는 예외 — 어느 쪽도 파일시스템에 닿지 않는다.
    """
    store, _, _ = store_bundle
    assert store.load("../../etc/passwd") is None
    with pytest.raises(ValueError, match="허용되지 않는"):
        store.save_questions("../../etc/passwd", QUESTIONS)


# ── 면접 기록 ────────────────────────────────────────────────────────────


def test_같은_준비_데이터로_여러_판_본다(store_bundle) -> None:
    """앞 판을 지우지 않는 것이 이번 구조 변경의 핵심이다."""
    store, _, user_id = store_bundle
    _save(store, user_id)
    first = store.start_session("abc")
    store.save_transcript(first, {"utterances": [{"text": "첫 판"}]})
    store.save_feedback(first, {"coaching": {"score": 60}})
    store.end_session(first)

    second = store.start_session("abc")
    assert second != first
    assert store.load_session(first).transcript == {"utterances": [{"text": "첫 판"}]}
    assert [s.id for s in store.list_sessions("abc")] == [second, first]
    assert store.latest_session("abc").id == second


#: 지원자가 한 마디라도 한 전사. 이게 있어야 면접 회차로 센다.
_ANSWERED = {
    "durationS": 40.0,
    "utterances": [
        {"speaker": "interviewer", "text": "자기소개 부탁드립니다.", "at": 1.0},
        {"speaker": "applicant", "text": "박지원입니다.", "at": 5.0},
    ],
}


def test_홈_목록은_본_면접_수와_최근_점수를_센다(store_bundle) -> None:
    """세는 단위는 "지원자가 답한 면접"이다. 면접관 인사만 남은 판은 세지 않는다 —
    면접관은 시작하자마자 말하므로 전사가 있다는 것만으로는 아무것도 모른다."""
    store, _, user_id = store_bundle
    _save(store, user_id)

    done = store.start_session("abc")
    store.save_transcript(done, _ANSWERED)
    store.save_feedback(done, {"coaching": {"score": 71}})
    store.end_session(done)

    running = store.start_session("abc")  # 답은 했고 아직 분석 전
    store.save_transcript(running, _ANSWERED)

    # 시작하자마자 나온 판 — 면접관 인사만 남았다. 회차가 아니다.
    bailed = store.start_session("abc")
    store.save_transcript(bailed, {"durationS": 6.4, "utterances": [
        {"speaker": "interviewer", "text": "안녕하세요. 자기소개 부탁드립니다.", "at": 1.0},
    ]})

    [summary] = store.list_for_user(user_id)
    assert summary.interview_count == 2
    assert summary.latest_score is None  # 가장 최근 회차는 아직 분석 전
    assert summary.latest_analyzed is False


def test_끊긴_면접은_이어받고_오래된_것은_닫는다(store_bundle) -> None:
    """커넥션이 끊긴 것과 면접이 끝난 것은 다르다 — 15~20분 면접은 반드시
    재접속한다. 다만 창을 닫고 안 돌아온 판까지 이어받으면 안 된다."""
    store, _, user_id = store_bundle
    _save(store, user_id)
    ongoing = store.start_session("abc")

    resumable, abandoned = store.resume_or_abandon("abc", stale_after_s=3600)
    assert resumable == ongoing and abandoned == []

    # 시작 시각을 과거로 밀어 "돌아오지 않은 면접"을 만든다.
    with store._db.session() as session:
        session.get(InterviewSession, ongoing).started_at = datetime.now(UTC) - timedelta(
            hours=3
        )

    resumable, abandoned = store.resume_or_abandon("abc", stale_after_s=3600)
    assert resumable is None and abandoned == [ongoing]
    assert store.load_session(ongoing).ended_at is not None


def test_끝난_면접은_이어받지_않는다(store_bundle) -> None:
    store, _, user_id = store_bundle
    _save(store, user_id)
    finished = store.start_session("abc")
    store.end_session(finished)
    assert store.resume_or_abandon("abc", stale_after_s=3600) == (None, [])


def test_녹음은_준비_데이터_아래_면접별로_나뉜다(store_bundle) -> None:
    store, _, user_id = store_bundle
    _save(store, user_id)
    session_id = store.start_session("abc")
    directory = store.session_directory("abc", session_id)
    assert directory.name == session_id and directory.parent.name == "abc"
