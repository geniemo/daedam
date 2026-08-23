"""면접관 목소리로 추임새 클립을 수확한다 — 일회성 개발용.

    uv run python scripts/harvest_fillers.py

면접과 같은 Live 모델·같은 목소리(`interviewer.agent`의 MODEL·VOICE)로 세션을
열어 추임새 문장을 읽게 하고, 24kHz PCM을 `assets/fillers/<이름>.pcm`으로
저장한다. 청음용 `<이름>.wav`도 같이 남긴다 — 커밋 전에 반드시 들어 보고
면접 목소리와 같은지 판정할 것.

TTS API로 만들지 않는 이유: 목소리 이름(Aoede)이 같아도 TTS와 Live는 다른
음성 엔진이라 같은 목소리로 들리지 않았다(실측: 기계음, interviewer/agent.py의
VOICE 주석). 클립이 Live 엔진 자신의 출력이면 그 문제가 원리적으로 없다.

확인 경로 (설치된 google-genai 소스):
  google/genai/live.py  `AsyncLive.connect(model=, config=)` — async context
    manager로 AsyncSession을 내놓는다. `send_client_content(turns=,
    turn_complete=True)` 뒤 `receive()`를 돌면 LiveServerMessage가 흐른다.
  google/genai/types.py  `LiveServerContent` — 오디오는
    server_content.model_turn.parts[].inline_data.data, 턴의 끝은 turn_complete.
"""

from __future__ import annotations

import asyncio
import sys
import wave
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interviewer.agent import MODEL, VOICE  # noqa: E402

_SERVER_DIR = Path(__file__).resolve().parent.parent
_OUT_DIR = _SERVER_DIR / "assets" / "fillers"

#: 출력 오디오 규격 — Live API 출력은 24kHz/mono/16-bit PCM (CLAUDE.md 오디오 제약).
_RATE = 24000

#: 수확할 추임새. 뼈대질문 답변이 끝난 직후, 다음 질문을 고르는 동안 나갈
#: 말들이다 — "잘 들었다"는 신호까지만 하고 내용은 건드리지 않는다.
#: 어느 답변 뒤에 어느 것이 나가는지는 `daedam.server.fillers`의 풀이 정한다.
_PHRASES = {
    # 수용 — "모르겠습니다·기억이 안 납니다" 뒤. 여기에 "잘 들었습니다"가
    # 나가면 어색해진다.
    "gwaenchanseumnida": "네, 괜찮습니다.",
    "algesseumnida": "네, 알겠습니다.",
    # 기본 — 그 밖의 답변 뒤.
    "jal-deureosseumnida": "네, 말씀 잘 들었습니다.",
    "ne-geureokunyo": "네, 그렇군요.",
    "geureokunyo": "아, 네. 그렇군요.",
    "deureosseumnida": "잘 들었습니다.",
    "jasehi": "네, 자세히 말씀해 주셔서 잘 들었습니다.",
    "sangsehan": "상세한 설명 감사합니다.",
}

#: 성우 지시. 면접 instruction과 무관한 일회성 세션이다 — 문장을 그대로,
#: 면접관의 차분한 말투로 읽게만 한다.
_INSTRUCTION = (
    "당신은 차분한 톤의 면접관입니다. 사용자가 보내는 문장을 토씨 하나 바꾸지"
    " 말고 그대로 말하세요. 인사, 덧붙이는 말, 되묻기 없이 그 문장만 말합니다."
)


async def _record(client: genai.Client, phrase: str) -> bytes:
    """문장 하나를 새 세션에서 읽게 하고 오디오 한 턴을 모은다.

    문장마다 세션을 새로 여는 이유: 한 세션에서 이어 읽히면 앞 문장이 맥락이
    되어 억양이 끌려간다 — 클립은 각각 독립적으로 쓰인다.
    """
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE)
            )
        ),
        system_instruction=_INSTRUCTION,
    )
    chunks: list[bytes] = []
    async with client.aio.live.connect(model=MODEL, config=config) as session:
        await session.send_client_content(
            turns=types.Content(role="user", parts=[types.Part(text=phrase)]),
            turn_complete=True,
        )
        async for message in session.receive():
            content = message.server_content
            if content is None:
                continue
            for part in (content.model_turn.parts if content.model_turn else None) or []:
                blob = part.inline_data
                if blob and blob.data:
                    chunks.append(blob.data)
            if content.turn_complete:
                break
    return b"".join(chunks)


def _save(name: str, pcm: bytes) -> None:
    """클립을 재생용 .pcm과 청음용 .wav로 남긴다."""
    (_OUT_DIR / f"{name}.pcm").write_bytes(pcm)
    with wave.open(str(_OUT_DIR / f"{name}.wav"), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(_RATE)
        f.writeframes(pcm)


async def main() -> None:
    load_dotenv(_SERVER_DIR / ".env")
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = genai.Client()
    for name, phrase in _PHRASES.items():
        if (_OUT_DIR / f"{name}.pcm").exists():
            print(f"{name}: 이미 있음 — 건너뜀 (다시 뜨려면 파일을 지우고 재실행)")
            continue
        pcm = await _record(client, phrase)
        _save(name, pcm)
        print(f"{name}: {len(pcm) / (_RATE * 2):.1f}초 — {phrase}")
    print(f"\n저장: {_OUT_DIR}")
    print("커밋 전에 .wav를 들어 보고 면접 목소리와 같은지 판정할 것.")


if __name__ == "__main__":
    asyncio.run(main())
