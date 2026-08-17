"""리서치 리포트의 형태 변환.

리포트의 캐논 형태는 프론트가 렌더하는 DocSection(web/src/data/types.ts)이다.
여기에 두 방향의 변환을 둔다: Deep Research 마크다운 → DocSection(수신),
DocSection → 지식 검색 입력(소비).

수신 쪽이 다루는 것은 실측(컬리 리포트)에 실제로 나온 것들이다: 헤딩, 리스트,
파이프 표, `**굵게**`, 셀 안의 `<br>`, 그리고 두 종류의 출처 줄.

검토 화면은 블록을 textarea로 열어 사용자가 직접 고치는 자리다. 그래서 강조
표시는 살릴 수가 없다 — 별표를 그대로 두면 편집란에 별표가 보인다. 지우고
평문으로 만든다. 리포트가 하는 일은 사실 검증과 질문 생성 입력이라 강조는
정보가 아니다.
"""

from __future__ import annotations

import re
from typing import Any

_HEADING = re.compile(r"^#{1,6}\s+(.*)$")
_LIST_ITEM = re.compile(r"^\s*[-*]\s+(.*)$")

#: `| a | b | c |` 한 줄. 표는 헤더 줄 바로 다음이 구분선일 때만 표로 본다.
_TABLE_ROW = re.compile(r"^\|(.*)\|$")
#: `| :--- | ---: |` 구분선. 콜론·하이픈·파이프·공백만으로 이루어진다.
_TABLE_DELIM = re.compile(r"^\|[\s:|-]+\|$")

_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)

#: `[cite: 8] https://... (설명)` — 출처 섹션의 형태.
_CITE_REF = re.compile(r"^\[cite:\s*([\d,\s]+)\]\s*(\S+)(?:\s*\((.+)\))?$")
#: `1. [chosun.com](https://...)` — 번호 매긴 링크 목록. URL이 200자 넘는
#: 리디렉트라 문단으로 두면 편집란 하나를 통째로 잡아먹는다.
_LINK_REF = re.compile(r"^(\d+)\.\s*\[([^\]]+)\]\((https?://[^)]+)\)$")


def _clean(text: str) -> str:
    """블록 본문을 편집란에 그대로 실을 수 있는 평문으로 만든다."""
    text = _BOLD.sub(lambda m: m.group(1) or m.group(2), text)
    text = _BR.sub(" · ", text)
    return " ".join(text.split())


def _cell(text: str) -> str:
    """표 한 칸. `<br>`로 나뉜 항목의 리스트 마커까지 떼어 한 줄로 만든다."""
    parts = [p.strip().lstrip("-").strip() for p in _BR.split(text)]
    return _clean(" · ".join(p for p in parts if p))


def _table_at(lines: list[str], start: int) -> tuple[dict[str, Any], int] | None:
    """`start`에서 시작하는 파이프 표를 읽는다. 표가 아니면 None.

    열 수는 고정하지 않는다. 행마다 칸 수가 다르면 가장 넓은 행에 맞춰 빈 칸을
    채운다 — 잘라내면 원문이 사라지고, 그대로 두면 화면 그리드가 어긋난다.

    Returns:
        (표 블록, 표가 끝난 다음 줄 번호) 또는 None.
    """
    if start + 1 >= len(lines):
        return None
    if not _TABLE_ROW.match(lines[start].strip()):
        return None
    if not _TABLE_DELIM.match(lines[start + 1].strip()):
        return None

    def cells(line: str) -> list[str]:
        return [_cell(c) for c in _TABLE_ROW.match(line.strip()).group(1).split("|")]

    head = cells(lines[start])
    rows: list[list[str]] = []
    index = start + 2
    while index < len(lines) and _TABLE_ROW.match(lines[index].strip()):
        rows.append(cells(lines[index]))
        index += 1

    width = max([len(head)] + [len(r) for r in rows])
    head += [""] * (width - len(head))
    rows = [r + [""] * (width - len(r)) for r in rows]
    return {"type": "table", "head": head, "rows": rows}, index


def _ref_at(line: str) -> dict[str, str] | None:
    """출처 한 줄을 `{n, label}`로. 두 형태 다 받는다."""
    if cite := _CITE_REF.match(line):
        number, url, note = cite.groups()
        return {"n": number.strip(), "label": _clean(note or url)}
    if link := _LINK_REF.match(line):
        number, label, _url = link.groups()
        return {"n": number, "label": _clean(label)}
    return None


def sections_from_markdown(markdown: str) -> list[dict[str, Any]]:
    """마크다운을 섹션·블록 구조로 바꾼다.

    Args:
        markdown: Deep Research가 돌려준 리포트 본문.

    Returns:
        `[{"title", "blocks": [...]}]` 목록. 블록은 p·li·table·refs 넷.
        헤딩이 없으면 전체가 "리서치 리포트" 섹션 하나가 된다.
    """
    lines = markdown.splitlines()
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] = {"title": "리서치 리포트", "blocks": []}
    paragraph: list[str] = []
    refs: list[dict[str, str]] = []

    def flush_paragraph() -> None:
        if paragraph:
            current["blocks"].append({"type": "p", "text": _clean(" ".join(paragraph))})
            paragraph.clear()

    def flush_refs() -> None:
        if refs:
            current["blocks"].append({"type": "refs", "refs": list(refs)})
            refs.clear()

    def flush_section() -> None:
        flush_paragraph()
        flush_refs()
        if current["blocks"]:
            sections.append(current)

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            flush_refs()
            index += 1
            continue

        if heading := _HEADING.match(stripped):
            flush_section()
            current = {"title": _clean(heading.group(1)), "blocks": []}
            index += 1
            continue

        if table := _table_at(lines, index):
            flush_paragraph()
            flush_refs()
            block, index = table
            current["blocks"].append(block)
            continue

        if ref := _ref_at(stripped):
            flush_paragraph()
            refs.append(ref)
            index += 1
            continue

        if item := _LIST_ITEM.match(line):
            flush_paragraph()
            flush_refs()
            current["blocks"].append({"type": "li", "text": _clean(item.group(1))})
            index += 1
            continue

        flush_refs()
        paragraph.append(stripped)
        index += 1

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
            lines.append(", ".join(f"{h} {c}" for h, c in zip(head, row) if c))
        return ". ".join(lines)
    return ""
