import React from 'react';
/**
 * 마이크 입력 파형 — 3px 폭 막대 16개, 간격 3. components/Stage.tsx 그대로.
 * levels(진폭 ref)가 있으면 실제 입력, 없으면 사인파 둘을 겹친 합성 진폭(랜딩). active=false면 막대가 눕는다.
 */
const BAR_COUNT = 16;
export function Waveform({ levels, active = true, height = 38 }) {
  const bars = React.useRef([]);
  React.useEffect(() => {
    let raf = 0;
    const loop = () => {
      const t = performance.now() / 1000;
      const level = levels ? levels.current.input : active ? Math.max(0, Math.sin(t * 5.3) * 0.5 + Math.sin(t * 9.1) * 0.3 + 0.3) : 0;
      for (let i = 0; i < BAR_COUNT; i++) {
        const el = bars.current[i]; if (!el) continue;
        const phase = Math.sin(t * 6 + i * 0.7) * 0.5 + 0.5;
        el.style.transform = 'scaleY(' + Math.min(1, 0.22 + level * (0.35 + 0.65 * phase) * 0.78) + ')';
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [levels, active]);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 3, height }}>
      {Array.from({ length: BAR_COUNT }, (_, i) => <div key={i} ref={el => { bars.current[i] = el; }} style={{ width: 3, height, background: 'var(--stage-sand)', transformOrigin: 'center', transform: 'scaleY(0.22)' }} />)}
    </div>
  );
}
/** 눕은 파형 — 답변이 녹음되지 않았을 때. 조금 전까지 움직이던 막대가 전부 누웠다. */
export function FlatWaveform({ dark = false, height = 38 }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 3, height }}>
      {Array.from({ length: BAR_COUNT }, (_, i) => <div key={i} style={{ width: 3, height: 2, background: dark ? 'rgba(255,255,255,.18)' : 'var(--color-line)' }} />)}
    </div>
  );
}
if (typeof window !== 'undefined') { window.Daedam = window.Daedam || {}; window.Daedam.Waveform = Waveform; window.Daedam.FlatWaveform = FlatWaveform; }
