"""면접 준비 오케스트레이터 테스트.

워커 스레드가 실제로 돌므로 짧은 실시간(fixture 리서치 수십 ms)을 쓰고,
완료는 타임아웃 폴링으로 기다린다. 질문 생성은 대역 함수다 — Grok 실호출 0회.
"""

import time
from pathlib import Path

from conftest import make_store

from daedam.research.service import FixtureResearch, ResearchStatus
from daedam.server.preparation import InterviewPreparation
from daedam.server.store import InterviewStore

REPORT_ONLY_STATE = dict(
    company="한결물류",
    role="데이터 엔지니어",
    application=[{"part": "자소서", "items": [{"title": "지원동기", "body": "본문"}]}],
    report=[{"title": "개요", "blocks": [{"type": "p", "text": "본문"}]}],
    uncertain=[],
)

QUESTIONS = [
    {"id": "q-0-0", "stage": 0, "text": "질문?", "priority": 1, "tags": ["태그"]}
]


VOCABULARY = ["한결물류", "산학협력"]


def _stub_generate(**kwargs):
    return QUESTIONS


def _stub_vocabulary(**kwargs):
    return VOCABULARY


def _preparation(
    tmp_path: Path,
    duration_s: float = 0.01,
    generate=_stub_generate,
    extract_vocabulary=_stub_vocabulary,
) -> tuple[InterviewPreparation, InterviewStore, str]:
    store, _, user_id = make_store(tmp_path / "data")
    preparation = InterviewPreparation(
        research=FixtureResearch(duration_s=duration_s),
        store=store,
        generate=generate,
        extract_vocabulary=extract_vocabulary,
        poll_interval_s=0.01,
    )
    return preparation, store, user_id


def _wait_until(condition, timeout_s: float = 3.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError("시간 안에 조건이 충족되지 않음")


def test_파이프라인이_등록부터_질문까지_완주한다(tmp_path: Path) -> None:
    preparation, store, user_id = _preparation(tmp_path)
    task_id = preparation.start("한결물류", "데이터 엔지니어", [], user_id=user_id)

    _wait_until(lambda: (s := preparation.status(task_id)) and s.state == "done")
    status = preparation.status(task_id)
    assert status.pct == 100 and status.report
    assert store.load(task_id).questions == QUESTIONS
    # 어휘도 준비 때 뽑아 둔다 — 면접 시작 경로에 LLM 호출을 두지 않기 위해서다.
    assert store.load(task_id).vocabulary == VOCABULARY


def test_어휘_추출이_실패해도_준비는_성공이다(tmp_path: Path) -> None:
    """질문은 이미 저장됐고 면접은 돌아간다 — 전사 정확도만 낮아진다."""

    def broken(**kwargs):
        raise RuntimeError("xAI 호출 실패")

    preparation, store, user_id = _preparation(tmp_path, extract_vocabulary=broken)
    task_id = preparation.start("한결물류", "데이터 엔지니어", [], user_id=user_id)

    _wait_until(lambda: (s := preparation.status(task_id)) and s.state == "done")
    assert store.load(task_id).questions == QUESTIONS
    assert store.load(task_id).vocabulary is None


def test_어휘_추출은_질문을_받는다(tmp_path: Path) -> None:
    """면접관이 실제로 읽을 문장이 추출의 입력이라 질문 뒤에 와야 한다."""
    seen: dict = {}

    def capture(**kwargs):
        seen.update(kwargs)
        return VOCABULARY

    preparation, _, user_id = _preparation(tmp_path, extract_vocabulary=capture)
    task_id = preparation.start("한결물류", "데이터 엔지니어", [], name="박지원", user_id=user_id)

    _wait_until(lambda: (s := preparation.status(task_id)) and s.state == "done")
    assert seen["questions"] == QUESTIONS
    assert seen["name"] == "박지원"


def test_리서치_중에는_90_이하의_running(tmp_path: Path) -> None:
    preparation, _, user_id = _preparation(tmp_path, duration_s=10)
    task_id = preparation.start("A", "B", [], user_id=user_id)

    status = preparation.status(task_id)
    assert status.state == "running" and status.pct <= 90


def test_생성_실패는_failed로_드러난다(tmp_path: Path) -> None:
    """폴백으로 뭉개지 않는다 — 크게 실패해야 준비 데이터 문제를 알아챈다."""

    def broken_generate(**kwargs):
        raise RuntimeError("생성 실패")

    preparation, _, user_id = _preparation(tmp_path, generate=broken_generate)
    task_id = preparation.start("A", "B", [], user_id=user_id)

    _wait_until(lambda: (s := preparation.status(task_id)) and s.state == "failed")


def test_없는_작업은_None(tmp_path: Path) -> None:
    preparation, _, user_id = _preparation(tmp_path)
    assert preparation.status("missing") is None


def test_재시작_후_완료된_면접은_파일에서_복원된다(tmp_path: Path) -> None:
    _, store, user_id = _preparation(tmp_path)
    store.save("survivor", user_id=user_id, **REPORT_ONLY_STATE)
    store.save_questions("survivor", QUESTIONS)

    restarted, _, _ = _preparation(tmp_path)  # 같은 데이터 디렉터리로 새 인스턴스
    status = restarted.status("survivor")
    assert status.state == "done" and status.report


def test_재시작_후_끊긴_생성은_이어서_한다(tmp_path: Path) -> None:
    """리서치 산출물은 저장됐는데 질문 전에 죽은 경우 — 생성만 재개된다."""
    _, store, user_id = _preparation(tmp_path)
    store.save("resumed", user_id=user_id, **REPORT_ONLY_STATE)

    restarted, store2, _ = _preparation(tmp_path)
    _wait_until(lambda: store2.load("resumed").questions is not None)
    assert restarted.status("resumed").state == "done"

# ── 폴링이 삐끗해도 돌고 있는 리서치를 버리지 않는다 ────────────────


class _FlakyResearch:
    """진행 중 조회가 이따금 터지는 백엔드. 실측에서 400을 한 번 냈다."""

    def __init__(self, fail_at: set[int]) -> None:
        self._fail_at = fail_at
        self._calls = 0

    def start(self, company, role, application, posting="") -> str:  # noqa: ANN001
        return "itx"

    def status(self, task_id: str):  # noqa: ANN201
        self._calls += 1
        if self._calls in self._fail_at:
            raise RuntimeError("Request contains an invalid argument.")
        if self._calls < 4:
            return ResearchStatus(state="running", pct=None)
        return ResearchStatus(state="done", pct=100, report=[{"title": "t", "blocks": []}], uncertain=[])


def test_조회가_한_번_실패해도_준비가_이어진다(tmp_path) -> None:
    """이 한 번을 실패로 단정하면 이미 돌고 있는 유료 작업을 통째로 버린다."""
    store, _, user_id = make_store(tmp_path)
    preparation = InterviewPreparation(
        research=_FlakyResearch(fail_at={2}),
        store=store,
        generate=lambda **_: [{"id": "q1", "stage": 0, "text": "질문", "priority": 1, "tags": []}],
        poll_interval_s=0.01,
    )
    task_id = preparation.start("컬리", "서비스기획", [], user_id=user_id)
    _wait_until(lambda: store.load(task_id) is not None and store.load(task_id).questions is not None)
    assert store.load(task_id).questions is not None


def test_조회가_계속_실패하면_결국_실패로_끝난다(tmp_path) -> None:
    store, _, user_id = make_store(tmp_path)
    preparation = InterviewPreparation(
        research=_FlakyResearch(fail_at=set(range(1, 40))),
        store=store,
        generate=lambda **_: [],
        poll_interval_s=0.001,
    )
    task_id = preparation.start("컬리", "서비스기획", [], user_id=user_id)
    _wait_until(lambda: preparation.status(task_id).state == "failed")
    assert preparation.status(task_id).state == "failed"
