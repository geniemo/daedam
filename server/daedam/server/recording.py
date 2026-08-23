"""면접 한 판을 파일로 남긴다 — 지원자 음성과 양쪽 전사.

면접이 끝나면 아무것도 남지 않았다. 세션 이벤트는 메모리에만 있고 서버가
재시작되면 사라진다. 리포트는 그 위에 세워야 하므로 여기가 시작점이다.

남기는 것:
  {면접 디렉터리}/mic.pcm        지원자 마이크 원본 (16-bit LE / 16kHz / mono)
  {면접 디렉터리}/mic.wav        재생용. 면접이 끝날 때 헤더를 씌워 만든다
  {면접 디렉터리}/transcript.json 누가 언제 무엇을 말했는가

**pcm으로 쓰고 끝에 wav로 바꾸는 이유**: 한 면접이 커넥션 여러 개에 걸친다.
Live API 커넥션 수명이 ~10분이라 15~20분 면접은 반드시 재접속하는데, `wave`
모듈은 이어쓰기를 못 한다. 원본을 이어 붙였다가 마지막에 한 번 감싼다 —
중간에 서버가 죽어도 pcm은 그대로 남아 되살릴 수 있다.

**시각의 기준은 벽시계가 아니라 쓴 바이트다.** `at`은 오디오 안에서의 위치라,
리포트가 "이 답변 다시 듣기"를 붙일 때 그대로 탐색 지점이 된다. 벽시계로
재면 재접속 사이의 공백만큼 어긋난다.
"""

from __future__ import annotations

import json
import logging
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

#: 프론트 pcm-recorder가 보내는 규격. ADK는 포맷 변환을 하지 않으므로 이 값이
#: 곧 브리지가 받는 바이트의 규격이다 (live_bridge._INPUT_MIME).
SAMPLE_RATE = 16_000
SAMPLE_WIDTH = 2  # 16-bit

Speaker = Literal["interviewer", "applicant"]


@dataclass
class Utterance:
    """한 사람이 이어서 말한 한 토막."""

    speaker: Speaker
    text: str
    #: 오디오 시작점부터의 초. 재생 탐색 지점과 같은 축이다.
    at: float

    def as_dict(self) -> dict[str, Any]:
        return {"speaker": self.speaker, "text": self.text, "at": round(self.at, 2)}


@dataclass
class InterviewRecording:
    """면접 하나의 녹음. 커넥션이 끊겼다 붙어도 같은 객체를 계속 쓴다."""

    directory: Path
    utterances: list[Utterance] = field(default_factory=list)
    #: 면접관의 말이 **브라우저에서** 끝난 시각들. 지원자가 질문을 다 들은
    #: 순간이라, "답변까지 걸린 시간"의 기준선이 된다. 서버는 모델이 생성을
    #: 마친 시각만 알아서 재생 지연만큼 이르다.
    question_ends: list[float] = field(default_factory=list)
    _bytes: int = 0
    _handle: Any = None

    def __post_init__(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        # 이미 쓰던 파일이 있으면 이어 쓴다 — 재접속은 같은 면접이다.
        # 바이트만 이어받고 전사를 두고 오면, 다음 저장이 앞 커넥션의 발화를
        # 덮어쓴다. 15~20분 면접은 반드시 재접속하므로 실제로 잃는다.
        if self._pcm_path.exists():
            self._bytes = self._pcm_path.stat().st_size
        self.utterances = self._load_utterances()

    def _load_utterances(self) -> list[Utterance]:
        if not self._transcript_path.exists():
            return []
        try:
            saved = json.loads(self._transcript_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.exception("앞선 전사를 읽지 못했습니다 (%s)", self._transcript_path)
            return []
        self.question_ends = list(saved.get("questionEnds", []))
        return [
            Utterance(speaker=item["speaker"], text=item["text"], at=item["at"])
            for item in saved.get("utterances", [])
        ]

    @property
    def elapsed_s(self) -> float:
        """지금까지 받은 오디오의 길이(초)."""
        return self._bytes / (SAMPLE_RATE * SAMPLE_WIDTH)

    def write_audio(self, pcm: bytes) -> None:
        """마이크 프레임을 이어 붙인다. 실패해도 면접을 멈추지 않는다.

        파일 핸들을 열어 둔 채로 쓴다. 프레임마다 열고 닫으면 그 동기 I/O가
        브리지의 이벤트 루프 안에서 20~60ms마다 일어난다 — 마이크를 Gemini로
        넘기는 길목을 막는다.
        """
        if not pcm:
            return
        try:
            if self._handle is None:
                self._handle = self._pcm_path.open("ab")
            self._handle.write(pcm)
            self._bytes += len(pcm)
        except OSError:
            logger.exception("녹음 쓰기 실패 (%s)", self._pcm_path)

    def mark_question_end(self) -> None:
        """면접관의 말이 브라우저에서 끝났다. 지금 위치를 적어 둔다.

        재생 버퍼가 잠깐 마르는 것으로도 신호가 오므로 한 질문에 여러 번
        찍힐 수 있다. 거르지 않고 다 남긴다 — 어느 것이 진짜 끝인지는 답변
        시작과 견줘야 알 수 있고, 그건 지표 쪽 판단이다.
        """
        self.question_ends.append(self.elapsed_s)

    def note(self, speaker: Speaker, text: str) -> None:
        """전사 한 토막을 지금 위치에 적는다. 빈 문자열은 무시한다."""
        text = text.strip()
        if not text:
            return
        self.utterances.append(Utterance(speaker=speaker, text=text, at=self.elapsed_s))

    def finish(self) -> None:
        """면접 종료 — 재생용 wav를 만들고 전사를 저장한다."""
        self._close_handle()
        self._write_wav()
        self._write_transcript()
        logger.info(
            "면접 기록 저장 (%s): 음성 %.1f초 · 발화 %d토막",
            self.directory.name,
            self.elapsed_s,
            len(self.utterances),
        )

    def _close_handle(self) -> None:
        """버퍼를 비우고 핸들을 놓는다. wav를 만들기 전에 반드시 거친다."""
        if self._handle is None:
            return
        try:
            self._handle.close()
        except OSError:
            logger.exception("녹음 파일을 닫지 못했습니다 (%s)", self._pcm_path)
        self._handle = None

    def _write_wav(self) -> None:
        if not self._pcm_path.exists():
            return
        try:
            pcm = self._pcm_path.read_bytes()
            with wave.open(str(self._wav_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(SAMPLE_WIDTH)
                wav.setframerate(SAMPLE_RATE)
                wav.writeframes(pcm)
        except (OSError, wave.Error):
            # wav를 못 만들어도 pcm 원본은 남아 있다 — 나중에 되살릴 수 있다.
            logger.exception("재생용 wav 생성 실패 (%s)", self._wav_path)

    def transcript_payload(self) -> dict[str, Any]:
        """지금까지의 전사. 브리지가 이걸 받아 면접 기록으로 올린다.

        디스크의 `transcript.json`은 재접속이 이어 쓰기 위한 작업 파일이고,
        질의 대상이 되는 사본은 데이터베이스에 있다.
        """
        return {
            "sampleRate": SAMPLE_RATE,
            "durationS": round(self.elapsed_s, 2),
            "utterances": [utterance.as_dict() for utterance in self.utterances],
            "questionEnds": [round(at, 2) for at in self.question_ends],
        }

    def _write_transcript(self) -> None:
        payload = self.transcript_payload()
        try:
            self._transcript_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            logger.exception("전사 저장 실패 (%s)", self._transcript_path)

    @staticmethod
    def discard(directory: Path) -> bool:
        """면접 기록과 그 위에 만든 피드백을 지운다. 리서치·질문은 그대로 둔다.

        면접을 다시 하려면 앞 판의 흔적이 없어야 한다 — 이어 쓰기 때문에
        남겨 두면 새 면접이 앞 면접 뒤에 붙는다.

        Returns:
            하나라도 지웠으면 True.
        """
        removed = False
        for name in ("mic.pcm", "mic.wav", "transcript.json", "feedback.json"):
            path = directory / name
            try:
                if path.exists():
                    path.unlink()
                    removed = True
            except OSError:
                logger.exception("면접 기록 삭제 실패 (%s)", path)
        return removed

    @property
    def _pcm_path(self) -> Path:
        return self.directory / "mic.pcm"

    @property
    def _wav_path(self) -> Path:
        return self.directory / "mic.wav"

    @property
    def _transcript_path(self) -> Path:
        return self.directory / "transcript.json"
