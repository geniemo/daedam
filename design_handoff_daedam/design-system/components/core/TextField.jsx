import React from 'react';
/** 한 줄 입력. 1px #C9D0DB, 3px, 12/13 패딩, 14.5px. focus 시 잉크 테두리. */
export function TextField({ value, onChange, placeholder, type = 'text', style, ...rest }) {
  const [focus, setFocus] = React.useState(false);
  return (
    <input
      {...rest}
      type={type}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      onFocus={() => setFocus(true)}
      onBlur={() => setFocus(false)}
      style={{
        font: 'inherit',
        fontSize: 14.5,
        color: 'var(--color-ink)',
        background: 'var(--color-surface)',
        border: '1px solid ' + (focus ? 'var(--color-ink)' : 'var(--color-field)'),
        borderRadius: 'var(--radius-control)',
        padding: '12px 13px',
        outline: 'none',
        width: '100%',
        boxSizing: 'border-box',
        ...style,
      }}
    />
  );
}

// Runtime registration for the no-bundler fallback (harmless under a bundler).
if (typeof window !== 'undefined') { window.Daedam = window.Daedam || {}; window.Daedam.TextField = TextField; }
