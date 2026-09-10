import { useSyncExternalStore } from 'react'

/**
 * 좁은 화면인가 — 720px 미만. 규격: design-system/components/core/useViewport.jsx
 *
 * 분기는 이 하나뿐이고 CSS에서는 `md:` 접두어가 같은 선을 가른다
 * (index.css의 --breakpoint-md). 이 훅은 **클래스로 가를 수 없는 숫자 prop**
 * (구체 지름 같은 것)에만 쓴다 — 여백·격자·글자 크기는 `md:`로 한다.
 */
const NARROW = '(max-width: 719.98px)'

const subscribe = (onChange: () => void) => {
  const query = window.matchMedia(NARROW)
  query.addEventListener('change', onChange)
  return () => query.removeEventListener('change', onChange)
}

export const useNarrow = () =>
  useSyncExternalStore(
    subscribe,
    () => window.matchMedia(NARROW).matches,
    // 서버 렌더(smoke)에는 창이 없다 — 넓은 화면으로 친다.
    () => false,
  )
