"""면접 조회·검토 라우트.

  GET /api/interviews             — 내 면접 목록 (최근에 손댄 순)
  GET /api/interviews/{id}        — 리포트와 면접 이력을 포함한 면접 하나
  PUT /api/interviews/{id}/report — 검토로 고친 리포트 저장 + 질문 재생성
  GET /api/interviews/{id}/sessions — 면접 이력
  GET /api/interviews/{id}/feedback — 면접 한 판의 피드백
  GET /api/interviews/{id}/audio    — 면접 한 판의 지원자 음성

프론트가 자기 메모리에 카드를 들고 있으면 새로고침에 사라지고, 준비 데이터가
없는 면접을 시작하려다 브리지에서 거절당한다. 목록의 진실은 저장소다 —
리서치가 작업당 $1~3·10~15분이라 그 결과가 남아 있는 것이 곧 "다시 돌리지
않는다"는 요구다.

**피드백과 녹음은 면접 한 판에 속한다.** 같은 준비 데이터로 여러 번 면접할 수
있으므로 `?session=`으로 어느 판인지 고르고, 생략하면 가장 최근 판이다 —
면접을 막 마친 화면이 원하는 것이 그것이다.

검토가 리포트 원문을 고치는 이유: 질문 생성의 입력이 리포트다. 원문은 그대로
두고 주석만 쌓으면 사용자가 고친 것과 질문에 들어가는 것이 갈린다.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .accounts import Accounts
from .preparation import InterviewPreparation
from .store import InterviewStore, SessionSummary


class ReportUpdate(BaseModel):
    """검토가 끝난 리포트. 형태는 `DocSection` 목록 그대로다."""

    report: list[dict[str, Any]] = Field(default_factory=list)


def _session_payload(summary: SessionSummary) -> dict[str, Any]:
    return {
        "id": summary.id,
        "startedAt": summary.started_at.isoformat(),
        "endedAt": None if summary.ended_at is None else summary.ended_at.isoformat(),
        "score": summary.score,
        "hasFeedback": summary.has_feedback,
    }


def create_interviews_router(
    store: InterviewStore,
    preparation: InterviewPreparation,
    accounts: Accounts,
    evaluation: Any = None,
) -> APIRouter:
    """면접 조회·검토 라우터를 만든다.

    Args:
        store: 준비 데이터·면접 기록 저장소.
        preparation: 리포트가 바뀌면 질문을 다시 뽑는 오케스트레이터.
        accounts: 요청의 사용자를 알려 준다 — 목록이 그 사용자의 것으로 좁혀진다.
        evaluation: 면접 뒤 피드백을 만드는 오케스트레이터. None이면 피드백
            조회가 늘 absent를 돌려준다(테스트).

    Returns:
        /api/interviews 라우터.
    """
    router = APIRouter(prefix="/api/interviews", tags=["interviews"])

    def owned(interview_id: str, user_id: str) -> None:
        """내 것이 아니면 404.

        403이 아닌 이유: 남의 면접이 존재한다는 사실 자체를 흘리지 않는다.
        id를 넣어 보는 것만으로 "있다/없다"를 알 수 있으면 안 된다.
        """
        if store.owner_of(interview_id) != user_id:
            raise HTTPException(status_code=404, detail="면접이 없습니다")

    def resolve_session(interview_id: str, session: str | None) -> str:
        """어느 판인가. 생략하면 가장 최근 판이다."""
        if session is not None:
            record = store.load_session(session)
            if record is None or record.application_id != interview_id:
                raise HTTPException(status_code=404, detail="면접 기록이 없습니다")
            return session
        latest = store.latest_session(interview_id)
        if latest is None:
            raise HTTPException(status_code=404, detail="면접 기록이 없습니다")
        return latest.id

    @router.get("")
    def list_interviews(
        user_id: str = Depends(accounts.current_user_id),
    ) -> list[dict[str, Any]]:
        """준비된 면접 목록. ready가 참이면 질문까지 만들어져 시작할 수 있다."""
        return [
            {
                "id": item.id,
                "company": item.company,
                "role": item.role,
                # 질문 풀까지 있어야 면접을 시작할 수 있다 — 브리지가 그것으로
                # 시작 가능 여부를 판정하므로 화면도 같은 기준을 쓴다.
                "ready": item.ready,
                # 가장 최근 면접의 점수. null인 이유가 둘이라(분석 전 / 채점할
                # 답변이 없었음) 화면이 가릴 수 있게 analyzed를 같이 보낸다.
                "score": item.latest_score,
                "analyzed": item.latest_analyzed,
                # 몇 번 봤는가. 0이면 아직 한 번도 안 본 면접이다.
                "interviewCount": item.interview_count,
                "savedAt": item.updated_at.timestamp(),
            }
            for item in store.list_for_user(user_id)
        ]

    @router.get("/{interview_id}")
    def get_interview(
        interview_id: str, user_id: str = Depends(accounts.current_user_id)
    ) -> dict[str, Any]:
        """검토 화면이 읽을 면접 하나 — 리포트 원문과 면접 이력까지."""
        owned(interview_id, user_id)
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
            "sessions": [
                _session_payload(item) for item in store.list_sessions(interview_id)
            ],
        }

    @router.put("/{interview_id}/report", status_code=202)
    def update_report(
        interview_id: str,
        update: ReportUpdate,
        user_id: str = Depends(accounts.current_user_id),
    ) -> dict[str, bool]:
        """고친 리포트를 저장하고 질문을 다시 뽑는다.

        202인 이유: 저장은 끝났지만 질문 생성은 워커에서 이어진다. 화면은
        기존 진행률 폴링으로 완료를 기다린다.
        """
        owned(interview_id, user_id)
        store.save_report(interview_id, update.report)
        return {"regenerating": preparation.regenerate(interview_id)}

    @router.get("/{interview_id}/sessions")
    def list_sessions(
        interview_id: str, user_id: str = Depends(accounts.current_user_id)
    ) -> list[dict[str, Any]]:
        """면접 이력 — 최근 판이 앞에 온다."""
        owned(interview_id, user_id)
        return [_session_payload(item) for item in store.list_sessions(interview_id)]

    @router.get("/{interview_id}/feedback")
    def get_feedback(
        interview_id: str,
        session: str | None = None,
        user_id: str = Depends(accounts.current_user_id),
    ) -> dict[str, Any]:
        """분석 화면이 기다리며 부르고, 리포트 화면이 결과를 읽는다.

        상태는 넷이다. running은 만드는 중, done이면 feedback이 실려 온다.
        failed는 만들다 실패한 것이고, absent는 아직 면접을 안 했다는 뜻이다 —
        실패와 미실행을 같은 값으로 두면 화면이 무엇을 말할지 정할 수 없다.
        """
        owned(interview_id, user_id)
        latest = store.latest_session(interview_id)
        if latest is None:
            # 한 번도 면접하지 않았다. 404가 아니라 absent다 — 면접은 존재하고
            # 아직 안 봤을 뿐이다.
            return {"status": "absent"}
        session_id = resolve_session(interview_id, session)
        if evaluation is None:
            return {"status": "absent"}
        status = evaluation.status(session_id)
        payload: dict[str, Any] = {"status": status.state, "sessionId": session_id}
        if status.feedback is not None:
            payload["feedback"] = status.feedback
        return payload

    @router.get("/{interview_id}/audio")
    def get_audio(
        interview_id: str,
        session: str | None = None,
        user_id: str = Depends(accounts.current_user_id),
    ) -> FileResponse:
        """면접에서 녹음된 지원자 음성.

        리포트가 답변마다 구간을 지정해 재생한다. FileResponse가 Range 요청을
        받아 주므로 20분짜리를 통째로 내려받지 않고 그 구간만 가져간다
        (starlette/responses.py FileResponse — accept-ranges: bytes).
        """
        owned(interview_id, user_id)
        session_id = resolve_session(interview_id, session)
        path = store.session_directory(interview_id, session_id) / "mic.wav"
        if not path.exists():
            raise HTTPException(status_code=404, detail="녹음이 없습니다")
        return FileResponse(path, media_type="audio/wav")

    return router
