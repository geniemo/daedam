"""면접 단계와 시간 예산 — 순수 로직 (ADK·FastAPI import 금지).

단계 전환의 최종 보장은 서버 코드에 있다. 모델의 내부 시계나 자율 판단에
맡기지 않는다. 모델은 자기가 어느 단계에 있는지 '통보받을' 뿐이다.

종료는 여기 없다. 면접을 끝내는 것은 지원자의 종료 버튼이고, 시간 예산은
단계를 옮기는 데만 쓴다 — 마지막 단계 예산을 넘어도 마지막 단계에 머문다.

경과 시간은 호출자가 주입한다(상태 없음 → 테스트 용이).
"""

from __future__ import annotations

from dataclasses import dataclass

# README §Screens 기준 4단계. 이름은 프론트 §5 단계 카드·§8 상단 라벨과 일치해야 한다.
STAGE_NAMES: tuple[str, ...] = ("자기소개", "직무역량", "인성·컬처핏", "마무리")


@dataclass(frozen=True)
class Profile:
    """단계별 시간 예산(초)."""

    name: str
    budgets: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.budgets) != len(STAGE_NAMES):
            raise ValueError(f"단계 수 불일치: {len(self.budgets)} != {len(STAGE_NAMES)}")


# demo  — 시연용. 발표 10분 중 시연에 5분을 쓴다. 자기소개 → 직무 → 마무리이고
#         인성 단계는 건너뛴다(예산 0 — 시간 경과로 즉시 넘어간다). 직무 180초에
#         뼈대질문 2개 + 파볼 곳이 들어가려면 답변이 20~30초로 짧아야 한다
#         (실측: 답변을 짧게 한 판이 직무 구간 179초).
# dev    — 개발용. 8분이면 Live API 커넥션 수명(~10분) 안쪽이라 재연결 경로를
#         타지 않는다. 네 단계를 다 돈다.
# full   — 제품 정의. 디자인 핸드오프의 "15~20분"에 맞춘다.
# probe  — 단계 전환 실증용. 실 Gemini 연결로도 2분 안에 네 단계를 다 지난다.

#: 하드캡을 예산의 몇 배로 두는가. 정상적으로 끝나는 면접은 예산 근처에서
#: 끝나므로 2배는 절대 안 닿는다. 이 값에 닿았다는 것은 누가 창을 닫고
#: 잊었다는 뜻이다.
_HARD_CAP_MULTIPLIER = 2.0

PROFILES: dict[str, Profile] = {
    "demo": Profile("demo", (60.0, 180.0, 0.0, 60.0)),
    "dev": Profile("dev", (90.0, 180.0, 150.0, 60.0)),
    "full": Profile("full", (120.0, 420.0, 360.0, 120.0)),
    "probe": Profile("probe", (20.0, 20.0, 20.0, 20.0)),
}

DEFAULT_PROFILE = "demo"


class SessionFlow:
    """경과 시간 → 단계 / 잔여 판정. 상태를 갖지 않는다."""

    def __init__(self, profile: Profile | str = DEFAULT_PROFILE) -> None:
        self.profile = PROFILES[profile] if isinstance(profile, str) else profile
        bounds: list[float] = []
        acc = 0.0
        for seconds in self.profile.budgets:
            acc += seconds
            bounds.append(acc)
        self._bounds = tuple(bounds)

    @property
    def total_budget_s(self) -> float:
        """모든 단계 예산의 합 — 이 면접이 원래 걸려야 하는 길이."""
        return sum(self.profile.budgets)

    @property
    def hard_cap_s(self) -> float:
        """서버가 끊는 지점(초). 예산의 2배 — `over_hard_cap` 참고."""
        return self.total_budget_s * _HARD_CAP_MULTIPLIER

    def over_hard_cap(self, elapsed_s: float) -> bool:
        """예산을 크게 넘겼는가 — 서버가 끊어야 하는 지점.

        면접을 끝내는 것은 지원자의 종료 버튼이고 그 설계는 그대로다. 이건
        그 아래 깔아 두는 백스톱이다: 창을 닫아 두고 잊었거나 모델이 끝맺지
        못한 면접이 무한히 도는 것을 막는다.

        필요한 이유가 돈이다. Live API는 **턴마다 누적 맥락 전체를 다시
        과금하므로**(docs/specs/2026-08-23-credit-pricing.md) 상한이 없으면
        면접 한 판의 원가에 천장이 없다.

        예산의 2배로 잡은 것은 정상 면접을 절대 건드리지 않기 위해서다 —
        full 프로필(17분)이면 34분, demo(5분)면 10분이다.
        """
        return elapsed_s > self.hard_cap_s

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
