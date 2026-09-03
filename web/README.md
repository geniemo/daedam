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

## 백엔드

면접 화면은 늘 실제 세션(`/ws/interview`)에 붙습니다. 앞서 있던 목업 타이밍
스위치(`VITE_VOICE_BACKEND`)는 없앴습니다 — 빌드 시점에 굳는 값이 gitignore된
`.env.local`에만 있어서, 서버에서 새로 빌드하면 가짜 면접이 나갔습니다.

1. ADK/FastAPI를 `localhost:8000`에 띄웁니다 (`vite.config.ts`의 proxy가 잡아줍니다).
2. `/ws/interview` 프로토콜은 `src/audio/voiceSession.ts` 상단 주석에 적어뒀습니다.
3. 백엔드 없이 화면만 확인하려면 `npm run smoke` — 10개 화면을 렌더만 합니다.

오디오 규격은 협상 대상이 아닙니다 — ADK는 포맷 변환을 하지 않습니다.

| | |
|---|---|
| 입력 | 16-bit PCM · 16,000Hz · mono · 1280샘플(80ms) 고정 청크 |
| 출력 | 16-bit PCM · 24,000Hz · mono |
| 전송 | 바이너리 WebSocket 프레임 (base64 아님) |

## 배포

`dist/`를 ADK의 FastAPI 앱에 `StaticFiles`로 mount하면 컨테이너 하나로 끝납니다.
Cloud Run은 **`--timeout=3600` 필수** — 기본 5분이라 면접이 중간에 끊깁니다.
