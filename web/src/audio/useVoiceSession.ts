import { useCallback, useEffect, useRef } from 'react'
import { VoiceSession } from './voiceSession'
import { useInterviewStore, QUESTION_COUNT } from '@/store/interview'

/**
 * Drives the interview screen.
 *
 * Until the ADK backend is up, `VITE_VOICE_BACKEND` is unset and this runs the
 * prototype's scripted timing (§타이머와 인터벌: 한 질문당 14초 사이클 —
 * 발화 5초 → 청취 9초). Set VITE_VOICE_BACKEND=1 to talk to the real session
 * instead; nothing else in the UI changes.
 */
const USE_BACKEND = import.meta.env.VITE_VOICE_BACKEND === '1'

const SPEAK_SEC = 5
const LISTEN_SEC = 9
const CYCLE = SPEAK_SEC + LISTEN_SEC

export interface Levels {
  input: number
  output: number
}

export function useVoiceSession(cardId: string, onFinished: () => void) {
  const session = useRef<VoiceSession | null>(null)
  /** Audio-rate values live here, never in the store — see store/app.ts. */
  const levels = useRef<Levels>({ input: 0, output: 0 })
  const finished = useRef(false)

  const { setConnection, setPhase, setQIndex, setResumeToken, tick, reset } =
    useInterviewStore.getState()

  const finish = useCallback(() => {
    if (finished.current) return
    finished.current = true
    onFinished()
  }, [onFinished])

  useEffect(() => {
    finished.current = false
    reset()

    if (USE_BACKEND) {
      const s = new VoiceSession({
        cardId,
        handlers: {
          onConnection: setConnection,
          onPhase: setPhase,
          onQuestionIndex: setQIndex,
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
    } else {
      setConnection('live')
    }

    // 1초 간격 타이머. 일시정지 중에는 진행하지 않습니다 (store.tick이 처리).
    const clock = setInterval(() => {
      const before = useInterviewStore.getState()
      if (before.paused) return
      tick()

      if (!USE_BACKEND) {
        const e = before.elapsed + 1
        const q = Math.floor(e / CYCLE)
        if (q >= QUESTION_COUNT) {
          finish()
          return
        }
        setQIndex(q)
        setPhase(e % CYCLE < SPEAK_SEC ? 'speaking' : 'listening')
      }
    }, 1000)

    // Mock amplitude so the waveform and avatar rings are alive before the
    // backend exists. With the backend on, real analyser peaks replace this.
    let raf = 0
    const loop = () => {
      const st = useInterviewStore.getState()
      if (USE_BACKEND && session.current) {
        levels.current = session.current.levels()
      } else if (st.paused) {
        levels.current = { input: 0, output: 0 }
      } else {
        const t = performance.now() / 1000
        const wobble = (0.55 + 0.45 * Math.sin(t * 7.3)) * (0.7 + 0.3 * Math.sin(t * 2.1))
        levels.current =
          st.phase === 'speaking' ? { input: 0, output: wobble } : { input: wobble, output: 0 }
      }
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
  }, [cardId, finish, reset, setConnection, setPhase, setQIndex, setResumeToken, tick])

  const setPaused = useCallback((paused: boolean) => {
    session.current?.setPaused(paused)
  }, [])

  const end = useCallback(() => {
    session.current?.stop()
    finish()
  }, [finish])

  return { levels, setPaused, end }
}
