/** @startingPoint section="Components" subtitle="공통 헤더 — 로고, 내 면접, 크레딧, 계정" viewport="1160x64" */
export interface ChromeProps {
  name?: string;
  /** 잔액. undefined면 크레딧 칩을 그리지 않는다 */
  credits?: number;
  avatarUrl?: string;
  onHome?: () => void;
  onAccount?: () => void;
  onCredits?: () => void;
}
export function Chrome(props: ChromeProps): JSX.Element;
