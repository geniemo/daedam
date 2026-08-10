"""마크다운 → 화면 리포트 변환 테스트."""

from daedam.research.report import sections_from_markdown


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
