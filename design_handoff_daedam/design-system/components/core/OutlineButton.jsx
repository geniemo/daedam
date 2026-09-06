import React from 'react';
/** 흰 배경, 1px #C9D0DB 테두리, 잉크 글자. 보조 행동. dark면 무대용(투명 배경, stage-line). */
export function OutlineButton({ children, onClick, size = 'md', dark, style }) {
  const pad = { sm: '9px 14px', md: '10px 16px', lg: '11px 18px' }[size];
  const fs = { sm: 12.5, md: 13.5, lg: 13.5 }[size];
  return (
    <button
      onClick={onClick}
      style={{
        font: 'inherit',
        fontSize: dark ? 13 : fs,
        fontWeight: dark ? 400 : 600,
        color: dark ? 'var(--color-stage-muted-2)' : 'var(--color-ink)',
        background: dark ? 'transparent' : 'var(--color-surface)',
        border: '1px solid ' + (dark ? 'var(--color-stage-line)' : 'var(--color-field)'),
        borderRadius: 'var(--radius-control)',
        padding: dark ? '9px 18px' : pad,
        cursor: 'pointer',
        ...style,
      }}
    >
      {children}
    </button>
  );
}

// Runtime registration for the no-bundler fallback (harmless under a bundler).
if (typeof window !== 'undefined') { window.Daedam = window.Daedam || {}; window.Daedam.OutlineButton = OutlineButton; }
