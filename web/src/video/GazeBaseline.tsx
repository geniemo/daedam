import { useEffect, useRef, useState } from 'react'
import { median, std, type Baseline } from './gaze'
import type { FaceFrame } from './useFaceTracking'

/**
 * 시선 기준선 잡기 — 얼굴을 가운데 두고 정면을 잠깐 바라보게 합니다.
 *
 * **아홉 점을 보게 하던 보정을 대체합니다.** 그쪽은 화면 위 좌표를 맞히려는
 * 것이었는데, 웹캠 모델은 각도만 알지 화면이 어디 있는지를 모릅니다. 그래서
 * 보정이 20초씩 걸리고 부호 하나에 무너졌습니다. 지금은 정면 한 곳만 잡고
 * 거기서 얼마나 벗어나는지를 잽니다 — 우리가 실제로 잴 수 있는 것입니다.
 *
 * 여기서 두 가지를 받습니다.
 *   center — 정면을 볼 때의 신호. 벗어남의 원점입니다.
 *   noise  — 가만히 볼 때도 남는 흔들림. "벗어났다"의 기준을 이 값에서 뽑으므로
 *            사람마다·조명마다 다른 조건이 흡수됩니다.
 */

/** 얼굴이 가운데 있다고 볼 범위. 화면 폭·높이의 이 비율 안쪽입니다. */
const CENTER_BOX = 0.22

/** 자세를 잡을 시간. 이 동안은 받지 않고 안내만 합니다. */
const SETTLE_MS = 1200

/** 실제로 신호를 받는 시간. */
const HOLD_MS = 1600

const POLL_MS = 33

export function GazeBaseline({
  latest,
  onDone,
  onCancel,
}: {
  latest: () => FaceFrame
  onDone: (baseline: Baseline) => void
  onCancel: () => void
}) {
  const [held, setHeld] = useState(0)
  const [centered, setCentered] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [warning, setWarning] = useState<string | null>(null)
  const done = useRef(false)

  useEffect(() => {
    done.current = false
    const xs: number[] = []
    const ys: number[] = []
    let lastAt = -1
    let found = 0
    let total = 0
    let settledAt = 0

    const timer = window.setInterval(() => {
      const frame = latest()
      if (frame.at === lastAt) return
      lastAt = frame.at

      // 얼굴이 가운데에서 벗어나 있으면 받지 않고 기다린다. 구석에서 잡은
      // 기준선은 면접 내내 어긋난 원점이 된다.
      const ok = frame.found && Math.abs(frame.center.x - 0.5) < CENTER_BOX &&
        Math.abs(frame.center.y - 0.5) < CENTER_BOX
      setCentered(ok)
      if (!ok) {
        settledAt = 0
        xs.length = 0
        ys.length = 0
        found = 0
        total = 0
        setHeld(0)
        return
      }

      if (settledAt === 0) settledAt = performance.now()
      const elapsed = performance.now() - settledAt
      if (elapsed < SETTLE_MS) {
        setHeld(0)
        return
      }

      total += 1
      if (frame.found) {
        found += 1
        xs.push(frame.gaze.x)
        ys.push(frame.gaze.y)
      }
      setHeld(Math.min(1, (elapsed - SETTLE_MS) / HOLD_MS))
      if (elapsed - SETTLE_MS < HOLD_MS || done.current) return

      done.current = true
      window.clearInterval(timer)
      if (total === 0 || found / total < 0.6 || xs.length < 8) {
        setWarning('얼굴이 잘 안 보입니다. 다시 받겠습니다')
        setAttempt((a) => a + 1)
        return
      }
      // 흔들림은 두 축 중 큰 쪽을 쓴다. 작은 쪽으로 잡으면 기준이 지나치게
      // 빡빡해져 가만히 있어도 "벗어났다"가 된다.
      const noise = Math.max(std(xs), std(ys))
      onDone({ center: { x: median(xs), y: median(ys) }, noise: Math.max(noise, 1e-4) })
    }, POLL_MS)

    return () => window.clearInterval(timer)
  }, [attempt, latest, onDone])

  return (
    <div className="fixed inset-0 z-70 flex flex-col items-center justify-center gap-[26px] bg-stage">
      {/* 얼굴을 맞출 자리. 원 안에 들어오면 색이 바뀐다 — 글로 설명하는 것보다
          테두리 하나가 빠르다. */}
      <div
        className="relative rounded-full"
        style={{
          width: 260,
          height: 260,
          border: `2px solid ${centered ? 'var(--color-listening)' : 'var(--color-stage-line)'}`,
          transition: 'border-color .25s ease',
        }}
      >
        <span
          className="absolute rounded-full"
          style={{
            left: '50%',
            top: '50%',
            transform: 'translate(-50%, -50%)',
            width: 16,
            height: 16,
            background: 'var(--color-accent)',
            boxShadow: `0 0 0 ${2 + held * 16}px rgba(181,127,28,${0.08 + held * 0.16})`,
          }}
        />
      </div>

      <div className="flex flex-col items-center gap-[9px] px-8 text-center">
        <span className="text-[17px] font-semibold text-stage-ink-2">
          {warning ?? (centered ? '노란 점을 그대로 바라봐 주세요' : '얼굴을 원 안에 맞춰 주세요')}
        </span>
        <span className="text-[13px] text-stage-muted">
          이 자세가 &lsquo;정면&rsquo;의 기준이 됩니다. 면접 중 여기서 얼마나 벗어나는지를 잽니다
        </span>
        <button
          onClick={onCancel}
          className="mt-[8px] rounded-control border border-stage-line px-[16px] py-[8px] text-[12.5px] text-stage-muted-2"
        >
          건너뛰기
        </button>
      </div>
    </div>
  )
}
