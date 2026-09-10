import React from 'react';
/**
 * 뷰포트 폭 분기 하나 — 720 미만이 "좁은 화면"(휴대폰·세로 태블릿). 화면마다 이 하나만 쓰고 중간 단계는 만들지 않는다.
 * 코드(Tailwind)에서는 md: 접두어 하나에 대응한다. window.__DAEDAM_W 가 있으면 그 폭으로 친다(킷 미리 보기용).
 */
const readW = () => (typeof window === 'undefined' ? 1280 : window.__DAEDAM_W || window.innerWidth);
export function useViewportWidth() {
  const [w, setW] = React.useState(readW);
  React.useEffect(() => { const on = () => setW(readW()); window.addEventListener('resize', on); return () => window.removeEventListener('resize', on); }, []);
  return w;
}
export function useNarrow(bp = 720) { return useViewportWidth() < bp; }
if (typeof window !== 'undefined') { window.Daedam = window.Daedam || {}; window.Daedam.useViewportWidth = useViewportWidth; window.Daedam.useNarrow = useNarrow; }
