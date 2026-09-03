"""면접 시작 전 리서치 파이프라인.

Deep Research는 비동기 전용(background=True)이고 20~60분, 작업당 $1~7이다.
그래서 실행 모드를 둘로 나눈다:
  - fixture(기본): 미리 준비된 리포트를 짧은 가짜 진행 뒤에 돌려준다.
    개발·데모 경로다 — 라이브는 40분이 걸려 현장에서 돌릴 수 없다.
  - live: interactions API로 실제 Deep Research를 돌린다.

interactions API 확인 경로 (설치된 google-genai 소스):
  google/genai/_gaos/interactions.py  `create(**body_kwargs)` / `get(id)`
  google/genai/_gaos/types/interactions/agentoption.py
    — "deep-research-preview-04-2026"
  google/genai/_gaos/types/interactions/interaction.py  `InteractionStatus`
    — queued/in_progress/requires_action은 진행 중, completed가 완료
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Protocol

from .fixture import fixture_report, fixture_uncertain
from .report import sections_from_markdown

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResearchStatus:
    """리서치 작업 하나의 진행 상황."""

    state: Literal["running", "done", "failed"]
    #: 0~100. **모를 수 있다.** fixture는 총 소요 시간을 알아 진짜 진행률을
    #: 내지만, Deep Research는 진행률을 주지 않는다(Interaction에 그런 필드가
    #: 없다). 경과 시간으로 어림한 숫자를 진행률이라 부르면 화면이 거짓말을
    #: 하므로, live에서는 None을 주고 화면은 막대를 그리지 않는다.
    pct: int | None
    report: list[dict[str, Any]] | None = None
    uncertain: list[dict[str, Any]] | None = None
    #: 지금까지 실제로 한 조사. 오래된 것부터. 진행 화면이 이걸 그린다 —
    #: 미리 적어둔 단계 목록은 실제 순서와 맞지 않아 화면이 거짓말을 한다.
    activity: tuple[str, ...] = ()
    #: 관측된 현재 단계. 스텝 종류에서 나오므로 지어낸 값이 아니다.
    phase: str = ""
    #: 시작 후 경과 초. 퍼센트와 달리 이건 언제나 사실이다.
    elapsed_s: float = 0.0


class ResearchService(Protocol):
    """라우트가 기대하는 리서치 백엔드 인터페이스.

    `start`의 `task_id`는 호출자가 미리 정한 id다. 등록은 유료 작업을 시작하기
    **전에** 이 id를 근거로 크레딧을 차감해야 하므로 id가 먼저 있어야 한다.
    없으면 백엔드가 만든다.
    """

    def start(
        self,
        company: str,
        role: str,
        application: list[dict[str, Any]],
        posting: str = "",
        *,
        task_id: str | None = None,
    ) -> str: ...

    def status(self, task_id: str) -> ResearchStatus | None: ...


@dataclass
class _FixtureTask:
    company: str
    role: str
    started_at: float


class FixtureResearch:
    """미리 준비된 리포트를 가짜 진행 뒤에 돌려준다 (RESEARCH_MODE=fixture)."""

    def __init__(
        self,
        duration_s: float = 12.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """
        Args:
            duration_s: 0%에서 100%까지 걸리는 시간. 데모에서 진행 화면이
                보일 만큼만 잡는다.
            clock: 단조 시계. 테스트가 가짜 시계를 주입한다.
        """
        self._duration_s = duration_s
        self._clock = clock
        self._tasks: dict[str, _FixtureTask] = {}

    def start(
        self,
        company: str,
        role: str,
        application: list[dict[str, Any]],
        posting: str = "",
        *,
        task_id: str | None = None,
    ) -> str:
        task_id = task_id or uuid.uuid4().hex
        self._tasks[task_id] = _FixtureTask(company, role, self._clock())
        return task_id

    def status(self, task_id: str) -> ResearchStatus | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        elapsed = self._clock() - task.started_at
        pct = min(100, int(elapsed / self._duration_s * 100))
        if pct < 100:
            # 그럴듯한 검색어를 지어내지 않는다. fixture는 조사를 하지 않으므로
            # 조사한 척하면 진행 화면이 다시 거짓말을 하게 된다.
            return ResearchStatus(
                state="running",
                pct=pct,
                activity=("미리 준비된 리포트를 불러오는 중입니다 (RESEARCH_MODE=fixture)",),
                phase="불러오는 중",
                elapsed_s=elapsed,
            )
        return ResearchStatus(
            state="done",
            pct=100,
            report=fixture_report(task.company, task.role),
            uncertain=fixture_uncertain(),
        )


@dataclass
class _LiveTask:
    interaction_id: str
    started_at: float
    #: 스트림이 채우는 조사 서술. 폴링으로는 절대 안 오는 값이라 여기 모은다.
    activity: list[str] = field(default_factory=list)
    #: 스트림 소비 스레드가 이미 붙었는가. 두 번 붙이면 같은 줄이 두 번 쌓인다.
    streaming: bool = False


class LiveResearch:
    """실제 Deep Research를 돌린다 (RESEARCH_MODE=live). 작업당 $1~7."""

    AGENT = "deep-research-preview-04-2026"

    def __init__(
        self,
        client: Any | None = None,
        clock: Callable[[], float] = time.time,
        raw_dir: Path | None = None,
        state_path: Path | None = None,
    ) -> None:
        """
        Args:
            client: genai Client. 기본값은 GOOGLE_API_KEY 환경변수로 만든
                실제 클라이언트고, 테스트는 대역을 주입한다.
            clock: 벽시계(epoch 초). 진행률 어림에 쓰고 파일에 그대로 남는다.
                단조 시계를 쓰면 재시작 후 경과 시간을 복원할 수 없다.
            raw_dir: 완료된 리포트 원문을 파싱 전에 떨어뜨릴 디렉터리.
                작업당 20~60분·$1~7이라, 파싱이 틀리면 원문까지 잃는 일이
                없어야 한다. None이면 남기지 않는다(테스트).
            state_path: 진행 중인 작업의 인터랙션 id를 남길 파일. 이게 없으면
                리서치가 서버 재시작을 못 넘긴다 — 20~60분 도는 동안 한 번만
                재기동해도 id가 사라져 결과를 영영 못 찾는다. None이면
                메모리에만 둔다(테스트).
        """
        if client is None:
            from google.genai import Client

            client = Client()
        self._client = client
        self._clock = clock
        self._raw_dir = raw_dir
        self._state_path = state_path
        self._tasks: dict[str, _LiveTask] = self._load_state()
        # 재시작으로 되살린 작업에도 스트림을 다시 붙인다.
        for task_id in self._tasks:
            self._attach_stream(task_id)

    def start(
        self,
        company: str,
        role: str,
        application: list[dict[str, Any]],
        posting: str = "",
        *,
        task_id: str | None = None,
    ) -> str:
        # 백그라운드 작업은 서버가 잡아 두므로 커넥션·프로세스와 무관하게
        # 진행된다 — 사용자가 창을 닫아도 계속된다는 요구가 이걸로 성립한다.
        interaction = self._client.interactions.create(
            agent=self.AGENT,
            # thinking_summaries를 켜야 진행 중에 무엇을 조사하는지가 스텝으로
            # 남는다. 끄면(기본) 완료 응답에 user_input과 model_output만 남아
            # 진행 화면이 보여줄 사실이 하나도 없다 — 실측으로 확인했다.
            #   types/interactions/deepresearchagentconfig.py  thinking_summaries
            #   types/interactions/thinkingsummaries.py        "auto" | "none"
            agent_config={"type": "deep-research", "thinking_summaries": "auto"},
            input=research_prompt(company, role, application, posting),
            background=True,
            store=True,
        )
        task_id = task_id or uuid.uuid4().hex
        self._tasks[task_id] = _LiveTask(interaction.id, self._clock())
        # 인터랙션이 만들어진 직후 남긴다. 여기서 죽으면 돌고 있는 작업을
        # 되찾을 방법이 없다.
        self._save_state()
        self._attach_stream(task_id)
        return task_id

    def status(self, task_id: str) -> ResearchStatus | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        interaction = self._client.interactions.get(task.interaction_id)
        if interaction.status == "completed":
            markdown = _report_text_from(interaction)
            self._dump_raw(task.interaction_id, markdown)
            return ResearchStatus(
                state="done",
                pct=100,
                report=sections_from_markdown(markdown),
                # 신뢰도 낮은 블록 플래그는 오프라인 평가(Grok)로 붙일 예정.
                uncertain=[],
            )
        if interaction.status in ("queued", "in_progress", "requires_action"):
            # 퍼센트를 만들지 않는다. Deep Research는 진행률을 주지 않고, 통상
            # 소요 시간(20~60분)으로 나눈 숫자는 매 회차 어긋난다. 대신 스텝에서
            # 읽어낸 단계와 경과 시간만 준다 — 둘 다 관측된 사실이다.
            return ResearchStatus(
                state="running",
                pct=None,
                # 조사 서술은 스트림이 채운다. 폴링(interactions.get)은 완료 전까지
                # user_input 하나만 돌려준다 — 실측으로 확인했다.
                activity=tuple(task.activity),
                phase=_phase_of(interaction),
                elapsed_s=self._clock() - task.started_at,
            )
        return ResearchStatus(state="failed", pct=0)

    def _attach_stream(self, task_id: str) -> None:
        """조사 서술을 받는 스트림을 붙인다. 실패해도 리서치에는 영향이 없다.

        폴링(`interactions.get`)은 완료 전까지 user_input 하나만 돌려준다 —
        15초 간격으로 6분 30초를 물어 확인했다. 진행 상황은 스트림으로만 온다.
        문서: ai.google.dev/gemini-api/docs/deep-research #long-running-tasks
          "stream=True 및 background=True를 설정해야 합니다"
          "agent_config에서 thinking_summaries를 auto로 설정"

        상태·리포트는 여전히 폴링이 담당한다. 검증된 경로를 새 기능이 망가뜨리면
        안 되므로 둘을 분리한다 — 스트림이 죽으면 서술만 잃는다.
        """
        task = self._tasks.get(task_id)
        if task is None or task.streaming:
            return
        task.streaming = True
        threading.Thread(
            target=self._consume_stream, args=(task_id,), daemon=True
        ).start()

    def _consume_stream(self, task_id: str) -> None:
        """스트림을 소비하고, 끊기면 끊긴 지점부터 다시 붙는다.

        20~60분짜리 작업이라 한 번의 끊김으로 포기하면 나머지 서술을 통째로
        잃는다. 모든 이벤트가 event_id를 싣고 그것으로 재개할 수 있다.
          types/interactions/stepdelta.py  event_id
            "The event_id token to be used to resume the interaction stream"

        재개 토큰을 못 받았으면 처음부터 다시 받는다 — 이미 쌓인 제목은
        중복으로 걸러지므로 같은 줄이 두 번 생기지 않는다.
        """
        task = self._tasks[task_id]
        last_event_id: str | None = None
        attempts = 0
        try:
            while True:
                try:
                    for event in self._client.interactions.get(
                        id=task.interaction_id,
                        stream=True,
                        last_event_id=last_event_id,
                    ):
                        attempts = 0  # 하나라도 받았으면 연결은 건강하다
                        data = getattr(event, "data", event)
                        event_id = getattr(data, "event_id", None)
                        if event_id:
                            last_event_id = event_id
                        if getattr(data, "event_type", None) in _STREAM_TERMINAL:
                            return
                        line = _headline(event)
                        # 델타는 이어 붙는 조각이라 같은 제목이 다시 오기도 한다.
                        if line and line not in task.activity:
                            task.activity.append(line)
                except Exception:
                    logger.warning(
                        "조사 서술 스트림이 끊겼습니다 (interaction=%s) — 다시 붙습니다",
                        task.interaction_id,
                        exc_info=True,
                    )

                attempts += 1
                if attempts > _STREAM_RETRIES:
                    logger.warning(
                        "조사 서술 스트림을 포기합니다 (interaction=%s) —"
                        " 리서치와 리포트는 폴링이 그대로 가져옵니다",
                        task.interaction_id,
                    )
                    return
                time.sleep(min(_STREAM_BACKOFF_S * attempts, _STREAM_BACKOFF_MAX_S))
        finally:
            task.streaming = False

    def _load_state(self) -> dict[str, _LiveTask]:
        """재시작 전에 돌고 있던 작업을 되살린다. 못 읽으면 빈 채로 시작한다."""
        if self._state_path is None or not self._state_path.exists():
            return {}
        try:
            saved = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.exception("리서치 작업 기록을 읽지 못했습니다 (%s)", self._state_path)
            return {}
        tasks = {
            task_id: _LiveTask(entry["interaction_id"], entry["started_at"])
            for task_id, entry in saved.items()
        }
        if tasks:
            logger.info("재시작 전 리서치 %d건을 이어받습니다", len(tasks))
        return tasks

    def _save_state(self) -> None:
        """작업 기록을 파일에 남긴다. 저장 실패가 리서치를 막지는 않는다."""
        if self._state_path is None:
            return
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                task_id: {
                    "interaction_id": task.interaction_id,
                    "started_at": task.started_at,
                }
                for task_id, task in self._tasks.items()
            }
            self._state_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            logger.exception("리서치 작업 기록 저장 실패 (%s)", self._state_path)

    def _dump_raw(self, interaction_id: str, markdown: str) -> None:
        """리포트 원문을 파싱 전에 파일로 떨어뜨린다.

        `sections_from_markdown`이 형식을 잘못 읽어도 원문은 남아야 한다 —
        다시 받으려면 20~60분과 $1~7이 또 든다. 저장 실패가 리서치를 실패로
        만들면 안 되므로 여기서만 삼킨다.
        """
        if self._raw_dir is None or not markdown:
            return
        try:
            self._raw_dir.mkdir(parents=True, exist_ok=True)
            (self._raw_dir / f"{interaction_id}.md").write_text(
                markdown, encoding="utf-8"
            )
        except OSError:
            logger.exception("리서치 원문 저장 실패 (interaction=%s)", interaction_id)


def research_prompt(
    company: str,
    role: str,
    application: list[dict[str, Any]],
    posting: str = "",
) -> str:
    """Deep Research에 줄 조사 지시문을 만든다.

    지원서는 항목 제목만 넘긴다 — 본문 대조는 리포트가 나온 뒤 서버가 한다.

    Args:
        company: 지원 회사.
        role: 지원 직무. "서비스기획 · 신입"처럼 경력 구분이 이미 들어 있을 수
            있어 문장에 "신입"을 덧붙이지 않는다.
        application: 지원서 파트 목록.
        posting: 채용공고 링크 또는 본문. 비어 있으면 Deep Research가 직접
            공고를 찾는데, 회사에 유사 직무 공고가 여럿이면 다른 공고의
            요구역량으로 질문이 만들어진다. 그래서 있으면 그대로 싣는다 —
            파싱하지 않는다. 링크면 에이전트가 열어 보고 본문이면 본문대로 읽는다.
    """
    lines = [
        f"{company}의 {role} 채용 면접을 준비하는 지원자를 위해,"
        " 아래 구성을 따르는 한국어 조사 리포트를 작성하십시오.",
        "",
        "## Executive Summary",
        "## 1. 회사와 사업 구조",
        "## 2. 최근 1년의 변화 (뉴스·IR·기술 블로그)",
        "## 3. 인재상과 조직문화",
        "## 4. 직무 요구역량 (채용공고 기준)",
        "## 5. 면접에서 검증될 가능성이 높은 지점",
        "## 출처",
        "",
        "각 사실에는 [n] 형태로 출처 번호를 달고, 마지막 출처 섹션에서 번호별"
        " 출처를 밝히십시오. 확인되지 않는 내용은 추정임을 명시하십시오.",
    ]
    titles = [
        item.get("title", "")
        for part in application
        for item in part.get("items", [])
        if item.get("title")
    ]
    if titles:
        lines += [
            "",
            "지원자의 지원서 항목: " + " / ".join(titles),
            "5번 섹션에서 이 항목들과 회사 요구역량의 접점을 짚으십시오.",
        ]
    if posting.strip():
        lines += [
            "",
            "지원자가 지원한 채용공고는 아래와 같습니다. 4번 섹션의 요구역량은"
            " 이 공고를 우선 근거로 삼고, 다른 공고를 참고했다면 그렇게 밝히십시오.",
            "",
            posting.strip(),
        ]
    return "\n".join(lines)


#: 리포트 본문이 실리는 스텝 종류. 첫 스텝은 우리가 보낸 프롬프트가 되돌아온
#: 것(user_input)이라 빼야 한다.
_MODEL_OUTPUT = "model_output"

def _phase_of(interaction: Any) -> str:
    """스텝 종류로 지금 어느 단계인지 읽는다.

    Deep Research는 진행률을 주지 않지만 단계는 드러난다. 리포트 본문이
    실리는 model_output 스텝이 나타났다는 것은 조사를 마치고 쓰기 시작했다는
    뜻이다 — 지어낸 값이 아니라 관측이다.
    """
    if getattr(interaction, "status", None) == "queued":
        return "차례를 기다리는 중"
    steps = getattr(interaction, "steps", None) or []
    if any(getattr(step, "type", None) == _MODEL_OUTPUT for step in steps):
        return "리포트 작성 중"
    return "자료 조사 중"


#: 이 이벤트가 오면 스트림을 더 붙잡지 않는다. 완료 후에도 계속 재연결하면
#: 같은 이벤트를 영원히 다시 받는다(완료된 인터랙션도 전체를 재생해 준다).
_STREAM_TERMINAL = ("interaction.completed", "error")
#: 스트림 재연결 상한과 대기. 끊김이 이어져도 서술만 포기하면 되고, 상태와
#: 리포트는 폴링이 따로 가져온다.
_STREAM_RETRIES = 20
_STREAM_BACKOFF_S = 5.0
_STREAM_BACKOFF_MAX_S = 60.0

#: `**제목**` 또는 `***제목***`으로 시작하는 서술 조각. 조사 에이전트가 자기
#: 생각을 이 형식으로 토막 내 보낸다(실측: 한 리서치에 24토막).
_HEADLINE = re.compile(r"\*{2,3}(.+?)\*{2,3}")


def _headline(event: Any) -> str:
    """스트림 이벤트 하나에서 화면에 걸 한 줄을 뽑는다.

    thought 스텝의 step.delta에만 서술이 실린다. 본문은 영어 산문 여러 문장이라
    화면에 그대로 걸 수 없어 굵게 표시된 제목만 쓴다 — 그게 조사 에이전트가
    스스로 붙인 단계 이름이다.

    확인 경로 (완료된 SK하이닉스 인터랙션에 스트림을 붙여 재생):
      step.start(step.type == "thought") → step.delta(delta.content.text) 다수
      델타 텍스트: "***Generating research plan***\n\nTo best answer..."
    """
    data = getattr(event, "data", event)
    if getattr(data, "event_type", None) != "step.delta":
        return ""
    delta = getattr(data, "delta", None)
    content = getattr(delta, "content", None)
    text = getattr(content, "text", None)
    if not text:
        return ""
    found = _HEADLINE.search(text)
    return found.group(1).strip() if found else ""


def _report_text_from(interaction: Any) -> str:
    """완료된 Interaction에서 리포트 본문을 꺼낸다.

    Deep Research는 리포트를 여러 스텝에 나눠 내보낸다. 실측(컬리 리서치)에서
    한 리포트가 세 조각으로 왔고, 마지막 조각만 쓰면 Executive Summary와 1~4장을
    통째로 잃는다 — 처음에 그렇게 만들었다가 실제로 잃었다.

    확인 경로 (실제 완료 응답):
      steps[0].type == "user_input"    — 요청 프롬프트
      steps[1:].type == "model_output" — content에 ImageContent(차트)와
                                         TextContent가 섞여 온다
    """
    parts: list[str] = []
    for step in interaction.steps or []:
        if getattr(step, "type", None) != _MODEL_OUTPUT:
            continue
        for item in getattr(step, "content", None) or []:
            text = getattr(item, "text", None)
            if text:
                parts.append(text)
    return "".join(parts)
