"""면접 툴 — 질문 게이트와 회사 지식 검색.

질문은 전부 `ask_question`을 지난다. 모델의 자율을 뺏자는 게 아니라, 페이싱
판단을 프롬프트가 아니라 툴 쪽에 두려는 것이다 — 대화가 길어질수록 시스템
프롬프트의 영향은 그 뒤에 쌓인 대화에 묻히지만, 툴 선언과 툴 출력은 매
호출마다 새로 도착한다.

지켜야 할 불변식이 하나 있다: **모델이 이미 손에 쥔 문장을 돌려주지 않는다.**
네이티브 오디오 모델은 물을 것을 정하는 순간 이미 말하고 있어서, 그 문장을
툴이 되돌려주면 한 번 더 말한다(실측 9턴 중 8턴). 그래서 꼬리질문을 허가할
때는 판정만 돌려주고, 문장은 모델에게 말할 것이 없을 때만 준다.

`ask_question`의 선언은 Live 커넥션을 열 때 한 번 실린다. 그 시점에 세션 풀의 태그 어휘를
tag 파라미터의 enum으로 주입해, 모델이 이 세션에 실제로 존재하는 태그만
고르게 한다. enum은 단계별이 아니라 풀 전체 어휘다 — 커넥션(~10분)이 단계
여러 개에 걸치기 때문이다(`QuestionPool.tags` 참고).

단계 전환은 질문 소진이 아니라 시간이 정한다. 다만 모델에게 시계를 보여
주지는 않는다 — 남은 시간을 알려 봐야 정작 늘어질 때는 툴을 부르지 않고
있고, 꼬리질문의 필요는 시간이 아니라 답변 내용이 정하기 때문이다. 툴이
세션 시작 시각으로 경과를 재서 예산보다 뒤처진 단계를 끌어올리고, 모델은
결과만 통보받는다(`daedam.interview.stages`).

선언 주입 경로 (설치된 ADK 2.6.3 소스에서 확인):
  google/adk/flows/llm_flows/base_llm_flow.py  `_process_agent_tools`
    — run_live 전처리도 툴마다 ToolContext를 만들어 process_llm_request를 부른다
  google/adk/tools/function_tool.py  `_get_declaration`
    — JSON_SCHEMA_FOR_FUNC_DECL이 기본 활성이라 선언은 parameters_json_schema
  google/adk/models/llm_request.py  `append_tools`
    — 선언을 config.tools에 병합하고 tools_dict에 등록
"""

from __future__ import annotations

import json
import logging
import time
from functools import lru_cache
from typing import Any, Mapping, override

from google.adk.models.llm_request import LlmRequest
from google.adk.tools import FunctionTool, ToolContext
from google.genai import types

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

#: 면접이 마무리에 들어갔다는 표시. 툴이 남기고 브리지가 읽는다 — 모델은
#: 커넥션을 끊을 수 없으므로, 마무리 인사가 끝난 뒤 실제로 닫는 것은 서버다.
#: `ask_question`(하드캡·질문 소진)과 `finish_interview`(면접관의 판단)가
#: 세운다. 이 표시가 없으면 서버는 하드캡까지 면접이 끝난 줄 모른다.
STATE_CLOSING = "closing"

#: 이미 낸 질문 id 목록과 현재 단계 인덱스. 툴이 갱신하고 브리지가 state
#: 델타에서 읽어 화면의 질문 번호·단계 표시를 움직인다.
STATE_ASKED = "asked"
STATE_STAGE = "stage"

#: 마지막 뼈대질문 이후 모델이 자기 문장으로 물은 질문 수. 주제가 아니라
#: "준비된 질문에서 얼마나 멀어졌는가"를 센다 — 꼬리질문마다 태그가 달라지므로
#: 주제를 상태로 붙들 수 없고, 붙들 필요도 없다. 새 뼈대질문이 나가면 0이 된다.
STATE_FREE_QUESTIONS = "free_questions"

#: 자유 질문 개수 상한. 준비된 질문 사이에 자작 질문이 이보다 길게 끼면
#: 어떤 경우에도 면접이 아니다. 문턱과 무관하게 먼저 걸린다.
_FREE_QUESTION_CAP = 3

#: 모든 지시 끝에 붙는 다음 행동. 시스템 프롬프트의 같은 규칙은 대화가 길어질수록
#: 뒤에 쌓인 대화에 묻히지만, 이 문장은 툴을 부를 때마다 새로 도착하고 도착 시점이
#: 바로 다음 결정 직전이다. 다만 툴을 안 부르는 모델에게는 닿지 않는다 — 습관을
#: 시작시키는 장치가 아니라 유지시키는 장치다.
_NEXT_CALL_INSTRUCTION = " 지원자의 답변을 들으면 다음 질문 전에 이 툴을 다시 부르세요."

#: 첫 자유 질문에 주는 여유. 방금 들은 답변을 한 번 되묻는 것은 거의 항상
#: 값어치를 하므로, 첫 질문은 다음 뼈대질문보다 한 칸 덜 중요해도 통과시킨다.
_FREE_QUESTION_SLACK = 2

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


def _free_question_threshold(nxt: Question | None, free: int) -> int | None:
    """자유 질문이 통과하려면 가져야 할 중요도. None이면 비교 대상이 없다.

    다음 뼈대질문의 중요도에 여유를 얹고 이미 쓴 자유 질문 수만큼 뺀다. 한 번
    더 물을수록 더 중요해야 하고, 다음에 물을 것이 중요할수록 조건이 까다로워진다.
    문턱이 고정이면 모델이 매번 1을 신고해 영원히 빠져나간다.

    단계가 진행돼 중요한 질문이 소진될수록 문턱이 저절로 낮아지는 것은 이
    식에서 따라 나온다 — 남은 게 곁가지뿐이면 파던 자리를 더 파는 편이 낫다.
    """
    return None if nxt is None else nxt.priority + _FREE_QUESTION_SLACK - free


def _stage_instruction(pool: QuestionPool, stage: int) -> str:
    """준비된 질문을 배달할 때 붙이는 상황 안내."""
    note = f"지금은 {STAGE_NAMES[stage]} 단계입니다."
    stage_tags = pool.tags_for(stage)
    if stage_tags:
        note += f" 이 단계의 주제 태그: {', '.join(stage_tags)}."
    return note


def _hard_cap_reached(
    state: Any, flow: SessionFlow, elapsed_s: float
) -> dict | None:
    """하드캡을 넘었으면 마무리 지시를, 아니면 None. 두 질문 툴이 공유한다."""
    if not flow.should_end(elapsed_s):
        return None
    state[STATE_STAGE] = len(STAGE_NAMES) - 1
    state[STATE_CLOSING] = True
    logger.info("하드캡 도달 — 마무리 지시 (경과 %.0f초)", elapsed_s)
    return {
        "done": True,
        "instruction": "면접 시간이 다 됐습니다. 짧게 마무리 인사를 하고 면접을 끝내세요.",
    }


def _stage_on_schedule(state: Any, flow: SessionFlow, elapsed_s: float) -> int:
    """예산보다 뒤처진 단계를 끌어올린 현재 단계.

    남은 질문이 있어도 건너뛴다 — 지난 단계에 계속 머무르면 뒤 단계가 통째로
    잘린다. 반대로 예산보다 앞서 가는 것(질문 소진)은 막지 않는다.
    """
    stage = int(state.get(STATE_STAGE, 0))
    on_schedule = flow.stage_index_at(elapsed_s)
    if on_schedule > stage:
        logger.info(
            "시간 경과로 단계 이동: %s → %s (경과 %.0f초)",
            STAGE_NAMES[stage],
            STAGE_NAMES[on_schedule],
            elapsed_s,
        )
        stage = on_schedule
    return stage


def _deliver(
    state: Any,
    pool: QuestionPool,
    *,
    tag: str | None,
    stage: int,
    asked: list[str],
    elapsed_s: float,
    lead: str = "",
) -> dict:
    """준비된 질문 하나를 배달하고 state를 갱신한다. 남은 게 없으면 마무리 지시."""
    found, at = _next_in_pool(pool, stage=stage, tag=tag, exclude=asked)
    if found is None:
        state[STATE_STAGE] = at
        state[STATE_CLOSING] = True
        logger.info("질문 소진 — 마무리 (경과 %.0f초, %d개 배달)", elapsed_s, len(asked))
        return {"done": True, "instruction": "질문이 모두 끝났습니다. 면접을 마무리해 주세요."}

    asked = [*asked, found.id]
    state[STATE_ASKED] = asked
    state[STATE_STAGE] = at
    state[STATE_FREE_QUESTIONS] = 0
    logger.info(
        "뼈대질문 %d번 배달 [%s] %s (경과 %.0f초)",
        len(asked) - 1,
        STAGE_NAMES[at],
        found.text,
        elapsed_s,
    )
    return {
        "ask": found.text,
        "stage": STAGE_NAMES[at],
        "instruction": lead + _stage_instruction(pool, at) + _NEXT_CALL_INSTRUCTION,
    }


def ask_question(
    tool_context: ToolContext, tag: str, priority: int, draft_question: str = ""
) -> dict:
    """질문하기 전에 반드시 호출하세요. 새 주제든 방금 들은 답변을 파고드는 꼬리질문이든 예외가 없습니다.

    draft_question을 비우면 지금 주제를 충분히 확인했다는 뜻이고, 준비된 다음
    질문이 ask에 담겨 옵니다. 채우면 그 꼬리질문을 물어도 되는지 판정합니다.

    돌아오는 것은 셋 중 하나입니다.
      ask     — 이 문장을 물어보세요. 준비된 질문입니다.
      ok      — 방금 적으신 꼬리질문을 그대로 물어도 됩니다.
      done    — 면접을 마무리하세요.

    Args:
        tag: 다음으로 확인하고 싶은 주제. 준비된 질문을 고르는 기준입니다.
        priority: 물으려는 것이 합격 판단에 얼마나 결정적인지 1~5로.
            1 핵심 검증 — 못 들으면 판단이 안 서는 질문.
            2 근거 확인 — 내세운 성과·판단의 근거, 본인이 맡은 몫.
            3 역량의 폭 — 다른 각도에서 같은 역량 재확인.
            4 맥락 보완 — 배경·동기·협업 방식.
            5 곁가지 — 흥미롭지만 평가와 연결이 옅음.
        draft_question: 물으려는 꼬리질문 문장. 아직 말하지 않은 후보입니다.
            더 물을 것이 없으면 비워 두세요 — 그때는 이 툴이 질문을 정합니다.

    Returns:
        ask 또는 ok와 instruction을 담은 dict. 면접을 끝낼 때가 되면 done이 True입니다.
    """
    # 빈 draft_question이 "이 주제는 끝났다"는 신호다. 종류를 따로 받지 않는 이유는
    # 신호가 범주적이어야 흔들리지 않아서다 — 문장을 썼거나 안 썼거나 둘뿐이고,
    # 크기 척도 위의 센티널(예: priority 6)처럼 이웃 값과 헷갈릴 여지가 없다.
    state = tool_context.state
    pool = _question_pool_from(state)
    flow = _session_flow_from(state)
    elapsed_s = _elapsed_s_from(state)
    if (ending := _hard_cap_reached(state, flow, elapsed_s)) is not None:
        return ending

    stage = _stage_on_schedule(state, flow, elapsed_s)
    asked = list(state.get(STATE_ASKED, []))

    if not draft_question:
        return _deliver(
            state, pool, tag=tag, stage=stage, asked=asked, elapsed_s=elapsed_s
        )

    free = int(state.get(STATE_FREE_QUESTIONS, 0))
    # 비교 대상은 태그 없이 뽑는다 — 이 주제를 파느라 못 하고 있는 것 중 가장
    # 중요한 질문이 기회비용이다. 모델이 태그로 지목하게 하면 문턱을 스스로
    # 정하는 셈이라, 중요한 질문이 영영 안 나간 채 면접이 끝날 수 있다.
    nxt, _ = _next_in_pool(pool, stage=stage, tag=None, exclude=asked)
    threshold = _free_question_threshold(nxt, free)
    passes = free < _FREE_QUESTION_CAP and (threshold is None or priority <= threshold)
    logger.info(
        "꼬리질문 %s: %s (중요도 %d, 문턱 %s, 누적 %d/%d, 경과 %.0f초)",
        "허가" if passes else "반려",
        draft_question,
        priority,
        "없음" if threshold is None else threshold,
        free,
        _FREE_QUESTION_CAP,
        elapsed_s,
    )

    if passes:
        state[STATE_STAGE] = stage
        state[STATE_FREE_QUESTIONS] = free + 1
        # 문장을 돌려주지 않는다. 모델이 이미 손에 쥔 초안을 되돌려줘 봐야 얻는
        # 정보가 없고, 말하고 나서 부르는 회차가 다시 나오면(실측된 적 있다)
        # 그 즉시 같은 질문이 두 번 나간다.
        #
        # instruction이라는 이름과 달리, 판정 결과를 명령으로 쓰지 않는다. "물어보세요"라고 쓰면 이미 말해버린
        # 경우에 한 번 더 말하라는 지시가 된다.
        return {
            "ok": True,
            "instruction": f"괜찮습니다. 준비된 질문 이후 {free + 1}번째 꼬리질문입니다."
            + _NEXT_CALL_INSTRUCTION,
        }

    # 반려는 문장을 같이 싣는다. 모델이 아직 말하기 전에 부른다는 것이 실측에서
    # 확인됐으므로(3/3), 여기서 준비된 질문을 줘도 두 번째 발화가 되지 않는다.
    # 대신 왕복이 한 번 줄어 침묵이 절반이 된다. 어느 주제로 갈지는 모델이 넘긴
    # 태그를 따른다 — 넘어갈지 말지는 서버가, 어디로 갈지는 모델이 정한다.
    return _deliver(
        state,
        pool,
        tag=tag,
        stage=stage,
        asked=asked,
        elapsed_s=elapsed_s,
        lead="이 주제는 여기까지입니다. 준비된 다음 질문으로 넘어가세요. ",
    )


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


# ── 면접 종료 ────────────────────────────────────────────────────────────


def finish_interview(tool_context: ToolContext) -> dict:
    """면접을 끝냅니다. 마무리 단계에서 마지막 질문의 답변까지 듣고 더 물어볼 것이 없을 때 호출하세요.

    호출한 뒤 짧게 마무리 인사를 하고 대화를 마치세요. 커넥션은 서버가 닫습니다.

    Returns:
        done(종료가 받아들여졌는지)과 instruction(다음에 할 일)를 담은 dict.
        아직 마무리 단계가 아니면 done이 False입니다.
    """
    # 이 툴이 있는 이유: 서버가 면접을 끝내는 근거가 시계밖에 없으면, 대화가
    # 끝나고도 하드캡까지 화면이 면접에 머문다. 면접관은 마지막 뼈대질문 뒤의
    # 역질문 응대와 마무리 인사를 툴 없이 하므로, 그 판단을 서버가 볼 통로가
    # 따로 필요하다. 하드캡은 이 툴을 안 부를 때를 위한 백스톱으로 남는다.
    state = tool_context.state
    flow = _session_flow_from(state)
    elapsed_s = _elapsed_s_from(state)
    stage = int(state.get(STATE_STAGE, 0))
    last_stage = len(STAGE_NAMES) - 1

    # 이른 종료를 막는다. 모델이 분위기로 끝내버리면 준비된 단계가 통째로
    # 날아간다 — 단계 판정은 여기서도 서버가 쥔다. 질문을 일찍 소진하면
    # ask_question이 이미 단계를 끌어올려 놓으므로, 대화가 실제로 일찍
    # 끝난 경우까지 막히지는 않는다.
    #
    # 다만 하드캡을 넘었으면 단계와 무관하게 받는다. 그 시점엔 브리지가 이미
    # 마무리를 지시한 뒤라, 여기서 반려하면 "끝내라"와 "계속하라"가 같이 가서
    # 모델이 어느 쪽도 못 믿게 된다.
    if stage < last_stage and not flow.should_end(elapsed_s):
        logger.info(
            "종료 요청 반려 — 아직 %s 단계 (경과 %.0f초)", STAGE_NAMES[stage], elapsed_s
        )
        return {
            "done": False,
            "instruction": f"아직 {STAGE_NAMES[last_stage]} 단계가 아닙니다."
            " ask_question으로 다음 주제를 이어가세요.",
        }

    state[STATE_CLOSING] = True
    logger.info(
        "면접관이 종료를 요청 (경과 %.0f초, %d개 배달)",
        elapsed_s,
        len(state.get(STATE_ASKED, [])),
    )
    return {"done": True, "instruction": "짧게 마무리 인사를 하고 대화를 마치세요."}


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
