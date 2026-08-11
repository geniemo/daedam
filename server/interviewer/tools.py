"""면접 툴 — 뼈대질문 배달과 회사 지식 검색.

`get_next_question`의 선언은 Live 커넥션을 열 때 한 번 실린다. 그 시점에 세션 풀의 태그 어휘를
tag 파라미터의 enum으로 주입해, 모델이 이 세션에 실제로 존재하는 태그만
고르게 한다. enum은 단계별이 아니라 풀 전체 어휘다 — 커넥션(~10분)이 단계
여러 개에 걸치기 때문이다(`QuestionPool.tags` 참고).

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
from functools import lru_cache
from typing import Any, Mapping, override

from google.adk.models.llm_request import LlmRequest
from google.adk.tools import FunctionTool, ToolContext
from google.genai import types

from daedam.interview.question_pool import QuestionPool
from daedam.interview.stages import STAGE_NAMES
from daedam.knowledge.chunk import Source, chunks_from_application, chunks_from_report
from daedam.knowledge.embedding import default_embedder
from daedam.knowledge.search import KnowledgeIndex

# ── 뼈대질문 배달 ────────────────────────────────────────────────────────

#: 세션 생성 시 서버가 이 키로 질문 풀(dict 목록)을 state에 심는다.
STATE_QUESTION_POOL = "question_pool"


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


def get_next_question(tool_context: ToolContext, tag: str | None = None) -> dict:
    """다음 뼈대질문을 가져옵니다. 면접을 시작할 때와 새 주제로 넘어갈 때 호출하세요.

    방금 들은 답변을 파고드는 꼬리질문은 직접 만드는 것입니다 — 그때는 이 툴을
    호출하지 마세요.

    Args:
        tag: 원하는 주제 태그. 지원자의 답변 맥락과 이어지는 태그를 고르세요.
            마땅한 태그가 없으면 생략하세요 — 준비된 우선순위 순서로 나갑니다.

    Returns:
        question(질문 문장), stage(현재 단계 이름), note(진행 안내)를 담은 dict.
        남은 질문이 없으면 done이 True.
    """
    state = tool_context.state
    pool = _question_pool_from(state)
    asked: list[str] = list(state.get("asked", []))
    stage: int = int(state.get("stage", 0))

    # 현재 단계가 소진되면 다음 단계로 넘긴다. 단계 전환의 최종 판단은 서버에 있다.
    question = pool.next(stage=stage, tag=tag, exclude=asked)
    while question is None and stage < len(STAGE_NAMES) - 1:
        stage += 1
        question = pool.next(stage=stage, tag=tag, exclude=asked)

    if question is None:
        state["stage"] = stage
        return {"done": True, "note": "질문이 모두 끝났습니다. 면접을 마무리해 주세요."}

    asked.append(question.id)
    state["asked"] = asked
    state["stage"] = stage

    note = f"지금은 {STAGE_NAMES[stage]} 단계입니다. 이 질문을 그대로 읽지 말고 자연스럽게 물어보세요."
    stage_tags = pool.tags_for(stage)
    if stage_tags:
        note += f" 이 단계의 주제 태그: {', '.join(stage_tags)}"
    return {"question": question.text, "stage": STAGE_NAMES[stage], "note": note}


class NextQuestionTool(FunctionTool):
    """세션 풀의 태그 어휘를 선언 enum으로 입힌 `get_next_question`.

    자동 생성 선언(`_get_declaration`)은 함수 서명만 보므로 tag가 자유
    문자열이 된다. 여기서는 선언이 요청에 실리는 시점에 enum을 덧입힌다 —
    프롬프트 산문보다 파라미터 스키마가 모델의 태그 선택을 훨씬 강하게
    구속한다.

    바꾸는 것은 모델이 보는 선언뿐이다. 모델이 툴을 호출했을 때의 실행
    경로(`run_async`)는 상속 그대로라 `get_next_question`은 순수 함수로 남는다.

    이 인스턴스는 root_agent에 물려 모든 세션이 공유한다. 그래서 self에는
    아무것도 저장하지 않고, 커넥션마다 새로 만들어지는 llm_request만 고친다.
    `_get_declaration`이 deep copy를 반환하므로 패치가 다른 세션에 새지 않는다.
    """

    def __init__(self) -> None:
        super().__init__(func=get_next_question)

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

    Args:
        query: 찾을 내용. 지원자의 답변이나 지금 파고드는 주제에 나온 구체적
            표현을 그대로 넣으세요 (예: "공차 거리 단축 기여도", "배차 자동화
            도입 배경"). "인재상", "직무경험" 같은 카테고리 단어 하나만 넣으면
            엉뚱한 대목이 나옵니다.
        source: 검색 범위. "research"는 회사 리서치 리포트, "application"은
            지원서. 생략하면 둘 다 검색합니다.

    Returns:
        results: 출처(source)·제목(title)·본문(text)을 담은 결과 목록,
        관련도 순 최대 3개. 관련 정보가 없으면 results가 비고 note로 알립니다.
    """
    found = _knowledge_index_from(tool_context.state).search(query, source=source)
    if not found:
        return {
            "results": [],
            "note": "관련 정보가 없습니다. 다른 검색어로 다시 시도하거나,"
            " 확인되지 않은 사실은 언급하지 마세요.",
        }
    return {"results": [chunk.as_tool_result() for chunk in found]}
