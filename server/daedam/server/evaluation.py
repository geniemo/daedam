"""면접이 끝난 뒤 피드백을 만든다 — 지표 계산 + 코칭.

면접 종료가 이걸 깨우고, 화면은 결과를 기다렸다 읽는다. 준비 파이프라인
(preparation.py)과 같은 모양이다: 작업마다 전담 스레드가 완주하고, 브라우저
폴링은 전진과 무관한 순수 조회다 — 창을 닫아도 계속된다.

**단위는 면접 한 판이다.** 같은 준비 데이터로 여러 번 면접하면 판마다 피드백이
따로 남는다 — 지난번보다 나아졌는지가 이 서비스의 재방문 이유다.

**완료의 증거는 저장된 피드백이다.** 면접 기록에 피드백이 있으면 끝난 것이고,
서버가 재시작돼도 그대로다. 메모리 상태는 "지금 만드는 중"을 알리는 데만 쓴다.

**음성 지표와 코칭을 따로 담는다.** 지표는 순수 계산이라 늘 나오지만 코칭은
LLM 호출이라 실패할 수 있다. 하나로 묶으면 코칭이 실패했을 때 멀쩡한 지표까지
못 보여준다.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from typing import Any, Callable, Literal

from daedam.eval.coaching import evaluate
from daedam.eval.gaze import analyze as analyze_gaze
from daedam.eval.voice import analyze

from .store import InterviewStore, has_answer

logger = logging.getLogger(__name__)


@dataclass
class _State:
    phase: Literal["running", "failed"]


@dataclass
class FeedbackStatus:
    """피드백 생성 상황. 화면이 이걸 보고 기다릴지 그릴지 정한다.

    `silent`와 `absent`를 가르는 이유: 둘 다 "피드백이 없다"지만 화면이 할 말이
    정반대다. absent는 아직 안 본 면접이고, silent는 시작은 했는데 지원자가 한
    마디도 안 한 면접이다 — 후자에게 "아직 면접을 진행하지 않았습니다"라고 하면
    거짓말이고, 반대로 회차로 세면 한 적 없는 면접이 이력에 생긴다.
    """

    state: Literal["running", "done", "failed", "absent", "silent"]
    feedback: dict[str, Any] | None = None


class InterviewEvaluation:
    """면접 기록에서 피드백을 만드는 오케스트레이터."""

    def __init__(
        self,
        store: InterviewStore,
        coach: Callable[..., Any] = evaluate,
    ) -> None:
        """
        Args:
            store: 준비·기록 파일 저장소.
            coach: 코칭 생성 함수. 테스트가 대역을 주입한다.
        """
        self._store = store
        self._coach = coach
        self._states: dict[str, _State] = {}

    def start(self, session_id: str) -> bool:
        """피드백 생성을 시작한다. 이미 돌고 있으면 아무것도 하지 않는다.

        Returns:
            새로 시작했으면 True.
        """
        if self._states.get(session_id) is not None:
            return False
        record = self._store.load_session(session_id)
        if record is None or not has_answer(record.transcript):
            # 지원자가 한 마디도 안 했다 — 채점할 것이 없다. 면접관 인사만 남은
            # 전사로 코칭을 부르면 "평가할 답변이 없습니다"짜리 피드백이 저장되고,
            # 그 행 때문에 한 적 없는 면접이 회차로 잡힌다(실측: 컬리 2회).
            logger.info("답변이 없어 피드백을 만들지 않습니다 (session=%s)", session_id)
            return False
        self._states[session_id] = _State(phase="running")
        threading.Thread(target=self._run, args=(session_id,), daemon=True).start()
        return True

    def status(self, session_id: str) -> FeedbackStatus:
        """완료의 증거는 저장된 피드백이다 — 재시작해도 done이 복원된다."""
        record = self._store.load_session(session_id)
        if record is not None and record.feedback is not None:
            return FeedbackStatus(state="done", feedback=record.feedback)
        state = self._states.get(session_id)
        if state is not None:
            return FeedbackStatus(
                state="failed" if state.phase == "failed" else "running"
            )
        if record is not None and not has_answer(record.transcript):
            # `start()`가 만들기를 거절한 바로 그 조건이다. 메모리가 아니라 기록을
            # 보므로 서버를 다시 띄워도 같은 답이 나온다 — 기다려도 생기지 않는
            # 결과를 화면이 계속 기다리지 않게 하는 것이 요점이다.
            return FeedbackStatus(state="silent")
        return FeedbackStatus(state="absent")

    def _run(self, session_id: str) -> None:
        state = self._states[session_id]
        try:
            record = self._store.load_session(session_id)
            if record is None:
                raise ValueError(f"면접 기록이 없습니다: {session_id}")
            data = self._store.load(record.application_id)
            if data is None:
                raise ValueError(f"준비 데이터가 없습니다: {record.application_id}")
            transcript = record.transcript or {}

            payload: dict[str, Any] = {
                "durationS": transcript.get("durationS", 0.0),
                "utterances": transcript.get("utterances", []),
            }

            # 지표는 순수 계산이라 늘 나온다. 코칭이 실패해도 이건 살린다.
            wav_path = (
                self._store.session_directory(record.application_id, session_id)
                / "mic.wav"
            )
            if wav_path.exists():
                payload["voice"] = _voice_payload(analyze(wav_path, transcript))
            else:
                logger.warning("녹음이 없어 음성 지표를 건너뜁니다 (%s)", session_id)

            # 시선·표정은 화면이 초당 한 줄로 올려 둔 것을 접는다. 답변 구간은
            # 방금 위에서 나왔으므로 여기서만 자를 수 있다 — 화면은 면접이 도는
            # 동안 그 경계를 모른다.
            gaze_path = (
                self._store.session_directory(record.application_id, session_id)
                / "gaze.json"
            )
            if gaze_path.exists():
                try:
                    timeline = json.loads(gaze_path.read_text(encoding="utf-8"))
                    gaze = analyze_gaze(
                        timeline, (payload.get("voice") or {}).get("answers")
                    )
                    if gaze is not None:
                        payload["gaze"] = gaze
                except (OSError, ValueError):
                    # 시선은 곁가지다. 못 읽어도 코칭과 음성 지표는 나가야 한다.
                    logger.warning("시선 기록을 읽지 못했습니다 (%s)", session_id, exc_info=True)

            coaching = self._coach(
                company=data.company, role=data.role, transcript=transcript
            )
            payload["coaching"] = coaching.as_dict()

            self._store.save_feedback(session_id, payload)
            del self._states[session_id]  # 완료 — 이제부터 저장된 것이 진실이다
            logger.info(
                "피드백 저장 (session=%s): 점수 %s · 답변 %d개",
                session_id,
                coaching.score,
                len(coaching.review.answers),
            )
        except Exception:
            logger.exception("피드백 생성 실패 (session=%s)", session_id)
            state.phase = "failed"


def _voice_payload(metrics: Any) -> dict[str, Any]:
    """음성 지표를 화면이 읽을 형태로. 답변마다 재생 구간이 함께 나간다."""
    return {
        "syllablesPerMinute": metrics.syllables_per_minute,
        "meanAnswerS": metrics.mean_answer_s,
        # 분당 지표(필러 워드)의 분모. 멈춘 시간을 뺀 실제 발화 시간이다.
        "spokenS": metrics.spoken_s,
        "pauseRatio": metrics.pause_ratio,
        "loudness": metrics.loudness,
        "loudnessVariation": metrics.loudness_variation,
        # 잴 수 없으면 null로 둔다 — 0으로 채우면 "바로 대답했다"는 거짓말이 된다.
        "meanStartDelayS": metrics.mean_start_delay_s,
        "answers": [
            {
                "startS": answer.start_s,
                "endS": answer.end_s,
                "text": answer.text,
                "pauses": len(answer.pauses),
                "startDelayS": answer.start_delay_s,
            }
            for answer in metrics.answers
        ],
    }
