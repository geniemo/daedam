"""기동 전 설정 점검 — 운영 모드에서는 빠진 설정이 있으면 뜨지 않는다.

앞서는 로그인 키가 안 읽히면 경고 한 줄을 남기고 **인증 없는 단일 사용자
모드로 기동**했다. 개발에서는 편했지만 배포에서는 `.env` 하나 잘못 두면
인터넷의 모든 방문자가 한 계정을 공유하는 서버가 된다 — 그리고 그 사실은
로그를 읽어야 안다(docs/deploy.md가 그 증상을 이미 적어 둘 만큼 실제로
겪었다). 안전한 쪽이 기본이어야 한다: 모드를 명시하지 않으면 운영으로 보고,
운영에 필요한 설정이 하나라도 빠지면 기동을 거부한다.

모드는 `DAEDAM_ENV`로 정한다.

    production   기본값. `production_problems`의 항목이 전부 갖춰져야 뜬다.
    development  로컬 개발. 로그인 없이, http로, fixture 리서치로 뜰 수 있다.

배포 유닛(deploy/daedam.service)이 `DAEDAM_ENV=production`을 직접 준다 —
`.env`가 통째로 안 읽히는 사고에서도 운영으로 판정되어 뜨지 않게.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping

from .auth import configured_providers

logger = logging.getLogger(__name__)

MODES = ("production", "development")

#: `secrets.token_urlsafe(32)`가 43자다. 이보다 짧으면 손으로 친 값이다.
_SECRET_MIN_CHARS = 32


def mode(env: Mapping[str, str] = os.environ) -> str:
    """`DAEDAM_ENV`. 비어 있으면 production — 안전한 쪽이 기본이다."""
    value = env.get("DAEDAM_ENV", "").strip() or "production"
    if value not in MODES:
        raise SystemExit(
            f"DAEDAM_ENV={value!r}는 모르는 값입니다 — production 또는 development"
        )
    return value


def production_problems(env: Mapping[str, str] = os.environ) -> list[str]:
    """운영에서 빠지면 안 되는 설정 중 빠진 것들. 비어 있으면 기동해도 된다.

    한 번에 전부 돌려준다 — 하나 고치고 다시 떠 보고를 반복하지 않게.
    """
    problems: list[str] = []
    if not configured_providers(env):
        problems.append(
            "로그인 제공자가 없습니다 — KAKAO_CLIENT_ID/SECRET 또는 "
            "GOOGLE_CLIENT_ID/SECRET. 없으면 모든 방문자가 한 계정을 공유합니다"
        )
    if len(env.get("SESSION_SECRET", "")) < _SECRET_MIN_CHARS:
        problems.append(
            f"SESSION_SECRET이 없거나 {_SECRET_MIN_CHARS}자보다 짧습니다 — "
            "비우면 재시작마다 전원이 로그아웃됩니다"
        )
    if env.get("COOKIE_SECURE") != "1":
        problems.append("COOKIE_SECURE=1이 아닙니다 — 세션 쿠키가 평문 HTTP로도 나갑니다")
    if not env.get("SERVER_BASE_URL", "").startswith("https://"):
        problems.append(
            "SERVER_BASE_URL이 https:// 주소가 아닙니다 — OAuth 콜백이 이 주소로 나갑니다"
        )
    app_url = env.get("APP_BASE_URL", "")
    if app_url and not app_url.startswith("https://"):
        problems.append(
            "APP_BASE_URL이 https:// 주소가 아닙니다 — 배포에서는 프론트가 같은 "
            "오리진이라 비웁니다. 남겨 두면 로그인 뒤 개발 서버로 튑니다"
        )
    if not env.get("GOOGLE_API_KEY"):
        problems.append("GOOGLE_API_KEY가 없습니다 — 면접·리서치·코칭이 전부 이 키를 씁니다")
    if env.get("RESEARCH_MODE", "fixture") != "live":
        problems.append(
            "RESEARCH_MODE=live가 아닙니다 — fixture는 가짜 리포트에 크레딧을 물립니다"
        )
    return problems


def enforce(env: Mapping[str, str] = os.environ) -> str:
    """모드를 판정하고, 운영인데 설정이 빠졌으면 프로세스를 끝낸다.

    Returns:
        판정된 모드. 개발이면 경고 한 줄을 남기고 그대로 돌려준다.

    Raises:
        SystemExit: 운영 모드인데 빠진 설정이 있을 때. 빠진 항목은 그 전에
            ERROR 로그로 한 줄씩 남는다.
    """
    current = mode(env)
    if current == "development":
        logger.warning(
            "개발 모드(DAEDAM_ENV=development) — 로그인·HTTPS·실제 리서치 없이 뜰 수 있습니다"
        )
        return current
    problems = production_problems(env)
    if problems:
        for problem in problems:
            logger.error("운영 설정 누락: %s", problem)
        raise SystemExit(
            f"운영 설정 {len(problems)}건이 갖춰지지 않아 기동을 거부합니다. "
            "위 로그를 보고 채우십시오 (로컬 개발이면 DAEDAM_ENV=development)"
        )
    logger.info("운영 모드 — 설정 점검 통과")
    return current
