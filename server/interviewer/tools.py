"""면접 툴 — 질문 배달과 회사 지식 검색.

면접을 끝내는 것은 서버도 모델도 아니라 지원자다 — 화면의 종료 버튼. 그래서
여기에는 끝내는 툴이 없고, 시간 예산은 단계를 옮기는 데만 쓴다.

질문은 전부 `ask_question`을 지난다. 모델의 자율을 뺏자는 게 아니라, **무엇을
물을지**의 판단을 프롬프트가 아니라 툴 쪽에 두려는 것이다 — 대화가 길어질수록
시스템 프롬프트의 영향은 그 뒤에 쌓인 대화에 묻히지만, 툴 선언과 툴 출력은
매 호출마다 새로 도착한다.

**꼬리질문의 방향은 서버가 정한다.** 뼈대질문에 답변이 오면 서버가 그 답변을
읽고(`daedam.interview.probes`) 파볼 곳을 둘 고른다. 모델은 그 주제와 힌트를
받아 제 문장으로 묻고, 답을 들었는지(`answered`)를 신고한다. 파볼 곳이 다
닫히면 다음 뼈대질문이다.

앞서는 모델이 초안(draft_question)을 들고 오고 서버가 중요도·문턱·상한으로
허가·반려만 했다. 그랬더니 꼬리질문이 답변에 붙지 않았다 — "직접 눈으로 보고
분류했다"를 듣고도 다음 키워드로 넘어갔다(실측). 게이트는 "물어도 되는가"만 보고
"무엇을 물을지"는 모델 혼자 즉석에서 정했기 때문이다. 그리고 모델이 물을 것을
툴보다 먼저 알고 있으니 툴보다 먼저 말해서 같은 질문이 두 번 나갔다. 방향을
서버가 주면 모델은 툴이 돌아오기 전에 물을 것을 모르므로 미리 말할 수 없다.

응답은 어느 경로든 **물을 것 하나 + 다음 행동 한 문장**이다. 뼈대질문이면 문장을
그대로(`ask`), 파볼 곳이면 주제와 힌트(`probe`·`hint`)를 준다. 그 밖의 것은 싣지
않는다 — 네이티브 오디오 모델은 텍스트를 읽고 골라내는 것이 아니라 들어온 것에
끌려가서, 행동을 못 바꾸는 문장은 입으로 새는 통로일 뿐이다(실측: "지원해 주신
직무와 관련된 질문입니다" 같은 예고, "툴을 호출합니다"를 대사로 읽음).

`ask_question`의 선언은 Live 커넥션을 열 때 한 번 실린다. 그 시점에 세션 풀의
태그 어휘를 tag 파라미터의 enum으로 주입해, 모델이 이 세션에 실제로 존재하는
태그만 고르게 한다. enum은 단계별이 아니라 풀 전체 어휘다 — 커넥션(~10분)이
단계 여러 개에 걸치기 때문이다(`QuestionPool.tags` 참고).

단계 전환은 질문 소진이 아니라 시간이 정한다. 다만 모델에게 시계를 보여 주지는
않는다 — 남은 시간을 알려 봐야 정작 늘어질 때는 툴을 부르지 않고 있다. 툴이
세션 시작 시각으로 경과를 재서 예산보다 뒤처진 단계를 끌어올리고, 모델은 결과만
통보받는다(`daedam.interview.stages`). 단계가 넘어가면 열린 파볼 곳은 버린다.

선언 주입 경로 (설치된 ADK 2.6.3 소스에서 확인):
  google/adk/flows/llm_flows/base_llm_flow.py  `_process_agent_tools`
    — run_live 전처리도 툴마다 ToolContext를 만들어 process_llm_request를 부른다
  google/adk/tools/function_tool.py  `_get_declaration`
    — JSON_SCHEMA_FOR_FUNC_DECL이 기본 활성이라 선언은 parameters_json_schema
  google/adk/models/llm_request.py  `append_tools`
    — 선언을 config.tools에 병합하고 tools_dict에 등록

세션 이력에서 답변을 읽는 경로 (설치된 ADK 2.6.3 소스에서 확인):
  google/adk/runners.py  `run_live` 이벤트 append 분기 (1497행 부근)
    — partial이 아닌 이벤트만 세션에 append한다. 완료된 전사(finished=True)는
      partial=False라 쌓인다 (gemini_llm_connection.py 395~440행)
"""

from __future__ import annotations

import json
import logging
import time
from functools import lru_cache
from typing import Any, Callable, Literal, Mapping, override

from google.adk.models.llm_request import LlmRequest
from google.adk.tools import FunctionTool, ToolContext
from google.genai import types

from daedam.interview.probes import Probe, extract_probes
from daedam.interview.question_pool import Question, QuestionPool
from daedam.interview.stages import DEFAULT_PROFILE, STAGE_NAMES, SessionFlow
from daedam.knowledge.chunk import Source, chunks_from_application, chunks_from_report
from daedam.knowledge.embedding import default_embedder
from daedam.knowledge.search import KnowledgeIndex

logger = logging.getLogger(__name__)

# ── 뼈대질문 배달 ────────────────────────────────────────────────────────

#: 세션 생성 시 서버가 이 키로 질문 풀(dict 목록)을 state에 심는다.
STATE_QUESTION_POOL = "question_pool"

#: 면접이 시작된 epoch 초. 단조 시계가 아니라 벽시계인 이유는 이 값이
#: 세션 state에 실려 재연결을 넘고, 나중에 파일·DB에 저장돼도 뜻이 남아야
#: 하기 때문이다. 면접 시계는 재연결 공백 동안에도 계속 간다.
STATE_STARTED_AT = "started_at"

#: 시간 예산 프로필 이름 (`daedam.interview.stages.PROFILES`의 키).
STATE_PROFILE = "profile"

#: 이미 낸 질문 id 목록과 현재 단계 인덱스. 툴이 갱신하고 브리지가 state
#: 델타에서 읽어 화면의 질문 번호를 움직인다.
STATE_ASKED = "asked"
STATE_STAGE = "stage"

#: 현재 뼈대질문의 파볼 곳. `[{"topic", "hint", "status", "attempts"}]`.
#: status는 open(아직 안 물음·답 못 받음) / covered(들음) / unanswered(두 번
#: 물어도 안 나옴) / dropped(단계가 넘어가 버림). 새 뼈대질문이 나가면 비운다.
#:
#: 추출은 뼈대질문을 배달한 **다음** 호출에서 한다 — 그때야 답변이 세션에 쌓여
#: 있다. 그래서 뼈대질문 배달 직후에는 이 목록이 비어 있고, 그것이 "아직 안
#: 뽑았다"는 표시다(`STATE_PROBES_FOR`로 어느 질문 것인지 가른다).
STATE_PROBES = "probes"
STATE_PROBES_FOR = "probes_for"

#: 마지막 뼈대질문을 배달한 시점의 세션 이벤트 수. 그 뒤의 지원자 전사가 이
#: 질문에 대한 답변이다.
STATE_ANSWER_MARKER = "answer_marker"

#: 닫힌 파볼 곳의 기록. 답변을 못 받아 닫힌 것(unanswered)은 코칭이 "끝내
#: 설명하지 못했다"의 근거로 쓴다. 면접 내내 쌓인다.
STATE_PROBE_LOG = "probe_log"

#: 한 파볼 곳을 몇 번까지 묻는가. 두 번 물어도 안 나오면 닫는다 — 세 번째는
#: 심문이다.
_PROBE_ATTEMPTS = 2

#: 질문을 돌려줄 때 붙는 지시. 무엇을 말할지와 다음에 뭘 할지, 그 둘 밖의 것은
#: 싣지 않는다. 시스템 프롬프트의 같은 규칙과 달리 툴을 부를 때마다 새로
#: 도착하고 도착 시점이 바로 다음 결정 직전이다. 다만 툴을 안 부르는 모델에게는
#: 닿지 않는다 — 습관을 시작시키는 장치가 아니라 유지시키는 장치다.
_ASK_INSTRUCTION = "이 질문을 물어보세요. 답변을 들으면 다음 질문 전에 이 툴을 다시 부르세요."
_PROBE_INSTRUCTION = (
    "이것을 당신의 문장으로 물어보세요. 답변을 들으면 다음 질문 전에 이 툴을 다시"
    " 부르세요 — 답을 들었으면 answered=yes와 들은 내용(evidence)을, 못 들었으면"
    " answered=no를."
)

#: 테스트가 대역을 끼우는 자리. 모듈 전역인 이유는 `ask_question`이 ADK가 선언을
#: 읽는 순수 함수라 인자를 늘릴 수 없기 때문이다.
_extract_probes: Callable[..., list[Probe]] = extract_probes


def _question_pool_from(state: Mapping[str, Any]) -> QuestionPool:
    """세션 state의 질문 풀을 되살린다.

    풀이 없다는 건 시딩이 안 된 세션이라는 뜻이다 — 폴백으로 가리면 엉뚱한
    데이터로 면접이 그럴듯하게 돌아버리므로 크게 실패한다. 브리지가 준비
    데이터 없는 면접을 거절하므로 정상 경로에서는 오지 않는다.
    """
    raw = state.get(STATE_QUESTION_POOL)
    if not raw:
        raise ValueError("세션에 질문 풀이 없습니다 — 준비 데이터가 시딩되지 않았습니다")
    return QuestionPool.from_dicts(raw)


def _elapsed_s_from(state: Mapping[str, Any]) -> float:
    """면접이 시작된 뒤 흐른 초를 잰다.

    시작 시각이 없다는 건 브리지가 세션을 시딩하지 않았다는 뜻이다 —
    질문 풀과 같은 이유로 크게 실패한다. 조용히 넘어가면 시간 예산 없이
    면접이 돌아 단계가 영영 안 넘어간다.
    """
    started_at = state.get(STATE_STARTED_AT)
    if started_at is None:
        raise ValueError("세션에 면접 시작 시각이 없습니다 — 시딩되지 않았습니다")
    return max(0.0, time.time() - float(started_at))


def _session_flow_from(state: Mapping[str, Any]) -> SessionFlow:
    """세션의 시간 예산 판정기를 만든다. 프로필이 없으면 기본 프로필."""
    return SessionFlow(state.get(STATE_PROFILE) or DEFAULT_PROFILE)


def _next_in_pool(
    pool: QuestionPool, *, stage: int, tag: str | None, exclude: list[str]
) -> tuple[Question | None, int]:
    """다음 뼈대질문과 그 질문이 속한 단계.

    현재 단계가 소진되면 다음 단계로 걸어 올라간다 — 단계 전환의 최종 판단은
    서버에 있다. 남은 질문이 하나도 없으면 (None, 마지막 단계).
    """
    at = stage
    found = pool.next(stage=at, tag=tag, exclude=exclude)
    while found is None and at < len(STAGE_NAMES) - 1:
        at += 1
        found = pool.next(stage=at, tag=tag, exclude=exclude)
    return found, at


def _stage_on_schedule(state: Any, flow: SessionFlow, elapsed_s: float) -> bool:
    """예산보다 뒤처진 단계를 끌어올린다. 옮겼으면 True.

    남은 질문이 있어도 건너뛴다 — 지난 단계에 계속 머무르면 뒤 단계가 통째로
    잘린다. 반대로 예산보다 앞서 가는 것(질문 소진)은 막지 않는다.
    """
    stage = int(state.get(STATE_STAGE, 0))
    on_schedule = flow.stage_index_at(elapsed_s)
    if on_schedule <= stage:
        return False
    logger.info(
        "시간 경과로 단계 이동: %s → %s (경과 %.0f초)",
        STAGE_NAMES[stage],
        STAGE_NAMES[on_schedule],
        elapsed_s,
    )
    state[STATE_STAGE] = on_schedule
    return True


# ── 답변 읽기 ────────────────────────────────────────────────────────────


def _applicant_said_since(tool_context: ToolContext, marker: int) -> tuple[str, int]:
    """마지막 뼈대질문 뒤에 지원자가 한 말과, 지금 이벤트 수.

    세션 이벤트에서 완료된 입력 전사(지원자)를 모은다. marker는 앞선 호출이
    읽은 지점(이벤트 수)이라, 그 뒤의 것만 본다.

    전사가 없으면(테스트 대역·꺼진 전사) 빈 문자열이다 — 그때는 파볼 곳을 못
    뽑고 다음 뼈대질문으로 간다. 못 보는 것이 지어내는 것보다 낫다.
    """
    session = getattr(tool_context, "session", None)
    events = list(getattr(session, "events", None) or [])
    spoken: list[str] = []
    for event in events[marker:]:
        transcription = getattr(event, "input_transcription", None)
        if transcription is None or not getattr(transcription, "finished", False):
            continue
        text = (getattr(transcription, "text", "") or "").strip()
        if text:
            spoken.append(text)
    return " ".join(spoken), len(events)


# ── 파볼 곳 ──────────────────────────────────────────────────────────────


def _open_probe(probes: list[dict[str, Any]]) -> dict[str, Any] | None:
    """아직 열려 있는 파볼 곳 중 첫 번째. 없으면 None."""
    for probe in probes:
        if probe["status"] == "open":
            return probe
    return None


def _close_probe(
    state: Any, probe: dict[str, Any], status: str, evidence: str = ""
) -> None:
    """파볼 곳을 닫고 기록에 남긴다."""
    probe["status"] = status
    if evidence:
        probe["evidence"] = evidence
    log = list(state.get(STATE_PROBE_LOG, []))
    log.append(
        {
            "question_id": state.get(STATE_PROBES_FOR),
            "topic": probe["topic"],
            "hint": probe["hint"],
            "status": status,
            "evidence": evidence,
        }
    )
    state[STATE_PROBE_LOG] = log


def _mark_answered(state: Any, probe: dict[str, Any], evidence: str) -> None:
    """직전에 건넨 파볼 곳의 답을 들었다 — 닫고 근거를 남긴다.

    어느 항목인지는 서버가 안다(방금 건넨 것). 모델에게 주제 이름을 되받지
    않는다 — 받아 봤더니 9회 중 9회가 다른 이름이었다(실측: 직전 뼈대질문의
    태그를 적어 보냄). 이름 맞추기는 모델이 못 하는 일이고 서버는 할 필요가
    없는 일이다.
    """
    _close_probe(state, probe, "covered", evidence)
    logger.info("파볼 곳 확인: %s — %s", probe["topic"], evidence[:60])


def _retry_or_close(state: Any, probe: dict[str, Any]) -> None:
    """신고 없이 돌아왔다 — 못 들은 것이다. 한 번 더 묻거나, 다 썼으면 닫는다."""
    probe["attempts"] = int(probe.get("attempts", 0)) + 1
    if probe["attempts"] >= _PROBE_ATTEMPTS:
        _close_probe(state, probe, "unanswered")
        logger.info("파볼 곳 포기: %s (%d번 물음)", probe["topic"], probe["attempts"])


def _probe_response(probe: dict[str, Any]) -> dict:
    """열린 파볼 곳을 모델에게 건넨다."""
    probe["asked"] = True
    return {"probe": probe["topic"], "hint": probe["hint"], "instruction": _PROBE_INSTRUCTION}


def _drop_open_probes(state: Any, probes: list[dict[str, Any]]) -> None:
    """단계가 넘어갔다 — 열린 파볼 곳은 버린다. 뒤 단계가 잘리는 것보다 낫다."""
    for probe in probes:
        if probe["status"] == "open":
            _close_probe(state, probe, "dropped")


def _deliver(
    state: Any,
    tool_context: ToolContext,
    pool: QuestionPool,
    *,
    tag: str | None,
    asked: list[str],
    elapsed_s: float,
) -> dict:
    """준비된 질문 하나를 배달하고 state를 갱신한다.

    남은 게 없어도 면접을 끝내지 않는다 — 끝내는 것은 지원자의 종료 버튼이다.
    그때까지는 모델이 제 문장으로 이어간다.
    """
    stage = int(state.get(STATE_STAGE, 0))
    found, at = _next_in_pool(pool, stage=stage, tag=tag, exclude=asked)
    state[STATE_STAGE] = at
    if found is None:
        logger.info("질문 소진 (경과 %.0f초, %d개 배달)", elapsed_s, len(asked))
        return {
            "instruction": "준비된 질문이 다 나갔습니다. 지금까지의 답변에서 더 확인할 것을"
            " 꼬리질문으로 이어가세요. 답변을 들으면 다음 질문 전에 이 툴을 다시 부르세요."
        }

    asked = [*asked, found.id]
    state[STATE_ASKED] = asked
    # 파볼 곳은 다음 호출에서 뽑는다 — 답변이 그때야 세션에 있다. 지금은
    # "이 질문 것은 아직 안 뽑았다"만 남긴다.
    state[STATE_PROBES] = []
    state[STATE_PROBES_FOR] = found.id
    _, marker = _applicant_said_since(tool_context, 0)
    state[STATE_ANSWER_MARKER] = marker
    logger.info(
        "뼈대질문 %d번 배달 [%s] %s (경과 %.0f초)",
        len(asked) - 1,
        STAGE_NAMES[at],
        found.text,
        elapsed_s,
    )
    return {"ask": found.text, "instruction": _ASK_INSTRUCTION}


def ask_question(
    tool_context: ToolContext,
    tag: str,
    answered: Literal["yes", "no", ""] = "",
    evidence: str = "",
) -> dict:
    """질문하기 전에 반드시 호출하세요. 무엇을 물을지는 이 툴이 정합니다.

    돌아오는 것은 둘 중 하나입니다.
      ask          — 준비된 질문입니다. 이 문장을 그대로 물어보세요.
      probe + hint — 방금 답변에서 더 파볼 곳입니다. 주제(probe)와 무엇이 빠졌는지
                     (hint)를 보고 당신의 문장으로 물어보세요.

    파볼 곳(probe)을 물은 뒤의 호출에서는 answered를 반드시 적으세요. 답을 들었으면
    yes, 못 들었으면(모른다고 했거나, 기억이 안 난다고 했거나, 딴 얘기를 했으면)
    no. no면 이 툴이 한 번 더 물을지 넘어갈지 정합니다.

    Args:
        tag: 다음으로 확인하고 싶은 주제. 준비된 질문을 고르는 기준입니다.
        answered: 직전에 받은 probe의 답을 들었는지. yes 또는 no. 준비된 질문(ask)
            뒤의 호출에서는 비워 두세요.
        evidence: answered=yes일 때, 지원자가 실제로 한 말의 요지를 한 문장으로.
            없는 말을 적지 마세요 — 이것이 리포트의 근거가 됩니다.

    Returns:
        ask 또는 probe·hint와 instruction을 담은 dict.
    """
    state = tool_context.state
    pool = _question_pool_from(state)
    flow = _session_flow_from(state)
    elapsed_s = _elapsed_s_from(state)
    asked = list(state.get(STATE_ASKED, []))
    probes = list(state.get(STATE_PROBES, []))

    # 단계가 넘어가면 파던 것을 버리고 다음 뼈대질문이다 — 뒤 단계가 잘리는
    # 것보다 낫다.
    if _stage_on_schedule(state, flow, elapsed_s):
        _drop_open_probes(state, probes)
        state[STATE_PROBES] = probes
        return _deliver(state, tool_context, pool, tag=tag, asked=asked, elapsed_s=elapsed_s)

    # 직전에 건넨 파볼 곳이 있으면 신고를 처리한다. yes/no 둘 중 하나여야
    # 한다 — 빈 값은 "못 들음"으로 보지 않는다. 앞서 빈 값을 그 신호로 뒀더니
    # 모델이 빈 값을 내지 않아 재시도 경로가 한 번도 안 돌았다(실측 0/9).
    # 신호는 범주적이어야 흔들리지 않는다.
    current = next((p for p in probes if p["status"] == "open" and p.get("asked")), None)
    if current is not None:
        if answered == "yes":
            _mark_answered(state, current, evidence)
        elif answered == "no":
            _retry_or_close(state, current)
        else:
            # 신고를 빼먹었다. 들었는지 모르니 못 들은 것으로 본다 — 한 번 더
            # 물어서 손해 볼 것은 없고, 못 들은 것을 들은 것으로 닫는 쪽이 나쁘다.
            logger.info("answered 누락 — 못 들은 것으로 봅니다: %s", current["topic"])
            _retry_or_close(state, current)

    # 아직 안 뽑았으면 지금 뽑는다 — 뼈대질문 뒤 첫 호출이다. 마무리 단계는
    # 빼고: "마지막으로 하고 싶은 말씀"에 파볼 곳은 없다. 파면 "꼭 입사하고
    # 싶습니다"에서 입사 동기를 캐게 된다(실측) — 그건 마무리가 아니라 심문이다.
    in_closing = int(state.get(STATE_STAGE, 0)) == len(STAGE_NAMES) - 1
    if not probes and state.get(STATE_PROBES_FOR) and asked and not in_closing:
        question = pool.by_id(state[STATE_PROBES_FOR])
        answer, _ = _applicant_said_since(tool_context, int(state.get(STATE_ANSWER_MARKER, 0)))
        if question is not None and answer:
            found = _extract_probes(question=question.text, answer=answer)
            probes = [
                {"topic": p.topic, "hint": p.hint, "status": "open", "attempts": 0}
                for p in found
            ]
            logger.info(
                "파볼 곳 %d개: %s",
                len(probes),
                " / ".join(p["topic"] for p in probes) or "(없음)",
            )
        # 뽑았든 못 뽑았든 이 질문에 대해서는 끝이다. 못 뽑았으면(전사 없음·
        # LLM 실패) 빈 목록이 남아 바로 다음 뼈대질문으로 간다.
        state[STATE_PROBES_FOR] = None
    elif in_closing:
        state[STATE_PROBES_FOR] = None
    state[STATE_PROBES] = probes

    nxt = _open_probe(probes)
    if nxt is not None:
        return _probe_response(nxt)
    return _deliver(state, tool_context, pool, tag=tag, asked=asked, elapsed_s=elapsed_s)


class AskQuestionTool(FunctionTool):
    """세션 풀의 태그 어휘를 선언 enum으로 입힌 `ask_question`.

    자동 생성 선언(`_get_declaration`)은 함수 서명만 보므로 tag가 자유
    문자열이 된다. 여기서는 선언이 요청에 실리는 시점에 enum을 덧입힌다 —
    프롬프트 산문보다 파라미터 스키마가 모델의 태그 선택을 훨씬 강하게
    구속한다.

    바꾸는 것은 모델이 보는 선언뿐이다. 모델이 툴을 호출했을 때의 실행
    경로(`run_async`)는 상속 그대로라 `ask_question`은 순수 함수로 남는다.

    이 인스턴스는 root_agent에 물려 모든 세션이 공유한다. 그래서 self에는
    아무것도 저장하지 않고, 커넥션마다 새로 만들어지는 llm_request만 고친다.
    `_get_declaration`이 deep copy를 반환하므로 패치가 다른 세션에 새지 않는다.
    """

    def __init__(self) -> None:
        super().__init__(func=ask_question)

    @override
    async def process_llm_request(
        self, *, tool_context: ToolContext, llm_request: LlmRequest
    ) -> None:
        # process_llm_request는 모델로 나가는 요청을 툴마다 손보라고 ADK가 열어
        # 둔 전처리 훅이다(live에서는 커넥션을 열 때 한 번). 기본 구현은 자기
        # 등록뿐이다 — 선언을 config.tools에(모델이 보는 쪽), 인스턴스를
        # tools_dict에(함수 호출을 돌려받는 쪽). 그래서 super()로 등록을 마친 뒤
        # 방금 실린 선언을 이어서 고친다. 재연결 때마다 다시 불리므로 풀이
        # 바뀌면 enum도 그때 갱신된다.
        await super().process_llm_request(
            tool_context=tool_context, llm_request=llm_request
        )
        tags = _question_pool_from(tool_context.state).tags()
        prop = self._tag_property(llm_request)
        if not tags or prop is None:
            return
        # `str | None`은 anyOf[string, null]로 렌더된다. 문자열 가지에 enum을
        # 끼우는 대신 통째로 string+enum으로 바꾼다 — required에 없어 생략은
        # 여전히 허용되고, 모델이 읽는 스키마는 이쪽이 단순하다.
        prop.pop("anyOf", None)
        prop.pop("default", None)
        prop["type"] = "string"
        prop["enum"] = tags

    def _tag_property(self, llm_request: LlmRequest) -> dict[str, Any] | None:
        """요청에 실린 이 툴의 선언에서 tag 프로퍼티 스키마를 찾는다.

        선언이 parameters_json_schema 형태가 아니면(피처 플래그 꺼짐) None을
        돌려주고 enum 없이 둔다. 그래도 동작은 유지된다 — 태그는 프롬프트로도
        안내되고, 엉뚱한 값은 `QuestionPool.next`가 우선순위로 대체한다.
        """
        for tool in llm_request.config.tools or []:
            if not isinstance(tool, types.Tool) or not tool.function_declarations:
                continue
            for declaration in tool.function_declarations:
                if declaration.name != self.name:
                    continue
                schema = declaration.parameters_json_schema
                if isinstance(schema, dict):
                    return schema.get("properties", {}).get("tag")
        return None


# ── 회사 지식 검색 ───────────────────────────────────────────────────────

#: 세션 생성 시 서버가 리서치 리포트(섹션 목록)를 심는 state 키.
#: 형태는 `daedam.knowledge.chunk.chunks_from_report`의 입력과 같다.
STATE_RESEARCH_REPORT = "research_report"

#: 세션 생성 시 서버가 지원서(파트 목록)를 심는 state 키.
#: 형태는 `daedam.knowledge.chunk.chunks_from_application`의 입력과 같다.
STATE_APPLICATION = "application"

@lru_cache(maxsize=2)
def _cached_knowledge_index(corpus_json: str) -> KnowledgeIndex:
    """코퍼스 내용을 키로 인덱스를 재사용한다.

    임베딩 인덱스는 청크 벡터 인코딩이 수십 ms라 한 번 만들고 다시 쓴다.
    """
    sections, parts = json.loads(corpus_json)
    return KnowledgeIndex(
        chunks_from_report(sections or []) + chunks_from_application(parts or []),
        embedder=default_embedder(),
    )


def _knowledge_index_from(state: Mapping[str, Any]) -> KnowledgeIndex:
    """세션 state의 리포트·지원서로 검색 인덱스를 얻는다.

    둘 다 없다는 건 시딩이 안 된 세션이라는 뜻이다 — 크게 실패한다
    (`_question_pool_from`과 같은 원칙). 한쪽만 있으면 있는 쪽으로 색인한다.
    """
    sections = state.get(STATE_RESEARCH_REPORT)
    parts = state.get(STATE_APPLICATION)
    if not sections and not parts:
        raise ValueError("세션에 검색할 자료가 없습니다 — 준비 데이터가 시딩되지 않았습니다")
    return _cached_knowledge_index(
        json.dumps([sections, parts], ensure_ascii=False, sort_keys=True)
    )


def search_knowledge(
    tool_context: ToolContext, query: str, source: Source | None = None
) -> dict:
    """회사 리서치 리포트와 지원서에서 관련 정보를 검색합니다.

    회사에 대한 사실이 필요할 때 호출하세요 — 꼬리질문을 만들 때, 지원자의
    답변을 회사 맥락과 연결할 때, 지원서에 적힌 내용을 확인할 때.
    검색 결과에 없는 회사 정보를 지어내서 말하지 마세요.

    결과를 말에 옮길 때는 어디서 본 것인지 밝히세요. 지원서에서 온 것이면
    "지원서에 기재해 주신 ○○ 프로젝트에서"처럼 그 항목의 이름을 붙여서,
    리서치 리포트에서 온 것이면 "저희가 파악하기로는"처럼. 지원자는 여러
    경험을 썼고 "그 프로젝트"라고만 하면 어느 것인지 되묻게 됩니다.

    Args:
        query: 찾을 내용. 지원자의 답변이나 지금 파고드는 주제에 나온 구체적
            표현을 그대로 넣으세요 (예: "공차 거리 단축 기여도", "배차 자동화
            도입 배경"). "인재상", "직무경험" 같은 카테고리 단어 하나만 넣으면
            엉뚱한 대목이 나옵니다.
        source: 검색 범위. "research"는 회사 리서치 리포트, "application"은
            지원서. 생략하면 둘 다 검색합니다.

    Returns:
        results: 출처(source)·제목(title)·본문(text)을 담은 결과 목록,
        관련도 순 최대 3개. 관련 정보가 없으면 results가 비고 instruction으로 알립니다.
    """
    found = _knowledge_index_from(tool_context.state).search(query, source=source)
    # 모델이 무엇을 찾았고 무엇이 걸렸는지 남긴다. 검색은 면접 중 유일한 사실
    # 조회 경로인데, 이 줄이 없으면 툴이 쓰이는지조차 알 수 없다.
    logger.info(
        "지식 검색 [%s] %s → %d건 %s",
        source or "전체",
        query,
        len(found),
        [chunk.title for chunk in found],
    )
    if not found:
        return {
            "results": [],
            "instruction": "관련 정보가 없습니다. 다른 검색어로 다시 시도하거나,"
            " 확인되지 않은 사실은 언급하지 마세요.",
        }
    return {"results": [chunk.as_tool_result() for chunk in found]}
