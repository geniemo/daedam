"""툴이 도는 침묵을 면접관 목소리의 추임새 클립으로 메운다.

`ask_question`이 파볼 곳 추출(Grok, ~2초)을 도는 호출에서만, 툴 실행 직전에
클립 하나를 브라우저로 내보낸다. Live API 함수 호출은 순차 전용이라 그동안
모델은 말이 없다 — 지원자에게는 답변을 마쳤는데 면접관이 침묵하는 2초다.

클립은 TTS가 아니라 면접과 같은 Live 엔진·같은 목소리(Aoede)의 출력을 미리
수확한 것이다(`scripts/harvest_fillers.py`). TTS는 목소리 이름이 같아도 다른
엔진이라 기계음이 났다(실측 — interviewer/agent.py의 VOICE 주석).

콜백이 타이밍을 보장한다: ADK가 툴 실행 전에 이 콜백을 await하므로
(설치된 ADK 2.6.3 flows/llm_flows/functions.py:845 — live 경로도 canonical
before_tool_callback을 await하고, None을 돌려주면 툴이 정상 실행된다),
클립이 소켓으로 나간 뒤에야 추출이 시작된다. 추출이 이벤트 루프를 잡고
있어도 클립은 이미 브라우저 재생 큐에서 돌고 있다.

배선은 두 곳이다 — 조립(app.py)이 이 콜백을 에이전트에 걸고, 브리지가
커넥션마다 `register`로 전송 함수를 준다. 클립은 프론트에 그냥 24kHz 오디오
프레임이라 프론트 수정이 없고, 전사가 없으므로 자막에도 안 뜬다(자막의
원칙은 "실제 모델 발화"다 — live_bridge의 caption 주석).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Awaitable, Callable

from google.adk.tools import BaseTool, ToolContext

from interviewer.tools import pending_extraction_answer

logger = logging.getLogger(__name__)

#: 수확된 클립이 있는 곳 (24kHz/mono/16-bit PCM — Live API 출력 규격 그대로).
_FILLER_DIR = Path(__file__).resolve().parents[2] / "assets" / "fillers"

#: 수용 풀 — 지원자가 모르겠다고 한 답변 뒤. "말씀 잘 들었습니다"가 나가면
#: 어색해지는 자리다(못 들은 것을 잘 들었다고 하는 셈).
_ACCEPT_POOL = ("gwaenchanseumnida", "algesseumnida")

#: 기본 풀 — 그 밖의 모든 답변 뒤.
_DEFAULT_POOL = (
    "jal-deureosseumnida",
    "ne-geureokunyo",
    "geureokunyo",
    "deureosseumnida",
    "jasehi",
    "sangsehan",
)

#: "모르겠다" 판정 패턴. 답변에서 공백을 지운 꼬리와 대조한다 — 전사의 띄어
#: 쓰기가 흔들려서("기억이 안나요"/"기억이 안 나요") 공백 없이 본다.
_UNSURE_PATTERNS = (
    "모르겠",
    "모릅니다",
    "잘모르",
    # "안 나요"와 "안 납니다"는 공백을 지우면 각각 "안나"·"안납"이다 — 둘 다 둔다.
    "기억이안나",
    "기억이안납",
    "기억안나",
    "기억안납",
    "기억이나지않",
    "기억나지않",
    "떠오르지않",
    "생각이안나",
    "생각이안납",
    "생각안나",
    "생각안납",
    "생각이나지않",
    "생각나지않",
)

#: 판정에 보는 꼬리 길이(공백 제거 후). 모르겠다는 말은 답변 끝에 온다 —
#: 중간에 "그때는 몰랐는데"라고 했다가 제대로 답한 경우까지 수용 풀로 보내지
#: 않기 위해 꼬리만 본다.
_TAIL_CHARS = 40


def _sounds_unsure(answer: str) -> bool:
    """답변이 "모르겠습니다" 류로 끝나는가."""
    tail = answer.replace(" ", "")[-_TAIL_CHARS:]
    return any(pattern in tail for pattern in _UNSURE_PATTERNS)


@lru_cache(maxsize=1)
def _clips() -> dict[str, bytes]:
    """클립 이름 → PCM. 없는 파일은 경고만 남기고 뺀다 — 필러는 장식이라
    없어도 면접은 돌아야 한다."""
    loaded: dict[str, bytes] = {}
    for name in _ACCEPT_POOL + _DEFAULT_POOL:
        path = _FILLER_DIR / f"{name}.pcm"
        if path.exists():
            loaded[name] = path.read_bytes()
        else:
            logger.warning("필러 클립 없음: %s — scripts/harvest_fillers.py로 수확", path)
    return loaded


@dataclass
class _Connection:
    """커넥션 하나의 전송 함수와 풀별 로테이션 위치."""

    send: Callable[[bytes], Awaitable[None]]
    #: 풀 튜플 → 다음에 낼 인덱스. 같은 클립이 연달아 나가지 않게 돌린다.
    counters: dict[tuple[str, ...], int] = field(default_factory=dict)


#: 세션 id(카드) → 활성 커넥션. 브리지가 커넥션 수명에 맞춰 넣고 뺀다.
_connections: dict[str, _Connection] = {}


def register(session_id: str, send: Callable[[bytes], Awaitable[None]]) -> _Connection:
    """이 세션의 클립 전송 함수를 등록한다. 돌려준 값이 해제용 표다."""
    connection = _Connection(send=send)
    _connections[session_id] = connection
    return connection


def unregister(session_id: str, connection: _Connection) -> None:
    """등록을 해제한다 — 내가 등록한 것일 때만.

    같은 카드에 새 커넥션이 이미 등록했으면 그쪽 것이다(브리지의 active
    딕셔너리와 같은 규칙 — 재접속이 이전 커넥션의 정리보다 먼저 올 수 있다).
    """
    if _connections.get(session_id) is connection:
        del _connections[session_id]


def _pick(connection: _Connection, answer: str) -> tuple[str, bytes] | None:
    """답변에 맞는 풀에서 다음 클립을 고른다. 쓸 클립이 없으면 None."""
    pool = _ACCEPT_POOL if _sounds_unsure(answer) else _DEFAULT_POOL
    available = [name for name in pool if name in _clips()]
    if not available:
        return None
    index = connection.counters.get(pool, 0)
    connection.counters[pool] = index + 1
    name = available[index % len(available)]
    return name, _clips()[name]


async def play_filler_before_tool(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext
) -> None:
    """에이전트의 `before_tool_callback` — 추출 호출이면 클립을 내보낸다.

    항상 None을 돌려줘 툴은 그대로 실행된다. 전송 실패(닫힌 소켓)는 삼킨다 —
    필러 때문에 툴 호출이 죽으면 안 된다.
    """
    del args
    if tool.name != "ask_question":
        return None
    connection = _connections.get(getattr(tool_context.session, "id", None))
    if connection is None:
        return None
    answer = pending_extraction_answer(tool_context)
    if not answer:
        return None
    picked = _pick(connection, answer)
    if picked is None:
        return None
    name, pcm = picked
    try:
        await connection.send(pcm)
        logger.info("필러 재생: %s (답변 %d자)", name, len(answer))
    except Exception:  # noqa: BLE001 — 커넥션이 닫히는 중이면 그만
        logger.warning("필러 전송 실패 — 소켓이 닫혔을 수 있다", exc_info=True)
    return None
