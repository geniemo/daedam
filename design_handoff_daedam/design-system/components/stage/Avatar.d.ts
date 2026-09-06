/** @startingPoint section="Components" subtitle="면접관 — 무광 유리 구체, 말할 때 앰버 · 들을 때 민트" viewport="400x400"
 *  무대 D의 구체. 면접(216)·문턱(128)·랜딩 데모(150)·홈 미리 보기(56)가 같은 것을 그린다. */
export interface AvatarProps {
  /** 면접관이 말하는 중인가. 앰버 ↔ 민트 */
  speaking: boolean;
  /** 실제 오디오 진폭 ref { current: { input, output } }. 없으면 정적 */
  levels?: { current: { input: number; output: number } };
  /** 지름 px. 기본 216 */
  size?: number;
}
export function Avatar(props: AvatarProps): JSX.Element;
