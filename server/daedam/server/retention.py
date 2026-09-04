"""녹음 보관 정책 — 오래된 판의 미디어를 지운다.

20분 면접 한 판이 약 160MB(음성 76 · 영상 56~80 · 스틸 6)라 51GB VM이면
300판쯤에서 찬다. 전사·피드백은 데이터베이스에 남기고 **재생·영상·스틸만**
지운다 — 리포트의 글은 그대로 읽히고, 다시 듣기·다시 보기만 빠진다.

`RECORDING_RETENTION_DAYS`로 켠다. 비우면 지우지 않는다(개발 기본). 얼마나
보관할지는 개인정보처리방침에 적는 값이라 운영자가 정한다 — 코드가 기본값을
정하면 방침과 어긋난 채 지워진다.

피드백이 아직 없는 판은 건드리지 않는다. 재기동 복구(`evaluation._recover`)가
그 판의 wav를 읽어 리포트를 만들어야 한다.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, datetime, timedelta

from daedam.eval.expression import FRAMES_DIR

from .store import InterviewStore, has_answer

logger = logging.getLogger(__name__)

#: 판 디렉터리에서 지우는 파일. 전사 작업 파일(transcript.json)과 판독 원값
#: (vlm.json)은 작아서 둔다 — 다시 판독할 근거다.
_MEDIA_FILES = ("mic.pcm", "mic.wav", "cam.webm")

#: 하루에 한 번. 판이 하루 사이에 상한을 넘길 만큼 쌓이지는 않는다.
_INTERVAL_S = 24 * 3600


def purge_old_recordings(
    store: InterviewStore, days: int, now: datetime | None = None
) -> tuple[int, int]:
    """`days`일보다 오래전에 끝난 판의 미디어를 지운다.

    Returns:
        (지운 판 수, 비운 바이트 수)
    """
    cutoff = (now or datetime.now(UTC)) - timedelta(days=days)
    purged = 0
    freed = 0
    for record in store.sessions_ended_before(cutoff):
        # 리포트가 만들어졌거나, 만들 것이 없는(답변 없는) 판만.
        if record.feedback is None and has_answer(record.transcript):
            continue
        directory = store.session_directory(record.application_id, record.id)
        removed = 0
        for name in _MEDIA_FILES:
            path = directory / name
            if path.exists():
                removed += path.stat().st_size
                path.unlink()
        frames = directory / FRAMES_DIR
        if frames.is_dir():
            for frame in frames.iterdir():
                removed += frame.stat().st_size
                frame.unlink()
            frames.rmdir()
        if removed:
            purged += 1
            freed += removed
    return purged, freed


def start_retention_timer(store: InterviewStore, days: int) -> threading.Thread:
    """기동 직후 한 번, 그 뒤 하루에 한 번 지운다. 데몬 스레드라 종료를 막지 않는다."""

    def loop() -> None:
        while True:
            try:
                purged, freed = purge_old_recordings(store, days)
                if purged:
                    logger.info(
                        "보관 기한(%d일) 지난 녹음 정리: %d판, %.0fMB",
                        days, purged, freed / 1e6,
                    )
            except Exception:
                logger.exception("녹음 정리 실패 — 다음 주기에 다시 시도합니다")
            time.sleep(_INTERVAL_S)

    thread = threading.Thread(target=loop, name="retention", daemon=True)
    thread.start()
    return thread
