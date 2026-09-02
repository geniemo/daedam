/**
 * 표정 쪽 어휘와 원재료.
 *
 * **분류는 여기 없습니다.** 앞서는 프레임마다 블렌드셰이프 문턱으로 인상을
 * 매겼는데, 차분한 얼굴에서 근육 신호가 0.00~0.09에 깔려 어떤 문턱으로도 한
 * 칸으로 몰렸습니다(실측: 132초 내내 미소 0.000 → 집중 100%). 인상은 이제
 * 3초 스냅샷을 서버가 VLM으로 읽습니다 — server/daedam/eval/expression.py의
 * 머리 주석에 왜와 실측 근거가 있습니다.
 *
 * 이 파일에 남는 것은 둘입니다:
 * - 리포트가 쓰는 인상 어휘(`IMPRESSIONS`) — 서버 판독의 키와 같아야 합니다.
 * - 근육 세기 추출(`strengths`) — 타임라인에 원값으로 남겨, 미소처럼 확인
 *   가능한 사실("입꼬리 0.32는 진짜 미소다")의 재료가 됩니다.
 */

/** MediaPipe 블렌드셰이프 이름 → 세기(0~1). */
export type Shapes = Record<string, number>

export interface Impression {
  key: string
  label: string
}

/**
 * 인상 어휘. 서버 판독(eval/expression.py의 IMPRESSIONS)과 키가 같아야 하고,
 * 화면에 쓸 한국어 라벨은 여기가 소유합니다.
 */
export const IMPRESSIONS: Impression[] = [
  { key: 'confident', label: '자신감' },
  { key: 'focused', label: '집중' },
  { key: 'tense', label: '긴장' },
  { key: 'flustered', label: '당황' },
]

function strength(shapes: Shapes, names: string[]): number {
  if (names.length === 0) return 0
  let sum = 0
  for (const name of names) sum += shapes[name] ?? 0
  return sum / names.length
}

/**
 * 이 프레임의 근육 세기 셋 — 미소·긴장·눈 크게.
 *
 * 타임라인에 원값으로 남기는 이유: 판독과 별개로 "실제로 웃었는가" 같은
 * 확인 가능한 사실을 나중에 셀 수 있고(또렷한 미소가 0.3대에 잡히는 것은
 * 실측으로 확인), 기준을 다시 잡을 때 재녹화가 필요 없어집니다.
 */
export function strengths(shapes: Shapes) {
  return {
    smile: strength(shapes, ['mouthSmileLeft', 'mouthSmileRight']),
    worry: Math.max(
      strength(shapes, ['browInnerUp']),
      strength(shapes, ['mouthPressLeft', 'mouthPressRight']),
    ),
    wide: strength(shapes, ['eyeWideLeft', 'eyeWideRight']),
  }
}
