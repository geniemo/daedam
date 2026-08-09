"""동적 instruction 조립 테스트."""

import asyncio

from conftest import ContextStub

from interviewer.agent import root_agent
from interviewer.instruction import (
    STATE_CANDIDATE,
    STATE_COMPANY,
    STATE_ROLE,
    build_instruction,
)
from interviewer.tools import STATE_APPLICATION, STATE_RESEARCH_REPORT

FULL_STATE = {
    STATE_COMPANY: "한결물류",
    STATE_ROLE: "데이터 엔지니어",
    STATE_CANDIDATE: "박시온",
    STATE_RESEARCH_REPORT: [
        {"title": "주력 사업과 기술", "blocks": [{"id": "blk-0-0", "text": "리포트 본문입니다."}]},
        {"title": "인재상과 조직문화", "blocks": [{"id": "blk-1-0", "text": "리포트 본문입니다."}]},
    ],
    STATE_APPLICATION: [
        {
            "part": "자기소개서",
            "items": [
                {"title": "지원동기", "body": "지원동기 본문입니다."},
                {"title": "프로젝트 경험", "body": "프로젝트 본문입니다."},
            ],
        },
    ],
}


def test_회사_직무_지원자가_박힌다() -> None:
    text = build_instruction(ContextStub(FULL_STATE))
    assert "당신은 한결물류의 신입 채용 면접관입니다" in text
    assert "지원자 박시온님과" in text
    assert "데이터 엔지니어 직무" in text


def test_지원서는_목차만_실린다() -> None:
    """본문은 프롬프트에 넣지 않는다 — 검색으로 가져온다."""
    text = build_instruction(ContextStub(FULL_STATE))
    assert "- 자기소개서: 지원동기 / 프로젝트 경험" in text
    assert "지원동기 본문입니다" not in text


def test_리포트도_목차만_실린다() -> None:
    """검색 질의 어휘를 리포트 어휘에 앵커링한다 — 본문은 넣지 않는다."""
    text = build_instruction(ContextStub(FULL_STATE))
    assert "회사 조사 자료의 목차: 주력 사업과 기술 / 인재상과 조직문화" in text
    assert "리포트 본문입니다" not in text


def test_모의라는_말은_어디에도_없다() -> None:
    """에이전트는 자신을 실제 면접관으로 알아야 한다."""
    for state in (FULL_STATE, {}):
        assert "모의" not in build_instruction(ContextStub(state))


def test_빈_state면_일반_면접관으로_줄어든다() -> None:
    """adk web에서 세션 state 없이 바로 띄워도 프롬프트가 성립한다."""
    text = build_instruction(ContextStub())
    assert "당신은 신입 채용 면접관입니다" in text
    assert "지원자와 한국어 음성으로 면접을 진행합니다" in text
    assert "None" not in text
    assert "목차" not in text


def test_에이전트가_provider로_해석한다() -> None:
    """ADK canonical_instruction 경로 — 콜러블 호출 + {var} state 주입 우회."""
    text, bypass = asyncio.run(
        root_agent.canonical_instruction(ContextStub(FULL_STATE))
    )
    assert "한결물류" in text
    assert bypass is True
