import React from 'react';
/** 진행 바. 트랙 --color-hair-2 / 채움 --color-accent, 높이 3. transition width .4s. */
export function ProgressBar({ pct = 0, height = 3, fill = 'var(--color-accent)', track = 'var(--color-hair-2)', style }) {
  return (
    <div style={{ width: '100%', height, background: track, ...style }}>
      <div style={{ height: '100%', width: Math.max(0, Math.min(100, pct)) + '%', background: fill, transition: 'width .4s ease' }} />
    </div>
  );
}

// Runtime registration for the no-bundler fallback (harmless under a bundler).
if (typeof window !== 'undefined') { window.Daedam = window.Daedam || {}; window.Daedam.ProgressBar = ProgressBar; }
