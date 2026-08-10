"""Deep Research 마크다운 → 화면 리포트(DocSection 목록) 변환.

프론트가 렌더하는 형태는 web/src/data/types.ts의 DocSection이다. 여기서는
헤딩과 리스트만 구조로 옮기고, 표와 출처 표기는 아직 문단으로 남긴다 —
live 리포트의 실제 마크다운을 보고 나서 넓힌다.
"""

from __future__ import annotations

import re
from typing import Any

_HEADING = re.compile(r"^#{1,6}\s+(.*)$")
_LIST_ITEM = re.compile(r"^\s*[-*]\s+(.*)$")


def sections_from_markdown(markdown: str) -> list[dict[str, Any]]:
    """마크다운을 섹션·블록 구조로 바꾼다.

    Args:
        markdown: Deep Research가 돌려준 리포트 본문.

    Returns:
        `[{"title", "blocks": [{"type": "p"|"li", "text"}]}]` 목록.
        헤딩이 없으면 전체가 "리서치 리포트" 섹션 하나가 된다.
    """
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] = {"title": "리서치 리포트", "blocks": []}
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            current["blocks"].append({"type": "p", "text": " ".join(paragraph)})
            paragraph.clear()

    def flush_section() -> None:
        flush_paragraph()
        if current["blocks"]:
            sections.append(current)

    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            continue
        if heading := _HEADING.match(stripped):
            flush_section()
            current = {"title": heading.group(1).strip(), "blocks": []}
            continue
        if item := _LIST_ITEM.match(line):
            flush_paragraph()
            current["blocks"].append({"type": "li", "text": item.group(1).strip()})
            continue
        paragraph.append(stripped)

    flush_section()
    return sections
