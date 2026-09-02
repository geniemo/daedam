"""환경에서 오는 경로 몇 개.

앱 조립(`daedam.server.app`)과 마이그레이션(`alembic/env.py`)이 같은 값을
봐야 하는데, 둘은 서로를 import하지 않는다. 그 공통분모만 여기 둔다.
"""

from __future__ import annotations

import os
from pathlib import Path

#: 이 패키지가 설치된 서버 디렉터리 (= server/). `interviewer` 패키지와
#: `data/`가 여기 있다.
SERVER_DIR = Path(__file__).resolve().parents[1]


def data_root() -> Path:
    """면접 준비 데이터·녹음·데이터베이스 파일이 놓이는 곳.

    `DAEDAM_DATA_DIR`로 옮길 수 있다. 시험용 서버를 따로 띄울 때 쓴다 —
    데모용 면접이 든 디렉터리에 시험 등록이 섞이면 지우다 실수한다.
    """
    return Path(os.environ.get("DAEDAM_DATA_DIR") or SERVER_DIR / "data")
