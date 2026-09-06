"""면접관 자막의 안전망 — 전사가 끊겼을 때 음성으로 다시 받아 적는다.

Live API의 출력 전사는 가끔 문장 앞머리에서 끊긴다(실측 "임펙스의 특수",
"과거 항공", "입사하시면 가장 해보고" — 뒤 전사가 끝내 오지 않았다). 그러면
지원자는 방금 들은 질문을 화면에서 읽을 수 없다. 턴이 끝났을 때 전사가 문장으로
끝나지 않았으면 그 턴의 음성을 Gemini에 보내 받아 적고, 그 결과로 자막과 전사록을
바꿔 끼운다. 1~2초 뒤에 오지만, 못 읽는 것보다 늦게 읽는 편이 낫다.

확인 경로(설치된 google-genai 2.17.0):
  google/genai/types.py:2397   Part.from_bytes(data=, mime_type=)
  google/genai/types.py         HttpOptions.timeout — 밀리초
  Gemini 오디오 입력은 WAV·MP3·AIFF·AAC·OGG·FLAC이라 24kHz PCM은 WAV로 감싼다.
"""

from __future__ import annotations

import io
import re
import wave
from typing import Any

from daedam.llm import MODEL_FAST

#: 면접 중 호출이라 오래 기다리지 않는다. 늦으면 자막 없이 넘어간다.
#: API가 허용하는 최소 deadline이 10초다(실측 400: "Minimum allowed deadline is 10s").
TIMEOUT_MS = 10_000

PROMPT = (
    "이 한국어 음성을 들리는 그대로 받아 적어 주세요. "
    "문장 부호를 넣고, 설명이나 따옴표 없이 받아 적은 글만 돌려주세요."
)

#: 문장이 끝난 모양. 전사에 붙는 부호로 끝나거나, 부호가 없어도 한국어 종결어미로 끝난다.
_COMPLETE = re.compile(r"(?:[.?!…][\"”’)\]]*|[다요까죠네])$")


def is_complete(text: str) -> bool:
    """전사가 문장으로 끝났는가. 끊긴 전사는 "임펙스의 특수"처럼 낱말에서 멈춘다."""
    text = text.strip()
    return bool(text) and _COMPLETE.search(text) is not None


def pcm_to_wav(pcm: bytes, rate: int = 24_000) -> bytes:
    """16-bit mono PCM을 WAV로 감싼다. 모델이 raw PCM은 받지 않는다."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    return buffer.getvalue()


def transcribe_pcm(
    pcm: bytes,
    *,
    rate: int = 24_000,
    client: Any = None,
    model: str = MODEL_FAST,
) -> str:
    """음성 한 토막을 받아 적는다. 실패는 예외로 올린다 — 호출자가 로그를 남긴다.

    Args:
        pcm: 16-bit mono PCM. 면접관 음성은 Live API 출력 규격인 24kHz.
        client: 테스트 대역. 없으면 GOOGLE_API_KEY로 만든다.
    """
    from google.genai import types

    if client is None:
        from google import genai

        client = genai.Client(http_options=types.HttpOptions(timeout=TIMEOUT_MS))

    response = client.models.generate_content(
        model=model,
        contents=[types.Part.from_bytes(data=pcm_to_wav(pcm, rate), mime_type="audio/wav"), PROMPT],
    )
    return (response.text or "").strip()
