"""브라우저 ↔ 면접관 에이전트 음성 브리지.

프론트(web/src/audio/voiceSession.ts)가 기대하는 /ws/interview 계약을 구현한다:
  클라 → 서버: 바이너리 프레임 = 16kHz PCM,
               JSON 텍스트 = 컨트롤 {"type": "start"|"end"|"playbackEnd"}
  서버 → 클라: 바이너리 프레임 = 24kHz PCM,
               JSON 텍스트 = {"type": "session"|"caption"|"question"|
                              "interrupted"|"resumeToken"|"goAway"|"ended"}

화면에 필요한 진행 상태(남은 시간·단계·질문 번호)는 전부 서버가 내려준다.
프론트가 자기 시계로 세면 재접속·단계 건너뜀에서 서버와 어긋난다.

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
import os
import time
from typing import Any, Mapping

from fastapi import APIRouter, WebSocket
from fastapi.websockets import WebSocketDisconnect
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import RunConfig
from google.adk.events.event import Event
from google.adk.runners import Runner
from google.adk.utils.context_utils import Aclosing
from google.genai import types

from daedam.interview.stages import DEFAULT_PROFILE, SessionFlow
from daedam.interview.vocabulary import interview_vocabulary
from daedam.research.report import search_sections_from_report
from interviewer.instruction import STATE_CANDIDATE, STATE_COMPANY, STATE_ROLE
from interviewer.tools import (
    STATE_APPLICATION,
    STATE_ASKED,
    STATE_CLOSING,
    STATE_PROFILE,
    STATE_QUESTION_POOL,
    STATE_RESEARCH_REPORT,
    STATE_STAGE,
    STATE_STARTED_AT,
)

from .recording import InterviewRecording
from .store import FileInterviewStore, InterviewData

logger = logging.getLogger(__name__)

#: 단일 사용자 앱 — 세션은 카드 id로만 구분한다.
_USER_ID = "user"

#: 전사에 줄 언어 힌트. 면접은 한국어로 진행되는데 자동 감지로 두면 "음"이
#: "um"으로, "팹"이 "fab"으로 떨어져 한 전사에 두 언어가 섞인다.
#: (genai types.AudioTranscriptionConfig.language_codes — BCP-47)
_LANGUAGE_CODES = ["ko-KR"]

#: 발화가 끝났다고 보기까지 필요한 침묵. 면접에서는 문장 사이 숨(0.3~0.5초)으로
#: 끊기면 안 되고, 정말 끝났을 때 1.2초 뜸 들이는 것은 부자연스럽지 않다.
_SILENCE_MS = 1200

#: Live API 입력 규격. 프론트 pcm-recorder가 이 형식 그대로 보낸다.
_INPUT_MIME = "audio/pcm;rate=16000"

#: 마무리에 들어간 뒤 인사 한 턴을 기다리는 상한(초). 모델이 인사를 안 하고
#: 뭉개도 여기서 끊는다.
_CLOSING_GRACE_S = 30.0

#: 모델이 말을 마친 뒤 큐를 닫기까지의 여유(초). 프론트 재생 큐에 아직 남아
#: 있는 오디오가 있어서, 바로 닫으면 마지막 인사가 잘려 들린다.
_PLAYBACK_TAIL_S = 3.0

#: TRACE_EVENTS=1이면 run_live 이벤트를 순서대로 남긴다 (`_event_trace`).
_TRACE_EVENTS = os.environ.get("TRACE_EVENTS") == "1"


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

    # 모델 발화의 전사 → 화면 자막. 조각으로 흘러오므로 프론트가 이어 붙이고,
    # finished가 턴의 끝을 알린다(google.genai types.Transcription.finished).
    # 자막이 실제 발화인 이유는 면접관이 뼈대질문을 그대로 읽지 않고, 꼬리질문에는
    # 대본 자체가 없기 때문이다 — 준비된 문장을 띄우면 들리는 말과 어긋난다.
    # 사용자 쪽 전사(input_transcription)는 화면에 안 쓰므로 보내지 않는다.
    transcription = event.output_transcription
    if transcription is not None and (transcription.text or transcription.finished):
        messages.append(
            (
                "json",
                {
                    "type": "caption",
                    "text": transcription.text or "",
                    "final": bool(transcription.finished),
                },
            )
        )

    # ask_question이 뼈대질문을 배달하면 그 이벤트의 state 델타에 늘어난 asked가
    # 실려 온다 — 뼈대질문이 하나 나간 순간이고, 낸 질문 수가 곧 번호다.
    # 같은 델타의 stage로 화면 상단의 단계 표시가 함께 움직인다.
    delta = (event.actions.state_delta or {}) if event.actions else {}
    asked = delta.get(STATE_ASKED)
    if asked:
        messages.append(
            (
                "json",
                {
                    "type": "question",
                    "index": len(asked) - 1,
                    "stage": int(delta.get(STATE_STAGE, 0)),
                },
            )
        )

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


def _event_trace(event: Event) -> str | None:
    """이벤트 하나를 한 줄로 요약한다. 오디오만 실린 이벤트면 None.

    자막 로그(턴당 최종 전사 한 줄)로는 발화와 툴 호출의 순서를 못 가른다.
    실측에서 한 전사 안에 지원자 발화 하나와 면접관 발화 셋이 섞여 나온 적이
    있어, 그 줄을 "무슨 말이 나갔는가"의 증인으로 쓸 수 없다는 것이 드러났다.
    순서를 봐야 할 때만 TRACE_EVENTS=1로 켠다 — 상시로 켜면 로그가 묻힌다.
    """
    bits: list[str] = []
    for part in (event.content.parts if event.content else None) or []:
        if part.text:
            bits.append(f"text {part.text[:60]!r}")
        if part.function_call is not None:
            # 인자까지 찍는다. 모델이 문장을 만들어 넘겼는지가, 그 문장이 소리로도
            # 나가는 이유를 가르는 유일한 증거다.
            bits.append(f"호출 {part.function_call.name}({part.function_call.args})")
        if part.function_response is not None:
            bits.append(f"응답 {part.function_response.name}")
    if (out := event.output_transcription) is not None:
        bits.append(f"면접관전사 fin={bool(out.finished)} {(out.text or '')[:60]!r}")
    if (inp := event.input_transcription) is not None:
        bits.append(f"지원자전사 fin={bool(inp.finished)} {(inp.text or '')[:60]!r}")
    if event.interrupted:
        bits.append("끼어들기")
    if event.turn_complete:
        bits.append("턴완료")
    if event.partial:
        bits.append("partial")
    return f"[{event.author}] " + " · ".join(bits) if bits else None


def _elapsed_s(state: Mapping[str, Any]) -> float:
    """면접이 시작된 뒤 흐른 초. 시작 시각이 없으면 0으로 본다."""
    started_at = state.get(STATE_STARTED_AT)
    return 0.0 if started_at is None else max(0.0, time.time() - float(started_at))


def _marks_closing(event: Event) -> bool:
    """면접이 마무리에 들어갔다는 표시인가.

    툴이 done을 돌려줄 때(질문 소진·하드캡) state에 남긴 자국이다. 모델은
    커넥션을 끊을 수 없으므로 실제 종료는 이걸 보고 서버가 한다.
    """
    delta = (event.actions.state_delta or {}) if event.actions else {}
    return bool(delta.get(STATE_CLOSING))


def _session_state_from(data: InterviewData, profile: str) -> dict[str, Any]:
    """준비 데이터를 세션 state로 옮긴다 — 시딩의 실체.

    이 키들을 instruction(회사·직무·목차)과 툴들(질문 풀·검색 인덱스·시간
    예산)이 읽는다. 리포트는 화면 형태에서 검색 입력 형태로 여기서 변환된다.
    세션이 만들어지는 순간이 곧 면접 시작이라 시계도 여기서 켠다.
    """
    return {
        STATE_COMPANY: data.company,
        STATE_ROLE: data.role,
        # instruction이 "지원자 OO님과 면접을 진행합니다"로 쓴다. 비어 있으면
        # "지원자와"로 떨어지므로 없는 이름을 지어내지 않는다.
        STATE_CANDIDATE: data.name,
        STATE_APPLICATION: data.application,
        STATE_RESEARCH_REPORT: search_sections_from_report(data.report),
        STATE_QUESTION_POOL: data.questions,
        STATE_STARTED_AT: time.time(),
        STATE_PROFILE: profile,
    }


def create_live_router(
    runner: Runner,
    store: FileInterviewStore,
    profile: str = DEFAULT_PROFILE,
    evaluation: Any = None,
) -> APIRouter:
    """음성 브리지 라우터를 만든다.

    Args:
        runner: 면접관 에이전트를 물고 있는 Runner. 세션 저장소도 이 러너의
            것을 쓴다 — 브리지가 세션 생성을 소유해야 준비 데이터 시딩이
            이 지점에 꽂힌다. 테스트는 대역 러너를 주입한다.
        evaluation: 면접이 끝나면 피드백을 만드는 오케스트레이터. None이면
            기록만 남기고 만들지 않는다(테스트).
        store: 면접 준비 데이터 저장소. 세션 생성 시 여기서 읽어 시딩한다.
        profile: 시간 예산 프로필 이름 (`daedam.interview.stages.PROFILES`).
            세션 state에도 실려 툴이 같은 예산으로 단계를 판정한다.
    """
    router = APIRouter()
    flow = SessionFlow(profile)

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
            # 새 면접이면 앞 판의 흔적을 지운다. 녹음은 이어 쓰기라 남겨 두면
            # 새 면접이 앞 면접 뒤에 붙고, 피드백은 앞 판의 것이라 새 면접이
            # 끝나기 전까지 화면이 옛 결과를 보여준다.
            InterviewRecording.discard(store.directory(card))
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
                state=_session_state_from(data, profile),
            )

        # 면접이 남기는 것. 커넥션이 끊겼다 붙어도 같은 디렉터리에 이어 쓴다 —
        # Live 커넥션 수명이 ~10분이라 15~20분 면접은 반드시 재접속한다.
        recording = InterviewRecording(directory=store.directory(card))
        # 전사는 조각으로 흘러오다 finished에 전문이 실린다. 그 전문만 한
        # 토막으로 남긴다. 프론트도 같은 규칙이다 — final이면 자막을 text로
        # 통째로 교체하고(store/interview.ts appendCaption), 그래도 자막이 잘려
        # 보인 적이 없다. 전문이 안 실린 경우를 대비해 모아둔 조각을 받쳐 둔다.
        partial: dict[str, str] = {"interviewer": "", "applicant": ""}

        def collect(speaker: str, transcription: Any) -> None:
            if transcription is None:
                return
            text = transcription.text or ""
            if not transcription.finished:
                partial[speaker] += text
                return
            recording.note(speaker, text or partial[speaker])
            partial[speaker] = ""

        # 에이전트의 귀. 여기 넣는 것이 Gemini로 흘러간다 — run_live가 이
        # 큐를 소비한다. close()가 들어가면 대화가 정상 종료된다.
        queue = LiveRequestQueue()

        # 이벤트 펌프가 세우고 종료 태스크가 기다리는 두 신호.
        closing = asyncio.Event()  # 툴이 마무리를 알렸다
        turn_done = asyncio.Event()  # 모델이 한 턴을 말끝까지 마쳤다
        turn_count = 0  # 이 커넥션에서 완료된 턴 수 — 인사 대기의 기준선
        turns_at_closing = 0  # 마무리 표시를 읽은 순간의 턴 수

        ended_notified = False

        async def notify_ended() -> None:
            """프론트에 종료를 알린다. 어느 경로로 끝나든 한 번만 나간다."""
            nonlocal ended_notified
            if ended_notified:
                return
            ended_notified = True
            try:
                await websocket.send_json({"type": "ended"})
                logger.info("종료 통지 전송 (card=%s)", card)
            except Exception:  # noqa: BLE001 — 이미 닫힌 소켓이면 그만
                # 삼키되 남긴다. 이 줄이 없으면 "화면이 안 넘어간다"를 놓고
                # 서버가 안 보냈는지 브라우저가 안 받았는지 가릴 수 없다.
                logger.warning("종료 통지 전송 실패 — 소켓이 이미 닫혔다 (card=%s)", card)

        async def wait_next_turn(baseline: int, timeout_s: float) -> bool:
            """모델이 턴을 하나 더 마칠 때까지 기다린다. 시간 안에 오면 True.

            turn_done을 clear하고 기다리는 대신 완료된 턴 수를 기준선으로 쓴다 —
            마무리 표시와 인사가 붙어 오면(종료 툴 경로) 표시를 읽고 깨어나는
            사이에 인사 턴이 이미 끝나 있을 수 있는데, clear()는 그 사실을 지운다.
            """
            if turn_count > baseline:
                return True
            turn_done.clear()
            try:
                await asyncio.wait_for(turn_done.wait(), timeout=timeout_s)
            except TimeoutError:
                return False
            return True

        # 화면이 자기 시계를 서버에 맞추게 하는 첫 메시지. 재접속이면 이미
        # 흐른 시간과 진행 상황이 실려 화면이 이어서 그려진다 — 프론트가
        # 0부터 다시 세면 남은 시간이 늘어나 보인다.
        await websocket.send_json(
            {
                "type": "session",
                "totalSeconds": int(flow.hard_cap_s),
                "elapsedSeconds": int(_elapsed_s(session.state)),
                "stageBudgets": [int(seconds) for seconds in flow.profile.budgets],
                "stage": int(session.state.get(STATE_STAGE, 0)),
                "asked": len(session.state.get(STATE_ASKED, [])),
            }
        )

        if is_new_interview:
            # 개시 신호 — 모델은 입력이 와야 입을 여는데, 지원자가 먼저 말을
            # 걸어야 면접이 시작되는 UX는 어색하다. 첫 입장에만 한 턴을 넣어
            # 면접관이 먼저 인사하게 한다. 재연결·재입장은 이력이 있으므로
            # 다시 인사하지 않는다.
            #
            # 지시문이 아니라 인사말인 이유: 이 채널은 지원자의 목소리다. 여기에
            # "(지원자가 입장했습니다…)" 같은 3인칭 지문을 넣으면 user 채널에
            # 지원자의 말과 지문이 섞이고, 그것이 세션 이벤트로 저장돼
            # (base_llm_flow._send_to_model) 재접속마다 다시 실린다. 면접이 대화가
            # 아니라 모델이 같이 쓰는 대본으로 읽히는 자리가 여기라고 보고 있다 —
            # 실측에서 모델이 지원자의 답변을 1인칭으로 대신 말한 적이 네 번 있다.
            #
            # 인사를 받으면 면접을 시작하라는 것은 instruction이 나른다. 모델은
            # 입력이 와야 입을 여는데, 지원자가 먼저 말을 걸어야 면접이 시작되는
            # UX는 어색하다. 그래서 첫 인사만 서버가 대신 건넨다.
            queue.send_content(
                types.Content(
                    role="user",
                    parts=[
                        types.Part(text="안녕하세요.")
                    ],
                )
            )
        # 이 면접에서 나올 말들. 세션 state가 아니라 준비 데이터에서 뽑는다 —
        # 재접속이면 state는 이미 진행 중이지만 어휘는 그대로다.
        prepared = store.load(card)
        vocabulary = (
            interview_vocabulary(
                name=prepared.name,
                company=prepared.company,
                role=prepared.role,
                application=prepared.application,
                questions=prepared.questions,
            )
            if prepared is not None
            else []
        )
        run_config = RunConfig(
            response_modalities=["AUDIO"],
            # Live 커넥션 재개 핸들을 받기 위해 켠다. 자막용 양방향 전사는
            # RunConfig 기본값이 이미 켜 준다(run_config.py의 default_factory).
            session_resumption=types.SessionResumptionConfig(),
            # 전사 힌트. 언어를 못 박고, 그날 나올 낱말을 미리 준다 — 실측에서
            # 이름과 기술 용어가 계속 깨졌다("박지원"→"박지훈", "Jetson AGX
            # Orin"→"Jeston Ajax 올인"). ADK가 이 설정을 그대로 Live 연결로
            # 넘긴다(adk/flows/llm_flows/basic.py:117).
            input_audio_transcription=types.AudioTranscriptionConfig(
                language_codes=_LANGUAGE_CODES,
                custom_vocabulary=vocabulary,
            ),
            # 발화 종료 판정을 늦춘다. 기본값이 면접에는 너무 급하다 —
            # genai types.py EndSensitivity: "The default is
            # END_SENSITIVITY_HIGH for Gemini Live". 지원자가 생각하느라 쉬는
            # 것을 끝으로 보고 모델이 먼저 말하기 시작하면, 지원자가 이어
            # 말할 때 끼어들기로 그 턴이 취소된다. 툴 응답이 이미 나간 뒤에
            # 취소되면 세션이 통째로 멈춘다(실측: 2분간 무응답).
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                    silence_duration_ms=_SILENCE_MS,
                )
            ),
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
                    recording.write_audio(data)
                elif text := message.get("text"):
                    control = json.loads(text).get("type")
                    if control == "playbackEnd":
                        # 면접관의 말이 브라우저에서 끝났다. 지원자가 질문을
                        # 다 들은 순간이라 "답변까지 걸린 시간"의 기준선이다.
                        recording.mark_question_end()
                        continue
                    if control == "end":
                        # 지원자가 끝냈다. 큐를 닫아 봐야 ADK가 재연결로 받으므로
                        # (end_interview 주석 참고) 이 펌프를 끝내 커넥션째 정리한다.
                        # 어느 쪽이 끝냈든 종료는 서버가 알린다 — 계약이 하나다.
                        logger.info("지원자 종료 요청 (card=%s)", card)
                        await notify_ended()
                        return
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
                nonlocal turn_count, turns_at_closing
                audio_run = 0  # 연속된 오디오 프레임 — 묶어서 한 줄로 낸다
                async for event in agen:
                    if _TRACE_EVENTS:
                        line = _event_trace(event)
                        if line is None:
                            audio_run += 1
                        else:
                            if audio_run:
                                logger.info("추적: 오디오 %d프레임", audio_run)
                                audio_run = 0
                            logger.info("추적: %s", line)
                    collect("interviewer", event.output_transcription)
                    collect("applicant", event.input_transcription)
                    if _marks_closing(event) and not closing.is_set():
                        # 인사 대기의 기준선은 여기서 잡는다. 종료 태스크가
                        # 깨어난 시점에 잡으면 그 사이에 끝난 인사 턴을 놓치고
                        # 다음 턴을 30초 기다리게 된다.
                        turns_at_closing = turn_count
                        closing.set()
                    if event.turn_complete:
                        turn_count += 1
                        turn_done.set()
                        logger.info(
                            "턴 완료 %d회째 (경과 %.0f초)",
                            turn_count,
                            _elapsed_s(session.state),
                        )
                    for kind, payload in _client_messages_from(event):
                        if kind == "bytes":
                            await websocket.send_bytes(payload)
                            continue
                        if payload["type"] == "question":
                            # 툴의 배달 로그와 짝을 이룬다. 둘 중 이 줄만 없으면
                            # state 델타가 브리지까지 오지 않은 것이다.
                            logger.info("질문 %d번 화면 전달", payload["index"])
                        elif payload["type"] == "caption" and payload["final"]:
                            # 면접관이 실제로 한 말. 툴 호출 기록만으로는 면접에서
                            # 무슨 일이 있었는지 알 수 없다 — 꼬리질문의 질, 준비된
                            # 질문을 어떻게 바꿔 물었는지, 검색 결과를 대화에
                            # 실었는지가 여기서만 드러난다. 턴이 끝난 전문만 남긴다.
                            if payload["text"]:
                                logger.info("면접관: %s", payload["text"])
                        await websocket.send_json(payload)
            await notify_ended()

        async def end_interview() -> None:
            """면접을 끝낸다 — 마무리에 들어갔거나, 하드캡에 닿거나.

            모델은 툴을 호출할 때만 시간을 알고, 커넥션을 끊을 수도 없다.
            꼬리질문만 이어가면 툴을 안 부르므로 툴 쪽 판정만으로는 면접이
            안 끝난다. 그래서 종료는 서버가 시계를 들고 쥔다
            (daedam/interview/stages.py 첫 줄의 원칙).
            """
            started_at = session.state.get(STATE_STARTED_AT)
            if started_at is None:
                logger.warning("시작 시각 없는 세션 — 시간 예산 미적용 (card=%s)", card)
                return
            remaining_s = flow.hard_cap_s - (time.time() - float(started_at))
            try:
                await asyncio.wait_for(closing.wait(), timeout=max(0.0, remaining_s))
                baseline = turns_at_closing
                logger.info("마무리 진입 — 인사를 기다린다 (card=%s)", card)
            except TimeoutError:
                # 하드캡. 지시는 지원자 발화로 넣는다 — 개시 신호와 같은 통로다.
                baseline = turn_count
                logger.info("하드캡 도달 — 마무리 지시 주입 (card=%s)", card)
                queue.send_content(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                text="(면접 시간이 다 됐습니다."
                                " 짧게 마무리 인사를 하고 면접을 끝내 주세요.)"
                            )
                        ],
                    )
                )

            # 인사 한 턴이 끝나기를 기다린다.
            if not await wait_next_turn(baseline, _CLOSING_GRACE_S):
                logger.info(
                    "마무리 인사가 오지 않아 그대로 종료 (턴 완료 %d회, card=%s)",
                    turn_count,
                    card,
                )
            await asyncio.sleep(_PLAYBACK_TAIL_S)

            # 종료를 알리고 소켓을 우리가 닫는다. run_live가 끝나기를 기다리지
            # 않는 이유: 큐를 닫으면 ADK는 Gemini 소켓이 끊어진 것으로 보고
            # 재개 핸들로 다시 붙는다(base_llm_flow.run_live의 ConnectionClosed
            # 분기) — 의도한 종료와 사고를 구분하지 못한다. 소켓을 닫으면 수신
            # 펌프가 정리되면서 run_live 제너레이터도 함께 닫힌다.
            await notify_ended()
            try:
                await websocket.close(code=1000, reason="면접 종료")
            except Exception:  # noqa: BLE001 — 이미 닫혔으면 그만
                pass
            logger.info(
                "면접 종료 — 소켓을 닫았다 (경과 %.0f초, card=%s)",
                _elapsed_s(session.state),
                card,
            )

        # 두 펌프를 나란히 돌리고, 어느 한쪽이 먼저 끝나면 전체를 정리한다.
        # 자연스러운 종료는 두 갈래다:
        #   클라가 끊음 → 위 펌프 리턴 → 아래 펌프 취소 + 큐 close
        #   대화 종료(end/모델/하드캡) → 아래 펌프 리턴 → 위 펌프 취소
        # 종료 태스크는 이 wait에 넣지 않는다 — 스스로 끝을 알리는 대신 큐를
        # 닫아 위 두 갈래 중 하나로 흘려보내는 역할이다.
        ending = asyncio.create_task(end_interview())
        tasks = [
            asyncio.create_task(pump_client_to_agent()),
            asyncio.create_task(pump_agent_to_client()),
        ]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        ending.cancel()
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
            # 커넥션이 끝날 때마다 저장한다. 재접속이면 다음 커넥션이 이어
            # 받으므로 중간 저장이고, 마지막 커넥션의 것이 최종본이 된다 —
            # 면접이 어떻게 끝나든(정상 종료·하드캡·창 닫기) 기록이 남는다.
            recording.finish()
            if ended_notified:
                # 면접이 끝났다. 세션을 지워야 다음 접속이 새 면접으로 시작한다 —
                # 남겨 두면 브리지가 재접속으로 보아 시간 예산과 진행 단계를
                # 이어받아, 두 번째 면접이 첫 면접의 뒷부분이 된다.
                #
                # 커넥션이 그냥 끊긴 경우(창 닫기·네트워크)는 지우지 않는다.
                # 그건 재접속이고, 이어가는 것이 맞다.
                try:
                    await runner.session_service.delete_session(
                        app_name=runner.app_name, user_id=_USER_ID, session_id=card
                    )
                    logger.info("면접 종료 — 세션을 비웠다 (card=%s)", card)
                except Exception:  # noqa: BLE001 — 이미 없으면 그만
                    logger.warning("세션 삭제 실패 (card=%s)", card, exc_info=True)
            # 기록이 남은 직후에 피드백 생성을 깨운다. 재접속이면 다음
            # 커넥션이 이어가므로 그때 다시 깨워지고, 이미 돌고 있으면
            # evaluation이 스스로 무시한다.
            if evaluation is not None:
                evaluation.start(card)
            # 내가 아직 활성 커넥션일 때만 지운다 — 새 커넥션이 이미
            # 자리를 차지했다면 그쪽 것이다.
            if active.get(card) is websocket:
                del active[card]

    return router
