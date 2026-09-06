import React from 'react';
/** 섹션 라벨. 12px/600 #8E98A8, 자간 +.04em. 카드 안·리포트 섹션 머리. */
export function SectionLabel({ children, style }) {
  return (
    <div style={{ fontSize: 12, fontWeight: 600, letterSpacing: '.04em', color: 'var(--color-faint)', ...style }}>
      {children}
    </div>
  );
}

// Runtime registration for the no-bundler fallback (harmless under a bundler).
if (typeof window !== 'undefined') { window.Daedam = window.Daedam || {}; window.Daedam.SectionLabel = SectionLabel; }
