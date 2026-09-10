repo: geniemo/daedam
branch: main
path: web/src

## Last sync
date: 2026-09-10T03:12:00Z

### Updated in this project
- 홈 기록 띠(면접 횟수·평균·최근·회차 막대·반복된 보완점) 추가, 전 화면 반응형(720 분기, useNarrow) 적용, ui_kits/mobile.html
- 디자인 확정: 종이 바탕 + 앰버 빛, 무대 D 구체, 심볼 C3, 선 아이콘, 카드 그림자
- 비교용 스냅샷(v0·v1)·팔레트 토글·탐색 파일·옛 핸드오프 삭제
- HANDOFF.md에 코드와 다른 부분만 정리 — 이것이 구현 대상

## Sync history
- 2026-09-05T08:59:24Z — Stage.tsx 공유 컴포넌트, 랜딩(2a)·온보딩(3c) 재현, 준비 완료·리포트·홈 갱신
- 2026-09-03 — 구현 코드 대조, 리포트 전달력 섹션, 랜딩·온보딩 개선안

## Screen map
| 프로젝트 파일 | 저장소 파일 |
|---|---|
| tokens/*.css, styles.css | web/src/index.css |
| components/core/* | web/src/components/ui.tsx |
| components/navigation/Chrome.jsx | web/src/components/Chrome.tsx |
| components/core/useViewport.jsx | (신규) — Tailwind md: 분기에 대응 |
| components/stage/* | web/src/components/Stage.tsx |
| ui_kits/web/Home.jsx | web/src/screens/Home.tsx |
| ui_kits/web/Ready.jsx | web/src/screens/Ready.tsx |
| ui_kits/web/Interview.jsx | web/src/screens/Interview.tsx, web/src/video/SelfView.tsx |
| ui_kits/web/Report.jsx | web/src/screens/Report.tsx, Delivery.tsx, web/src/video/expression.ts |
| ui_kits/web/App.jsx | web/src/App.tsx, web/src/screens/Progress.tsx |
| ui_kits/web/States.jsx | web/src/screens/Progress.tsx, Research.tsx, ApplicationGuide.tsx |
| ui_kits/web/Landing.jsx | web/src/screens/Landing.tsx, web/src/components/ProviderMark.tsx |
| ui_kits/web/Onboarding.jsx | web/src/screens/Onboarding.tsx |
| assets/logo/*, assets/favicon.svg | web/public/favicon.svg |
| (킷에 없음) 등록·검토·계정·크레딧·약관 | web/src/screens/Register.tsx, Review.tsx, Account.tsx, Credits.tsx, Legal.tsx |
