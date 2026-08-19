"""면접 뒤 피드백 생성 테스트.

Grok은 대역으로 대체한다. 여기서 보는 것은 배관이다 — 언제 시작하고, 무엇을
저장하고, 실패하면 무엇이 남는가.
"""

import json
import time
import wave
from types import SimpleNamespace

import numpy as np

from daedam.server.evaluation import InterviewEvaluation
from daedam.server.store import FileInterviewStore

RATE = 16_000


def _store(tmp_path) -> FileInterviewStore:
    store = FileInterviewStore(tmp_path / "data")
    store.save(
        "itv",
        company="SK하이닉스",
        role="기반기술",
        application=[],
        report=[{"title": "개요", "blocks": []}],
        uncertain=[],
    )
    return store


def _record(store: FileInterviewStore, *, with_audio: bool = True) -> None:
    directory = store.directory("itv")
    (directory / "transcript.json").write_text(
        json.dumps(
            {
                "durationS": 3.0,
                "utterances": [
                    {"speaker": "interviewer", "text": "자기소개 부탁드립니다.", "at": 0.5},
                    {"speaker": "applicant", "text": "박지원입니다. 데이터 분석을 했습니다.", "at": 3.0},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    if not with_audio:
        return
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


def test_전사가_없으면_시작하지_않는다(tmp_path) -> None:
    """면접을 시작만 하고 끝낸 경우 — 만들 것이 없다."""
    evaluation = InterviewEvaluation(_store(tmp_path), coach=lambda **_: _coaching())
    assert evaluation.start("itv") is False
    assert evaluation.status("itv").state == "absent"


def test_기록이_있으면_피드백을_만들어_저장한다(tmp_path) -> None:
    store = _store(tmp_path)
    _record(store)
    evaluation = InterviewEvaluation(store, coach=lambda **_: _coaching(80))

    assert evaluation.start("itv") is True
    _wait(lambda: evaluation.status("itv").state == "done")

    status = evaluation.status("itv")
    assert status.state == "done"
    assert status.feedback["coaching"]["score"] == 80
    assert status.feedback["voice"]["answers"][0]["startS"] > 0
    # 파일이 완료의 증거다 — 서버가 재시작돼도 done이 복원된다.
    assert store.load("itv").feedback is not None


def test_두_번_깨워도_한_번만_돈다(tmp_path) -> None:
    """재접속이면 커넥션마다 종료 정리가 돈다 — 그때마다 새로 만들면 안 된다."""
    store = _store(tmp_path)
    _record(store)
    calls: list[int] = []

    def coach(**_):
        calls.append(1)
        time.sleep(0.05)
        return _coaching()

    evaluation = InterviewEvaluation(store, coach=coach)
    assert evaluation.start("itv") is True
    assert evaluation.start("itv") is False
    _wait(lambda: evaluation.status("itv").state == "done")
    assert len(calls) == 1


def test_녹음이_없어도_코칭은_만든다(tmp_path) -> None:
    """지표는 순수 계산이고 코칭은 Grok이다 — 하나가 없다고 둘 다 버리지 않는다."""
    store = _store(tmp_path)
    _record(store, with_audio=False)
    evaluation = InterviewEvaluation(store, coach=lambda **_: _coaching())

    evaluation.start("itv")
    _wait(lambda: evaluation.status("itv").state == "done")

    feedback = evaluation.status("itv").feedback
    assert "voice" not in feedback
    assert feedback["coaching"]["summary"] == "총평"


def test_코칭이_실패하면_failed로_남는다(tmp_path) -> None:
    """조용히 넘어가면 화면이 영원히 기다린다."""
    store = _store(tmp_path)
    _record(store)

    def broken(**_):
        raise RuntimeError("xAI 호출 실패")

    evaluation = InterviewEvaluation(store, coach=broken)
    evaluation.start("itv")
    _wait(lambda: evaluation.status("itv").state == "failed")

    assert evaluation.status("itv").state == "failed"
    assert store.load("itv").feedback is None


def test_전사도_피드백에_함께_담는다(tmp_path) -> None:
    """리포트가 '이 답변 다시 듣기'를 붙이려면 발화와 시각이 같이 있어야 한다."""
    store = _store(tmp_path)
    _record(store)
    evaluation = InterviewEvaluation(store, coach=lambda **_: _coaching())

    evaluation.start("itv")
    _wait(lambda: evaluation.status("itv").state == "done")

    feedback = evaluation.status("itv").feedback
    assert feedback["durationS"] == 3.0
    assert len(feedback["utterances"]) == 2
