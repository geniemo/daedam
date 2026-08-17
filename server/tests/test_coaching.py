"""답변 평가·코칭 테스트.

Grok은 부르지 않는다 — 오프라인 배치라 대역으로 충분하고, 실제 호출은
부트캠프 협찬 토큰을 쓴다.
"""

from types import SimpleNamespace

from daedam.eval.coaching import (
    AnswerReview,
    Exchange,
    InterviewReview,
    coaching_prompt,
    evaluate,
    exchanges_from,
)


def _transcript(*utterances):
    return {
        "utterances": [
            {"speaker": speaker, "text": text, "at": float(index)}
            for index, (speaker, text) in enumerate(utterances)
        ]
    }


class _StubClient:
    """구조화 출력을 흉내 낸다. 보낸 프롬프트를 붙잡아 검증에 쓴다."""

    def __init__(self, review: InterviewReview) -> None:
        self.review = review
        self.prompt: str | None = None
        self.beta = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(parse=self._parse))
        )

    def _parse(self, *, model, messages, response_format):  # noqa: ANN001
        self.prompt = messages[0]["content"]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(parsed=self.review))]
        )


def _review(*scores: int) -> InterviewReview:
    return InterviewReview(
        answers=[
            AnswerReview(
                question=f"질문 {index}",
                score=score,
                strength="근거를 들었습니다",
                gap="수치가 없습니다",
                suggestion="측정 방법을 덧붙이세요",
            )
            for index, score in enumerate(scores, start=1)
        ],
        summary="총평",
        strengths=["구조가 분명함"],
        improvements=["수치 근거 보강"],
    )


def test_면접관_뒤의_답변이_그_질문의_답이다() -> None:
    pairs = exchanges_from(
        _transcript(
            ("interviewer", "자기소개 부탁드립니다."),
            ("applicant", "박지원입니다."),
            ("interviewer", "지원 이유는요?"),
            ("applicant", "방향성에 공감했습니다."),
        )
    )
    assert pairs == [
        Exchange("자기소개 부탁드립니다.", "박지원입니다."),
        Exchange("지원 이유는요?", "방향성에 공감했습니다."),
    ]


def test_면접관이_연달아_말하면_마지막이_질문이다() -> None:
    """인사와 질문이 한 턴에 오기도 한다 — 첫 번째를 잡으면 인사가 붙는다."""
    pairs = exchanges_from(
        _transcript(
            ("interviewer", "안녕하세요."),
            ("interviewer", "먼저 자기소개 부탁드립니다."),
            ("applicant", "박지원입니다."),
        )
    )
    assert pairs == [Exchange("먼저 자기소개 부탁드립니다.", "박지원입니다.")]


def test_질문_없이_나온_말은_짝이_없다() -> None:
    assert exchanges_from(_transcript(("applicant", "안녕하세요"))) == []


def test_총점은_답변_점수의_평균이다() -> None:
    """총점을 따로 받으면 그 숫자가 어디서 나왔는지 설명할 수 없다."""
    client = _StubClient(_review(80, 60, 70))
    coaching = evaluate(
        company="SK하이닉스",
        role="기반기술",
        transcript=_transcript(
            ("interviewer", "질문 1"),
            ("applicant", "충분히 긴 답변입니다 하나"),
            ("interviewer", "질문 2"),
            ("applicant", "충분히 긴 답변입니다 둘"),
            ("interviewer", "질문 3"),
            ("applicant", "충분히 긴 답변입니다 셋"),
        ),
        client=client,
    )
    assert coaching.score == 70


def test_짧은_답변도_평가한다() -> None:
    """답변이 짧았다는 것 자체가 해줘야 할 피드백이다.

    실측에서 자기소개 답변이 "안녕하세요. 박지원입니다." 13자였다. 이걸 빼면
    코칭이 그 얘기를 못 한다.
    """
    client = _StubClient(_review(40, 80))
    evaluate(
        company="SK하이닉스",
        role="기반기술",
        transcript=_transcript(
            ("interviewer", "자기소개 부탁드립니다."),
            ("applicant", "안녕하세요. 박지원입니다."),
            ("interviewer", "질문 2"),
            ("applicant", "이 답변은 평가할 만큼 깁니다"),
        ),
        client=client,
    )
    assert "안녕하세요. 박지원입니다." in client.prompt


def test_전사_잡음은_평가에서_뺀다() -> None:
    """기침이 '어' 한 글자로 잡히는 것까지 답변으로 세면 안 된다."""
    client = _StubClient(_review(80))
    evaluate(
        company="SK하이닉스",
        role="기반기술",
        transcript=_transcript(
            ("interviewer", "질문 1"),
            ("applicant", "어"),
            ("interviewer", "질문 2"),
            ("applicant", "이 답변은 평가할 만큼 깁니다"),
        ),
        client=client,
    )
    assert "지원자: 어\n" not in client.prompt
    assert "이 답변은 평가할 만큼 깁니다" in client.prompt


def test_평가할_답변이_없으면_부르지_않는다() -> None:
    """점수 0과 '평가 대상 없음'은 다르다."""
    client = _StubClient(_review(80))
    coaching = evaluate(
        company="SK하이닉스",
        role="기반기술",
        transcript=_transcript(("interviewer", "자기소개 부탁드립니다.")),
        client=client,
    )
    assert coaching.score is None
    assert client.prompt is None
    assert coaching.review.answers == []


def test_프롬프트에_주고받은_내용이_그대로_실린다() -> None:
    prompt = coaching_prompt(
        company="SK하이닉스",
        role="기반기술",
        exchanges=[Exchange("자기소개 부탁드립니다.", "박지원입니다.")],
    )
    assert "SK하이닉스 기반기술" in prompt
    assert "자기소개 부탁드립니다." in prompt
    assert "박지원입니다." in prompt
    # 근거 없는 칭찬을 막는 원칙이 프롬프트에 남아 있어야 한다.
    assert "실제로 한 말만" in prompt


def test_화면이_읽을_형태로_바꾼다() -> None:
    client = _StubClient(_review(90))
    coaching = evaluate(
        company="A",
        role="B",
        transcript=_transcript(
            ("interviewer", "질문"), ("applicant", "충분히 긴 답변입니다")
        ),
        client=client,
    )
    payload = coaching.as_dict()
    assert payload["score"] == 90
    assert payload["strengths"] == ["구조가 분명함"]
    assert payload["answers"][0]["suggestion"] == "측정 방법을 덧붙이세요"
