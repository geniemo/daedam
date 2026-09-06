The interviewer. A matte glass sphere lit from above; the light inside is amber while the interviewer speaks and mint while listening. No rings — earlier concentric rings read as a radar.

```jsx
<Avatar speaking={phase === 'speaking'} levels={levelsRef} />   {/* 면접 — 오디오 구동, 216 */}
<Avatar speaking={!done} size={150} />                           {/* 랜딩 데모 — 정적 */}
<Avatar speaking={false} size={128} />                           {/* 문턱 띠 · 리서치 · 분석 중 */}
```

Audio-rate values go ref → style, never React state. Replace only the inside of `[data-avatar-slot]` when a real avatar API arrives. Needs `--gradient-sphere`, `--gradient-voice-*`, `--shadow-sphere`, `--stage-keylight-rgb` from tokens/colors.css.
