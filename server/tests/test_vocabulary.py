"""전사 어휘 힌트 테스트.

실측에서 이름과 용어가 계속 깨졌다 — "박지원"→"박지훈", "Jetson AGX
Orin"→"Jeston Ajax 올인", "산학협력"→"산악인력". 그 낱말들은 면접 전에 이미
손에 있다.

뽑는 것은 Grok이고 여기서는 부르지 않는다. 대역으로 보는 것은 배관이다 —
확실한 낱말이 추출 결과와 무관하게 남는가, 프롬프트에 자료가 실리는가.
"""

from types import SimpleNamespace

from daedam.interview.vocabulary import (
    generate_vocabulary,
    interview_vocabulary,
    vocabulary_prompt,
)
from daedam.server.live_bridge import _vocabulary_for
from daedam.server.store import InterviewData


class _StubClient:
    """구조화 출력을 흉내 낸다. 보낸 프롬프트를 붙잡아 검증에 쓴다."""

    def __init__(self, terms: list[str]) -> None:
        self.parsed = SimpleNamespace(terms=terms)
        self.prompt: str | None = None
        self.beta = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(parse=self._parse))
        )

    def _parse(self, *, model, messages, response_format):  # noqa: ANN001
        self.prompt = messages[0]["content"]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(parsed=self.parsed))]
        )


def _application(body: str = "") -> list[dict]:
    return [
        {
            "part": "경험",
            "items": [{"title": "DMILLION 인턴", "body": body}],
        }
    ]


def test_이름과_회사는_추출과_무관하게_실린다() -> None:
    """가장 자주 나오고 가장 자주 깨지는 낱말이라 Grok에 맡기지 않는다."""
    client = _StubClient(["TensorRT"])
    terms = generate_vocabulary(
        company="SK 하이닉스",
        role="기반기술",
        name="박지원",
        application=_application(),
        client=client,
    )
    assert terms[:3] == ["박지원", "SK 하이닉스", "기반기술"]
    assert "TensorRT" in terms


def test_추출이_확실한_낱말을_다시_내도_한_번만_넣는다() -> None:
    client = _StubClient(["박지원", "산학협력"])
    terms = generate_vocabulary(
        company="A", role="B", name="박지원", application=[], client=client
    )
    assert terms.count("박지원") == 1


def test_추출이_비어도_확실한_낱말은_남는다() -> None:
    """Grok이 아무것도 못 뽑아도 이름 없이 면접을 시작하지 않는다."""
    terms = generate_vocabulary(
        company="A", role="B", name="박지원", application=[], client=_StubClient([])
    )
    assert terms == ["박지원", "A", "B"]


def test_문장_길이의_추출물은_걸러진다() -> None:
    """어휘 힌트 자리에 문장이 들어가면 상한만 잡아먹는다."""
    sentence = "데이터 전처리를 통해 성능을 크게 개선한 경험이 있습니다"
    terms = generate_vocabulary(
        company="A", role="B", application=[], client=_StubClient([sentence, "비콘"])
    )
    assert sentence not in terms
    assert "비콘" in terms


def test_프롬프트에_지원서_본문과_질문이_실린다() -> None:
    """제목만으로는 못 뽑는다 — 깨지는 용어는 본문에 있다."""
    prompt = vocabulary_prompt(
        company="SK 하이닉스",
        role="기반기술",
        name="박지원",
        application=_application("컬리 산학협력 프로젝트에서 BLE 비콘을 다뤘습니다"),
        questions=[{"text": "백본을 나눈 기준은 무엇이었나요?"}],
    )
    assert "산학협력" in prompt and "BLE 비콘" in prompt
    assert "백본을 나눈 기준은 무엇이었나요?" in prompt
    assert "박지원" in prompt


# ── 규칙 폴백 ────────────────────────────────────────────────────────────
# 준비 때 추출이 없었거나 실패한 면접이 쓴다. 영문 약어까지가 한계다.


def test_회사와_직무가_맨_앞이다() -> None:
    terms = interview_vocabulary(
        company="SK 하이닉스", role="기반기술 · 신입", application=[]
    )
    assert terms[:3] == ["SK 하이닉스", "기반기술", "신입"]


def test_지원서_제목과_파트가_들어간다() -> None:
    terms = interview_vocabulary(company="A", role="B", application=_application())
    assert "경험" in terms and "DMILLION 인턴" in terms


def test_본문의_영문_용어를_건진다() -> None:
    """가장 많이 깨지는 것이 기술 용어인데 그건 제목이 아니라 본문에 있다."""
    terms = interview_vocabulary(
        company="A",
        role="B",
        application=_application("Jetson AGX Orin에서 TensorRT FP16으로 최적화했습니다"),
    )
    for term in ("Jetson", "AGX", "Orin", "TensorRT", "FP16"):
        assert term in terms


def test_흔한_영단어는_넣지_않는다() -> None:
    """상한이 있는데 the·and 같은 말이 자리를 차지하면 안 된다."""
    terms = interview_vocabulary(
        company="A", role="B", application=_application("the data for AI project")
    )
    assert not {"the", "data", "for", "project"} & set(terms)


def test_문항_제목처럼_긴_문장은_뺀다() -> None:
    """지원서 문항은 한 문장이라 어휘 힌트가 못 되고 상한만 잡아먹는다."""
    long_title = "지원하신 직무 분야의 전문성을 키우기 위해 꾸준히 노력한 경험을 서술해주세요."
    terms = interview_vocabulary(
        company="A",
        role="B",
        application=[{"part": "자기소개서", "items": [{"title": long_title, "body": ""}]}],
    )
    assert long_title not in terms
    assert "자기소개서" in terms


def test_추출_어휘를_키워드_뒤에_합친다() -> None:
    """순서가 곧 가치다 — 확실한 것(이름·회사)이 앞, 추출이 다음, 규칙이 뒤."""
    terms = interview_vocabulary(
        company="A",
        role="B",
        name="박지원",
        application=_application("TensorRT"),
        stored=["산학협력", "박지원"],   # 추출이 이름을 다시 내도 한 번만
    )
    assert terms[:3] == ["박지원", "A", "B"]
    assert terms.index("산학협력") < terms.index("TensorRT")
    assert terms.count("박지원") == 1


def test_질문_태그도_그날의_주제어다() -> None:
    terms = interview_vocabulary(
        company="A",
        role="B",
        application=[],
        questions=[{"tags": ["센서 융합", "수치 검증"]}],
    )
    assert "센서 융합" in terms and "수치 검증" in terms


def test_중복은_한_번만_넣는다() -> None:
    terms = interview_vocabulary(
        company="DMILLION",
        role="B",
        application=_application("DMILLION dmillion"),
    )
    assert sum(1 for t in terms if t.lower() == "dmillion") == 1


# ── 브리지가 무엇을 쓰는가 ───────────────────────────────────────────────


def test_준비된_어휘에_키워드를_합친다() -> None:
    """추출만 쓰면 확실한 낱말이 빠질 수 있다 — 실측에서 이름이 빠진 채
    면접이 돌아 전사가 깨졌다. 키워드가 앞, 추출이 그 다음이다."""
    data = InterviewData(
        company="A",
        role="B",
        name="박지원",
        application=_application("TensorRT로 최적화했습니다"),
        report=[],
        uncertain=[],
        vocabulary=["산학협력"],
    )
    terms = _vocabulary_for(data)
    assert terms[:3] == ["박지원", "A", "B"]
    assert "산학협력" in terms          # 추출 어휘
    assert "TensorRT" in terms          # 규칙 키워드도 같이


def test_계정_이름이_등록_이름보다_앞선다() -> None:
    """등록 때 이름이 비어 있던 면접이 실제로 있다 — 면접 시점의 계정
    프로필 이름으로 채운다."""
    data = InterviewData(
        company="A", role="B", name="", application=[], report=[], uncertain=[],
        vocabulary=["산학협력"],
    )
    assert _vocabulary_for(data, name="박지원")[0] == "박지원"


def test_준비된_어휘가_없으면_규칙_폴백으로_만든다() -> None:
    """추출이 실패했거나 그 단계가 없던 옛 면접 — 이름 없이 시작하지 않는다."""
    data = InterviewData(
        company="A",
        role="B",
        name="박지원",
        application=_application("TensorRT로 최적화했습니다"),
        report=[],
        uncertain=[],
    )
    terms = _vocabulary_for(data)
    assert terms[0] == "박지원"
    assert "TensorRT" in terms
