"""면접 준비 오케스트레이터 — 리서치 → 저장 → 질문 생성 → 완료.

작업(면접)마다 전담 워커 스레드가 파이프라인을 완주한다. 브라우저 폴링은
전진과 무관한 순수 조회라, 사용자가 창을 닫아도 준비는 서버에서 계속된다 —
진행 화면의 안내 문구가 여기서 참이 된다.

pct는 백엔드가 진행률을 아는 경우에만 흐른다. fixture는 총 소요 시간을 알아
0~90(서비스 pct의 0.9배) → 95 → 100으로 가지만, live는 Deep Research가
진행률을 주지 않아 끝까지 None이다 — 그때 화면은 단계와 경과 시간만 보여준다.

완료의 증거는 메모리가 아니라 파일 저장소다 — 서버가 재시작돼도 저장된
면접은 done으로 복원되고, 생성 도중 끊겼다면 부팅 복원이 생성만 이어서
한다. 진행 중이던 리서치도 넘어간다: live 백엔드가 인터랙션 id를 파일에
남기므로, 부팅 복원이 그 작업을 이어받아 끝까지 기다린다.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Literal

from daedam.interview.generation import generate_question_pool
from daedam.interview.vocabulary import generate_vocabulary
from daedam.knowledge.chunk import chunks_from_application, chunks_from_report
from daedam.research.report import search_sections_from_report
from daedam.research.service import ResearchService, ResearchStatus

from .store import InterviewData, InterviewStore

logger = logging.getLogger(__name__)

#: 연속 조회 실패를 몇 번까지 견디는가. live 폴링 간격이 30초이므로 10번이면
#: 5분이다 — 그보다 오래 응답이 없으면 일시적인 문제가 아니다.
_POLL_STRIKES = 10


@dataclass
class _PipelineState:
    """워커가 갱신하고 status()가 읽기만 하는 진행 기록."""

    phase: Literal["researching", "generating", "failed"]
    #: 리서치 백엔드가 진행률을 아는 경우에만 숫자. live는 모른다(None).
    pct: int | None
    #: 리서치가 지금까지 실제로 한 조사. 워커가 폴링하면서 갱신한다.
    activity: tuple[str, ...] = ()
    #: 관측된 현재 단계.
    label: str = ""
    #: 워커가 마지막으로 받은 경과 초와, 그것을 받은 벽시계 시각. 워커는
    #: live에서 30초에 한 번만 도는데 화면은 1초마다 물어본다. 받은 값을 그대로
    #: 돌려주면 시계가 30초씩 튀므로, 읽을 때 그동안 흐른 시간을 더해 준다.
    elapsed_s: float = 0.0
    elapsed_at: float = 0.0


class InterviewPreparation:
    """리서치 서비스와 질문 생성을 하나의 준비 파이프라인으로 묶는다."""

    def __init__(
        self,
        research: ResearchService,
        store: InterviewStore,
        generate: Callable[..., list[dict[str, Any]]] = generate_question_pool,
        extract_vocabulary: Callable[..., list[str]] = generate_vocabulary,
        poll_interval_s: float = 1.0,
        on_failed: Callable[[str, str], None] | None = None,
    ) -> None:
        """
        Args:
            research: fixture 또는 live 리서치 백엔드.
            store: 준비 데이터 저장소.
            generate: 질문 생성 함수. 테스트가 대역을 주입한다.
            extract_vocabulary: 전사 어휘 추출 함수. 테스트가 대역을 주입한다.
            poll_interval_s: 워커가 리서치 완료를 확인하는 간격. live에서는
                30초쯤으로 늘려 폴링 API 낭비를 없앤다.
            on_failed: 준비가 실패했을 때 `(user_id, 준비 id)`로 불린다.
                크레딧을 되돌리는 자리 — 실패한 작업에 요금을 물리면 다시
                시도할 수도 없다. 파이프라인이 크레딧을 직접 알지는 않는다.
        """
        self._research = research
        self._store = store
        self._generate = generate
        self._extract_vocabulary = extract_vocabulary
        self._poll_interval_s = poll_interval_s
        self._on_failed = on_failed
        self._states: dict[str, _PipelineState] = {}
        self._recover()

    def start(
        self,
        company: str,
        role: str,
        application: list[dict[str, Any]],
        posting: str = "",
        name: str = "",
        *,
        user_id: str,
    ) -> str:
        # posting은 여기서만 쓰인다 — 리서치 프롬프트에 실려 나가고, 이후
        # 재개·재생성 경로는 이미 만들어진 인터랙션을 따라가므로 필요 없다.
        task_id = self._research.start(company, role, application, posting)
        # 등록되는 순간 파일에 남긴다. 리서치가 끝나야 저장하면 그동안 홈 목록에
        # 이 면접이 없어서, 방금 등록한 카드가 새로고침에 사라진다. 리포트는
        # 아직 비어 있고, 그 비어 있음이 "리서치 진행 중"의 표시다.
        self._store.save(
            task_id,
            user_id=user_id,
            company=company,
            role=role,
            application=application,
            report=[],
            uncertain=[],
            name=name,
        )
        # pct=None으로 시작한다. live는 첫 폴링이 30초 뒤라, 0으로 두면 그동안
        # 화면에 0%가 떠 있는다 — 백엔드가 진행률을 아는지도 모르는 시점이다.
        # elapsed_at을 지금으로 잡아 둔다. live는 첫 폴링이 30초 뒤라, 비워
        # 두면 그동안 화면의 경과 시간이 0에 멈춰 있는다.
        self._states[task_id] = _PipelineState(
            phase="researching", pct=None, elapsed_at=time.time()
        )
        # 이 면접 전담 워커 — 브라우저가 닫혀도 파이프라인은 여기서 완주한다.
        threading.Thread(
            target=self._run_pipeline,
            args=(task_id, company, role, application, name, user_id),
            daemon=True,
        ).start()
        return task_id

    def regenerate(self, interview_id: str) -> bool:
        """검토로 고쳐진 리포트에서 질문 풀을 다시 뽑는다.

        질문은 리포트를 근거로 만들어졌으므로, 사용자가 사실을 고치면 그 질문은
        낡은 근거 위에 서 있다. 저장된 리포트가 없으면 할 일이 없다.

        Returns:
            생성을 시작했으면 True.
        """
        data = self._store.load(interview_id)
        if data is None or not data.report:
            return False
        self._states[interview_id] = _PipelineState(
            phase="generating", pct=None, label="질문 뽑는 중"
        )
        threading.Thread(
            target=self._recover_generation, args=(interview_id, data), daemon=True
        ).start()
        return True

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
            # 저장은 됐는데 워커가 없다 — 재시작으로 리서치가 끊긴 면접이다.
            # 404로 두면 화면이 "없는 면접"으로 읽지만, 실제로는 등록됐고 진행이
            # 끊긴 것이라 실패로 알린다.
            return ResearchStatus(state="failed", pct=0) if stored else None
        if state.phase == "failed":
            return ResearchStatus(state="failed", pct=0)
        return ResearchStatus(
            state="running",
            pct=state.pct,
            activity=state.activity,
            phase=state.label,
            elapsed_s=(
                state.elapsed_s + (time.time() - state.elapsed_at)
                if state.elapsed_at
                else state.elapsed_s
            ),
        )

    def _run_pipeline(
        self,
        task_id: str,
        company: str,
        role: str,
        application: list[dict[str, Any]],
        name: str,
        user_id: str,
    ) -> None:
        state = self._states[task_id]
        try:
            # ① 리서치 완주 대기. 프론트의 1초 폴링과 무관하게 자기 속도로 묻는다.
            strikes = 0
            while True:
                try:
                    research = self._research.status(task_id)
                except Exception:
                    # 진행 중 조회는 이따금 400/403을 낸다(실측: 20~60분짜리
                    # 작업에서 한 번). 그 한 번을 리서치 실패로 단정하면 이미
                    # 돌고 있는 유료 작업을 버리게 된다 — 실제로 그렇게 버렸다.
                    # 작업은 서버가 잡고 있으므로 우리가 다시 물어보면 된다.
                    strikes += 1
                    logger.warning(
                        "리서치 조회 실패 %d/%d (interview=%s) — 다시 시도합니다",
                        strikes,
                        _POLL_STRIKES,
                        task_id,
                        exc_info=True,
                    )
                    if strikes >= _POLL_STRIKES:
                        raise
                    time.sleep(self._poll_interval_s)
                    continue
                strikes = 0

                if research is None or research.state == "failed":
                    self._fail(state, task_id, user_id)
                    return
                if research.state == "done":
                    break
                # 리서치 구간을 0~90에 배정한다. 백엔드가 진행률을 모르면
                # (live) 우리도 모른다 — 지어내지 않고 None을 그대로 통과시킨다.
                state.pct = None if research.pct is None else int(research.pct * 0.9)
                state.activity = research.activity
                state.label = research.phase
                state.elapsed_s = research.elapsed_s
                state.elapsed_at = time.time()
                time.sleep(self._poll_interval_s)

            # ② 산출물 저장 — 이 순간부터 서버가 죽어도 리서치를 잃지 않는다.
            self._store.save(
                task_id,
                user_id=user_id,
                company=company,
                role=role,
                application=application,
                report=research.report or [],
                uncertain=research.uncertain or [],
                name=name,
            )

            # ③ 질문 생성 — 화면의 "질문 준비" 단계가 실제로 이 구간이다.
            self._run_generation(task_id, self._store.load(task_id))
        except Exception:
            logger.exception("면접 준비 실패 (interview=%s)", task_id)
            self._fail(state, task_id, user_id)

    def _fail(self, state: _PipelineState, task_id: str, user_id: str) -> None:
        """준비가 실패했다. 상태를 남기고 크레딧을 되돌린다."""
        state.phase = "failed"
        if self._on_failed is not None and user_id:
            try:
                self._on_failed(user_id, task_id)
            except Exception:
                logger.exception("준비 실패 뒤처리 중 오류 (interview=%s)", task_id)

    def _run_generation(self, task_id: str, data: InterviewData) -> None:
        state = self._states[task_id]
        state.phase = "generating"
        # 퍼센트는 백엔드가 알 때만 쓴다. live는 리서치 진행률을 모르는데
        # 생성 단계에서만 95%를 띄우면 그 숫자가 어디서 왔는지 알 수 없다.
        state.pct = None if state.pct is None else 95
        state.label = "질문 뽑는 중"
        state.activity = state.activity + ("리서치를 마쳤습니다. 질문을 뽑고 있습니다",)
        questions = self._generate(
            company=data.company,
            role=data.role,
            report_chunks=chunks_from_report(search_sections_from_report(data.report)),
            application_chunks=chunks_from_application(data.application),
        )
        self._store.save_questions(task_id, questions)

        # ④ 전사 어휘 — 질문이 정해진 뒤라야 뽑을 수 있다. 면접관이 실제로 읽을
        # 문장이 추출의 입력이기 때문이다.
        #
        # 실패해도 준비는 성공이다. 질문은 이미 저장됐고 면접은 돌아간다 —
        # 어휘가 없으면 브리지가 규칙 폴백으로 만들어 전사 정확도만 낮아진다.
        # 여기서 터뜨리면 멀쩡한 질문 풀을 두고 준비가 실패로 남는다.
        try:
            vocabulary = self._extract_vocabulary(
                company=data.company,
                role=data.role,
                name=data.name,
                application=data.application,
                questions=questions,
            )
            self._store.save_vocabulary(task_id, vocabulary)
            logger.info("전사 어휘 %d개 (interview=%s)", len(vocabulary), task_id)
        except Exception:
            logger.exception("전사 어휘 추출 실패 (interview=%s) — 폴백으로 둡니다", task_id)

        del self._states[task_id]  # 완료 — 이제부터 파일이 진실을 말한다

    def _recover(self) -> None:
        """저장은 됐는데 질문이 없는 면접 — 재시작으로 끊긴 준비를 이어서 한다.

        두 갈래다. 리포트가 있으면 질문 생성만 남은 것이고, 비어 있으면 리서치가
        끝나기 전에 재시작된 것이다. 후자는 리서치 백엔드가 그 작업을 아직
        아는지에 달렸다 — live 백엔드는 인터랙션 id를 파일에 남기므로 이어서
        기다릴 수 있고, 모르면(fixture·기록 없음) 손대지 않는다. 리포트 없이
        질문을 만들면 근거 없는 질문 풀이 나온다.
        """
        for interview_id in self._store.list_ids():
            data = self._store.load(interview_id)
            if data is None or data.questions is not None:
                continue

            if not data.report:
                # 기동 중이라 여기서 터지면 서버가 아예 안 뜬다. 조회가 실패하면
                # 이번 기동에서는 이어받지 않고 넘어간다 — 기록은 파일에 남아
                # 있으므로 다음 기동에서 다시 시도한다.
                try:
                    running = self._research.status(interview_id)
                except Exception:
                    logger.exception(
                        "끊긴 리서치 상태를 확인하지 못했습니다 (interview=%s)",
                        interview_id,
                    )
                    continue
                if running is None:
                    continue
                logger.info("끊긴 리서치를 이어받습니다 (interview=%s)", interview_id)
                self._states[interview_id] = _PipelineState(
                    phase="researching", pct=None, elapsed_at=time.time()
                )
                threading.Thread(
                    target=self._run_pipeline,
                    args=(
                        interview_id,
                        data.company,
                        data.role,
                        data.application,
                        data.name,
                        # 복원은 이미 저장된 준비 데이터를 이어받는 것이라
                        # 주인은 그때 정해져 있다.
                        self._store.owner_of(interview_id) or "",
                    ),
                    daemon=True,
                ).start()
                continue

            self._states[interview_id] = _PipelineState(
                phase="generating", pct=None, label="질문 뽑는 중"
            )
            threading.Thread(
                target=self._recover_generation, args=(interview_id, data), daemon=True
            ).start()

    def _recover_generation(self, interview_id: str, data: InterviewData) -> None:
        try:
            self._run_generation(interview_id, data)
        except Exception:
            logger.exception("질문 생성 복원 실패 (interview=%s)", interview_id)
            self._states[interview_id].phase = "failed"
