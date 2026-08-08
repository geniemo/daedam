# Handoff: 대담 (Daedam) — AI 음성 모의면접 서비스

## Overview

대담은 한국 취업준비생을 위한 AI 음성 모의면접 서비스입니다. 사용자가 지원할 회사·직무·지원서를 등록하면 Gemini Deep Research API로 해당 회사를 조사하고, 그 리포트를 근거로 면접 질문을 생성합니다. 사용자는 음성 에이전트와 15~20분간 한국어 면접을 진행하고, 종료 후 정량 피드백 리포트를 받습니다.

이 번들은 전체 사용자 플로우(랜딩 → 등록 → 리서치 → 검토 → 준비 완료 → 면접 → 분석 → 리포트)를 담은 클릭 가능한 프로토타입입니다.

## About the Design Files

**이 번들의 HTML 파일은 프로덕션 코드가 아니라 디자인 레퍼런스입니다.** 의도한 화면 구성과 동작을 보여주는 프로토타입이며, 그대로 복사해 배포할 코드가 아닙니다.

해야 할 일은 **이 디자인을 대상 코드베이스의 기존 환경에서 다시 구현하는 것**입니다. React, Vue, Next.js 등 이미 쓰고 있는 프레임워크와 컴포넌트 라이브러리, 상태 관리 방식, 라우팅 규칙을 따르십시오. 아직 환경이 없다면 프로젝트에 맞는 프레임워크를 선택해 구현하면 됩니다.

프로토타입의 모든 데이터는 하드코딩된 목업입니다. 실제 구현에서는 API 연동으로 대체되어야 합니다.

## Fidelity

**High-fidelity (hifi)** 입니다. 색상, 타이포그래피, 여백, 인터랙션이 모두 확정된 값입니다. 아래 Design Tokens 섹션의 정확한 hex 값과 px 단위를 사용해 픽셀 단위로 재현하십시오.

단, 다음 두 가지는 의도적으로 미완성입니다.

- **아바타**: `data-avatar-slot="true"` 속성이 붙은 원형 컨테이너는 나중에 영상·3D·립싱크 아바타 API로 교체될 슬롯입니다. 현재는 추상적인 원형 도형이 들어 있습니다. 주변의 발화 링, 파형, 컨트롤은 이 컨테이너 바깥에 있으므로 내부만 교체하면 됩니다.
- **마이크 테스트**: 준비 완료 화면에 링크만 있고 화면은 만들지 않았습니다.

`대담 와이어프레임.dc.html`은 초기 구조 탐색 기록입니다. 구현 참고용이 아니라 왜 이 구조가 선택됐는지 맥락을 보려면 참고하십시오.

---

## Screens / Views

전체 9개 화면이며, 단일 페이지 안에서 `screen` state로 전환됩니다. 실제 구현에서는 라우트로 분리하는 것을 권합니다.

### 공통 헤더 (chrome)

면접 진행(`interview`), 분석 중(`analyzing`), 질문 재생성(`regen`) 화면에서는 숨깁니다.

- **위치·크기**: `position: sticky; top: 0; z-index: 40`, 높이 64px
- **배경**: `rgba(244,245,247,.92)` + `backdrop-filter: blur(8px)`, 하단 `1px solid #E2E6ED`
- **내부 컨테이너**: `max-width: 1160px; margin: 0 auto; padding: 0 32px`, flex, `gap: 32px`
- **로고**: 22×22px 정사각형 `1.5px solid #16233A` 안에 8×8px `#B57F1C` 정사각형, 우측에 "대담" 17px/700/`letter-spacing: -.02em`, 둘 사이 `gap: 9px`
- **내비게이션**: "내 면접" 하나만. 14px/600, `#16233A`
- **우측**: 사용자 이름 13px `#5F6B7E`, 30×30px 아바타 (`1px solid #C9D0DB`, 배경 `#fff`, 12px/600 `#5F6B7E`)

---

### 1. 홈 — 내 면접 (`screen: 'home'`)

**목적**: 등록한 회사 목록을 보고, 상태에 따라 다음 행동으로 진입합니다.

**레이아웃**: `max-width: 1160px; padding: 44px 32px 80px`

- 상단 행: 제목 블록 + `flex: 1` 스페이서 + 우측 CTA, `align-items: flex-end`, `margin-bottom: 28px`
  - 제목 "내 면접" 27px/700/`-.03em`
  - 부제 "회사를 등록하면 그 회사에 맞춘 질문으로 면접을 준비합니다." 14px `#5F6B7E`
  - CTA "회사 등록하기" — 배경 `#16233A`, 흰 글자 14px/600, `padding: 11px 20px`, `border-radius: 3px`
- 카드 그리드: `repeat(auto-fill, minmax(340px, 1fr))`, `gap: 16px`

**회사 카드** (`min-height: 172px`, `padding: 20px`, `1px solid #E2E6ED`, `border-radius: 4px`, 배경 `#fff`, `cursor: pointer`)

카드 상단은 공통입니다. 회사명 17px/700/`-.02em`, 직무 13px `#5F6B7E`, 우측 상단에 등록·면접 날짜 11.5px `#8E98A8`. 그 아래 `flex: 1` 스페이서로 하단 영역을 바닥에 붙입니다.

하단 영역은 상태별로 다릅니다.

| 상태 | 표시 내용 | 클릭 시 |
|---|---|---|
| `ready` | `#B57F1C` 5px 원형 점 + "면접 준비 완료" 12.5px/600 `#B57F1C`. 구분선(`1px solid #EEF0F4`, `padding-top: 11px`) 아래 좌측 "4단계 · 15~20분" 12.5px `#5F6B7E`, 우측 "시작하기 →" 13px/600 | 준비 완료 화면 |
| `researching` | "면접 준비 중 · N%" 12.5px `#5F6B7E`, 우측 "자세히 보기 →" 12px `#8E98A8`. 아래 3px 진행 바(트랙 `#EEF0F4`, 채움 `#B57F1C`, `transition: width .4s ease`). 그 아래 현재 진행 중인 단계 라벨 12.5px `#5F6B7E` | 리서치 진행 화면 |
| `done` | 구분선 위로 좌측에 "면접 완료" 12px `#8E98A8` + "리포트 보기 →" 12.5px `#5F6B7E`, 우측에 점수 28px/700/`-.04em` + "점" 12px `#8E98A8` | 리포트 |

**빈 카드**: 마지막에 `1px dashed #C9D0DB` 카드, 중앙 정렬 "+ 새 회사 등록" 13.5px `#8E98A8`. 클릭 시 등록 시작.

---

### 2. 등록 STEP 1 — 회사·직무 (`screen: 'register', regStep: 1`)

**목적**: 어느 회사의 어떤 직무에 지원하는지 받습니다.

**레이아웃**: 상단 바는 `max-width: 1160px`, 본문은 `max-width: 520px; margin: 0 auto`

- 상단 바 (`padding: 26px 0 34px`): 좌측 "✕ 나가기" 13px `#5F6B7E`, 우측에 "1 / 2" 12.5px `#5F6B7E` + 스텝 인디케이터 (22×2.5px 바 2개, `gap: 5px`. 현재 `#16233A`, 미도달 `#D8DDE5`)
- "STEP 1" 12px/600 `#B57F1C`, `letter-spacing: .05em`, `margin-bottom: 10px`
- 제목 "어느 회사에 지원하시나요" 25px/700/`-.03em`
- 설명 "회사와 직무를 알려주시면 그 회사의 채용공고와 최근 소식을 조사해 질문을 준비합니다." 14px `#5F6B7E`, `line-height: 1.6`, `margin-bottom: 32px`
- 입력 필드 4개, `gap: 20px`

| 라벨 | 필수 | placeholder | 비고 |
|---|---|---|---|
| 회사명 | 필수 | 예) 누리테크 | |
| 직무 | 필수 | 예) 서비스기획 | |
| 채용공고 링크 | 선택 | https:// | 라벨 옆 "선택" 12px `#8E98A8` |
| 직무 소개서 (JD) | 선택 | — | 드롭존. "선택 · 있으면 질문이 더 정확해집니다" |

- 입력 스타일: `1px solid #C9D0DB`, `border-radius: 3px`, `padding: 12px 13px`, 14.5px, 배경 `#fff`. focus 시 `border-color: #16233A` (outline 제거)
- 라벨: 13px/600
- JD 드롭존: `1px dashed #C9D0DB`, `padding: 18px`, 배경 `#fff`. 안쪽에 "파일을 끌어다 놓거나" 13px `#5F6B7E`, "파일 선택" 버튼(`1px solid #C9D0DB`, `padding: 6px 12px`, 12.5px, 배경 `#FAFBFC`), 우측 끝에 "직접 붙여넣기" 12.5px `#5F6B7E` + `border-bottom: 1px solid #C9D0DB`
- 하단 우측 "다음" 버튼: 배경 `#16233A`, 14px/600, `padding: 12px 30px`

---

### 3. 등록 STEP 2 — 지원서 (`screen: 'register', regStep: 2`)

**목적**: 회사 양식 그대로 지원서를 파트·항목 2단 구조로 받습니다. 항목 하나하나가 꼬리질문의 근거가 됩니다.

**레이아웃**: `max-width: 760px; margin: 0 auto`

- "STEP 2" / 제목 "지원서를 넣어 주세요" / 설명 "회사 양식 그대로 파트를 만들고 그 안에 항목을 나눠 넣으면, 항목 하나하나를 파고드는 질문이 만들어집니다."
- 파트 카드 목록, `gap: 14px`

**파트 카드** (`1px solid #E2E6ED`, `border-radius: 4px`, 배경 `#fff`)

- 헤더 (`padding: 15px 18px`, 하단 `1px solid #F1F3F6`, `cursor: pointer`): 파트명 15px/700, 항목 수 배지(11.5px `#8E98A8`, `1px solid #E2E6ED`, `border-radius: 2px`, `padding: 1px 6px`), 우측 caret `▲`/`▼` 12px `#B7C0CD`
- 펼침 영역 (`padding: 16px 18px`, `gap: 10px`): 항목 카드 목록 + "+ 항목 추가" (`1px dashed #D8DDE5`, 중앙 정렬, 12.5px `#8E98A8`)

**항목 카드** (`1px solid #E8EBF0`, `border-radius: 3px`, 배경 `#FAFBFC`)

- 헤더 (`padding: 11px 13px`, `cursor: pointer`): 제목 13px/600 `#2A3A55`, 우측에 글자 수 또는 "비어 있음" 11.5px `#8E98A8`, caret 11px
- 펼침 영역 (`padding: 0 13px 13px`, `gap: 9px`): textarea + 하단 행
  - textarea: `1px solid #D8DDE5`, `padding: 10px 11px`, 13.5px, `line-height: 1.65`, `min-height: 96px`, `resize: vertical`, 배경 `#fff`. placeholder "내용을 붙여넣어 주세요"
  - 하단 행: 좌측 안내 11.5px `#8E98A8` (내용이 있으면 "이 항목을 근거로 꼬리질문이 만들어집니다", 없으면 "비워 두어도 등록할 수 있습니다"), 우측 "삭제" 12px `#8E98A8`

**주의**: 항목 제목은 헤더에만 표시합니다. 펼쳤을 때 제목 입력란을 따로 두면 같은 문자열이 두 번 보입니다.

**기본 시드 데이터** (프로토타입 기준. 실제로는 빈 상태로 시작)

- 경험 — "경험 1 — 교내 물류 데이터 분석 프로젝트" (본문 있음), "경험 2 — 스타트업 서비스기획 인턴 4개월" (비어 있음)
- 자격증 — "SQLD (SQL 개발자)", "ADsP (데이터분석 준전문가)"
- 자기소개서 — "문항 1 — 지원 동기와 입사 후 포부", "문항 2 — 협업 과정에서 갈등을 해결한 경험", "문항 3 — 직무를 위해 준비한 노력"

- "+ 파트 추가" (`1px dashed #C9D0DB`, `padding: 15px`, 중앙 정렬, 13px `#8E98A8`, 배경 `#fff`). 회색 힌트 "경력 · 포트폴리오 · 기타" `#B7C0CD`
- 하단 행: "← 이전" 13.5px `#5F6B7E`, "파일로 올리기 (PDF · DOCX)" 12.5px `#8E98A8`, 우측 "등록하고 준비 시작" 버튼(`#16233A`, `padding: 12px 26px`)

---

### 4. 리서치 진행 (`screen: 'research'`)

**목적**: Deep Research가 무엇을 조사 중인지 보여주며 기다리게 합니다.

**레이아웃**: `max-width: 760px; padding: 44px 32px 80px`

- "← 내 면접" 13px `#5F6B7E`
- 카드 (`padding: 28px`, `1px solid #E2E6ED`, `border-radius: 4px`, 배경 `#fff`)
  - 상단: 좌측 회사명 20px/700 + 직무 13.5px `#5F6B7E`, 우측 진행률 22px/700 `#B57F1C` + 남은 시간 12px `#8E98A8`
  - 3px 진행 바 (`#EEF0F4` / `#B57F1C`, `transition: width .5s ease`), `margin-bottom: 26px`
  - "조사 진행 상황" 12px/600 `#8E98A8`, `letter-spacing: .04em`
  - 단계 목록: 각 행 `padding: 13px 0`, 하단 `1px solid #F1F3F6`, `gap: 13px`
    - 완료: 14×14px 원 배경 `#16233A`, 흰 `✓` 9px. 라벨 `#16233A`. **결과 문장 표시**
    - 진행 중: 13×13px 원, `1.5px solid #B57F1C`, `border-top-color: transparent`, `animation: spin 1s linear infinite`. 라벨 `#B57F1C`. **결과 문장 숨김**
    - 대기: 13×13px 원 `1.5px solid #E2E6ED`. 라벨 `#B7C0CD`. **결과 문장 숨김**
  - 라벨 14px/600, 결과 문장 12.5px `#8E98A8` `line-height: 1.5`
  - 하단 안내 박스: 배경 `#FAFBFC`, `1px solid #EEF0F4`, `padding: 13px 15px`, 12.5px `#5F6B7E` — "창을 닫아도 준비는 계속됩니다. 완료되면 알려드립니다."

**중요**: 아직 실행되지 않은 단계의 결과 문장을 미리 보여주면 안 됩니다. 완료된 단계만 결과를 표시합니다.

**5단계 로그**

1. 채용공고와 직무기술서 분석 — "요구 역량 12개를 추출하고 우선순위를 매겼습니다."
2. 최근 1년 뉴스 · IR · 기술 블로그 수집 — 회사별 뉴스 문장
3. 인재상 · 조직문화 정리 — "채용 페이지와 재직자 인터뷰에서 반복되는 표현을 모았습니다."
4. 지원서와 대조 · 검증이 필요한 항목 추출 — "경험 1의 성과 수치와 본인 기여도를 확인할 질문이 필요합니다."
5. 질문 준비 — "4단계에 걸쳐 8개 질문과 꼬리질문을 준비합니다."

---

### 5. 준비 완료 (`screen: 'ready'`)

**목적**: 무엇이 준비됐는지 보여주고 면접을 시작하게 합니다.

**레이아웃**: `max-width: 760px; padding: 44px 32px 80px`

- "← 내 면접"
- `#B57F1C` 5px 점 + "면접 준비 완료" 12px/600 `#B57F1C` `letter-spacing: .05em`
- 제목 "{회사} · {직무}" 27px/700/`-.03em`
- 설명 "채용공고와 최근 소식, 지원서를 함께 읽고 질문을 준비했습니다. 한국어 음성으로 15~20분간 진행됩니다." 14px `#5F6B7E`, `margin-bottom: 30px`

**단계 카드 4개**: `grid-template-columns: repeat(4, 1fr)`, `gap: 10px`, 각 `padding: 15px 14px`

- "01" 11.5px/600 `#B7C0CD` / 단계명 14px/700 / "N개 질문" 11.5px `#8E98A8`
- 자기소개(2개) · 직무역량(3개) · 인성·컬처핏(2개) · 마무리(1개)

**리서치 리포트 카드** (`padding: 20px`, `gap: 14px`)

- 헤더 행: "리서치 리포트" 12px/600 `#8E98A8` `letter-spacing: .04em`, `flex: 1` 스페이서, 우측 "8월 4일 생성" 11.5px `#B7C0CD`
- 정정 사항이 있으면 안내 박스: 배경 `#FBF7EF`, `1px solid #EFE2CB`, `padding: 10px 12px`, 12.5px `#3E4C63` — "남기신 정정 사항 N건을 함께 넘겨 질문을 다시 뽑았습니다."
- 본문 행 (상단 `1px solid #F1F3F6`, `padding-top: 14px`): 좌측에 리포트 제목 14.5px/700 + "확인이 필요한 대목 N곳" 12.5px/600 `#B57F1C`, 우측에 "리포트 열기" 버튼(`1px solid #C9D0DB`, `padding: 9px 14px`, 12.5px/600, 배경 `#fff`)

**시작 전 확인 카드** (`padding: 20px`, `gap: 12px`, `margin-bottom: 26px`)

- "시작 전 확인" 12px/600 `#8E98A8`
- 체크 항목 3개, `gap: 10px`
  - 완료: 15×15px 원 배경 `#16233A` + 흰 `✓` 9px. 텍스트 13.5px `#16233A`
  - 미완료: 15×15px 원 `1.5px solid #C9D0DB`. 텍스트 13.5px `#5F6B7E`
  - "마이크가 연결되어 있습니다" (완료, 우측에 "테스트하기" 12.5px `#5F6B7E` + `border-bottom: 1px solid #C9D0DB`) / "조용한 곳에서 진행하시길 권합니다" / "중간에 멈추면 이어서 진행할 수 있습니다"
- 하단 행: 좌측 "지원서 수정" 13px `#5F6B7E`, 우측 "면접 시작하기" 버튼(`#16233A`, 15px/600, `padding: 14px 34px`)

---

### 6. 리포트 검토 (`screen: 'review'`)

**목적**: Deep Research 리포트 원문을 사용자가 확인하고, 틀린 대목을 표시하거나 아는 내용을 메모로 남기게 합니다.

**설계 근거 (중요)**: 질문 생성의 입력은 **리포트 원문 + 사용자 정정 사항** 두 개입니다. 리포트에서 사실을 추출한 별도 목록을 만들어 그것만 편집하게 하면, 사용자가 고친 것과 질문에 들어가는 것이 달라져 편집이 무의미해집니다. 그래서 문서 자체가 검토 대상이고, 사용자 입력은 원문을 수정하지 않는 주석(delta)으로 쌓입니다. 질문 생성 시 정정 사항이 원문보다 우선한다고 프롬프트에 지시하십시오.

**레이아웃**: `max-width: 1180px; padding: 34px 32px 130px`. 2단 flex, `gap: 36px`, `align-items: flex-start`

**좌측 사이드바** (`width: 236px`, `position: sticky; top: 88px`, `gap: 20px`)

- "확인이 필요한 대목 N" 11.5px/600 `#B57F1C` `letter-spacing: .04em`
- 카드 3개: `1px solid #EFE2CB`, 배경 `#FBF7EF`, `border-radius: 3px`, `padding: 11px 12px`, `cursor: pointer`
  - 제목 12.5px/600, 사유 11.5px `#8E98A8` `line-height: 1.55`
  - 클릭 시 해당 블록으로 스크롤 (`getBoundingClientRect().top + pageYOffset - 96`, `behavior: 'smooth'`)
- 구분선 위에 "목차" 11.5px/600 `#8E98A8`, 섹션 제목 목록 12.5px `#5F6B7E`

확인이 필요한 대목 3건:
- "팀 리드 중심 의사결정" — 익명 커뮤니티 게시글 한 건이 근거입니다
- "기업 고객 비중 70%" — 2025년판 소개서 기준이라 현재와 다를 수 있습니다
- "변화 시점 표" — 보도 시점 기준이며 실제 적용일과 다를 수 있습니다

**우측 문서** (`flex: 1`, `1px solid #E2E6ED`, `border-radius: 4px`, `padding: 36px 40px`, 배경 `#fff`)

- "8월 4일 생성" 11.5px `#B7C0CD`
- h1 23px/700/`-.03em` `line-height: 1.4`
- 안내 "사실과 다른 대목에 표시하거나, 알고 계신 내용을 메모로 남겨 주세요." 13px `#5F6B7E`
- 섹션: h2 16px/700/`-.02em`, `margin: 30px 0 6px`, `padding-bottom: 10px`, 하단 `1px solid #EEF0F4`

**블록** — 문단(`p`), 불릿(`li`), 표(`table`), 출처(`refs`) 네 종류. 출처를 뺀 나머지가 주석 대상입니다.

각 블록은 flex 행입니다. `padding: 9px 10px 9px 12px`, `gap: 14px`, 좌측 `border-left: 2px solid` (기본 `transparent`, 표시됨 `#B57F1C`), 배경 (기본 `transparent`, 표시됨 `#FDFBF7`).

- 좌측 열 (`flex: 1`, `gap: 8px`): 본문 + 표시 칩 + 메모 목록 + 메모 입력
  - 문단 14px `line-height: 1.9`, 불릿 14px `line-height: 1.85` (앞에 `—` 12px `#C9D0DB`)
  - 본문 색: 기본 `#2A3A55`, 표시됨 `#A9B2C0`
  - 표: `1px solid #EEF0F4`, `border-radius: 3px`, `grid-template-columns: 96px 1fr 120px`. 헤더 행 배경 `#FAFBFC`, 11.5px/600 `#5F6B7E`. 본문 행 12.5px, 하단 `1px solid #F4F6F9`
  - 출처: `[n]` 11.5px `#B7C0CD` (`width: 20px`) + 라벨 12.5px `#5F6B7E`
  - 표시 칩: "사실과 다름으로 표시함" 11px/600 `#B57F1C`, 배경 `#FBF7EF`, `1px solid #EFE2CB`, `padding: 3px 8px`
  - 메모 항목: 배경 `#FAFBFC`, `1px solid #EEF0F4`, `padding: 10px 12px`. "메모" 라벨 11px/600 `#B57F1C`, 본문 13px `#3E4C63`, 우측 "삭제" 11.5px `#8E98A8`
  - 메모 입력: input(`1px solid #D8DDE5`, `padding: 9px 11px`, 13px, placeholder "아는 내용이나 정정할 내용을 적어 주세요") + "남기기" 버튼(`#16233A`, 흰 글자 12.5px/600, `padding: 9px 14px`)
- 우측 열 (`flex: none`, `gap: 6px`, `padding-top: 3px`): 두 버튼, 11.5px, `padding: 5px 9px`, `border-radius: 2px`, `white-space: nowrap`
  - "사실과 다름" / 표시 후 "표시 해제" — 기본 `#8E98A8` / `1px solid #E2E6ED` / 배경 `#fff`, 표시됨 `#B57F1C` / `#EFE2CB` / `#FBF7EF`
  - "메모" — `#8E98A8`, `1px solid #E2E6ED`, 배경 `#fff`

**하단 고정 바** (`position: fixed; bottom: 0`, `z-index: 30`)

- 배경 `rgba(255,255,255,.94)` + `backdrop-filter: blur(8px)`, 상단 `1px solid #E2E6ED`
- 내부 `max-width: 1180px`, `padding: 14px 32px`
- 좌측 요약 13px `#5F6B7E` — 없으면 "표시하거나 메모한 대목이 없습니다", 있으면 "정정 N건 · 메모 M건"
- 우측 "돌아가기" 13px `#5F6B7E` + 주 버튼
  - 편집 없음: "이대로 진행", 배경 `#fff`, 글자 `#16233A`, `1px solid #C9D0DB`
  - 편집 있음: "질문 다시 뽑기", 배경 `#16233A`, 흰 글자, `1px solid #16233A`

**리포트 문서 구조** (7개 섹션 · 17개 블록)

1. Executive Summary — 문단 1
2. 회사와 사업 구조 — 문단 1, 불릿 3
3. 최근 1년의 변화 — 문단 1, 표 1 (시점/내용/관련 조직 3행), 문단 1
4. 인재상과 조직문화 — 문단 1, 불릿 3
5. 직무 요구역량 — 불릿 3
6. 면접에서 검증될 가능성이 높은 지점 — 문단 1
7. 출처 — 각주 9건

본문에는 `[1]` 형태의 각주 번호가 인라인으로 들어갑니다. 프로토타입에서는 평문이지만, 실제 구현에서는 클릭 시 출처 항목으로 이동하게 만들면 좋습니다.

---

### 7. 질문 재생성 (`screen: 'regen'`)

정정 사항이 있을 때만 거칩니다. 헤더 숨김. `max-width: 520px`, `padding: 120px 32px`, 중앙 정렬

- 34×34px 스피너 (`2px solid #E2E6ED`, `border-top-color: #B57F1C`, `animation: spin .9s linear infinite`)
- "고치신 내용으로 질문을 다시 뽑고 있습니다" 18px/700
- "정정 N건 · 메모 M건 · 잠시만 기다려 주세요" 13.5px `#5F6B7E`
- 220×2.5px 진행 바
- 완료 시 준비 완료 화면으로 복귀

---

### 8. 면접 진행 (`screen: 'interview'`)

**목적**: 몰입해서 음성 면접을 진행합니다. 화면이 시선을 뺏지 않는 것이 목표입니다.

**레이아웃**: `position: fixed; inset: 0`, 배경 `#0E1726`, `z-index: 60`, flex column

**상단 오버레이** (`position: absolute; top: 0`, `padding: 22px 30px`, `z-index: 3`)

- 좌측: 6px 원형 점 + 상태 라벨 13.5px `#E8ECF3`
  - 면접관 발화 중: 점 `#B57F1C`, "면접관이 말하고 있습니다"
  - 사용자 답변 중: 점 `#4E9E7E`, "듣고 있습니다"
- 우측: 단계 라벨 13px `#8896AC` ("2단계 · 직무역량"), 1×12px 구분선 `#2A3A55`, 남은 시간 13px `#E8ECF3` `font-variant-numeric: tabular-nums`

**아바타 영역** (`flex: 1`, 중앙 정렬)

- 컨테이너 340×340px
- 발화 중일 때만 배경 링 2개
  - 340×340px 원, `radial-gradient(circle, rgba(181,127,28,.5), transparent 68%)`, `animation: pulse2 2.6s ease-in-out infinite` (scale 1 → 1.26, opacity .32 → .06)
  - 270×270px 원, `1px solid rgba(181,127,28,.34)`, `animation: pulse 2.2s ease-in-out infinite` (scale 1 → 1.14, opacity .5 → .14)
- **아바타 슬롯** (`data-avatar-slot="true"`): 206×206px 원. `linear-gradient(160deg, #233047, #16223A)`, `1px solid #2E3F5C`, `overflow: hidden`, `animation: breathe 4.5s ease-in-out infinite` (scale 1 → 1.035)
  - 내부 하이라이트: `radial-gradient(circle at 34% 28%, rgba(255,255,255,.07), transparent 58%)`
  - 내부 도형: 96×96px 원 `1px solid rgba(232,236,243,.22)` 안에 44×44px 원 `rgba(181,127,28,.85)`
  - **이 컨테이너 내부만 교체하면 실제 아바타로 대체됩니다.** 상태(`speaking` / `listening`)를 아바타 API의 이벤트에 연결하십시오.

**자막** (`showCaption` prop으로 on/off. 기본 on)

- 최대 660px, 중앙 정렬, 17px/500 `#E8ECF3` `line-height: 1.65` `letter-spacing: -.01em`
- 질문이 바뀔 때 `fade .4s ease` (opacity 0 → 1, translateY 6px → 0)

**하단 상태 영역** (높이 104px, 중앙 정렬)

- 사용자 답변 중: 파형 — 3px 폭 막대 16개, 높이 38px, `gap: 3px`, 배경 `#B57F1C`, `transform-origin: center`, `animation: wave 1.1s ease-in-out infinite` (scaleY .22 → 1). 막대별 `animation-delay` 0~.39s 무작위 분산
- 면접관 발화 중: "답변이 끝나면 마이크가 열립니다" 12.5px `#8395AF`

**하단 컨트롤** (`padding: 0 30px 26px`, `gap: 14px`)

- 단계 진행 바 4개: `flex: 1`, 높이 2.5px, 트랙 `#22314A`, 채움 `#B57F1C`, `transition: width .5s ease`
- 하단 행: 좌측 "질문 N / 8" 12.5px `#8395AF`, 우측 "일시정지" · "종료" 버튼 (`1px solid #2E3F5C`, 투명 배경, `#C7D0DE` 13px, `padding: 9px 18px`)

**일시정지 오버레이**

- `position: absolute; inset: 0`, 배경 `rgba(14,23,38,.86)` + `backdrop-filter: blur(6px)`, `z-index: 5`
- 모달 390px, 배경 `#16233A`, `1px solid #2E3F5C`, `padding: 28px`
  - "면접을 잠시 멈췄습니다" 19px/700 `#F2F5F9`
  - "이어서 진행하거나, 지금까지의 답변만으로 리포트를 받을 수 있습니다." 13.5px `#8896AC`
  - "이어서 진행" 버튼 배경 `#B57F1C`, 흰 글자 14px/600, `padding: 12px`
  - "종료하고 리포트 받기" 13px `#C7D0DE`
  - "면접 취소 · 기록을 남기지 않습니다" 12.5px `#8395AF`

**질문 8개** (프로토타입 목업. `{회사}`, `{제품}`은 리서치 결과로 치환)

1. (자기소개) 먼저 간단히 자기소개 부탁드립니다.
2. (자기소개) 여러 회사 중 저희 {회사}에 지원하신 이유가 무엇인가요?
3. (직무역량) 지원서에 적으신 물류 데이터 분석 프로젝트에서 본인이 맡은 역할을 설명해 주세요.
4. (직무역량) 그 프로젝트에서 가장 어려웠던 판단은 무엇이었고, 어떤 근거로 결정하셨나요?
5. (직무역량) 저희가 올해 공개한 {제품}를 써보셨다면, 어떤 점을 먼저 개선하시겠습니까?
6. (인성·컬처핏) 동료와 의견이 부딪혔을 때 어떻게 풀어가시는 편인가요?
7. (인성·컬처핏) 실패했다고 생각하는 경험과, 그때 배운 점을 말씀해 주세요.
8. (마무리) 마지막으로 궁금한 점이나 하고 싶은 말씀이 있으신가요?

---

### 9. 분석 중 (`screen: 'analyzing'`)

헤더 숨김. `position: fixed; inset: 0`, 배경 `#0E1726`, 중앙 정렬, `gap: 18px`

- 96×96px 원, 아바타와 같은 그라디언트, `animation: breathe 3s ease-in-out infinite`
- "면접이 끝났습니다. 수고하셨습니다" 19px/600 `#F2F5F9`
- "답변을 분석하고 있습니다 · 약 1분" 13.5px `#8896AC`
- 240×2.5px 진행 바 (트랙 `#22314A`, 채움 `#B57F1C`)

---

### 10. 피드백 리포트 (`screen: 'report'`)

**목적**: 코칭 중심 리포트. 점수에서 시작해 답변별 개선 제안으로 내려갑니다.

**레이아웃**: `max-width: 860px; padding: 40px 32px 90px`. 섹션 사이 `padding: 30px 0`, `border-bottom: 1px solid #E2E6ED`

**상단 바**: "← 내 면접" / 우측 "공유" · "PDF로 저장" 12.5px `#5F6B7E`

**헤더** (flex, `gap: 34px`, `padding-bottom: 30px`)

- 좌측: 메타 12.5px `#8E98A8` ("7월 28일 면접 · 18분 · 질문 8개"), 제목 "{회사} · {직무}" 25px/700/`-.03em`, 총평 14px `#3E4C63` `line-height: 1.7` `max-width: 480px`
- 우측: 점수 52px/700/`-.05em` + "/ 100" 15px `#8E98A8`, 아래 "같은 직무 지원자 중 상위 24%" 12.5px/600 `#B57F1C`

**단계별 점수**

- 섹션 라벨 12px/600 `#8E98A8` `letter-spacing: .04em`
- 각 행 (`gap: 16px`, `align-items: center`): 단계명 13.5px/600 (`width: 96px`), 6px 바 (`flex: 1`, 트랙 `#EAEDF2`, 채움 `#16233A`, `animation: grow .7s ease`), 점수 15px/700 (`width: 34px`, 우측 정렬, tabular-nums), 근거 12px `#8E98A8` (`width: 76px`, 우측 정렬)
- 자기소개 78 (Q1~Q2 평균) · 직무역량 78 (Q3~Q5 평균) · 인성·컬처핏 85 (Q6~Q7 평균) · 마무리 80 (Q8)

**산술 일관성 (중요)**: 종합 점수는 답변 8개 점수의 평균과 일치해야 합니다. 단계별 점수도 해당 질문 그룹의 평균이어야 합니다. 프로토타입 기준 답변 점수 84/71/88/79/68/86/83/80 → 평균 79.875 → 종합 80. 필러 워드 지표(24회)도 답변별 필러 합계(2+6+1+3+5+2+3+2)와 일치합니다.

**음성 지표** — `grid-template-columns: repeat(3, 1fr)`, `gap: 12px`

각 카드 `padding: 16px`, `gap: 7px`: 라벨 12.5px `#5F6B7E` / 값 23px/700/`-.03em` tabular-nums + 단위 12px `#8E98A8` / 3px 게이지 / 판정 11.5px/600 + 권장 범위 11.5px `#B7C0CD`

| 지표 | 값 | 게이지 | 판정 | 범위 |
|---|---|---|---|---|
| 말하기 속도 | 312 음절/분 | 62% | 적정 `#2F6B55` | 280~340 권장 |
| 필러 워드 | 24 회 | 78% | 다소 많음 `#B57F1C` | 답변당 3회 |
| 답변 길이 | 62 초 평균 | 58% | 적정 `#2F6B55` | 45~90초 권장 |
| 답변 시작까지 | 2.4 초 | 40% | 적정 `#2F6B55` | 3초 이내 |
| 침묵 · 머뭇거림 | 8 % | 70% | 주의 `#B57F1C` | 5% 이하 권장 |
| 목소리 크기 · 안정성 | 안정 | 84% | 양호 `#2F6B55` | 흔들림 적음 |

**내용 평가** — `grid-template-columns: 1fr 1fr`, `gap: 14px`

- 좌측 "잘한 점" 13px/700 `#2F6B55`, 항목 앞에 `✓` 12px `#2F6B55`
- 우측 "보완할 점" 13px/700 `#B57F1C`, 항목 앞에 `→` 12px `#B57F1C`
- 항목 13.5px `#3E4C63` `line-height: 1.65`, `gap: 12px`

**답변별 피드백**

카드 8개, `gap: 10px`. `border-radius: 4px`, 배경 `#fff`, 테두리 기본 `1px solid #E2E6ED`, 펼침 시 `#C9D0DB`

- 헤더 행 (`padding: 15px 18px`, `gap: 13px`, `cursor: pointer`): "Q1" 11.5px/600 `#B7C0CD` (`width: 22px`) / 단계명 11.5px `#8E98A8` (`width: 74px`) / 질문 요약 13.5px/600 (`flex: 1`, ellipsis) / 길이 11.5px `#B7C0CD` / 점수 15px/700 (`width: 28px`) / caret 11px (`width: 12px`)
- **펼치면 헤더의 질문 요약을 비웁니다.** 바로 아래 전체 질문이 나오므로 같은 문장이 두 번 보이는 것을 막습니다.
- 펼침 영역 (`padding: 4px 18px 20px`, `gap: 16px`, `animation: fade .25s ease`)
  - 전체 질문 15px/600 `line-height: 1.6` (상단 `1px solid #F1F3F6`, `padding-top: 16px`)
  - 재생 바: `1px solid #E8EBF0`, `border-radius: 3px`, `padding: 10px 13px`, 배경 `#FAFBFC`. 26×26px 원형 재생 버튼(배경 `#16233A`, 흰 `▶` 9px), 파형 34개 막대(`flex: 1`, 배경 `#C9D0DB`, 높이 24~98%), 길이 11.5px `#8E98A8`, 좌측 구분선 뒤 "질문 음성" 11.5px `#5F6B7E`
  - "내 답변" 11.5px/600 `#8E98A8` + 스크립트 13.5px `#3E4C63` `line-height: 1.85`
  - "전체 스크립트 보기 · 필러 워드 N회 표시" 11.5px `#B7C0CD`
  - 개선 제안: `border-left: 2px solid #B57F1C`, `padding-left: 15px`. "이렇게 바꿔보세요" 11.5px/700 `#B57F1C`, 본문 13.5px `#2A3A55` `line-height: 1.8`
  - 태그 칩: 11.5px `#5F6B7E`, `1px solid #E8EBF0`, `border-radius: 2px`, `padding: 4px 9px`, 배경 `#FAFBFC`

**하단**: 좌측 "내 면접으로" 13px `#5F6B7E`, 우측 "이 회사로 다시 면접 보기" 버튼(`#16233A`, 14px/600, `padding: 13px 28px`)

---

## Interactions & Behavior

### 화면 전환

```
home ──(회사 등록하기)──> register(1) ──(다음)──> register(2)
                                                      │
                                          (등록하고 준비 시작)
                                                      ▼
home ◄──(카드: researching)──────────────────────► research
                                                      │ 100%
                                                      ▼
                                                    ready ◄──────┐
                                                      │           │
                                        (리포트 열기)  │           │ 완료
                                                      ▼           │
                                                   review ──> regen
                                                      │  (정정 有)
                                          (이대로 진행)│
                                                      ▼
                                                    ready
                                                      │
                                            (면접 시작하기)
                                                      ▼
                                                 interview ──(일시정지)──> paused overlay
                                                      │                        │
                                                      │ 질문 8개 소진 / 종료      │
                                                      ▼                        │
                                                 analyzing ◄───────────────────┘
                                                      │ 100%
                                                      ▼
                                                   report ──(다시 면접 보기)──> ready
```

홈 카드 클릭: `ready` → 준비 완료 / `researching` → 리서치 진행 / `done` → 리포트

### 타이머와 인터벌

- **리서치**: 120ms마다 2%씩 증가. 100%에서 카드 상태가 `researching` → `ready`로 바뀌고 준비 완료 화면으로 이동
- **면접**: 1초 간격. 한 질문당 14초 사이클 (발화 5초 → 청취 9초). 8질문 소진 시 자동 종료. 남은 시간은 900초에서 카운트다운
- **분석**: 70ms마다 4%. 100%에서 리포트로
- **질문 재생성**: 90ms마다 5%. 100%에서 준비 완료로
- 일시정지 중에는 면접 타이머가 진행되지 않습니다
- 화면을 벗어날 때 모든 인터벌을 정리해야 합니다

프로토타입의 속도는 시연용입니다. 실제로는 리서치 수 분, 면접 15~20분입니다.

### 애니메이션

| 이름 | 용도 | 정의 |
|---|---|---|
| `pulse` | 아바타 발화 링 (안쪽) | 2.2s ease-in-out infinite, scale 1→1.14, opacity .5→.14 |
| `pulse2` | 아바타 발화 링 (바깥) | 2.6s ease-in-out infinite, scale 1→1.26, opacity .32→.06 |
| `breathe` | 아바타 호흡 | 4.5s ease-in-out infinite, scale 1→1.035 |
| `wave` | 마이크 입력 파형 | 1.1s ease-in-out infinite, scaleY .22→1, 막대별 delay 분산 |
| `spin` | 로딩 스피너 | .9~1s linear infinite |
| `fade` | 화면·카드 진입 | .25~.4s ease, opacity 0→1 + translateY 6px→0 |
| `grow` | 점수 바 | .7s ease, width 0→목표 |

### 접근성

- 어두운 배경(`#0E1726`) 위 작은 텍스트는 `#8395AF` 이상을 쓰십시오. `#5D6E88`은 대비 3.3:1로 AA에 미달합니다
- 면접 화면의 버튼은 최소 44px 터치 영역을 확보하십시오

---

## State Management

```
screen          'home' | 'register' | 'research' | 'ready' | 'review'
                | 'regen' | 'interview' | 'analyzing' | 'report'
regStep         1 | 2
company, role   등록 폼 입력값
parts           [{ name, items: [{ title, body, len }] }]
cards           [{ id, company, role, date, status, pct?, score? }]
                status: 'ready' | 'researching' | 'done'
activeCard      현재 보고 있는 카드 id
researchPct     0~100
flags           { [blockId]: boolean }   리포트 블록별 '사실과 다름' 표시
memos           { [blockId]: string[] }  리포트 블록별 메모
memoOpenId      메모 입력창이 열린 블록 id
memoDraft       메모 입력 중인 값
regenPct        0~100
elapsed         면접 경과 초
qIndex          현재 질문 인덱스 0~7
phase           'speaking' | 'listening'
paused          boolean
analyzePct      0~100
openQ           리포트에서 펼쳐진 답변 인덱스 (-1이면 전부 접힘)
openPart        등록 STEP 2에서 펼쳐진 파트 인덱스
openItem        등록 STEP 2에서 펼쳐진 항목 인덱스
```

### 서버 연동이 필요한 지점

1. **회사 등록** — 회사·직무·공고 링크·JD·지원서(파트/항목 구조)를 저장하고 리서치 작업을 큐에 넣습니다
2. **리서치 진행 조회** — 단계별 진행 상황과 완료 여부를 폴링하거나 스트리밍합니다. 사용자가 창을 닫아도 서버에서 계속 진행되어야 합니다
3. **리포트 조회** — Deep Research 결과를 블록 단위로 받습니다. 블록마다 안정적인 id가 있어야 주석을 붙일 수 있습니다. 신뢰도가 낮은 블록에는 '확인 필요' 플래그와 사유를 함께 내려주십시오
4. **정정 사항 저장 + 질문 재생성** — flags와 memos를 블록 id와 함께 보냅니다. 서버는 리포트 원문과 정정 사항을 함께 프롬프트에 넣어 질문을 다시 생성합니다. 정정 사항이 원문보다 우선한다고 명시하십시오
5. **면접 세션** — 음성 에이전트와의 실시간 연결. 질문 진행 상태, 발화/청취 상태, 녹음 저장
6. **리포트 생성** — 점수, 음성 지표, 답변별 스크립트와 코칭, 녹음 파일 URL

### 아직 정하지 않은 것

- **꼬리질문 처리**: 현재는 질문 8개가 순서대로 나가는 구조입니다. 실제 면접은 답변에 따라 파고들어야 하므로, 리포트에서 "Q3-1" 같은 표기를 쓸지 정해야 합니다
- **면접 중단 복구**: 일시정지 모달에 "이어서 진행"이 있지만, 창을 닫았다가 돌아왔을 때의 복구 흐름과 홈 카드의 '진행 중' 상태는 만들지 않았습니다
- **빈 상태**: 처음 가입한 사용자가 보는 화면이 없습니다
- **회차 비교**: 같은 회사로 두 번째 면접을 봤을 때 지난 회차와 비교하는 화면이 없습니다

---

## Design Tokens

### Colors

| 용도 | 값 |
|---|---|
| 배경 | `#F4F5F7` |
| 표면 (카드) | `#FFFFFF` |
| 보조 표면 | `#FAFBFC` |
| 주 텍스트 | `#16233A` |
| 본문 텍스트 | `#2A3A55` |
| 부가 텍스트 | `#3E4C63` |
| 보조 텍스트 | `#5F6B7E` |
| 흐린 텍스트 | `#8E98A8` |
| 가장 흐린 텍스트 | `#B7C0CD` |
| 구분선 (연함) | `#F1F3F6`, `#EEF0F4`, `#F4F6F9` |
| 구분선 | `#E2E6ED`, `#E8EBF0`, `#EAEDF2` |
| 테두리 (입력) | `#C9D0DB`, `#D8DDE5` |
| 강조 (머스터드) | `#B57F1C` |
| 강조 배경 | `#FBF7EF`, `#FDFBF7` |
| 강조 테두리 | `#EFE2CB` |
| 긍정 | `#2F6B55` |
| 면접 화면 배경 | `#0E1726` |
| 면접 화면 표면 | `#16233A` |
| 면접 화면 테두리 | `#2E3F5C`, `#22314A` |
| 면접 화면 주 텍스트 | `#E8ECF3`, `#F2F5F9` |
| 면접 화면 보조 텍스트 | `#8896AC`, `#C7D0DE`, `#8395AF` |
| 청취 상태 점 | `#4E9E7E` |
| 아바타 그라디언트 | `linear-gradient(160deg, #233047, #16223A)` |

### Typography

**폰트**: Pretendard (fallback: Spoqa Han Sans Neo, -apple-system, system-ui, sans-serif)

CDN: `https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css`

| 용도 | 크기 / 굵기 / 자간 |
|---|---|
| 페이지 제목 | 25~27px / 700 / -.03em |
| 큰 숫자 (종합 점수) | 52px / 700 / -.05em |
| 중간 숫자 (지표) | 23px / 700 / -.03em |
| 카드 점수 | 28px / 700 / -.04em |
| 섹션 제목 | 16px / 700 / -.02em |
| 카드 제목 | 17px / 700 / -.02em |
| 강조 본문 | 15px / 600 |
| 본문 | 14px / 400 / line-height 1.7~1.9 |
| 보조 본문 | 13.5px / 400 / line-height 1.65~1.85 |
| 라벨 | 13px / 600 |
| 작은 텍스트 | 12.5px / 400 |
| 캡션 | 11.5px / 400~600 |
| 섹션 라벨 | 12px / 600 / letter-spacing .04em |
| 스텝 라벨 | 12px / 600 / letter-spacing .05em |

숫자에는 `font-variant-numeric: tabular-nums`를 씁니다.

### Spacing

4px 배수를 기본으로 하되 카드 내부는 실측값을 따릅니다.

- 페이지 좌우 여백 32px
- 컨테이너 최대 폭: 홈·헤더 1160px / 등록 STEP 1 520px / 등록 STEP 2·리서치·준비 완료 760px / 리포트 860px / 검토 화면 1180px
- 카드 내부 패딩 20px (큰 카드 28~40px)
- 카드 간격 10~16px
- 섹션 간격 30px

### Border radius

- 카드 4px
- 버튼·입력 3px
- 칩·배지 2px
- 원형 요소 50%

### Shadows

그림자를 쓰지 않습니다. 깊이는 테두리(`1px solid`)와 배경 대비로만 표현합니다. 고정 바에만 `backdrop-filter: blur(8px)`을 씁니다.

---

## Assets

외부 이미지나 아이콘 파일을 쓰지 않습니다.

- 아이콘류(`✓ ▶ → ← ✕ ▲ ▼ —`)는 모두 텍스트 문자입니다. 실제 구현에서는 코드베이스의 아이콘 세트로 교체하십시오
- 로고는 CSS 도형 2개(정사각형 테두리 + 채운 정사각형)로 만들었습니다
- 파형은 CSS 애니메이션과 계산된 높이값입니다
- 아바타 자리는 CSS 그라디언트입니다. 실제 아바타 API 연동 시 전부 교체됩니다
- 폰트만 CDN에서 불러옵니다

---

## Files

| 파일 | 내용 |
|---|---|
| `대담 프로토타입.dc.html` | 전체 플로우 하이파이 프로토타입. 이 문서가 설명하는 대상 |
| `대담 와이어프레임.dc.html` | 초기 구조 탐색. 등록·리서치 플로우 4안과 면접·리포트 각 2안. 구현 참고용이 아니라 결정 배경 참고용 |

프로토타입 파일은 브라우저에서 바로 열립니다. 상단 `<style>` 블록에 keyframes와 리셋만 있고, 나머지 스타일은 전부 인라인입니다. 로직은 파일 하단 `Component` 클래스에 있으며 `renderVals()`가 화면에 넘기는 값을 만듭니다.
