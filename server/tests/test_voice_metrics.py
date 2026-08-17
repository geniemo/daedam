"""음성 지표 테스트.

합성 오디오로 규칙을 못 박는다. 실제 녹음은 회차마다 다르지만 "얼마나 비어야
답변이 갈리는가" 같은 판단은 고정돼 있어야 한다.
"""

import wave

import numpy as np
import pytest

from daedam.eval.voice import analyze, frame_rms, speech_spans

RATE = 16_000


def _tone(seconds: float, amplitude: float = 3000.0) -> np.ndarray:
    """말로 잡힐 만한 소리. 파형 모양은 RMS에만 쓰이므로 사인파면 충분하다."""
    t = np.arange(int(RATE * seconds)) / RATE
    return (amplitude * np.sin(2 * np.pi * 220 * t)).astype(np.int16)


def _silence(seconds: float) -> np.ndarray:
    return np.zeros(int(RATE * seconds), dtype=np.int16)


def _wav(tmp_path, *chunks: np.ndarray):
    path = tmp_path / "mic.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(np.concatenate(chunks).tobytes())
    return path


def _transcript(*utterances):
    return {
        "sampleRate": RATE,
        "utterances": [
            {"speaker": speaker, "text": text, "at": at}
            for speaker, text, at in utterances
        ],
    }


def test_소리가_없으면_답변도_없다(tmp_path) -> None:
    metrics = analyze(_wav(tmp_path, _silence(3.0)), _transcript())
    assert metrics.answered == 0
    assert metrics.syllables_per_minute == 0.0


def test_한_번_말하면_답변_하나(tmp_path) -> None:
    """끝에 붙은 침묵이 답변 길이에 딸려 들어가면 안 된다."""
    path = _wav(tmp_path, _silence(1.0), _tone(2.0), _silence(1.0))
    metrics = analyze(path, _transcript(("applicant", "안녕하세요", 3.4)))

    (answer,) = metrics.answers
    assert answer.start_s == pytest.approx(1.0, abs=0.05)
    assert answer.end_s == pytest.approx(3.0, abs=0.05)
    assert answer.text == "안녕하세요"


def test_긴_공백은_답변을_가른다(tmp_path) -> None:
    """멈춤(0.35초)보다 확실히 길어야 다른 답변이다."""
    path = _wav(tmp_path, _tone(1.0), _silence(2.0), _tone(1.0))
    metrics = analyze(path, _transcript(("applicant", "첫째", 1.5), ("applicant", "둘째", 4.5)))

    assert [a.text for a in metrics.answers] == ["첫째", "둘째"]


def test_짧은_공백은_한_답변_안의_숨이다(tmp_path) -> None:
    """문장 사이 숨으로 답변을 쪼개면 안 된다."""
    path = _wav(tmp_path, _tone(1.0), _silence(0.2), _tone(1.0))
    metrics = analyze(path, _transcript(("applicant", "이어서 말합니다", 2.5)))

    (answer,) = metrics.answers
    assert answer.duration_s == pytest.approx(2.2, abs=0.1)
    assert answer.pauses == ()  # 숨은 멈춤으로 세지 않는다


def test_답변_안의_멈춤은_센다(tmp_path) -> None:
    """머뭇거림을 소리로 잰다 — 전사는 '음·어'를 지워서 글자로는 못 센다."""
    path = _wav(tmp_path, _tone(1.0), _silence(0.6), _tone(1.0))
    metrics = analyze(path, _transcript(("applicant", "머뭇", 2.9)))

    (answer,) = metrics.answers
    assert len(answer.pauses) == 1
    assert metrics.pause_ratio > 0


def test_말하기_속도는_멈춘_시간을_빼고_잰다(tmp_path) -> None:
    """멈춤을 포함해 나누면 또박또박 말해도 느리게 나온다."""
    path = _wav(tmp_path, _tone(1.0), _silence(0.6), _tone(1.0))
    metrics = analyze(path, _transcript(("applicant", "가나다라마가나다라마", 2.9)))

    # 음절 10개, 실제 말한 시간 2.0초 → 300음절/분 언저리
    assert metrics.syllables_per_minute == pytest.approx(300, rel=0.15)


def test_짧은_잡음은_답변이_아니다(tmp_path) -> None:
    path = _wav(tmp_path, _tone(0.1), _silence(1.0), _tone(1.0))
    metrics = analyze(path, _transcript(("applicant", "본 답변", 2.5)))
    assert metrics.answered == 1


def test_면접관_전사는_답변에_붙지_않는다(tmp_path) -> None:
    path = _wav(tmp_path, _silence(0.5), _tone(1.0))
    metrics = analyze(
        path,
        _transcript(("interviewer", "질문입니다", 0.4), ("applicant", "답변입니다", 1.9)),
    )
    assert [a.text for a in metrics.answers] == ["답변입니다"]


def test_목소리_흔들림은_변동계수다(tmp_path) -> None:
    """크기가 고르면 0에 가깝다. 값이 커지면 들쭉날쭉하다는 뜻이다."""
    path = _wav(tmp_path, _tone(1.0, 3000), _silence(1.0), _tone(1.0, 3000))
    metrics = analyze(path, _transcript(("applicant", "가", 1.5), ("applicant", "나", 3.5)))
    assert metrics.loudness_variation < 0.05


def test_구간_나누기는_임계값에_둔감하다() -> None:
    """게이팅 덕에 침묵이 사실상 0이라 임계값이 거칠어도 같은 구간이 나온다."""
    pcm = np.concatenate([_tone(1.0), _silence(2.0), _tone(1.0)]).astype(np.float32)
    assert len(speech_spans(frame_rms(pcm, RATE))) == 2


def test_떨어진_잡음_두_점은_답변이_아니다(tmp_path) -> None:
    """간격으로만 묶으면 1초 떨어진 잡음 두 점이 '1초짜리 답변'이 된다.

    실측에서 그렇게 만들어진 평균 RMS 43짜리 구간이 진짜 답변의 전사를
    가로챘다. 길이가 아니라 실제 소리가 난 프레임 수로 걸러야 한다.
    """
    path = _wav(
        tmp_path,
        _tone(0.06), _silence(1.0), _tone(0.06),  # 잡음 두 점
        _silence(2.0),
        _tone(1.5),                                # 진짜 답변
    )
    metrics = analyze(path, _transcript(("applicant", "진짜 답변입니다", 5.0)))

    assert metrics.answered == 1
    assert metrics.answers[0].text == "진짜 답변입니다"
