import React from 'react';
/** 총량 모르는 작업용. 25% 조각이 1.6s 주기로 지나간다. "얼마나 남았다"가 아니라 "돌고 있다"만 말한다. */
export function IndeterminateBar({ height = 3, dark, style }) {
  return (
    <div style={{ width: '100%', height, overflow: 'hidden', background: dark ? 'var(--color-stage-line-2)' : 'var(--color-hair-2)', ...style }}>
      <div style={{ width: '25%', height: '100%', background: 'var(--color-accent)', animation: 'dm-slide 1.6s ease-in-out infinite' }} />
    </div>
  );
}

// Runtime registration for the no-bundler fallback (harmless under a bundler).
if (typeof window !== 'undefined') { window.Daedam = window.Daedam || {}; window.Daedam.IndeterminateBar = IndeterminateBar; }
