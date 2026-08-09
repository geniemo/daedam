"""툴 테스트 공용 스텁."""

from typing import Any


class ToolContextStub:
    """state만 흉내 내는 ToolContext 대역.

    선언 주입(process_llm_request)과 툴 함수가 컨텍스트에서 읽는 것은
    state뿐이다 — append_tools는 tool_context를 아예 쓰지 않는다(설치된
    ADK 소스에서 확인). 그래서 InvocationContext 조립 없이 이걸로 충분하다.
    """

    def __init__(self, state: dict[str, Any] | None = None) -> None:
        self.state = state if state is not None else {}
