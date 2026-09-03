import { useEffect, useRef } from 'react'
import type { RefObject } from 'react'
import type { Levels } from '@/audio/useVoiceSession'

/**
 * 면접 무대의 아바타와 파형. 면접 화면(Interview.tsx)과 랜딩의 데모 창이 같은
 * 것을 그린다 — 규격은 README §8 아바타 영역, 값은 index.css의 무대 토큰.
 *
 * **구동 방식이 둘이다.** 면접에서는 실제 오디오 진폭(`levels`)이 60fps로
 * 들어오므로 React state를 거치지 않고 rAF 루프가 ref → style에 직접 쓴다.
 * 랜딩에는 오디오가 없다 — `levels`를 안 주면 README §Assets가 정의한 순수
 * CSS 애니메이션(dm-pulse · dm-pulse2)으로 돈다.
 *
 * **말할 때와 들을 때 둘 다 살아 있어야 한다.** 앞서는 링이 speaking일 때만
 * 붙어서, 지원자가 답하는 동안(면접 시간의 절반) 아바타가 정지한 검은 원이
 * 됐다. 지금은 링 두 벌이 늘 붙어 있고 불투명도로 건넨다 — 마운트를 여닫으면
 * 전환할 때 툭 끊긴다. 색이 갈린다: 면접관이 말할 때는 강조색(머스터드),
 * 지원자가 말할 때는 듣는 색(초록). 내 목소리가 면접관에게 가 닿는 것이
 * 보여야 대화가 된다.
 *
 * CSS 구동에서 링을 켜고 끄는 것은 링 자체가 아니라 바깥 래퍼의 불투명도다.
 * 키프레임이 opacity를 쥐고 있어서 링에 직접 opacity를 주면 애니메이션에
 * 덮여 speaking과 무관하게 늘 보인다.
 *
 * `data-avatar-slot="true"` 컨테이너 내부만 교체하면 실제 아바타로 대체된다.
 * 링·자막·컨트롤은 이 컨테이너 바깥에 있다.
 */

/** 면접 화면 원본 슬롯 지름. 다른 크기는 이 비율로 링·내부 도형까지 줄인다. */
const BASE_SIZE = 206

export function Avatar({
  speaking,
  levels,
  size = BASE_SIZE,
}: {
  speaking: boolean
  /** 실제 오디오 진폭. 없으면 CSS 애니메이션으로 돈다. */
  levels?: RefObject<Levels>
  /** 아바타 슬롯 지름(px). 링과 내부 도형이 같은 비율로 따라간다. */
  size?: number
}) {
  const s = size / BASE_SIZE
  const live = levels !== undefined
  const talkGlow = useRef<HTMLDivElement>(null)
  const talkRing = useRef<HTMLDivElement>(null)
  const hearRing = useRef<HTMLDivElement>(null)
  const core = useRef<HTMLDivElement>(null)
  // 루프가 phase마다 다시 붙지 않도록 ref로 읽는다.
  const isSpeaking = useRef(speaking)
  isSpeaking.current = speaking

  useEffect(() => {
    if (!levels) return
    let raf = 0
    const loop = () => {
      const talking = isSpeaking.current
      const out = levels.current.output
      const inp = levels.current.input

      if (talkGlow.current) {
        talkGlow.current.style.transform = `scale(${1 + out * 0.26})`
        talkGlow.current.style.opacity = String(talking ? 0.06 + out * 0.26 : 0)
      }
      if (talkRing.current) {
        talkRing.current.style.transform = `scale(${1 + out * 0.14})`
        talkRing.current.style.opacity = String(talking ? 0.14 + out * 0.36 : 0)
      }
      // 듣는 링은 지원자 목소리를 받는다. 조용해도 완전히 꺼지지 않는다 —
      // 꺼두면 "듣고 있다"가 화면에서 사라진다.
      if (hearRing.current) {
        hearRing.current.style.transform = `scale(${1 + inp * 0.1})`
        hearRing.current.style.opacity = String(talking ? 0 : 0.28 + inp * 0.62)
      }
      // 가운데 표식이 말차례를 쥔다. 면접관이 말하면 부풀고, 들을 때는 잦아든다.
      if (core.current) {
        const level = talking ? out : inp * 0.4
        core.current.style.transform = `scale(${(talking ? 1 : 0.82) + level * 0.22})`
      }
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [levels])

  // CSS 구동일 때 래퍼가 링을 켜고 끈다. 오디오 구동에서는 rAF가 링에 직접 쓴다.
  const gate = (on: boolean) =>
    live ? undefined : { opacity: on ? 1 : 0, transition: 'opacity .6s' }
  // 오디오 구동은 꺼진 채 시작한다 — 첫 진폭이 오기 전까지 링이 보이면 안 된다.
  const dark = live ? { opacity: 0 } : undefined

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: 340 * s, height: 340 * s }}
    >
      <div className="absolute inset-0 flex items-center justify-center" style={gate(speaking)}>
        <div
          ref={talkGlow}
          className={`rounded-full ${live ? '' : 'animate-dm-pulse2'}`}
          style={{ width: 340 * s, height: 340 * s, background: 'var(--gradient-talk-glow)', ...dark }}
        />
      </div>
      <div className="absolute inset-0 flex items-center justify-center" style={gate(speaking)}>
        <div
          ref={talkRing}
          className={`rounded-full border border-talk-ring ${live ? '' : 'animate-dm-pulse'}`}
          style={{ width: 270 * s, height: 270 * s, ...dark }}
        />
      </div>
      <div className="absolute inset-0 flex items-center justify-center" style={gate(!speaking)}>
        <div
          ref={hearRing}
          className={`rounded-full border-[1.5px] border-hear-ring ${live ? '' : 'animate-dm-pulse'}`}
          style={{ width: 246 * s, height: 246 * s, ...dark }}
        />
      </div>

      <div
        data-avatar-slot="true"
        className="relative flex animate-dm-breathe items-center justify-center overflow-hidden rounded-full border border-stage-line"
        style={{ width: size, height: size, background: 'var(--gradient-avatar)' }}
      >
        <div className="absolute inset-0" style={{ background: 'var(--gradient-avatar-highlight)' }} />
        <div
          className="flex items-center justify-center rounded-full border border-avatar-inner-ring"
          style={{ width: 96 * s, height: 96 * s }}
        >
          <div
            ref={core}
            className="rounded-full bg-avatar-core"
            style={{
              width: 44 * s,
              height: 44 * s,
              ...(live
                ? { transition: 'background .4s ease' }
                : { transform: speaking ? 'scale(1)' : 'scale(.82)', transition: 'transform .6s' }),
            }}
          />
        </div>
      </div>
    </div>
  )
}

/**
 * 마이크 입력 파형 — 3px 폭 막대 16개.
 * 진폭은 입력 AnalyserNode에서 온다. 막대별 위상차로 파도 모양을 만든다.
 * 오디오가 없으면(랜딩) 사인파 둘을 겹친 합성 진폭으로 말소리처럼 들쭉날쭉하게.
 */
const BAR_COUNT = 16

export function Waveform({
  levels,
  active = true,
  height = 38,
}: {
  /** 실제 오디오 진폭. 없으면 합성 진폭으로 돈다. */
  levels?: RefObject<Levels>
  /** 합성 진폭일 때만 — false면 막대가 눕는다. */
  active?: boolean
  height?: number
}) {
  const bars = useRef<(HTMLDivElement | null)[]>([])

  useEffect(() => {
    let raf = 0
    const loop = () => {
      const t = performance.now() / 1000
      const level = levels
        ? levels.current.input
        : active
          ? Math.max(0, Math.sin(t * 5.3) * 0.5 + Math.sin(t * 9.1) * 0.3 + 0.3)
          : 0
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
  }, [levels, active])

  return (
    <div className="flex items-center" style={{ gap: 3, height }}>
      {Array.from({ length: BAR_COUNT }, (_, i) => (
        <div
          key={i}
          ref={(el) => {
            bars.current[i] = el
          }}
          className="bg-accent"
          style={{ width: 3, height, transformOrigin: 'center', transform: 'scaleY(0.22)' }}
        />
      ))}
    </div>
  )
}
