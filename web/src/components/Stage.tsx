import { useEffect, useRef } from 'react'
import type { CSSProperties, RefObject } from 'react'
import type { Levels } from '@/audio/useVoiceSession'

/**
 * 무대의 부품 — 면접관(구체), 파형, 키라이트, 진행 막대.
 *
 * 무대는 밝은 화면과 다른 세계다(index.css의 --stage-* 토큰). 면접 화면·문턱
 * 띠(준비 완료)·리서치 진행·분석 중·리포트 머리·랜딩의 데모 창이 같은 부품을
 * 그린다. 규격: design_handoff_daedam/design-system/components/stage.
 *
 * **면접관은 무광 유리 구체 하나다.** 앞서 있던 동심원 링은 레이더로 읽혀서
 * 걷어냈다. 구체 안의 불이 말차례를 쥔다 — 면접관이 말하면 앰버, 지원자의 말을
 * 들을 때는 민트. 바깥 번짐도 같은 색을 따른다.
 *
 * **구동 방식이 둘이다.** 면접에서는 실제 오디오 진폭(`levels`)이 60fps로
 * 들어오므로 React state를 거치지 않고 rAF 루프가 ref → style에 직접 쓴다.
 * 오디오가 없으면(문턱·리포트 머리·분석 중) 불의 밝기를 `glow`로 고정하고
 * 숨쉬기 애니메이션만 돈다.
 */

/** 면접 화면 원본 지름. 문턱·리서치·분석 128, 랜딩 데모 150, 리포트 머리 72. */
const BASE_SIZE = 216

export function Avatar({
  speaking,
  levels,
  size = BASE_SIZE,
  glow,
  bloom = true,
}: {
  speaking: boolean
  /** 실제 오디오 진폭. 없으면 정적으로 선다. */
  levels?: RefObject<Levels>
  /** 구체 지름(px). */
  size?: number
  /** 정적일 때 불의 불투명도. 없으면 말할 때 .85, 들을 때 .4. */
  glow?: number
  /** 구체 바깥의 번짐. 좁은 자리(카드 안)에서는 끈다. */
  bloom?: boolean
}) {
  const live = levels !== undefined
  const voice = useRef<HTMLDivElement>(null)
  const bloomEl = useRef<HTMLDivElement>(null)
  // 루프가 phase마다 다시 붙지 않도록 ref로 읽는다.
  const isSpeaking = useRef(speaking)
  isSpeaking.current = speaking

  useEffect(() => {
    if (!levels) return
    let raf = 0
    const loop = () => {
      const talking = isSpeaking.current
      const level = talking ? levels.current.output : levels.current.input
      // 면접관이 말할 때는 불이 늘 켜져 있고 진폭이 그 위에 얹힌다. 들을 때는
      // 지원자의 목소리가 불이다 — 조용하면 잦아들고 말하면 또렷이 차오른다.
      // 앞서는 입력 진폭을 0.35배로 눌러 놓아 말해도 빛이 보이지 않았다(실측).
      if (voice.current) {
        voice.current.style.transform = `scale(${1 + level * (talking ? 0.16 : 0.22)})`
        voice.current.style.opacity = String(talking ? 0.6 + level * 0.4 : 0.3 + level * 0.7)
      }
      if (bloomEl.current) {
        bloomEl.current.style.transform = `scale(${1 + level * 0.12})`
        bloomEl.current.style.opacity = String(talking ? 1 : 0.6 + level * 0.4)
      }
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [levels])

  // 큰 구체는 토큰의 그림자 그대로, 작은 구체는 안쪽 그림자만 지름에 비례해서.
  const shadow =
    size >= 160
      ? 'var(--shadow-sphere)'
      : `inset 0 1px 0 rgba(255,255,255,.10), inset 0 -${Math.round(size * 0.14)}px ${Math.round(size * 0.25)}px rgba(0,0,0,.42)`
  const layer: CSSProperties = { position: 'absolute', inset: 0, borderRadius: '50%' }

  return (
    <div data-avatar-slot="true" style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <div
        style={{
          ...layer,
          background: 'var(--gradient-sphere)',
          boxShadow: shadow,
          animation: 'dm-breathe 6s ease-in-out infinite',
        }}
      />
      <div style={{ ...layer, background: 'var(--gradient-sphere-sheen)' }} />
      <div
        ref={voice}
        style={{
          ...layer,
          background: speaking ? 'var(--gradient-voice-amber)' : 'var(--gradient-voice-mint)',
          opacity: live ? (speaking ? 0.6 : 0.28) : (glow ?? (speaking ? 0.85 : 0.4)),
          transition: 'background 1.4s ease, opacity 1s ease',
        }}
      />
      {bloom && (
        <div
          ref={bloomEl}
          style={{
            ...layer,
            inset: -Math.round(size * 0.5),
            pointerEvents: 'none',
            background: speaking
              ? 'radial-gradient(circle, rgba(var(--stage-keylight-rgb), .13), transparent 60%)'
              : 'radial-gradient(circle, rgba(var(--stage-mint-rgb), .09), transparent 60%)',
            transition: 'background 1.4s ease',
          }}
        />
      )}
    </div>
  )
}

/**
 * 마이크 입력 파형 — 3px 폭 막대 16개, 모래색.
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
          style={{
            width: 3,
            height,
            background: 'var(--stage-sand)',
            transformOrigin: 'center',
            transform: 'scaleY(0.22)',
          }}
        />
      ))}
    </div>
  )
}

/** 눕은 파형 — 답변이 녹음되지 않았을 때. 조금 전까지 움직이던 막대가 전부 누웠다. */
export function FlatWaveform({ dark = false, height = 38 }: { dark?: boolean; height?: number }) {
  return (
    <div className="flex items-center" style={{ gap: 3, height }}>
      {Array.from({ length: BAR_COUNT }, (_, i) => (
        <div
          key={i}
          style={{ width: 3, height: 2, background: dark ? 'rgba(255,255,255,.18)' : 'var(--color-line)' }}
        />
      ))}
    </div>
  )
}

/**
 * 정지한 키라이트 — 무대 위쪽에서 내려오는 타원 하나. 움직이지 않는다.
 * 면접에서는 면접관이 말할 때 조금 밝아진다(alpha .10 / .06).
 */
export function Keylight({
  width,
  height,
  top,
  left = '50%',
  alpha = 0.07,
}: {
  width: number
  height: number
  top: string | number
  left?: string | number
  alpha?: number
}) {
  return (
    <div
      className="pointer-events-none absolute"
      style={{
        left,
        top,
        width,
        height,
        transform: 'translateX(-50%)',
        background: `radial-gradient(ellipse at 50% 0%, rgba(var(--stage-keylight-rgb), ${alpha}), transparent 62%)`,
        transition: 'background 1.4s ease',
      }}
    />
  )
}

/**
 * 무대 위의 진행 막대 — 2px, 앰버. pct를 모르면(null) 조각이 지나간다.
 * 밝은 화면의 ProgressBar·IndeterminateBar와 약속은 같고 색만 무대 것이다.
 */
export function StageBar({ pct, width = '100%' }: { pct: number | null; width?: number | string }) {
  return (
    <div className="overflow-hidden" style={{ width, height: 2, background: 'rgba(255,255,255,.08)' }}>
      <div
        className={pct === null ? 'animate-dm-slide h-full' : 'h-full'}
        style={{
          width: pct === null ? '25%' : `${pct}%`,
          background: 'var(--stage-amber)',
          transition: pct === null ? undefined : 'width .4s ease',
        }}
      />
    </div>
  )
}
