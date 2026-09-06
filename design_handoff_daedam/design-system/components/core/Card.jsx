import React from 'react';
/** 카드. 4px 라운드, 1px #E2E6ED 테두리, 흰 배경. 그림자 없음. onClick이 있으면 커서만 바뀐다. */
export function Card({ children, onClick, padding = 20, style, className }) {
  return (
    <div
      onClick={onClick}
      className={className}
      style={{
        background: 'var(--color-surface)',
        border: '1px solid var(--color-line)',
        borderRadius: 'var(--radius-card)',
        boxShadow: 'var(--shadow-card)',
        padding,
        cursor: onClick ? 'pointer' : undefined,
        boxSizing: 'border-box',
        ...style,
      }}
    >
      {children}
    </div>
  );
}

// Runtime registration for the no-bundler fallback (harmless under a bundler).
if (typeof window !== 'undefined') { window.Daedam = window.Daedam || {}; window.Daedam.Card = Card; }
