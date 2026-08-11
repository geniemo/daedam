"""면접 준비 오케스트레이터 테스트.

워커 스레드가 실제로 돌므로 짧은 실시간(fixture 리서치 수십 ms)을 쓰고,
완료는 타임아웃 폴링으로 기다린다. 질문 생성은 대역 함수다 — Grok 실호출 0회.
"""

import time
from pathlib import Path

from daedam.research.service import FixtureResearch
from daedam.server.preparation import InterviewPreparation
from daedam.server.store import FileInterviewStore

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


def _stub_generate(**kwargs):
    return QUESTIONS


def _preparation(
    tmp_path: Path, duration_s: float = 0.01, generate=_stub_generate
) -> tuple[InterviewPreparation, FileInterviewStore]:
    store = FileInterviewStore(tmp_path / "data")
    preparation = InterviewPreparation(
        research=FixtureResearch(duration_s=duration_s),
        store=store,
        generate=generate,
        poll_interval_s=0.01,
    )
    return preparation, store


def _wait_until(condition, timeout_s: float = 3.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError("시간 안에 조건이 충족되지 않음")


def test_파이프라인이_등록부터_질문까지_완주한다(tmp_path: Path) -> None:
    preparation, store = _preparation(tmp_path)
    task_id = preparation.start("한결물류", "데이터 엔지니어", [])

    _wait_until(lambda: (s := preparation.status(task_id)) and s.state == "done")
    status = preparation.status(task_id)
    assert status.pct == 100 and status.report
    assert store.load(task_id).questions == QUESTIONS


def test_리서치_중에는_90_이하의_running(tmp_path: Path) -> None:
    preparation, _ = _preparation(tmp_path, duration_s=10)
    task_id = preparation.start("A", "B", [])

    status = preparation.status(task_id)
    assert status.state == "running" and status.pct <= 90


def test_생성_실패는_failed로_드러난다(tmp_path: Path) -> None:
    """폴백으로 뭉개지 않는다 — 크게 실패해야 준비 데이터 문제를 알아챈다."""

    def broken_generate(**kwargs):
        raise RuntimeError("생성 실패")

    preparation, _ = _preparation(tmp_path, generate=broken_generate)
    task_id = preparation.start("A", "B", [])

    _wait_until(lambda: (s := preparation.status(task_id)) and s.state == "failed")


def test_없는_작업은_None(tmp_path: Path) -> None:
    preparation, _ = _preparation(tmp_path)
    assert preparation.status("missing") is None


def test_재시작_후_완료된_면접은_파일에서_복원된다(tmp_path: Path) -> None:
    _, store = _preparation(tmp_path)
    store.save("survivor", **REPORT_ONLY_STATE)
    store.save_questions("survivor", QUESTIONS)

    restarted, _ = _preparation(tmp_path)  # 같은 데이터 디렉터리로 새 인스턴스
    status = restarted.status("survivor")
    assert status.state == "done" and status.report


def test_재시작_후_끊긴_생성은_이어서_한다(tmp_path: Path) -> None:
    """리서치 산출물은 저장됐는데 질문 전에 죽은 경우 — 생성만 재개된다."""
    _, store = _preparation(tmp_path)
    store.save("resumed", **REPORT_ONLY_STATE)

    restarted, store2 = _preparation(tmp_path)
    _wait_until(lambda: store2.load("resumed").questions is not None)
    assert restarted.status("resumed").state == "done"