"""테스트 공용 스텁."""

import os
from typing import Any

# 유닛 테스트는 실제 임베딩 모델을 로드하지 않는다 — 모델 다운로드(수 GB)와
# GPU 없이도 돌아야 한다. 의미 검색 경로는 대역 임베더로 검증한다.
os.environ.setdefault("SEARCH_EMBEDDINGS", "off")


class ContextStub:
    """state만 노출하는 컨텍스트 대역 — ToolContext와 ReadonlyContext 겸용.

    선언 주입·툴 함수·instruction 조립이 컨텍스트에서 읽는 것은 state뿐이다
    (설치된 ADK 소스에서 확인 — append_tools는 tool_context를 아예 쓰지
    않는다). 그래서 InvocationContext 조립 없이 이걸로 충분하다.
    """

    def __init__(self, state: dict[str, Any] | None = None) -> None:
        self.state = state if state is not None else {}
