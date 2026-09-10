/** @startingPoint section="Components" subtitle="4px 카드 — 1px 테두리 + 옅은 잉크 그림자(--shadow-card)" viewport="700x200" */
export interface CardProps {
  children?: React.ReactNode;
  onClick?: () => void;
  /** px. 기본 20. 큰 카드 28, 문서 카드 '36px 40px' */
  padding?: number | string;
  style?: React.CSSProperties;
  /** 바깥 div에 붙는 ref (크기 측정용) */
  rootRef?: React.Ref<HTMLDivElement>;
  className?: string;
}
export function Card(props: CardProps): JSX.Element;
