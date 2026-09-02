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


#: 지원자가 한 마디라도 한 전사. 이게 있어야 "면접을 봤다"로 센다.
_SPOKE = {
    "durationS": 30.0,
    "utterances": [{"speaker": "applicant", "text": "안녕하세요", "at": 1.0}],
}


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
    """저장된 피드백을 그대로 상태로 옮기는 대역.

    진짜와 같은 순서로 판정한다 — 피드백이 있으면 done, 남긴 말이 없으면
    silent(만들 것이 없다), 나머지는 running. 대역이 이 갈래를 뭉개면 라우트가
    silent를 실어 보내는지 여기서 볼 수 없다.
    """

    def __init__(self, store) -> None:
        self._store = store

    def status(self, session_id: str):
        from daedam.server.evaluation import FeedbackStatus

        record = self._store.load_session(session_id)
        if record is None:
            return FeedbackStatus(state="running")
        if record.feedback is not None:
            return FeedbackStatus(state="done", feedback=record.feedback)
        if not (record.transcript or {}).get("utterances"):
            return FeedbackStatus(state="silent")
        return FeedbackStatus(state="running")


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
        create_interviews_router(
            store, preparation, accounts, _StubEvaluation(store), accounts.credits
        )
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


def test_아무_말도_없이_끝난_면접은_silent다(tmp_path) -> None:
    """면접은 진행됐고 남긴 말만 없다 — absent로 뭉치면 화면이 "아직 면접을
    진행하지 않았습니다"라고 거짓말을 한다."""
    bundle = _store(tmp_path, ("aaa", True))
    store, accounts = bundle
    session_id = store.start_session("aaa")
    store.save_transcript(session_id, {"durationS": 4.0, "utterances": []})
    store.end_session(session_id)

    body = _client(bundle).get("/api/interviews/aaa/feedback").json()
    assert body["status"] == "silent" and body["sessionId"] == session_id
    # 크레딧을 물린 적이 없으니 되돌린 적도 없다 — 짐작하지 않고 원장을 본다.
    assert body["refunded"] is False


def test_되돌린_크레딧을_그대로_알려준다(tmp_path) -> None:
    """무응답 면접에서 사용자가 가장 먼저 묻는 것이 크레딧이다."""
    bundle = _store(tmp_path, ("aaa", True))
    store, accounts = bundle
    user_id = accounts.default_user_id()
    session_id = store.start_session("aaa")
    store.save_transcript(session_id, {"durationS": 4.0, "utterances": []})
    accounts.credits.charge(user_id, 4, "interview", session_id)
    accounts.credits.refund(user_id, "interview", session_id)

    body = _client(bundle).get("/api/interviews/aaa/feedback").json()
    assert body["status"] == "silent" and body["refunded"] is True


def test_답변이_없는_판은_회차로_세지_않는다(tmp_path) -> None:
    """시작만 하고 아무 말 없이 나온 것은 "면접을 봤다"가 아니다.

    회차 번호가 이 목록에서 매겨지므로, 빼지 않으면 한 적 없는 회차가 생긴다.
    기록 자체는 남는다 — 크레딧을 되돌린 근거이고 녹음도 남아 있다.
    """
    bundle = _store(tmp_path, ("aaa", True))
    store, _ = bundle

    talked = store.start_session("aaa")
    store.save_transcript(talked, _SPOKE)
    store.save_feedback(talked, {"coaching": {"score": 68}})
    store.end_session(talked)
    silent = store.start_session("aaa")
    store.save_transcript(silent, {"durationS": 4.0, "utterances": []})
    store.end_session(silent)

    client = _client(bundle)
    body = client.get("/api/interviews/aaa/sessions").json()
    assert [item["id"] for item in body] == [talked]
    assert store.load_session(silent) is not None  # 기록은 그대로다

    # 홈 카드도 같은 기준이다 — 없던 일 대신 마지막 면접의 점수를 보여준다.
    [card] = client.get("/api/interviews").json()
    assert card["analyzed"] is True and card["score"] == 68


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


def test_녹화는_순서대로_이어_붙는다(tmp_path) -> None:
    """MediaRecorder는 첫 조각에만 헤더를 넣는다 — 이어 붙인 결과가 곧 파일이다."""
    bundle = _store(tmp_path, ("aaa", True))
    store, _ = bundle
    session_id = store.start_session("aaa")
    client = _client(bundle)

    for chunk in (b"\x1a\x45\xdf\xa3head", b"middle", b"tail"):
        r = client.post(f"/api/interviews/aaa/video?session={session_id}", content=chunk)
        assert r.status_code == 204

    saved = store.session_directory("aaa", session_id) / "cam.webm"
    assert saved.read_bytes() == b"\x1a\x45\xdf\xa3headmiddletail"

    got = client.get(f"/api/interviews/aaa/video?session={session_id}")
    assert got.status_code == 200 and got.headers["content-type"] == "video/webm"


def test_녹화가_없으면_404다(tmp_path) -> None:
    bundle = _store(tmp_path, ("aaa", True))
    store, _ = bundle
    store.start_session("aaa")
    assert _client(bundle).get("/api/interviews/aaa/video").status_code == 404


def test_너무_큰_조각은_거절한다(tmp_path) -> None:
    """상한이 없으면 한 사람이 51GB짜리 디스크를 다 먹는다."""
    from daedam.server.interview_routes import _VIDEO_CHUNK_MAX

    bundle = _store(tmp_path, ("aaa", True))
    store, _ = bundle
    session_id = store.start_session("aaa")
    r = _client(bundle).post(
        f"/api/interviews/aaa/video?session={session_id}",
        content=b"x" * (_VIDEO_CHUNK_MAX + 1),
    )
    assert r.status_code == 413
    assert not (store.session_directory("aaa", session_id) / "cam.webm").exists()


def test_남의_면접에는_녹화를_올릴_수_없다(tmp_path) -> None:
    """소유권 검사가 업로드에도 걸려야 한다 — 없으면 남의 세션에 파일을 쓴다."""
    bundle = _store(tmp_path, ("aaa", True), ("bbb", True))
    store, _ = bundle
    other = store.start_session("bbb")
    r = _client(bundle).post(f"/api/interviews/aaa/video?session={other}", content=b"x")
    assert r.status_code == 404
    assert not (store.session_directory("bbb", other) / "cam.webm").exists()


def test_시선_타임라인은_통째로_덮어쓴다(tmp_path) -> None:
    """영상과 달리 이어 붙이지 않는다 — 순서도 구멍도 걱정할 것이 없다."""
    import json

    bundle = _store(tmp_path, ("aaa", True))
    store, _ = bundle
    session_id = store.start_session("aaa")
    client = _client(bundle)
    url = f"/api/interviews/aaa/gaze?session={session_id}"

    first = {"baseline": {"center": {"x": 0, "y": 0}, "noise": 0.01},
             "seconds": [{"at": 1.0, "cell": 4, "impression": "focused", "ratio": 1.0}]}
    assert client.put(url, json=first).status_code == 204

    second = {**first, "seconds": first["seconds"] + [
        {"at": 2.0, "cell": 7, "impression": "tense", "ratio": 4.2}]}
    assert client.put(url, json=second).status_code == 204

    saved = json.loads((store.session_directory("aaa", session_id) / "gaze.json").read_text())
    assert len(saved["seconds"]) == 2  # 덧붙지 않고 교체됐다


def test_타임라인이_아닌_것은_거절한다(tmp_path) -> None:
    bundle = _store(tmp_path, ("aaa", True))
    store, _ = bundle
    session_id = store.start_session("aaa")
    client = _client(bundle)
    url = f"/api/interviews/aaa/gaze?session={session_id}"

    assert client.put(url, content=b"not json").status_code == 400
    assert client.put(url, json={"seconds": "문자열"}).status_code == 400
    assert not (store.session_directory("aaa", session_id) / "gaze.json").exists()


def test_남의_면접에는_타임라인을_올릴_수_없다(tmp_path) -> None:
    bundle = _store(tmp_path, ("aaa", True), ("bbb", True))
    store, _ = bundle
    other = store.start_session("bbb")
    r = _client(bundle).put(
        f"/api/interviews/aaa/gaze?session={other}",
        json={"seconds": []},
    )
    assert r.status_code == 404
    assert not (store.session_directory("bbb", other) / "gaze.json").exists()


def test_남의_면접_기록은_고를_수_없다(tmp_path) -> None:
    bundle = _store(tmp_path, ("aaa", True), ("bbb", True))
    store, _ = bundle
    store.start_session("aaa")
    other = store.start_session("bbb")
    client = _client(bundle)
    assert client.get(f"/api/interviews/aaa/feedback?session={other}").status_code == 404


def test_이력_목록은_최근_회차부터(tmp_path) -> None:
    bundle = _store(tmp_path, ("aaa", True))
    store, _ = bundle
    first = store.start_session("aaa")
    store.save_transcript(first, _SPOKE)
    store.end_session(first)
    second = store.start_session("aaa")
    store.save_transcript(second, _SPOKE)
    body = _client(bundle).get("/api/interviews/aaa/sessions").json()
    assert [item["id"] for item in body] == [second, first]
    assert body[0]["hasFeedback"] is False


def test_분석이_끝났는데_점수가_없는_경우를_가른다(tmp_path) -> None:
    """한 마디도 안 하고 끝낸 면접은 채점할 답변이 없어 점수가 null이다.
    그것과 "아직 분석 중"을 화면이 구분하지 못하면, 오지 않을 결과를 계속
    기다리는 카드가 된다(실측)."""
    bundle = _store(tmp_path, ("aaa", True))
    store, _ = bundle
    client = _client(bundle)

    # ① 답변은 했는데 아직 분석 전이다.
    session_id = store.start_session("aaa")
    store.save_transcript(session_id, _SPOKE)
    [item] = client.get("/api/interviews").json()
    assert item["analyzed"] is False and item["score"] is None

    # ② 분석은 끝났는데 채점할 답변이 없었다.
    store.save_feedback(session_id, {"coaching": {"score": None}})
    [item] = client.get("/api/interviews").json()
    assert item["analyzed"] is True and item["score"] is None

    # ③ 보통의 경우.
    later = store.start_session("aaa")
    store.save_transcript(later, _SPOKE)
    store.save_feedback(later, {"coaching": {"score": 71}})
    [item] = client.get("/api/interviews").json()
    assert item["analyzed"] is True and item["score"] == 71


def test_스냅샷은_시각이_이름이_된다(tmp_path) -> None:
    """f00012.3.jpg — 이름이 곧 시각이라 목록 파일 없이 답변별로 나눌 수 있다."""
    bundle = _store(tmp_path, ("aaa", True))
    store, _ = bundle
    session_id = store.start_session("aaa")
    r = _client(bundle).post(
        f"/api/interviews/aaa/frames?session={session_id}&at=12.3",
        content=b"\xff\xd8jpeg",
    )
    assert r.status_code == 204
    saved = store.session_directory("aaa", session_id) / "frames" / "f00012.3.jpg"
    assert saved.read_bytes() == b"\xff\xd8jpeg"


def test_같은_시각의_스냅샷은_덮어쓴다(tmp_path) -> None:
    """재전송이 와도 장수만 같다 — 영상 조각과 달리 순서·중복 문제가 없다."""
    bundle = _store(tmp_path, ("aaa", True))
    store, _ = bundle
    session_id = store.start_session("aaa")
    url = f"/api/interviews/aaa/frames?session={session_id}&at=3.0"
    client = _client(bundle)
    assert client.post(url, content=b"old").status_code == 204
    assert client.post(url, content=b"new").status_code == 204
    directory = store.session_directory("aaa", session_id) / "frames"
    assert [p.name for p in directory.glob("*.jpg")] == ["f00003.0.jpg"]
    assert (directory / "f00003.0.jpg").read_bytes() == b"new"


def test_너무_큰_스냅샷은_거절한다(tmp_path) -> None:
    from daedam.server.interview_routes import _FRAME_MAX

    bundle = _store(tmp_path, ("aaa", True))
    store, _ = bundle
    session_id = store.start_session("aaa")
    r = _client(bundle).post(
        f"/api/interviews/aaa/frames?session={session_id}&at=1.0",
        content=b"x" * (_FRAME_MAX + 1),
    )
    assert r.status_code == 413
    assert not (store.session_directory("aaa", session_id) / "frames").exists()


def test_스냅샷_장수에_상한이_있다(tmp_path, monkeypatch) -> None:
    """상한이 없으면 시각만 바꿔 보내는 클라이언트가 디스크를 다 먹는다."""
    from daedam.server import interview_routes

    monkeypatch.setattr(interview_routes, "_FRAMES_COUNT_MAX", 2)
    bundle = _store(tmp_path, ("aaa", True))
    store, _ = bundle
    session_id = store.start_session("aaa")
    client = _client(bundle)
    for at in ("1.0", "2.0"):
        ok = client.post(
            f"/api/interviews/aaa/frames?session={session_id}&at={at}", content=b"x"
        )
        assert ok.status_code == 204
    r = client.post(
        f"/api/interviews/aaa/frames?session={session_id}&at=3.0", content=b"x"
    )
    assert r.status_code == 413


def test_남의_면접에는_스냅샷을_올릴_수_없다(tmp_path) -> None:
    bundle = _store(tmp_path, ("aaa", True), ("bbb", True))
    store, _ = bundle
    other = store.start_session("bbb")
    r = _client(bundle).post(
        f"/api/interviews/aaa/frames?session={other}&at=1.0", content=b"x"
    )
    assert r.status_code == 404
    assert not (store.session_directory("bbb", other) / "frames").exists()
