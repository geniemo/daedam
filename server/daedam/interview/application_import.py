"""지원서 PDF → 파트·항목, 채용공고 파일 → 본문. Gemini가 문서를 읽고 옮긴다.

**왜 LLM인가.** 지원 사이트에서 내려받은 PDF(SK Careers 등)를 markitdown으로
돌려 봤다 — 텍스트는 잘 빠지지만 평문일 뿐이다. 우리에게 필요한 건 "자기소개서
2번 문항의 질문과 답변"이라는 구조이고, 그 단서("질문 :", "답변 :", "경험 1")는
회사마다 다르다. 게다가 그 PDF에는 생년월일·연락처·주소·학점까지 들어 있어서
무엇을 버릴지도 판단이 필요하다. 규칙으로 쓰면 첫 회사에서 깨지고, 판단은 애초에
규칙이 못 한다. Gemini는 PDF를 그대로 읽고(스캔본 포함) 구조화 응답으로 돌려주며,
쪽당 258토큰이라 지원서 한 부에 몇 원이다.

결과는 저장하지 않고 화면으로 돌려보낸다. 사용자가 등록 화면에서 검토·수정한
뒤 등록으로 낸다 — LLM이 본문을 고쳤을 위험은 그 검토가 받친다.

확인 경로(설치된 google-genai 2.17.0):
  google/genai/types.py:2397   Part.from_bytes(data=, mime_type=)
  google/genai/types.py:6439   GenerateContentConfig.response_mime_type
  google/genai/types.py:6449   GenerateContentConfig.response_schema (pydantic 모델 가능)
  google/genai/types.py:8519   GenerateContentResponse.parsed
  ai.google.dev/gemini-api/docs/document-processing — PDF 50MB·1000쪽까지, 쪽당 258토큰
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from daedam.llm import MODEL_QUALITY

logger = logging.getLogger(__name__)

#: 업로드 상한. 자기소개서 PDF는 수백 KB고, 사진이 든 것도 몇 MB다.
MAX_PDF_BYTES = 10 * 1024 * 1024

#: 파일 머리로 종류를 가린다 — 브라우저가 보내는 content-type은 믿지 않는다.
#: 채용공고는 PDF 말고 캡처 이미지로 오는 일이 흔해서 PNG·JPG도 받는다.
_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"%PDF", "application/pdf"),
    (b"\x89PNG", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)

#: 채용공고 본문 상한. 공고는 길어야 수천 자다.
_MAX_POSTING_CHARS = 20_000

#: 응답에서 받아들이는 상한. 이보다 크면 지원서가 아니라 다른 문서다.
_MAX_PARTS = 12
_MAX_ITEMS = 40
_MAX_BODY_CHARS = 8000


class ImportedItem(BaseModel):
    title: str = Field(description="문항(질문) 제목 또는 경력·프로젝트 이름")
    body: str = Field(description="답변 본문. 원문 그대로")


class ImportedPart(BaseModel):
    name: str = Field(description="문서의 큰 묶음 이름. 예: 자기소개서, 경력, 프로젝트")
    items: list[ImportedItem]


class ImportedApplication(BaseModel):
    parts: list[ImportedPart]


PROMPT = """아래 PDF는 취업 지원서(입사지원서 또는 자기소개서)다. 면접 준비에 쓸 수 있게 파트와 항목으로 옮겨라.

- 파트(part)는 문서의 큰 묶음이다. 예: 자기소개서, 경력, 프로젝트, 대외활동, 연구. 문서에 있는 묶음 이름을 그대로 쓴다.
- 항목(item)은 그 안의 문항 하나다. title은 문항(질문) 제목, body는 그 답변 본문이다. 문항 번호가 있으면 title 앞에 "1."처럼 남긴다.
- 경력·프로젝트·활동은 건마다 항목 하나로 만든다. title에 회사·프로젝트 이름과 기간·역할을, body에 설명을 둔다.
- body는 원문을 글자 그대로 옮긴다. 요약·수정·보완·번역을 하지 않는다. 줄바꿈 때문에 끊긴 문장은 이어 붙이고, 문단 구분만 줄바꿈으로 남긴다.
- 넣지 않는 것: 이름·생년월일·나이·성별·연락처·이메일·주소·병역·장애·보훈 같은 인적사항, 학력·학점·수강 과목, 어학 점수, 자격증 목록, 수상 목록, 지원 경로·희망 근무지·지망 같은 관리 정보, 거주지 확인처럼 운영용으로 묻는 문항.
- 선택 문항도 답변이 있으면 넣는다. 답변이 비어 있는 문항은 넣지 않는다.
"""


def extract_application(
    pdf: bytes, *, client: Any = None, model: str = MODEL_QUALITY
) -> list[dict[str, Any]]:
    """PDF 바이트를 등록 화면의 파트·항목으로 옮긴다.

    Returns:
        `[{"part": str, "items": [{"title": str, "body": str}]}]` — 준비 요청의
        `application`과 같은 모양이라 화면이 그대로 폼에 채운다.

    Raises:
        ValueError: 모델이 구조화 응답을 내지 않았을 때.
    """
    from google.genai import types

    if client is None:
        from google import genai

        client = genai.Client()

    response = client.models.generate_content(
        model=model,
        contents=[types.Part.from_bytes(data=pdf, mime_type="application/pdf"), PROMPT],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ImportedApplication,
            # 옮겨 적는 일이다. 창의성이 끼면 본문이 바뀐다.
            temperature=0,
        ),
    )
    parsed = response.parsed
    if not isinstance(parsed, ImportedApplication):
        raise ValueError("지원서 PDF에서 구조화 응답을 받지 못했습니다")
    parts = _tidy(parsed)
    logger.info(
        "지원서 PDF 가져오기: 파트 %d · 항목 %d",
        len(parts),
        sum(len(part["items"]) for part in parts),
    )
    return parts


def _tidy(parsed: ImportedApplication) -> list[dict[str, Any]]:
    """빈 것을 걷어내고 상한을 건다. 모델 출력은 믿되 모양은 여기서 보장한다."""
    parts: list[dict[str, Any]] = []
    total_items = 0
    for part in parsed.parts[:_MAX_PARTS]:
        items = []
        for item in part.items:
            title = item.title.strip()
            body = item.body.strip()[:_MAX_BODY_CHARS]
            if not body:
                continue  # 답변 없는 문항은 넣지 않는다 — 질문도 나오지 않는다
            items.append({"title": title or f"항목 {len(items) + 1}", "body": body})
            total_items += 1
            if total_items >= _MAX_ITEMS:
                break
        if items:
            parts.append({"part": part.name.strip() or f"파트 {len(parts) + 1}", "items": items})
        if total_items >= _MAX_ITEMS:
            break
    return parts


def sniff_mime(data: bytes) -> str | None:
    """파일 머리로 본 종류. 받는 종류가 아니면 None."""
    for magic, mime in _MAGIC:
        if data.startswith(magic):
            return mime
    return None


POSTING_PROMPT = """이 파일은 채용공고(직무 기술서)다. 본문을 글자 그대로 텍스트로 옮겨라.

- 요약·보완·번역을 하지 않는다. 문장과 항목의 순서를 지킨다.
- 표는 줄마다 "항목: 내용"으로 푼다. 머리글자·불릿은 "- "로 통일한다.
- 사이트의 메뉴·광고·쿠키 안내처럼 공고와 무관한 화면 요소는 뺀다.
- 결과는 본문 텍스트만 낸다. 앞뒤에 설명을 붙이지 않는다.
"""


def extract_posting(data: bytes, *, client: Any = None, model: str = MODEL_QUALITY) -> str:
    """채용공고 파일(PDF·PNG·JPG)의 본문을 텍스트로 옮긴다.

    구조를 만들지 않는다. 채용공고는 리서치 프롬프트에 그대로 실리는 문자열이라
    (`posting`), 화면의 입력란에 채워 넣을 본문만 있으면 된다.

    Raises:
        ValueError: 받는 종류의 파일이 아니거나 글을 읽지 못했을 때.
    """
    mime = sniff_mime(data)
    if mime is None:
        raise ValueError("PDF·PNG·JPG 파일만 읽을 수 있습니다")
    from google.genai import types

    if client is None:
        from google import genai

        client = genai.Client()

    response = client.models.generate_content(
        model=model,
        contents=[types.Part.from_bytes(data=data, mime_type=mime), POSTING_PROMPT],
        config=types.GenerateContentConfig(temperature=0),
    )
    text = (response.text or "").strip()
    if not text:
        raise ValueError("채용공고 파일에서 글을 읽지 못했습니다")
    logger.info("채용공고 파일 가져오기: %s, %d자", mime, len(text))
    return text[:_MAX_POSTING_CHARS]
