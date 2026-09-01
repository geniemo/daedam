/**
 * 표정과 시선을 "면접관에게 어떻게 보였는가"로 옮깁니다.
 *
 * **재는 것은 인상이지 속마음이 아닙니다.** 면접 비언어 연구가 다루는 것도
 * 지원자의 내면이 아니라 평가자에게 **어떻게 읽히는가**입니다(Cannata 외 2024,
 * 면접에서 미소(AU6+AU12)가 자신감·친근함으로 읽힘).
 *
 * 라벨은 "자신감"처럼 짧게 씁니다. 넷 다 "…있어 보임"으로 끝내면 화면만
 * 지저분해지고, 표정 항목에 적힌 "자신감"은 어차피 그렇게 읽힙니다. 대신 그
 * 단서를 섹션에 **한 번** 답니다(`IMPRESSION_CAPTION`) — 없으면 속마음을 쟀다는
 * 뜻이 되고, 그건 근거가 없습니다.
 *
 * 그 아래에 **실제로 잰 근육 값**을 그대로 남겨 둡니다(`MUSCLES`). 위층은 읽기
 * 쉬우라고 있는 것이고, 근거를 물으면 아래층을 보여줄 수 있어야 합니다.
 *
 * 문턱값과 조합은 **잠정입니다.** 문헌에 "자신감 = 기쁨 N% + 놀람 M%" 같은
 * 매핑은 없습니다(찾아봤고 없습니다). 미소가 자신감으로 읽힌다는 방향만 있고
 * 경계는 우리가 정한 것이라, 면접이 쌓이면 다시 잡아야 합니다.
 */

/** MediaPipe 블렌드셰이프 이름 → 우리 분류. 값은 0~1입니다. */
export type Shapes = Record<string, number>

export interface Category {
  key: string
  label: string
  /** 이 분류로 볼 근육 조합. 여러 개면 평균입니다. */
  shapes: string[]
  /** 이 값을 넘으면 그 표정으로 셉니다. */
  threshold: number
  /** 화면에 붙일 한 줄 설명 — 무엇을 보고 센 것인지. */
  note: string
}

/**
 * 문턱값은 실측이 아니라 잠정입니다.
 *
 * 블렌드셰이프는 0~1인데 "이 정도면 웃는 것"의 경계가 사람마다 다릅니다.
 * 면접이 쌓이면 분포를 보고 다시 정해야 합니다 — 목소리 흔들림 지표와 같은
 * 처지라 화면에도 그렇게 적습니다.
 */
export const MUSCLES: Category[] = [
  {
    key: 'smile',
    label: '미소',
    shapes: ['mouthSmileLeft', 'mouthSmileRight'],
    threshold: 0.25,
    note: '입꼬리가 올라간 시간',
  },
  {
    key: 'brow',
    label: '찡그림',
    shapes: ['browDownLeft', 'browDownRight'],
    threshold: 0.3,
    note: '눈썹이 내려간 시간',
  },
  {
    key: 'wide',
    label: '눈 크게',
    shapes: ['eyeWideLeft', 'eyeWideRight'],
    threshold: 0.3,
    note: '눈이 크게 떠진 시간',
  },
  {
    key: 'neutral',
    label: '무표정',
    shapes: [],
    threshold: 0,
    note: '위 어느 것도 두드러지지 않은 시간',
  },
]

function strength(shapes: Shapes, names: string[]): number {
  if (names.length === 0) return 0
  let sum = 0
  for (const name of names) sum += shapes[name] ?? 0
  return sum / names.length
}

/**
 * 이 프레임의 표정 하나. 여럿이 동시에 넘으면 가장 센 것을 고릅니다 —
 * 한 프레임이 두 칸에 들어가면 합이 100%를 넘습니다.
 */
export function classify(shapes: Shapes): string {
  let best = 'neutral'
  let bestScore = 0
  for (const category of MUSCLES) {
    if (category.key === 'neutral') continue
    const score = strength(shapes, category.shapes)
    if (score >= category.threshold && score > bestScore) {
      best = category.key
      bestScore = score
    }
  }
  return best
}

export interface ExpressionSummary {
  frames: number
  /** 분류 키 → 시간 비율(0~1). 합이 1입니다. */
  shares: Record<string, number>
}

export function summarizeMuscles(frames: Shapes[]): ExpressionSummary {
  const counts: Record<string, number> = {}
  for (const category of MUSCLES) counts[category.key] = 0
  for (const shapes of frames) counts[classify(shapes)] += 1
  const n = frames.length || 1
  const shares: Record<string, number> = {}
  for (const key of Object.keys(counts)) shares[key] = counts[key] / n
  return { frames: frames.length, shares }
}


// ── 어떻게 보였는가 ────────────────────────────────────────────────────

export interface Impression {
  key: string
  label: string
  note: string
}

/**
 * 시선이 같이 들어가는 이유: 표정만으로는 자신감과 집중이 갈리지 않습니다.
 * 둘 다 정면을 지키는데, 미소가 있으면 자신감으로, 없으면 집중으로 읽힙니다.
 * 반대로 시선이 흔들리면 같은 표정도 긴장·당황으로 읽힙니다.
 */
export const IMPRESSIONS: Impression[] = [
  { key: 'confident', label: '자신감', note: '미소가 있고 시선이 정면에 머문 시간' },
  { key: 'focused', label: '집중', note: '표정 변화가 적고 시선이 정면에 머문 시간' },
  { key: 'tense', label: '긴장', note: '눈썹 안쪽이 올라가거나 입을 다문 시간' },
  { key: 'flustered', label: '당황', note: '눈이 커지거나 시선이 크게 흔들린 시간' },
]

/**
 * 표정 섹션에 한 줄로 답니다. 라벨마다 붙이지 않고 여기 모아 둔 것은 화면을
 * 깔끔하게 두면서도 "무엇을 잰 값인가"를 흘리지 않기 위해서입니다.
 */
export const IMPRESSION_CAPTION = '얼굴 움직임과 시선에서 읽은 인상입니다'

/**
 * 이 프레임의 근육 세기 셋. 분류의 원료이자 **나중에 문턱을 다시 잡을 재료**입니다.
 *
 * 타임라인에 이 값을 같이 남기는 이유: 분류 결과만 저장하면 문턱을 조정할 때마다
 * 새로 녹화해야 합니다. 세기를 남겨 두면 지난 면접 기록으로 다시 계산할 수 있습니다.
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

/**
 * 분류 문턱. **잠정입니다.**
 *
 * 처음에 0.25~0.4로 뒀더니 실측에서 아무것도 안 걸려 집중 100%가 나왔습니다.
 * 면접에서 나오는 표정은 크게 웃거나 찌푸리는 것이 아니라 미묘한 쪽이라, 아바타를
 * 움직이려고 만든 블렌드셰이프의 눈금으로는 낮은 자리에 놓입니다. 기록에 세기를
 * 같이 남기므로(`strengths`) 면접이 쌓이면 그 분포로 다시 잡을 수 있습니다.
 */
export const THRESHOLDS = { smile: 0.14, worry: 0.18, wide: 0.22 }

/** 이 프레임이 어떻게 보였는가. 시선을 모르면(보정 안 함) 표정만으로 봅니다. */
export function impressionOf(shapes: Shapes, steady: boolean | null): string {
  const { smile, worry, wide } = strengths(shapes)

  // 표정이 먼저다. 시선은 자신감(미소+정면)을 가르는 데만 거든다.
  //
  // 앞서는 "정면이 아니면 긴장"으로 뒀는데, 그러면 시선 판정이 조금만 빡빡해도
  // 표정이 통째로 한 칸에 몰린다 — 실측에서 98%가 긴장으로 나왔다. 시선이
  // 흔들린다는 것만으로 긴장했다고 말할 근거도 없다.
  if (wide >= THRESHOLDS.wide) return 'flustered'
  if (worry >= THRESHOLDS.worry) return 'tense'
  if (smile >= THRESHOLDS.smile) return steady === false ? 'focused' : 'confident'
  return 'focused'
}

export interface ImpressionSummary {
  frames: number
  /** 인상 키 → 시간 비율(0~1). 합이 1입니다. */
  shares: Record<string, number>
}

export function summarizeImpressions(
  frames: { shapes: Shapes; steady: boolean | null }[],
): ImpressionSummary {
  const counts: Record<string, number> = {}
  for (const impression of IMPRESSIONS) counts[impression.key] = 0
  for (const frame of frames) counts[impressionOf(frame.shapes, frame.steady)] += 1
  const n = frames.length || 1
  const shares: Record<string, number> = {}
  for (const key of Object.keys(counts)) shares[key] = counts[key] / n
  return { frames: frames.length, shares }
}
