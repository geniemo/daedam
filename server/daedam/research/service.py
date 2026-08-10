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

import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Literal, Protocol

from .fixture import fixture_report, fixture_uncertain
from .report import sections_from_markdown

#: Deep Research가 통상 걸리는 시간. live 모드 진행률 어림의 분모다.
_LIVE_EXPECTED_S = 40 * 60


@dataclass(frozen=True)
class ResearchStatus:
    """리서치 작업 하나의 진행 상황."""

    state: Literal["running", "done", "failed"]
    pct: int
    report: list[dict[str, Any]] | None = None
    uncertain: list[dict[str, Any]] | None = None


class ResearchService(Protocol):
    """라우트가 기대하는 리서치 백엔드 인터페이스."""

    def start(
        self, company: str, role: str, application: list[dict[str, Any]]
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
        self, company: str, role: str, application: list[dict[str, Any]]
    ) -> str:
        task_id = uuid.uuid4().hex
        self._tasks[task_id] = _FixtureTask(company, role, self._clock())
        return task_id

    def status(self, task_id: str) -> ResearchStatus | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        elapsed = self._clock() - task.started_at
        pct = min(100, int(elapsed / self._duration_s * 100))
        if pct < 100:
            return ResearchStatus(state="running", pct=pct)
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


class LiveResearch:
    """실제 Deep Research를 돌린다 (RESEARCH_MODE=live). 작업당 $1~7."""

    AGENT = "deep-research-preview-04-2026"

    def __init__(
        self,
        client: Any | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """
        Args:
            client: genai Client. 기본값은 GOOGLE_API_KEY 환경변수로 만든
                실제 클라이언트고, 테스트는 대역을 주입한다.
            clock: 단조 시계. 진행률 어림에 쓴다.
        """
        if client is None:
            from google.genai import Client

            client = Client()
        self._client = client
        self._clock = clock
        self._tasks: dict[str, _LiveTask] = {}

    def start(
        self, company: str, role: str, application: list[dict[str, Any]]
    ) -> str:
        # 백그라운드 작업은 서버가 잡아 두므로 커넥션·프로세스와 무관하게
        # 진행된다 — 사용자가 창을 닫아도 계속된다는 요구가 이걸로 성립한다.
        interaction = self._client.interactions.create(
            agent=self.AGENT,
            agent_config={"type": "deep-research"},
            input=research_prompt(company, role, application),
            background=True,
            store=True,
        )
        task_id = uuid.uuid4().hex
        self._tasks[task_id] = _LiveTask(interaction.id, self._clock())
        return task_id

    def status(self, task_id: str) -> ResearchStatus | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        interaction = self._client.interactions.get(task.interaction_id)
        if interaction.status == "completed":
            return ResearchStatus(
                state="done",
                pct=100,
                report=sections_from_markdown(_report_text_from(interaction)),
                # 신뢰도 낮은 블록 플래그는 오프라인 평가(Grok)로 붙일 예정.
                uncertain=[],
            )
        if interaction.status in ("queued", "in_progress", "requires_action"):
            # Deep Research는 진행률을 주지 않는다. 통상 소요 시간으로 어림하고
            # 완료 전에는 95%에서 멈춘다.
            elapsed = self._clock() - task.started_at
            return ResearchStatus(
                state="running", pct=min(95, int(elapsed / _LIVE_EXPECTED_S * 100))
            )
        return ResearchStatus(state="failed", pct=0)


def research_prompt(
    company: str, role: str, application: list[dict[str, Any]]
) -> str:
    """Deep Research에 줄 조사 지시문을 만든다.

    지원서는 항목 제목만 넘긴다 — 본문 대조는 리포트가 나온 뒤 서버가 한다.
    """
    lines = [
        f"{company}의 {role} 직무 신입 채용 면접을 준비하는 지원자를 위해,"
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
    return "\n".join(lines)


def _report_text_from(interaction: Any) -> str:
    """완료된 Interaction에서 리포트 본문을 꺼낸다.

    출력은 steps[*].content[*]의 text 항목으로 실린다(interaction.py의
    outputs→steps 강제 변환 참고). Deep Research는 중간 사고 요약도 텍스트로
    남길 수 있어 마지막 텍스트를 리포트로 본다.
    """
    texts: list[str] = []
    for step in interaction.steps or []:
        for item in getattr(step, "content", None) or []:
            text = getattr(item, "text", None)
            if text:
                texts.append(text)
    return texts[-1] if texts else ""
