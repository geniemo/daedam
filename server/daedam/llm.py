"""오프라인 LLM 호출의 공통 자리 — 클라이언트와 모델 선택.

**Gemini의 OpenAI 호환 엔드포인트를 쓴다.** 앞서는 Grok(xAI)이었는데,
호출 형태가 `chat.completions.parse(response_format=<Pydantic>)`로 같아서
base_url과 모델만 바꾸면 코드가 그대로 돈다. 벤더가 하나로 줄면 키도 하나,
장애 지점도 하나다.

모델은 두 갈래다. 갈리는 기준은 **면접 중인가**다.

  FAST     면접이 도는 중에 불린다 — 지연이 곧 침묵이다. 파볼 곳 추출이
           여기 속한다. 실측(같은 프롬프트 3회 중앙값):
             gemini-3.5-flash-lite   1.20초   ← 선택
             gemini-3.1-flash-lite   1.18초
             gemini-3.7-flash        4.16초
             gemini-2.5-flash        7.39초
           앞서 쓰던 grok-4.20-non-reasoning이 약 2초였으므로 더 빨라졌다.

  QUALITY  면접 밖에서 배치로 돈다 — 질문 풀 생성, 전사 어휘 추출, 답변 코칭.
           몇 초 더 걸려도 되고 결과의 질이 제품의 질이다.

`-latest` 별칭을 쓰지 않는다. 뒤에서 모델이 바뀌면 프롬프트를 그대로 두고도
결과가 달라지는데, 그걸 알아챌 방법이 없다.

확인 경로: Gemini OpenAI 호환 엔드포인트에서 `client.beta.chat.completions.parse`와
Pydantic response_format이 동작하는 것을 실호출로 확인했다.
"""

from __future__ import annotations

import os
from typing import Any

#: OpenAI SDK가 Gemini를 보게 하는 주소.
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

#: 면접 중에 불리는 호출. 1초대여야 한다.
MODEL_FAST = "gemini-3.5-flash-lite"

#: 면접 밖 배치. 지연보다 질이 중요하다.
MODEL_QUALITY = "gemini-3.7-flash"


def text_client(timeout_s: float | None = None) -> Any:
    """Gemini를 보는 OpenAI 호환 클라이언트.

    Args:
        timeout_s: 면접 중 호출은 반드시 준다 — 응답이 늦으면 면접이 멈추므로
            기다리느니 빈 결과로 넘어가는 편이 낫다. 배치에는 필요 없다.

    음성 면접(Live)과 임베딩은 google-genai를 직접 쓴다. 여기는 텍스트
    배치 호출만이다 — 그쪽은 OpenAI 호환 계층에 없는 기능을 쓴다.
    """
    from openai import OpenAI

    return OpenAI(
        api_key=os.environ["GOOGLE_API_KEY"], base_url=BASE_URL, timeout=timeout_s
    )
