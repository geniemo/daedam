# 대담 — 확정 디자인 핸드오프 (2026-09-06)

이 폴더가 구현 대상입니다. 저장소(`geniemo/daedam`, `web/src`)의 현재 코드와 **다른 부분만** 아래에 적었습니다. 값은 `tokens/*.css`와 `ui_kits/web/*.jsx`가 정본이고, 이 문서는 그 지도입니다.

## 폴더

```
tokens/            colors · typography · spacing · effects · fonts  (styles.css가 @import)
components/core/   Card · PrimaryButton · OutlineButton · TextField · TextArea · Label · SectionLabel · Chip · ProgressBar · IndeterminateBar · Dots · Caret · Icons
components/navigation/Chrome.jsx
components/stage/  Avatar(구체) · Waveform · FlatWaveform
ui_kits/web/       index.html(홈 → 준비 완료 → 면접 → 분석 중 → 리포트) · landing.html · onboarding.html · states.html
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

### 5. 홈 (`Home.tsx` → `ui_kits/web/Home.jsx`)
- 준비 완료 카드 중 최근 하나를 **다음 면접**으로 상단에 크게(300px 무대 미리 보기 + 회사·직무 + 면접 시작하기 · 준비 내용 보기), 나머지는 격자
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

## 바꾸지 않은 것
온보딩(3c), 등록 2단계, 리서치 리포트 검토, 계정·크레딧·약관, 리포트의 지표·전달력·답변별 코칭 구조와 카피.
