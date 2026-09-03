"""기동 전 설정 점검 테스트.

운영 모드에서 빠진 설정으로 뜨는 서버는 인증 없는 공개 서버가 된다. 그 길을
막는 것이 이 모듈의 유일한 일이라, 시험할 것은 둘이다 — 갖춰지면 통과하고,
하나라도 빠지면 그 항목을 이름 붙여 거부하는가.
"""

import pytest

from daedam.server import preflight

_PRODUCTION = {
    "DAEDAM_ENV": "production",
    "KAKAO_CLIENT_ID": "id",
    "KAKAO_CLIENT_SECRET": "secret",
    "SESSION_SECRET": "x" * 43,
    "COOKIE_SECURE": "1",
    "SERVER_BASE_URL": "https://daedam.example",
    "APP_BASE_URL": "",
    "GOOGLE_API_KEY": "key",
    "RESEARCH_MODE": "live",
}


def test_갖춰진_운영_설정은_통과한다() -> None:
    assert preflight.production_problems(_PRODUCTION) == []
    assert preflight.enforce(_PRODUCTION) == "production"


def test_모드를_안_적으면_운영이다() -> None:
    """안전한 쪽이 기본이어야 한다 — 빈 값도 운영."""
    assert preflight.mode({}) == "production"
    assert preflight.mode({"DAEDAM_ENV": "  "}) == "production"


def test_모르는_모드는_거부한다() -> None:
    with pytest.raises(SystemExit):
        preflight.mode({"DAEDAM_ENV": "prod"})


@pytest.mark.parametrize(
    ("key", "value", "word"),
    [
        ("KAKAO_CLIENT_SECRET", "", "로그인 제공자"),
        ("SESSION_SECRET", "short", "SESSION_SECRET"),
        ("COOKIE_SECURE", "0", "COOKIE_SECURE"),
        ("SERVER_BASE_URL", "http://localhost:8000", "SERVER_BASE_URL"),
        ("APP_BASE_URL", "http://localhost:5173", "APP_BASE_URL"),
        ("GOOGLE_API_KEY", "", "GOOGLE_API_KEY"),
        ("RESEARCH_MODE", "fixture", "RESEARCH_MODE"),
    ],
)
def test_빠진_항목을_이름_붙여_돌려준다(key: str, value: str, word: str) -> None:
    env = {**_PRODUCTION, key: value}
    problems = preflight.production_problems(env)
    assert len(problems) == 1 and word in problems[0]


def test_빠진_것을_한_번에_전부_돌려준다() -> None:
    """하나 고치고 다시 떠 보기를 반복하게 만들면 안 된다."""
    # 빈 환경에서 APP_BASE_URL은 "비어 있음"이라 정상 — 나머지 여섯이 전부 나온다.
    problems = preflight.production_problems({})
    assert len(problems) == 6
    assert len(preflight.production_problems({"APP_BASE_URL": "http://localhost:5173"})) == 7


def test_운영에서_빠지면_기동을_거부한다() -> None:
    with pytest.raises(SystemExit):
        preflight.enforce({**_PRODUCTION, "COOKIE_SECURE": "0"})


def test_구글만_있어도_제공자로_친다() -> None:
    env = {**_PRODUCTION, "KAKAO_CLIENT_ID": "", "KAKAO_CLIENT_SECRET": ""}
    env.update(GOOGLE_CLIENT_ID="id", GOOGLE_CLIENT_SECRET="secret")
    assert preflight.production_problems(env) == []


def test_개발_모드는_아무것도_요구하지_않는다() -> None:
    """로컬은 로그인 없이, http로, fixture로 떠야 한다 — 지금까지의 동작."""
    assert preflight.enforce({"DAEDAM_ENV": "development"}) == "development"
