/** 뷰포트 폭 훅. narrow = 720 미만. 화면 컴포넌트는 이 한 분기만 쓴다. */
export function useViewportWidth(): number;
export function useNarrow(bp?: number): boolean;
