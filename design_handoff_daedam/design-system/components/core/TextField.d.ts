/** Single-line input. Focus ring is the border turning ink — no outline, no glow. */
export interface TextFieldProps {
  value?: string;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string;
  type?: string;
  style?: React.CSSProperties;
  [rest: string]: unknown;
}
export function TextField(props: TextFieldProps): JSX.Element;
