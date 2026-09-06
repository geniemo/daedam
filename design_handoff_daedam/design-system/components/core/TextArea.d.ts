/** Multi-line input that grows with content. Lighter border (#D8DDE5) than TextField. */
export interface TextAreaProps {
  value?: string;
  onChange?: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  placeholder?: string;
  /** px. 기본 140 */
  minHeight?: number;
  style?: React.CSSProperties;
  [rest: string]: unknown;
}
export function TextArea(props: TextAreaProps): JSX.Element;
