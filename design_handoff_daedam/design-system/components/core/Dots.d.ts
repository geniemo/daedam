/** 상태 점 넷. 리스트·체크리스트·진행 로그에서 행 앞에 붙는다. */
export interface AccentDotProps { size?: number; color?: string; }
export interface CheckDotProps { size?: number; }
export interface EmptyDotProps { size?: number; }
export interface SpinnerProps { size?: number; borderWidth?: number; }
export function AccentDot(props: AccentDotProps): JSX.Element;
export function CheckDot(props: CheckDotProps): JSX.Element;
export function EmptyDot(props: EmptyDotProps): JSX.Element;
export function Spinner(props: SpinnerProps): JSX.Element;
