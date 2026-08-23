"""면접 목록·조회 라우트 테스트.

홈 화면이 그릴 카드의 출처. 준비 데이터가 저장된 면접만 나와야 한다 —
프론트가 자기 메모리로 카드를 들고 있으면 새로고침에 사라지고, 준비되지 않은
면접을 시작하려다 브리지에서 거절당한다.

피드백과 녹음은 면접 한 판에 속한다. 같은 준비 데이터로 여러 번 면접할 수
있으므로 `?session=`으로 고르고, 생략하면 가장 최근 판이다.
"""

import time

from conftest import make_store
from fastapi import FastAPI
from fastapi.testclient import TestClient

from daedam.server.interview_routes import create_interviews_router
from daedam.server.preparation import InterviewPreparation


def _store(tmp_path, *ids_with_questions: tuple[str, bool]):
    store, accounts, user_id = make_store(tmp_path / "data")
    for interview_id, has_questions in ids_with_questions:
        store.save(
            interview_id,
            user_id=user_id,
            company=f"{interview_id}물류",
            role="데이터 엔지니어",
            application=[],
            # 질문이 없는 면접은 리포트도 비워 둔다 — 리서치가 아직 안 끝난
            # 상태이고, 그래야 부팅 복원이 생성을 이어서 하지 않는다.
            report=[{"title": "개요", "blocks": []}] if has_questions else [],
            uncertain=[],
        )
        if has_questions:
            store.save_questions(
                interview_id,
                [{"id": "q-0-0", "stage": 0, "text": "질문?", "priority": 1,
                  "tags": ["태그"]}],
            )
    return store, accounts


class _StubResearch:
    """리서치는 이 라우트의 관심사가 아니다 — 시작을 부르지 않는다."""

    def start(self, company, role, application):  # pragma: no cover
        raise AssertionError("목록 라우트가 리서치를 시작하면 안 된다")

    def status(self, task_id):  # pragma: no cover
        return None


class _StubEvaluation:
    """저장된 피드백을 그대로 상태로 옮기는 대역."""

    def __init__(self, store) -> None:
        self._store = store

    def status(self, session_id: str):
        from daedam.server.evaluation import FeedbackStatus

        record = self._store.load_session(session_id)
        if record is None or record.feedback is None:
            return FeedbackStatus(state="running")
        return FeedbackStatus(state="done", feedback=record.feedback)


def _client(bundle, generated: list | None = None) -> TestClient:
    store, accounts = bundle
    preparation = InterviewPreparation(
        research=_StubResearch(),
        store=store,
        generate=lambda **_: generated
        or [{"id": "q-1-0", "stage": 1, "text": "다시 뽑은 질문?", "priority": 1,
             "tags": ["태그"]}],
    )
    app = FastAPI()
    app.include_router(
        create_interviews_router(store, preparation, accounts, _StubEvaluation(store))
    )
    return TestClient(app)


def test_저장된_면접이_목록에_나온다(tmp_path) -> None:
    response = _client(_store(tmp_path, ("aaa", True))).get("/api/interviews")
    assert response.status_code == 200
    (item,) = response.json()
    assert item["id"] == "aaa"
    assert item["company"] == "aaa물류" and item["role"] == "데이터 엔지니어"
    assert item["interviewCount"] == 0 and item["score"] is None


def test_질문까지_있어야_ready다(tmp_path) -> None:
    """브리지가 질문 풀로 시작 가능 여부를 판정한다 — 화면도 같은 기준을 쓴다."""
    bundle = _store(tmp_path, ("done", True), ("half", False))
    ready = {
        item["id"]: item["ready"] for item in _client(bundle).get("/api/interviews").json()
    }
    assert ready == {"done": True, "half": False}


def test_최근_손댄_것이_앞에_온다(tmp_path) -> None:
    """홈은 방금 등록한 면접부터 보여야 한다."""
    bundle = _store(tmp_path, ("older", True), ("newer", True))
    store, _ = bundle
    store.save_report("newer", [{"title": "개요", "blocks": []}])  # updated_at 갱신
    ids = [item["id"] for item in _client(bundle).get("/api/interviews").json()]
    assert ids == ["newer", "older"]


def test_저장된_것이_없으면_빈_목록(tmp_path) -> None:
    assert _client(_store(tmp_path)).get("/api/interviews").json() == []


def test_면접_하나를_리포트까지_돌려준다(tmp_path) -> None:
    """검토 화면은 목업이 아니라 실제 리포트를 그려야 한다."""
    body = _client(_store(tmp_path, ("aaa", True))).get("/api/interviews/aaa").json()
    assert body["company"] == "aaa물류"
    assert body["report"] == [{"title": "개요", "blocks": []}]
    assert body["sessions"] == []


def test_없는_면접은_404(tmp_path) -> None:
    client = _client(_store(tmp_path))
    assert client.get("/api/interviews/nope").status_code == 404
    assert client.put("/api/interviews/nope/report", json={"report": []}).status_code == 404


def test_남의_면접도_404다(tmp_path) -> None:
    """존재 여부 자체를 흘리지 않는다 — 403이면 있다는 뜻이 된다."""
    from daedam.db import User

    bundle = _store(tmp_path, ("aaa", True))
    store, _ = bundle
    with store._db.session() as session:
        stranger = User(provider="kakao", provider_user_id="stranger")
        session.add(stranger)
        session.flush()
        stranger_id = stranger.id
    store.save(
        "other-card",
        user_id=stranger_id,
        company="비밀",
        role="비밀",
        application=[],
        report=[],
        uncertain=[],
    )
    client = _client(bundle)
    assert client.get("/api/interviews/other-card").status_code == 404
    assert [item["id"] for item in client.get("/api/interviews").json()] == ["aaa"]


def test_고친_리포트를_저장하고_질문을_다시_뽑는다(tmp_path) -> None:
    """질문은 리포트를 근거로 만들어졌다 — 사실을 고치면 낡은 근거 위에 선다."""
    bundle = _store(tmp_path, ("aaa", True))
    store, _ = bundle
    fixed = [{"title": "개요", "blocks": [{"type": "p", "text": "고친 사실"}]}]
    response = _client(bundle).put("/api/interviews/aaa/report", json={"report": fixed})
    assert response.status_code == 202 and response.json()["regenerating"] is True

    data = store.load("aaa")
    assert data is not None and data.report == fixed
    # 워커가 끝날 때까지 기다렸다가 새 질문이 들어갔는지 본다.
    for _ in range(50):
        data = store.load("aaa")
        if data is not None and data.questions and data.questions[0]["id"] == "q-1-0":
            break
        time.sleep(0.05)
    assert data is not None and data.questions is not None
    assert data.questions[0]["text"] == "다시 뽑은 질문?"


# ── 면접 이력 ────────────────────────────────────────────────────────────


def test_면접을_안_봤으면_피드백은_absent(tmp_path) -> None:
    """면접은 존재하고 아직 안 봤을 뿐이다 — 404가 아니다."""
    body = _client(_store(tmp_path, ("aaa", True))).get("/api/interviews/aaa/feedback")
    assert body.status_code == 200 and body.json() == {"status": "absent"}


def test_피드백은_기본으로_가장_최근_판이다(tmp_path) -> None:
    bundle = _store(tmp_path, ("aaa", True))
    store, _ = bundle
    first = store.start_session("aaa")
    store.save_feedback(first, {"coaching": {"score": 60}})
    store.end_session(first)
    second = store.start_session("aaa")
    store.save_feedback(second, {"coaching": {"score": 82}})

    client = _client(bundle)
    body = client.get("/api/interviews/aaa/feedback").json()
    assert body["sessionId"] == second
    assert body["feedback"]["coaching"]["score"] == 82

    # 지난 판도 골라서 볼 수 있다 — 성장 추이가 이 서비스의 재방문 이유다.
    body = client.get(f"/api/interviews/aaa/feedback?session={first}").json()
    assert body["feedback"]["coaching"]["score"] == 60


def test_남의_면접_기록은_고를_수_없다(tmp_path) -> None:
    bundle = _store(tmp_path, ("aaa", True), ("bbb", True))
    store, _ = bundle
    store.start_session("aaa")
    other = store.start_session("bbb")
    client = _client(bundle)
    assert client.get(f"/api/interviews/aaa/feedback?session={other}").status_code == 404


def test_이력_목록은_최근_판부터(tmp_path) -> None:
    bundle = _store(tmp_path, ("aaa", True))
    store, _ = bundle
    first = store.start_session("aaa")
    store.end_session(first)
    second = store.start_session("aaa")
    body = _client(bundle).get("/api/interviews/aaa/sessions").json()
    assert [item["id"] for item in body] == [second, first]
    assert body[0]["hasFeedback"] is False
