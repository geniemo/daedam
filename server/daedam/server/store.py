"""면접 준비 데이터 파일 저장소.

면접(카드) id마다 디렉터리 하나에 JSON으로 저장한다. 단일 사용자 로컬
앱이라 파일이 곧 데이터베이스다 — 동시 쓰기·질의·관계가 없고, 데모 전에
리포트나 질문을 에디터로 손질하는 워크플로에는 파일이 맞다. 전환 트리거
(동시 사용자, 목록 질의, 다중 인스턴스 배포)가 실제로 오면 이 클래스
인터페이스 뒤에서 SQLite로 갈아 끼운다.

리서치는 작업당 $1~7·수십 분이라, 여기 저장된 결과가 서버 재시작 후에도
남는 것이 "매주 데모 때 리서치를 다시 돌리지 않는다"는 요구의 근거다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: 면접 id 허용 형식. URL 경로 조각으로 들어오므로 디렉터리 탈출을 막는다.
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass(frozen=True)
class InterviewData:
    """면접 하나의 준비 데이터 묶음."""

    company: str
    role: str
    application: list[dict[str, Any]]
    report: list[dict[str, Any]]
    uncertain: list[dict[str, Any]]
    questions: list[dict[str, Any]] | None = None


class FileInterviewStore:
    """`{root}/{면접 id}/*.json` 구조의 저장소."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def save(
        self,
        interview_id: str,
        *,
        company: str,
        role: str,
        application: list[dict[str, Any]],
        report: list[dict[str, Any]],
        uncertain: list[dict[str, Any]],
    ) -> None:
        """리서치 완료 시점의 준비 데이터를 저장한다. 질문은 아직 없다."""
        directory = self._directory(interview_id)
        directory.mkdir(parents=True, exist_ok=True)
        self._write(directory / "meta.json", {"company": company, "role": role})
        self._write(directory / "application.json", application)
        self._write(directory / "report.json", report)
        self._write(directory / "uncertain.json", uncertain)

    def save_questions(
        self, interview_id: str, questions: list[dict[str, Any]]
    ) -> None:
        """생성된 질문 풀을 저장한다. 검토 후 재생성하면 덮어쓴다."""
        self._write(self._directory(interview_id) / "questions.json", questions)

    def save_report(self, interview_id: str, report: list[dict[str, Any]]) -> None:
        """검토·정정이 반영된 리포트로 교체한다."""
        self._write(self._directory(interview_id) / "report.json", report)

    def load(self, interview_id: str) -> InterviewData | None:
        """준비 데이터를 읽는다. 저장된 적 없거나 id 형식이 어긋나면 None.

        id는 URL에서 오므로, 여기서는 예외 대신 None — 조회 경로에서 이상한
        id는 "없는 면접"과 같은 404로 끝나야 한다. 쓰기는 여전히 거부한다.
        """
        if not _SAFE_ID.match(interview_id):
            return None
        directory = self._directory(interview_id)
        meta_path = directory / "meta.json"
        if not meta_path.exists():
            return None
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        questions_path = directory / "questions.json"
        return InterviewData(
            company=meta["company"],
            role=meta["role"],
            application=json.loads(
                (directory / "application.json").read_text(encoding="utf-8")
            ),
            report=json.loads((directory / "report.json").read_text(encoding="utf-8")),
            uncertain=json.loads(
                (directory / "uncertain.json").read_text(encoding="utf-8")
            ),
            questions=(
                json.loads(questions_path.read_text(encoding="utf-8"))
                if questions_path.exists()
                else None
            ),
        )

    def list_ids(self) -> list[str]:
        """저장된 면접 id 목록. 부팅 시 복원 스캔에 쓴다."""
        if not self._root.exists():
            return []
        return sorted(
            path.name for path in self._root.iterdir() if (path / "meta.json").exists()
        )

    def _directory(self, interview_id: str) -> Path:
        if not _SAFE_ID.match(interview_id):
            raise ValueError(f"허용되지 않는 면접 id: {interview_id!r}")
        return self._root / interview_id

    @staticmethod
    def _write(path: Path, payload: Any) -> None:
        # 임시 파일에 쓰고 rename — 쓰다 죽어도 반쪽짜리 JSON이 남지 않는다.
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(path)
