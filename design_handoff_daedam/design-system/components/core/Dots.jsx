import React from 'react';
/** 강조 점 — "면접 준비 완료" 앞. 5px 머스터드 원. */
export function AccentDot({ size = 5, color = 'var(--color-accent)' }) {
  return <span style={{ display: 'inline-block', flexShrink: 0, width: size, height: size, borderRadius: '50%', background: color }} />;
}
/** 완료 표시 — 잉크 원 위 9px 흰 체크. */
export function CheckDot({ size = 14 }) {
  return (
    <span style={{ display: 'inline-flex', flexShrink: 0, width: size, height: size, alignItems: 'center', justifyContent: 'center', borderRadius: '50%', background: 'var(--color-ink)', color: '#fff', lineHeight: 1 }}><svg width={Math.round(size * .62)} height={Math.round(size * .62)} viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.2 4.2L19 7.5" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" /></svg></span>
  );
}
/** 미완료 표시 — 1.5px line 테두리 원. */
export function EmptyDot({ size = 13 }) {
  return <span style={{ display: 'inline-block', flexShrink: 0, width: size, height: size, borderRadius: '50%', border: '1.5px solid var(--color-line)', boxSizing: 'border-box' }} />;
}
/** 진행 중 — 머스터드 1.5px 링, 위쪽 투명, 1s 회전. */
export function Spinner({ size = 13, borderWidth = 1.5 }) {
  return <span style={{ display: 'inline-block', flexShrink: 0, width: size, height: size, borderRadius: '50%', border: borderWidth + 'px solid var(--color-accent)', borderTopColor: 'transparent', boxSizing: 'border-box', animation: 'dm-spin 1s linear infinite' }} />;
}

// Runtime registration for the no-bundler fallback (harmless under a bundler).
if (typeof window !== 'undefined') { window.Daedam = window.Daedam || {}; window.Daedam.AccentDot = AccentDot; window.Daedam.CheckDot = CheckDot; window.Daedam.EmptyDot = EmptyDot; window.Daedam.Spinner = Spinner; }
