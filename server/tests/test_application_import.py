"""지원서 PDF 가져오기 테스트.

Gemini는 부르지 않는다. 대역이 구조화 응답을 돌려주고, 여기서 보는 것은 배관이다
— PDF가 어떤 모양으로 실리는가, 지시문에 무엇이 있는가, 응답을 어떻게 다듬는가.
"""

from types import SimpleNamespace

import pytest

from daedam.interview.application_import import (
    POSTING_PROMPT,
    PROMPT,
    ImportedApplication,
    ImportedItem,
    ImportedPart,
    extract_application,
    extract_posting,
    sniff_mime,
)


class _Client:
    def __init__(self, parsed) -> None:  # noqa: ANN001
        self.parsed = parsed
        self.calls: list[dict] = []
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, **kwargs):  # noqa: ANN003
        self.calls.append(kwargs)
        return SimpleNamespace(parsed=self.parsed)


def _parsed() -> ImportedApplication:
    return ImportedApplication(
        parts=[
            ImportedPart(
                name=" 자기소개서 ",
                items=[
                    ImportedItem(title="1. 지원 동기", body=" 저는 …  "),
                    ImportedItem(title="2. 답 없는 문항", body="   "),
                ],
            ),
            ImportedPart(name="경력", items=[ImportedItem(title="", body="본문만 있음")]),
            ImportedPart(name="비어 있는 파트", items=[]),
        ]
    )


def test_PDF를_그대로_싣고_구조로_돌려준다() -> None:
    client = _Client(_parsed())
    parts = extract_application(b"%PDF-1.4 ...", client=client, model="m")

    [call] = client.calls
    part, prompt = call["contents"]
    assert part.inline_data.mime_type == "application/pdf"
    assert prompt is PROMPT
    assert call["config"].response_schema is ImportedApplication
    assert parts == [
        {"part": "자기소개서", "items": [{"title": "1. 지원 동기", "body": "저는 …"}]},
        {"part": "경력", "items": [{"title": "항목 1", "body": "본문만 있음"}]},
    ]


def test_지시문은_인적사항을_빼고_원문_그대로를_요구한다() -> None:
    """지원 사이트 export에는 생년월일·주소·학점까지 들어 있다. 그게 항목이
    되면 면접관이 주소를 읽는다."""
    for word in ("연락처", "주소", "학점", "그대로", "요약"):
        assert word in PROMPT


def test_구조화_응답이_아니면_실패한다() -> None:
    with pytest.raises(ValueError):
        extract_application(b"%PDF", client=_Client(parsed=None), model="m")


# ── 채용공고 파일 ─────────────────────────────────────────────────────────


class _TextClient:
    def __init__(self, text: str | None) -> None:
        self.text = text
        self.calls: list[dict] = []
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, **kwargs):  # noqa: ANN003
        self.calls.append(kwargs)
        return SimpleNamespace(text=self.text)


def test_파일_종류는_머리로_가린다() -> None:
    assert sniff_mime(b"%PDF-1.7") == "application/pdf"
    assert sniff_mime(b"\x89PNG\r\n") == "image/png"
    assert sniff_mime(b"\xff\xd8\xff\xe0") == "image/jpeg"
    assert sniff_mime(b"GIF89a") is None
    assert sniff_mime(b"hello") is None


def test_채용공고_이미지를_본문_텍스트로_옮긴다() -> None:
    client = _TextClient("  담당 업무\n- 결함 데이터 분석  ")
    text = extract_posting(b"\x89PNG....", client=client, model="m")
    [call] = client.calls
    part, prompt = call["contents"]
    assert part.inline_data.mime_type == "image/png"
    assert prompt is POSTING_PROMPT
    assert text == "담당 업무\n- 결함 데이터 분석"


def test_받지_않는_파일은_모델을_부르지_않는다() -> None:
    client = _TextClient("x")
    with pytest.raises(ValueError):
        extract_posting(b"GIF89a", client=client, model="m")
    assert client.calls == []


def test_빈_응답은_실패다() -> None:
    with pytest.raises(ValueError):
        extract_posting(b"%PDF", client=_TextClient("   "), model="m")
