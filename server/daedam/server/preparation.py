"""면접 준비 오케스트레이터 — 리서치 → 저장 → 질문 생성 → 완료.

작업(면접)마다 전담 워커 스레드가 파이프라인을 완주한다. 브라우저 폴링은
전진과 무관한 순수 조회라, 사용자가 창을 닫아도 준비는 서버에서 계속된다 —
진행 화면의 안내 문구가 여기서 참이 된다.

pct 배분: 리서치 0~90(서비스 pct의 0.9배), 질문 생성 95, 완료 100. 화면
진행 단계의 마지막 칸(질문 준비)이 실제 생성 구간과 일치한다.

완료의 증거는 메모리가 아니라 파일 저장소다 — 서버가 재시작돼도 저장된
면접은 done으로 복원되고, 생성 도중 끊겼다면 부팅 복원이 생성만 이어서
한다. 진행 중이던 리서치 자체는 재시작을 넘지 못한다(후속: live의
interaction id를 저장해 워커 재기동).
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Literal

from daedam.interview.generation import generate_question_pool
from daedam.knowledge.chunk import chunks_from_application, chunks_from_report
from daedam.research.report import search_sections_from_report
from daedam.research.service import ResearchService, ResearchStatus

from .store import FileInterviewStore, InterviewData

logger = logging.getLogger(__name__)


@dataclass
class _PipelineState:
    """워커가 갱신하고 status()가 읽기만 하는 진행 기록."""

    phase: Literal["researching", "generating", "failed"]
    pct: int


class InterviewPreparation:
    """리서치 서비스와 질문 생성을 하나의 준비 파이프라인으로 묶는다."""

    def __init__(
        self,
        research: ResearchService,
        store: FileInterviewStore,
        generate: Callable[..., list[dict[str, Any]]] = generate_question_pool,
        poll_interval_s: float = 1.0,
    ) -> None:
        """
        Args:
            research: fixture 또는 live 리서치 백엔드.
            store: 준비 데이터 파일 저장소.
            generate: 질문 생성 함수. 테스트가 대역을 주입한다.
            poll_interval_s: 워커가 리서치 완료를 확인하는 간격. live에서는
                30초쯤으로 늘려 폴링 API 낭비를 없앤다.
        """
        self._research = research
        self._store = store
        self._generate = generate
        self._poll_interval_s = poll_interval_s
        self._states: dict[str, _PipelineState] = {}
        self._recover()

    def start(
        self, company: str, role: str, application: list[dict[str, Any]]
    ) -> str:
        task_id = self._research.start(company, role, application)
        self._states[task_id] = _PipelineState(phase="researching", pct=0)
        # 이 면접 전담 워커 — 브라우저가 닫혀도 파이프라인은 여기서 완주한다.
        threading.Thread(
            target=self._run_pipeline,
            args=(task_id, company, role, application),
            daemon=True,
        ).start()
        return task_id

    def status(self, task_id: str) -> ResearchStatus | None:
        """준비 전체의 진행 상황. 읽기만 한다 — 전진은 워커의 일이다."""
        stored = self._store.load(task_id)
        if stored is not None and stored.questions is not None:
            # 완료의 증거는 파일 — 재시작 후에도 이 분기가 done을 복원한다.
            return ResearchStatus(
                state="done", pct=100, report=stored.report, uncertain=stored.uncertain
            )
        state = self._states.get(task_id)
        if state is None:
            return None
        if state.phase == "failed":
            return ResearchStatus(state="failed", pct=0)
        return ResearchStatus(state="running", pct=state.pct)

    def _run_pipeline(
        self,
        task_id: str,
        company: str,
        role: str,
        application: list[dict[str, Any]],
    ) -> None:
        state = self._states[task_id]
        try:
            # ① 리서치 완주 대기. 프론트의 1초 폴링과 무관하게 자기 속도로 묻는다.
            while True:
                research = self._research.status(task_id)
                if research is None or research.state == "failed":
                    state.phase = "failed"
                    return
                if research.state == "done":
                    break
                state.pct = int(research.pct * 0.9)
                time.sleep(self._poll_interval_s)

            # ② 산출물 저장 — 이 순간부터 서버가 죽어도 리서치를 잃지 않는다.
            self._store.save(
                task_id,
                company=company,
                role=role,
                application=application,
                report=research.report or [],
                uncertain=research.uncertain or [],
            )

            # ③ 질문 생성 — 화면의 "질문 준비" 단계가 실제로 이 구간이다.
            self._run_generation(task_id, self._store.load(task_id))
        except Exception:
            logger.exception("면접 준비 실패 (interview=%s)", task_id)
            state.phase = "failed"

    def _run_generation(self, task_id: str, data: InterviewData) -> None:
        state = self._states[task_id]
        state.phase, state.pct = "generating", 95
        questions = self._generate(
            company=data.company,
            role=data.role,
            report_chunks=chunks_from_report(search_sections_from_report(data.report)),
            application_chunks=chunks_from_application(data.application),
        )
        self._store.save_questions(task_id, questions)
        del self._states[task_id]  # 완료 — 이제부터 파일이 진실을 말한다

    def _recover(self) -> None:
        """저장은 됐는데 질문이 없는 면접 — 재시작으로 끊긴 생성을 이어서 한다."""
        for interview_id in self._store.list_ids():
            data = self._store.load(interview_id)
            if data is None or data.questions is not None:
                continue
            self._states[interview_id] = _PipelineState(phase="generating", pct=95)
            threading.Thread(
                target=self._recover_generation, args=(interview_id, data), daemon=True
            ).start()

    def _recover_generation(self, interview_id: str, data: InterviewData) -> None:
        try:
            self._run_generation(interview_id, data)
        except Exception:
            logger.exception("질문 생성 복원 실패 (interview=%s)", interview_id)
            self._states[interview_id].phase = "failed"
