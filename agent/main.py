# 대담 — Phase A 캐스케이드 음성 루프 (모델 평가 하네스 포함)
# 확인 문서 (2026-07-21):
# - https://docs.livekit.io/agents/start/voice-ai/          (AgentServer/AgentSession/rtc_session 구조)
# - https://docs.livekit.io/agents/integrations/xai/        (xAI 플러그인 개요, XAI_API_KEY)
# - https://docs.livekit.io/agents/models/llm/plugins/xai/  (xai.responses.LLM)
# - https://docs.livekit.io/agents/models/stt/plugins/xai/  (xai.STT — BCP-47, language="ko")
# - https://docs.livekit.io/agents/models/tts/plugins/xai/  (xai.TTS — voice="ara")
# - https://docs.livekit.io/agents/build/turns/vad/         (silero.VAD.load + prewarm 패턴)
# - https://docs.livekit.io/agents/ops/logging/             (metrics_collected, EOU/LLM/TTS 지연 필드)
import json
import logging
import os
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

# 모델 평가 중에는 DAEDAM_LLM_MODEL로 세션별 스왑, 평가 후 승자를 기본값으로 확정.
# 후보·근거: scripts/bench_llm_ttft.py → data/metrics/bench-llm-*.jsonl
LLM_MODEL = os.getenv("DAEDAM_LLM_MODEL", "grok-4-1-fast-non-reasoning")

# 면접관 instruction v1 (친절 모드 기준) — 로드맵 2에서 interview/로 이전 예정
INSTRUCTIONS = """당신은 AI 모의면접 서비스 '대담'의 면접관입니다.

[역할과 태도]
- 실제 기업 면접관처럼 전문적이고 차분하게 진행합니다. 항상 존댓말을 사용하며, 어떤 경우에도 반말을 쓰지 않습니다.
- 지원자를 존중하되 과한 칭찬은 하지 않습니다. 친절하지만 긴장감 있는 면접 분위기를 유지합니다.

[진행 규칙]
- 첫 발화: 간단히 인사하고 '대담' 모의면접의 시작을 안내한 뒤, 1분 자기소개를 요청합니다.
- 질문은 한 번에 하나만, 세 문장 이내로 간결하게 합니다.
- 답변에서 구체성이 부족한 부분이 있으면 꼬리질문을 1회 던지고, 그 후에는 다음 주제로 넘어갑니다.
- 이미 한 질문이나 같은 문구를 반복하지 않습니다. 지원자가 이미 말한 내용을 다시 묻지 않습니다.
- 면접 종료는 마무리 단계에서만 합니다. 지원자가 답변 도중 감사 인사를 하더라도 그것을 종료 신호로 받아들이지 않고 면접을 계속 진행합니다.
- 면접 흐름: 자기소개 → 핵심 경험 검증 → 직무 역량 → 협업·갈등 → 마무리 순으로 자연스럽게 진행합니다.

[음성 출력 규칙]
- 모든 발화는 음성으로 변환됩니다. 이모지·특수문자·목록·마크다운 없이 자연스러운 구어체 문장으로만 말합니다.
- 숫자와 영어 약어는 한국어로 자연스럽게 읽힐 형태로 말합니다."""


def prewarm(proc: agents.JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server = AgentServer()
server.setup_fnc = prewarm


@server.rtc_session(agent_name="daedam")
async def entrypoint(ctx: agents.JobContext):
    logger.info("세션 시작 — LLM 모델: %s", LLM_MODEL)
    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        stt=xai.STT(language="ko"),
        llm=xai.responses.LLM(model=LLM_MODEL),
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
                "model": LLM_MODEL,
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
                "턴 지연 model=%s eou=%s llm_ttft=%s tts_ttfb=%s total=%s",
                LLM_MODEL, row["eou_delay"], row["llm_ttft"], row["tts_ttfb"], row["total"],
            )
            turns.pop(sid, None)

    await session.start(room=ctx.room, agent=Agent(instructions=INSTRUCTIONS))
    await session.generate_reply(
        instructions="면접관으로서 첫 발화를 하세요: 인사, '대담' 모의면접 시작 안내, 1분 자기소개 요청."
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
