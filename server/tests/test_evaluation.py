"""면접 뒤 피드백 생성 테스트.

코칭 LLM은 대역으로 대체한다. 여기서 보는 것은 배관이다 — 언제 시작하고,
무엇을 저장하고, 실패하면 무엇이 남는가.
"""

import time
import wave
from types import SimpleNamespace

import numpy as np
from conftest import make_store

from daedam.server.evaluation import InterviewEvaluation
from daedam.server.store import InterviewStore

RATE = 16_000

TRANSCRIPT = {
    "durationS": 3.0,
    "utterances": [
        {"speaker": "interviewer", "text": "자기소개 부탁드립니다.", "at": 0.5},
        {"speaker": "applicant", "text": "박지원입니다. 데이터 분석을 했습니다.", "at": 3.0},
    ],
}


def _store(tmp_path) -> tuple[InterviewStore, str]:
    """준비 데이터 하나와 그 위에 열린 면접 한 판 — (저장소, 면접 id)."""
    store, _, user_id = make_store(tmp_path / "data")
    store.save(
        "itv",
        user_id=user_id,
        company="SK하이닉스",
        role="기반기술",
        application=[],
        report=[{"title": "개요", "blocks": []}],
        uncertain=[],
    )
    return store, store.start_session("itv")


def _record(store: InterviewStore, session_id: str, *, with_audio: bool = True) -> None:
    store.save_transcript(session_id, TRANSCRIPT)
    if not with_audio:
        return
    directory = store.session_directory("itv", session_id)
    directory.mkdir(parents=True, exist_ok=True)
    t = np.arange(int(RATE * 1.5)) / RATE
    tone = (3000 * np.sin(2 * np.pi * 220 * t)).astype(np.int16)
    with wave.open(str(directory / "mic.wav"), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(np.concatenate([np.zeros(RATE, dtype=np.int16), tone]).tobytes())


def _coaching(score=70):
    review = SimpleNamespace(
        answers=[SimpleNamespace(score=score)],
        summary="총평",
        strengths=["강점"],
        improvements=["개선"],
    )
    return SimpleNamespace(
        review=review,
        score=score,
        fillers=0,
        as_dict=lambda: {
            "score": score,
            "fillers": 0,
            "summary": "총평",
            "strengths": ["강점"],
            "improvements": ["개선"],
            "answers": [{"question": "자기소개 부탁드립니다.", "score": score}],
        },
    )


def _wait(condition, timeout_s: float = 3.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline and not condition():
        time.sleep(0.01)


def test_전사가_없으면_시작하지_않고_silent를_돌려준다(tmp_path) -> None:
    """한 마디도 안 하고 끝낸 면접 — 만들 것이 없다.

    absent가 아니라 silent인 것이 요점이다. 면접은 실제로 진행됐으므로 화면이
    "아직 면접을 진행하지 않았습니다"라고 말하면 거짓말이 된다.
    """
    store, session_id = _store(tmp_path)
    evaluation = InterviewEvaluation(store, coach=lambda **_: _coaching())
    assert evaluation.start(session_id) is False
    assert evaluation.status(session_id).state == "silent"


def test_없는_면접은_그대로_absent다(tmp_path) -> None:
    """silent가 absent를 잡아먹으면 안 된다 — 기록 자체가 없는 경우다."""
    store, _ = _store(tmp_path)
    evaluation = InterviewEvaluation(store, coach=lambda **_: _coaching())
    assert evaluation.status("없는판").state == "absent"


def test_전사가_있는데_분석이_안_돌면_silent가_아니다(tmp_path) -> None:
    """서버가 분석 도중 재시작된 경우. 답변은 남아 있으므로 silent가 아니고,
    다시 깨우면 만들어진다 — silent로 뭉치면 되살릴 길이 화면에서 사라진다."""
    store, session_id = _store(tmp_path)
    _record(store, session_id)
    evaluation = InterviewEvaluation(store, coach=lambda **_: _coaching())
    assert evaluation.status(session_id).state == "absent"


def test_기록이_있으면_피드백을_만들어_저장한다(tmp_path) -> None:
    store, session_id = _store(tmp_path)
    _record(store, session_id)
    evaluation = InterviewEvaluation(store, coach=lambda **_: _coaching(80))

    assert evaluation.start(session_id) is True
    _wait(lambda: evaluation.status(session_id).state == "done")

    status = evaluation.status(session_id)
    assert status.state == "done"
    assert status.feedback["coaching"]["score"] == 80
    assert status.feedback["voice"]["answers"][0]["startS"] > 0
    # 저장된 피드백이 완료의 증거다 — 서버가 재시작돼도 done이 복원된다.
    assert store.load_session(session_id).feedback is not None


def test_두_번_깨워도_한_번만_돈다(tmp_path) -> None:
    """재접속이면 커넥션마다 종료 정리가 돈다 — 그때마다 새로 만들면 안 된다."""
    store, session_id = _store(tmp_path)
    _record(store, session_id)
    calls: list[int] = []

    def coach(**_):
        calls.append(1)
        time.sleep(0.05)
        return _coaching()

    evaluation = InterviewEvaluation(store, coach=coach)
    assert evaluation.start(session_id) is True
    assert evaluation.start(session_id) is False
    _wait(lambda: evaluation.status(session_id).state == "done")
    assert len(calls) == 1


def test_녹음이_없어도_코칭은_만든다(tmp_path) -> None:
    """지표는 순수 계산이고 코칭은 Grok이다 — 하나가 없다고 둘 다 버리지 않는다."""
    store, session_id = _store(tmp_path)
    _record(store, session_id, with_audio=False)
    evaluation = InterviewEvaluation(store, coach=lambda **_: _coaching())

    evaluation.start(session_id)
    _wait(lambda: evaluation.status(session_id).state == "done")

    feedback = evaluation.status(session_id).feedback
    assert "voice" not in feedback
    assert feedback["coaching"]["summary"] == "총평"


def test_코칭이_실패하면_failed로_남는다(tmp_path) -> None:
    """조용히 넘어가면 화면이 영원히 기다린다."""
    store, session_id = _store(tmp_path)
    _record(store, session_id)

    def broken(**_):
        raise RuntimeError("xAI 호출 실패")

    evaluation = InterviewEvaluation(store, coach=broken)
    evaluation.start(session_id)
    _wait(lambda: evaluation.status(session_id).state == "failed")

    assert evaluation.status(session_id).state == "failed"
    assert store.load_session(session_id).feedback is None


def test_전사도_피드백에_함께_담는다(tmp_path) -> None:
    """리포트가 '이 답변 다시 듣기'를 붙이려면 발화와 시각이 같이 있어야 한다."""
    store, session_id = _store(tmp_path)
    _record(store, session_id)
    evaluation = InterviewEvaluation(store, coach=lambda **_: _coaching())

    evaluation.start(session_id)
    _wait(lambda: evaluation.status(session_id).state == "done")

    feedback = evaluation.status(session_id).feedback
    assert feedback["durationS"] == 3.0
    assert len(feedback["utterances"]) == 2


def _wait_done(evaluation, session_id, timeout_s: float = 3.0):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status = evaluation.status(session_id)
        if status.state in ("done", "failed"):
            return status
        time.sleep(0.02)
    raise AssertionError("피드백이 제 시간에 끝나지 않았습니다")


def test_스냅샷이_있으면_표정_판독이_실린다(tmp_path) -> None:
    store, session_id = _store(tmp_path)
    _record(store, session_id)
    frames = store.session_directory("itv", session_id) / "frames"
    frames.mkdir(parents=True)
    (frames / "f00001.0.jpg").write_bytes(b"jpg")

    def judge(directory, **_):
        assert directory == frames
        return {
            "frames": [
                {"at": 1.0, "confident": 30, "focused": 60, "tense": 10,
                 "flustered": 0, "gaze": "camera", "note": ""}
            ],
            "strengths": ["차분한 시선"],
            "observations": ["카메라를 눈높이로"],
        }

    evaluation = InterviewEvaluation(store, coach=lambda **_: _coaching(), judge=judge)
    assert evaluation.start(session_id)
    status = _wait_done(evaluation, session_id)
    assert status.state == "done"
    expression = status.feedback["expression"]
    assert expression["impressions"]["focused"] == 0.6
    # 관찰은 코칭의 두 목록에 합쳐진다 — 조언이 두 집이면 어색하고,
    # 고칠 점만 합치면 목록이 한쪽으로 분다.
    assert status.feedback["coaching"]["improvements"] == ["개선", "카메라를 눈높이로"]
    assert status.feedback["coaching"]["strengths"] == ["강점", "차분한 시선"]
    # 시선은 판독의 방향에서 온다 — 홍채 기하의 좌우 뒤집힘이 없는 쪽이다.
    assert status.feedback["gaze"]["source"] == "vlm"
    assert status.feedback["gaze"]["steady"] == 1.0
    assert "gaze" not in expression


def test_판독이_실패해도_지표와_코칭은_나간다(tmp_path) -> None:
    """판독은 곁가지다 — LLM 하나가 죽었다고 리포트가 통째로 죽으면 안 된다."""
    store, session_id = _store(tmp_path)
    _record(store, session_id)
    frames = store.session_directory("itv", session_id) / "frames"
    frames.mkdir(parents=True)
    (frames / "f00001.0.jpg").write_bytes(b"jpg")

    def judge(directory, **_):
        raise RuntimeError("판독 실패")

    evaluation = InterviewEvaluation(store, coach=lambda **_: _coaching(), judge=judge)
    assert evaluation.start(session_id)
    status = _wait_done(evaluation, session_id)
    assert status.state == "done"
    assert "expression" not in status.feedback
    assert status.feedback["coaching"]["summary"] == "총평"


def test_스냅샷이_없으면_판독을_부르지_않는다(tmp_path) -> None:
    store, session_id = _store(tmp_path)
    _record(store, session_id)

    def judge(directory, **_):  # pragma: no cover
        raise AssertionError("스냅샷이 없는데 판독을 불렀다")

    evaluation = InterviewEvaluation(store, coach=lambda **_: _coaching(), judge=judge)
    assert evaluation.start(session_id)
    assert _wait_done(evaluation, session_id).state == "done"


def test_앞토막에서_끊긴_뼈대질문_전사를_원문으로_채운다() -> None:
    """출력 전사 스트림이 죽으면 질문이 반토막으로 남는다 — 원문은 서버가 안다."""
    from daedam.server.evaluation import _repair_transcript

    questions = [{"text": "성균관대 졸업작품을 진행하며 발휘한 패기는 무엇인가요?"}]
    transcript = {
        "utterances": [
            {"speaker": "interviewer", "text": "성균관대 졸업작품을", "at": 1.0},
            {"speaker": "applicant", "text": "성균관대 졸업작품을 했습니다", "at": 5.0},
            {"speaker": "interviewer", "text": "네,", "at": 9.0},
        ]
    }
    repaired = _repair_transcript(transcript, questions)
    assert repaired["utterances"][0]["text"] == questions[0]["text"]
    # 지원자 발화와 짧은 추임새는 건드리지 않는다.
    assert repaired["utterances"][1]["text"] == "성균관대 졸업작품을 했습니다"
    assert repaired["utterances"][2]["text"] == "네,"
    # 원본은 그대로다 — 읽는 시점의 보정이다.
    assert transcript["utterances"][0]["text"] == "성균관대 졸업작품을"


def test_온전한_질문_전사는_보정하지_않는다() -> None:
    from daedam.server.evaluation import _repair_transcript

    questions = [{"text": "지원 이유는 무엇인가요?"}]
    transcript = {
        "utterances": [
            {"speaker": "interviewer", "text": "지원 이유는 무엇인가요?", "at": 1.0}
        ]
    }
    repaired = _repair_transcript(transcript, questions)
    assert repaired["utterances"][0]["text"] == "지원 이유는 무엇인가요?"


# ── 재기동 복구 · 원본 pcm 정리 ──────────────────────────────────────────


def test_끝났는데_피드백이_없는_판은_재기동_때_이어서_만든다(tmp_path) -> None:
    """생성 스레드는 데몬이라 재시작에 죽는다 — 앞서는 그 판의 리포트가 영영
    없었다. 완료의 증거가 저장된 피드백이니 다시 깨우면 된다."""
    store, session_id = _store(tmp_path)
    _record(store, session_id)
    store.end_session(session_id)
    # 답변이 없는 판은 이어받지 않는다 — 만들 것이 없다.
    silent = store.start_session("itv")
    store.save_transcript(silent, {"durationS": 1.0, "utterances": [
        {"speaker": "interviewer", "text": "안녕하세요", "at": 0.5}]})
    store.end_session(silent)

    calls: list[str] = []

    def coach(**kwargs):
        calls.append("coach")
        return _coaching()

    evaluation = InterviewEvaluation(store, coach=coach)  # 생성자가 복구를 돈다
    _wait(lambda: evaluation.status(session_id).state == "done")
    assert calls == ["coach"]
    assert evaluation.status(silent).state == "silent"


def test_피드백을_저장하면_원본_pcm을_지운다(tmp_path) -> None:
    """wav는 pcm에 헤더만 붙인 것이라 같은 바이트가 두 벌이었다."""
    store, session_id = _store(tmp_path)
    _record(store, session_id)
    directory = store.session_directory("itv", session_id)
    (directory / "mic.pcm").write_bytes(b"\x00" * 64)
    store.end_session(session_id)

    evaluation = InterviewEvaluation(store, coach=lambda **_: _coaching())
    evaluation.start(session_id)
    _wait(lambda: evaluation.status(session_id).state == "done")
    assert (directory / "mic.wav").exists()
    assert not (directory / "mic.pcm").exists()
