"""리서치 리포트의 형태 변환.

리포트의 캐논 형태는 프론트가 렌더하는 DocSection(web/src/data/types.ts)이다.
여기에 두 방향의 변환을 둔다: Deep Research 마크다운 → DocSection(수신),
DocSection → 지식 검색 입력(소비). 마크다운 변환은 헤딩과 리스트만 구조로
옮기고 표·출처는 문단으로 남긴다 — live 리포트 실물을 보고 나서 넓힌다.
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


def search_sections_from_report(report: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """화면 리포트(DocSection)를 지식 검색 입력으로 바꾼다.

    검색·질문 생성의 근거는 마크다운 원문이 아니라 이 화면 형태다 — 사용자
    검토·정정이 블록 단위로 반영되는 곳이 여기라서, 정정된 리포트를 믿으려면
    이 형태에서 출발해야 한다.

    블록 id는 화면 좌표 그대로 "blk-{si}-{bi}"다 — 검토 화면의 '확인 필요'
    좌표, 질문의 근거 청크 id가 전부 이 한 체계를 공유한다. 출처(refs)
    블록은 검색 대상이 아니라 건너뛰지만 좌표는 enumerate가 보존한다.

    Args:
        report: p·li·table·refs 블록을 가진 섹션 목록.

    Returns:
        `[{"title", "blocks": [{"id", "text"}]}]` —
        `daedam.knowledge.chunk.chunks_from_report`의 입력 형태.
    """
    sections: list[dict[str, Any]] = []
    for section_index, section in enumerate(report):
        blocks = []
        for block_index, block in enumerate(section.get("blocks", [])):
            text = _block_text(block)
            if text:
                blocks.append(
                    {"id": f"blk-{section_index}-{block_index}", "text": text}
                )
        if blocks:
            sections.append({"title": section.get("title", ""), "blocks": blocks})
    return sections


def _block_text(block: dict[str, Any]) -> str:
    """블록을 색인 가능한 평문으로 만든다. 표는 행을 "헤더 값" 문장으로 잇는다."""
    kind = block.get("type")
    if kind in ("p", "li"):
        return (block.get("text") or "").strip()
    if kind == "table":
        head = block.get("head") or []
        lines = []
        for row in block.get("rows") or []:
            cells = [row.get(key, "") for key in ("a", "b", "c")]
            lines.append(", ".join(f"{h} {c}" for h, c in zip(head, cells) if c))
        return ". ".join(lines)
    return ""
