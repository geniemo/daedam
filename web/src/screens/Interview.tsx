import { useCallback, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router'
import { useActiveCard } from '@/store/app'
import { formatClock, useInterviewStore } from '@/store/interview'
import { useVoiceSession, type Levels } from '@/audio/useVoiceSession'
import { fill } from '@/data/mock'

/** README §8. 면접 진행 — 화면이 시선을 뺏지 않는 것이 목표입니다. */
export function Interview({ showCaption = true }: { showCaption?: boolean }) {
  const nav = useNavigate()
  const card = useActiveCard()

  // 진행 상태는 전부 서버가 내려준 것입니다 (§/ws/interview의 session·question
  // 메시지). 화면이 자체 대본을 그리면 실제 면접과 어긋납니다 — 면접관은
  // 뼈대질문을 그대로 읽지 않고, 꼬리질문에는 대본 자체가 없습니다.
  //
  // 단계와 남은 시간은 보여주지 않습니다. 면접을 끝내는 것은 지원자의 버튼이라
  // "남은 시간"이 없고, 단계는 서버가 질문을 고르는 내부 사정이지 지원자가
  // 의식할 것이 아닙니다 — 실제 면접에서도 "지금은 인성 단계입니다"라고 알려
  // 주지 않습니다.
  const phase = useInterviewStore((s) => s.phase)
  const caption = useInterviewStore((s) => s.caption)
  // 화면에 번호로 띄우지는 않는다. 새 뼈대질문마다 자막 fade를 다시 돌리는
  // key로만 쓴다.
  const askedCount = useInterviewStore((s) => s.askedCount)
  const elapsed = useInterviewStore((s) => s.elapsed)
  const connection = useInterviewStore((s) => s.connection)

  // 크레딧이 없어 면접이 열리지도 않은 경우는 분석할 것이 없다 — 홈으로
  // 돌려보낸다. 그 밖에는 정상 종료라 결과를 기다린다.
  const onFinished = useCallback(
    (reason?: string) => nav(reason === 'credits' ? '/' : '/analyzing'),
    [nav],
  )
  const { levels, end } = useVoiceSession(card.id, onFinished)

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
        <span className="num text-[13px] text-stage-ink">{formatClock(elapsed)}</span>
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

      {/* 하단 컨트롤 — 종료 버튼 하나. 질문 번호·단계·남은 시간 같은 진행
          표시는 두지 않는다. 실제 면접에서 지원자가 보는 것은 면접관뿐이다. */}
      <div className="px-[30px] pb-[26px]">
        <div className="flex items-center justify-end">
          {/* 멈췄다 이어가는 길은 두지 않는다 — 면접은 한 번에 끝까지 간다.
              중간에 그만두면 그때까지의 답변으로 리포트를 받는다. */}
          <button
            onClick={end}
            className="tap44 rounded-control border border-stage-line px-[18px] py-[9px] text-[13px] text-stage-muted-2"
          >
            종료하고 리포트 받기
          </button>
        </div>
      </div>

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
