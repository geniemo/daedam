"""리포트 형태 변환 테스트 — 마크다운 → 화면, 화면 → 검색 입력."""

from daedam.research.report import search_sections_from_report, sections_from_markdown


def test_헤딩이_섹션이_된다() -> None:
    sections = sections_from_markdown("## 회사 개요\n본문\n\n### 세부\n더 있음")
    assert [s["title"] for s in sections] == ["회사 개요", "세부"]


def test_리스트_줄은_li_블록이_된다() -> None:
    sections = sections_from_markdown("## 개요\n- 하나\n* 둘")
    assert [b["type"] for b in sections[0]["blocks"]] == ["li", "li"]
    assert sections[0]["blocks"][1]["text"] == "둘"


def test_연속_문단_줄은_한_블록으로_합쳐진다() -> None:
    sections = sections_from_markdown("## 개요\n첫 줄이\n이어진다\n\n다음 문단")
    blocks = sections[0]["blocks"]
    assert blocks[0]["text"] == "첫 줄이 이어진다"
    assert blocks[1]["text"] == "다음 문단"


def test_헤딩이_없으면_기본_섹션_하나() -> None:
    sections = sections_from_markdown("그냥 문단 하나")
    assert len(sections) == 1
    assert sections[0]["title"] == "리서치 리포트"


def test_빈_입력은_빈_목록() -> None:
    assert sections_from_markdown("") == []


# ── 화면 리포트 → 검색 입력 ──────────────────────────────────────────────


def test_블록_id는_화면_좌표를_그대로_쓴다() -> None:
    """'확인 필요' 좌표·질문 근거 id와 같은 체계여야 한다."""
    report = [
        {"title": "개요", "blocks": [
            {"type": "p", "text": "문단"},
            {"type": "li", "text": "항목"},
        ]},
    ]
    (section,) = search_sections_from_report(report)
    assert [b["id"] for b in section["blocks"]] == ["blk-0-0", "blk-0-1"]
    assert section["blocks"][1]["text"] == "항목"


def test_표는_헤더와_값을_붙인_문장이_된다() -> None:
    report = [
        {"title": "변화", "blocks": [
            {"type": "table", "head": ["시점", "내용", "조직"],
             "rows": [{"a": "2025.09", "b": "본부 신설", "c": "전사"}]},
        ]},
    ]
    (section,) = search_sections_from_report(report)
    assert section["blocks"][0]["text"] == "시점 2025.09, 내용 본부 신설, 조직 전사"


def test_출처_블록은_건너뛰되_좌표는_보존된다() -> None:
    report = [
        {"title": "출처 섞임", "blocks": [
            {"type": "refs", "refs": [{"n": "[1]", "label": "자료"}]},
            {"type": "p", "text": "본문"},
        ]},
    ]
    (section,) = search_sections_from_report(report)
    # refs가 0번을 소비했으므로 본문은 blk-0-1 — 화면과 어긋나면 안 된다.
    assert section["blocks"] == [{"id": "blk-0-1", "text": "본문"}]
