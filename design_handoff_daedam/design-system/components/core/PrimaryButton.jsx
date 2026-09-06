import React from 'react';
/** 잉크 배경 흰 글자. 화면당 하나. disabled면 --color-faintest 배경. */
export function PrimaryButton({ children, onClick, disabled, size = 'md', style }) {
  const pad = { sm: '10px 24px', md: '12px 26px', lg: '14px 34px' }[size];
  const fs = { sm: 13.5, md: 14, lg: 15 }[size];
  return (
    <button
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      style={{
        font: 'inherit',
        fontSize: fs,
        fontWeight: 600,
        color: '#fff',
        background: disabled ? 'var(--color-faintest)' : 'var(--color-ink)',
        border: '1px solid ' + (disabled ? 'var(--color-faintest)' : 'var(--color-ink)'),
        borderRadius: 'var(--radius-control)',
        padding: pad,
        cursor: disabled ? 'default' : 'pointer',
        ...style,
      }}
    >
      {children}
    </button>
  );
}

// Runtime registration for the no-bundler fallback (harmless under a bundler).
if (typeof window !== 'undefined') { window.Daedam = window.Daedam || {}; window.Daedam.PrimaryButton = PrimaryButton; }
