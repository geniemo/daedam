"""음성 브리지 테스트.

실제 Gemini 연결 없이 두 층을 검증한다: 이벤트→프론트 메시지 번역(순수
함수)과 WebSocket 왕복(대역 러너 — 큐에서 오디오를 받아 스크립트된 이벤트를
돌려준다).
"""

import asyncio
import json
import time
import wave

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

from daedam.interview.stages import PROFILES, Profile
from daedam.server import live_bridge
from daedam.server.live_bridge import _client_messages_from, create_live_router
from daedam.server.store import FileInterviewStore


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
    assert (
        "json",
        {"type": "caption", "text": "자기소개 부탁드립니다", "final": False},
    ) in _client_messages_from(event)


def test_전사의_끝은_final로_알린다() -> None:
    """조각을 이어 붙이는 프론트가 다음 턴에서 자막을 새로 시작할 지점이다.
    마지막 조각은 텍스트가 비어 올 수 있어 finished만으로도 내보낸다."""
    event = Event(
        author="interviewer",
        output_transcription=types.Transcription(finished=True),
    )
    assert ("json", {"type": "caption", "text": "", "final": True}) in _client_messages_from(event)


def test_질문_배달은_번호와_단계가_된다() -> None:
    """asked가 늘어난 state 델타 = 뼈대질문 하나가 나간 순간이다. 같은 델타의
    stage가 화면 상단의 단계 표시를 움직인다."""
    event = Event(
        author="interviewer",
        actions=EventActions(state_delta={"asked": ["q1", "q0"], "stage": 2}),
    )
    assert ("json", {"type": "question", "index": 1, "stage": 2}) in _client_messages_from(event)


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


def _seeded_store(tmp_path, *interview_ids: str) -> FileInterviewStore:
    """준비 데이터(질문 포함)가 저장된 상태의 저장소를 만든다."""
    store = FileInterviewStore(tmp_path / "data")
    for interview_id in interview_ids:
        store.save(
            interview_id,
            company="한결물류",
            role="데이터 엔지니어",
            application=[{"part": "자소서", "items": [{"title": "지원동기", "body": "본문"}]}],
            report=[{"title": "개요", "blocks": [{"type": "p", "text": "회사 본문"}]}],
            uncertain=[],
        )
        store.save_questions(
            interview_id,
            [{"id": "q-0-0", "stage": 0, "text": "질문?", "priority": 1, "tags": ["태그"]}],
        )
    return store


def _client(
    runner: _FakeRunner, store: FileInterviewStore, profile: str = "demo"
) -> TestClient:
    app = FastAPI()
    app.include_router(create_live_router(runner, store, profile=profile))
    return TestClient(app)


def _handshake(websocket) -> dict:
    """접속 직후의 session 메시지를 받아 돌려준다 — 모든 커넥션의 첫 메시지."""
    message = websocket.receive_json()
    assert message["type"] == "session"
    return message


def test_접속하면_화면이_맞출_진행_상태를_먼저_받는다(tmp_path) -> None:
    """남은 시간·단계·질문 번호의 출처는 서버 하나다."""
    client = _client(_FakeRunner(), _seeded_store(tmp_path, "hs"))
    with client.websocket_connect("/ws/interview?card=hs") as websocket:
        message = _handshake(websocket)

    assert message["totalSeconds"] == 540  # demo 하드캡
    assert message["stageBudgets"] == [90, 180, 150, 60]
    assert message["elapsedSeconds"] == 0
    assert message["stage"] == 0 and message["asked"] == 0


def test_왕복_오디오와_이벤트가_흐른다(tmp_path) -> None:
    runner = _FakeRunner()
    client = _client(runner, _seeded_store(tmp_path, "c1"))
    with client.websocket_connect("/ws/interview?card=c1") as websocket:
        _handshake(websocket)
        websocket.send_bytes(b"\x00\x01")
        assert websocket.receive_bytes() == b"\x01\x02"
        assert websocket.receive_json() == {"type": "caption", "text": "자막", "final": False}
        assert websocket.receive_json() == {"type": "ended"}

    blob = runner.heard[-1].blob
    assert blob.data == b"\x00\x01"
    assert blob.mime_type == "audio/pcm;rate=16000"


def test_새_세션은_준비_데이터가_시딩되고_개시_신호로_시작한다(tmp_path) -> None:
    """저장소의 준비 데이터가 세션 state로 들어가고, 면접관이 먼저 인사한다."""
    runner = _FakeRunner()
    client = _client(runner, _seeded_store(tmp_path, "fresh"))
    with client.websocket_connect("/ws/interview?card=fresh") as websocket:
        _handshake(websocket)
        websocket.send_bytes(b"\x00")
        websocket.receive_bytes()

    # 개시 신호는 지문이 아니라 인사말이다 — 이 채널은 지원자의 목소리라,
    # 3인칭 지문을 넣으면 지원자의 말과 섞여 이력에 남는다.
    opening = runner.heard[0]
    assert opening.content is not None
    assert opening.content.role == "user"
    assert opening.content.parts[0].text == "안녕하세요."

    session = asyncio.run(
        runner.session_service.get_session(
            app_name="daedam", user_id="user", session_id="fresh"
        )
    )
    assert session.state["company"] == "한결물류"
    assert session.state["question_pool"][0]["id"] == "q-0-0"
    # 리포트는 화면 형태에서 검색 입력 형태(blk 좌표 id)로 변환돼 들어간다.
    assert session.state["research_report"][0]["blocks"][0]["id"] == "blk-0-0"
    # 세션이 만들어지는 순간이 면접 시작이다 — 시계와 예산도 같이 들어간다.
    assert session.state["started_at"] == pytest.approx(time.time(), abs=10)
    assert session.state["profile"] == "demo"


def test_준비_데이터_없는_면접은_거절된다(tmp_path) -> None:
    """조용한 폴백 대신 명시적 거절 — 시딩 실패가 첫 접속에서 드러난다."""
    client = _client(_FakeRunner(), FileInterviewStore(tmp_path / "empty"))
    with client.websocket_connect("/ws/interview?card=nope") as websocket:
        assert websocket.receive_json() == {"type": "ended"}
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_bytes()


def test_재접속에는_개시_신호가_없다(tmp_path) -> None:
    """이미 진행된 면접에 다시 붙으면 인사를 반복하지 않는다."""
    runner = _FakeRunner()
    asyncio.run(
        runner.session_service.create_session(
            app_name="daedam", user_id="user", session_id="re", state={}
        )
    )
    client = _client(runner, _seeded_store(tmp_path, "re"))
    with client.websocket_connect("/ws/interview?card=re") as websocket:
        _handshake(websocket)
        websocket.send_bytes(b"\x00")
        websocket.receive_bytes()

    assert runner.heard[0].blob is not None  # 개시 신호 없이 바로 오디오


def test_같은_카드의_새_접속이_이전_커넥션을_닫는다(tmp_path) -> None:
    """이중 마운트·중복 탭이 만드는 '두 목소리'를 서버가 차단한다."""
    client = _client(_FakeRunner(), _seeded_store(tmp_path, "dup"))
    with client.websocket_connect("/ws/interview?card=dup") as first:
        _handshake(first)
        with client.websocket_connect("/ws/interview?card=dup") as second:
            _handshake(second)
            with pytest.raises(WebSocketDisconnect):
                first.receive_bytes()
            # 새 커넥션은 정상 동작한다.
            second.send_bytes(b"\x00")
            assert second.receive_bytes() == b"\x01\x02"


class _ClosingRunner(_FakeRunner):
    """하드캡 지시가 들어올 때까지 큐를 계속 소비하는 대역."""

    async def run_live(self, *, session, live_request_queue, run_config):
        while True:
            request = await live_request_queue.get()
            self.heard.append(request)
            content = request.content
            if content is not None and "마무리" in (content.parts[0].text or ""):
                break
        yield _audio_event(b"\x01\x02")


def test_하드캡에_닿으면_서버가_마무리를_지시한다(tmp_path, monkeypatch) -> None:
    """모델이 툴을 한 번도 안 불러도 면접은 끝난다 — 종료는 서버가 쥔다."""
    monkeypatch.setitem(
        PROFILES, "instant", Profile("instant", (0.0, 0.0, 0.0, 0.0), hard_cap_s=0.0)
    )
    runner = _ClosingRunner()
    client = _client(runner, _seeded_store(tmp_path, "cap"), profile="instant")
    with client.websocket_connect("/ws/interview?card=cap") as websocket:
        _handshake(websocket)
        assert websocket.receive_bytes() == b"\x01\x02"

    spoken = [r.content.parts[0].text for r in runner.heard if r.content is not None]
    assert any("마무리" in text for text in spoken)


class _ClosingSignalRunner(_FakeRunner):
    """마무리 표시를 한 번 내보내고 그대로 살아 있는 대역.

    끝나지 않는 것이 핵심이다 — 실제 ADK도 큐를 닫으면 재연결로 받아 끝나지
    않는다. 종료는 브리지가 스스로 매듭지어야 한다.
    """

    async def run_live(self, *, session, live_request_queue, run_config):
        yield Event(
            author="interviewer", actions=EventActions(state_delta={"closing": True})
        )
        while True:
            self.heard.append(await live_request_queue.get())


def test_마무리_표시가_뜨면_서버가_커넥션을_끝낸다(tmp_path, monkeypatch) -> None:
    """질문이 다 나갔는데 하드캡까지 침묵을 끌고 가지 않는다. run_live가 계속
    돌더라도 ended를 보내고 소켓을 닫는 것은 브리지 몫이다."""
    monkeypatch.setattr(live_bridge, "_CLOSING_GRACE_S", 0.0)
    monkeypatch.setattr(live_bridge, "_PLAYBACK_TAIL_S", 0.0)
    client = _client(_ClosingSignalRunner(), _seeded_store(tmp_path, "fin"))
    with client.websocket_connect("/ws/interview?card=fin") as websocket:
        _handshake(websocket)
        assert websocket.receive_json() == {"type": "ended"}
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_json()


class _ClosingWithTurnRunner(_FakeRunner):
    """마무리 표시와 인사 턴 완료를 붙여 내보내고 그대로 살아 있는 대역.

    종료 태스크가 표시를 읽고 깨어나기 전에 인사 턴이 이미 끝난 순서다. 종료
    툴 경로에서는 툴 응답과 인사가 붙어 오므로 실제로 이렇게 된다.
    """

    async def run_live(self, *, session, live_request_queue, run_config):
        yield Event(
            author="interviewer", actions=EventActions(state_delta={"closing": True})
        )
        yield Event(author="interviewer", turn_complete=True)
        while True:
            self.heard.append(await live_request_queue.get())


def test_인사_턴이_먼저_끝나도_그레이스를_다_기다리지_않는다(
    tmp_path, monkeypatch
) -> None:
    """이미 끝난 인사를 못 본 척하고 다음 턴을 기다리면 그만큼 침묵이 길어진다.
    대기 기준은 신호를 지우고 새로 받는 것이 아니라 완료된 턴 수다."""
    monkeypatch.setattr(live_bridge, "_CLOSING_GRACE_S", 5.0)
    monkeypatch.setattr(live_bridge, "_PLAYBACK_TAIL_S", 0.0)
    client = _client(_ClosingWithTurnRunner(), _seeded_store(tmp_path, "quick"))
    with client.websocket_connect("/ws/interview?card=quick") as websocket:
        _handshake(websocket)
        started = time.monotonic()
        assert websocket.receive_json() == {"type": "ended"}
        assert time.monotonic() - started < 2.0


def test_지원자가_끝내면_종료를_알리고_정리한다(tmp_path) -> None:
    """end 컨트롤도 같은 계약을 탄다 — 끝을 알리는 것은 언제나 서버다."""
    client = _client(_ClosingSignalRunner(), _seeded_store(tmp_path, "bye"))
    with client.websocket_connect("/ws/interview?card=bye") as websocket:
        _handshake(websocket)
        websocket.send_text('{"type": "end"}')
        assert websocket.receive_json() == {"type": "ended"}


def test_세션은_카드_id로_만들어진다(tmp_path) -> None:
    runner = _FakeRunner()
    client = _client(runner, _seeded_store(tmp_path, "card-77"))
    with client.websocket_connect("/ws/interview?card=card-77") as websocket:
        _handshake(websocket)
        websocket.send_bytes(b"\x00")
        websocket.receive_bytes()

    session = asyncio.run(
        runner.session_service.get_session(
            app_name="daedam", user_id="user", session_id="card-77"
        )
    )
    assert session is not None


# ── 면접이 남기는 것 (§리포트의 재료) ────────────────────────────────


class _TranscribingRunner(_FakeRunner):
    """양쪽 전사를 흘리는 대역.

    조각이 오다가 finished에 **전문**이 실린다. 프론트가 final일 때 자막을
    text로 통째로 교체하는데(store/interview.ts appendCaption) 자막이 잘려
    보인 적이 없으므로 실제 모양이 이렇다.
    """

    async def run_live(self, *, session, live_request_queue, run_config):
        while True:
            request = await live_request_queue.get()
            self.heard.append(request)
            if request.blob is not None:
                break
        yield Event(
            author="interviewer",
            output_transcription=types.Transcription(text="자기소개 "),
        )
        yield Event(
            author="interviewer",
            output_transcription=types.Transcription(
                text="자기소개 부탁드립니다.", finished=True
            ),
        )
        yield Event(
            author="user",
            input_transcription=types.Transcription(text="네, 저는", finished=True),
        )


def test_면접이_음성과_전사를_남긴다(tmp_path) -> None:
    """면접이 끝나면 아무것도 안 남았다 — 리포트는 이 파일들 위에 선다."""
    store = _seeded_store(tmp_path, "rec")
    client = _client(_TranscribingRunner(), store)
    with client.websocket_connect("/ws/interview?card=rec") as websocket:
        _handshake(websocket)
        websocket.send_bytes(b"\x00\x01" * 16_000)  # 1초치
        # 대역 러너가 낸 자막 셋을 흘려보내고 종료 통지까지 받는다.
        while websocket.receive_json()["type"] != "ended":
            pass

    directory = store.directory("rec")
    saved = json.loads((directory / "transcript.json").read_text(encoding="utf-8"))
    assert [(u["speaker"], u["text"]) for u in saved["utterances"]] == [
        ("interviewer", "자기소개 부탁드립니다."),
        ("applicant", "네, 저는"),
    ]
    # 조각은 이어 붙고, 위치는 그때까지 받은 오디오 길이다.
    assert saved["durationS"] == 1.0
    assert saved["utterances"][0]["at"] == 1.0

    with wave.open(str(directory / "mic.wav"), "rb") as wav:
        assert wav.getnframes() == 16_000
