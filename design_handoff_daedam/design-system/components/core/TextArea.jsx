import React from 'react';
/** 여러 줄 입력. 내용만큼 자란다(field-sizing:content). 1px #D8DDE5, 13.5px, lh 1.65. */
export function TextArea({ value, onChange, placeholder, minHeight = 140, style, ...rest }) {
  const [focus, setFocus] = React.useState(false);
  return (
    <textarea
      {...rest}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      onFocus={() => setFocus(true)}
      onBlur={() => setFocus(false)}
      style={{
        font: 'inherit',
        fontSize: 13.5,
        lineHeight: 1.65,
        color: 'var(--color-ink)',
        background: 'var(--color-surface)',
        border: '1px solid ' + (focus ? 'var(--color-ink)' : 'var(--color-field-2)'),
        borderRadius: 'var(--radius-control)',
        padding: '10px 11px',
        minHeight,
        resize: 'vertical',
        fieldSizing: 'content',
        outline: 'none',
        width: '100%',
        boxSizing: 'border-box',
        ...style,
      }}
    />
  );
}

// Runtime registration for the no-bundler fallback (harmless under a bundler).
if (typeof window !== 'undefined') { window.Daedam = window.Daedam || {}; window.Daedam.TextArea = TextArea; }
