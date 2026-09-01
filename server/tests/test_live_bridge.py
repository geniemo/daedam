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

from daedam.server import live_bridge
from daedam.server.live_bridge import _client_messages_from, create_live_router
from conftest import make_store


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


def test_질문_배달은_번호가_된다() -> None:
    """asked가 늘어난 state 델타 = 뼈대질문 하나가 나간 순간이다. 단계는 화면에
    보내지 않는다 — 서버가 질문을 고르는 내부 사정이다."""
    event = Event(
        author="interviewer",
        actions=EventActions(state_delta={"asked": ["q1", "q0"], "stage": 2}),
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
        # 면접이 끝나면 브리지가 세션을 지운다. 시딩을 검증하려면 돌던 중에
        # 붙잡아 둬야 한다.
        self.session = None

    async def run_live(self, *, session, live_request_queue, run_config):
        self.session = session
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


def _seeded_store(tmp_path, *interview_ids: str):
    """준비 데이터(질문 포함)가 저장된 상태의 저장소를 만든다.

    계정은 저장소에 매달아 둔다 — 브리지가 소유권을 확인하려면 둘이 같은
    데이터베이스를 봐야 한다.
    """
    store, accounts, user_id = make_store(tmp_path / "data")
    store.accounts = accounts
    for interview_id in interview_ids:
        store.save(
            interview_id,
            user_id=user_id,
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


def _client(runner: _FakeRunner, store, profile: str = "demo") -> TestClient:
    app = FastAPI()
    app.include_router(
        create_live_router(
            runner, store, store.accounts, store.accounts.credits, profile=profile
        )
    )
    return TestClient(app)


def _handshake(websocket) -> dict:
    """접속 직후의 session 메시지를 받아 돌려준다 — 모든 커넥션의 첫 메시지."""
    message = websocket.receive_json()
    assert message["type"] == "session"
    return message


def test_접속하면_화면이_맞출_진행_상태를_먼저_받는다(tmp_path) -> None:
    """경과 시간·질문 번호의 출처는 서버 하나다. 남은 시간과 단계는 없다 —
    면접을 끝내는 것은 지원자의 버튼이다.

    판 id도 여기 실린다. 화면이 웹캠 녹화를 어느 판에 올릴지 알아야 하는데,
    "가장 최근 판"으로 유추하게 두면 첫 조각이 판 생성보다 빠를 때 404를 받고
    녹화가 통째로 죽는다."""
    store = _seeded_store(tmp_path, "hs")
    client = _client(_FakeRunner(), store)
    with client.websocket_connect("/ws/interview?card=hs") as websocket:
        message = _handshake(websocket)

    assert message["elapsedSeconds"] == 0 and message["asked"] == 0
    assert message["sessionId"] == store.latest_session("hs").id


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

    session = runner.session
    assert session is not None
    assert session.state["company"] == "한결물류"
    assert session.state["question_pool"][0]["id"] == "q-0-0"
    # 리포트는 화면 형태에서 검색 입력 형태(blk 좌표 id)로 변환돼 들어간다.
    assert session.state["research_report"][0]["blocks"][0]["id"] == "blk-0-0"
    # 세션이 만들어지는 순간이 면접 시작이다 — 시계와 예산도 같이 들어간다.
    assert session.state["started_at"] == pytest.approx(time.time(), abs=10)
    assert session.state["profile"] == "demo"


def test_질문이_없는_면접은_거절된다(tmp_path) -> None:
    """조용한 폴백 대신 명시적 거절 — 시딩 실패가 첫 접속에서 드러난다."""
    store = _seeded_store(tmp_path)
    # 리서치가 아직 안 끝난 카드 — 내 것이지만 질문 풀이 없다.
    store.save(
        "half",
        user_id=store.accounts.default_user_id(),
        company="한결물류",
        role="데이터 엔지니어",
        application=[],
        report=[],
        uncertain=[],
    )
    client = _client(_FakeRunner(), store)
    with client.websocket_connect("/ws/interview?card=half") as websocket:
        assert websocket.receive_json() == {"type": "ended"}
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_bytes()


def test_남의_면접에는_붙을_수_없다(tmp_path) -> None:
    """카드 id만 알면 들어와 원래 있던 사람을 끊어낼 수 있었다 — 인증의
    구멍이 여기였다. 없는 카드도 같은 응답이라 존재 여부가 새지 않는다."""
    from daedam.db import User

    store = _seeded_store(tmp_path, "mine")
    with store._db.session() as session:
        stranger = User(provider="kakao", provider_user_id="stranger")
        session.add(stranger)
        session.flush()
        stranger_id = stranger.id
    store.save(
        "theirs",
        user_id=stranger_id,
        company="비밀",
        role="비밀",
        application=[],
        report=[],
        uncertain=[],
    )
    store.save_questions("theirs", [{"id": "q", "stage": 0, "text": "?", "priority": 1, "tags": []}])

    client = _client(_FakeRunner(), store)
    for card in ("theirs", "nope"):
        with client.websocket_connect(f"/ws/interview?card={card}") as websocket:
            assert websocket.receive_json() == {"type": "ended"}
            with pytest.raises(WebSocketDisconnect):
                websocket.receive_bytes()


def test_재접속에는_개시_신호가_없다(tmp_path) -> None:
    """이미 진행된 면접에 다시 붙으면 인사를 반복하지 않는다.

    재접속의 판정 기준은 "끝나지 않은 면접이 있는가"다. 커넥션이 끊긴 것과
    면접이 끝난 것은 다르다 — 15~20분 면접은 Live 커넥션 수명(~10분) 때문에
    반드시 재접속한다.
    """
    runner = _FakeRunner()
    store = _seeded_store(tmp_path, "re")
    # 앞 커넥션이 열어 둔 면접 한 판.
    store.start_session("re")

    client = _client(runner, store)
    with client.websocket_connect("/ws/interview?card=re") as websocket:
        _handshake(websocket)
        websocket.send_bytes(b"\x00")
        websocket.receive_bytes()

    assert runner.heard[0].blob is not None  # 개시 신호 없이 바로 오디오
    # 판이 새로 열리지 않았다 — 같은 면접을 이어받았다.
    assert len(store.list_sessions("re")) == 1


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


class _EndlessRunner(_FakeRunner):
    """이벤트 하나를 내고 그대로 살아 있는 대역. 실제 ADK도 큐를 닫으면 재연결로
    받아 끝나지 않는다 — 종료는 지원자의 end 컨트롤을 받은 브리지가 매듭지어야
    한다."""

    async def run_live(self, *, session, live_request_queue, run_config):
        yield _audio_event(b"\x01\x02")
        while True:
            self.heard.append(await live_request_queue.get())


def test_지원자가_끝내면_종료를_알리고_정리한다(tmp_path) -> None:
    """면접을 끝내는 유일한 경로다. run_live가 계속 돌더라도 ended를 보내고
    정리하는 것은 브리지 몫이다."""
    client = _client(_EndlessRunner(), _seeded_store(tmp_path, "bye"))
    with client.websocket_connect("/ws/interview?card=bye") as websocket:
        _handshake(websocket)
        assert websocket.receive_bytes() == b"\x01\x02"
        websocket.send_text('{"type": "end"}')
        assert websocket.receive_json() == {"type": "ended"}


def test_대화_세션은_면접_한_판마다_새로_만들어진다(tmp_path) -> None:
    """앞서는 카드 id를 대화 세션 id로 썼다. 같은 카드로 두 번째 면접을 보면
    첫 면접의 대화 이력을 이어받아, 면접관이 이미 물어본 것을 아는 상태로
    시작한다."""
    runner = _FakeRunner()
    store = _seeded_store(tmp_path, "card-77")
    client = _client(runner, store)
    with client.websocket_connect("/ws/interview?card=card-77") as websocket:
        _handshake(websocket)
        websocket.send_bytes(b"\x00")
        websocket.receive_bytes()

    [session] = store.list_sessions("card-77")
    assert runner.session is not None
    assert runner.session.id == session.id != "card-77"


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

    [session] = store.list_sessions("rec")
    directory = store.session_directory("rec", session.id)
    # 전사는 질의 대상이라 면접 기록으로 올라간다. 디스크의 transcript.json은
    # 재접속이 이어 쓰기 위한 작업 파일이다.
    saved = store.load_session(session.id).transcript
    assert json.loads((directory / "transcript.json").read_text(encoding="utf-8")) == saved
    assert [(u["speaker"], u["text"]) for u in saved["utterances"]] == [
        ("interviewer", "자기소개 부탁드립니다."),
        ("applicant", "네, 저는"),
    ]
    # 조각은 이어 붙고, 위치는 그때까지 받은 오디오 길이다.
    assert saved["durationS"] == 1.0
    assert saved["utterances"][0]["at"] == 1.0

    with wave.open(str(directory / "mic.wav"), "rb") as wav:
        assert wav.getnframes() == 16_000


# ── 끝난 면접은 이어지지 않는다 ──────────────────────────────────────


def test_면접이_끝나면_세션을_비운다(tmp_path) -> None:
    """남겨 두면 다음 접속이 재접속으로 잡혀 두 번째 면접이 첫 면접의
    뒷부분이 된다 — 시간 예산과 진행 단계를 이어받는다."""
    runner = _FakeRunner()
    client = _client(runner, _seeded_store(tmp_path, "again"))
    with client.websocket_connect("/ws/interview?card=again") as websocket:
        _handshake(websocket)
        websocket.send_bytes(b"\x00")
        websocket.receive_bytes()  # 대역 러너가 먼저 내는 오디오
        while websocket.receive_json()["type"] != "ended":
            pass

    session = asyncio.run(
        runner.session_service.get_session(
            app_name="daedam", user_id="user", session_id="again"
        )
    )
    assert session is None


def test_새_면접은_앞_판을_지우지_않고_쌓는다(tmp_path) -> None:
    """앞서는 새 면접이 앞 판의 녹음·전사·피드백을 지웠다. 반복이 곧 제품
    가치이므로 판마다 따로 남는다 — 지난번보다 나아졌는지가 재방문 이유다."""
    store = _seeded_store(tmp_path, "clean")
    old = store.start_session("clean")
    store.save_transcript(old, {"utterances": [{"text": "앞 판"}]})
    store.save_feedback(old, {"coaching": {"score": 55}})
    store.end_session(old)

    client = _client(_FakeRunner(), store)
    with client.websocket_connect("/ws/interview?card=clean") as websocket:
        _handshake(websocket)
        websocket.send_bytes(b"\x00")
        websocket.receive_bytes()

    assert len(store.list_sessions("clean")) == 2
    kept = store.load_session(old)
    assert kept.transcript == {"utterances": [{"text": "앞 판"}]}
    assert kept.feedback == {"coaching": {"score": 55}}
    # 녹음도 판마다 다른 디렉터리라 서로 덮지 않는다.
    [new, _] = store.list_sessions("clean")
    assert store.session_directory("clean", new.id) != store.session_directory(
        "clean", old
    )


def test_지원자_이름이_세션에_실린다(tmp_path) -> None:
    """instruction이 "지원자 OO님과 면접을 진행합니다"로 쓰고, 전사 어휘
    힌트로도 나간다 — 이름은 ASR이 가장 자주 틀리는 낱말이다."""
    store = _seeded_store(tmp_path)
    user_id = store.accounts.default_user_id()
    store.save(
        "named",
        user_id=user_id,
        company="SK 하이닉스",
        role="기반기술",
        application=[],
        report=[{"title": "개요", "blocks": []}],
        uncertain=[],
        name="박지원",
    )
    store.save_questions(
        "named",
        [{"id": "q-0-0", "stage": 0, "text": "질문?", "priority": 1, "tags": ["태그"]}],
    )

    runner = _FakeRunner()
    client = _client(runner, store)
    with client.websocket_connect("/ws/interview?card=named") as websocket:
        _handshake(websocket)
        websocket.send_bytes(b"\x00")
        websocket.receive_bytes()

    assert runner.session.state["candidate"] == "박지원"


# ── 토큰 사용 집계 (원가 실측) ───────────────────────────────────────────


def test_토큰은_턴마다_더해진다() -> None:
    """Live API는 턴마다 누적 맥락을 다시 과금한다 — 마지막 턴의 숫자만 보면
    실제 청구를 크게 밑돈다. 그래서 합계를 쓴다."""
    from daedam.server.live_bridge import _Usage

    def _usage(prompt: int, response: int, audio: int, text: int):
        return types.GenerateContentResponseUsageMetadata(
            prompt_token_count=prompt,
            candidates_token_count=response,
            prompt_tokens_details=[
                types.ModalityTokenCount(modality="AUDIO", token_count=audio),
                types.ModalityTokenCount(modality="TEXT", token_count=text),
            ],
        )

    usage = _Usage()
    usage.add(_usage(1_000, 100, 800, 200))
    usage.add(_usage(3_000, 120, 2_600, 400))

    assert usage.turns == 2
    assert usage.prompt == 4_000 and usage.response == 220
    # 오디오와 텍스트는 요율이 4배 차이라 갈라서 남긴다.
    assert usage.prompt_by_modality == {"AUDIO": 3_400, "TEXT": 600}
    assert "2턴" in usage.summary() and "AUDIO=3400" in usage.summary()


def test_사용량이_없으면_집계도_비어_있다() -> None:
    from daedam.server.live_bridge import _Usage

    usage = _Usage()
    usage.add(types.GenerateContentResponseUsageMetadata())
    assert usage.turns == 1 and usage.prompt == 0
    assert usage.prompt_by_modality == {}
