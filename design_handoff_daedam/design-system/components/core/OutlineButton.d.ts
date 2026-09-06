/** Secondary action. 흰 배경 + field 테두리. dark 변형은 면접 무대용. */
export interface OutlineButtonProps {
  children?: React.ReactNode;
  onClick?: () => void;
  size?: 'sm' | 'md' | 'lg';
  /** 면접 무대(#0E1726) 위 — 투명 배경, stage-line 테두리, 400 */
  dark?: boolean;
  style?: React.CSSProperties;
}
export function OutlineButton(props: OutlineButtonProps): JSX.Element;
