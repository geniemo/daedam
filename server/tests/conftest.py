"""테스트 공용 스텁."""

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

# 유닛 테스트는 실제 임베딩 모델을 로드하지 않는다 — 모델 다운로드(수 GB)와
# GPU 없이도 돌아야 한다. 의미 검색 경로는 대역 임베더로 검증한다.
os.environ.setdefault("SEARCH_EMBEDDINGS", "off")


def make_store(root: Path) -> tuple[Any, Any, str]:
    """테스트용 저장소 한 벌 — (저장소, 계정, 기본 사용자 id).

    임시 디렉터리의 SQLite 파일을 쓴다. 인메모리로 하면 스레드마다 다른
    데이터베이스를 보게 되는데, 준비·평가 파이프라인이 전담 스레드로 돈다.

    마이그레이션이 아니라 `create_all`로 만든다 — 테스트는 스키마의 최종
    형태만 필요하고, 마이그레이션 자체는 실제 기동에서 검증된다.
    """
    from daedam.db import Database
    from daedam.server.accounts import Accounts
    from daedam.server.store import InterviewStore

    root.mkdir(parents=True, exist_ok=True)
    db = Database(f"sqlite:///{root / 'test.db'}")
    db.create_all()
    accounts = Accounts(db)
    return InterviewStore(db, root), accounts, accounts.default_user_id()


class ContextStub:
    """state와 세션 이력을 노출하는 컨텍스트 대역 — ToolContext·ReadonlyContext 겸용.

    선언 주입과 instruction 조립이 읽는 것은 state뿐이다(설치된 ADK 소스에서
    확인 — append_tools는 tool_context를 아예 쓰지 않는다). 질문 툴은 여기에
    더해 세션 이벤트의 완료된 입력 전사를 읽어 지원자의 답변을 모은다. 그래서
    InvocationContext 조립 없이 이 둘만 흉내 내면 충분하다.
    """

    def __init__(
        self,
        state: dict[str, Any] | None = None,
        said: list[str] | None = None,
    ) -> None:
        self.state = state if state is not None else {}
        # 지원자가 한 말. Live에서는 완료된 입력 전사가 세션 이벤트로 쌓이고
        # 툴이 그걸 읽는다 — 여기서는 그 모양만 흉내 낸다.
        self.session = SimpleNamespace(events=[])
        for text in said or []:
            self.hear(text)

    def hear(self, text: str) -> None:
        """지원자가 한 마디 더 했다 — 완료된 입력 전사 이벤트 하나를 쌓는다."""
        self.session.events.append(
            SimpleNamespace(
                input_transcription=SimpleNamespace(text=text, finished=True),
                output_transcription=None,
            )
        )
