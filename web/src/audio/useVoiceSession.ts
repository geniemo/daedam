import { useCallback, useEffect, useRef } from 'react'
import { VoiceSession } from './voiceSession'
import { useInterviewStore } from '@/store/interview'

/**
 * 면접 화면과 음성 세션을 잇는 훅.
 *
 * 앞서는 `VITE_VOICE_BACKEND`가 꺼져 있으면 프로토타입 타이밍(질문당 14초)으로
 * 도는 목업 경로가 있었다. 그 스위치는 빌드 시점에 굳고, 켜는 값은 gitignore된
 * `.env.local`에만 있어서 서버에서 새로 빌드하면 가짜 면접이 그대로 나갔다.
 * 지금은 늘 실제 세션(/ws/interview)에 붙는다. 백엔드 없이 화면 렌더만 보는
 * 것은 smoke(scripts/smoke.mjs)가 맡는다 — 이 훅의 effect는 SSR에서 돌지 않는다.
 */

export interface Levels {
  input: number
  output: number
}

export function useVoiceSession(
  cardId: string,
  onFinished: (reason?: string) => void,
) {
  const session = useRef<VoiceSession | null>(null)
  /** Audio-rate values live here, never in the store — see store/app.ts. */
  const levels = useRef<Levels>({ input: 0, output: 0 })
  const finished = useRef(false)

  const {
    setConnection,
    setPhase,
    setQuestion,
    appendCaption,
    applySession,
    setResumeToken,
    tick,
    reset,
  } = useInterviewStore.getState()

  const finish = useCallback(
    (reason?: string) => {
      if (finished.current) return
      finished.current = true
      onFinished(reason)
    },
    [onFinished],
  )

  useEffect(() => {
    finished.current = false
    reset()

    const s = new VoiceSession({
      cardId,
      handlers: {
        onConnection: setConnection,
        onSession: applySession,
        onPhase: setPhase,
        onQuestion: setQuestion,
        onCaption: appendCaption,
        onResumeToken: setResumeToken,
        onEnded: finish,
        onError: (e) => console.error('[voice]', e),
      },
    })
    session.current = s
    s.start().catch((e) => {
      console.error('[voice] start failed', e)
      setConnection('ended')
    })

    // 1초 간격 타이머 — 화면의 경과 시간을 움직입니다.
    const clock = setInterval(tick, 1000)

    // 파형과 아바타 링이 읽는 진폭. 60fps라 React state를 거치지 않는다.
    let raf = 0
    const loop = () => {
      if (session.current) levels.current = session.current.levels()
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)

    // §타이머와 인터벌: 화면을 벗어날 때 모든 인터벌을 정리해야 합니다
    return () => {
      clearInterval(clock)
      cancelAnimationFrame(raf)
      session.current?.stop()
      session.current = null
    }
  }, [
    cardId,
    finish,
    reset,
    setConnection,
    setPhase,
    setQuestion,
    appendCaption,
    applySession,
    setResumeToken,
    tick,
  ])

  const end = useCallback(() => {
    session.current?.stop()
    finish()
  }, [finish])

  // 웹캠 녹화가 마이크 트랙을 같이 담으려면 필요하다. ref로 내보내는 이유는
  // 세션이 연결된 뒤에야 생기고, 그 사이 화면을 다시 그릴 이유가 없어서다.
  const micStream = useCallback(() => session.current?.stream ?? null, [])
  return { levels, end, micStream }
}
