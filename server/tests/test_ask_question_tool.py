"""질문 툴 테스트.

선언 주입은 네트워크 없이 LlmRequest에 대해 검증한다. 시간 예산은 세션의
시작 시각을 과거로 밀어 만든다 — 툴이 벽시계를 읽으므로 시계를 재는 대신
면접이 언제 시작했는지를 바꾼다.

파볼 곳 추출(Grok)은 대역으로 바꾼다 — 모듈 전역 `_extract_probes`를
monkeypatch한다. 여기서 보는 것은 흐름이다: 뼈대질문 → 답변 → 파볼 곳 → 신고
→ 다음 파볼 곳 → 다음 뼈대질문.
"""

import asyncio
import time
from typing import Any

import pytest
from conftest import ContextStub
from google.adk.models.llm_request import LlmRequest
from google.genai import types

from daedam.interview.probes import Extraction, Probe
from interviewer import tools
from interviewer.tools import (
    STATE_ASKED,
    STATE_PROBE_LOG,
    STATE_PROBES,
    STATE_PROFILE,
    STATE_QUESTION_POOL,
    STATE_STAGE,
    STATE_STARTED_AT,
    AskQuestionTool,
    ask_question,
)

POOL_RAW = [
    {"id": "a", "stage": 0, "text": "자기소개 부탁드립니다.", "priority": 1,
     "tags": ["자기소개"]},
    {"id": "b", "stage": 1, "text": "맡으신 역할을 설명해 주세요.", "priority": 1,
     "tags": ["경험상세"]},
    {"id": "c", "stage": 1, "text": "가장 어려웠던 판단은 무엇이었나요?", "priority": 4,
     "tags": ["문제해결"]},
]

#: dev 프로필 단계 경계: 90 / 270 / 420 / 480초. 네 단계를 다 돈다.
PROFILE = "dev"

PROBES = [Probe("분류 기준", "어떤 기준으로 나눴는지 안 나왔다"),
          Probe("본인 역할", "본인이 한 일이 안 갈렸다")]


def _state(started_s_ago: float = 0.0, **overrides: Any) -> dict[str, Any]:
    """시딩된 세션 state. started_s_ago만큼 면접이 이미 진행된 상태가 된다."""
    return {
        STATE_QUESTION_POOL: POOL_RAW,
        STATE_STARTED_AT: time.time() - started_s_ago,
        STATE_PROFILE: PROFILE,
        **overrides,
    }


def _call(context: ContextStub, tag: str = "경험상세", answered: str = "", evidence: str = "") -> dict:
    return ask_question(tool_context=context, tag=tag, answered=answered, evidence=evidence)


class _FakeExtract:
    """추출 대역. 호출 기록을 남기고 정해 둔 목록을 돌려준다."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.result: list[Probe] = list(PROBES)
        self.leads_with: str = ""

    def __call__(self, *, question: str, answer: str, experiences=None) -> Extraction:
        self.calls.append({"question": question, "answer": answer, "experiences": experiences or []})
        return Extraction(probes=list(self.result), leads_with=self.leads_with)


@pytest.fixture
def probes(monkeypatch) -> _FakeExtract:
    fake = _FakeExtract()
    monkeypatch.setattr(tools, "_extract_probes", fake)
    return fake


def _inject(state: dict[str, Any] | None = None) -> LlmRequest:
    request = LlmRequest()
    asyncio.run(
        AskQuestionTool().process_llm_request(
            tool_context=ContextStub(state), llm_request=request
        )
    )
    return request


def _declaration(request: LlmRequest) -> types.FunctionDeclaration:
    (tool,) = request.config.tools
    (declaration,) = tool.function_declarations
    return declaration


# ── 선언 주입 ────────────────────────────────────────────────────────────


def test_세션_풀의_태그가_enum으로_실린다() -> None:
    prop = _declaration(_inject(_state())).parameters_json_schema["properties"]["tag"]
    assert prop["enum"] == ["자기소개", "경험상세", "문제해결"]
    assert prop["type"] == "string"


def test_answered는_enum이고_필수가_아니다() -> None:
    """yes/no가 스키마에 보여야 모델이 고른다 — 산문으로 부탁하는 것보다 세다.
    뼈대질문 뒤 호출에서는 비우므로 필수는 아니다."""
    schema = _declaration(_inject(_state())).parameters_json_schema
    assert set(schema["required"]) == {"tag"}
    assert set(schema["properties"]["answered"]["enum"]) >= {"yes", "no"}


def test_시딩_안_된_세션은_크게_실패한다() -> None:
    """폴백으로 가리면 엉뚱한 데이터로 면접이 그럴듯하게 돌아버린다."""
    with pytest.raises(ValueError, match="시딩"):
        _inject()


def test_선언과_등록은_한_번만_된다() -> None:
    """super() 호출 뒤의 패치가 이중 등록을 만들면 안 된다."""
    request = _inject(_state())
    _declaration(request)
    assert list(request.tools_dict) == ["ask_question"]


# ── 뼈대질문 배달 ────────────────────────────────────────────────────────


def test_준비된_질문이_ask로_나간다(probes) -> None:
    context = ContextStub(_state(stage=1))
    result = _call(context)
    assert result["ask"] == "맡으신 역할을 설명해 주세요."
    assert context.state[STATE_ASKED] == ["b"]
    assert set(result) == {"ask", "instruction"}


def test_tag로_해당_주제의_질문을_고른다(probes) -> None:
    result = _call(ContextStub(_state(stage=1)), tag="문제해결")
    assert result["ask"] == "가장 어려웠던 판단은 무엇이었나요?"


def test_배달_직후에는_추출하지_않는다(probes) -> None:
    """답변이 아직 없다. 뽑는 것은 다음 호출이다."""
    _call(ContextStub(_state(stage=1)))
    assert probes.calls == []


# ── 파볼 곳 흐름 ─────────────────────────────────────────────────────────


def test_답변이_오면_파볼_곳을_뽑아_첫_번째를_준다(probes) -> None:
    context = ContextStub(_state(stage=1))
    _call(context)  # 뼈대질문 b 배달
    context.hear("구조적 결함은 YOLO로, 질감은 EfficientNet으로 했습니다.")

    result = _call(context)
    assert len(probes.calls) == 1
    assert probes.calls[0]["question"] == "맡으신 역할을 설명해 주세요."
    assert probes.calls[0]["answer"] == "구조적 결함은 YOLO로, 질감은 EfficientNet으로 했습니다."
    assert result["probe"] == "분류 기준"
    assert result["hint"] == "어떤 기준으로 나눴는지 안 나왔다"
    assert "ask" not in result


def test_뼈대질문_뒤_여러_조각의_답변을_이어_붙인다(probes) -> None:
    """말하다 쉬면 전사가 조각으로 온다 — 첫 조각만 읽으면 반쪽 답변을 판단한다."""
    context = ContextStub(_state(stage=1))
    _call(context)
    context.hear("구조적 결함은 YOLO로,")
    context.hear("질감은 EfficientNet으로 했습니다.")
    _call(context)
    assert probes.calls[0]["answer"] == "구조적 결함은 YOLO로, 질감은 EfficientNet으로 했습니다."


def test_뼈대질문_전의_말은_답변에_넣지_않는다(probes) -> None:
    """앞 질문의 답변이 섞이면 엉뚱한 곳을 판다."""
    context = ContextStub(_state(stage=1), said=["앞 질문에 대한 답으로 한참 말했습니다."])
    _call(context)
    context.hear("이번 질문의 답은 YOLO와 EfficientNet을 결합한 것입니다.")
    _call(context)
    assert probes.calls[0]["answer"] == "이번 질문의 답은 YOLO와 EfficientNet을 결합한 것입니다."


def test_yes로_신고하면_다음_파볼_곳을_준다(probes) -> None:
    context = ContextStub(_state(stage=1))
    _call(context)
    context.hear("구조적 결함은 YOLO로, 질감은 EfficientNet으로 나눠서 결합했습니다.")
    assert _call(context)["probe"] == "분류 기준"

    context.hear("기준은 결함의 형태였습니다.")
    result = _call(context, answered="yes", evidence="결함 형태를 기준으로")
    assert result["probe"] == "본인 역할"
    # 닫힌 것은 기록에 남는다 — 리포트의 근거가 된다.
    log = context.state[STATE_PROBE_LOG]
    assert log[-1]["topic"] == "분류 기준"
    assert log[-1]["status"] == "covered"
    assert log[-1]["evidence"] == "결함 형태를 기준으로"


def test_다_닫히면_다음_뼈대질문이다(probes) -> None:
    context = ContextStub(_state(stage=1))
    _call(context)
    context.hear("구조적 결함은 YOLO로, 질감은 EfficientNet으로 나눠서 결합했습니다.")
    _call(context)
    _call(context, answered="yes", evidence="e1")
    result = _call(context, answered="yes", evidence="e2")
    assert result["ask"] == "가장 어려웠던 판단은 무엇이었나요?"
    assert context.state[STATE_ASKED] == ["b", "c"]


def test_no로_돌아오면_한_번_더_묻고_그다음엔_포기한다(probes) -> None:
    """두 번 물어도 안 나오면 닫는다 — 세 번째는 심문이다."""
    context = ContextStub(_state(stage=1))
    _call(context)
    context.hear("구조적 결함은 YOLO로, 질감은 EfficientNet으로 나눠서 결합했습니다.")
    first = _call(context)
    assert first["probe"] == "분류 기준"  # 1회
    retry = _call(context, answered="no")  # 못 들음 → 2회
    assert retry["probe"] == "분류 기준"
    # 재시도는 첫 응답과 다른 지시여야 한다 — 같으면 모델이 "또?"로 읽고 다른
    # 것을 묻는다(실측).
    assert retry["instruction"] != first["instruction"]
    assert "다른 질문으로 넘어가지 말고" in retry["instruction"]
    result = _call(context, answered="no")  # 또 못 들음 → 포기, 다음 파볼 곳
    assert result["probe"] == "본인 역할"
    log = context.state[STATE_PROBE_LOG]
    assert log[-1]["topic"] == "분류 기준" and log[-1]["status"] == "unanswered"


def test_신고를_빼먹으면_못_들은_것으로_본다(probes) -> None:
    """들었는지 모르니 한 번 더 묻는다 — 못 들은 것을 들은 것으로 닫는 쪽이 나쁘다."""
    context = ContextStub(_state(stage=1))
    _call(context)
    context.hear("구조적 결함은 YOLO로, 질감은 EfficientNet으로 나눠서 결합했습니다.")
    _call(context)
    assert _call(context)["probe"] == "분류 기준"  # answered 없음 → 재시도
    result = _call(context)  # 또 없음 → 포기
    assert result["probe"] == "본인 역할"
    assert context.state[STATE_PROBE_LOG][-1]["status"] == "unanswered"


def test_마무리_단계에서는_파볼_곳을_뽑지_않는다(probes) -> None:
    """"마지막으로 하고 싶은 말씀"에 파볼 곳은 없다 — 파면 심문이 된다."""
    pool = POOL_RAW + [{"id": "z", "stage": 3, "text": "마지막으로 하고 싶은 말씀은?",
                        "priority": 4, "tags": ["마지막 한마디"]}]
    context = ContextStub(_state(stage=3, **{STATE_QUESTION_POOL: pool}))
    assert _call(context, tag="마지막 한마디")["ask"] == "마지막으로 하고 싶은 말씀은?"
    context.hear("꼭 입사하고 싶습니다.")
    result = _call(context)
    assert probes.calls == []
    assert "probe" not in result


def test_파볼_곳이_없으면_바로_다음_뼈대질문이다(probes) -> None:
    """LLM이 빈 목록을 냈거나 실패했다 — 면접은 돈다."""
    probes.result = []
    context = ContextStub(_state(stage=1))
    _call(context)
    context.hear("충분히 설명했습니다.")
    result = _call(context)
    assert result["ask"] == "가장 어려웠던 판단은 무엇이었나요?"


def test_답변_전사가_없으면_추출하지_않고_다음_뼈대질문이다(probes) -> None:
    """못 보는 것이 지어내는 것보다 낫다."""
    context = ContextStub(_state(stage=1))
    _call(context)
    result = _call(context)  # hear() 없음
    assert probes.calls == []
    assert result["ask"] == "가장 어려웠던 판단은 무엇이었나요?"


def test_응답은_물을_것과_다음_행동뿐이다(probes) -> None:
    """단계 이름·힌트 밖의 설명은 싣지 않는다 — 입으로 샌다."""
    context = ContextStub(_state(stage=1))
    _call(context)
    context.hear("구조적 결함은 YOLO로, 질감은 EfficientNet으로 나눠서 결합했습니다.")
    result = _call(context)
    assert set(result) == {"probe", "hint", "instruction"}
    assert "단계" not in result["instruction"]


# ── 시간 예산 ────────────────────────────────────────────────────────────


def test_시간이_지나면_단계를_건너뛴다(probes) -> None:
    """1단계에 질문이 남아 있어도 예산을 넘겼으면 2단계로 간다."""
    context = ContextStub(_state(100.0, stage=0))
    assert _call(context)["ask"] == "맡으신 역할을 설명해 주세요."
    assert context.state[STATE_STAGE] == 1


def test_단계가_넘어가면_열린_파볼_곳을_버린다(probes) -> None:
    """지난 단계를 계속 파면 뒤 단계가 통째로 잘린다."""
    context = ContextStub(_state(0.0, stage=0))
    _call(context, tag="자기소개")  # a 배달
    context.hear("구조적 결함은 YOLO로, 질감은 EfficientNet으로 나눠서 결합했습니다.")
    assert _call(context)["probe"] == "분류 기준"
    # 시계를 2단계로 민다
    context.state[STATE_STARTED_AT] = time.time() - 100.0
    result = _call(context)
    assert result["ask"] == "맡으신 역할을 설명해 주세요."
    assert all(p["status"] == "dropped" for p in context.state[STATE_PROBES])


def test_예산보다_앞서_가는_것은_막지_않는다(probes) -> None:
    context = ContextStub(_state(0.0, stage=1))
    _call(context)
    assert context.state[STATE_STAGE] == 1


def test_시간이_다_지나도_면접을_끝내지_않는다(probes) -> None:
    """끝내는 것은 지원자의 종료 버튼이다. 시간 예산은 단계를 옮기는 데만 쓴다 —
    마지막 단계 예산을 넘겨도 마무리 지시가 아니라 이어가라는 지시가 온다."""
    result = _call(ContextStub(_state(600.0)))
    assert "done" not in result
    assert "이어가세요" in result["instruction"]


def test_질문을_다_쓰면_꼬리질문으로_이어가라고_한다(probes) -> None:
    context = ContextStub(_state(stage=1, **{STATE_ASKED: ["a", "b", "c"]}))
    result = _call(context)
    assert "ask" not in result and "probe" not in result
    assert "꼬리질문" in result["instruction"]


def test_시작_시각_없는_세션은_크게_실패한다(probes) -> None:
    with pytest.raises(ValueError, match="시딩"):
        _call(ContextStub({STATE_QUESTION_POOL: POOL_RAW}))


# ── 이어갈 경험 ──────────────────────────────────────────────────────────

POOL_EXP = [
    {"id": "a", "stage": 0, "text": "자기소개 부탁드립니다.", "priority": 1,
     "tags": ["자기소개"], "source_chunk_ids": []},
    {"id": "d1", "stage": 1, "text": "디밀리언에서 결합 기준은?", "priority": 1,
     "tags": ["모델 선택"], "source_chunk_ids": ["app-0-1#1"]},
    {"id": "f1", "stage": 1, "text": "딥페이크에서 DCT 계기는?", "priority": 1,
     "tags": ["데이터 표현"], "source_chunk_ids": ["app-0-2#0"]},
    {"id": "d2", "stage": 1, "text": "디밀리언 배포 범위는?", "priority": 2,
     "tags": ["엣지 배포"], "source_chunk_ids": ["app-0-1#2"]},
]


def test_자기소개가_가리킨_경험부터_간다(probes) -> None:
    """자기소개에서 딥페이크 얘기를 길게 했으면 디밀리언(우선순위 동점, 앞)이
    아니라 딥페이크부터. 추출이 후보 중 골라 주고, 다음 배달이 그것을 따른다."""
    probes.leads_with = "딥페이크에서 DCT 계기는?"
    context = ContextStub(_state(0.0, stage=0, **{STATE_QUESTION_POOL: POOL_EXP}))
    _call(context, tag="자기소개")  # a 배달
    context.hear("학부 연구생 때 딥페이크 탐지 모델을 개발하면서 데이터를 분석했습니다.")
    _call(context)  # 추출 → leads_with 저장, 파볼 곳 1
    # 후보에 1단계 경험 둘이 실렸어야 한다
    assert set(probes.calls[0]["experiences"]) == {"디밀리언에서 결합 기준은?", "딥페이크에서 DCT 계기는?"}
    # 자기소개는 파볼 곳 하나다 — 닫으면 0단계 소진으로 1단계 진입
    result = _call(context, answered="yes", evidence="e")
    assert result["ask"] == "딥페이크에서 DCT 계기는?"


def test_같은_경험이_남아_있으면_그것부터(probes) -> None:
    """d1 뒤에는 f1(동점)이 아니라 d2(같은 경험)."""
    probes.result = []
    context = ContextStub(_state(0.0, stage=1, **{STATE_QUESTION_POOL: POOL_EXP}))
    assert _call(context, tag="모델 선택")["ask"] == "디밀리언에서 결합 기준은?"
    context.hear("구조적 결함은 YOLO로, 질감은 EfficientNet으로 나눠서 결합했습니다.")
    assert _call(context)["ask"] == "디밀리언 배포 범위는?"
    context.hear("구조적 결함은 YOLO로, 질감은 EfficientNet으로 나눠서 결합했습니다.")
    assert _call(context)["ask"] == "딥페이크에서 DCT 계기는?"




def test_자기소개_단계는_파볼_곳이_하나다(probes) -> None:
    """둘을 다 파면 자기소개에만 2분이 간다(실측 126초). 자기소개는 어느 경험부터
    갈지 잡는 자리지 파는 자리가 아니다."""
    context = ContextStub(_state(0.0, stage=0))
    _call(context, tag="자기소개")
    context.hear("안녕하십니까, 데이터의 본질을 보는 지원자 박지원입니다. 딥페이크 탐지를 했습니다.")
    _call(context)
    assert len(context.state[STATE_PROBES]) == 1
