"""면접 조회·검토 라우트.

  GET /api/interviews             — 저장소에 있는 면접 목록 (최근 저장 순)
  GET /api/interviews/{id}        — 리포트를 포함한 면접 하나
  PUT /api/interviews/{id}/report — 검토로 고친 리포트 저장 + 질문 재생성
  GET /api/interviews/{id}/feedback — 면접이 끝난 뒤의 피드백 (없으면 상태만)

프론트가 자기 메모리에 카드를 들고 있으면 새로고침에 사라지고, 준비 데이터가
없는 면접을 시작하려다 브리지에서 거절당한다. 목록의 진실은 파일 저장소다 —
리서치가 작업당 $1~7·수십 분이라 그 결과가 남아 있는 것이 곧 "매주 데모 때
다시 돌리지 않는다"는 요구다(`store.py` 첫 줄).

검토가 리포트 원문을 고치는 이유: 질문 생성의 입력이 리포트다. 원문은 그대로
두고 주석만 쌓으면 사용자가 고친 것과 질문에 들어가는 것이 갈린다.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .preparation import InterviewPreparation
from .store import FileInterviewStore


class ReportUpdate(BaseModel):
    """검토가 끝난 리포트. 형태는 `DocSection` 목록 그대로다."""

    report: list[dict[str, Any]] = Field(default_factory=list)


def create_interviews_router(
    store: FileInterviewStore,
    preparation: InterviewPreparation,
    evaluation: Any = None,
) -> APIRouter:
    """면접 조회·검토 라우터를 만든다.

    Args:
        store: 준비 데이터 파일 저장소.
        preparation: 리포트가 바뀌면 질문을 다시 뽑는 오케스트레이터.
        evaluation: 면접 뒤 피드백을 만드는 오케스트레이터. None이면 피드백
            조회가 늘 absent를 돌려준다(테스트).

    Returns:
        /api/interviews 라우터.
    """
    router = APIRouter(prefix="/api/interviews", tags=["interviews"])

    @router.get("")
    def list_interviews() -> list[dict[str, Any]]:
        """준비된 면접 목록. ready가 참이면 질문까지 만들어져 시작할 수 있다."""
        items: list[dict[str, Any]] = []
        for interview_id in store.list_ids():
            data = store.load(interview_id)
            if data is None:
                continue
            items.append(
                {
                    "id": interview_id,
                    "company": data.company,
                    "role": data.role,
                    # 질문 풀까지 있어야 면접을 시작할 수 있다 — 브리지가 그것으로
                    # 시작 가능 여부를 판정하므로 화면도 같은 기준을 쓴다.
                    "ready": data.questions is not None,
                    "savedAt": store.saved_at(interview_id),
                }
            )
        # 방금 등록한 면접이 맨 앞에 오게 한다.
        items.sort(key=lambda item: item["savedAt"], reverse=True)
        return items

    @router.get("/{interview_id}")
    def get_interview(interview_id: str) -> dict[str, Any]:
        """검토 화면이 읽을 면접 하나 — 리포트 원문까지."""
        data = store.load(interview_id)
        if data is None:
            raise HTTPException(status_code=404, detail="면접이 없습니다")
        return {
            "id": interview_id,
            "company": data.company,
            "role": data.role,
            "report": data.report,
            "uncertain": data.uncertain,
            "ready": data.questions is not None,
        }

    @router.put("/{interview_id}/report", status_code=202)
    def update_report(interview_id: str, update: ReportUpdate) -> dict[str, bool]:
        """고친 리포트를 저장하고 질문을 다시 뽑는다.

        202인 이유: 저장은 끝났지만 질문 생성은 워커에서 이어진다. 화면은
        기존 진행률 폴링으로 완료를 기다린다.
        """
        if store.load(interview_id) is None:
            raise HTTPException(status_code=404, detail="면접이 없습니다")
        store.save_report(interview_id, update.report)
        return {"regenerating": preparation.regenerate(interview_id)}

    @router.get("/{interview_id}/feedback")
    def get_feedback(interview_id: str) -> dict[str, Any]:
        """분석 화면이 기다리며 부르고, 리포트 화면이 결과를 읽는다.

        상태는 넷이다. running은 만드는 중, done이면 feedback이 실려 온다.
        failed는 만들다 실패한 것이고, absent는 아직 면접을 안 했다는 뜻이다 —
        실패와 미실행을 같은 값으로 두면 화면이 무엇을 말할지 정할 수 없다.
        """
        if store.load(interview_id) is None:
            raise HTTPException(status_code=404, detail="면접이 없습니다")
        if evaluation is None:
            return {"status": "absent"}
        status = evaluation.status(interview_id)
        payload: dict[str, Any] = {"status": status.state}
        if status.feedback is not None:
            payload["feedback"] = status.feedback
        return payload

    return router
