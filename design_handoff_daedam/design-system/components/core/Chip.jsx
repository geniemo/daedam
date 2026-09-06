import React from 'react';
/** 칩 · 배지 — 2px 라운드, 11.5px, line-2 테두리, surface-2 배경, muted 글자. 스타일 한 벌(ui.tsx). 강조·카운트 변형 없음. */
export function Chip({ children, className, style }) {
  return (
    <span className={className} style={{ display: 'inline-block', fontSize: 11.5, lineHeight: 1.3, color: 'var(--color-muted)', background: 'var(--color-surface-2)', border: '1px solid var(--color-line-2)', borderRadius: 'var(--radius-chip)', padding: '4px 9px', ...style }}>
      {children}
    </span>
  );
}
if (typeof window !== 'undefined') { window.Daedam = window.Daedam || {}; window.Daedam.Chip = Chip; }
