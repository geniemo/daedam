"""면접이 끝난 뒤 피드백을 만든다 — 지표 계산 + 코칭.

면접 종료가 이걸 깨우고, 화면은 결과를 기다렸다 읽는다. 준비 파이프라인
(preparation.py)과 같은 모양이다: 작업마다 전담 스레드가 완주하고, 브라우저
폴링은 전진과 무관한 순수 조회다 — 창을 닫아도 계속된다.

**완료의 증거는 파일이다.** `feedback.json`이 있으면 끝난 것이고, 서버가
재시작돼도 그대로다. 메모리 상태는 "지금 만드는 중"을 알리는 데만 쓴다.

**음성 지표와 코칭을 따로 담는다.** 지표는 순수 계산이라 늘 나오지만 코칭은
Grok 호출이라 실패할 수 있다. 하나로 묶으면 코칭이 실패했을 때 멀쩡한 지표까지
못 보여준다.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from typing import Any, Callable, Literal

from daedam.eval.coaching import evaluate
from daedam.eval.voice import analyze

from .store import FileInterviewStore

logger = logging.getLogger(__name__)


@dataclass
class _State:
    phase: Literal["running", "failed"]


@dataclass
class FeedbackStatus:
    """피드백 생성 상황. 화면이 이걸 보고 기다릴지 그릴지 정한다."""

    state: Literal["running", "done", "failed", "absent"]
    feedback: dict[str, Any] | None = None


class InterviewEvaluation:
    """면접 기록에서 피드백을 만드는 오케스트레이터."""

    def __init__(
        self,
        store: FileInterviewStore,
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

    def start(self, interview_id: str) -> bool:
        """피드백 생성을 시작한다. 이미 돌고 있으면 아무것도 하지 않는다.

        Returns:
            새로 시작했으면 True.
        """
        if self._states.get(interview_id) is not None:
            return False
        transcript_path = self._store.directory(interview_id) / "transcript.json"
        if not transcript_path.exists():
            # 면접이 아무것도 남기지 않았다 — 만들 것이 없다.
            logger.info("전사가 없어 피드백을 만들지 않습니다 (interview=%s)", interview_id)
            return False
        self._states[interview_id] = _State(phase="running")
        threading.Thread(target=self._run, args=(interview_id,), daemon=True).start()
        return True

    def status(self, interview_id: str) -> FeedbackStatus:
        """완료의 증거는 파일이다 — 재시작해도 done이 복원된다."""
        data = self._store.load(interview_id)
        if data is not None and data.feedback is not None:
            return FeedbackStatus(state="done", feedback=data.feedback)
        state = self._states.get(interview_id)
        if state is None:
            return FeedbackStatus(state="absent")
        return FeedbackStatus(state="failed" if state.phase == "failed" else "running")

    def _run(self, interview_id: str) -> None:
        state = self._states[interview_id]
        directory = self._store.directory(interview_id)
        try:
            transcript = json.loads(
                (directory / "transcript.json").read_text(encoding="utf-8")
            )
            data = self._store.load(interview_id)
            if data is None:
                raise ValueError(f"준비 데이터가 없습니다: {interview_id}")

            payload: dict[str, Any] = {
                "durationS": transcript.get("durationS", 0.0),
                "utterances": transcript.get("utterances", []),
            }

            # 지표는 순수 계산이라 늘 나온다. 코칭이 실패해도 이건 살린다.
            wav_path = directory / "mic.wav"
            if wav_path.exists():
                payload["voice"] = _voice_payload(analyze(wav_path, transcript))
            else:
                logger.warning("녹음이 없어 음성 지표를 건너뜁니다 (%s)", interview_id)

            coaching = self._coach(
                company=data.company, role=data.role, transcript=transcript
            )
            payload["coaching"] = coaching.as_dict()

            self._store.save_feedback(interview_id, payload)
            del self._states[interview_id]  # 완료 — 이제부터 파일이 진실을 말한다
            logger.info(
                "피드백 저장 (interview=%s): 점수 %s · 답변 %d개",
                interview_id,
                coaching.score,
                len(coaching.review.answers),
            )
        except Exception:
            logger.exception("피드백 생성 실패 (interview=%s)", interview_id)
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
