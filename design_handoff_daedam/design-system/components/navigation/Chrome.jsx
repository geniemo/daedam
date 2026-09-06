import React from 'react';
/** 공통 헤더. sticky 64px, 반투명 바탕 + blur 8, 아래 1px line. 로고 + "내 면접" + 크레딧 + 이름 + 아바타. */
export function Chrome({ name = '지원자', credits, onHome, onAccount, onCredits, avatarUrl }) {
  // Chrome.tsx: name.slice(-2, -1) — 성 아닌 이름의 첫 글자 ("김서연" → "서")
    const initial = name.slice(-2, -1); // Chrome.tsx: 3자 이름의 가운데 글자 (김서연 → 서)
  return (
    <header style={{ position: 'sticky', top: 0, zIndex: 40, height: 64, background: 'var(--header-bg)', backdropFilter: 'blur(8px)', borderBottom: '1px solid var(--color-line)' }}>
      <div style={{ maxWidth: 'var(--container-home)', margin: '0 auto', height: '100%', padding: '0 32px', display: 'flex', alignItems: 'center', gap: 32, boxSizing: 'border-box' }}>
        <a onClick={onHome} style={{ display: 'flex', alignItems: 'center', gap: 9, cursor: 'pointer', textDecoration: 'none' }}>
          <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true" style={{ flexShrink: 0 }}><path d="M9 3.51A9 9 0 0 0 9 20.49Z" fill="var(--color-ink)" /><path d="M10.6 3.11A9 9 0 1 1 10.6 20.89Z" fill="var(--color-accent)" /></svg>
          <span style={{ fontSize: 17, fontWeight: 700, letterSpacing: '-.02em', color: 'var(--color-ink)' }}>대담</span>
        </a>
        <nav><a onClick={onHome} style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-ink)', cursor: 'pointer' }}>내 면접</a></nav>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {credits !== undefined && (
            <a onClick={onCredits} style={{ marginRight: 4, borderRadius: 9999, border: '1px solid var(--color-accent-line)', background: 'var(--color-accent-bg)', padding: '4px 10px', fontSize: 12, color: 'var(--color-accent)', cursor: 'pointer' }}>
              크레딧 <span style={{ fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{credits}</span>
            </a>
          )}
          <a onClick={onAccount} style={{ fontSize: 13, color: 'var(--color-muted)', cursor: 'pointer' }}>{name}</a>
          <a onClick={onAccount} style={{ cursor: 'pointer' }}>
            {avatarUrl ? (
              <img src={avatarUrl} alt="" style={{ width: 30, height: 30, borderRadius: '50%', border: '1px solid var(--color-field)', objectFit: 'cover' }} />
            ) : (
              <span style={{ display: 'flex', width: 30, height: 30, alignItems: 'center', justifyContent: 'center', borderRadius: '50%', border: '1px solid var(--color-field)', background: 'var(--color-surface)', fontSize: 12, fontWeight: 600, color: 'var(--color-muted)', boxSizing: 'border-box' }}>{initial}</span>
            )}
          </a>
        </div>
      </div>
    </header>
  );
}

// Runtime registration for the no-bundler fallback (harmless under a bundler).
if (typeof window !== 'undefined') { window.Daedam = window.Daedam || {}; window.Daedam.Chrome = Chrome; }
