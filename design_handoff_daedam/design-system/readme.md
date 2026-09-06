# 대담 디자인 시스템

**대담(Daedam)** 은 한국 취업준비생을 위한 AI 음성 모의면접 서비스입니다. 회사·직무·지원서를 등록하면 Gemini Deep Research로 그 회사를 조사하고, 리포트를 근거로 질문을 만들어 15~20분 한국어 음성 면접을 진행합니다. 끝나면 답변별 코칭과 음성 지표가 담긴 리포트를 줍니다. 한 계정에 여러 회사가 카드로 쌓입니다.

이 시스템은 **코드에서 뽑아낸 것**입니다. 정본은 `geniemo/daedam` 저장소의 `web/src/index.css`(토큰)와 `web/src/components/ui.tsx`(프리미티브), `web/src/components/Stage.tsx`(아바타·파형)이고, 여기 적힌 값은 전부 그 파일에서 그대로 옮겼습니다. 둘이 어긋나면 코드가 맞습니다.

## Handoff

코드와 다른 부분만 모은 구현 지도는 `HANDOFF.md`입니다. 저장소 상태와의 대응은 `github.md`.

## Sources

- GitHub: `geniemo/daedam` (branch `main`) — `web/src/index.css`, `web/src/components/ui.tsx`, `Chrome.tsx`, `Stage.tsx`, `ProviderMark.tsx`, `web/src/screens/*.tsx`(ApplicationGuide 포함), `web/src/video/SelfView.tsx`, `expression.ts`, `web/public/favicon.svg`. 마지막 대조 2026-09-05.
- 디자인 핸드오프: 같은 저장소 `design_handoff_daedam/README.md` (프로토타입 기준 화면 10개 스펙). 구현이 핸드오프에서 벗어난 부분은 코드 주석에 실측 근거가 있고, 이 시스템은 **구현을 따릅니다**.
- 프로토타입 원본: 이 프로젝트의 `대담 프로토타입.dc.html`, `대담 와이어프레임.dc.html` (역사 참고용)

## Products

하나. **대담 web** — Vite + React SPA, 데스크톱 우선. 화면 14개: 랜딩, 온보딩, 홈(내 면접), 등록 1·2, 리서치 진행, 준비 완료, 리포트 검토, 질문 재생성, 면접 진행, 분석 중, 피드백 리포트, 계정, 크레딧, 약관 — 여기에 등록 2단계가 여는 지원서 가이드 다이얼로그 하나. 별도 로그인 페이지는 없습니다. 랜딩이 곧 로그인 화면이고, 헤더 "로그인"은 히어로의 소셜 버튼으로 내려보냅니다.

두 세계가 있습니다. **밝은 화면**(따뜻한 종이 바탕 `#F5F3EF` 위 흰 카드)과 **무대**(`--stage-bg`, 면접·문턱 띠·리서치 진행·분석 중·리포트 머리·랜딩 데모 창). 무대에서는 헤더가 사라지고 팔레트가 `--stage-*`로 바뀝니다. 두 세계는 같은 온도(앰버·민트)를 공유해 문을 열 때 색이 튀지 않습니다.

---

## Content fundamentals

**담백한 존댓말.** 조언자가 옆에서 말하듯 씁니다. 감탄사·이모지·느낌표 없음. "~합니다 / ~해 주세요 / ~있습니다"로 끝나고, 명령은 "~해 주세요"까지만.

- 상태를 사실로 적습니다. "면접 준비 완료", "듣고 있습니다", "답변을 분석하고 있습니다". 격려("잘하고 있어요!")를 쓰지 않습니다.
- 시선·표정은 **등급이 아니라 서술**입니다. "정면을 잘 유지했습니다. 가끔 오른쪽으로 시선이 갔습니다." 몇 %가 좋은지 근거가 없으니 관찰된 쏠림만 적습니다. 표본이 얇으면(얼굴 30초 미만, 스냅샷 10장 미만) "참고만 해 주세요"를 머스터드로 붙입니다.
- 가린 것과 끈 것을 구별합니다. "내 화면을 가렸습니다 · 촬영은 계속됩니다".
- 결과 없이 돌아온 이유는 홈 상단 배너 한 줄로 남깁니다(머스터드 배경, "닫기"). "크레딧이 부족해 면접을 시작하지 못했습니다." / "다른 탭에서 같은 면접이 열렸습니다. 새 탭에서 계속 진행해 주세요."
- 이름은 성을 빼고 부릅니다. "박지원 님"이 아니라 "지원 님" — 한글 3자 이상일 때만, 로마자·띄어쓴 이름은 그대로. 헤더 이니셜은 가운데 글자(김서연 → 서).
- 못 하는 건 못 한다고 씁니다. "이 면접에서는 재지 못했습니다", "시선 기록이 없습니다", "이 회차의 리포트가 없습니다". 0이나 그럴듯한 숫자로 채우지 않습니다.
- 돈이 걸린 행동은 한 번 더 묻습니다. "면접을 시작하면 크레딧 3개가 사용됩니다." 잔액을 작은 글씨로 적어두는 건 안내지 확인이 아닙니다.
- 기다림에는 무엇을 하는지와 기다려도 되는 이유를 적습니다. "창을 닫아도 준비는 계속됩니다. 완료되면 알려드립니다."
- 코칭은 **무엇이 빠졌는지 → 어떻게 고치는지** 순서로, 실제 문장을 제안합니다. "'제 제안이 실제 발주 주기에 반영된 경험이 있습니다'로 열면 첫 문장에서 이미 검증된 사람이라는 인상을 줍니다." 칭찬은 "잘한 점" 칸에 따로, 짧게.
- 섹션 라벨은 명사구: 조사 진행 상황, 음성 지표, 종합 평가, 답변별 피드백, 시작 전 확인. 코칭 소제목 셋은 고정: **잘한 점 / 더 듣고 싶었던 것 / 이렇게 바꿔보세요**.
- 버튼은 동사형 4~9자: 회사 등록하기, 등록하고 준비 시작, 면접 시작하기, 리포트 검토, 종료하고 리포트 받기, 이 회사로 다시 면접 보기. 뒤로가기는 "← 내 면접", 나가기는 "✕ 나가기".
- 영어는 안 씁니다. 예외는 "STEP 1" 표기와 "Executive Summary"(Deep Research 원문 제목) 정도.
- 사용자는 2인칭 호칭 없이 존댓말 어미로만 부릅니다. 면접관은 "면접관", 사용자 본인은 "내"(내 면접, 내 답변, 내 화면).
- 숫자 단위는 한글로 붙입니다: 음절/분, 초 평균, 회/분, 개 보유, 회차, 점.

## Visual foundations

**한 문장으로:** 평가 기관의 문서 같은 담백함에, 면접장의 조명 한 줄. 종이 위의 잉크, 어둠 속의 앰버.

### Color
- 바탕 `#F5F3EF`(종이), 카드 `#FFFFFF`, 인셋 `#FAF8F4`. 카드는 종이 바탕 위에 흰 면으로 뜨고(옅은 잉크 그림자 `--shadow-card` 하나), 카드 안의 인셋(전사, 재생 바, 메모)은 다시 아주 연한 종이색으로 내려갑니다. 세 단계로 끝.
- 텍스트 6단계: 잉크 `#16233A` → 본문 `#2A3A55` → `#3E4C63` → 보조 `#5F6B7E` → 흐린 `#8E98A8` → 가장 흐린 `#B7C0CD`. **위계는 굵기보다 이 회색 단계로 만듭니다.** 같은 줄 안에서 값은 잉크, 단위는 흐린 회색.
- **앰버 `#B8802E`는 "봐야 할 것"에만.** 준비 완료 점, STEP 라벨, 진행 바 채움, 범위 밖 지표, 보완할 점, 코칭 왼쪽 선, 로고의 오른쪽 조각. 무대의 앰버 `#D9A86C`와 같은 색상, 밝은 바탕용 농도입니다. 배경으로 쓸 때는 `#F8F0E3`+`#EADCC4` 테두리(확인 박스, 회원 탈퇴). 버튼 채움으로는 쓰지 않습니다.
- **초록 `#3A7A68`는 범위 안·정상·연결됨.** 잘한 점, 적정 판정, 연결된 계정 점. `#5AA48D`는 지원자의 목소리(듣는 점, 기록 중 점). 무대의 민트 `#8FCFBC` 계열.
- 빨강 없음. 실패도 머스터드 텍스트나 회색으로 말합니다.
- 무대: 바탕 `--stage-bg`(위에서 내려오는 밤 — `radial(120% 90% at 50% 18%, #1A1E2E → #0C0F19 → #07090F)`), 정지한 키라이트 `rgba(255,205,160,.06~.10)`(말할 때 조금 밝아짐). 글자는 따뜻한 흰색 `#F4EFE6`(paper) / `#E9E3D8`(ink-warm), 보조 `#8F897D`(dim) / `#7F796E`(dim-2), 선 `rgba(255,255,255,.12)`. 광원 둘: 앰버 `#D9A86C`(면접관), 민트 `#8FCFBC`(지원자). 파형은 모래색 `#D9B98C`. 옛 `--color-stage-*`(`#0E1726` 계열)는 무대 밖의 어두운 요소(검토 화면 등)에만 남습니다.
- 서드파티 마크(카카오 `#FEE500`, 구글 4색)는 로그인 버튼 안에서만 팔레트를 벗어납니다.

### Typography
- **Pretendard Variable 한 종.** 굵기 400/500/600/700. 디스플레이 서체 없음, 세리프 없음.
- 클수록 자간을 조입니다: 52px `-.05em`, 28px `-.04em`, 34px `-.035em`, 23~27px `-.03em`, 16~17px `-.02em`, 15px `-.01em`. 작은 라벨은 반대로 넓힙니다: 섹션 라벨 12px `+.04em`, STEP 12px `+.05em`.
- 면접 자막 19px/500/-.01em, lh 1.6, 폭 620 — 무대에서 유일하게 읽는 글자라 본문보다 크다.
- 본문 14px, 보조 13.5px, 라벨 13px/600, 작은 글 12.5px, 캡션 11.5px. 소수점 크기(13.5, 12.5, 11.5)를 반올림하지 않습니다.
- 행간은 용도별: 제목 1.2~1.4, 본문 1.6~1.7, 코칭 1.8, 전사 1.85, 리서치 문서 1.9.
- 숫자는 전부 `font-variant-numeric: tabular-nums`. 큰 숫자 옆 단위는 12~15px 흐린 회색으로 baseline 정렬.
- 소수점 표기: 지표는 소수 한 자리(2.4초, 0.31), 비율은 정수 %.

### Spacing & layout
- 좌우 여백 32px 고정. 컨테이너는 화면 종류별: 520(등록 1) / 560(랜딩) / 760(문서형) / 860(리포트) / 1160(홈·헤더) / 1180(검토).
- 카드 패딩 20, 큰 카드 28, 문서 36/40. 카드 그리드 gap 16, 카드 목록 gap 10~14, 섹션 padding 30 + 아래 1px 선.
- 실측값을 그대로 씁니다. 7·9·11·13·15 같은 홀수가 흔합니다(라벨 gap 7, 행 padding 13, 헤더 padding 15/18).
- 홈 카드 `minmax(340px, 1fr)` auto-fill, 최소 높이 172. 리포트 지표 3열, 종합 평가 2열, 단계 카드 4열.
- 헤더 sticky 64px. 검토 화면 하단 바 fixed. 그 외 고정 요소 없음.
- 면접 무대는 `position: fixed; inset: 0`. 아바타 340 컨테이너 / 206 슬롯 / 270·246 링 / 96 내부 원 / 44 코어. 셀프뷰 160×120, 우상단 (74, 30).

### Shape
- 라운드 **4 / 3 / 2**: 카드 4, 버튼·입력 3, 칩 2. 완전한 원(점, 아바타, 재생 버튼, 헤더 아바타, 크레딧 칩, 회차 칩)을 제외하면 이보다 둥근 것이 없습니다.
- **그림자는 둘.** 밝은 화면의 카드에 `--shadow-card`(0 1px 2px .05 + 0 6px 20px -14px .12) 하나, 무대의 구체에 `--shadow-sphere`. 그 외 없음 — 깊이는 1px 테두리(`#E3DFD7`)와 배경 대비. 카드 안 구분선은 `#F0EDE7`/`#ECE8E1`.
- 점선 테두리(`1px dashed #C9D0DB`)는 "여기에 추가"에만: 새 회사, 항목 추가, 파트 추가, 파일 드롭존.
- 왼쪽 2px 세로선은 코칭 블록에만(초록=잘한 점, 회색=더 듣고 싶었던 것, 머스터드=이렇게 바꿔보세요). 정정 표시된 문단도 머스터드 2px.
- **데이터 시각화는 셋뿐**: 3px 게이지(지표 — 권장 상한 대비 위치, 범위 안 초록·밖 머스터드), 시선 3×3 격자(칸 높이 52, `color-mix` 머스터드 농도 = 머문 비율×130%, 40% 넘으면 흰 글자, 가운데 칸만 "정면"과 `#EFE2CB` 테두리), 표정 7px 막대(강조색 하나 — 길이가 크기를 말하므로 색을 갈리지 않음) + 12px 흐름 띠(기본 상태 "집중"은 투명 트랙, 이탈 순간만 색: 자신감 머스터드 · 긴장 머스터드 55% · 당황 잉크; 이탈이 없으면 띠 대신 문장). 백분율은 소수 한 자리(`toFixed(1)`), 정면 요약만 정수.

### Interaction states
- **버튼·카드에 hover 없음.** 카드는 커서만 바뀌고 채운 버튼은 색이 변하지 않습니다. **텍스트 링크는 hover에 회색 한 단계** 진해집니다(`faint`→`muted`, `muted`→`ink`): 약관 링크, "다른 계정으로 로그인", "이름 고치기", 다이얼로그 "닫기". 인라인 편집 입력(리서치 문서, 파트명·항목명)은 hover에 `#FAFBFC`/`#FFFFFF` 배경, focus에 머스터드 밑줄(`border-b`, 점선→실선). 등록의 "?" 원형 버튼은 hover에 테두리·글자가 잉크로.
- focus: 입력 테두리가 `#C9D0DB` → `#16233A`. outline 없음, glow 없음.
- disabled: 버튼 배경 `#B7C0CD` + 흰 글자(비활성 시작 버튼). 텍스트 링크 disabled는 `#B7C0CD`.
- pressed 상태 없음. **확인은 모달이 아니라 제자리에서 펼치는 확인 박스**(머스터드 배경 `#FBF7EF` + `#EFE2CB`)로 받습니다 — 면접 시작(크레딧 차감), 회원 탈퇴. **정보 안내만 화면 위 다이얼로그**를 씁니다. 지원서 가이드 하나: 오버레이 `rgba(22,35,58,.45)`, 카드 최대 640, 헤더 `18px 26px` + 하단 1px 선, Esc와 바깥 클릭으로 닫힘. 색이 있는 오버레이는 이것과 면접 무대 위(`rgba(14,23,38,.86)`) 둘뿐.
- 아코디언은 chevron 아이콘(`Caret`, 1.5px 선). 펼치면 헤더의 요약 텍스트를 비워 중복을 막습니다.
- 게이트: 시작 전 확인은 마이크가 실제로 소리를 잡고(진폭 ≥ 0.12) 수동 항목 둘을 누를 때까지 시작 버튼이 `#B7C0CD`입니다. 카메라는 통과 조건이 아닙니다. 크레딧이 모자라면 확인을 마쳐도 열리지 않고 그 사실을 먼저 말합니다.
- 면접 무대의 버튼은 `.tap44`(index.css)로 44px 터치 영역을 확보합니다 — 보이는 크기는 그대로, 누르는 영역만 넓힙니다.

### Motion
- 화면 진입 `dm-fade` 0.3s(opacity 0→1, translateY 6→0). 자막 0.4s. 아코디언 펼침 0.25s.
- 진행 바 width `.4s ease`, 점수 바 `dm-grow .7s`.
- 아바타 `dm-breathe` 4.5s(scale 1→1.035). 분석 중 원은 3s.
- 아바타는 `Stage.tsx` 하나를 면접(206px, 오디오 구동)과 랜딩 데모 창(150px, CSS 구동)이 같이 씁니다. 오디오가 없으면 `dm-pulse`/`dm-pulse2`로 돌고, CSS 구동에서 링을 켜고 끄는 것은 링이 아니라 바깥 래퍼의 불투명도입니다(키프레임이 opacity를 쥐고 있어서).
- **진폭 값은 React state에 넣지 않습니다.** 링 스케일·불투명도·파형 높이는 rAF 루프에서 ref → style로 직접 씁니다. 말할 때 링과 들을 때 링이 둘 다 항상 마운트되어 있고 불투명도로만 건넙니다.
- 총량 모르는 작업은 `dm-slide` 1.6s 불확정 막대. 가짜 퍼센트를 만들지 않습니다. 분석 중·질문 재생성 모두 타이머가 아니라 서버 상태를 폴링하고, 끝나지 않는 경우는 그 자리에서 말합니다(답변이 녹음되지 않았습니다 / 분석 결과를 만들지 못했습니다 / 질문을 다시 뽑지 못했습니다).
- 랜딩 제목은 세 줄 "대담과 함께 미리 / [타일] 삼성전자 면접장에 / 들어가세요". 둘째 줄의 회사가 2.6초마다 바뀝니다 — `dm-fade` 리마운트, 줄 높이 1.22em 고정으로 아래 줄이 흔들리지 않게. 회사와 "면접장에"를 한 줄에 둡니다(명사구를 갈라 놓지 않기 위해). 로고 자리는 `<image-slot id="logo-{key}">`(38×38, 카드 라운드, line 테두리)이고 비어 있으면 모노그램(글자 16px/700)이 보입니다. 이름은 6자 이하.
- 로고 파일은 디자이너·개발자가 슬롯에 직접 넣는다. 이 시스템은 로고를 그리지 않는다.
- 면접의 두 배치(기본 ↔ 거울)는 마운트를 바꾸지 않고 **두 상자가 동시에 자리를 트레이드**합니다 — left/top/width/height/transform `.45s ease-in-out`, 면접관은 `scale(92/206)`로 줄어들며 우상단으로, 내 모습은 가운데로 커지며. 라벨은 도착 자리에서 `dm-fade .3s`(0.3s 지연).
- 랜딩의 타이핑 효과는 28ms/자, 커서 2px 머스터드. 회사 칩은 5.2초마다 넘어가고 손으로 고르면 그 시점부터 다시 셉니다. 단계·색 전환은 `transition-colors .3s`.
- 이징은 `ease` / `ease-in-out` / `linear`(스피너)만. bounce·spring 없음.

### Imagery
- **무대는 D 규칙을 따른다.** 바탕 `--stage-bg`, 정지한 키라이트, 무광 유리 구체(`--gradient-sphere` + `--gradient-sphere-sheen` + `--shadow-sphere`), 안의 불(`--gradient-voice-amber` / `--gradient-voice-mint`, 진폭에 따라 부풂), **링 없음**(동심원은 레이더로 읽혔다). 질문은 구체 바로 아래 44px — 가는 색선 28×1 + Pretendard 25/600/-.02em, paper 색, 두 줄 높이를 늘 확보. 크기: 면접 `clamp(150px, 24vh, 216px)`, 문턱·리서치·분석 128, 랜딩 데모 150, 홈 미리 보기 56, 리포트 머리 72. 여기서는 그림자·그라디언트 규칙을 해제합니다.
- 사진·일러스트 없음. 아바타는 위의 구체 하나(`components/stage/Avatar.jsx`) — 실제 아바타 API로 교체되는 슬롯(`data-avatar-slot="true"`)입니다. 랜딩 회사 로고 자리는 `image-slot`(사용자가 채움, 무채색).
- 웹캠은 세 크기: 시작 전 확인 미리보기 320×240(거울), 면접 셀프뷰 240×180(거울, 우상단 74/30), 거울 배치 560×420(내 모습이 가운데 위쪽, 면접관은 우상단 92px 슬롯으로 — 표정을 보며 연습하는 사람용. PiP를 키우는 대신 자리를 바꾼다: 오래 볼 화면은 카메라 축 근처에 있어야 녹화된 시선이 정면으로 남는다), 리포트 녹화본 4:3 248px 열(반전 없음). 셀프뷰를 가려도 촬영은 계속되고 그 사실을 적습니다.
- 배경 텍스처·패턴·그레인 없음. 반투명+blur는 sticky 헤더(`rgba(245,243,239,.92)` + 8px)와 검토 화면 하단 고정 바(`rgba(255,255,255,.94)` + 8px)에만.

## Iconography

**선 아이콘 8종** — `components/core/Icons.jsx`, 1.5px stroke, 24 viewBox, 글자 크기에 맞춰 13~18px: check, arrow-right, arrow-left, close, chevron-down, chevron-up, play, pause. 텍스트 글리프(→ ✓ ▲ ▶ ❚❚)는 쓰지 않습니다. 상태 점 넷(AccentDot / CheckDot(안에 체크 아이콘) / EmptyDot / Spinner)이 행 앞 표식입니다. 이모지 없음.

SVG는 로고 세트(`assets/logo/`), 아이콘 8종, 로그인 제공자 마크(구글·카카오 원본 좌표 — `ProviderMark.tsx`)입니다.

로고는 심볼 C3 — 원 하나(중심 12, r9)를 세로로 갈라 왼쪽 조각을 잉크(면접관), 오른쪽 조각을 앰버(지원자)로. 자른 선이 지름보다 왼쪽(x=9.0 / 10.6)에 있어 앰버가 반원보다 조금 넓고 틈은 1.6. `assets/logo/` — symbol.svg, symbol-on-dark.svg(종이+앰버), symbol-mono.svg(currentColor), app-icon.svg(잉크 타일, 심볼 58%), wordmark.svg. 헤더 22 · 랜딩 26, 워드마크 "대담" Pretendard 17~20/700/-.02em, 간격 10. 이전 사각 표식은 폐기.

---

## Index

```
styles.css                  @import 진입점 (tokens/* 전부)
tokens/
  fonts.css                 Pretendard Variable (jsDelivr dynamic subset)
  colors.css                --color-* 40여 개 + 그라디언트 + 시맨틱 별칭
  typography.css            크기·굵기·자간·행간
  spacing.css               컨테이너·패딩·크기·라운드
  effects.css               blur·transition·@keyframes 9종
guidelines/                 파운데이션 스펙 카드 (Colors / Type / Spacing / Brand — 심볼·아이콘·모션)
components/
  core/                     Card · PrimaryButton · OutlineButton · TextField · TextArea · Label ·
                            SectionLabel · Chip · ProgressBar · IndeterminateBar ·
                            Dots (AccentDot, CheckDot, EmptyDot, Spinner) · Caret
  navigation/               Chrome (공통 헤더)
  stage/                    Avatar(구체) · Waveform · FlatWaveform
ui_kits/web/                index.html 홈 → 준비 완료 → 면접 → 분석 → 리포트 · landing.html · onboarding.html · states.html(전환·빈 상태)
assets/logo/                symbol · symbol-on-dark · symbol-mono · app-icon · wordmark
assets/favicon.svg
SKILL.md
```

### Components (source: `web/src/components/ui.tsx` + `Chrome.tsx` + `Stage.tsx`)

| Component | 역할 |
|---|---|
| Card | 4px 카드, 1px line, `--shadow-card` |
| PrimaryButton | 잉크 채움. sm/md/lg, disabled |
| OutlineButton | 흰 배경 + field 테두리. `dark`는 무대용 |
| TextField / TextArea | 입력. focus는 테두리만 잉크로 |
| Label / SectionLabel | 13/600 라벨, 12/600 +.04em 회색 섹션 라벨 |
| Chip | 2px 칩. 단일 스타일 (변형 없음) |
| ProgressBar / IndeterminateBar | 3px 바. 퍼센트를 알 때 / 모를 때 |
| AccentDot / CheckDot / EmptyDot / Spinner | 행 앞 상태 점 |
| Caret | chevron 아이콘 |
| Icon | 선 아이콘 8종 |
| Chrome | sticky 헤더 |
| Avatar | 면접관. 무광 유리 구체, 안의 불 앰버(말할 때)/민트(들을 때), 오디오 구동 또는 정적, size |
| Waveform / FlatWaveform | 마이크 파형 16개 / 눕은 파형(무응답) |

**Intentional additions:** 없음. `ui.tsx`·`Stage.tsx`에 있는 것만 만들었고 변형도 코드에 있는 것만 둡니다 (2026-09-05 동기화 확인). `Dots.jsx`는 네 점을 한 파일에 묶은 것이고, `OutlineButton`의 `dark`와 `IndeterminateBar`의 `dark`는 각각 `Interview.tsx` 종료 버튼과 `Progress.tsx` 막대의 인라인 스타일을 옮긴 것, `FlatWaveform`은 `Progress.tsx`/`Report.tsx`의 눕은 파형입니다. `Chip`은 스타일 한 벌(이전의 accent/count 변형은 코드에 없어 제거).

**Not componentized (screen-local in the source):** Metric(`Report.tsx`가 export, 랜딩도 `compact`로 씀), Playback(오디오·영상), SessionPicker, ReportEmpty·EmptyMark, 답변 아코디언, 홈 CompanyCard·안내 배너, Preflight·StartInterview, SelfView, GazeCard·ExpressionCard, ApplicationGuide, 랜딩의 LiveDemo·StepFrame·ResearchLog·Dialogue·ScoreCard·CoachCard, 온보딩의 StepMark·StepButton·givenName. UI 킷 안에 화면 코드로 들어 있습니다. 앞서 있던 GazeBaseline(정면 기준선)은 업스트림에서 삭제됐습니다 — 판독이 지원자 기준으로 방향을 읽어 기준선이 필요 없어졌습니다.

## Caveats

- 디자인 시스템 프로젝트(`2b70d367…`)가 비어 있고 다른 프로젝트여서 이 파일들은 **현재 프로젝트 안**에 만들었습니다. 그쪽으로 옮기거나 이 프로젝트를 디자인 시스템으로 지정해야 다른 프로젝트에서 참조됩니다.
- 폰트는 npm 패키지 대신 같은 버전의 jsDelivr CDN을 씁니다. 오프라인이면 폰트가 시스템 sans로 떨어집니다.
- 컴포넌트 카드와 UI 킷은 번들 없이 `components/**/*.jsx`를 직접 읽어 `window.Daedam`에 올립니다. 컴파일러가 `_ds_bundle.js`를 만들면 그쪽을 우선하도록 바꾸는 게 좋습니다.
- UI 킷은 화면 14개 중 6개(랜딩·온보딩·홈·준비 완료·면접·리포트)와 전환·빈 상태 갤러리를 재현했습니다. 등록·리서치·검토·계정·크레딧·약관은 같은 토큰과 프리미티브만 쓰므로 소스를 읽으면 됩니다.
- 정본이 바뀌면 여기가 낡습니다. 마지막 대조는 2026-09-05이고 `github.md`에 화면 ↔ 소스 파일 표가 있습니다.
