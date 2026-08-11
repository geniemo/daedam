"""브라우저 ↔ 면접관 에이전트 음성 브리지.

프론트(web/src/audio/voiceSession.ts)가 기대하는 /ws/interview 계약을 구현한다:
  클라 → 서버: 바이너리 프레임 = 16kHz PCM,
               JSON 텍스트 = 컨트롤 {"type": "start"|"pause"|"resume"|"end"}
  서버 → 클라: 바이너리 프레임 = 24kHz PCM,
               JSON 텍스트 = {"type": "caption"|"question"|"interrupted"|
                              "resumeToken"|"goAway"|"ended"}

골격은 ADK api_server의 /run_live와 같다 — 받은 오디오를 LiveRequestQueue에
넣고, run_live 이벤트 스트림을 프론트 어휘로 번역해 내보낸다. 차이는 두 가지:
오디오가 base64-in-JSON이 아니라 바이너리 프레임이고, 세션 생성을 브리지가
소유한다(준비 데이터 시딩이 꽂힐 자리).

확인 경로 (설치된 ADK 2.6.3 소스):
  google/adk/cli/api_server.py  `/run_live`
    — run_live(session, live_request_queue, run_config) + 양방향 태스크 골격
  google/adk/agents/live_request_queue.py — send_realtime(Blob) / close()
  google/adk/models/llm_response.py — interrupted·output_transcription·
    live_session_resumption_update·go_away 필드
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket
from fastapi.websockets import WebSocketDisconnect
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import RunConfig
from google.adk.events.event import Event
from google.adk.runners import Runner
from google.adk.utils.context_utils import Aclosing
from google.genai import types

from daedam.research.report import search_sections_from_report
from interviewer.instruction import STATE_COMPANY, STATE_ROLE
from interviewer.tools import (
    STATE_APPLICATION,
    STATE_QUESTION_POOL,
    STATE_RESEARCH_REPORT,
)

from .store import FileInterviewStore, InterviewData

logger = logging.getLogger(__name__)

#: 단일 사용자 앱 — 세션은 카드 id로만 구분한다.
_USER_ID = "user"

#: Live API 입력 규격. 프론트 pcm-recorder가 이 형식 그대로 보낸다.
_INPUT_MIME = "audio/pcm;rate=16000"


def _client_messages_from(event: Event) -> list[tuple[str, Any]]:
    """에이전트 이벤트를 프론트 프로토콜 메시지로 번역한다.

    화면에 필요한 것만 옮긴다 — 툴 호출, state 델타 내용, 사용자 전사 같은
    서버 내부는 클라이언트로 내보내지 않는다.

    Returns:
        ("bytes", 오디오 bytes) 또는 ("json", dict) 튜플 목록.
    """
    messages: list[tuple[str, Any]] = []

    # 모델 음성 조각(24kHz PCM) → 바이너리 프레임 그대로. 프론트 pcm-player의
    # 재생 큐로 들어간다.
    for part in (event.content.parts if event.content else None) or []:
        blob = part.inline_data
        if blob and blob.data:
            messages.append(("bytes", blob.data))

    # 모델 발화의 전사 → 화면 자막. 사용자 쪽 전사(input_transcription)는
    # 화면에 안 쓰므로 보내지 않는다.
    if event.output_transcription and event.output_transcription.text:
        messages.append(
            ("json", {"type": "caption", "text": event.output_transcription.text})
        )

    # get_next_question이 실행되면 그 이벤트의 state 델타에 늘어난 asked가
    # 실려 온다 — 뼈대질문이 하나 나간 순간이고, 낸 질문 수가 곧 번호다.
    # 화면의 "질문 N" 표시가 이걸로 움직인다.
    asked = (event.actions.state_delta or {}).get("asked") if event.actions else None
    if asked:
        messages.append(("json", {"type": "question", "index": len(asked) - 1}))

    # 사용자가 말을 끊었다(barge-in). 프론트는 이걸 받는 즉시 재생 버퍼를
    # 비운다 — 안 비우면 에이전트가 사용자 말 위로 계속 떠든다.
    if event.interrupted:
        messages.append(("json", {"type": "interrupted"}))

    # Live 커넥션 재개 핸들. 프론트가 보관했다가 재접속 URL에 실어 보낸다
    # (서버는 아직 이 값을 쓰지 않는다 — 핸들러의 resume 주석 참고).
    update = event.live_session_resumption_update
    if update is not None and update.new_handle:
        messages.append(("json", {"type": "resumeToken", "token": update.new_handle}))

    # Gemini가 커넥션을 곧 끊겠다는 예고. 프론트는 이걸 받으면 끊기기 전에
    # 먼저 재접속한다.
    if event.go_away is not None:
        messages.append(("json", {"type": "goAway"}))
    return messages


def _session_state_from(data: InterviewData) -> dict[str, Any]:
    """준비 데이터를 세션 state로 옮긴다 — 시딩의 실체.

    이 키들을 instruction(회사·직무·목차)과 툴들(질문 풀·검색 인덱스)이
    읽는다. 리포트는 화면 형태에서 검색 입력 형태로 여기서 변환된다.
    """
    return {
        STATE_COMPANY: data.company,
        STATE_ROLE: data.role,
        STATE_APPLICATION: data.application,
        STATE_RESEARCH_REPORT: search_sections_from_report(data.report),
        STATE_QUESTION_POOL: data.questions,
    }


def create_live_router(runner: Runner, store: FileInterviewStore) -> APIRouter:
    """음성 브리지 라우터를 만든다.

    Args:
        runner: 면접관 에이전트를 물고 있는 Runner. 세션 저장소도 이 러너의
            것을 쓴다 — 브리지가 세션 생성을 소유해야 준비 데이터 시딩이
            이 지점에 꽂힌다. 테스트는 대역 러너를 주입한다.
        store: 면접 준비 데이터 저장소. 세션 생성 시 여기서 읽어 시딩한다.
    """
    router = APIRouter()

    #: 카드당 활성 커넥션 하나. 새 접속이 오면 이전 것을 서버가 닫는다 —
    #: 개발 모드 이중 마운트나 중복 탭이 만드는 "두 목소리"의 방어선이다.
    active: dict[str, WebSocket] = {}

    @router.websocket("/ws/interview")
    async def interview_socket(
        websocket: WebSocket, card: str, resume: str | None = None
    ) -> None:
        # 이 함수 호출 하나 = 브라우저 커넥션 하나. 아래에서 만드는 세션 조회,
        # 큐, 펌프 태스크 둘은 전부 이 커넥션과 수명을 같이한다. 재접속이
        # 오면 이 함수가 처음부터 다시 돈다.
        #
        # resume 파라미터는 아직 쓰지 않는다 — 재접속하면 같은 ADK 세션
        # (session_id=card)에 새 run_live를 열고, 대화 맥락은 세션 이력이
        # 복원한다. Live API 수준의 재개 핸들 활용은 후속 과제.
        del resume
        await websocket.accept()

        # 같은 카드의 이전 커넥션을 닫는다. 닫히면 그쪽 수신 펌프가
        # disconnect를 받아 자기 정리를 시작한다.
        previous = active.get(card)
        if previous is not None:
            try:
                await previous.close(code=4000, reason="새 커넥션으로 대체")
            except Exception:  # noqa: BLE001 — 이미 닫힌 소켓이면 그만
                pass
        active[card] = websocket

        session = await runner.session_service.get_session(
            app_name=runner.app_name, user_id=_USER_ID, session_id=card
        )
        is_new_interview = session is None
        if is_new_interview:
            data = store.load(card)
            if data is None or data.questions is None:
                # 준비 데이터 없는 면접은 시작하지 않는다. 조용한 폴백으로
                # 엉뚱한 데이터 면접이 도는 것보다 크게 실패하는 쪽이 낫다.
                logger.warning("준비 데이터 없는 면접 시작 거부 (card=%s)", card)
                await websocket.send_json({"type": "ended"})
                await websocket.close(code=4004, reason="준비 데이터 없음")
                return
            session = await runner.session_service.create_session(
                app_name=runner.app_name,
                user_id=_USER_ID,
                session_id=card,
                state=_session_state_from(data),
            )

        # 에이전트의 귀. 여기 넣는 것이 Gemini로 흘러간다 — run_live가 이
        # 큐를 소비한다. close()가 들어가면 대화가 정상 종료된다.
        queue = LiveRequestQueue()

        if is_new_interview:
            # 개시 신호 — 모델은 입력이 와야 입을 여는데, 지원자가 먼저 말을
            # 걸어야 면접이 시작되는 UX는 어색하다. 첫 입장에만 한 턴을 넣어
            # 면접관이 먼저 인사하게 한다. 재연결·재입장은 이력이 있으므로
            # 다시 인사하지 않는다.
            queue.send_content(
                types.Content(
                    role="user",
                    parts=[types.Part(text="(지원자가 입장했습니다.)")],
                )
            )
        run_config = RunConfig(
            response_modalities=["AUDIO"],
            # Live 커넥션 재개 핸들을 받기 위해 켠다. 자막용 양방향 전사는
            # RunConfig 기본값이 이미 켜 준다(run_config.py의 default_factory).
            session_resumption=types.SessionResumptionConfig(),
        )

        async def pump_client_to_agent() -> None:
            """브라우저 → 에이전트 방향 펌프.

            마이크 PCM(바이너리)은 큐로 넣고, 컨트롤(JSON)은 해석한다.
            클라이언트가 끊으면 리턴한다 — 그 리턴이 아래 wait를 깨워
            커넥션 전체 정리가 시작된다.
            """
            while True:
                # starlette의 저수준 수신: {"type": "websocket.receive",
                # "bytes"|"text": ...} 또는 {"type": "websocket.disconnect"}.
                # 한 소켓에 바이너리와 텍스트가 섞여 오므로 이 형태로 받는다.
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    return
                if (data := message.get("bytes")) is not None:
                    queue.send_realtime(types.Blob(mime_type=_INPUT_MIME, data=data))
                elif text := message.get("text"):
                    if json.loads(text).get("type") == "end":
                        queue.close()
                    # start/pause/resume는 서버 조치가 없다 — 마이크 뮤트는
                    # 프론트 워클릿이 하고, 커넥션은 유지한다.

        async def pump_agent_to_client() -> None:
            """에이전트 → 브라우저 방향 펌프.

            run_live 제너레이터가 곧 대화 전체다: Gemini 연결을 열고, 살아
            있는 동안 이벤트(음성·전사·신호)를 내놓는다. 루프가 끝났다는 건
            대화가 끝났다는 뜻이다 — end 컨트롤로 큐가 닫혔거나 모델이
            종료했거나. 그때 프론트에 ended를 알린다.
            """
            async with Aclosing(
                runner.run_live(
                    session=session,
                    live_request_queue=queue,
                    run_config=run_config,
                )
            ) as agen:
                async for event in agen:
                    for kind, payload in _client_messages_from(event):
                        if kind == "bytes":
                            await websocket.send_bytes(payload)
                        else:
                            await websocket.send_json(payload)
            await websocket.send_json({"type": "ended"})

        # 두 펌프를 나란히 돌리고, 어느 한쪽이 먼저 끝나면 전체를 정리한다.
        # 자연스러운 종료는 두 갈래다:
        #   클라가 끊음 → 위 펌프 리턴 → 아래 펌프 취소 + 큐 close
        #   대화 종료(end/모델) → 아래 펌프 리턴 → 위 펌프 취소
        tasks = [
            asyncio.create_task(pump_client_to_agent()),
            asyncio.create_task(pump_agent_to_client()),
        ]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        queue.close()
        try:
            for task in done:
                task.result()
        except WebSocketDisconnect:
            logger.info("면접 소켓 끊김 (card=%s)", card)
        except Exception:
            logger.exception("음성 브리지 오류 (card=%s)", card)
        finally:
            # 내가 아직 활성 커넥션일 때만 지운다 — 새 커넥션이 이미
            # 자리를 차지했다면 그쪽 것이다.
            if active.get(card) is websocket:
                del active[card]

    return router
