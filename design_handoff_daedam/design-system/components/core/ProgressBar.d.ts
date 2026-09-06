/** Determinate bar. Only when a real percentage exists — otherwise use IndeterminateBar. */
export interface ProgressBarProps {
  /** 0–100 */
  pct?: number;
  /** 기본 3. 리포트 점수 바 6 */
  height?: number;
  fill?: string;
  track?: string;
  style?: React.CSSProperties;
}
export function ProgressBar(props: ProgressBarProps): JSX.Element;
