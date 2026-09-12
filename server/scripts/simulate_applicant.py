"""모의 지원자 — 면접관과 실제 소켓으로 면접을 본다. 평가 하네스용.

    uv run python scripts/simulate_applicant.py --card <id> --cookie <파일> --runs 5 --out <디렉터리>

지원서로 만든 페르소나를 가진 Live 세션이 면접관의 말(자막)을 읽고 소리로 답한다.
그 소리를 브라우저와 같은 규격(16kHz/mono/16-bit PCM, 20ms 프레임)으로
`/ws/interview`에 실시간으로 흘려 넣는다. 서버 입장에서는 실제 면접이라 게이트
로그·전사·피드백이 그대로 남는다 — 그 로그를 `agent_metrics.py`가 읽는다.

브라우저가 하는 일을 그대로 흉내 낸다.
- 마이크는 말이 없을 때도 무음을 계속 보낸다(서버 VAD가 그것으로 턴 끝을 잰다).
- 면접관의 말이 다 재생된 뒤에야 답한다(오디오 길이로 재생 끝을 어림해 `playbackEnd`).
- 커넥션이 끊기거나 goAway가 오면 같은 카드로 재접속한다(서버가 같은 면접을 잇는다).
- 면접관이 마무리 인사를 하면 종료 버튼(`{"type": "end"}`)을 누른다.

답변 품질은 일부러 고르지 않게 한다 — 세 번에 한 번쯤 근거·수치를 빼고 말해
면접관이 파고들 자리를 만든다. 게이트가 실제로 도는 조건이 그것이다.

확인 경로 (설치된 패키지):
  google/genai/live.py  `AsyncLive.connect(model=, config=)` → `send_client_content(turns=,
    turn_complete=True)` 뒤 `receive()` — scripts/harvest_fillers.py와 같은 경로
  google/genai/types.py  LiveConnectConfig(output_audio_transcription=,
    context_window_compression=), LiveServerContent.output_transcription.text
  websockets 15  websockets.asyncio.client.connect(uri, additional_headers=)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import sys
import time
from collections import deque
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types
from scipy.signal import resample_poly
from websockets.asyncio.client import connect

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from daedam.db import Database  # noqa: E402
from daedam.server.store import InterviewStore  # noqa: E402
from interviewer.agent import MODEL  # noqa: E402

_SERVER_DIR = Path(__file__).resolve().parent.parent

#: 브라우저 마이크 규격 — 16kHz, 20ms 프레임 = 320샘플 = 640바이트.
_MIC_RATE = 16_000
_FRAME_S = 0.02
_FRAME_BYTES = int(_MIC_RATE * _FRAME_S) * 2
#: Live 출력 규격.
_OUT_RATE = 24_000

#: 면접관의 말이 끝난 뒤 답하기까지 쉬는 시간(초). 사람이 숨 고르는 만큼.
_THINK_S = (1.0, 2.4)

#: 마무리 인사 — 이것이 들리면 종료 버튼을 누른다. 질문이 아닌 문장이어야 한다.
_FAREWELL = re.compile(
    r"(안녕히 가십시오|안녕히 계십시오|안녕히 가세요|안녕히 계세요|들어가세요|면접을 마치|마치겠습니다|수고 많으셨|고생 많으셨|이상으로)"
)
_QUESTION = re.compile(r"(\?|까|나요|세요|주십시오|죠)[.?]?\s*$")


def _persona(company: str, role: str, name: str, parts: list[dict]) -> str:
    """지원서 전부를 넣은 지원자 지시. 경험 밖의 말은 못 하게 한다."""
    lines = []
    for part in parts:
        lines.append(f"[{part.get('part') or part.get('name') or '항목'}]")
        for item in part.get("items", []):
            lines.append(f"- {item.get('title', '')}\n{item.get('body', '')}")
    application = "\n".join(lines)
    return f"""\
당신은 {company} {role} 직무에 지원한 {name}입니다. 지금 한국어 음성 면접 중입니다.
면접관의 말은 글로 전달됩니다. 당신은 답변만 소리 내어 말합니다.

당신의 지원서(당신이 가진 경험의 전부):
{application}

답변 규칙:
- 구어체 존댓말. 한 번에 20~50초(네다섯 문장). 방금 받은 질문 하나에만 답합니다.
- 지원서에 있는 경험 안에서만 말합니다. 없는 경력·수치를 지어내지 않습니다.
- 세 번에 한 번쯤은 결론만 말하고 근거·수치·과정은 빼 둡니다. 면접관이 그것을
  되물으면 지원서에 있는 세부를 말하고, 지원서에 없으면 "정확히 기억나지 않습니다"라고
  합니다.
- 면접관이 인사하면 짧게 인사한 뒤 바로 자기소개를 합니다. "마지막으로 하고 싶은 말"을
  물으면 한두 문장으로. 면접관이 마무리 인사를 하면 "감사합니다"만 합니다.
- 면접관에게 되묻지 않고, 면접이나 면접관에 대한 평이나 메타 발언을 하지 않습니다."""


def _to_mic(pcm24: bytes) -> bytes:
    """Live 출력(24kHz)을 마이크 규격(16kHz)으로. 2/3 다상 리샘플."""
    samples = np.frombuffer(pcm24, dtype=np.int16).astype(np.float32)
    down = resample_poly(samples, 2, 3)
    return np.clip(down, -32768, 32767).astype(np.int16).tobytes()


class Applicant:
    """지원자 목소리 — 페르소나를 가진 Live 세션 하나. 면접 한 번에 하나."""

    def __init__(self, client: genai.Client, instruction: str, voice: str) -> None:
        self._client = client
        self._config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
            system_instruction=instruction,
            # 답변 원문을 같이 받는다 — 기록용이고, 재접속 때 요약으로 넘긴다.
            output_audio_transcription=types.AudioTranscriptionConfig(),
            # 세션 시간 한도(오디오 15분)를 푼다. 브리지와 같은 설정.
            context_window_compression=types.ContextWindowCompressionConfig(
                trigger_tokens=24_000, sliding_window=types.SlidingWindow(target_tokens=16_000)
            ),
            # 커넥션 수명(~10분)이 다하면 GoAway가 온다. 재개 핸들을 받아 두었다가
            # 다음 답변 전에 같은 대화로 다시 붙는다 — 답하는 도중에 끊기면
            # 면접관이 반 토막 답변을 듣는다(실측 1008 "failed to close … GoAway").
            session_resumption=types.SessionResumptionConfig(),
        )
        self._cm = None
        self._session = None
        self._handle: str | None = None
        self._go_away = False
        self.history: list[tuple[str, str]] = []

    async def _open(self) -> None:
        await self.close()
        config = self._config
        if self._handle:
            config = config.model_copy(
                update={"session_resumption": types.SessionResumptionConfig(handle=self._handle)}
            )
        self._cm = self._client.aio.live.connect(model=MODEL, config=config)
        self._session = await self._cm.__aenter__()
        self._go_away = False
        if self.history and not self._handle:
            # 핸들 없이 다시 연 세션은 앞의 대화를 모른다 — 요약으로 되살린다.
            recap = "\n".join(f"면접관: {q}\n나: {a}" for q, a in self.history[-6:])
            await self._session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text=f"(지금까지의 대화)\n{recap}")]),
                turn_complete=False,
            )

    async def close(self) -> None:
        if self._cm is not None:
            try:
                await self._cm.__aexit__(None, None, None)
            except Exception:  # noqa: BLE001 — 닫는 중 실패는 무시
                pass
        self._cm = self._session = None

    async def say(self, heard: str, sink) -> tuple[float, str]:
        """면접관의 말에 답한다. 오디오는 **생기는 대로** sink(24kHz PCM)에 넘긴다.

        Live 모델은 소리를 재생 속도로 내놓는다 — 턴을 다 모은 뒤에 보내면 답변
        길이만큼(20초) 면접관이 침묵을 듣는다(실측: 첫 답변 전 28초 공백).

        Returns:
            (말한 초, 답변 원문). 실패하면 (0, "").
        """
        for attempt in range(2):
            try:
                if self._session is None:
                    await self._open()
                return await self._say(heard, sink)
            except asyncio.CancelledError:
                # 답하던 중 면접관이 또 말했다 — 반쯤 받은 턴을 버리고 세션을 새로 연다.
                await self.close()
                raise
            except Exception as exc:  # noqa: BLE001 — 커넥션 수명·일시 오류면 한 번 다시 연다
                print(f"    지원자 세션 오류({attempt + 1}): {exc!r}", flush=True)
                await self.close()
        return 0.0, ""

    async def _say(self, heard: str, sink) -> tuple[float, str]:
        assert self._session is not None
        await self._session.send_client_content(
            turns=types.Content(role="user", parts=[types.Part(text=heard)]),
            turn_complete=True,
        )
        # 0.5초 단위로 리샘플해 넘긴다 — 조각마다 하면 필터 가장자리가 틱틱거린다.
        block = bytearray()
        total = 0
        said: list[str] = []
        async for message in self._session.receive():
            update = message.session_resumption_update
            if update is not None and update.resumable and update.new_handle:
                self._handle = update.new_handle
            if message.go_away is not None:
                self._go_away = True
            content = message.server_content
            if content is None:
                continue
            for part in (content.model_turn.parts if content.model_turn else None) or []:
                blob = part.inline_data
                if blob and blob.data:
                    block += blob.data
                    total += len(blob.data)
                    if len(block) >= _OUT_RATE:  # 0.5초
                        sink(bytes(block))
                        block.clear()
            if content.output_transcription and content.output_transcription.text:
                said.append(content.output_transcription.text)
            if content.turn_complete:
                break
        if block:
            sink(bytes(block))
        text = "".join(said).strip()
        self.history.append((heard, text))
        if self._go_away:
            # 이 턴은 끝났다. 끊기기 전에 우리가 닫고, 다음 답변 때 핸들로 다시 붙는다.
            await self.close()
        return total / (_OUT_RATE * 2), text


class Mic:
    """브라우저 마이크 — 20ms마다 프레임 하나. 할 말이 없으면 무음."""

    def __init__(self) -> None:
        self._pending: deque[bytes] = deque()
        self.speaking_until = 0.0

    def speak(self, pcm16: bytes) -> float:
        """말을 큐에 넣고, 다 나갈 때까지 걸리는 초를 돌려준다."""
        for at in range(0, len(pcm16), _FRAME_BYTES):
            frame = pcm16[at : at + _FRAME_BYTES]
            self._pending.append(frame.ljust(_FRAME_BYTES, b"\0"))
        seconds = len(self._pending) * _FRAME_S
        self.speaking_until = time.monotonic() + seconds
        return seconds

    def cut(self) -> None:
        """말을 끊는다 — 면접관이 끼어들었을 때 사람이 입을 닫듯."""
        self._pending.clear()
        self.speaking_until = 0.0

    async def run(self, ws) -> None:
        # 진짜 마이크는 완전한 0을 보내지 않는다 — 들리지 않는 바닥 소음(±3)을 깐다.
        rng = np.random.default_rng(0)
        next_at = time.monotonic()
        while True:
            if self._pending:
                frame = self._pending.popleft()
            else:
                frame = rng.integers(-3, 4, _FRAME_BYTES // 2, dtype=np.int16).tobytes()
            await ws.send(frame)
            next_at += _FRAME_S
            await asyncio.sleep(max(0.0, next_at - time.monotonic()))


class Interview:
    """면접 한 번 — 소켓 수명을 넘어 이어진다(재접속)."""

    def __init__(self, *, url: str, cookie: str, applicant: Applicant, max_minutes: float) -> None:
        self._url = url
        self._headers = {"Cookie": f"session={cookie}"}
        self._applicant = applicant
        self._deadline = time.monotonic() + max_minutes * 60
        self.session_id: str | None = None
        self.exchanges: list[dict] = []
        self.reconnects = 0
        self.ended_reason: str | None = None
        self._ended = asyncio.Event()

    async def run(self) -> None:
        started = time.monotonic()
        while not self._ended.is_set() and time.monotonic() < self._deadline:
            try:
                async with connect(self._url, additional_headers=self._headers, max_size=None) as ws:
                    await self._one_connection(ws)
            except Exception as exc:  # noqa: BLE001 — 끊긴 커넥션은 재접속한다
                if self._ended.is_set():
                    break
                print(f"    커넥션 끊김: {exc!r} — 재접속", flush=True)
            if not self._ended.is_set():
                self.reconnects += 1
                if self.reconnects > 6:
                    print("    재접속이 너무 잦아 그만둡니다", flush=True)
                    break
                await asyncio.sleep(1.0)
        self.duration_s = time.monotonic() - started

    async def _one_connection(self, ws) -> None:
        await ws.send(json.dumps({"type": "start"}))
        mic = Mic()
        mic_task = asyncio.create_task(mic.run(ws))
        responder: asyncio.Task | None = None
        # 면접관 턴의 오디오 — 재생 끝을 어림하는 데 쓴다.
        turn_bytes = 0
        turn_first_at: float | None = None
        caption = ""

        async def respond(heard: str, playback_end: float) -> None:
            # 면접관의 말이 다 재생된 뒤, 숨 고르고 답한다.
            await asyncio.sleep(max(0.0, playback_end - time.monotonic()))
            await ws.send(json.dumps({"type": "playbackEnd"}))
            await asyncio.sleep(random.uniform(*_THINK_S))
            asked_at = time.monotonic()
            first_at: list[float] = []

            def sink(pcm24: bytes) -> None:
                if not first_at:
                    first_at.append(time.monotonic())
                mic.speak(_to_mic(pcm24))

            seconds, text = await self._applicant.say(heard, sink)
            if not seconds:
                return
            started = (first_at[0] if first_at else asked_at) - playback_end
            self.exchanges.append({"heard": heard, "said": text, "answer_s": round(seconds, 1), "started_after_s": round(started, 1)})
            stamp = time.strftime("%H:%M:%S")
            print(f"    {stamp} Q {heard[:48]}…\n    {stamp} A ({seconds:.0f}초, 질문 끝 {started:.1f}초 뒤 시작) {text[:60]}…", flush=True)

        async def press_end(reason: str) -> None:
            await ws.send(json.dumps({"type": "end"}))
            self.ended_reason = reason

        async def heard_turn(heard: str, playback_end: float) -> None:
            """면접관의 한 턴이 끝났다 — 답하거나, 마무리 인사면 종료 버튼."""
            nonlocal responder
            if not heard.strip():
                return
            if _FAREWELL.search(heard) and not _QUESTION.search(heard):
                await asyncio.sleep(max(0.0, playback_end - time.monotonic()) + 2.0)
                await press_end("farewell")
                return
            if responder is not None and not responder.done():
                responder.cancel()
            responder = asyncio.create_task(respond(heard, playback_end))

        async def watchdog() -> None:
            nonlocal caption, turn_bytes, turn_first_at
            while True:
                await asyncio.sleep(1)
                now = time.monotonic()
                if now > self._deadline:
                    await press_end("timeout")
                    return
                # 소리는 다 왔는데 턴 완료(최종 자막)가 안 오는 턴이 있다(실측: 질문
                # 전사까지 나오고 turn_complete가 없음). 브라우저는 재생이 끝나면
                # 마이크가 열리므로 사람은 그냥 답한다 — 여기서도 재생이 끝나고
                # 2.5초 조용하면 지금까지의 자막을 그 턴의 말로 본다.
                if turn_first_at is not None and caption.strip():
                    playback_end = turn_first_at + turn_bytes / (_OUT_RATE * 2)
                    if now > playback_end + 2.5 and now - last_chunk_at[0] > 2.5:
                        heard, caption = caption, ""
                        turn_bytes, turn_first_at = 0, None
                        print("    (턴 완료 없이 소리만 끝남 — 자막으로 답합니다)", flush=True)
                        await heard_turn(heard, playback_end)
                # 면접관이 마무리 인사에 정해진 말을 안 쓰거나 세션이 멈추면 자막이 더
                # 안 온다. 답변이 끝난 뒤 한참 조용하면 종료 버튼을 누른다.
                quiet_for = now - max(mic.speaking_until, last_caption_at[0], last_chunk_at[0])
                if quiet_for > 75 and (responder is None or responder.done()):
                    print("    면접관이 75초째 말이 없어 종료 버튼을 누릅니다", flush=True)
                    await press_end("quiet")
                    return

        last_caption_at = [time.monotonic()]
        last_chunk_at = [0.0]
        watchdog_task = asyncio.create_task(watchdog())
        try:
            async for raw in ws:
                if isinstance(raw, bytes):
                    last_chunk_at[0] = time.monotonic()
                    if turn_first_at is None:
                        turn_first_at = time.monotonic()
                        # 면접관이 말을 시작했다 — 아직 답하는 중이면 입을 닫는다.
                        if mic.speaking_until > time.monotonic():
                            mic.cut()
                    turn_bytes += len(raw)
                    continue
                msg = json.loads(raw)
                kind = msg.get("type")
                if kind == "session":
                    self.session_id = msg.get("sessionId")
                    # 재접속이면 면접관의 마지막 말이 실려 온다 — 아직 답하지 않은
                    # 질문이면 그것에 답한다(브라우저도 이 자막을 보여 준다).
                    last = (msg.get("caption") or "").strip()
                    if last and _QUESTION.search(last) and not any(e["heard"] == last for e in self.exchanges):
                        last_caption_at[0] = time.monotonic()
                        responder = asyncio.create_task(respond(last, time.monotonic()))
                elif kind == "caption":
                    caption = msg.get("text") or caption
                    last_caption_at[0] = time.monotonic()
                    if msg.get("final"):
                        heard = caption
                        caption = ""
                        first = turn_first_at if turn_first_at is not None else time.monotonic()
                        playback_end = first + turn_bytes / (_OUT_RATE * 2)
                        turn_bytes, turn_first_at = 0, None
                        await heard_turn(heard, playback_end)
                elif kind == "interrupted":
                    turn_bytes, turn_first_at = 0, None
                elif kind == "goAway":
                    # 브라우저처럼 먼저 끊고 다시 붙는다.
                    return
                elif kind == "ended":
                    self.ended_reason = self.ended_reason or msg.get("reason") or "ended"
                    self._ended.set()
                    return
        finally:
            mic_task.cancel()
            watchdog_task.cancel()
            if responder is not None:
                responder.cancel()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--card", required=True, help="면접(준비 데이터) id")
    parser.add_argument("--cookie", required=True, help="세션 쿠키 값이 든 파일")
    parser.add_argument("--server", default="ws://127.0.0.1:8000")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--out", default=str(_SERVER_DIR / "data" / "_sim"))
    parser.add_argument("--voice", default="Charon")
    parser.add_argument("--max-minutes", type=float, default=25)
    args = parser.parse_args()

    load_dotenv(_SERVER_DIR / ".env")
    store = InterviewStore(Database(f"sqlite:///{_SERVER_DIR / 'data' / 'daedam.db'}"), _SERVER_DIR / "data")
    data = store.load(args.card)
    if data is None or data.questions is None:
        raise SystemExit("준비가 끝난 면접이 아닙니다")
    instruction = _persona(data.company, data.role, data.name or "지원자", data.application)
    cookie = Path(args.cookie).read_text().strip()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    client = genai.Client()

    for run in range(1, args.runs + 1):
        print(f"\n▸ 모의 면접 {run}/{args.runs}", flush=True)
        applicant = Applicant(client, instruction, args.voice)
        interview = Interview(
            url=f"{args.server}/ws/interview?card={args.card}",
            cookie=cookie,
            applicant=applicant,
            max_minutes=args.max_minutes,
        )
        try:
            await interview.run()
        finally:
            await applicant.close()
        record = {
            "session": interview.session_id,
            "duration_s": round(interview.duration_s),
            "ended": interview.ended_reason,
            "reconnects": interview.reconnects,
            "exchanges": interview.exchanges,
        }
        (out / f"run-{run}-{(interview.session_id or 'none')[:8]}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=1)
        )
        print(
            f"  끝: session={interview.session_id} {record['duration_s']}초, 답변 {len(interview.exchanges)}개,"
            f" 종료={interview.ended_reason}, 재접속 {interview.reconnects}회",
            flush=True,
        )
        await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())
