/** Sliding bar for tasks with unknown total (Deep Research, coaching generation). */
export interface IndeterminateBarProps {
  height?: number;
  /** 무대 위 — 트랙 stage-line-2 */
  dark?: boolean;
  style?: React.CSSProperties;
}
export function IndeterminateBar(props: IndeterminateBarProps): JSX.Element;
