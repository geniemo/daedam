"""녹음 보관 정책 테스트 — 무엇을 지우고 무엇을 남기는가."""

from datetime import UTC, datetime, timedelta

from conftest import make_store

from daedam.server.retention import purge_old_recordings

TRANSCRIPT = {"durationS": 3.0, "utterances": [
    {"speaker": "interviewer", "text": "자기소개", "at": 0.5},
    {"speaker": "applicant", "text": "박지원입니다", "at": 2.0},
]}


def _session(store, user_id, application_id, *, ended_days_ago, feedback, answered=True):
    if store.load(application_id) is None:
        store.save(application_id, user_id=user_id, company="A", role="B",
                   application=[], report=[], uncertain=[])
    session_id = store.start_session(application_id)
    store.save_transcript(session_id, TRANSCRIPT if answered else {"utterances": []})
    store.end_session(session_id)
    if feedback:
        store.save_feedback(session_id, {"coaching": {"score": 70}})
    directory = store.session_directory(application_id, session_id)
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("mic.wav", "cam.webm", "transcript.json", "vlm.json"):
        (directory / name).write_bytes(b"x" * 100)
    (directory / "frames").mkdir()
    (directory / "frames" / "f0003.0.jpg").write_bytes(b"j" * 50)
    return session_id, directory


def test_기한이_지난_판의_미디어만_지우고_기록은_남긴다(tmp_path) -> None:
    store, _, user_id = make_store(tmp_path)
    old_id, old_dir = _session(store, user_id, "app", ended_days_ago=100, feedback=True)
    now = datetime.now(UTC) + timedelta(days=100)  # 시계를 100일 뒤로

    purged, freed = purge_old_recordings(store, days=90, now=now)

    assert purged == 1 and freed == 250
    assert not (old_dir / "mic.wav").exists() and not (old_dir / "cam.webm").exists()
    assert not (old_dir / "frames").exists()
    assert (old_dir / "transcript.json").exists() and (old_dir / "vlm.json").exists()
    assert store.load_session(old_id).feedback is not None  # 리포트는 그대로


def test_기한_안의_판은_건드리지_않는다(tmp_path) -> None:
    store, _, user_id = make_store(tmp_path)
    _, fresh_dir = _session(store, user_id, "app", ended_days_ago=0, feedback=True)
    purged, _ = purge_old_recordings(store, days=90)
    assert purged == 0 and (fresh_dir / "mic.wav").exists()


def test_피드백이_아직_없는_판은_남긴다(tmp_path) -> None:
    """재기동 복구가 그 판의 wav로 리포트를 만들어야 한다."""
    store, _, user_id = make_store(tmp_path)
    _, pending_dir = _session(store, user_id, "app", ended_days_ago=100, feedback=False)
    _, silent_dir = _session(store, user_id, "app", ended_days_ago=100, feedback=False, answered=False)
    now = datetime.now(UTC) + timedelta(days=100)
    purged, _ = purge_old_recordings(store, days=90, now=now)
    assert (pending_dir / "mic.wav").exists()      # 답변 있음 + 피드백 없음 → 보류
    assert not (silent_dir / "mic.wav").exists()   # 답변 없음 → 만들 것이 없어 지운다
    assert purged == 1
