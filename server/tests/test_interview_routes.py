"""면접 목록 라우트 테스트.

홈 화면이 그릴 카드의 출처. 준비 데이터가 저장된 면접만 나와야 한다 —
프론트가 자기 메모리로 카드를 들고 있으면 새로고침에 사라지고, 준비되지 않은
면접을 시작하려다 브리지에서 거절당한다.
"""

import os
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from daedam.server.interview_routes import create_interviews_router
from daedam.server.preparation import InterviewPreparation
from daedam.server.store import FileInterviewStore


def _store(tmp_path, *ids_with_questions: tuple[str, bool]) -> FileInterviewStore:
    store = FileInterviewStore(tmp_path / "data")
    for interview_id, has_questions in ids_with_questions:
        store.save(
            interview_id,
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
    return store


class _StubResearch:
    """리서치는 이 라우트의 관심사가 아니다 — 시작을 부르지 않는다."""

    def start(self, company, role, application):  # pragma: no cover
        raise AssertionError("목록 라우트가 리서치를 시작하면 안 된다")

    def status(self, task_id):  # pragma: no cover
        return None


def _client(store: FileInterviewStore, generated: list | None = None) -> TestClient:
    preparation = InterviewPreparation(
        research=_StubResearch(),
        store=store,
        generate=lambda **_: generated
        or [{"id": "q-1-0", "stage": 1, "text": "다시 뽑은 질문?", "priority": 1,
             "tags": ["태그"]}],
    )
    app = FastAPI()
    app.include_router(create_interviews_router(store, preparation))
    return TestClient(app)


def test_저장된_면접이_목록에_나온다(tmp_path) -> None:
    response = _client(_store(tmp_path, ("aaa", True))).get("/api/interviews")
    assert response.status_code == 200
    (item,) = response.json()
    assert item["id"] == "aaa"
    assert item["company"] == "aaa물류" and item["role"] == "데이터 엔지니어"


def test_질문까지_있어야_ready다(tmp_path) -> None:
    """브리지가 질문 풀로 시작 가능 여부를 판정한다 — 화면도 같은 기준을 쓴다."""
    store = _store(tmp_path, ("done", True), ("half", False))
    ready = {item["id"]: item["ready"] for item in _client(store).get("/api/interviews").json()}
    assert ready == {"done": True, "half": False}


def test_최근_저장된_것이_앞에_온다(tmp_path) -> None:
    """홈은 방금 등록한 면접부터 보여야 한다."""
    store = _store(tmp_path, ("older", True), ("newer", True))
    # 파일 시각으로 정렬하므로 새 쪽을 명시적으로 미래로 민다.
    meta = tmp_path / "data" / "newer" / "meta.json"
    os.utime(meta, (meta.stat().st_atime, meta.stat().st_mtime + 60))
    ids = [item["id"] for item in _client(store).get("/api/interviews").json()]
    assert ids == ["newer", "older"]


def test_저장된_것이_없으면_빈_목록(tmp_path) -> None:
    assert _client(FileInterviewStore(tmp_path / "none")).get("/api/interviews").json() == []


def test_면접_하나를_리포트까지_돌려준다(tmp_path) -> None:
    """검토 화면은 목업이 아니라 실제 리포트를 그려야 한다."""
    body = _client(_store(tmp_path, ("aaa", True))).get("/api/interviews/aaa").json()
    assert body["company"] == "aaa물류"
    assert body["report"] == [{"title": "개요", "blocks": []}]


def test_없는_면접은_404(tmp_path) -> None:
    client = _client(FileInterviewStore(tmp_path / "none"))
    assert client.get("/api/interviews/nope").status_code == 404
    assert client.put("/api/interviews/nope/report", json={"report": []}).status_code == 404


def test_고친_리포트를_저장하고_질문을_다시_뽑는다(tmp_path) -> None:
    """질문은 리포트를 근거로 만들어졌다 — 사실을 고치면 낡은 근거 위에 선다."""
    store = _store(tmp_path, ("aaa", True))
    fixed = [{"title": "개요", "blocks": [{"type": "p", "text": "고친 사실"}]}]
    response = _client(store).put("/api/interviews/aaa/report", json={"report": fixed})
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
