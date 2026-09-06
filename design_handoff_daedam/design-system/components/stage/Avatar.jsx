import React from 'react';
/**
 * 면접관 — 무대 D. 무광 유리 구체 + 안의 불(말할 때 앰버, 들을 때 민트). 링 없음.
 * levels(오디오 진폭 ref)가 있으면 rAF가 ref→style에 직접 쓴다. 없으면 정적(CSS breathe만).
 * data-avatar-slot="true" 컨테이너 내부만 교체하면 실제 아바타로 대체된다.
 * 크기: 면접 216(clamp 150~216, 24vh) · 문턱·리서치·분석 128 · 랜딩 데모 150 · 홈 미리 보기 56 · 리포트 머리 72.
 */
export function Avatar({ speaking, levels, size = 216 }) {
  const live = levels !== undefined;
  const voice = React.useRef(null), bloom = React.useRef(null);
  const isSpeaking = React.useRef(speaking); isSpeaking.current = speaking;
  React.useEffect(() => {
    if (!levels) return;
    let raf = 0;
    const loop = () => {
      const t = isSpeaking.current, l = t ? levels.current.output : levels.current.input * 0.35;
      if (voice.current) { voice.current.style.transform = 'scale(' + (1 + l * 0.16) + ')'; voice.current.style.opacity = String((t ? 0.6 : 0.28) + l * (t ? 0.4 : 0.22)); }
      if (bloom.current) { bloom.current.style.transform = 'scale(' + (1 + l * 0.12) + ')'; }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [levels]);
  const shadow = size >= 160 ? 'var(--shadow-sphere)' : 'inset 0 1px 0 rgba(255,255,255,.10), inset 0 -' + Math.round(size * 0.14) + 'px ' + Math.round(size * 0.25) + 'px rgba(0,0,0,.42)';
  return (
    <div data-avatar-slot="true" style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'var(--gradient-sphere)', boxShadow: shadow, animation: 'dm-breathe 6s ease-in-out infinite' }} />
      <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'var(--gradient-sphere-sheen)' }} />
      <div ref={voice} style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: speaking ? 'var(--gradient-voice-amber)' : 'var(--gradient-voice-mint)', opacity: live ? undefined : speaking ? 0.85 : 0.4, transition: 'background 1.4s ease, opacity 1s ease' }} />
      <div ref={bloom} style={{ position: 'absolute', inset: -Math.round(size * 0.5), borderRadius: '50%', pointerEvents: 'none', background: speaking ? 'radial-gradient(circle, rgba(var(--stage-keylight-rgb), .13), transparent 60%)' : 'radial-gradient(circle, rgba(var(--stage-mint-rgb), .09), transparent 60%)', transition: 'background 1.4s ease' }} />
    </div>
  );
}
if (typeof window !== 'undefined') { window.Daedam = window.Daedam || {}; window.Daedam.Avatar = Avatar; }
