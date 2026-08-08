"""청킹·검색 테스트.

검색은 면접 중 임계 경로에서 호출되므로 (1) 빈 입력에도 절대 예외를 던지지
않고 (2) 블록 id를 잃지 않는 것이 중요하다. id는 §6 검토 화면의 주석이
매달리는 앵커다(README §서버 연동 3).
"""

import pytest

from daedam.knowledge.chunk import Chunk, from_application, from_report, outline
from daedam.knowledge.search import Knowledge

# ── 픽스처 ───────────────────────────────────────────────────────────────

REPORT = [
    {
        "title": "1. 회사와 사업 구조",
        "blocks": [
            {
                "id": "blk-1-0",
                "text": "누리테크의 매출은 세 축으로 나뉘며, 파트너 정산 서비스 부문이 절반 이상을 차지합니다.",
                "ref": "2026 상반기 실적 발표 자료",
            },
            {"id": "blk-1-1", "text": "기업 고객 대상 계약이 전체의 약 70%를 차지합니다."},
            {"id": "blk-1-2", "text": "   "},  # 빈 블록 — 색인 대상 아님
        ],
    },
    {
        "title": "3. 인재상과 조직문화",
        "blocks": [
            {
                "id": "blk-3-0",
                "text": "호칭은 수평적이나 의사결정은 팀 리드 중심이라는 후기가 있습니다.",
            },
        ],
    },
]

APPLICATION = [
    {
        "part": "경험",
        "items": [
            {
                "title": "경험 1 — 교내 물류 데이터 분석 프로젝트",
                "body": "재고 회전율이 낮은 품목을 찾기 위해 3개월치 출고 데이터를 정리했습니다.",
            },
            {"title": "경험 2 — 스타트업 인턴", "body": ""},  # 미작성 — 색인 대상 아님
        ],
    },
    {
        "part": "자격증",
        "items": [{"title": "SQLD", "body": "2025년 3월 취득"}],
    },
]


# ── 청킹 ─────────────────────────────────────────────────────────────────


def test_리포트_블록_id가_그대로_보존된다() -> None:
    chunks = from_report(REPORT)
    assert [c.id for c in chunks] == ["blk-1-0", "blk-1-1", "blk-3-0"]


def test_리포트_빈_블록은_색인하지_않는다() -> None:
    assert all(c.text.strip() for c in from_report(REPORT))


def test_리포트_청크는_섹션_제목과_출처를_함께_갖는다() -> None:
    first = from_report(REPORT)[0]
    assert first.title == "1. 회사와 사업 구조"
    assert first.ref == "2026 상반기 실적 발표 자료"
    assert first.source == "research"


def test_지원서_빈_항목은_색인하지_않는다() -> None:
    chunks = from_application(APPLICATION)
    assert len(chunks) == 2
    assert all("인턴" not in c.title for c in chunks)


def test_지원서_청크_제목은_파트와_항목을_합친다() -> None:
    chunks = from_application(APPLICATION)
    assert chunks[0].title == "경험 · 경험 1 — 교내 물류 데이터 분석 프로젝트"
    assert chunks[0].source == "application"


def test_지원서_항목에_id가_없으면_생성한다() -> None:
    assert from_application(APPLICATION)[0].id == "app-0-0"


def test_목차는_작성된_항목만_담는다() -> None:
    text = outline(APPLICATION)
    assert "경험 1" in text
    assert "SQLD" in text
    assert "경험 2" not in text  # 본문이 비어 있음


def test_목차는_빈_지원서에도_문장을_돌려준다() -> None:
    assert outline([]) != ""


# ── 검색 ─────────────────────────────────────────────────────────────────


@pytest.fixture
def knowledge() -> Knowledge:
    return Knowledge(from_report(REPORT) + from_application(APPLICATION))


def test_관련_청크를_찾는다(knowledge: Knowledge) -> None:
    hits = knowledge.search("파트너 정산 서비스 매출 비중")
    assert hits[0].id == "blk-1-0"


def test_지원서도_같은_인덱스에서_검색된다(knowledge: Knowledge) -> None:
    hits = knowledge.search("물류 데이터 분석 프로젝트에서 한 일")
    assert hits[0].source == "application"


def test_source로_코퍼스를_좁힐_수_있다(knowledge: Knowledge) -> None:
    hits = knowledge.search("물류 데이터", source="research")
    assert all(c.source == "research" for c in hits)


def test_k로_결과_개수를_제한한다(knowledge: Knowledge) -> None:
    assert len(knowledge.search("데이터", k=2)) <= 2


def test_전혀_안_맞는_질의는_빈_결과를_준다(knowledge: Knowledge) -> None:
    assert knowledge.search("양자역학 초전도체") == []


def test_빈_질의에도_예외를_던지지_않는다(knowledge: Knowledge) -> None:
    assert knowledge.search("") == []
    assert knowledge.search("   ") == []


def test_빈_코퍼스에도_예외를_던지지_않는다() -> None:
    """지원서를 안 쓰고 리서치도 실패한 세션 — 면접은 계속돼야 한다."""
    assert Knowledge([]).search("아무거나") == []


def test_결과는_모델에게_넘길_형태로_직렬화된다(knowledge: Knowledge) -> None:
    hit = knowledge.search("기업 고객 계약 비중")[0].as_result()
    assert hit["source"] == "리서치 리포트"  # 모델이 읽을 한국어 라벨
    assert "id" in hit and "title" in hit and "text" in hit


def test_출처가_없는_블록은_ref_필드를_안_넣는다(knowledge: Knowledge) -> None:
    chunk = Chunk(id="x", source="application", title="t", text="본문")
    assert "ref" not in chunk.as_result()
