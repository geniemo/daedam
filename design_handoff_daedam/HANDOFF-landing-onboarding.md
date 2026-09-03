# Handoff: 랜딩 + 온보딩 개선

대상 저장소: `geniemo/daedam` (`web/src/screens/Landing.tsx`, `web/src/screens/Onboarding.tsx`)
디자인 시스템: 이 프로젝트의 `tokens/*.css`, `readme.md`. 토큰 이름은 `web/src/index.css`의 `@theme`과 같다.

이 문서는 **두 화면만** 다룬다. 나머지 화면은 그대로 둔다.

참고 파일 (이 폴더):
- `landing.html` + `Landing.final.jsx` — 랜딩 확정안 (2a 라이브 데모). 브라우저에서 열어 보는 시안. **프로덕션 코드가 아니다** — 기존 Tailwind 클래스 방식으로 다시 구현한다.
- `onboarding.html` + `Onboarding.final.jsx` — 온보딩 확정안. 같음.

---

## 1. Landing — 2a "라이브 데모" + 카피 "벅차오름"

### 왜 바꾸나
기존 랜딩은 1440px 화면에 560px 글 기둥 하나라 비어 보인다. 확정안은 밝은 바탕을 유지하되, 히어로 우측에 **스스로 돌아가는 면접관 창**을 둔다. 회사가 바뀌면 질문이 바뀐다 — "그 회사에 맞춘 질문"을 말이 아니라 예시로 보여준다. 아래로 01·02·03 단계가 실제 화면 조각으로 이어진다.

### 구조 (위에서 아래로)

**① 헤더** — 기존 Chrome과 같은 규격. sticky 64px, `--header-bg` + blur 8, 하단 `1px solid --color-line`. `max-width 1160`, `padding 0 32px`. 좌 로고(26/10, 20px 워드마크) · (flex 1) · 우 "로그인" 버튼(13.5px/600, `padding 9px 16px`, `1px solid --color-field`, 흰 배경). **로그인 버튼은 히어로의 소셜 버튼으로 스크롤**한다 — 별도 로그인 페이지가 없다.

**② 히어로** `max-width 1160`, `padding 72px 32px 80px`, 그리드 `minmax(0,1fr) minmax(0,1fr)` gap 56, `align-items: center`
- **좌측**
  - 눈썹: 5px 머스터드 점 + "AI 음성 모의면접" 12.5px/600/+.04em 머스터드, margin-bottom 22
  - h1 44px/700/-.04em, lh 1.22, `word-break: keep-all`, 두 줄: **대담과 함께 / 미리 면접장에 들어가세요**
  - 부제 16px lh 1.75 `--color-body-2`, max-width 440, margin-top 22: **몇 번이든 다시 연습하세요.**
  - 로그인 버튼 행 `id="login"`, margin-top 36, gap 10, `flex-wrap`. 기존 `LoginButton` 그대로. 각 `min-width 236`, 높이 50
  - 안내 줄("첫 면접 무료 · …") **없음**
  - 요약 3개 (margin-top 40, gap 28): 값 22px/700/-.03em + 설명 12px `--color-muted`
    `4단계` 자기소개 · 직무역량 · 인성 · 마무리 / `6가지` 음성 지표를 권장 범위와 비교 / `답변마다` 녹음을 다시 듣고 문장을 고치기
- **우측 — LiveDemo 창** (max-width 640, min-height 440, `--color-stage` 배경, `1px solid --color-stage-line`, radius 4, overflow hidden, 비네트 `--gradient-stage-vignette`)
  - 상단 행 `padding 18px 22px`: 상태 점 6px(타이핑 중 머스터드 / 끝나면 초록) + "면접관이 말하고 있습니다"/"듣고 있습니다" 13px `--color-stage-ink` · (flex 1) · "{회사} · {직무}" 12.5px `--color-stage-muted-2` (바뀔 때 `dm-fade`)
  - 가운데: 아바타 **150px 슬롯** (Interview.tsx Avatar를 150/206 비율로 축소; 링 포함). 말할 때 머스터드 링, 끝나면 초록 링
  - 자막 영역 min-height 78, max-width 520, 16.5px/500/-.01em `--color-stage-ink` 가운데 정렬. **타이핑 효과** 28ms/자, 끝에 2px 머스터드 커서
  - 하단 상태 영역 높이 92: 타이핑 중 "답변이 끝나면 마이크가 열립니다" 12px `--color-stage-muted-3` / 끝나면 파형(16개, 높이 28)
  - 맨 아래 `padding 0 22px 16px`: "이 질문의 출처" 11px `--color-stage-muted` + 출처 문구 11px `--color-stage-muted-2`
  - 창 아래 회사 칩 4개 (gap 6, 가운데): pill, 12px, `padding 5px 11px`. 선택 = `--color-ink` 배경 흰 글자, 비선택 = 투명 + `--color-line` 테두리 + `--color-muted` 글자. **5.2초마다 자동 순환**, 클릭으로도 선택

**데모 데이터** (회사 → 질문 → 출처). 시안 값이며 실제 서비스에서는 고정 예시로 두면 된다:
| 회사 | 직무 | 질문 | 출처 |
|---|---|---|---|
| 누리테크 | 서비스기획 | 저희가 올해 공개한 파트너 정산 서비스를 써보셨다면, 어떤 점을 먼저 개선하시겠습니까? | 2026년 3월 보도자료 · 채용공고 우대사항 |
| 세종바이오 | 마케팅 | 지원서에 쓰신 SNS 캠페인 경험을, 처방약 광고 규제가 있는 저희 업계에서는 어떻게 바꿔 적용하시겠어요? | 지원서 경험 2 · 회사 IR 자료 |
| 한빛금융 | IT기획 | 작년 저희 앱 장애 때 고객 공지가 늦었다는 지적이 있었는데, 기획자로서 무엇을 먼저 바꾸시겠습니까? | 2025년 11월 뉴스 · 인재상 "책임" |
| 오름소프트 | 백엔드 개발 | 지원서의 트래픽 3배 처리 경험에서, 병목이 DB였는지 애플리케이션이었는지 어떻게 판단하셨나요? | 지원서 경험 1 · 기술 블로그 |

**③ 단계 섹션 3개** `max-width 1160`, `padding 0 32px 40px`. 각 섹션은 `StepFrame`: 그리드 `300px 1fr` gap 48, `padding 56px 0`, 상단 `1px solid --color-line`. 좌측 = 라벨(12px/600/+.05em 머스터드) + h2(25px/700/-.03em, lh 1.3) + 본문(14.5px lh 1.75 `--color-body-2`), 우측 = 화면 조각

| 라벨 | h2 | 본문 | 우측 |
|---|---|---|---|
| 01 회사 조사 | **실제와 같은 면접관과 대화하세요** | 공신력 있는 근거를 통해 기업을 조사합니다. 실제 면접관이 할 법한 질문을 받아보세요. | ResearchLog — Research.tsx 5단계 로그 목업. **행 높이 고정**(각 행 `min-height 40`, 결과 문장은 항상 자리를 차지하고 완료 시 opacity 0→1). 2.2초마다 다음 단계, 5단계 뒤 처음으로. 상단 불확정 막대 `dm-slide` |
| 02 음성 면접 | **얼버무린 자리를 먼저 들켜보세요** | 파고드는 꼬리질문을 받아보세요. 숫자가 빠지면 숫자를, 근거가 빠지면 근거를 되묻습니다. 모의면접에서 먼저 당황해보세요. | 대화 카드 4장 2×2 (면접관·나·면접관·나). 카드 `padding 18`, 화자 점 5px(면접관 머스터드 / 나 초록) + 11.5px/600, 본문 13.5px lh 1.7(면접관 600 잉크 / 나 400 body-2). 세 번째 카드에 "꼬리질문" 칩(10.5px, `1px solid --color-line-2`, radius 2) |
| 03 답변 코칭 | **정확한 지표와 함께 리뷰하고 개선하세요** | 녹음을 다시 들으면서 답변마다 잘한 점과 빠진 것을 확인하고, 다음 면접장에서 그대로 말할 수 있게 고쳐 쓴 문장을 받으세요. | ScoreCard(점수 40px + 지표 3개) + CoachCard(Q3 · 재생 바 · 잘한 점 · 이렇게 바꿔보세요). **Report.tsx의 Metric/Playback/코칭 블록 규격과 같다** — 재사용 |

대화 카드 문구: ① 면접관 "그 프로젝트에서 가장 어려웠던 판단은 무엇이었나요?" ② 나 "분류 기준을 바꾸는 게 가장 어려웠습니다. 팀원들은 기존 기준을 유지하자고 했는데…" ③ 면접관 "팀원들을 어떤 근거로 설득하셨나요? 비교 자료가 있었습니까?" (꼬리질문) ④ 나 "음… 3개월 데이터로 두 기준을 나눠 봤을 때 회전율 차이가…"

**④ 마무리 띠** — 상단 `1px solid --color-line`, 배경 `--color-surface`. 내부 `max-width 1160`, `padding 96px 32px`, 가운데 정렬
- h2 34px/700/-.04em, lh 1.3, 두 줄: **연습은 여기서 끝내고 / 합격 소식을 전하세요**
- 부제 없음, 버튼 없음

**⑤ 푸터 줄** 같은 흰 배경 안, `padding 0 32px 40px`, 12px `--color-faintest`: "면접 중 음성과 웹캠 영상이 기록되고, 답변 분석에 쓰입니다." · (flex 1) · 이용약관 · 개인정보처리방침 (링크 `--color-faint`)

### 반응형
- 모든 2열 그리드는 `minmax(0,1fr)`로 — 고정 px 열 금지 (좁은 폭에서 가로 스크롤이 생겼다). StepFrame의 `300px 1fr`도 900px 아래에서는 1열로
- 로그인 버튼 행은 항상 `flex-wrap`
- 본문 한국어에 `word-break: keep-all`
- 지표 카드 안 판정·범위는 `white-space: nowrap`, 행만 `flex-wrap` (글자 중간이 끊겼다)
- 1000px 아래: 히어로 1열 — 카피 위, 데모 창 아래

### 로그인 버튼
`Landing.tsx`의 `LoginButton`·`ProviderMark.tsx` 그대로. `getProviders()`가 빈 배열이면 기존 안내문("로그인 설정이 없는 서버입니다…")을 같은 자리에.

---

## 2. Onboarding — 3c "두 단계"

### 왜 바꾸나
한 화면에 이름 + 동의 2건 + 안내 + 버튼이 560px 기둥에 몰려 있다. 확정안은 **화면 하나에 질문 하나**: 이름 → 동의. 빈 공간이 여백으로 읽힌다.

### 공통 프레임
- 배경 `--color-bg`, `min-height 100vh`, column
- 상단 바 `padding 26px 32px`: 좌측 로고(26/10, 20px 워드마크) · (flex 1) · 우측 진행 막대 2개 (22×2.5px, gap 5; 현재 이하 `--color-ink`, 미도달 `--color-field-2`, `transition background .3s`)
- 본문: 세로 중앙, `padding 0 32px 96px`, 컨테이너 **460px**
- 단계 전환은 `dm-fade .3s` (key 바꿔 리마운트)
- 본문 한국어에 `word-break: keep-all`

### STEP 1 — 이름
- "1 / 2" 12px/600/+.05em 머스터드
- h1 30px/700/-.035em, lh 1.3, 두 줄: **면접관이 어떻게 / 부르면 좋을까요**
- 본문 14.5px lh 1.7 `--color-body-2`, margin `14px 0 32px`: **실명으로 적어 주세요.**
- 입력: **밑줄형**. 22px/600/-.02em, 배경 투명, 테두리 없음, `border-bottom 2px solid --color-field` (focus: `--color-ink`), `padding 10px 0`, 폭 100%, placeholder "예: 박지원", autoFocus. Enter = 다음
- 입력 아래 반응 문구 **없음**
- 하단 행 margin-top 36: 좌 "다른 계정으로 로그인" 12.5px `--color-faint` (기존 logout 동작) · (flex 1) · 우 "다음" 버튼 높이 46, `padding 0 28px`, 14px/600, 이름 비면 disabled (`--color-faintest` 배경)

### STEP 2 — 동의
- "2 / 2"
- h1 두 줄: **{이름} 님, 시작하기 전에 / 한 가지만 확인해 주세요**. {이름}은 입력값에서 성을 뺀 것 — 3자 이상이면 마지막 두 글자, 아니면 그대로 (Chrome.tsx의 `slice(-2,-1)` 이니셜 규칙과 같은 방향)
- 본문 margin `14px 0 28px`: **면접 중 음성과 웹캠 영상이 기록되고, 분석을 위해 Google Gemini로 처리됩니다.** (기존 안내문을 여기로 올린다)
- 동의 목록: 상단 `1px solid --color-line`, 각 행 `padding 16px 0` + 하단 선. 행 = [CheckDot/EmptyDot 16px] [라벨 14.5px `--color-ink`] (flex 1) [전문 보기 12.5px `--color-faint` 밑줄, 새 탭]
  - 이용약관에 동의합니다 → /terms
  - 개인정보 수집·이용에 동의합니다 → /privacy
- 하단 행 margin-top 32: 좌 "← 이름 고치기" 13px `--color-muted` (STEP 1로) · (flex 1) · 우 "동의하고 시작하기" 높이 46, `padding 0 28px`, 둘 다 체크 전 disabled. 전송 중 "저장 중…", 실패 시 기존 error 문구를 버튼 위 13px 머스터드

### 로직
`Onboarding.tsx`의 상태(name/terms/privacy/error/sending)와 `completeOnboarding` → `queryClient.setQueryData(['me'])` 흐름 그대로. 추가되는 건 `step` 하나. 라우트는 나누지 않는다 — 게이트(`RequireLogin`)에서 거는 구조를 유지해야 주소로 건너뛸 수 없다.

---

## 3. 하지 않는 것
- 별도 로그인 페이지 — 없다. 헤더 "로그인"은 히어로의 소셜 버튼으로 스크롤
- "첫 면접 무료", "15~20분" 같은 조건 문구 — 넣지 않는다
- 마무리 띠의 부제·버튼 — 넣지 않는다
- 이름 단계의 부가 설명("음성 인식에도 씁니다", "면접관은 ~라고 부릅니다") — 넣지 않는다

## 4. 시안 파일 읽는 법
`*.final.jsx`는 인라인 스타일 React다. 값(px, 색 토큰, 간격)은 그대로 옮기되, 코드베이스 방식(Tailwind 클래스 + `--color-*` 토큰)으로 다시 쓴다. `Avatar`/`Waveform`/`ScoreCard`/`CoachCard`/`ResearchLog`는 각각 `Interview.tsx`/`Report.tsx`/`Research.tsx`의 기존 컴포넌트를 목업 데이터로 재사용하는 것이 맞다 — 새로 만들지 않는다.
