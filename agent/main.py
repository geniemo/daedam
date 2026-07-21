# 대담 — Phase A 캐스케이드 음성 루프 (로드맵 1: 워커 뼈대 + 구간별 지연 계측)
# 확인 문서 (2026-07-21):
# - https://docs.livekit.io/agents/start/voice-ai/          (AgentServer/AgentSession/rtc_session 구조)
# - https://docs.livekit.io/agents/integrations/xai/        (xAI 플러그인 개요, XAI_API_KEY)
# - https://docs.livekit.io/agents/models/llm/plugins/xai/  (xai.responses.LLM — 기본 grok-4-1-fast-non-reasoning)
# - https://docs.livekit.io/agents/models/stt/plugins/xai/  (xai.STT — BCP-47, language="ko")
# - https://docs.livekit.io/agents/models/tts/plugins/xai/  (xai.TTS — voice="ara")
# - https://docs.livekit.io/agents/build/turns/vad/         (silero.VAD.load + prewarm 패턴)
# - https://docs.livekit.io/agents/ops/logging/             (metrics_collected, EOU/LLM/TTS 지연 필드)
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, MetricsCollectedEvent, metrics
from livekit.agents.metrics import EOUMetrics, LLMMetrics, TTSMetrics
from livekit.plugins import silero, xai

load_dotenv()

logger = logging.getLogger("daedam.metrics")

METRICS_DIR = Path(__file__).resolve().parent.parent / "data" / "metrics"

# 로드맵 1 단계용 임시 instruction — 면접 상태 머신(로드맵 2)에서 교체된다
INSTRUCTIONS = """당신은 '대담' 서비스의 음성 대화 테스트 도우미입니다.
모든 답변은 한국어로, 두세 문장 이내로 간결하게 말합니다.
이모지·특수문자·목록 없이 자연스러운 구어체로만 답합니다."""


def prewarm(proc: agents.JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server = AgentServer()
server.setup_fnc = prewarm


@server.rtc_session(agent_name="daedam")
async def entrypoint(ctx: agents.JobContext):
    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        stt=xai.STT(language="ko"),
        llm=xai.responses.LLM(),
        tts=xai.TTS(voice="ara"),
    )

    # 구간별 지연 계측: 턴(speech_id)마다 EOU 지연 / LLM TTFT / TTS TTFB를 모아
    # TTS 시작(첫 오디오 산출) 시점에 JSONL 한 줄로 기록. total ≈ 발화 종료 → 첫 오디오.
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = METRICS_DIR / f"{datetime.now(timezone.utc):%Y%m%d}-cascade.jsonl"
    turns: dict[str, dict] = {}

    @session.on("metrics_collected")
    def _on_metrics(ev: MetricsCollectedEvent):
        m = ev.metrics
        metrics.log_metrics(m)
        sid = getattr(m, "speech_id", None)
        if sid is None:
            return
        turn = turns.setdefault(sid, {})
        if isinstance(m, EOUMetrics):
            turn["eou_delay"] = m.end_of_utterance_delay
        elif isinstance(m, LLMMetrics):
            turn["llm_ttft"] = m.ttft
        elif isinstance(m, TTSMetrics):
            turn["tts_ttfb"] = m.ttfb
            row = {
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "pipeline": "cascade-xai",
                "room": ctx.room.name,
                "speech_id": sid,
                "eou_delay": turn.get("eou_delay"),
                "llm_ttft": turn.get("llm_ttft"),
                "tts_ttfb": turn.get("tts_ttfb"),
            }
            parts = [row["eou_delay"], row["llm_ttft"], row["tts_ttfb"]]
            row["total"] = round(sum(parts), 3) if all(v is not None for v in parts) else None
            with metrics_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            logger.info(
                "턴 지연 eou=%s llm_ttft=%s tts_ttfb=%s total=%s",
                row["eou_delay"], row["llm_ttft"], row["tts_ttfb"], row["total"],
            )
            turns.pop(sid, None)

    await session.start(room=ctx.room, agent=Agent(instructions=INSTRUCTIONS))
    await session.generate_reply(
        instructions="사용자에게 한국어로 짧게 인사하고, 음성이 잘 들리는지 확인해 달라고 요청하세요."
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
