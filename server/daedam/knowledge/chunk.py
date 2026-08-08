"""리서치 리포트와 지원서를 공통 검색 단위(Chunk)로 변환한다.

두 문서 모두 이미 자연스러운 경계를 갖고 있어 별도 청킹 알고리즘을 쓰지 않는다.
리포트는 블록(§서버 연동 3), 지원서는 항목(§3)이 그대로 청크가 된다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

#: 청크의 출처. 검색 시 이 값으로 코퍼스를 좁힐 수 있다.
Source = Literal["research", "application"]

#: 모델에게 보여줄 출처 라벨. 영문 키를 그대로 노출하지 않는다.
_SOURCE_LABEL: dict[str, str] = {
    "research": "리서치 리포트",
    "application": "지원서",
}


@dataclass(frozen=True)
class Chunk:
    """검색 단위 하나.

    Attributes:
        id: 안정적 식별자. 리서치는 블록 id("blk-1-0"), 지원서는 "app-{파트}-{항목}".
            §6 검토 화면의 주석이 이 id에 매달린다.
        source: "research" 또는 "application".
        title: 리서치는 섹션 제목, 지원서는 "파트 · 항목명".
        text: 본문.
        ref: 리서치 블록의 출처 라벨. 지원서는 None.
    """

    id: str
    source: Source
    title: str
    text: str
    ref: str | None = None

    def as_result(self) -> dict[str, Any]:
        """툴이 모델에게 돌려줄 형태로 직렬화한다.

        Returns:
            id·source·title·text를 담은 dict. ref가 있을 때만 ref 키가 붙는다.
        """
        result: dict[str, Any] = {
            "id": self.id,
            "source": _SOURCE_LABEL[self.source],
            "title": self.title,
            "text": self.text,
        }
        if self.ref:
            result["ref"] = self.ref
        return result


def from_report(sections: list[dict[str, Any]]) -> list[Chunk]:
    """리서치 리포트를 검색 청크로 변환한다.

    정정이 이미 적용된 리포트를 받는다. 원문과 정정본을 함께 다루지 않는다.

    Args:
        sections: `[{"title": str, "blocks": [{"id": str, "text": str,
            "ref": str | None}]}]` 형태의 섹션 목록.

    Returns:
        본문이 있는 블록만 담은 Chunk 목록. 블록 id는 그대로 보존된다.
    """
    chunks: list[Chunk] = []
    for section in sections:
        section_title = section.get("title", "")
        for block in section.get("blocks", []):
            text = (block.get("text") or "").strip()
            if not text:
                continue
            chunks.append(
                Chunk(
                    id=block["id"],
                    source="research",
                    title=section_title,
                    text=text,
                    ref=block.get("ref"),
                )
            )
    return chunks


def from_application(parts: list[dict[str, Any]]) -> list[Chunk]:
    """지원서를 검색 청크로 변환한다.

    Args:
        parts: `[{"part": str, "items": [{"title": str, "body": str,
            "id": str | None}]}]` 형태의 파트 목록.

    Returns:
        본문이 작성된 항목만 담은 Chunk 목록. id가 없는 항목에는
        "app-{파트index}-{항목index}"를 부여한다.
    """
    chunks: list[Chunk] = []
    for part_index, part in enumerate(parts):
        part_name = part.get("part", "")
        for item_index, item in enumerate(part.get("items", [])):
            body = (item.get("body") or "").strip()
            if not body:
                continue
            # 파트명을 제목에 붙인다. 제목도 함께 색인되므로 검색에 유리하다.
            title = f"{part_name} · {item.get('title', '')}".strip(" ·")
            chunks.append(
                Chunk(
                    id=item.get("id") or f"app-{part_index}-{item_index}",
                    source="application",
                    title=title,
                    text=body,
                )
            )
    return chunks


def outline(parts: list[dict[str, Any]]) -> str:
    """지원서 목차를 시스템 프롬프트용 문자열로 만든다.

    본문은 넣지 않는다. 목차만으로 에이전트가 "무엇을 파고들 수 있는지"를
    알 수 있고, 본문 전체(3천 토큰 안팎)를 프롬프트에 넣지 않아도 된다.

    Args:
        parts: `from_application`과 같은 형태의 파트 목록.

    Returns:
        "- 파트: 항목1 / 항목2" 줄들. 작성된 항목이 없으면 안내 문구.
    """
    lines: list[str] = []
    for part in parts:
        titles = [
            item.get("title", "")
            for item in part.get("items", [])
            if (item.get("body") or "").strip()
        ]
        if not titles:
            continue
        lines.append(f"- {part.get('part', '')}: " + " / ".join(titles))
    return "\n".join(lines) if lines else "(등록된 지원서 항목이 없습니다)"
