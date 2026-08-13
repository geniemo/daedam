import { useCallback, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router'
import { useActiveCard } from '@/store/app'
import { formatClock, remainingSeconds, stageAt, useInterviewStore } from '@/store/interview'
import { useVoiceSession, type Levels } from '@/audio/useVoiceSession'
import { STAGE_NAMES, fill } from '@/data/mock'

/** README §8. 면접 진행 — 화면이 시선을 뺏지 않는 것이 목표입니다. */
export function Interview({ showCaption = true }: { showCaption?: boolean }) {
  const nav = useNavigate()
  const card = useActiveCard()

  // 진행 상태는 전부 서버가 내려준 것입니다 (§/ws/interview의 session·question
  // 메시지). 화면이 자체 대본을 그리면 실제 면접과 어긋납니다 — 면접관은
  // 뼈대질문을 그대로 읽지 않고, 꼬리질문에는 대본 자체가 없습니다.
  const phase = useInterviewStore((s) => s.phase)
  const deliveredStage = useInterviewStore((s) => s.stage)
  const caption = useInterviewStore((s) => s.caption)
  const askedCount = useInterviewStore((s) => s.askedCount)
  const elapsed = useInterviewStore((s) => s.elapsed)
  const totalSeconds = useInterviewStore((s) => s.totalSeconds)
  const stageBudgets = useInterviewStore((s) => s.stageBudgets)
  const paused = useInterviewStore((s) => s.paused)
  const connection = useInterviewStore((s) => s.connection)
  const togglePause = useInterviewStore((s) => s.togglePause)

  const onFinished = useCallback(() => nav('/analyzing'), [nav])
  const { levels, setPaused, end } = useVoiceSession(card.id, onFinished)

  // 진행 바는 단계별 시간 예산이 칸 너비이고 경과 시간이 채움입니다 — 단계를
  // 넘기는 것이 질문 수가 아니라 시간이라서 그렇습니다. 예산을 모르면(백엔드
  // 없이 도는 프로토타입) 균등 분할합니다.
  const budgets = stageBudgets ?? STAGE_NAMES.map(() => totalSeconds / STAGE_NAMES.length)

  // 단계도 같은 시계에서 뽑습니다. 다만 서버가 더 앞선 단계를 알려줬다면
  // (질문을 일찍 소진해 먼저 넘어간 경우) 그쪽이 맞습니다.
  const stage = Math.max(deliveredStage, stageAt(elapsed, budgets))

  const doPause = () => {
    const next = !paused
    togglePause()
    setPaused(next)
  }

  return (
    <div className="fixed inset-0 z-60 flex flex-col bg-stage">
      {/* 상단 오버레이 */}
      <div className="absolute top-0 right-0 left-0 z-3 flex items-center px-[30px] py-[22px]">
        <div className="flex items-center gap-[8px]">
          <span
            className="rounded-full"
            style={{
              width: 6,
              height: 6,
              background: phase === 'speaking' ? 'var(--color-accent)' : 'var(--color-listening)',
            }}
          />
          <span className="text-[13.5px] text-stage-ink">
            {phase === 'speaking' ? '면접관이 말하고 있습니다' : '듣고 있습니다'}
          </span>
          {connection === 'reconnecting' && (
            <span className="text-[12.5px] text-stage-muted-3">· 연결을 복구하는 중입니다</span>
          )}
        </div>
        <div className="flex-1" />
        <div className="flex items-center gap-[10px]">
          <span className="text-[13px] text-stage-muted">
            {stage + 1}단계 · {STAGE_NAMES[stage]}
          </span>
          <span className="bg-body" style={{ width: 1, height: 12 }} />
          <span className="num text-[13px] text-stage-ink">
            {formatClock(remainingSeconds(elapsed, totalSeconds))}
          </span>
        </div>
      </div>

      {/* 아바타 영역 */}
      <div className="flex flex-1 items-center justify-center">
        <Avatar levels={levels} speaking={phase === 'speaking'} />
      </div>

      {/* 자막 — 면접관이 실제로 하고 있는 말. 뼈대질문 문장이 아닙니다. */}
      {showCaption && caption && (
        <div
          key={askedCount}
          className="mx-auto max-w-[660px] animate-dm-fade-slow px-8 text-center text-[17px] leading-[1.65] font-medium tracking-[-.01em] text-stage-ink"
        >
          {fill(caption, card.company, card.role)}
        </div>
      )}

      {/* 하단 상태 영역 */}
      <div className="flex h-[104px] items-center justify-center">
        {phase === 'listening' ? (
          <Waveform levels={levels} />
        ) : (
          <span className="text-[12.5px] text-stage-muted-3">답변이 끝나면 마이크가 열립니다</span>
        )}
      </div>

      {/* 하단 컨트롤 */}
      <div className="flex flex-col gap-[14px] px-[30px] pb-[26px]">
        <div className="flex gap-[6px]">
          {STAGE_NAMES.map((name, i) => {
            const before = budgets.slice(0, i).reduce((sum, seconds) => sum + seconds, 0)
            const prog = Math.max(0, Math.min(1, (elapsed - before) / budgets[i]))
            return (
              <div
                key={name}
                className="bg-stage-line-2"
                style={{ height: 2.5, flexGrow: budgets[i], flexBasis: 0 }}
              >
                <div
                  className="h-full bg-accent"
                  style={{ width: `${Math.round(prog * 100)}%`, transition: 'width .5s ease' }}
                />
              </div>
            )
          })}
        </div>
        <div className="flex items-center">
          {/* 분모를 두지 않습니다 — 풀은 여유 있게 만들고 다 묻지 않습니다.
              아직 한 문항도 안 나갔으면 번호를 지어내지 않고 비워 둡니다. */}
          <span className="num text-[12.5px] text-stage-muted-3">
            {askedCount > 0 ? `질문 ${askedCount}` : ''}
          </span>
          <div className="flex-1" />
          <div className="flex gap-[10px]">
            <button
              onClick={doPause}
              className="tap44 rounded-control border border-stage-line px-[18px] py-[9px] text-[13px] text-stage-muted-2"
            >
              일시정지
            </button>
            <button
              onClick={end}
              className="tap44 rounded-control border border-stage-line px-[18px] py-[9px] text-[13px] text-stage-muted-2"
            >
              종료
            </button>
          </div>
        </div>
      </div>

      {paused && <PauseOverlay onResume={doPause} onEnd={end} onCancel={() => nav('/')} />}
    </div>
  )
}

/**
 * 아바타 + 발화 링.
 *
 * README §Assets는 링을 순수 CSS 애니메이션으로 정의하지만, 여기서는 모델
 * 출력 오디오의 실제 진폭으로 구동합니다. 값이 60fps로 바뀌므로 React state를
 * 거치지 않고 ref → style에 직접 씁니다.
 *
 * `data-avatar-slot="true"` 컨테이너 내부만 교체하면 실제 아바타로 대체됩니다.
 * 링·자막·컨트롤은 이 컨테이너 바깥에 있습니다.
 */
function Avatar({ levels, speaking }: { levels: React.RefObject<Levels>; speaking: boolean }) {
  const ringA = useRef<HTMLDivElement>(null)
  const ringB = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let raf = 0
    const loop = () => {
      const out = levels.current.output
      if (ringA.current) {
        ringA.current.style.transform = `scale(${1 + out * 0.26})`
        ringA.current.style.opacity = String(0.06 + out * 0.26)
      }
      if (ringB.current) {
        ringB.current.style.transform = `scale(${1 + out * 0.14})`
        ringB.current.style.opacity = String(0.14 + out * 0.36)
      }
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [levels])

  return (
    <div className="relative flex items-center justify-center" style={{ width: 340, height: 340 }}>
      {speaking && (
        <>
          <div
            ref={ringA}
            className="absolute rounded-full"
            style={{
              width: 340,
              height: 340,
              background: 'radial-gradient(circle, rgba(181,127,28,.5), transparent 68%)',
            }}
          />
          <div
            ref={ringB}
            className="absolute rounded-full"
            style={{ width: 270, height: 270, border: '1px solid rgba(181,127,28,.34)' }}
          />
        </>
      )}

      <div
        data-avatar-slot="true"
        className="relative flex animate-dm-breathe items-center justify-center overflow-hidden rounded-full"
        style={{
          width: 206,
          height: 206,
          background: 'linear-gradient(160deg, #233047, #16223A)',
          border: '1px solid #2E3F5C',
        }}
      >
        <div
          className="absolute inset-0"
          style={{
            background: 'radial-gradient(circle at 34% 28%, rgba(255,255,255,.07), transparent 58%)',
          }}
        />
        <div
          className="flex items-center justify-center rounded-full"
          style={{ width: 96, height: 96, border: '1px solid rgba(232,236,243,.22)' }}
        >
          <div
            className="rounded-full"
            style={{ width: 44, height: 44, background: 'rgba(181,127,28,.85)' }}
          />
        </div>
      </div>
    </div>
  )
}

/**
 * 마이크 입력 파형 — 3px 폭 막대 16개, 높이 38px.
 * 진폭은 입력 AnalyserNode에서 옵니다. 막대별 위상차로 파도 모양을 만듭니다.
 */
const BAR_COUNT = 16

function Waveform({ levels }: { levels: React.RefObject<Levels> }) {
  const bars = useRef<(HTMLDivElement | null)[]>([])

  useEffect(() => {
    let raf = 0
    const loop = () => {
      const level = levels.current.input
      const t = performance.now() / 1000
      for (let i = 0; i < BAR_COUNT; i++) {
        const el = bars.current[i]
        if (!el) continue
        const phase = Math.sin(t * 6 + i * 0.7) * 0.5 + 0.5
        const scale = 0.22 + level * (0.35 + 0.65 * phase) * 0.78
        el.style.transform = `scaleY(${Math.min(1, scale)})`
      }
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [levels])

  return (
    <div className="flex items-center" style={{ gap: 3, height: 38 }}>
      {Array.from({ length: BAR_COUNT }, (_, i) => (
        <div
          key={i}
          ref={(el) => {
            bars.current[i] = el
          }}
          className="bg-accent"
          style={{ width: 3, height: 38, transformOrigin: 'center', transform: 'scaleY(0.22)' }}
        />
      ))}
    </div>
  )
}

function PauseOverlay({
  onResume,
  onEnd,
  onCancel,
}: {
  onResume: () => void
  onEnd: () => void
  onCancel: () => void
}) {
  return (
    <div
      className="absolute inset-0 z-5 flex items-center justify-center"
      style={{ background: 'rgba(14,23,38,.86)', backdropFilter: 'blur(6px)' }}
    >
      <div
        className="flex flex-col gap-3 rounded-card border border-stage-line p-7"
        style={{ width: 390, background: 'var(--color-stage-surface)' }}
      >
        <h2 className="m-0 text-[19px] font-bold text-stage-ink-2">면접을 잠시 멈췄습니다</h2>
        <p className="m-0 mb-2 text-[13.5px] text-stage-muted">
          이어서 진행하거나, 지금까지의 답변만으로 리포트를 받을 수 있습니다.
        </p>
        <button
          onClick={onResume}
          className="tap44 rounded-control bg-accent py-3 text-[14px] font-semibold text-white"
        >
          이어서 진행
        </button>
        <button onClick={onEnd} className="tap44 text-[13px] text-stage-muted-2">
          종료하고 리포트 받기
        </button>
        <button onClick={onCancel} className="tap44 text-[12.5px] text-stage-muted-3">
          면접 취소 · 기록을 남기지 않습니다
        </button>
      </div>
    </div>
  )
}
