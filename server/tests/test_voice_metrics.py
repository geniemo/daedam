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
    tmp_path.mkdir(parents=True, exist_ok=True)
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
    path = _wav(tmp_path, _tone(1.0), _silence(0.9), _tone(1.0))
    metrics = analyze(path, _transcript(("applicant", "머뭇", 3.2)))

    (answer,) = metrics.answers
    assert len(answer.pauses) == 1
    assert metrics.pause_ratio > 0


def test_숨_쉬는_길이는_멈춤이_아니다(tmp_path) -> None:
    """0.6초는 숨과 어절 경계의 길이다. 이걸 세면 7초짜리 답변에도 "2번
    끊겼습니다"가 붙는다 — 그 길이 안에 머뭇거림이 두 번 있을 수는 없다."""
    path = _wav(tmp_path, _tone(1.0), _silence(0.6), _tone(1.0))
    metrics = analyze(path, _transcript(("applicant", "숨", 2.9)))

    (answer,) = metrics.answers
    assert answer.pauses == ()


def test_말하기_속도는_멈춘_시간을_빼고_잰다(tmp_path) -> None:
    """멈춤을 포함해 나누면 또박또박 말해도 느리게 나온다."""
    path = _wav(tmp_path, _tone(1.0), _silence(0.9), _tone(1.0))
    metrics = analyze(path, _transcript(("applicant", "가나다라마가나다라마", 3.2)))

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
    path = _wav(tmp_path, _tone(1.0, 3000), _silence(2.0), _tone(1.0, 3000))
    metrics = analyze(path, _transcript(("applicant", "가", 1.5), ("applicant", "나", 4.5)))
    assert metrics.loudness_variation < 0.05


def test_멈춤이_많다고_작은_목소리가_되지_않는다(tmp_path) -> None:
    """조용한 프레임까지 넣어 평균을 내면 멈춤과 성량이 섞인다 — 또박또박
    같은 크기로 말했는데도 뜸을 들였다는 이유로 흔들림이 커진다."""
    steady = _wav(tmp_path / "a", _tone(2.0, 3000))
    paused = _wav(
        tmp_path / "b", _tone(0.6, 3000), _silence(0.9), _tone(0.6, 3000)
    )
    a = analyze(steady, _transcript(("applicant", "가", 2.5)))
    b = analyze(paused, _transcript(("applicant", "나", 2.5)))

    assert b.answers[0].pauses  # 멈춤은 잡히고
    assert abs(a.loudness - b.loudness) < a.loudness * 0.05  # 크기는 같다
    assert b.loudness_variation < 0.05


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


def test_답변까지_걸린_시간은_직전_재생_종료에서_잰다(tmp_path) -> None:
    """재생 버퍼가 잠깐 마르면 신호가 여러 번 온다 — 직전 것이 진짜 끝이다."""
    path = _wav(tmp_path, _silence(5.0), _tone(1.0))
    transcript = _transcript(("applicant", "답변", 6.5))
    # 3.0은 질문 도중 생긴 틈, 4.2가 진짜 끝. 답변은 5.0에 시작한다.
    transcript["questionEnds"] = [3.0, 4.2]

    metrics = analyze(path, transcript)
    assert metrics.answers[0].start_delay_s == pytest.approx(0.8, abs=0.05)
    assert metrics.mean_start_delay_s == pytest.approx(0.8, abs=0.05)


def test_재생_종료_신호가_없으면_재지_않는다(tmp_path) -> None:
    """0초로 채우면 '바로 대답했다'는 거짓말이 된다."""
    path = _wav(tmp_path, _silence(1.0), _tone(1.0))
    metrics = analyze(path, _transcript(("applicant", "답변", 2.5)))
    assert metrics.answers[0].start_delay_s is None
    assert metrics.mean_start_delay_s is None


def test_띄엄띄엄한_잡음은_길어도_답변이_아니다(tmp_path) -> None:
    """소리 난 프레임 수만 보면 몇 초짜리 잡음이 답변으로 살아남는다.

    실측에서 평균 RMS 92~113짜리 구간이 셋 나왔고(말 임계값은 200),
    그것이 말하기 속도를 60음절/분으로 끌어내렸다. 구간 평균도 봐야 한다.
    """
    # 짧고 작은 소리가 띄엄띄엄 — 소리 난 프레임은 충분하지만 구간 평균은
    # 말 수준(200)에 못 미친다. 실측 잡음 구간의 평균이 92~113이었다.
    noise = []
    for _ in range(6):
        noise += [_tone(0.08, 700), _silence(0.9)]
    path = _wav(tmp_path, *noise, _silence(2.0), _tone(1.5))
    # 전사는 발화가 끝난 뒤에 도착한다 — 구간 끝(9.4초)보다 뒤여야 한다.
    metrics = analyze(path, _transcript(("applicant", "진짜 답변", 10.0)))

    assert metrics.answered == 1
    assert metrics.answers[0].text == "진짜 답변"


def test_생각하느라_쉰_것은_답변을_가르지_않는다(tmp_path) -> None:
    """경계는 침묵 길이가 아니라 면접관이 다시 말한 지점이다.

    2초를 쉬어도 그다음 질문이 오기 전이면 같은 답변이다 — 침묵 길이로
    가르면 한 답변이 둘로 쪼개진다.
    """
    path = _wav(tmp_path, _silence(1.0), _tone(1.0), _silence(2.0), _tone(1.0))
    transcript = _transcript(("applicant", "쉬었다가 이어서 말했습니다", 5.5))
    transcript["questionEnds"] = [0.8]

    metrics = analyze(path, transcript)

    assert metrics.answered == 1
    answer = metrics.answers[0]
    assert answer.start_s == pytest.approx(1.0, abs=0.05)
    assert answer.end_s == pytest.approx(5.0, abs=0.05)
    # 쉰 시간은 답변 안의 멈춤으로 남는다.
    assert len(answer.pauses) == 1


def test_다음_질문이_오면_거기서_답변이_끝난다(tmp_path) -> None:
    path = _wav(tmp_path, _silence(0.5), _tone(1.0), _silence(2.0), _tone(1.0))
    transcript = _transcript(("applicant", "첫 답변", 2.0), ("applicant", "둘째 답변", 5.0))
    # 3.0초에 다음 질문이 끝났다 — 그 앞뒤는 다른 답변이다.
    transcript["questionEnds"] = [0.3, 3.0]

    metrics = analyze(path, transcript)
    assert [a.text for a in metrics.answers] == ["첫 답변", "둘째 답변"]


def test_질문_경계가_없으면_침묵으로_가른다(tmp_path) -> None:
    """옛 녹음에는 재생 종료 표시가 없다 — 그때는 폴백한다."""
    path = _wav(tmp_path, _tone(1.0), _silence(2.0), _tone(1.0))
    metrics = analyze(path, _transcript(("applicant", "첫", 1.5), ("applicant", "둘", 4.5)))
    assert metrics.answered == 2


def test_질문_경계를_놓쳐도_면접_전체를_한_답변으로_보지_않는다(tmp_path) -> None:
    """모델이 멈추면 재생 종료 표시가 안 찍혀 한 창이 몇 분을 삼킨다.

    실측: 406초짜리 면접에 표시가 둘뿐이라 389초짜리 창이 생겼고, 그 전체를
    한 답변으로 보니 평균이 침묵 수준으로 내려가 발화가 통째로 버려졌다.
    """
    path = _wav(
        tmp_path,
        _silence(0.5),
        _tone(2.0),        # 진짜 답변
        _silence(20.0),    # 그 뒤로 한참 조용
        _tone(0.3),        # 뒤늦은 잡소리
    )
    transcript = _transcript(("applicant", "답변입니다", 3.0))
    transcript["questionEnds"] = [0.3]  # 그다음 질문 표시가 없다

    metrics = analyze(path, transcript)

    assert metrics.answered == 1
    assert metrics.answers[0].duration_s == pytest.approx(2.0, abs=0.15)
