import React from 'react';
/** 선 아이콘 8종 — 1.5px stroke, 24 viewBox. 텍스트 글리프(→ ✓ ▲ ▶)를 대신한다. 크기는 글자와 맞춰 14~18. */
const PATHS = {
  check: 'M5 12.5l4.2 4.2L19 7.5',
  'chevron-down': 'M6 9l6 6 6-6',
  'chevron-up': 'M6 15l6-6 6 6',
  'arrow-right': 'M5 12h14M13 6l6 6-6 6',
  'arrow-left': 'M19 12H5M11 6l-6 6 6 6',
  close: 'M6 6l12 12M18 6L6 18',
  mic: 'M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3zM5 11a7 7 0 0 0 14 0M12 18v3',
  camera: 'M4 8h3l2-3h6l2 3h3v11H4zM12 17a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z',
};
export function Icon({ name, size = 16, stroke = 1.5, color = 'currentColor', style }) {
  if (name === 'play') return <svg width={size} height={size} viewBox="0 0 24 24" style={style} aria-hidden="true"><path d="M8 5.5v13l10-6.5z" fill={color} /></svg>;
  if (name === 'pause') return <svg width={size} height={size} viewBox="0 0 24 24" style={style} aria-hidden="true"><path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" fill={color} /></svg>;
  return <svg width={size} height={size} viewBox="0 0 24 24" style={style} aria-hidden="true"><path d={PATHS[name] || ''} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" /></svg>;
}
if (typeof window !== 'undefined') { window.Daedam = window.Daedam || {}; window.Daedam.Icon = Icon; }
