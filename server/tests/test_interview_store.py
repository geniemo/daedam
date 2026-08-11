"""면접 준비 데이터 파일 저장소 테스트."""

from pathlib import Path

import pytest

from daedam.server.store import FileInterviewStore

REPORT = [{"title": "개요", "blocks": [{"type": "p", "text": "본문"}]}]
APPLICATION = [{"part": "자소서", "items": [{"title": "지원동기", "body": "본문"}]}]
UNCERTAIN = [{"si": 0, "bi": 0, "title": "확인", "reason": "근거 부족"}]
QUESTIONS = [{"id": "q-0-0", "stage": 0, "text": "질문?", "priority": 1, "tags": ["태그"]}]


def _store(tmp_path: Path) -> FileInterviewStore:
    return FileInterviewStore(tmp_path / "data")


def _save(store: FileInterviewStore, interview_id: str = "abc") -> None:
    store.save(
        interview_id,
        company="한결물류",
        role="데이터 엔지니어",
        application=APPLICATION,
        report=REPORT,
        uncertain=UNCERTAIN,
    )


def test_저장하고_그대로_읽는다(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _save(store)

    data = store.load("abc")
    assert data.company == "한결물류" and data.role == "데이터 엔지니어"
    assert data.report == REPORT and data.application == APPLICATION
    assert data.uncertain == UNCERTAIN
    assert data.questions is None  # 질문은 생성 뒤에 온다


def test_질문은_나중에_붙는다(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _save(store)
    store.save_questions("abc", QUESTIONS)
    assert store.load("abc").questions == QUESTIONS


def test_검토된_리포트로_교체된다(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _save(store)
    corrected = [{"title": "개요", "blocks": [{"type": "p", "text": "정정된 본문"}]}]
    store.save_report("abc", corrected)
    assert store.load("abc").report == corrected


def test_저장된_적_없으면_None(tmp_path: Path) -> None:
    assert _store(tmp_path).load("없는것") is None


def test_저장된_면접_id_목록(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _save(store, "b")
    _save(store, "a")
    assert store.list_ids() == ["a", "b"]


def test_경로_탈출_id는_차단된다(tmp_path: Path) -> None:
    """면접 id는 URL에서 오므로 디렉터리 탈출을 막아야 한다.

    조회는 조용히 None(→404), 쓰기는 예외 — 어느 쪽도 파일시스템에 닿지 않는다.
    """
    store = _store(tmp_path)
    assert store.load("../../etc/passwd") is None
    with pytest.raises(ValueError, match="허용되지 않는"):
        store.save_questions("../../etc/passwd", QUESTIONS)