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

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from daedam.eval import expression

from .accounts import Accounts
from .credits import Credits
from .preparation import InterviewPreparation
from .store import InterviewStore, SessionSummary


#: 웹캠 녹화 파일 이름. 세션 디렉터리에서 mic.wav 옆에 놓인다.
_VIDEO_NAME = "cam.webm"

#: 녹화가 시작된 시점의 면접 경과 초를 적어 두는 곳.
#:
#: 답변 구간(`voice.answers[].startS`)은 서버가 받은 오디오 바이트로 센 시각이고,
#: 영상의 0초는 녹화가 시작된 순간이다. **원점이 다르므로** 이 값을 빼야 리포트가
#: 답변 위치로 정확히 감는다. 컬럼 대신 파일로 두는 것은 마이그레이션 없이 영상과
#: 생사를 같이하게 하려는 것이다 — 영상을 지우면 이것도 같이 지워진다.
_VIDEO_START_NAME = "cam.start"

#: 스냅샷 디렉터리 이름은 판독하는 쪽(eval/expression.py)이 소유한다 —
#: 올리는 곳과 읽는 곳이 서로 다른 이름을 보게 되면 판독이 조용히 빈다.
_FRAMES_DIR = expression.FRAMES_DIR

#: 스냅샷 한 장의 상한. 320×240 JPEG(품질 0.8)이 15KB 안팎이라 넉넉하다.
_FRAME_MAX = 200 * 1024

#: 한 판의 장수 상한. 3초당 한 장이면 20분이 400장이다 — 두 배가 넘는 값이라
#: 여기 걸리는 것은 우리 화면이 아니다.
_FRAMES_COUNT_MAX = 900

#: 업로드 조각 하나의 상한. 640×480 15fps에서 5초 조각이 300KB 안팎이라
#: 넉넉하다. 이걸 넘는 요청은 우리 클라이언트가 보낸 것이 아니다.
_VIDEO_CHUNK_MAX = 4 * 1024 * 1024

#: 한 판 영상의 상한. 20분이 60MB 안팎이므로 세 배 여유다. 디스크가 51GB뿐이라
#: 상한이 없으면 한 사람이 남의 면접 자리를 다 먹는다.
_VIDEO_MAX = 200 * 1024 * 1024


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


def _history(store: InterviewStore, application_id: str) -> list[dict[str, Any]]:
    """화면에 보이는 면접 이력 — 최근 회차가 앞에 온다.

    **지원자가 한 마디도 안 한 판은 뺀다.** 시작만 하고 나온 것은 "면접을
    봤다"가 아니다. 회차 번호도 이 목록에서 매겨지므로, 빼지 않으면 한 적 없는
    3회차가 생긴다.

    기록 자체는 지우지 않는다 — 크레딧을 되돌린 근거이고, 답변이 없을 뿐
    녹음은 남아 있다(전사가 실패한 것일 수도 있다).
    """
    return [
        _session_payload(item)
        for item in store.list_sessions(application_id)
        if item.has_answer
    ]


def create_interviews_router(
    store: InterviewStore,
    preparation: InterviewPreparation,
    accounts: Accounts,
    evaluation: Any = None,
    credits: Credits | None = None,
) -> APIRouter:
    """면접 조회·검토 라우터를 만든다.

    Args:
        store: 준비 데이터·면접 기록 저장소.
        preparation: 리포트가 바뀌면 질문을 다시 뽑는 오케스트레이터.
        accounts: 요청의 사용자를 알려 준다 — 목록이 그 사용자의 것으로 좁혀진다.
        evaluation: 면접 뒤 피드백을 만드는 오케스트레이터. None이면 피드백
            조회가 늘 absent를 돌려준다(테스트).
        credits: 원장. 아무 말도 없이 끝난 면접의 크레딧이 되돌려졌는지 화면에
            알려 주는 데만 쓴다. None이면 그 사실을 싣지 않는다.

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
            "sessions": _history(store, interview_id),
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
        """면접 이력 — 최근 회차가 앞에 온다."""
        owned(interview_id, user_id)
        return _history(store, interview_id)

    @router.get("/{interview_id}/feedback")
    def get_feedback(
        interview_id: str,
        session: str | None = None,
        user_id: str = Depends(accounts.current_user_id),
    ) -> dict[str, Any]:
        """분석 화면이 기다리며 부르고, 리포트 화면이 결과를 읽는다.

        상태는 다섯이다. running은 만드는 중, done이면 feedback이 실려 온다.
        failed는 만들다 실패한 것, silent는 면접은 했는데 한 마디도 남기지 않아
        만들 것이 없는 것, absent는 아직 면접을 안 했다는 뜻이다 — 넷을 한
        값으로 뭉치면 화면이 무엇을 말할지 정할 수 없다.
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
        # 웹캠 녹화가 있으면 리포트가 답변별로 되감아 보여준다. 원점이 달라
        # 그대로 쓰면 어긋나므로 시작 시각을 함께 싣는다.
        directory = store.session_directory(interview_id, session_id)
        if (directory / _VIDEO_NAME).exists():
            payload["hasVideo"] = True
            start_file = directory / _VIDEO_START_NAME
            try:
                payload["videoStartS"] = float(start_file.read_text())
            except (OSError, ValueError):
                # 원점을 모르면 0으로 둔다 — 어긋나더라도 전체 재생은 된다.
                payload["videoStartS"] = 0.0
        if status.state == "silent" and credits is not None:
            # 아무 말도 못 한 면접에서 사용자가 가장 먼저 묻는 것이 크레딧이다.
            # 되돌리는 경로가 하나가 아니라(브리지의 무응답 환불) 짐작하지 않고
            # 원장을 본다 — 돈 이야기는 틀리면 안 된다.
            payload["refunded"] = credits.refunded(user_id, session_id)
        return payload

    @router.post("/{interview_id}/video", status_code=204)
    async def append_video(
        interview_id: str,
        request: Request,
        session: str | None = None,
        startS: float | None = None,
        user_id: str = Depends(accounts.current_user_id),
    ) -> None:
        """웹캠 녹화 조각을 이어 붙인다.

        면접용 WebSocket이 아니라 별도 HTTP로 받는다 — 영상은 곁가지라
        업로드가 실패해도 면접이 흔들리면 안 된다. 소켓에 얹으면 한 채널에
        두 종류의 바이트가 섞이고, 재접속 때 영상까지 같이 끊긴다.

        **순서대로 이어 붙는 것이 전부다.** MediaRecorder는 첫 조각에만 WebM
        헤더를 넣으므로, 중간이 비면 파일 전체가 깨진다. 그래서 클라이언트가
        한 번에 하나씩 순서대로 보내고, 실패하면 건너뛰지 않고 멈춘다 —
        잘린 파일은 재생되지만 구멍 난 파일은 안 된다.
        """
        owned(interview_id, user_id)
        session_id = resolve_session(interview_id, session)
        chunk = await request.body()
        if not chunk:
            return
        if len(chunk) > _VIDEO_CHUNK_MAX:
            raise HTTPException(status_code=413, detail="조각이 너무 큽니다")

        path = store.session_directory(interview_id, session_id) / _VIDEO_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        written = path.stat().st_size if path.exists() else 0
        if written + len(chunk) > _VIDEO_MAX:
            raise HTTPException(status_code=413, detail="녹화가 너무 깁니다")
        with path.open("ab") as handle:
            handle.write(chunk)

        # 원점은 첫 조각에만 실려 온다. 이미 적혀 있으면 덮지 않는다 —
        # 재접속으로 뒤늦게 온 첫 조각이 앞의 값을 밀어내면 안 된다.
        if startS is not None and written == 0:
            (path.parent / _VIDEO_START_NAME).write_text(f"{startS:.2f}")

    @router.post("/{interview_id}/frames", status_code=204)
    async def append_frame(
        interview_id: str,
        request: Request,
        at: float,
        session: str | None = None,
        user_id: str = Depends(accounts.current_user_id),
    ) -> None:
        """표정 판독용 스냅샷 한 장을 저장한다. 화면이 3초마다 보낸다.

        영상(cam.webm)이 이미 올라오는데 따로 받는 이유: 서버가 영상에서
        프레임을 뽑으려면 디코더(opencv급 의존성)가 필요하다. 화면은 프레임을
        이미 손에 들고 있으므로 찍는 쪽이 보내는 것이 싸다.

        `at`은 면접 경과 초 — 답변 구간과 같은 시계라, 분석이 답변별로 나눌
        열쇠다. **파일 이름이 곧 시각이다**(f00012.3.jpg). 별도 목록 파일이
        없으니 같은 장이 다시 와도 덮어쓸 뿐, 순서·중복 문제가 없다. 영상
        조각과 달리 한 장쯤 빠져도 구멍이 아니다 — 그래서 화면도 재시도 없이
        놓아 보낸다.
        """
        owned(interview_id, user_id)
        session_id = resolve_session(interview_id, session)
        if not 0 <= at < 24 * 3600:
            raise HTTPException(status_code=400, detail="시각이 이상합니다")
        body = await request.body()
        if not body:
            return
        if len(body) > _FRAME_MAX:
            raise HTTPException(status_code=413, detail="스냅샷이 너무 큽니다")

        directory = store.session_directory(interview_id, session_id) / _FRAMES_DIR
        directory.mkdir(parents=True, exist_ok=True)
        if len(list(directory.glob("*.jpg"))) >= _FRAMES_COUNT_MAX:
            raise HTTPException(status_code=413, detail="스냅샷이 너무 많습니다")
        # 07.1f: 1200.0초(20분)까지 자릿수가 같아 이름 정렬이 곧 시간 정렬이다.
        (directory / f"f{at:07.1f}.jpg").write_bytes(body)

    @router.get("/{interview_id}/video")
    def get_video(
        interview_id: str,
        session: str | None = None,
        user_id: str = Depends(accounts.current_user_id),
    ) -> FileResponse:
        """면접에서 녹화된 지원자 영상. 리포트가 되돌아보기용으로 재생한다."""
        owned(interview_id, user_id)
        session_id = resolve_session(interview_id, session)
        path = store.session_directory(interview_id, session_id) / _VIDEO_NAME
        if not path.exists():
            raise HTTPException(status_code=404, detail="녹화가 없습니다")
        return FileResponse(path, media_type="video/webm")

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
