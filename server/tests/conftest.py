"""테스트 공용 스텁."""

from typing import Any


class ContextStub:
    """state만 노출하는 컨텍스트 대역 — ToolContext와 ReadonlyContext 겸용.

    선언 주입·툴 함수·instruction 조립이 컨텍스트에서 읽는 것은 state뿐이다
    (설치된 ADK 소스에서 확인 — append_tools는 tool_context를 아예 쓰지
    않는다). 그래서 InvocationContext 조립 없이 이걸로 충분하다.
    """

    def __init__(self, state: dict[str, Any] | None = None) -> None:
        self.state = state if state is not None else {}
