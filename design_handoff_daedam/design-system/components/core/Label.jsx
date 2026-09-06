import React from 'react';
/** 입력 라벨. 13px/600 잉크. optional을 주면 옆에 12px 회색 부가 설명. */
export function Label({ children, optional, htmlFor }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
      <label htmlFor={htmlFor} style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)' }}>{children}</label>
      {optional && <span style={{ fontSize: 12, color: 'var(--color-faint)' }}>{optional}</span>}
    </div>
  );
}

// Runtime registration for the no-bundler fallback (harmless under a bundler).
if (typeof window !== 'undefined') { window.Daedam = window.Daedam || {}; window.Daedam.Label = Label; }
