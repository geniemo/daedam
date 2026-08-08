# 대담 — web

`design_handoff_daedam/README.md`의 화면 10개를 Vite + React로 옮긴 것입니다.
디자인 값(색·px·자간)은 핸드오프 문서에서 그대로 가져왔습니다.

```bash
npm run dev      # http://localhost:5173
npm run build    # tsc -b && vite build → dist/
npm run smoke    # 브라우저 없이 10개 화면을 실제로 렌더해 런타임 에러를 잡습니다
```

## 구조

```
src/
├─ data/          목업 + 타입. 서버가 붙으면 여기만 교체하면 됩니다.
├─ store/         app.ts (카드·지원서·정정사항)  interview.ts (세션 상태)
├─ audio/         ★ voice agent가 붙는 자리
│  ├─ voiceSession.ts     WebSocket + AudioWorklet + 재연결
│  └─ useVoiceSession.ts  화면과 세션을 잇는 훅
├─ components/    Chrome(공통 헤더), ui(프리미티브)
└─ screens/       10개 화면
public/worklets/  pcm-recorder.js (16kHz 캡처) · pcm-player.js (24kHz 재생)
```

## 지금 상태

`VITE_VOICE_BACKEND`가 꺼져 있어 면접 화면은 프로토타입 타이밍(질문당 14초)으로
돕니다. 파형과 아바타 링은 이미 진폭 구동이라, 백엔드를 켜면 그대로 실제 오디오에
반응합니다.

## 백엔드를 붙일 때

1. ADK/FastAPI를 `localhost:8000`에 띄웁니다 (`vite.config.ts`의 proxy가 잡아줍니다).
2. `.env.local`에 `VITE_VOICE_BACKEND=1`.
3. `/ws/interview` 프로토콜은 `src/audio/voiceSession.ts` 상단 주석에 적어뒀습니다.

오디오 규격은 협상 대상이 아닙니다 — ADK는 포맷 변환을 하지 않습니다.

| | |
|---|---|
| 입력 | 16-bit PCM · 16,000Hz · mono · 1280샘플(80ms) 고정 청크 |
| 출력 | 16-bit PCM · 24,000Hz · mono |
| 전송 | 바이너리 WebSocket 프레임 (base64 아님) |

## 배포

`dist/`를 ADK의 FastAPI 앱에 `StaticFiles`로 mount하면 컨테이너 하나로 끝납니다.
Cloud Run은 **`--timeout=3600` 필수** — 기본 5분이라 면접이 중간에 끊깁니다.
