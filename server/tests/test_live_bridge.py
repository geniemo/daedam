"""음성 브리지 테스트.

실제 Gemini 연결 없이 두 층을 검증한다: 이벤트→프론트 메시지 번역(순수
함수)과 WebSocket 왕복(대역 러너 — 큐에서 오디오를 받아 스크립트된 이벤트를
돌려준다).
"""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

from daedam.server.live_bridge import _client_messages_from, create_live_router


def _audio_event(data: bytes = b"\x01\x02") -> Event:
    return Event(
        author="interviewer",
        content=types.Content(
            role="model",
            parts=[types.Part(inline_data=types.Blob(mime_type="audio/pcm", data=data))],
        ),
    )


# ── 이벤트 번역 ──────────────────────────────────────────────────────────


def test_오디오_파트는_바이너리가_된다() -> None:
    assert _client_messages_from(_audio_event(b"\x0a\x0b")) == [("bytes", b"\x0a\x0b")]


def test_모델_전사는_caption이_된다() -> None:
    event = Event(
        author="interviewer",
        output_transcription=types.Transcription(text="자기소개 부탁드립니다"),
    )
    assert ("json", {"type": "caption", "text": "자기소개 부탁드립니다"}) in _client_messages_from(event)


def test_질문_배달은_question_index가_된다() -> None:
    """asked가 늘어난 state 델타 = 뼈대질문 하나가 나간 순간이다."""
    event = Event(
        author="interviewer",
        actions=EventActions(state_delta={"asked": ["q1", "q0"], "stage": 0}),
    )
    assert ("json", {"type": "question", "index": 1}) in _client_messages_from(event)


def test_끼어들기와_goAway가_전달된다() -> None:
    event = Event(author="interviewer", interrupted=True, go_away=types.LiveServerGoAway())
    messages = [payload for _, payload in _client_messages_from(event)]
    assert {"type": "interrupted"} in messages and {"type": "goAway"} in messages


def test_재개_핸들은_resumeToken이_된다() -> None:
    event = Event(
        author="interviewer",
        live_session_resumption_update=types.LiveServerSessionResumptionUpdate(new_handle="h-1"),
    )
    assert ("json", {"type": "resumeToken", "token": "h-1"}) in _client_messages_from(event)


def test_내부_이벤트는_아무것도_내보내지_않는다() -> None:
    """툴 호출·사용자 전사 같은 서버 내부는 클라이언트로 새지 않는다."""
    event = Event(
        author="interviewer",
        input_transcription=types.Transcription(text="사용자 발화"),
    )
    assert _client_messages_from(event) == []


# ── WebSocket 왕복 (대역 러너) ───────────────────────────────────────────


class _FakeRunner:
    """오디오가 올 때까지 큐를 소비하고 스크립트된 이벤트 둘을 돌려주는 대역."""

    app_name = "daedam"

    def __init__(self) -> None:
        self.session_service = InMemorySessionService()
        self.heard: list = []  # LiveRequest 순서 그대로 — 개시 신호 검증용

    async def run_live(self, *, session, live_request_queue, run_config):
        while True:
            request = await live_request_queue.get()
            self.heard.append(request)
            if request.blob is not None:
                break
        yield _audio_event(b"\x01\x02")
        yield Event(
            author="interviewer",
            output_transcription=types.Transcription(text="자막"),
        )


def _client(runner: _FakeRunner) -> TestClient:
    app = FastAPI()
    app.include_router(create_live_router(runner))
    return TestClient(app)


def test_왕복_오디오와_이벤트가_흐른다() -> None:
    runner = _FakeRunner()
    with _client(runner).websocket_connect("/ws/interview?card=c1") as websocket:
        websocket.send_bytes(b"\x00\x01")
        assert websocket.receive_bytes() == b"\x01\x02"
        assert websocket.receive_json() == {"type": "caption", "text": "자막"}
        assert websocket.receive_json() == {"type": "ended"}

    blob = runner.heard[-1].blob
    assert blob.data == b"\x00\x01"
    assert blob.mime_type == "audio/pcm;rate=16000"


def test_새_세션은_개시_신호로_시작한다() -> None:
    """면접관이 먼저 인사한다 — 첫 큐 항목이 입장 알림 턴이어야 한다."""
    runner = _FakeRunner()
    with _client(runner).websocket_connect("/ws/interview?card=fresh") as websocket:
        websocket.send_bytes(b"\x00")
        websocket.receive_bytes()

    opening = runner.heard[0]
    assert opening.content is not None
    assert "입장" in opening.content.parts[0].text


def test_재접속에는_개시_신호가_없다() -> None:
    """이미 진행된 면접에 다시 붙으면 인사를 반복하지 않는다."""
    runner = _FakeRunner()
    asyncio.run(
        runner.session_service.create_session(
            app_name="daedam", user_id="user", session_id="re", state={}
        )
    )
    with _client(runner).websocket_connect("/ws/interview?card=re") as websocket:
        websocket.send_bytes(b"\x00")
        websocket.receive_bytes()

    assert runner.heard[0].blob is not None  # 개시 신호 없이 바로 오디오


def test_같은_카드의_새_접속이_이전_커넥션을_닫는다() -> None:
    """이중 마운트·중복 탭이 만드는 '두 목소리'를 서버가 차단한다."""
    client = _client(_FakeRunner())
    with client.websocket_connect("/ws/interview?card=dup") as first:
        with client.websocket_connect("/ws/interview?card=dup") as second:
            with pytest.raises(WebSocketDisconnect):
                first.receive_bytes()
            # 새 커넥션은 정상 동작한다.
            second.send_bytes(b"\x00")
            assert second.receive_bytes() == b"\x01\x02"


def test_세션은_카드_id로_만들어진다() -> None:
    runner = _FakeRunner()
    with _client(runner).websocket_connect("/ws/interview?card=card-77") as websocket:
        websocket.send_bytes(b"\x00")
        websocket.receive_bytes()

    session = asyncio.run(
        runner.session_service.get_session(
            app_name="daedam", user_id="user", session_id="card-77"
        )
    )
    assert session is not None
