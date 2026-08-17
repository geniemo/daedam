"""전사 어휘 힌트 테스트.

실측에서 이름과 기술 용어가 계속 깨졌다 — "박지원"→"박지훈",
"Jetson AGX Orin"→"Jeston Ajax 올인". 그 낱말들은 면접 전에 이미 손에 있다.
"""

from daedam.interview.vocabulary import interview_vocabulary


def _application(body: str = "") -> list[dict]:
    return [
        {
            "part": "경험",
            "items": [{"title": "DMILLION 인턴", "body": body}],
        }
    ]


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
