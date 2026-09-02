import { useCallback, useEffect, useRef } from 'react'
import { cellOf, deviation, type Baseline } from './gaze'
import { strengths } from './expression'
import type { FaceFrame } from './useFaceTracking'

/**
 * 면접 내내 시선과 인상을 모읍니다.
 *
 * **1초에 한 줄로 접습니다.** 15fps로 20분이면 18,000프레임인데, 그걸 다 보낼
 * 이유가 없습니다. 나중에 쪼갤 단위가 답변(보통 10~60초)이라 초 단위면 충분하고,
 * 20분이 1,200줄이라 크기를 신경 쓸 필요가 없어집니다.
 *
 * **요약이 아니라 타임라인을 보냅니다.** 답변 구간은 면접이 끝난 뒤 서버가
 * 오디오를 분석해야 알 수 있습니다 — 그때 잘라 쓸 수 있게 시각을 남깁니다.
 * 클라이언트가 미리 합쳐 버리면 답변별로 나눌 방법이 사라집니다.
 *
 * **여기서 인상을 매기지 않습니다.** 앞서는 프레임마다 근육 문턱으로
 * 분류했는데, 차분한 얼굴에서 근육 신호가 0에 깔려 전부 한 칸으로 몰렸습니다.
 * 인상은 3초 스냅샷을 서버가 VLM으로 읽습니다(eval/expression.py). 근육
 * 세기(`s`)는 계속 남깁니다 — 미소 같은 확인 가능한 사실의 재료입니다.
 *
 * **얼굴을 못 찾은 초는 빠집니다.** 자리를 비운 시간을 "정면을 안 봤다"로 세면
 * 없는 사실을 만드는 것입니다. 빠진 초가 많으면 리포트가 그 사실을 말해야 하므로
 * 총 몇 초를 담았는지도 같이 보냅니다.
 */

/** 한 줄로 접는 단위. */
const BUCKET_S = 1

export interface GazeSecond {
  /** 면접 경과 초. 답변 구간과 맞추는 열쇠입니다. */
  at: number
  /** 3×3 격자에서의 칸(0~8, 4가 정면). */
  cell: number
  /** 정면에서 벗어난 정도(흔들림 대비 배수)의 평균. */
  ratio: number
  /**
   * 근육 세기의 평균 — 미소·긴장·눈 크게.
   *
   * 분류 결과와 함께 원본을 남깁니다. 문턱은 잠정이라 언젠가 다시 잡아야 하는데,
   * 이 값이 없으면 그때마다 새로 녹화해야 합니다.
   */
  s: [number, number, number]
}

export interface GazeLog {
  baseline: Baseline
  seconds: GazeSecond[]
}

/** 가장 많이 나온 값. 같으면 먼저 나온 것을 씁니다. */
function mode(values: string[]): string {
  const counts = new Map<string, number>()
  let best = values[0]
  let bestCount = 0
  for (const value of values) {
    const next = (counts.get(value) ?? 0) + 1
    counts.set(value, next)
    if (next > bestCount) {
      best = value
      bestCount = next
    }
  }
  return best
}

function modeNumber(values: number[]): number {
  return Number(mode(values.map(String)))
}

export function useGazeLog(
  latest: () => FaceFrame,
  baseline: Baseline | null,
  /** 면접 경과 초를 돌려주는 함수. 답변 구간과 같은 시계여야 합니다. */
  elapsedNow: () => number,
) {
  const seconds = useRef<GazeSecond[]>([])
  const base = useRef<Baseline | null>(null)
  base.current = baseline

  const snapshot = useCallback((): GazeLog | null => {
    if (!base.current || seconds.current.length === 0) return null
    return { baseline: base.current, seconds: seconds.current }
  }, [])

  useEffect(() => {
    if (!baseline) return
    seconds.current = []
    let lastAt = -1
    let bucketStart = -1
    let cells: number[] = []
    let ratios: number[] = []
    let muscles: { smile: number; worry: number; wide: number }[] = []

    const flush = () => {
      if (bucketStart < 0 || cells.length === 0) return
      seconds.current.push({
        at: Math.round(bucketStart * 10) / 10,
        cell: modeNumber(cells),
        ratio: Math.round((ratios.reduce((a, b) => a + b, 0) / ratios.length) * 100) / 100,
        s: (['smile', 'worry', 'wide'] as const).map((key) =>
          Math.round((muscles.reduce((a, m) => a + m[key], 0) / muscles.length) * 1000) / 1000,
        ) as [number, number, number],
      })
      cells = []
      ratios = []
      muscles = []
    }

    const timer = window.setInterval(() => {
      const frame = latest()
      // 새 프레임만 본다 — 얼굴 인식(66ms)보다 촘촘히 도는 타이머다.
      if (frame.at === lastAt) return
      lastAt = frame.at
      // 얼굴을 못 찾은 프레임은 담지 않는다. 없는 초는 없는 채로 둔다.
      if (!frame.found) return

      const now = elapsedNow()
      if (bucketStart < 0) bucketStart = now
      if (now - bucketStart >= BUCKET_S) {
        flush()
        bucketStart = now
      }

      const dev = deviation(baseline, frame.gaze)
      cells.push(cellOf(dev))
      ratios.push(dev.ratio)
      muscles.push(strengths(frame.shapes))
    }, 33)

    return () => {
      window.clearInterval(timer)
      flush()
    }
  }, [baseline, latest, elapsedNow])

  return { snapshot }
}
