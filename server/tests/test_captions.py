"""자막 안전망 — 끊긴 전사 판정과 음성 받아 적기 호출 모양."""

import io
import wave

from daedam.server.captions import PROMPT, is_complete, pcm_to_wav, transcribe_pcm


def test_문장으로_끝나야_완전한_전사다() -> None:
    # 실측에서 끊긴 것들 — 낱말에서 멈춘다
    for broken in ["임펙스의 특수", "과거 항공", "입사하시면 가장 해보고", "", "   "]:
        assert not is_complete(broken), broken
    for whole in [
        "마지막으로 하고 싶은 말씀이 있으신가요?",
        "안녕히 가십시오.",
        "그 기준이 궁금합니다.",
        "말씀해 주시면 좋겠습니다",  # 부호가 빠져도 종결어미로 끝난다
        '"지원 동기"에 대해 여쭙겠습니다.',
        "감사합니다!",
    ]:
        assert is_complete(whole), whole


def test_PCM은_WAV로_감싼다() -> None:
    pcm = b"\x00\x01" * 2_400  # 0.1초
    with wave.open(io.BytesIO(pcm_to_wav(pcm)), "rb") as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 24_000)
        assert wav.getnframes() == 2_400


def test_받아_적기는_음성을_WAV_파트로_보내고_텍스트를_돌려준다() -> None:
    class _Models:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def generate_content(self, *, model, contents):
            self.calls.append({"model": model, "contents": contents})
            return type("Response", (), {"text": " 임펙스의 특수 물류 서비스에 대해 어떻게 생각하시나요? \n"})()

    class _Client:
        def __init__(self) -> None:
            self.models = _Models()

    client = _Client()
    text = transcribe_pcm(b"\x00\x01" * 2_400, client=client, model="m")
    assert text == "임펙스의 특수 물류 서비스에 대해 어떻게 생각하시나요?"
    [call] = client.models.calls
    part, prompt = call["contents"]
    assert call["model"] == "m" and prompt == PROMPT
    assert part.inline_data.mime_type == "audio/wav"
    assert part.inline_data.data.startswith(b"RIFF")
