"""회사 지식 검색 툴 테스트.

검색 품질 자체는 knowledge 계층 테스트가 맡는다. 여기서는 툴 경계 —
state 복원, source 좁히기, 빈 결과 안내, 선언 스키마 — 를 검증한다.
"""

import asyncio

import pytest
from conftest import ContextStub
from google.adk.models.llm_request import LlmRequest
from google.adk.tools import FunctionTool

from interviewer.tools import (
    STATE_APPLICATION,
    STATE_RESEARCH_REPORT,
    _knowledge_index_from,
    search_knowledge,
)

REPORT = [
    {
        "title": "주력 사업",
        "blocks": [
            {"id": "blk-0-0", "text": "핀테크 정산 서비스를 운영하며 가맹점 정산 주기를 사흘에서 하루로 단축했다.", "ref": "보도자료"},
        ],
    },
]
APPLICATION = [
    {
        "part": "자기소개서",
        "items": [
            {"title": "지원동기", "body": "가맹점 정산 주기 단축 사례를 보고 지원했습니다."},
        ],
    },
]

STATE = {STATE_RESEARCH_REPORT: REPORT, STATE_APPLICATION: APPLICATION}


# ── 검색 ─────────────────────────────────────────────────────────────────


def test_리포트에서_관련_정보를_찾는다() -> None:
    """기본 검색은 두 코퍼스를 다 본다. 순위는 검증하지 않는다 — BM25 길이
    정규화 때문에 짧은 청크가 앞설 수 있고, 그건 정상이다."""
    result = search_knowledge(tool_context=ContextStub(STATE), query="정산 주기")
    report_items = [i for i in result["results"] if i["source"] == "리서치 리포트"]
    assert report_items, "리포트 청크가 결과에 있어야 한다"
    assert report_items[0]["ref"] == "보도자료"


def test_source로_지원서만_좁힌다() -> None:
    result = search_knowledge(
        tool_context=ContextStub(STATE), query="정산", source="application"
    )
    assert result["results"]
    assert all(item["source"] == "지원서" for item in result["results"])


def test_무관한_질의는_빈_결과와_note() -> None:
    """모델이 '없음'을 지어내지 않고 말할 수 있어야 한다."""
    result = search_knowledge(tool_context=ContextStub(STATE), query="등산 코스 추천")
    assert result["results"] == []
    assert "note" in result


def test_시딩_안_된_세션은_크게_실패한다() -> None:
    """폴백으로 가리면 엉뚱한 데이터로 검색이 그럴듯하게 돌아버린다."""
    with pytest.raises(ValueError, match="시딩"):
        search_knowledge(tool_context=ContextStub(), query="배차 자동화")


def test_같은_코퍼스는_인덱스를_재사용한다() -> None:
    """임베딩 인덱스(청크 벡터 인코딩)를 검색마다 다시 만들지 않는다."""
    first = _knowledge_index_from({STATE_RESEARCH_REPORT: REPORT, STATE_APPLICATION: APPLICATION})
    second = _knowledge_index_from({STATE_RESEARCH_REPORT: list(REPORT), STATE_APPLICATION: list(APPLICATION)})
    assert first is second


# ── 선언 ─────────────────────────────────────────────────────────────────


def test_선언에_query는_필수_source는_enum이다() -> None:
    """source enum은 Literal 타입에서 나오는 정적 선언이다."""
    request = LlmRequest()
    asyncio.run(
        FunctionTool(search_knowledge).process_llm_request(
            tool_context=ContextStub(), llm_request=request
        )
    )
    (tool,) = request.config.tools
    (declaration,) = tool.function_declarations
    schema = declaration.parameters_json_schema
    assert schema["required"] == ["query"]
    (string_branch,) = [
        branch
        for branch in schema["properties"]["source"]["anyOf"]
        if branch.get("type") == "string"
    ]
    assert string_branch["enum"] == ["research", "application"]
