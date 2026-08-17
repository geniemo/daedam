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
             "rows": [["2025.09", "본부 신설", "전사"]]},
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


# ── 실측(컬리 리포트)에 실제로 나온 마크다운 ──────────────────────────


def test_굵게_표시는_지워진다() -> None:
    (section,) = sections_from_markdown("## 기술\n**AI 오케스트레이션**을 도입했다.")
    assert section["blocks"][0]["text"] == "AI 오케스트레이션을 도입했다."


def test_파이프_표는_표_블록이_된다() -> None:
    markdown = (
        "## 기술\n"
        "| 기술 | 영역 | 효과 |\n"
        "| :--- | :--- | :--- |\n"
        "| **오케스트레이션** | 물류 | 생산성 |\n"
    )
    (section,) = sections_from_markdown(markdown)
    assert section["blocks"] == [
        {
            "type": "table",
            "head": ["기술", "영역", "효과"],
            "rows": [["오케스트레이션", "물류", "생산성"]],
        }
    ]


def test_표의_열_수는_고정이_아니다() -> None:
    markdown = "## 비교\n| 축 | 값 |\n| :--- | :--- |\n| 매출 | 증가 |\n"
    (section,) = sections_from_markdown(markdown)
    assert section["blocks"][0]["head"] == ["축", "값"]


def test_칸_수가_모자란_행은_빈_칸으로_채운다() -> None:
    """잘라내면 원문이 사라지고, 그대로 두면 화면 그리드가 어긋난다."""
    markdown = "## 비교\n| 가 | 나 | 다 |\n| :- | :- | :- |\n| 하나 | 둘 |\n"
    (section,) = sections_from_markdown(markdown)
    assert section["blocks"][0]["rows"] == [["하나", "둘", ""]]


def test_구분선이_없으면_표가_아니다() -> None:
    (section,) = sections_from_markdown("## 본문\n| 이건 | 표가 아니다 |")
    assert section["blocks"][0]["type"] == "p"


def test_셀_안의_br은_한_줄로_펼쳐진다() -> None:
    markdown = "## 역량\n| 축 | 세부 |\n| :- | :- |\n| SQL | - 추출<br>- 시각화 |\n"
    (section,) = sections_from_markdown(markdown)
    assert section["blocks"][0]["rows"] == [["SQL", "추출 · 시각화"]]


def test_출처_줄은_refs_블록으로_모인다() -> None:
    markdown = (
        "## 출처\n"
        "[cite: 8] https://www.kurly.com/introduce (컬리 인재상)\n"
        "[cite: 9] https://cloud.google.com/customers/kurly (빅쿼리 연동)\n"
    )
    (section,) = sections_from_markdown(markdown)
    assert section["blocks"] == [
        {
            "type": "refs",
            "refs": [
                {"n": "8", "label": "컬리 인재상"},
                {"n": "9", "label": "빅쿼리 연동"},
            ],
        }
    ]


def test_번호_매긴_링크도_refs로_간다() -> None:
    """리디렉트 URL이 200자를 넘어 문단으로 두면 편집란 하나를 통째로 먹는다."""
    (section,) = sections_from_markdown(
        "## 출처\n1. [chosun.com](https://vertexaisearch.cloud.google.com/x?a=1)"
    )
    assert section["blocks"] == [
        {"type": "refs", "refs": [{"n": "1", "label": "chosun.com"}]}
    ]
