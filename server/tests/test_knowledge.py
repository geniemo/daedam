"""청킹·검색 테스트.

검색은 면접 중 임계 경로에서 호출되므로 (1) 빈 입력에도 절대 예외를 던지지
않고 (2) 블록 id를 잃지 않는 것이 중요하다. id는 §6 검토 화면의 주석이
매달리는 앵커다(README §서버 연동 3).
"""

import pytest

from daedam.knowledge.chunk import Chunk, chunks_from_application, chunks_from_report, application_outline
from daedam.knowledge.search import KnowledgeIndex

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
    chunks = chunks_from_report(REPORT)
    assert [c.id for c in chunks] == ["blk-1-0", "blk-1-1", "blk-3-0"]


def test_리포트_빈_블록은_색인하지_않는다() -> None:
    assert all(c.text.strip() for c in chunks_from_report(REPORT))


def test_리포트_청크는_섹션_제목과_출처를_함께_갖는다() -> None:
    first = chunks_from_report(REPORT)[0]
    assert first.title == "1. 회사와 사업 구조"
    assert first.ref == "2026 상반기 실적 발표 자료"
    assert first.source == "research"


def test_지원서_빈_항목은_색인하지_않는다() -> None:
    chunks = chunks_from_application(APPLICATION)
    assert len(chunks) == 2
    assert all("인턴" not in c.title for c in chunks)


def test_지원서_청크_제목은_파트와_항목을_합친다() -> None:
    chunks = chunks_from_application(APPLICATION)
    assert chunks[0].title == "경험 · 경험 1 — 교내 물류 데이터 분석 프로젝트"
    assert chunks[0].source == "application"


def test_지원서_항목에_id가_없으면_생성한다() -> None:
    assert chunks_from_application(APPLICATION)[0].id == "app-0-0"


# ── 긴 본문 쪼개기 ───────────────────────────────────────────────────────
#
# 자소서 문항은 1000자를 넘는 경우가 흔하다. 항목을 통째로 청크로 쓰면
# 검색 정밀도가 떨어지고, 검색 결과가 그대로 대화 컨텍스트에 실린다.

LONG_BODY = (
    "저는 대학 3학년 때 교내 물류 데이터 분석 프로젝트를 주도했습니다. "
    "매점 재고가 자주 소진되는 문제가 있었는데, 담당자분들은 원인을 발주 주기로 보고 계셨습니다. "
    "저는 그보다 품목 분류 기준에 문제가 있다고 판단했습니다.\n\n"
    "3개월치 출고 데이터를 정리해 보니 기존 분류가 대분류 단위여서 회전율이 낮은 품목이 "
    "평균에 가려지고 있었습니다. 소분류로 다시 나누자 상위 20개 품목이 드러났고, "
    "이들이 전체 결품의 절반 이상을 차지한다는 것을 확인했습니다.\n\n"
    "팀원들은 기존 기준을 유지하자는 입장이었습니다. 작업량이 두 배로 늘어난다는 이유였습니다. "
    "저는 두 방식으로 모두 분석해 비교 자료를 만들었고, 제가 데이터 정리를 맡는 조건으로 합의했습니다. "
    "최종적으로 발주 주기를 2주에서 1주로 줄이자는 제안이 채택되어 세 개 매장에 적용되었습니다."
)

LONG_APPLICATION = [{"part": "자기소개서", "items": [{"title": "문항 1", "body": LONG_BODY}]}]


def test_긴_지원서_항목은_여러_청크로_쪼개진다() -> None:
    chunks = chunks_from_application(LONG_APPLICATION)
    assert len(chunks) > 1


def test_쪼개진_청크는_부모_id에_번호를_붙인다() -> None:
    """§6 주석이 매달리는 앵커를 잃지 않도록 부모 id를 접두로 유지한다."""
    ids = [c.id for c in chunks_from_application(LONG_APPLICATION)]
    assert all(i.startswith("app-0-0#") for i in ids)
    assert ids == sorted(ids, key=lambda i: int(i.split("#")[1]))


def test_짧은_본문은_번호_없이_원래_id를_유지한다() -> None:
    """대부분의 리서치 블록은 짧다 — 불필요하게 id를 바꾸지 않는다."""
    assert chunks_from_report(REPORT)[0].id == "blk-1-0"


def test_쪼개진_청크도_제목과_출처를_그대로_물려받는다() -> None:
    chunks = chunks_from_application(LONG_APPLICATION)
    assert all(c.title == "자기소개서 · 문항 1" for c in chunks)
    assert all(c.source == "application" for c in chunks)


def test_쪼개진_청크는_각각_검색된다() -> None:
    """긴 항목의 뒷부분 내용도 독립적으로 걸려야 한다."""
    knowledge = KnowledgeIndex(chunks_from_application(LONG_APPLICATION))
    hits = knowledge.search("팀원 설득 비교 자료")
    assert hits and "비교 자료" in hits[0].text


def test_목차는_작성된_항목만_담는다() -> None:
    text = application_outline(APPLICATION)
    assert "경험 1" in text
    assert "SQLD" in text
    assert "경험 2" not in text  # 본문이 비어 있음


def test_목차는_빈_지원서에도_문장을_돌려준다() -> None:
    assert application_outline([]) != ""


# ── 검색 ─────────────────────────────────────────────────────────────────


@pytest.fixture
def knowledge() -> KnowledgeIndex:
    return KnowledgeIndex(chunks_from_report(REPORT) + chunks_from_application(APPLICATION))


def test_관련_청크를_찾는다(knowledge: KnowledgeIndex) -> None:
    hits = knowledge.search("파트너 정산 서비스 매출 비중")
    assert hits[0].id == "blk-1-0"


def test_지원서도_같은_인덱스에서_검색된다(knowledge: KnowledgeIndex) -> None:
    hits = knowledge.search("물류 데이터 분석 프로젝트에서 한 일")
    assert hits[0].source == "application"


def test_source로_코퍼스를_좁힐_수_있다(knowledge: KnowledgeIndex) -> None:
    hits = knowledge.search("물류 데이터", source="research")
    assert all(c.source == "research" for c in hits)


def test_k로_결과_개수를_제한한다(knowledge: KnowledgeIndex) -> None:
    assert len(knowledge.search("데이터", k=2)) <= 2


def test_전혀_안_맞는_질의는_빈_결과를_준다(knowledge: KnowledgeIndex) -> None:
    assert knowledge.search("양자역학 초전도체") == []


def test_빈_질의에도_예외를_던지지_않는다(knowledge: KnowledgeIndex) -> None:
    assert knowledge.search("") == []
    assert knowledge.search("   ") == []


def test_어미만_겹치는_무관한_질의는_걸러진다(knowledge: KnowledgeIndex) -> None:
    """한국어는 조사·어미 때문에 우발적 겹침이 생긴다. 실측상 무관 질의는 27% 이하."""
    assert knowledge.search("그렇게 하는 것이 좋았습니다") == []
    assert knowledge.search("지원자는 어떤 사람인가요") == []


def test_빈_코퍼스에도_예외를_던지지_않는다() -> None:
    """지원서를 안 쓰고 리서치도 실패한 세션 — 면접은 계속돼야 한다."""
    assert KnowledgeIndex([]).search("아무거나") == []


def test_결과는_모델에게_넘길_형태로_직렬화된다(knowledge: KnowledgeIndex) -> None:
    hit = knowledge.search("기업 고객 계약 비중")[0].as_tool_result()
    assert hit["source"] == "리서치 리포트"  # 모델이 읽을 한국어 라벨
    assert "title" in hit and "text" in hit


def test_청크_id는_모델에게_노출하지_않는다(knowledge: KnowledgeIndex) -> None:
    """서버 내부용 식별자다. 검색을 반복하면 쓸모없는 문자열만 컨텍스트에 쌓인다."""
    assert "id" not in knowledge.search("기업 고객 계약 비중")[0].as_tool_result()


def test_출처가_없는_블록은_ref_필드를_안_넣는다(knowledge: KnowledgeIndex) -> None:
    chunk = Chunk(id="x", source="application", title="t", text="본문")
    assert "ref" not in chunk.as_tool_result()
