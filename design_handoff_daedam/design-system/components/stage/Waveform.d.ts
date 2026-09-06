/** 마이크 입력 파형 16개 막대. levels가 없으면 합성 진폭(랜딩). FlatWaveform은 무응답 표식. */
export interface WaveformProps {
  levels?: { current: { input: number; output: number } };
  /** 합성 진폭일 때만 — false면 막대가 눕는다 */
  active?: boolean;
  /** 기본 38. 데모 창 28 */
  height?: number;
}
export function Waveform(props: WaveformProps): JSX.Element;
export interface FlatWaveformProps { dark?: boolean; height?: number; }
export function FlatWaveform(props: FlatWaveformProps): JSX.Element;
