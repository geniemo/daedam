"""녹음과 전사에서 음성 지표를 낸다.

리포트의 음성 카드가 여기서 나온다. 입력은 면접이 남긴 두 파일뿐이고
(`mic.wav`, `transcript.json`) 외부 호출이 없다 — 순수 계산이다.

**소리로 재는 것과 글자로 재는 것을 나눈다.** 말이 언제 시작하고 끝났는지는
소리만 안다. 전사의 시각(`at`)은 최종 전사 이벤트가 도착한 때라 발화보다
1초 남짓 늦고, 시작 시각은 아예 없다.

**말버릇은 여기서 세지 않는다.** "그 프로젝트"의 "그"와 "어… 그러니까"의 "그"는
같은 글자라 낱말 목록으로는 못 가른다. 문맥이 필요하므로 코칭(daedam/eval/
coaching.py)이 답변을 읽으며 함께 센다. 여기서는 소리로 답변 중 멈춤을 잰다 —
"말이 자주 끊기는가"는 소리가 더 정확하다.

말 임계값은 녹음마다 다시 잡는다. 고정값으로 두면 마이크 게인에 통째로
휘둘린다 — 실측에서 AGC를 끄자 발화가 하나도 안 잡혔다. 노이즈 억제 덕에
침묵이 거의 0이라, 또렷하게 말한 대목(상위 1퍼센타일) 대비 비율로 잡으면
게인이 달라져도 같은 자리를 가른다.
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
#: 말로 볼 RMS의 절대 하한. 이보다 낮으면 아무리 상대적으로 커도 말이 아니다.
_RMS_FLOOR = 40.0
#: 말 임계값을 녹음의 큰 소리 대비 몇 배로 잡을지. 고정값으로 두면 마이크
#: 게인에 따라 통째로 무너진다 — 실측에서 AGC를 끄자 200 넘는 프레임이
#: 1075개(21초)나 있는데도 구간 평균이 못 미쳐 발화가 하나도 안 잡혔다.
_RMS_RATIO = 0.1
#: 재생 종료 표시가 없을 때만 쓰는 폴백. 이보다 길게 비면 다른 답변으로 본다.
#: 표시가 있으면 침묵 길이가 아니라 **면접관이 말한 지점**으로 가른다 —
#: 생각하느라 쉬는 것과 답변이 끝난 것은 침묵 길이로 구분되지 않는다.
_JOIN_GAP_S = 1.2
#: 이보다 짧은 소리는 기침·잡음으로 보고 답변으로 세지 않는다.
_MIN_SPEECH_S = 0.25
#: 답변 안에서 이만큼 이상 비면 "멈춤"으로 센다. 반드시 답변을 가르는 간격보다
#: 짧아야 한다 — 같으면 멈춤으로 셀 만큼 길 때 이미 답변이 갈려서 멈춤이
#: 영영 0으로 나온다.
#:
#: 실측으로 정했다(4분 40초 면접, 지원자 발화 104초). 멈춤 길이를 0.2초부터
#: 전부 뽑으면 0.20~0.70에 43개가 몰려 있고 0.86초 위로 5개만 떨어져 나온다 —
#: **0.70과 0.86 사이가 비어 있다.** 앞 무리는 숨과 어절 경계이고 뒤가 실제로
#: 말이 끊긴 자리다. 앞서 0.35초로 세던 때는 7초짜리 답변에 "2번 끊겼습니다"가
#: 붙었는데, 그 길이 안에 머뭇거림이 두 번 있을 수는 없다.
#:
#: 숨을 멈춤에서 뺀 결과로 두 지표의 기준이 함께 움직인다 — `pause_ratio`의
#: 권장선과 `syllables_per_minute`의 분모다. 각각의 주석에 적어 두었다.
_PAUSE_S = 0.8
#: 한 질문에 대한 답변 안에서 허용하는 최대 공백. 생각하느라 쉬는 것은
#: 여기 들어오고, 이보다 벌어지면 같은 답변으로 보지 않는다 — 질문 경계를
#: 놓쳤을 때(모델이 멈춘 판) 한 창이 면접 전체를 삼키는 것을 막는다.
_ANSWER_GAP_S = 5.0

_HANGUL = re.compile(r"[가-힣]")


@dataclass(frozen=True)
class Answer:
    """지원자가 한 번 이어서 말한 구간."""

    start_s: float
    end_s: float
    text: str
    #: 답변 안에서 말이 멈춘 구간들. 숨은 빠져 있고 머뭇거림만 남는다.
    pauses: tuple[tuple[float, float], ...]
    #: 이 구간에서 **소리가 난 프레임만**의 평균 RMS. 조용한 프레임까지 넣으면
    #: 멈춤이 많은 답변이 자동으로 "작은 목소리"가 되어 성량과 멈춤이 섞인다.
    loudness: float
    #: 질문이 끝나고 이 답변을 시작하기까지 걸린 초. 기준선을 못 찾으면 None
    #: (첫 답변 앞에 재생 종료 신호가 없었던 경우).
    start_delay_s: float | None = None

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
    #: 실제로 말한 시간의 합(초) — 멈춘 시간을 뺀 값. 분당 지표의 분모다.
    spoken_s: float
    #: 답변 시간 중 멈춰 있던 비율(0~1).
    pause_ratio: float
    #: 목소리 크기의 평균과 흔들림.
    #:
    #: 둘 다 **소리가 난 프레임 전체**에서 낸다. 답변별 평균끼리 비교하면
    #: 표본이 답변 수(보통 2~4개)뿐이라 한 번 크게 말한 답변 하나에 값이
    #: 휘둘리고, 답변 안에서 목소리가 흔들리는 것은 아예 못 본다.
    #: 흔들림은 변동계수라 작을수록 고르다.
    loudness: float
    loudness_variation: float
    #: 질문이 끝나고 답을 시작하기까지의 평균 초. 잴 수 있는 답변이 없으면 None.
    mean_start_delay_s: float | None = None

    @property
    def answered(self) -> int:
        return len(self.answers)


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """모노 16-bit wav를 float 배열과 표본율로 읽는다."""
    with wave.open(str(path), "rb") as handle:
        rate = handle.getframerate()
        raw = handle.readframes(handle.getnframes())
    return np.frombuffer(raw, dtype="<i2").astype(np.float32), rate


def voice_threshold(rms: np.ndarray) -> float:
    """이 녹음에서 말로 볼 RMS. 큰 소리 대비 상대값이다.

    노이즈 억제 덕에 침묵은 거의 0이라, 상위 1퍼센타일(사람이 또렷하게 말한
    대목)의 일정 비율을 경계로 삼으면 마이크 게인이 달라져도 같은 자리를
    가른다. 절대 하한을 둬서 통째로 조용한 녹음에서 잡음이 말로 잡히지 않게
    한다.
    """
    if rms.size == 0:
        return _RMS_FLOOR
    return max(_RMS_FLOOR, float(np.percentile(rms, 99)) * _RMS_RATIO)


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
    threshold = voice_threshold(rms)
    voiced = np.flatnonzero(rms > threshold)
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
    # 두 가지를 함께 본다. 소리 난 프레임이 충분히 많아야 하고(짧은 잡음 배제),
    # 구간 **평균**도 말 수준이어야 한다. 앞의 조건만 두면 띄엄띄엄한 잡음이
    # 몇 초짜리 구간으로 살아남는다 — 실측에서 평균 RMS 92~113짜리 구간이
    # 셋 나왔고, 그게 말하기 속도를 60음절/분으로 끌어내렸다.
    least = max(1, int(min_speech_s / _FRAME_S))
    spans = []
    for a, b in zip(starts, ends):
        voiced_in = int(((voiced >= a) & (voiced < b)).sum())
        if voiced_in >= least and float(rms[a:b].mean()) >= threshold:
            spans.append((int(a), int(b)))
    return spans


def spans_between_questions(
    rms: np.ndarray, question_ends: list[float]
) -> tuple[list[tuple[int, int]], list[tuple[float, float]]]:
    """질문과 질문 사이의 지원자 발화를 한 답변으로 묶는다.

    답변의 경계는 침묵 길이가 아니라 대화 구조다 — 면접관이 다시 말하기
    전까지가 한 답변이다. 생각하느라 2초 쉰 것과 답변을 마친 것은 침묵
    길이로는 구분되지 않는다.

    헤드폰을 쓰면 마이크에 면접관 소리가 안 들어오므로, 두 질문 사이의
    발화는 전부 지원자의 것이다.

    창 안에서도 크게 벌어진 곳은 가르고 **첫 덩어리만** 답변으로 본다.
    질문 경계를 놓치면(모델이 멈춘 판) 한 창이 몇 분을 삼키는데, 그 전체를
    한 답변으로 보면 평균이 침묵 수준으로 내려가 통째로 버려진다.

    Returns:
        (발화 구간 프레임, 전사를 모을 시간 창) — 둘의 길이는 같다.
    """
    threshold = voice_threshold(rms)
    voiced = np.flatnonzero(rms > threshold)
    if voiced.size == 0:
        return [], []

    bounds = [int(at / _FRAME_S) for at in sorted(question_ends)] + [len(rms)]
    least = max(1, int(_MIN_SPEECH_S / _FRAME_S))
    gap = max(1, int(_ANSWER_GAP_S / _FRAME_S))

    spans: list[tuple[int, int]] = []
    windows: list[tuple[float, float]] = []
    for start, stop in zip(bounds, bounds[1:]):
        inside = voiced[(voiced >= start) & (voiced < stop)]
        if inside.size < least:
            continue
        cuts = np.flatnonzero(np.diff(inside) > gap)
        chunk_starts = np.concatenate(([inside[0]], inside[cuts + 1]))
        chunk_ends = np.concatenate((inside[cuts], [inside[-1]])) + 1
        for first, last in zip(chunk_starts, chunk_ends):
            first, last = int(first), int(last)
            if last - first < least or float(rms[first:last].mean()) < threshold:
                continue
            spans.append((first, last))
            # 전사는 발화보다 늦게 도착한다. 마지막 창은 열어 둔다 — 녹음이
            # 끝난 뒤에 도착한 전사도 그 답변의 것이다.
            windows.append(
                (
                    start * _FRAME_S,
                    float("inf") if stop >= len(rms) else stop * _FRAME_S,
                )
            )
            break  # 질문 하나에 답변 하나 — 뒤에 남은 소리는 그 답변이 아니다
    return spans, windows


def _voiced_mean(window: np.ndarray, threshold: float) -> float:
    """소리가 난 프레임만의 평균 RMS. 없으면 0."""
    voiced = window[window > threshold]
    return float(voiced.mean()) if voiced.size else 0.0


def _pauses_in(rms: np.ndarray, start: int, end: int) -> tuple[tuple[float, float], ...]:
    """답변 안에서 말이 멈춘 구간. 숨은 빼고 머뭇거림만 센다(`_PAUSE_S`)."""
    quiet = rms[start:end] <= voice_threshold(rms)
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
    """구간마다 전사를 붙인다 (질문 경계를 모를 때의 폴백).

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


def _text_between(
    windows: list[tuple[float, float]], utterances: list[dict[str, Any]]
) -> list[str]:
    """질문과 질문 사이에 도착한 지원자 전사를 **모두** 이어 붙인다.

    한 답변이 전사 여러 조각으로 온다. 말하다 잠깐 쉬면 Live API가 거기서
    발화가 끝난 것으로 보고 finished를 내기 때문이다(실측: "안녕하십니까? 음"
    다음에 "어, 박지호입니다. 음."). 하나만 붙이면 나머지를 통째로 잃는다.
    """
    spoken = [u for u in utterances if u.get("speaker") == "applicant"]
    return [
        " ".join(u["text"] for u in spoken if start <= u["at"] < stop).strip()
        for start, stop in windows
    ]


def _start_delay(start_s: float, question_ends: list[float]) -> float | None:
    """질문이 끝나고 답을 시작하기까지 걸린 초.

    재생 버퍼가 잠깐 마르는 것으로도 신호가 오므로 한 질문에 표시가 여럿
    찍힌다. 답변 시작 **직전**의 것이 진짜 끝이다 — 그보다 앞의 것들은
    질문을 말하는 도중에 생긴 틈이다.
    """
    before = [at for at in question_ends if at <= start_s]
    if not before:
        return None
    return round(start_s - max(before), 2)


def analyze(wav_path: Path, transcript: dict[str, Any]) -> VoiceMetrics:
    """녹음과 전사에서 음성 지표를 낸다. 답변이 없으면 0으로 채운 결과."""
    pcm, rate = read_wav(wav_path)
    rms = frame_rms(pcm, rate)
    question_ends = list(transcript.get("questionEnds", []))
    # 질문 경계를 알면 그것으로 가른다. 없으면(옛 녹음) 침묵 길이로 폴백한다.
    if question_ends:
        spans, windows = spans_between_questions(rms, question_ends)
        texts = _text_between(windows, transcript.get("utterances", []))
    else:
        spans = speech_spans(rms)
        texts = _text_for(spans, transcript.get("utterances", []))

    answers = tuple(
        Answer(
            start_s=round(start * _FRAME_S, 2),
            end_s=round(end * _FRAME_S, 2),
            text=text,
            pauses=_pauses_in(rms, start, end),
            loudness=_voiced_mean(rms[start:end], voice_threshold(rms)),
            start_delay_s=_start_delay(start * _FRAME_S, question_ends),
        )
        for (start, end), text in zip(spans, texts)
    )
    if not answers:
        return VoiceMetrics(
            answers=(),
            syllables_per_minute=0.0,
            mean_answer_s=0.0,
            spoken_s=0.0,
            pause_ratio=0.0,
            loudness=0.0,
            loudness_variation=0.0,
        )

    spoken_s = sum(a.duration_s - a.pause_s for a in answers)
    syllables = sum(a.syllables for a in answers)
    total_s = sum(a.duration_s for a in answers)
    # 소리가 난 프레임을 답변 전체에서 모아 그 위에서 잰다. 답변별 평균끼리
    # 비교하면 표본이 답변 수뿐이고 멈춤이 성량에 섞인다.
    threshold = voice_threshold(rms)
    voiced_frames = np.concatenate(
        [
            window[window > threshold]
            for window in (
                rms[int(a.start_s / _FRAME_S) : int(a.end_s / _FRAME_S)] for a in answers
            )
            if window.size
        ]
        or [np.zeros(0, dtype=np.float32)]
    )
    mean_loud = float(voiced_frames.mean()) if voiced_frames.size else 0.0
    delays = [a.start_delay_s for a in answers if a.start_delay_s is not None]
    return VoiceMetrics(
        answers=answers,
        # 멈춘 시간을 빼고 나눈다 — 포함하면 또박또박 말해도 느리게 나온다.
        syllables_per_minute=round(syllables / spoken_s * 60, 1) if spoken_s else 0.0,
        mean_answer_s=round(total_s / len(answers), 2),
        spoken_s=round(spoken_s, 2),
        pause_ratio=round(sum(a.pause_s for a in answers) / total_s, 3) if total_s else 0.0,
        loudness=round(mean_loud, 1),
        loudness_variation=(
            round(float(voiced_frames.std()) / mean_loud, 3) if mean_loud else 0.0
        ),
        mean_start_delay_s=round(sum(delays) / len(delays), 2) if delays else None,
    )
