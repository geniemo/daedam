/** Primary action. One per screen. 잉크 배경, 3px 라운드, 600. */
export interface PrimaryButtonProps {
  children?: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  /** sm 10/24 · md 12/26 (기본) · lg 14/34 */
  size?: 'sm' | 'md' | 'lg';
  style?: React.CSSProperties;
}
export function PrimaryButton(props: PrimaryButtonProps): JSX.Element;
