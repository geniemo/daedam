"""면접 단계와 시간 예산 — 순수 로직 (ADK·FastAPI import 금지).

단계 전환과 종료의 최종 보장은 서버 코드에 있다. 모델의 내부 시계나 자율
판단에 맡기지 않는다. 모델은 자기가 어느 단계에 있는지 '통보받을' 뿐이다.

경과 시간은 호출자가 주입한다(상태 없음 → 테스트 용이).
"""

from __future__ import annotations

from dataclasses import dataclass

# README §Screens 기준 4단계. 이름은 프론트 §5 단계 카드·§8 상단 라벨과 일치해야 한다.
STAGE_NAMES: tuple[str, ...] = ("자기소개", "직무역량", "인성·컬처핏", "마무리")


@dataclass(frozen=True)
class Profile:
    """단계별 시간 예산(초)과 하드캡."""

    name: str
    budgets: tuple[float, ...]
    hard_cap_s: float

    def __post_init__(self) -> None:
        if len(self.budgets) != len(STAGE_NAMES):
            raise ValueError(f"단계 수 불일치: {len(self.budgets)} != {len(STAGE_NAMES)}")


# demo  — 개발·시연용. 8분이면 Live API 커넥션 수명(~10분) 안쪽이라
#         시연 도중 재연결 경로를 타지 않는다.
# full   — 제품 정의. 디자인 핸드오프의 "15~20분"에 맞춘다.
# probe  — 종료 경로 실증용. 실 Gemini 연결로도 한 판이 2분 안에 끝나서,
#          9분짜리 면접을 다시 돌리지 않고 마무리·종료를 확인할 수 있다.
PROFILES: dict[str, Profile] = {
    "demo": Profile("demo", (90.0, 180.0, 150.0, 60.0), hard_cap_s=540.0),
    "full": Profile("full", (120.0, 420.0, 360.0, 120.0), hard_cap_s=1200.0),
    "probe": Profile("probe", (20.0, 20.0, 20.0, 20.0), hard_cap_s=100.0),
}

DEFAULT_PROFILE = "demo"


class SessionFlow:
    """경과 시간 → 단계 / 잔여 / 종료 판정. 상태를 갖지 않는다."""

    def __init__(self, profile: Profile | str = DEFAULT_PROFILE) -> None:
        self.profile = PROFILES[profile] if isinstance(profile, str) else profile
        bounds: list[float] = []
        acc = 0.0
        for seconds in self.profile.budgets:
            acc += seconds
            bounds.append(acc)
        self._bounds = tuple(bounds)

    @property
    def hard_cap_s(self) -> float:
        return self.profile.hard_cap_s

    def stage_index_at(self, elapsed_s: float) -> int:
        """경과 시간이 속한 단계. 마지막 단계 예산을 넘어도 마지막 단계를 유지한다."""
        for i, bound in enumerate(self._bounds):
            if elapsed_s < bound:
                return i
        return len(STAGE_NAMES) - 1

    def stage_name_at(self, elapsed_s: float) -> str:
        return STAGE_NAMES[self.stage_index_at(elapsed_s)]

    def stage_remaining_s(self, elapsed_s: float) -> float:
        """현재 단계에 남은 시간. 마지막 단계 예산을 넘었으면 0."""
        return max(0.0, self._bounds[self.stage_index_at(elapsed_s)] - elapsed_s)

    def should_end(self, elapsed_s: float) -> bool:
        """하드캡 초과 — 서버가 종료를 강제해야 하는 시점."""
        return elapsed_s >= self.hard_cap_s
