# 대담 — Phase A 캐스케이드 음성 루프 (로드맵 1: 워커 뼈대)
# 확인 문서 (2026-07-21):
# - https://docs.livekit.io/agents/start/voice-ai/          (AgentServer/AgentSession/rtc_session 구조)
# - https://docs.livekit.io/agents/integrations/xai/        (xAI 플러그인 개요, XAI_API_KEY)
# - https://docs.livekit.io/agents/models/llm/plugins/xai/  (xai.responses.LLM — 기본 grok-4-1-fast-non-reasoning)
# - https://docs.livekit.io/agents/models/stt/plugins/xai/  (xai.STT — BCP-47, language="ko")
# - https://docs.livekit.io/agents/models/tts/plugins/xai/  (xai.TTS — voice="ara")
# - https://docs.livekit.io/agents/build/turns/vad/         (silero.VAD.load + prewarm 패턴)
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession
from livekit.plugins import silero, xai

load_dotenv()

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
    await session.start(room=ctx.room, agent=Agent(instructions=INSTRUCTIONS))
    await session.generate_reply(
        instructions="사용자에게 한국어로 짧게 인사하고, 음성이 잘 들리는지 확인해 달라고 요청하세요."
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
