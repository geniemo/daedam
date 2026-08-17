"""녹음과 전사에서 음성 지표를 낸다.

리포트의 음성 카드가 여기서 나온다. 입력은 면접이 남긴 두 파일뿐이고
(`mic.wav`, `transcript.json`) 외부 호출이 없다 — 순수 계산이다.

**소리로 재는 것과 글자로 재는 것을 나눈다.** 말이 언제 시작하고 끝났는지는
소리만 안다. 전사의 시각(`at`)은 최종 전사 이벤트가 도착한 때라 발화보다
1초 남짓 늦고, 시작 시각은 아예 없다.

**필러 워드는 내지 않는다.** 전사가 "음·어" 같은 것을 지워서 세면 언제나 0이
나온다 — 없는 것이 아니라 못 보는 것이다. 대신 답변 중 멈춤을 소리에서 잰다.
코칭에서 묻는 것("말이 자주 끊기는가")은 같고 이쪽은 실측이 된다.

세그먼트 임계값이 거칠어도 되는 이유: 브라우저가 노이즈 게이팅을 해서 침묵이
사실상 0이다(실측 중앙 RMS 1, 발화 구간 90퍼센타일 1290). 임계값을 100에서
400까지 바꿔도 같은 구간이 나온다.
"""

from __future__ import annotations

import re
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

#: 에너지를 재는 창. 20ms는 음절 하나보다 짧아 말의 시작·끝을 놓치지 않는다.
_FRAME_S = 0.02
#: 말로 볼 RMS 하한. 게이팅된 침묵(≈0)과 발화(≈1000+) 사이가 넓어 여유가 크다.
_VOICE_RMS = 200.0
#: 이보다 길게 비면 다른 답변으로 본다. 답변 사이에는 면접관이 몇 초씩
#: 말하므로 여유롭게 잡아도 갈린다.
_JOIN_GAP_S = 1.2
#: 이보다 짧은 소리는 기침·잡음으로 보고 답변으로 세지 않는다.
_MIN_SPEECH_S = 0.25
#: 답변 안에서 이만큼 이상 비면 "멈춤"으로 센다. 반드시 _JOIN_GAP_S보다
#: 짧아야 한다 — 같으면 멈춤으로 셀 만큼 길 때 이미 답변이 갈려서 멈춤이
#: 영영 0으로 나온다.
_PAUSE_S = 0.35

_HANGUL = re.compile(r"[가-힣]")


@dataclass(frozen=True)
class Answer:
    """지원자가 한 번 이어서 말한 구간."""

    start_s: float
    end_s: float
    text: str
    #: 답변 안에서 말이 멈춘 구간들. 숨이 아니라 머뭇거림으로 볼 길이만.
    pauses: tuple[tuple[float, float], ...]
    #: 이 구간의 평균 RMS. 목소리 크기.
    loudness: float

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    @property
    def syllables(self) -> int:
        return len(_HANGUL.findall(self.text))

    @property
    def pause_s(self) -> float:
        return sum(end - start for start, end in self.pauses)


@dataclass(frozen=True)
class VoiceMetrics:
    """리포트의 음성 카드가 그대로 읽는 값."""

    answers: tuple[Answer, ...]
    #: 음절/분. 말한 시간으로만 나눈다 — 멈춘 시간을 포함하면 느리게 나온다.
    syllables_per_minute: float
    #: 답변 하나의 평균 길이(초).
    mean_answer_s: float
    #: 답변 시간 중 멈춰 있던 비율(0~1).
    pause_ratio: float
    #: 목소리 크기의 평균과 흔들림. 흔들림은 변동계수라 작을수록 고르다.
    loudness: float
    loudness_variation: float

    @property
    def answered(self) -> int:
        return len(self.answers)


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """모노 16-bit wav를 float 배열과 표본율로 읽는다."""
    with wave.open(str(path), "rb") as handle:
        rate = handle.getframerate()
        raw = handle.readframes(handle.getnframes())
    return np.frombuffer(raw, dtype="<i2").astype(np.float32), rate


def frame_rms(pcm: np.ndarray, sample_rate: int) -> np.ndarray:
    """20ms 창마다의 RMS. 이 배열이 모든 시간 계산의 바탕이다."""
    window = max(1, int(sample_rate * _FRAME_S))
    usable = len(pcm) // window * window
    if usable == 0:
        return np.zeros(0, dtype=np.float32)
    frames = pcm[:usable].reshape(-1, window)
    return np.sqrt((frames**2).mean(axis=1))


def speech_spans(
    rms: np.ndarray, *, join_gap_s: float = _JOIN_GAP_S, min_speech_s: float = _MIN_SPEECH_S
) -> list[tuple[int, int]]:
    """말이 이어진 구간을 프레임 번호로 돌려준다. 끝은 포함하지 않는다.

    소리가 난 프레임만 모아 이웃 간격으로 자른다. 침묵을 따라가며 자르면
    끝에 붙은 침묵이 마지막 구간에 딸려 들어간다 — 답변이 실제보다 길어진다.
    """
    voiced = np.flatnonzero(rms > _VOICE_RMS)
    if voiced.size == 0:
        return []
    join_gap = max(1, int(join_gap_s / _FRAME_S))
    # 이웃한 발화 프레임 사이가 join_gap보다 벌어지면 거기서 답변이 갈린다.
    breaks = np.flatnonzero(np.diff(voiced) > join_gap)
    starts = np.concatenate(([voiced[0]], voiced[breaks + 1]))
    ends = np.concatenate((voiced[breaks], [voiced[-1]])) + 1
    # 길이가 아니라 **실제 소리가 난 프레임 수**로 거른다. 길이로 거르면
    # 1.2초 떨어진 잡음 두 점이 "1.2초짜리 답변"이 된다 — 실측에서 평균 RMS
    # 43짜리 구간이 진짜 답변의 전사를 가로챘다.
    least = max(1, int(min_speech_s / _FRAME_S))
    spans = []
    for a, b in zip(starts, ends):
        voiced_in = int(((voiced >= a) & (voiced < b)).sum())
        if voiced_in >= least:
            spans.append((int(a), int(b)))
    return spans


def _pauses_in(rms: np.ndarray, start: int, end: int) -> tuple[tuple[float, float], ...]:
    """답변 안에서 말이 멈춘 구간. 숨보다 긴 것만 센다."""
    quiet = rms[start:end] <= _VOICE_RMS
    least = max(1, int(_PAUSE_S / _FRAME_S))
    found: list[tuple[float, float]] = []
    run = 0
    for offset, is_quiet in enumerate(quiet):
        if is_quiet:
            run += 1
            continue
        if run >= least:
            found.append(((start + offset - run) * _FRAME_S, (start + offset) * _FRAME_S))
        run = 0
    if run >= least:
        found.append(((end - run) * _FRAME_S, end * _FRAME_S))
    return tuple(found)


def _text_for(spans: list[tuple[int, int]], utterances: list[dict[str, Any]]) -> list[str]:
    """구간마다 전사를 붙인다.

    전사의 `at`은 최종 이벤트가 도착한 때라 발화가 끝난 **뒤**다. 그래서 구간이
    끝난 뒤 처음 도착한 지원자 전사를 그 구간의 것으로 본다.
    """
    pending = [u for u in utterances if u.get("speaker") == "applicant"]
    texts: list[str] = []
    for _, end in spans:
        end_s = end * _FRAME_S
        match = next((u for u in pending if u["at"] >= end_s - _FRAME_S), None)
        if match is None:
            texts.append("")
            continue
        pending = pending[pending.index(match) + 1 :]
        texts.append(match["text"])
    return texts


def analyze(wav_path: Path, transcript: dict[str, Any]) -> VoiceMetrics:
    """녹음과 전사에서 음성 지표를 낸다. 답변이 없으면 0으로 채운 결과."""
    pcm, rate = read_wav(wav_path)
    rms = frame_rms(pcm, rate)
    spans = speech_spans(rms)
    texts = _text_for(spans, transcript.get("utterances", []))

    answers = tuple(
        Answer(
            start_s=round(start * _FRAME_S, 2),
            end_s=round(end * _FRAME_S, 2),
            text=text,
            pauses=_pauses_in(rms, start, end),
            loudness=float(rms[start:end].mean()) if end > start else 0.0,
        )
        for (start, end), text in zip(spans, texts)
    )
    if not answers:
        return VoiceMetrics(
            answers=(),
            syllables_per_minute=0.0,
            mean_answer_s=0.0,
            pause_ratio=0.0,
            loudness=0.0,
            loudness_variation=0.0,
        )

    spoken_s = sum(a.duration_s - a.pause_s for a in answers)
    syllables = sum(a.syllables for a in answers)
    total_s = sum(a.duration_s for a in answers)
    louds = np.array([a.loudness for a in answers], dtype=np.float32)
    mean_loud = float(louds.mean())
    return VoiceMetrics(
        answers=answers,
        # 멈춘 시간을 빼고 나눈다 — 포함하면 또박또박 말해도 느리게 나온다.
        syllables_per_minute=round(syllables / spoken_s * 60, 1) if spoken_s else 0.0,
        mean_answer_s=round(total_s / len(answers), 2),
        pause_ratio=round(sum(a.pause_s for a in answers) / total_s, 3) if total_s else 0.0,
        loudness=round(mean_loud, 1),
        loudness_variation=round(float(louds.std()) / mean_loud, 3) if mean_loud else 0.0,
    )
