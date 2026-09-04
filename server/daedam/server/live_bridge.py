"""브라우저 ↔ 면접관 에이전트 음성 브리지.

프론트(web/src/audio/voiceSession.ts)가 기대하는 /ws/interview 계약을 구현한다:
  클라 → 서버: 바이너리 프레임 = 16kHz PCM,
               JSON 텍스트 = 컨트롤 {"type": "start"|"end"|"playbackEnd"}
  서버 → 클라: 바이너리 프레임 = 24kHz PCM,
               JSON 텍스트 = {"type": "session"|"caption"|"question"|
                              "interrupted"|"resumeToken"|"goAway"|"ended"}

화면에 필요한 진행 상태(경과 시간·질문 번호)는 서버가 내려준다. 프론트가
자기 시계로 세면 재접속에서 서버와 어긋난다.

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
from dataclasses import dataclass, field
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
from interviewer.agent import VOICE
from interviewer.instruction import STATE_CANDIDATE, STATE_COMPANY, STATE_ROLE
from interviewer.tools import (
    STATE_APPLICATION,
    STATE_ASKED,
    STATE_PROFILE,
    STATE_QUESTION_POOL,
    STATE_RESEARCH_REPORT,
    STATE_STARTED_AT,
)

from . import fillers
from .accounts import LOCAL_PROVIDER, Accounts
from .credits import COST_INTERVIEW, Credits, InsufficientCredits
from .recording import InterviewRecording
from .store import InterviewData, InterviewStore, has_answer

logger = logging.getLogger(__name__)

#: 단일 사용자 앱 — 세션은 카드 id로만 구분한다.
_USER_ID = "user"

#: 전사에 줄 언어 힌트. 면접은 한국어로 진행되는데 자동 감지로 두면 "음"이
#: "um"으로, "팹"이 "fab"으로 떨어져 한 전사에 두 언어가 섞인다.
#: (genai types.AudioTranscriptionConfig.language_codes — BCP-47)
_LANGUAGE_CODES = ["ko-KR"]

#: 발화가 끝났다고 보기까지 필요한 침묵. 면접에서는 문장 사이 숨(0.3~0.5초)으로
#: 끊기면 안 되고, 정말 끝났을 때 1.2초 뜸 들이는 것은 부자연스럽지 않다.
#:
#: 1500의 근거는 실측이다(21.7분 면접, 답변 42개): 답변 안 생각-멈춤이 중앙값
#: 0.97초·p90 1.4초라, 그보다 짧은 문턱에서는 일상적 멈춤이 "답변 끝"으로
#: 넘어가 면접관이 끼어들었다. 1.5초는 분포의 무릎이다 — p90까지 살리면서
#: (50회 중 3회만 초과) 답변 끝 반응 지연은 +0.5초 안팎. 2초로 올려도 더
#: 살아나는 멈춤이 없다(1.5~2초 구간이 비어 있다).
_SILENCE_MS = 1500

#: Live API 입력 규격. 프론트 pcm-recorder가 이 형식 그대로 보낸다.
_INPUT_MIME = "audio/pcm;rate=16000"

#: TRACE_EVENTS=1이면 run_live 이벤트를 순서대로 남긴다 (`_event_trace`).
_TRACE_EVENTS = os.environ.get("TRACE_EVENTS") == "1"

#: 끝나지 않은 면접을 언제까지 "진행 중"으로 보는가. 제품 길이가 15~20분이고
#: 재접속 공백까지 넉넉히 잡아도 한 시간이면 충분하다. 이보다 오래된 미완
#: 면접은 창을 닫고 돌아오지 않은 것이라, 이어받지 않고 닫는다 — 이어받으면
#: 며칠 뒤의 새 면접이 옛 대화 위에서 시작한다.
_STALE_SESSION_S = 3600.0


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
    delta = (event.actions.state_delta or {}) if event.actions else {}
    asked = delta.get(STATE_ASKED)
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


@dataclass
class _Usage:
    """면접 한 판이 태운 토큰. 원가를 실측하는 유일한 길이다.

    **Live API는 턴마다 누적 맥락 전체를 다시 과금한다** — 마지막 턴의 숫자만
    보면 실제 청구의 1/8까지 내려간다는 개발자 실측 보고가 있다. 그래서
    합계를 쓴다. 원가가 통화 길이가 아니라 "길이 × 턴 수"에 비례한다는 뜻이라,
    크레딧 가격을 정하려면 이 값이 있어야 한다.

    양방향 전사도 텍스트 출력 요율로 따로 붙는다(입력·출력 오디오 요금과 별개).
    모달리티별 내역을 같이 남기는 이유가 그것이다.

    확인 경로 (설치된 ADK 2.6.3 / google-genai):
      adk/events/event.py `class Event(LlmResponse)`
      adk/models/llm_response.py:112 `usage_metadata`
      genai/types.py `GenerateContentResponseUsageMetadata`
        — prompt_token_count · candidates_token_count · *_tokens_details
    """

    turns: int = 0
    prompt: int = 0
    response: int = 0
    #: 모달리티 이름 → 토큰 수. 오디오와 텍스트의 요율이 4배 차이라 갈라 둔다.
    prompt_by_modality: dict[str, int] = field(default_factory=dict)
    response_by_modality: dict[str, int] = field(default_factory=dict)

    def add(self, usage: Any) -> None:
        self.turns += 1
        self.prompt += usage.prompt_token_count or 0
        self.response += usage.candidates_token_count or 0
        for details, bucket in (
            (usage.prompt_tokens_details, self.prompt_by_modality),
            (usage.candidates_tokens_details, self.response_by_modality),
        ):
            for item in details or []:
                name = getattr(item.modality, "value", str(item.modality))
                bucket[name] = bucket.get(name, 0) + (item.token_count or 0)

    def summary(self) -> str:
        def parts(bucket: dict[str, int]) -> str:
            return " ".join(f"{k}={v}" for k, v in sorted(bucket.items())) or "-"

        return (
            f"{self.turns}턴 · 입력 {self.prompt} [{parts(self.prompt_by_modality)}]"
            f" · 출력 {self.response} [{parts(self.response_by_modality)}]"
        )


def _last_said(recording: InterviewRecording, speaker: str) -> str:
    """이 판에서 `speaker`가 마지막으로 한 말. 없으면 빈 문자열."""
    for utterance in reversed(recording.utterances):
        if utterance.speaker == speaker:
            return utterance.text
    return ""


def _elapsed_s(state: Mapping[str, Any]) -> float:
    """면접이 시작된 뒤 흐른 초. 시작 시각이 없으면 0으로 본다."""
    started_at = state.get(STATE_STARTED_AT)
    return 0.0 if started_at is None else max(0.0, time.time() - float(started_at))


def _vocabulary_for(data: InterviewData | None, name: str = "") -> list[str]:
    """이 면접의 전사 어휘 힌트 — 키워드에 준비 단계의 추출 어휘를 합친다.

    추출 어휘만 쓰지 않는 이유: 추출은 LLM이라 확실한 낱말을 빠뜨릴 수 있고,
    실측에서 이름이 빠진 채 면접이 돌아 전사가 깨졌다. 이름·회사·직무 같은
    키워드는 규칙으로 늘 싣고 그 위에 추출을 얹는다.

    Args:
        data: 준비 데이터.
        name: 지원자 이름 — 계정 프로필에서 온다. 등록 때 이름이 비어 있던
            면접이 실제로 있어서, 여기서 채워야 이름이 힌트에 실린다.
    """
    if data is None:
        return []
    if not data.vocabulary:
        logger.info("준비된 전사 어휘가 없어 키워드만 싣습니다 (%s)", data.company)
    return interview_vocabulary(
        name=name or data.name,
        company=data.company,
        role=data.role,
        application=data.application,
        questions=data.questions,
        stored=data.vocabulary or None,
    )


def _onboarded_name(account: dict[str, Any] | None) -> str:
    """온보딩에서 사용자가 직접 입력한 이름. 아니면 빈 문자열.

    로컬 개발 모드의 기본 사용자는 "지원자"라는 자리 이름을 달고 늘
    onboarded=True다 — 그 이름이 등록 데이터의 실명을 덮으면 안 된다
    (실측: 호칭·어휘 힌트가 전부 "지원자"로 밀렸다). 소셜 계정만,
    온보딩을 마친 경우만 믿는다.
    """
    if not account:
        return ""
    if not account.get("onboarded") or account.get("provider") == LOCAL_PROVIDER:
        return ""
    return str(account.get("name") or "")


def _session_state_from(
    data: InterviewData, profile: str, name: str = ""
) -> dict[str, Any]:
    """준비 데이터를 세션 state로 옮긴다 — 시딩의 실체.

    이 키들을 instruction(회사·직무·목차)과 툴들(질문 풀·검색 인덱스·시간
    예산)이 읽는다. 리포트는 화면 형태에서 검색 입력 형태로 여기서 변환된다.
    세션이 만들어지는 순간이 곧 면접 시작이라 시계도 여기서 켠다.
    """
    return {
        STATE_COMPANY: data.company,
        STATE_ROLE: data.role,
        # instruction이 "지원자 OO님과 면접을 진행합니다"로 쓴다. 온보딩에서
        # 입력한 계정 이름이 우선이다 — 등록 데이터의 이름은 비어 있을 수
        # 있고(실측), 어휘 힌트와 호칭이 다른 이름을 쓰면 안 된다. 둘 다
        # 없으면 "지원자와"로 떨어진다 — 없는 이름을 지어내지 않는다.
        STATE_CANDIDATE: name or data.name,
        STATE_APPLICATION: data.application,
        STATE_RESEARCH_REPORT: search_sections_from_report(data.report),
        STATE_QUESTION_POOL: data.questions,
        STATE_STARTED_AT: time.time(),
        STATE_PROFILE: profile,
    }


def create_live_router(
    runner: Runner,
    store: InterviewStore,
    accounts: Accounts,
    credits: Credits,
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
        accounts: 접속한 사람을 알아낸다 — 남의 면접에 붙는 것을 막는다.
        credits: 새 면접 한 판의 크레딧을 차감한다. 재접속에는 물리지 않는다 —
            커넥션 수명(~10분) 때문에 한 판이 여러 번 접속하기 때문이다.
        profile: 시간 예산 프로필 이름 (`daedam.interview.stages.PROFILES`).
            세션 state에도 실려 툴이 같은 예산으로 단계를 판정한다.
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

        # 남의 면접에 붙지 못하게 한다. 카드 id만 알면 들어올 수 있었고, 들어온
        # 쪽이 원래 있던 커넥션을 끊어냈다 — 인증의 구멍이 여기였다.
        # 소켓도 같은 세션 쿠키를 읽는다(Starlette SessionMiddleware가
        # http·websocket 스코프를 모두 다룬다).
        user_id = accounts.session_user_id(websocket)
        if user_id is None or store.owner_of(card) != user_id:
            logger.warning("허용되지 않은 면접 접속 (card=%s)", card)
            await websocket.send_json({"type": "ended"})
            await websocket.close(code=4003, reason="권한 없음")
            return
        # 온보딩에서 입력한 이름 — 면접관 호칭과 전사 어휘 힌트가 같이 쓴다.
        # 이름이 `account`인 이유: `profile`은 이 클로저에서 시간 예산
        # 프로필이라, 같은 이름에 대입하면 클로저 읽기가 UnboundLocal로
        # 죽는다(실측).
        account_name = _onboarded_name(accounts.profile(user_id))

        # 같은 카드의 이전 커넥션을 닫는다. 닫히면 그쪽 수신 펌프가
        # disconnect를 받아 자기 정리를 시작한다.
        previous = active.get(card)
        if previous is not None:
            # 옛 탭에는 "다른 곳에서 이어졌다"를 먼저 알린다. 안 그러면 그쪽
            # 프론트가 사고로 끊긴 줄 알고 재접속해 이 커넥션을 다시 끊는다 —
            # 두 탭이 서로를 0.5초마다 쫓아내며 Live 연결을 계속 새로 여는
            # 핑퐁이 된다. 프론트는 이 이유(또는 4000 코드)를 받으면 재접속하지
            # 않고 홈으로 간다.
            try:
                await previous.send_json({"type": "ended", "reason": "replaced"})
            except Exception:  # noqa: BLE001 — 이미 닫힌 소켓이면 그만
                pass
            try:
                await previous.close(code=4000, reason="새 커넥션으로 대체")
            except Exception:  # noqa: BLE001 — 이미 닫힌 소켓이면 그만
                pass
        active[card] = websocket

        # 이 카드에서 이어받을 면접이 있는가. 커넥션이 끊긴 것과 면접이 끝난
        # 것은 다르다 — 15~20분 면접은 Live 커넥션 수명(~10분) 때문에 반드시
        # 재접속하고, 그 사이에도 같은 판이 이어져야 한다.
        session_id, abandoned = store.resume_or_abandon(card, _STALE_SESSION_S)
        for stale in abandoned:
            # 창을 닫고 돌아오지 않은 면접. 답변은 남아 있으므로 피드백은
            # 만들어 준다 — 여기서 깨우지 않으면 영영 분석되지 않는다.
            logger.info("오래된 미완 면접을 닫습니다 (session=%s)", stale)
            if evaluation is not None:
                evaluation.start(stale)

        is_new_interview = session_id is None
        data = store.load(card)
        if is_new_interview:
            if data is None or data.questions is None:
                # 준비 데이터 없는 면접은 시작하지 않는다. 조용한 폴백으로
                # 엉뚱한 데이터 면접이 도는 것보다 크게 실패하는 쪽이 낫다.
                logger.warning("준비 데이터 없는 면접 시작 거부 (card=%s)", card)
                await websocket.send_json({"type": "ended"})
                await websocket.close(code=4004, reason="준비 데이터 없음")
                return
            # 면접 한 판을 연다. 이 id가 녹음 디렉터리이자 대화 세션 id다 —
            # 앞서는 카드 id를 대화 세션 id로 썼는데, 면접을 여러 번 하게 되면
            # 두 번째 면접이 첫 면접의 대화 이력을 이어받는다.
            session_id = store.start_session(card)
            try:
                # 새 판에만 물린다. 재접속은 같은 판이라 여기를 지나지 않는다 —
                # 커넥션 수명이 ~10분이라 15~20분 면접은 반드시 재접속한다.
                credits.charge(user_id, COST_INTERVIEW, "interview", session_id)
            except InsufficientCredits:
                # 열어 둔 판을 닫는다. 안 닫으면 다음 접속이 이걸 이어받아
                # 크레딧 없이 면접이 시작된다.
                store.end_session(session_id)
                logger.info("크레딧 부족으로 면접 시작 거부 (card=%s)", card)
                await websocket.send_json({"type": "ended", "reason": "credits"})
                await websocket.close(code=4002, reason="크레딧 부족")
                return
            logger.info("면접 시작 (card=%s, session=%s)", card, session_id)

        session = await runner.session_service.get_session(
            app_name=runner.app_name, user_id=_USER_ID, session_id=session_id
        )
        if session is None:
            if data is None:
                logger.warning("준비 데이터 없는 면접 시작 거부 (card=%s)", card)
                await websocket.send_json({"type": "ended"})
                await websocket.close(code=4004, reason="준비 데이터 없음")
                return
            if not is_new_interview:
                # 면접은 진행 중인데 대화 세션이 없다. 대화 맥락은 잃지만
                # 면접을 끊는 것보다 낫다 — 준비 데이터로 다시 시딩한다.
                logger.warning(
                    "대화 세션이 없어 새로 시딩합니다 (session=%s)", session_id
                )
            session = await runner.session_service.create_session(
                app_name=runner.app_name,
                user_id=_USER_ID,
                session_id=session_id,
                state=_session_state_from(data, profile, name=account_name),
            )

        # 면접이 남기는 것. 커넥션이 끊겼다 붙어도 같은 디렉터리에 이어 쓴다 —
        # Live 커넥션 수명이 ~10분이라 15~20분 면접은 반드시 재접속한다.
        recording = InterviewRecording(
            directory=store.session_directory(card, session_id)
        )
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

        # 툴이 도는 침묵을 메울 필러 클립의 전송 상대 — 이 커넥션의 소켓.
        # 콜백(`fillers.play_filler_before_tool`)이 세션 id로 찾아 쓴다.
        filler_connection = fillers.register(session_id, websocket.send_bytes)

        # 에이전트의 귀. 여기 넣는 것이 Gemini로 흘러간다 — run_live가 이
        # 큐를 소비한다. close()가 들어가면 대화가 정상 종료된다.
        queue = LiveRequestQueue()

        turn_count = 0  # 이 커넥션에서 완료된 턴 수 — 로그용
        usage = _Usage()  # 이 커넥션이 태운 토큰 — 원가 실측용
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

        # 화면이 자기 시계를 서버에 맞추게 하는 첫 메시지. 재접속이면 이미
        # 흐른 시간과 질문 번호가 실려 화면이 이어서 그려진다 — 프론트가
        # 0부터 다시 세면 경과 시간이 줄어 보인다.
        await websocket.send_json(
            {
                "type": "session",
                # 화면이 웹캠 녹화를 어느 판에 올릴지 알아야 한다. "가장 최근
                # 판"으로 유추하게 두면, 첫 조각이 판 생성보다 빠를 때 404를
                # 받고 녹화가 통째로 죽는다.
                "sessionId": session_id,
                "elapsedSeconds": int(_elapsed_s(session.state)),
                "asked": len(session.state.get(STATE_ASKED, [])),
                # 재접속(다른 탭 포함)이면 면접관이 마지막으로 한 말. 새 탭은
                # 자막이 비어 있어서 지금 무슨 질문에 답하던 중인지 알 길이
                # 없었다 — 실측에서 지원자가 면접관에게 되물었다. 새 판이면 빈
                # 문자열이고 프론트가 무시한다.
                "caption": _last_said(recording, "interviewer"),
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
        # 이 면접에서 나올 말들. 세션 state가 아니라 준비 데이터에서 읽는다 —
        # 재접속이면 state는 이미 진행 중이지만 어휘는 그대로다.
        #
        # 준비 단계에서 뽑아 둔 것을 쓴다. 없으면(추출 실패·그 단계가 없던 옛
        # 면접) 규칙 폴백으로 만든다 — 면접 시작 경로에 LLM 호출을 두지 않는다.
        prepared = store.load(card)
        vocabulary = _vocabulary_for(prepared, name=account_name)
        run_config = RunConfig(
            response_modalities=["AUDIO"],
            # 면접관 목소리를 고정한다(`interviewer.agent.VOICE`) — 세션마다
            # 바뀌지 않게. ADK가 Live 연결로 넘긴다(adk/flows/llm_flows/basic.py:111).
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE)
                )
            ),
            # Live 커넥션 재개 핸들을 받기 위해 켠다.
            session_resumption=types.SessionResumptionConfig(),
            # 세션 시간 한도를 푼다. audio-only 세션은 압축 없이 15분에서
            # 끊기는데, full 프로필 면접(17분·하드캡 34분)이 그 한도를 넘는다.
            # 압축을 켜면 한도가 사라진다 — "enabling context window compression
            # extends session duration to unlimited time"
            # (~/refs/adk-docs/docs/live/dev-guide/part4.md, ADK 전달 경로는
            # run_config.py:270 → flows/llm_flows/basic.py:148 확인).
            #
            # 값은 보수적으로 잡는다. 이 모델의 컨텍스트 크기가 문서에 없어서
            # (예시는 128k), 32k급이어도 토큰 한도에 닿기 전에 압축이 돌게
            # 트리거를 낮게 둔다. 오디오가 초당 ~25토큰이라 target 16k는 최근
            # ~10분을 원문으로 지킨다 — 잘려 나가는 것은 더 오래된 대화의
            # 세부인데, 질문은 풀에서 오고 평가는 저장된 전사로 하므로 영향은
            # "10분 전 답변을 파고드는 꼬리질문"의 정밀도뿐이다.
            context_window_compression=types.ContextWindowCompressionConfig(
                trigger_tokens=24_000,
                sliding_window=types.SlidingWindow(target_tokens=16_000),
            ),
            # 전사 힌트. 언어를 못 박고, 그날 나올 낱말을 미리 준다. 입력
            # (지원자) 쪽은 이름·용어가 깨져서고("박지원"→"박지훈", "Jetson AGX
            # Orin"→"Jeston Ajax 올인"), 출력(면접관) 쪽은 기본값(빈 설정 =
            # 언어 자동 감지)에서 전사 스트림이 중간에 죽어서다 — 음차
            # 고유명사 "디밀리언 젯슨"까지 적고 멈춘 채 오디오만 계속 온 실측
            # 2회(같은 질문에서 재현, 오디오 31프레임에 전사 1조각). ADK가
            # 둘 다 그대로 Live 연결로 넘긴다(adk/flows/llm_flows/basic.py:114·117).
            input_audio_transcription=types.AudioTranscriptionConfig(
                language_codes=_LANGUAGE_CODES,
                custom_vocabulary=vocabulary,
            ),
            output_audio_transcription=types.AudioTranscriptionConfig(
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
                    parsed = json.loads(text)
                    # dict가 아닌 JSON(`[]`, `"x"`)에 .get을 부르면 이 커넥션이
                    # 예외로 죽는다. 모르는 모양은 그냥 넘긴다.
                    control = parsed.get("type") if isinstance(parsed, dict) else None
                    if control == "playbackEnd":
                        # 면접관의 말이 브라우저에서 끝났다. 지원자가 질문을
                        # 다 들은 순간이라 "답변까지 걸린 시간"의 기준선이다.
                        recording.mark_question_end()
                        continue
                    if control == "end":
                        if active.get(card) is not websocket:
                            # 새 커넥션에 자리를 내준 옛 탭이 정리하며 보낸 end다.
                            # 판은 이제 그쪽 것이라 여기서 닫으면 안 된다.
                            logger.info("대체된 커넥션의 종료 요청 무시 (card=%s)", card)
                            return
                        # 지원자가 끝냈다 — 면접이 끝나는 유일한 경로다. 큐를 닫아
                        # 봐야 ADK는 Gemini 소켓이 끊어진 것으로 보고 재개 핸들로
                        # 다시 붙으므로(base_llm_flow.run_live의 ConnectionClosed
                        # 분기), 이 펌프를 끝내 커넥션째 정리한다.
                        logger.info("지원자 종료 요청 (card=%s)", card)
                        await notify_ended()
                        return
                    # start/pause/resume는 서버 조치가 없다 — 마이크 뮤트는
                    # 프론트 워클릿이 하고, 커넥션은 유지한다.

        # 이 면접의 시간 예산 판정기. 하드캡을 재는 데 쓴다.
        flow = SessionFlow(session.state.get(STATE_PROFILE) or profile)

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
                nonlocal turn_count
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
                    if event.usage_metadata is not None:
                        usage.add(event.usage_metadata)
                    collect("interviewer", event.output_transcription)
                    collect("applicant", event.input_transcription)
                    # 하드캡 백스톱. 면접을 끝내는 것은 지원자의 종료 버튼이고
                    # 그 설계는 그대로다 — 이건 창을 닫고 잊은 면접이 무한히
                    # 도는 것만 막는다. Live API가 턴마다 누적 맥락을 다시
                    # 과금하므로 상한이 없으면 원가에 천장이 없다.
                    if flow.over_hard_cap(_elapsed_s(session.state)):
                        logger.warning(
                            "하드캡 도달 — 면접을 끊는다 (session=%s, 경과 %.0f초)",
                            session_id,
                            _elapsed_s(session.state),
                        )
                        await notify_ended()
                        return
                    if event.turn_complete:
                        turn_count += 1
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

        async def hard_cap_timer() -> None:
            """하드캡을 시계로 건다.

            이벤트 루프 안의 검사(`over_hard_cap`)는 모델 이벤트가 올 때만
            돌아서, 아무 말 없이 켜 둔 커넥션은 걸리지 않았다 — 마이크만 흘려
            보내면 Live 입력 오디오가 벽시계로 계속 과금됐다. 여기는 이벤트와
            무관하게 예산의 2배가 지나면 끊는다. 재접속이면 이미 흐른 시간만큼
            남은 시간이 짧다.
            """
            remaining = flow.hard_cap_s - _elapsed_s(session.state)
            await asyncio.sleep(max(0.0, remaining))
            logger.warning(
                "하드캡 도달 — 시계로 끊는다 (session=%s, 경과 %.0f초)",
                session_id,
                _elapsed_s(session.state),
            )
            await notify_ended()

        # 펌프 둘과 타이머를 나란히 돌리고, 어느 하나가 먼저 끝나면 전체를
        # 정리한다. 종료는 세 갈래다:
        #   지원자가 끝냄(end 컨트롤) 또는 클라가 끊음 → 위 펌프 리턴 → 나머지 취소
        #   모델이 끊음(run_live 종료·실패) → 아래 펌프 리턴 → 나머지 취소
        #   하드캡 → 타이머 리턴 → 나머지 취소
        # 면접을 끝내는 것은 지원자다. 타이머는 잊힌 면접의 돈을 막는 백스톱이다.
        tasks = [
            asyncio.create_task(pump_client_to_agent()),
            asyncio.create_task(pump_agent_to_client()),
            asyncio.create_task(hard_cap_timer()),
        ]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        queue.close()
        failed = False
        try:
            for task in done:
                task.result()
        except WebSocketDisconnect:
            logger.info("면접 소켓 끊김 (card=%s)", card)
        except Exception:
            # run_live가 예외로 끝났다(Live 연결 거부·쿼터·재접속 포기). 앞서는
            # 여기서 그냥 나가 소켓이 비정상 종료됐고, 프론트는 사고로 끊긴 줄
            # 알고 재접속해 같은 판을 다시 열었다 — 실패가 반복되는 동안
            # 판은 닫히지 않고 크레딧도 돌아가지 않았다.
            logger.exception("음성 브리지 오류 (card=%s)", card)
            failed = True
        finally:
            fillers.unregister(session_id, filler_connection)
            # 커넥션이 끝날 때마다 저장한다. 재접속이면 다음 커넥션이 이어
            # 받으므로 중간 저장이고, 마지막 커넥션의 것이 최종본이 된다 —
            # 면접이 어떻게 끝나든(종료 버튼·창 닫기) 기록이 남는다.
            recording.finish()
            # 이 커넥션이 태운 토큰. 크레딧 가격의 근거가 될 유일한 실측치라
            # 커넥션마다 남긴다 — 한 면접이 재접속으로 여러 커넥션에 걸친다.
            if usage.turns:
                logger.info("토큰 사용 (session=%s): %s", session_id, usage.summary())
            # 전사 전문을 면접 기록으로 올린다. 커넥션이 끊길 때마다 덮으므로
            # 마지막 커넥션의 것이 최종본이 된다.
            store.save_transcript(session_id, recording.transcript_payload())
            if failed and not ended_notified:
                # 재접속으로 될 일이 아니라는 것을 프론트에 알린다 — 4000번대는
                # 프론트가 재접속하지 않고 홈으로 가는 코드다. 답변 전이면 판을
                # 닫아 아래 종료 경로가 크레딧을 되돌리게 하고, 답변이 있으면
                # 판을 남긴다 — 한 시간 안에 다시 시작하면 이어진다.
                try:
                    await websocket.send_json({"type": "ended", "reason": "failed"})
                    await websocket.close(code=4005, reason="면접 서버 연결 실패")
                except Exception:  # noqa: BLE001 — 이미 닫힌 소켓이면 그만
                    pass
                if not has_answer(recording.transcript_payload()):
                    ended_notified = True
            if ended_notified:
                # 면접이 끝났다. 이 판을 닫아야 다음 접속이 새 면접으로
                # 시작한다 — 열어 두면 브리지가 재접속으로 보아 시간 예산과
                # 진행 단계를 이어받아, 두 번째 면접이 첫 면접의 뒷부분이 된다.
                #
                # 커넥션이 그냥 끊긴 경우(창 닫기·네트워크)는 닫지 않는다.
                # 그건 재접속이고, 이어가는 것이 맞다.
                store.end_session(session_id)
                try:
                    await runner.session_service.delete_session(
                        app_name=runner.app_name,
                        user_id=_USER_ID,
                        session_id=session_id,
                    )
                except Exception:  # noqa: BLE001 — 이미 없으면 그만
                    logger.warning(
                        "대화 세션 삭제 실패 (session=%s)", session_id, exc_info=True
                    )
                # 지원자가 한 마디도 안 한 면접은 되돌린다. 실수로 시작하고
                # 바로 나온 경우인데, 실제 원가는 몇 초치라 거의 0이면서
                # "잘못 눌렀는데 크레딧이 날아갔다"는 첫인상은 비싸다.
                if not has_answer(recording.transcript_payload()):
                    logger.info("답변이 없어 크레딧을 되돌린다 (session=%s)", session_id)
                    credits.refund(user_id, "interview", session_id)
                logger.info("면접 종료 (card=%s, session=%s)", card, session_id)
                # 끝난 뒤에만 피드백을 만든다. 재접속마다 만들면 15~20분
                # 면접 한 판에 Grok 호출이 여러 번 나간다 — 커넥션 수명이
                # ~10분이라 재접속은 정상 경로다.
                if evaluation is not None:
                    evaluation.start(session_id)
            # 내가 아직 활성 커넥션일 때만 지운다 — 새 커넥션이 이미
            # 자리를 차지했다면 그쪽 것이다.
            if active.get(card) is websocket:
                del active[card]

    return router
