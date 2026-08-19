"""파볼 곳 추출 테스트.

Grok은 부르지 않는다 — 대역으로 보는 것은 배관이다. 빈 답변을 거르는가,
실패하면 빈 목록인가, 상한을 지키는가, 프롬프트에 질문과 답변이 실리는가.
"""

from types import SimpleNamespace

from daedam.interview.probes import PROBE_COUNT, Probe, extract_probes, probe_prompt


class _StubClient:
    """구조화 출력을 흉내 낸다. 보낸 프롬프트를 붙잡아 검증에 쓴다."""

    def __init__(self, probes: list[tuple[str, str]] | Exception, leads_with: str = "") -> None:
        self._probes = probes
        self._leads_with = leads_with
        self.prompt: str | None = None
        self.beta = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(parse=self._parse))
        )

    def _parse(self, *, model, messages, response_format):  # noqa: ANN001
        self.prompt = messages[0]["content"]
        if isinstance(self._probes, Exception):
            raise self._probes
        parsed = SimpleNamespace(
            probes=[SimpleNamespace(topic=t, hint=h) for t, h in self._probes],
            leads_with=self._leads_with,
        )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))]
        )


QUESTION = "두 백본을 결합할 기준은 어떻게 정하셨나요?"
ANSWER = "구조적 결함은 YOLO로, 질감적 결함은 EfficientNet으로 추출해서 결합했습니다."


def test_답변에서_파볼_곳을_뽑는다() -> None:
    client = _StubClient([("선정 근거", "왜 그 백본인지 안 나왔다"), ("결합 방식", "어떻게 합쳤는지 없다")])
    result = extract_probes(question=QUESTION, answer=ANSWER, client=client)
    assert result.probes == [
        Probe("선정 근거", "왜 그 백본인지 안 나왔다"),
        Probe("결합 방식", "어떻게 합쳤는지 없다"),
    ]
    assert result.leads_with == ""


def test_빈_답변이면_부르지_않는다() -> None:
    """답변이 없는데 파볼 곳을 물으면 LLM이 지어낸다."""
    client = _StubClient([("x", "y")])
    assert extract_probes(question=QUESTION, answer="   ", client=client).probes == []
    assert client.prompt is None


def test_실패하면_빈_목록이다() -> None:
    """면접 중 LLM 호출은 면접을 멈출 권리가 없다."""
    client = _StubClient(RuntimeError("xAI 타임아웃"))
    assert extract_probes(question=QUESTION, answer=ANSWER, client=client).probes == []


def test_상한을_넘으면_앞에서_자른다() -> None:
    """중요한 것 먼저 내라고 했으니 앞의 것이 남는다."""
    client = _StubClient([("a", "1"), ("b", "2"), ("c", "3")])
    probes = extract_probes(question=QUESTION, answer=ANSWER, client=client).probes
    assert len(probes) == PROBE_COUNT
    assert probes[0].topic == "a"


def test_빈_항목은_거른다() -> None:
    client = _StubClient([("선정 근거", ""), ("", "힌트만"), ("결합 방식", "어떻게 합쳤는지")])
    probes = extract_probes(question=QUESTION, answer=ANSWER, client=client).probes
    assert probes == [Probe("결합 방식", "어떻게 합쳤는지")]


def test_프롬프트에_질문과_답변이_실린다() -> None:
    prompt = probe_prompt(question=QUESTION, answer=ANSWER)
    assert QUESTION in prompt and ANSWER in prompt
    # 새 주제를 끌어오지 말라는 원칙이 남아 있어야 한다.
    assert "이 답변 안에서" in prompt


# ── 이어갈 경험 ──────────────────────────────────────────────────────────

CANDIDATES = ["디밀리언 사출 불량 판별에서 두 백본을…", "대시 랩 딥페이크 탐지에서…"]


def test_후보_중_하나를_그대로_옮기면_받는다() -> None:
    client = _StubClient([("x", "y")], leads_with=CANDIDATES[1])
    result = extract_probes(
        question=QUESTION, answer=ANSWER, experiences=CANDIDATES, client=client
    )
    assert result.leads_with == CANDIDATES[1]


def test_후보에_없는_것을_적으면_버린다() -> None:
    """그대로 옮기라고 했는데 안 맞으면 지어낸 것이다."""
    client = _StubClient([("x", "y")], leads_with="전혀 다른 경험")
    result = extract_probes(
        question=QUESTION, answer=ANSWER, experiences=CANDIDATES, client=client
    )
    assert result.leads_with == ""


def test_후보가_있으면_프롬프트에_실린다() -> None:
    prompt = probe_prompt(question=QUESTION, answer=ANSWER, experiences=CANDIDATES)
    assert "이어갈 경험 후보" in prompt
    for c in CANDIDATES:
        assert c in prompt


def test_후보가_없으면_그_문단이_없다() -> None:
    assert "이어갈 경험 후보" not in probe_prompt(question=QUESTION, answer=ANSWER)
