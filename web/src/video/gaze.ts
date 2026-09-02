/**
 * 시선을 "정면에서 얼마나 벗어났는가"로 재는 규칙.
 *
 * **화면 좌표를 주장하지 않습니다.** 웹캠 모델이 주는 것은 시선의 *각도*이고,
 * 그걸 화면 위 좌표로 옮기려면 카메라가 화면 어디에 붙었는지·화면이 얼마나
 * 큰지·얼마나 떨어져 앉았는지를 알아야 합니다. 모델은 그걸 모릅니다. 앞서
 * 화면을 아홉 칸으로 나눠 어디를 봤는지 맞히려 했는데, 그러자면 아홉 점을
 * 차례로 보게 하는 긴 보정이 필요했고 부호 하나만 어긋나도 통째로 무너졌습니다.
 *
 * 지금은 **정면 한 곳만 기준으로 잡고 거기서 벗어난 정도**를 잽니다. 우리가
 * 실제로 잴 수 있는 것이 그것이고, 면접에서 의미 있는 것도 "화면 어느 칸"이
 * 아니라 "정면을 유지했는가 / 얼마나 흔들렸는가"입니다.
 */

export interface GazePoint {
  x: number
  y: number
}

/**
 * 정면을 볼 때의 시선 신호. 앉은 자리가 바뀌면 무효라 면접마다 다시 잡습니다.
 *
 * `noise`는 그 사람이 가만히 볼 때도 남는 흔들림입니다. 사람마다·조명마다
 * 다르므로, "벗어났다"의 기준을 절댓값으로 못 박지 않고 이 값에서 뽑습니다.
 */
export interface Baseline {
  center: GazePoint
  noise: number
}

/** 벗어남을 방향까지 담아 돌려줍니다. */
export interface Deviation {
  /** 정면에서 떨어진 거리. `Baseline.noise` 배수가 아니라 원 신호 단위입니다. */
  distance: number
  /** 흔들림 대비 몇 배로 벗어났는가. 사람 사이 비교가 되는 값입니다. */
  ratio: number
  dx: number
  dy: number
}

/** 흔들림의 몇 배를 넘으면 "정면을 벗어났다"로 볼지. */
export const AWAY_RATIO = 3

/**
 * 흔들림의 하한. **이것이 없으면 기준이 무너집니다.**
 *
 * 기준선을 잡을 때 사람은 점을 뚫어지게 보며 굳어 있습니다. 그때의 미세 떨림을
 * 그대로 "정상 범위"로 쓰면 문턱이 터무니없이 좁아지고, 말하면서 자연스럽게
 * 움직이는 실제 면접에서는 거의 모든 프레임이 "벗어남"이 됩니다 — 실측에서
 * noise가 0.0019로 잡혀 벗어남 중앙값이 그 **81배**였고, 정면 비율이 8%,
 * 표정이 98% 긴장으로 무너졌습니다.
 *
 * 값은 신호 규모에서 나옵니다. 홍채 오프셋은 눈 폭으로 나눈 값이라 사람·거리에
 * 무관하고, 화면 가장자리를 볼 때 0.2 안팎까지 움직입니다. 그 1/10을 "같은 곳을
 * 보고 있다"의 하한으로 둡니다.
 *
 * **잠정입니다.** 실측 한 판으로 정한 값이라 면접이 쌓이면 다시 잡아야 합니다.
 */
export const MIN_NOISE = 0.02

export function deviation(baseline: Baseline, point: GazePoint): Deviation {
  const dx = point.x - baseline.center.x
  const dy = point.y - baseline.center.y
  const distance = Math.hypot(dx, dy)
  const noise = Math.max(baseline.noise, MIN_NOISE)
  return { distance, ratio: distance / noise, dx, dy }
}

/**
 * 3×3 격자에서의 칸 번호(0~8, 왼쪽 위부터 행 우선). 4번이 정면입니다.
 *
 * **화면 위의 좌표가 아닙니다.** 정면에서 좌우로 벗어났는지, 위아래로
 * 벗어났는지를 축마다 따로 판정해 아홉 칸에 놓은 것입니다. 화면 어디를 봤는지
 * 맞히려면 카메라·화면의 기하를 알아야 하는데 우리는 모릅니다. 격자는 "정면
 * 기준으로 어느 쪽이 얼마나"를 읽기 쉽게 놓는 **표현 형식**입니다.
 */
export function cellOf(dev: Deviation, awayRatio = AWAY_RATIO): number {
  // 축마다 따로 본다. 한쪽만 크면 변·모서리가 아니라 변으로 간다.
  const unit = dev.ratio > 0 ? dev.distance / dev.ratio : 0
  const limit = unit * awayRatio
  const col = Math.abs(dev.dx) < limit ? 1 : dev.dx > 0 ? 2 : 0
  const row = Math.abs(dev.dy) < limit ? 1 : dev.dy > 0 ? 2 : 0
  return row * 3 + col
}

/** 칸 이름 — 리포트가 그대로 씁니다. 4번은 정면입니다. */
export const CELL_NAMES = [
  '왼쪽 위', '위', '오른쪽 위',
  '왼쪽', '정면', '오른쪽',
  '왼쪽 아래', '아래', '오른쪽 아래',
]

/** 값들의 중앙값. 눈 깜빡임 한 프레임이 평균을 끌고 가지 못하게 합니다. */
export function median(values: number[]): number {
  if (values.length === 0) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

export function std(values: number[]): number {
  if (values.length < 2) return 0
  const mean = values.reduce((a, b) => a + b, 0) / values.length
  return Math.sqrt(values.reduce((a, b) => a + (b - mean) ** 2, 0) / values.length)
}

/**
 * 면접 한 판의 시선 집계 — 리포트가 그대로 그립니다.
 *
 * 비율만 담고 판정은 담지 않습니다. "정면 72%"는 관찰이고 "산만했습니다"는
 * 주장인데, 웹캠 하나로 뒤엣것을 말할 근거가 없습니다.
 */
export interface GazeSummary {
  /** 얼굴이 보인 프레임 수. 이게 적으면 나머지 숫자를 믿을 수 없습니다. */
  frames: number
  /** 칸마다 머문 시간 비율(0~1). 아홉 개의 합이 1입니다. */
  cells: number[]
  /** 정면(4번 칸)에 머문 비율. 화면 상단의 "N% 안정"이 이것입니다. */
  steady: number
  /** 시선이 얼마나 크게 움직였는가. 흔들림 대비 배수의 평균입니다. */
  wander: number
}

export function summarize(baseline: Baseline, points: GazePoint[]): GazeSummary {
  const cells = new Array(9).fill(0)
  let total = 0
  for (const point of points) {
    const dev = deviation(baseline, point)
    total += dev.ratio
    cells[cellOf(dev)] += 1
  }
  const n = points.length || 1
  return {
    frames: points.length,
    cells: cells.map((c) => c / n),
    steady: cells[4] / n,
    wander: total / n,
  }
}
