"""리서치 리포트와 지원서를 공통 검색 단위(Chunk)로 변환한다.

리포트는 블록, 지원서는 항목이 1차 경계다. 다만 자소서 문항은 1000자를 넘는
일이 흔해, 항목을 통째로 두면 검색 정밀도가 떨어지고 검색 결과가 그대로 대화
컨텍스트에 실린다. 그래서 긴 본문은 문단·문장 경계에서 다시 쪼갠다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from semantic_text_splitter import TextSplitter

#: 청크의 출처. 검색 시 이 값으로 코퍼스를 좁힐 수 있다.
Source = Literal["research", "application"]

#: 청크 하나의 목표 길이(문자). 검색 결과가 그대로 모델 컨텍스트에 실리므로
#: 한 문단 남짓으로 제한한다.
_CAPACITY = 400

#: 경계에 걸친 내용이 양쪽에서 모두 검색되도록 하는 중첩 길이.
_OVERLAP = 50

#: 문단 → 문장 → 단어 순으로 경계를 찾아 쪼갠다. 유니코드를 제대로 다루므로
#: 한국어에서도 문장 중간을 자르지 않는다. 생성 비용이 있어 모듈 단위로 재사용한다.
_splitter = TextSplitter(capacity=_CAPACITY, overlap=_OVERLAP)


def _split(text: str, base_id: str) -> list[tuple[str, str]]:
    """본문을 청크로 쪼개고 각각에 id를 부여한다.

    Args:
        text: 쪼갤 본문.
        base_id: 부모 단위(리포트 블록 또는 지원서 항목)의 id.

    Returns:
        `(id, 본문)` 튜플 목록. 쪼갤 필요가 없으면 base_id를 그대로 쓰고,
        여러 조각이 되면 "{base_id}#0", "{base_id}#1" 형태로 번호를 붙인다.
    """
    pieces = _splitter.chunks(text)
    if len(pieces) <= 1:
        return [(base_id, text)]
    return [(f"{base_id}#{index}", piece) for index, piece in enumerate(pieces)]

#: 모델에게 보여줄 출처 라벨. 영문 키를 그대로 노출하지 않는다.
_SOURCE_LABEL: dict[str, str] = {
    "research": "리서치 리포트",
    "application": "지원서",
}


@dataclass(frozen=True)
class Chunk:
    """검색 단위 하나.

    Attributes:
        id: 청크 식별자. 리서치는 블록 id("blk-1-0"), 지원서는 "app-{파트}-{항목}"
            이며, 쪼개진 조각에는 "#n"이 붙는다. 로그와 검색 eval에서 쓰는
            서버 내부용 값이라 모델에게는 노출하지 않는다.
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
            source·title·text를 담은 dict. ref가 있을 때만 ref 키가 붙는다.
        """
        result: dict[str, Any] = {
            "source": _SOURCE_LABEL[self.source],
            "title": self.title,
            "text": self.text,
        }
        if self.ref:
            result["ref"] = self.ref
        return result


def from_report(sections: list[dict[str, Any]]) -> list[Chunk]:
    """리서치 리포트를 검색 청크로 변환한다.

    Args:
        sections: `[{"title": str, "blocks": [{"id": str, "text": str,
            "ref": str | None}]}]` 형태의 섹션 목록.

    Returns:
        본문이 있는 블록만 담은 Chunk 목록. 짧은 블록은 id가 그대로 보존되고,
        긴 블록은 "{블록id}#n"으로 쪼개진다.
    """
    chunks: list[Chunk] = []
    for section in sections:
        section_title = section.get("title", "")
        for block in section.get("blocks", []):
            text = (block.get("text") or "").strip()
            if not text:
                continue
            for chunk_id, piece in _split(text, block["id"]):
                chunks.append(
                    Chunk(
                        id=chunk_id,
                        source="research",
                        title=section_title,
                        text=piece,
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
        "app-{파트index}-{항목index}"를 부여하고, 본문이 길면 "#n"을 덧붙여
        쪼갠다.
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
            base_id = item.get("id") or f"app-{part_index}-{item_index}"
            for chunk_id, piece in _split(body, base_id):
                chunks.append(
                    Chunk(
                        id=chunk_id,
                        source="application",
                        title=title,
                        text=piece,
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
