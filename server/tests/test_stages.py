"""단계·시간 예산 판정 테스트.

단계 전환과 종료의 최종 보장은 서버 코드에 있다(모델의 자율 판단에 맡기지
않는다). 그 판정이 여기 전부 들어 있으므로 경계값을 촘촘히 고정한다.
"""

import pytest

from daedam.interview.stages import (
    PROFILES,
    STAGE_NAMES,
    Profile,
    SessionFlow,
)


@pytest.fixture
def demo() -> SessionFlow:
    """dev 프로필: 90 / 180 / 150 / 60초 → 누적 경계 90, 270, 420, 480. 네 단계를
    다 돈다. fixture 이름은 이 프로필이 demo였을 때의 것이다."""
    return SessionFlow("dev")


# ── 단계 판정 ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "elapsed, expected",
    [
        (0.0, 0),  # 시작
        (89.9, 0),  # 1단계 마지막 순간
        (90.0, 1),  # 경계는 다음 단계에 속한다 (elapsed < bound)
        (269.9, 1),
        (270.0, 2),
        (419.9, 2),
        (420.0, 3),
    ],
)
def test_경계에서_단계가_넘어간다(demo: SessionFlow, elapsed: float, expected: int) -> None:
    assert demo.stage_index_at(elapsed) == expected


def test_마지막_단계_예산을_넘어도_마지막_단계를_유지한다(demo: SessionFlow) -> None:
    """예산 총합(480초)을 넘겨도 5번째 단계는 없다 — 면접을 끝내는 것은 지원자의
    종료 버튼이고, 그때까지 마지막 단계에 머문다."""
    assert demo.stage_index_at(480.0) == 3
    assert demo.stage_index_at(10_000.0) == 3


def test_단계_이름은_프론트_라벨과_일치한다(demo: SessionFlow) -> None:
    assert demo.stage_name_at(0.0) == "자기소개"
    assert demo.stage_name_at(100.0) == "직무역량"
    assert demo.stage_name_at(300.0) == "인성·컬처핏"
    assert demo.stage_name_at(450.0) == "마무리"


# ── 잔여 시간 ────────────────────────────────────────────────────────────


def test_현재_단계의_잔여_시간(demo: SessionFlow) -> None:
    assert demo.stage_remaining_s(0.0) == pytest.approx(90.0)
    assert demo.stage_remaining_s(80.0) == pytest.approx(10.0)
    # 2단계 진입 직후 — 남은 건 2단계 예산 전체(180초)
    assert demo.stage_remaining_s(90.0) == pytest.approx(180.0)


def test_마지막_단계_예산_초과시_잔여는_0(demo: SessionFlow) -> None:
    assert demo.stage_remaining_s(600.0) == 0.0


# ── 프로필 ───────────────────────────────────────────────────────────────


def test_두_프로필_모두_4단계여야_한다() -> None:
    """단계 수는 프론트(§5 단계 카드 4개, §8 진행 바 4개)와 묶여 있다."""
    for profile in PROFILES.values():
        assert len(profile.budgets) == len(STAGE_NAMES) == 4


def test_demo는_Live_커넥션_수명_안쪽이어야_한다() -> None:
    """Live API 커넥션 수명이 ~10분. 예산 총합이 그 안이면 시연 중 단계 전환이
    재연결 경로를 타지 않는다."""
    assert sum(PROFILES["demo"].budgets) <= 600.0
    assert sum(PROFILES["dev"].budgets) <= 600.0


def test_단계_수가_안_맞으면_생성이_실패한다() -> None:
    with pytest.raises(ValueError, match="단계 수 불일치"):
        Profile("broken", (60.0, 60.0))


def test_문자열과_객체_둘_다로_생성할_수_있다() -> None:
    assert SessionFlow("full").profile == SessionFlow(PROFILES["full"]).profile


def test_demo는_인성_단계를_건너뛴다() -> None:
    """시연은 5~6분이라 자기소개 → 직무 → 마무리다. 인성 예산이 0이면 시간 경과로
    즉시 넘어간다 — 단계 구조는 그대로 두고 예산만으로 건너뛴다."""
    demo = SessionFlow("demo")
    assert demo.stage_index_at(299.9) == 1   # 직무 끝 직전
    assert demo.stage_index_at(300.0) == 3   # 인성(예산 0)을 지나 바로 마무리
    assert demo.stage_remaining_s(300.0) == 60.0
