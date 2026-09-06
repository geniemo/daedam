```jsx
<Waveform levels={levelsRef} />            {/* 면접 하단, 듣는 중일 때만 */}
<Waveform active height={28} />            {/* 랜딩 데모 */}
<FlatWaveform dark />                      {/* 분석 중 화면: 답변이 녹음되지 않았습니다 */}
<FlatWaveform />                           {/* 빈 리포트(silent) */}
```
The flat variant is the same 16 bars laid down to 2px — read as "nothing came in" without a caption.
