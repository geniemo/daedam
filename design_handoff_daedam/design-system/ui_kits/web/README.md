# UI kit — 대담 web

Recreation of the Vite + React app in `geniemo/daedam` (`web/src/screens/*`). Cosmetic and click-through; data is mocked.

| File | Source | Notes |
|---|---|---|
| `index.html` | App.tsx + Chrome.tsx + Progress.tsx | 홈 → 준비 완료 → 면접 → 분석 중 → 리포트. 카드별로 리포트 변형(영상 有 / 오디오만 / 답변 없음) |
| `landing.html` · `Landing.jsx` | screens/Landing.tsx, components/ProviderMark.tsx | 로그인 전 첫 화면(2a). 회사 칩 5.2초 순환, 타이핑 질문, 01·02·03 단계, 마무리 띠 |
| `onboarding.html` · `Onboarding.jsx` | screens/Onboarding.tsx | 이름 → 동의 두 단계(3c). 밑줄 입력, 성 뺀 호칭 |
| `states.html` · `States.jsx` | screens/Progress.tsx, screens/ApplicationGuide.tsx | 분석 중 3상태, 질문 재생성 2상태, 지원서 가이드 모달 |
| `Home.jsx` | screens/Home.tsx | 카드 ready / researching / done(점수 · 답변 없음 · 분석 중), 안내 배너 |
| `Ready.jsx` | screens/Ready.tsx | 시작 전 확인 게이트(마이크 실측 + 수동 2건), 카메라 상태 4종 + 320×240 미리보기, 크레딧 확인 박스 |
| `Interview.jsx` | screens/Interview.tsx, video/SelfView.tsx | components/stage의 Avatar·Waveform 사용. 종료 버튼 하나 |
| `Report.jsx` | screens/Report.tsx, screens/Delivery.tsx, video/expression.ts | 회차 칩, Metric(compact·측정 불가), 전달력(시선 3×3·표정·흐름 띠), 답변별 전사+영상 248열, 빈 리포트 5상태 |

Not recreated (exist in the app): Register (2 steps), Research, Review, Account, Credits, Legal. They use only the tokens and primitives in this system.

Each screen file registers itself on `window.Daedam<Name>`; the primitives and stage components come from `components/**` via the loader at the bottom of each page.
