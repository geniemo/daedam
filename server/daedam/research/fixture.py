"""fixture 모드 리서치 리포트.

디자인 핸드오프의 목업 리포트(web/src/data/mock.ts의 doc)를 서버 캐논으로
옮긴 것이다. 개발·데모는 이 리포트로 돌고, live 모드가 만드는 리포트도 이
형태(DocSection 목록)를 따른다. 블록 좌표(섹션 si, 블록 bi)가 그대로
"blk-{si}-{bi}" 청크 id가 되므로 순서를 바꾸면 uncertain 좌표도 함께
바꿔야 한다.
"""

from __future__ import annotations

from typing import Any

_REPORT: list[dict[str, Any]] = [
    {
        "title": "Executive Summary",
        "blocks": [
            {
                "type": "p",
                "text": "{company}는 신규 플랫폼을 중심으로 사업 구조를 재편하는"
                " 중이며, 최근 1년간 조직과 제품 양쪽에서 변화가 있었습니다. 지원"
                " 직무인 {role}은 이 변화가 진행되는 조직에 속해 있어, 면접에서는"
                " 회사의 최근 방향을 얼마나 이해하고 있는지가 비중 있게 다뤄질"
                " 가능성이 높습니다. [1]",
            },
        ],
    },
    {
        "title": "1. 회사와 사업 구조",
        "blocks": [
            {
                "type": "p",
                "text": "{company}의 매출은 크게 세 축으로 나뉘며, 그중 신규 플랫폼"
                " 부문이 올해 상반기 기준 전체의 절반 이상을 차지합니다. 나머지는"
                " 기존 주력 사업과 신규 투자 부문에서 발생합니다. [1]",
            },
            {"type": "li", "text": "기업 고객 대상 계약이 전체 계약의 약 70%를 차지합니다. [2]"},
            {"type": "li", "text": "개인 사용자 대응보다 파트너사 운영 프로세스가 조직 구조의 중심에 있습니다. [2]"},
            {"type": "li", "text": "지난해 데이터 조직을 별도 본부로 분리해 전사 지표 관리를 맡기고 있습니다. [3]"},
        ],
    },
    {
        "title": "2. 최근 1년의 변화",
        "blocks": [
            {
                "type": "p",
                "text": "최근 1년 사이 신규 플랫폼 공개와 조직 개편이 이어졌고, 이"
                " 변화는 채용 규모와 조직 개편에도 이어지고 있습니다. [4]",
            },
            {
                "type": "table",
                "head": ["시점", "내용", "관련 조직"],
                "rows": [
                    {"a": "2025.09", "b": "데이터 본부 신설", "c": "전사"},
                    {"a": "2026.03", "b": "신규 플랫폼 공개", "c": "프로덕트 부문"},
                    {"a": "2026.05", "b": "신입 채용 확대 발표", "c": "인사"},
                ],
            },
            {
                "type": "p",
                "text": "개발자 콘퍼런스에서는 내부 데이터 파이프라인 개편 사례를"
                " 공개했으며, 지표 정의를 팀 단위로 옮긴 점을 성과로 제시했습니다. [4]",
            },
        ],
    },
    {
        "title": "3. 인재상과 조직문화",
        "blocks": [
            {"type": "p", "text": "채용 페이지와 재직자 인터뷰에서 반복되는 표현을 정리하면 다음과 같습니다."},
            {"type": "li", "text": "\"스스로 문제를 정의하는 사람\"이라는 표현이 채용 페이지 세 곳에 반복됩니다. [5]"},
            {"type": "li", "text": "문서와 회의록으로 일하는 문화가 재직자 인터뷰 3건에서 공통으로 언급됩니다. [6]"},
            {"type": "li", "text": "호칭은 수평적이나 의사결정은 팀 리드 중심이라는 후기가 있습니다. 출처가 익명 게시글이어서 신뢰도는 낮습니다. [7]"},
        ],
    },
    {
        "title": "4. 직무 요구역량",
        "blocks": [
            {"type": "li", "text": "SQL을 이용한 데이터 추출이 자격요건에 명시되어 있습니다. [8]"},
            {"type": "li", "text": "지표를 정의하고 그 근거를 설명하는 능력을 우대사항으로 둡니다. [8]"},
            {"type": "li", "text": "유관 부서와의 협업 경험을 직무 소개서에서 세 차례 언급합니다. [9]"},
        ],
    },
    {
        "title": "5. 면접에서 검증될 가능성이 높은 지점",
        "blocks": [
            {
                "type": "p",
                "text": "지원서에 기재된 프로젝트 경험은 요구역량과 직접 맞닿아 있어,"
                " 본인 기여도와 판단 근거를 확인하는 질문이 나올 가능성이 높습니다."
                " 반대로 신규 플랫폼에 대한 이해는 지원서에서 확인되지 않아, 회사"
                " 이해도를 묻는 질문에서 변별이 일어날 수 있습니다.",
            },
        ],
    },
    {
        "title": "출처",
        "blocks": [
            {
                "type": "refs",
                "refs": [
                    {"n": "[1]", "label": "2026 상반기 실적 발표 자료"},
                    {"n": "[2]", "label": "회사 소개서 (2025년판)"},
                    {"n": "[3]", "label": "채용 페이지 · 조직 소개"},
                    {"n": "[4]", "label": "2026년 3월 보도자료 및 기술 블로그"},
                    {"n": "[5]", "label": "채용 페이지 · 인재상"},
                    {"n": "[6]", "label": "재직자 인터뷰 3건"},
                    {"n": "[7]", "label": "채용 커뮤니티 게시글"},
                    {"n": "[8]", "label": "채용공고 자격요건 · 우대사항"},
                    {"n": "[9]", "label": "직무 소개서"},
                ],
            },
        ],
    },
]

#: 확인이 필요한 대목 — (si, bi)가 위 리포트의 블록 좌표를 가리킨다.
_UNCERTAIN: list[dict[str, Any]] = [
    {"si": 3, "bi": 3, "title": "팀 리드 중심 의사결정", "reason": "익명 커뮤니티 게시글 한 건이 근거입니다"},
    {"si": 1, "bi": 1, "title": "기업 고객 비중 70%", "reason": "2025년판 소개서 기준이라 현재와 다를 수 있습니다"},
    {"si": 2, "bi": 1, "title": "변화 시점 표", "reason": "보도 시점 기준이며 실제 적용일과 다를 수 있습니다"},
]


def _fill_placeholders(value: Any, company: str, role: str) -> Any:
    """텍스트 값의 {company}·{role} 자리를 채우며 깊은 복사본을 만든다."""
    if isinstance(value, str):
        return value.replace("{company}", company).replace("{role}", role)
    if isinstance(value, list):
        return [_fill_placeholders(item, company, role) for item in value]
    if isinstance(value, dict):
        return {key: _fill_placeholders(item, company, role) for key, item in value.items()}
    return value


def fixture_report(company: str, role: str) -> list[dict[str, Any]]:
    """회사·직무를 채운 fixture 리포트를 돌려준다."""
    return _fill_placeholders(_REPORT, company, role)


def fixture_uncertain() -> list[dict[str, Any]]:
    """확인이 필요한 대목 목록을 돌려준다."""
    return _fill_placeholders(_UNCERTAIN, "", "")
