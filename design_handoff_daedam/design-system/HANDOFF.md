# 대담 — 확정 디자인 핸드오프 (2026-09-10)

이 폴더가 구현 대상입니다. 저장소(`geniemo/daedam`, `web/src`)의 현재 코드와 **다른 부분만** 아래에 적었습니다. 값은 `tokens/*.css`와 `ui_kits/web/*.jsx`가 정본이고, 이 문서는 그 지도입니다.

## 폴더

```
tokens/            colors · typography · spacing · effects · fonts  (styles.css가 @import)
components/core/   Card · PrimaryButton · OutlineButton · TextField · TextArea · Label · SectionLabel · Chip · ProgressBar · IndeterminateBar · Dots · Caret · Icons · useViewport(useNarrow)
components/navigation/Chrome.jsx
components/stage/  Avatar(구체) · Waveform · FlatWaveform
ui_kits/web/       index.html(홈 → 준비 완료 → 면접 → 분석 중 → 리포트) · landing.html · onboarding.html · states.html
ui_kits/mobile.html  네 페이지를 390px 폰 프레임으로 나란히 (주소 뒤 ?w=390 으로 폭 강제)
assets/logo/       symbol · symbol-on-dark · symbol-mono · app-icon · wordmark   +  assets/favicon.svg
guidelines/        색·타이포·간격·브랜드 스펙 카드
readme.md          규칙 전체   ·   SKILL.md   요약 규칙
```

`ui_kits/web/*.html`은 브라우저에서 바로 열립니다(Babel 런타임으로 `.jsx`를 읽음). 각 화면 파일 상단 주석에 대응하는 저장소 파일이 있습니다.

## 코드에 반영할 것

### 1. 토큰 (`web/src/index.css`)
- 밝은 화면을 **종이 바탕**으로: `--color-bg #F5F3EF`, `--color-surface-2 #FAF8F4`, 구분선 `#F0EDE7 / #ECE8E1 / #F3F0EA`, 테두리 `#E3DFD7 / #E9E5DE / #EBE7E0`, 입력 `#CBC6BC / #D9D4CB`, 헤더 `rgba(245,243,239,.92)`
- 강조 `--color-accent #B8802E`(배경 `#F8F0E3`, 선 `#EADCC4`), 긍정 `#3A7A68`, 청취 `#5AA48D`
- 카드 그림자 `--shadow-card: 0 1px 2px rgba(22,35,58,.05), 0 6px 20px -14px rgba(22,35,58,.12)`
- **무대 토큰 신설**: `--stage-bg`, `--stage-amber #D9A86C`, `--stage-mint #8FCFBC`, `--stage-sand #D9B98C`, `--stage-paper #F4EFE6`, `--stage-ink-warm #E9E3D8`, `--stage-dim #8F897D`, `--stage-dim-2 #7F796E`, `--stage-line-warm`, `--stage-keylight-rgb 255,205,160`, `--stage-mint-rgb`, `--gradient-sphere`, `--gradient-sphere-sheen`, `--gradient-voice-amber`, `--gradient-voice-mint`, `--shadow-sphere` — 값은 `tokens/colors.css`
- 키프레임 추가: `dm-slide`(불확정 막대), 확장 전환은 화면에서 인라인 키프레임

### 2. 무대 (`Stage.tsx` → `components/stage/Avatar.jsx`)
링 아바타를 버리고 **무광 유리 구체**로. `--gradient-sphere` + sheen + `--shadow-sphere`, 안의 불은 말할 때 `--gradient-voice-amber`, 들을 때 `--gradient-voice-mint`(1.4s 전환), 바깥 번짐은 키라이트/민트 rgb. 진폭은 ref→style. 크기: 면접 `clamp(150, 24vh, 216)`, 문턱·리서치·분석 128, 랜딩 데모 150, 홈 미리 보기 56, 리포트 머리 72. `data-avatar-slot` 유지.

### 3. 면접 (`Interview.tsx`, `SelfView.tsx` → `ui_kits/web/Interview.jsx`)
- 바탕 `--stage-bg` + 정지한 키라이트(위쪽 타원, 말할 때 .10 / 들을 때 .06). 비네트·헤더 페이드 없음
- **질문은 구체 바로 아래 44px**: 가는 색선 28×1(앰버/민트) + Pretendard 25/600/-.02em, `--stage-paper`, 두 줄 높이 상시 확보. 덩이(구체+44+질문)를 세로 중앙에
- 셀프뷰 **240×180**(우상단 74/30). **거울 배치**: "내 모습 크게 보기" → 웹캠이 가운데 4:3 `min(420, 100vh−380)`, 면접관은 우상단 92 PiP, 두 상자가 .45s에 자리를 트레이드, 질문은 가운데 것 아래를 따라감. 시계는 거울일 때 좌상단 상태 문장 옆
- 파형 모래색 `--stage-sand`, 폭 3 이하면 둥글림 0. 종료 버튼 필(pill), `--stage-line-warm` 테두리

### 4. 준비 완료 (`Ready.tsx` → `ui_kits/web/Ready.jsx`)
- 폭 760 → **860**. 제목 아래 설명 문장 제거
- **문턱 띠**(`data-threshold`): 무대 D 정지 화면, 구체 128, "면접관이 기다리고 있습니다", 제목 "지금 면접장에 들어갑니다", 안내 "면접은 15분 내외로 진행됩니다. 면접관에게 직무역량과 인성 · 컬처핏을 어필해보세요.", 시작 버튼(paper 배경·잉크 글자) 오른쪽, 하단 1px 선 아래 **단계 줄 가운데 정렬**(01 자기소개 — 02 직무역량 — 03 인성·컬처핏 — 04 마무리, 연결선 28). 단계 카드 4개·하단 시작 행 제거
- 시작 → 띠가 화면 전체로 커지는 **확장 전환 .45s**(`App.jsx enterStage`: 띠 좌표 한 번 → CSS 키프레임 → 460ms 뒤 면접 화면). 그 외 페이드 없음

### 5. 홈 (`Home.tsx` → `ui_kits/web/Home.jsx`, variant `strip`)
- **기록 띠**(제목 아래 한 줄, 완료된 면접이 1건 이상일 때): 면접 N회 · 평균 · 최근 점수, 회차별 점수 막대(14px, 마지막만 앰버), **반복된 보완점**(리포트 2건 이상에서 같은 보완점 → 문장 + "N회 지적", 없으면 "반복된 보완점이 아직 없습니다"), 오른쪽 "리포트 보기". 데이터는 리포트 `coaching.improvements`를 가로질러 집계 — 서버 API 필요
- 준비 완료 카드 중 최근 하나를 **다음 면접**으로 상단에 크게(300px 무대 미리 보기 + 회사·직무 + 면접 시작하기 · 준비 내용 보기), 나머지는 격자. 카드 폭 720 미만이면 무대가 위로 올라가는 세로 쌓기(ResizeObserver)
- 킷의 `rail` · `dense` 변형은 비교용, 구현하지 않음
- **빈 상태**: "첫 회사를 등록해 보세요 / 회사를 등록하면 대담의 노하우를 통해 면접을 준비합니다. (줄바꿈) 준비가 끝나면 면접을 시작해보세요." 버튼 하나

### 6. 분석 중 · 리서치 · 리포트 머리
- 분석 중(`Progress.tsx`): 무대 D, 구체 128, "면접이 끝났습니다. 수고하셨습니다 / **답변을 평가 중입니다**", 앰버 불확정 막대. 실패·무응답 상태도 같은 무대 위 (`States.jsx`)
- 리서치 진행(`Research.tsx`): "면접관이 준비하고 있습니다" — 왼쪽 구체, 오른쪽 진행 로그 (`States.jsx ResearchStage`)
- 리포트(`Report.tsx`): 머리를 **무대 띠**로 — 구체 72 + 회사·직무 + 총평 + 점수 56px. 나머지 섹션은 밝은 화면 그대로

### 7. 랜딩 (`Landing.tsx` → `ui_kits/web/Landing.jsx`)
- 폭 1160 → **1240**. 부제 18px, 단계 제목 28px, 단계 본문 16px/1.8, 왼쪽 열 360, 보조 글자 최소 13.5, 회색 `#8E98A8` 대신 muted
- 제목 셋째 줄 회사 이름 회전(2.6s) + `image-slot` 로고 자리(사용자 채움, 무채색)
- 데모 창 = 무대 D 축소판(구체 150, 질문 18/600)

### 8. 로고 · 아이콘
- 심볼 **C3**(`assets/logo/`): 원 하나를 x=9.0 / 10.6에서 갈라 왼쪽 잉크(면접관), 오른쪽 앰버(지원자). `Chrome.tsx`(22) · `Landing.tsx` · `Onboarding.tsx`(26)의 사각 표식과 `public/favicon.svg` 교체. 워드마크 간격 10
- 글리프(→ ✓ ▲ ▼ ▶ ❚❚) 전부 **선 아이콘**(`components/core/Icons.jsx`, 1.5px)으로. `CheckDot` 안도 SVG 체크

### 9. 반응형 (전 화면)
- 분기 **하나**: 720px 미만이 좁은 화면(`md:`). 킷 각 화면은 `useNarrow()` 한 값으로 갈라져 있으니 그대로 `md:` 접두어로 옮기면 된다. 중간 단계 없음
- 공통: 페이지 좌우 여백 32 → 16~20 · 제목 한 단계 축소(44→30, 27→23, 25→21, 점수 56→44) · 2~3열 격자 → 1열(음성 지표만 2열) · 헤더는 이름 글자 숨기고 아바타만(여백 16) · 카드 격자 `minmax(min(340px,100%),1fr)`
- 홈: 기록 띠 1열(세로 구분선 제거, 보완점 문장 줄바꿈), 레일 변형 1열, 제목 행 wrap
- 준비 완료: 문턱 띠 wrap — 구체 88 + 문구 한 줄, 시작 버튼 열은 100% 폭으로 아래(버튼 가로 100%), 단계 줄 연결선 제거·wrap(columnGap 16); 리서치 카드 행 wrap; 카메라 미리 보기 `aspect-ratio 4/3`, 최대 320
- 면접(600 미만): 상단 여백 14/16, 셀프뷰 132×99(우상단 16/8), 거울 PiP 64, 구체 min 120 · ≤ 폭 50%, 거울 폭 `min(4/3·높이, 폭−32)`, 질문 18px · 폭 100%−32, 하단 파형 영역 84, 셀프뷰 링크 세로 쌓기(구분점 제거). 영역 크기는 ResizeObserver로
- 리포트: 무대 머리 wrap(여백 22/20, 제목 21, 점수 44는 아래 줄에 가로 배치 + 위 1px 선), 지표 2열, 전달력·종합 평가 1열, 답변 행 질문 줄바꿈(지속시간·표정 칩 숨김), 전사+영상 1열
- 랜딩: 히어로 1열(제목 30, 로그인 버튼 세로 100%), 단계 프레임 1열(제목 23, 여백 44), 대화 1열, 데모 창 min-height 380 · 질문 16, 마무리 띠 64/20 · 26px
- 온보딩: 여백 18/20 · 0 20 64. 전환 갤러리: `auto-fit minmax(300, 1fr)`, 리서치 무대 1열
- `<meta name="viewport" content="width=device-width, initial-scale=1">` 필수

## 바꾸지 않은 것
온보딩(3c), 등록 2단계, 리서치 리포트 검토, 계정·크레딧·약관, 리포트의 지표·전달력·답변별 코칭 구조와 카피.
