import React from 'react';
/** 아코디언 캐럿. ▲/▼ 텍스트 글리프, 11~12px, --color-faintest. */
export function Caret({ open, size = 11, style }) {
  return <svg width={size + 4} height={size + 4} viewBox="0 0 24 24" style={{ color: 'var(--color-faintest)', display: 'block', ...style }} aria-hidden="true"><path d={open ? 'M6 15l6-6 6 6' : 'M6 9l6 6 6-6'} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

// Runtime registration for the no-bundler fallback (harmless under a bundler).
if (typeof window !== 'undefined') { window.Daedam = window.Daedam || {}; window.Daedam.Caret = Caret; }
