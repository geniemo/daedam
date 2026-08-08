import { create } from 'zustand'

/**
 * Interview session state (README §8).
 *
 * `phase` is driven by the agent, not by a timer, once the Live session is
 * wired: 'speaking' while the model streams audio, 'listening' after
 * generationComplete / on VAD activityStart.
 *
 * `connection` exists because a 15–20분 면접 outlives every relevant limit:
 *   - Live API audio-only 세션: 15분 (contextWindowCompression 없이)
 *   - Live API 커넥션 수명: ~10분
 *   - Cloud Run 요청 타임아웃: 기본 5분 (--timeout=3600 필수)
 * so reconnect-with-resumption is a normal path, not an error path.
 * README §"아직 정하지 않은 것 — 면접 중단 복구"가 여기에 해당합니다.
 */
export type Phase = 'speaking' | 'listening'
export type Connection = 'idle' | 'connecting' | 'live' | 'reconnecting' | 'ended'

export const TOTAL_SECONDS = 900 // §타이머와 인터벌 — 900초에서 카운트다운
export const QUESTION_COUNT = 8

interface InterviewState {
  connection: Connection
  phase: Phase
  qIndex: number
  elapsed: number
  paused: boolean
  /** 서버가 내려주는 세션 재개 토큰 (유효 2시간). 재연결 시 그대로 돌려보냅니다. */
  resumeToken: string | null

  setConnection: (c: Connection) => void
  setPhase: (p: Phase) => void
  setQIndex: (i: number) => void
  setResumeToken: (t: string | null) => void
  tick: () => void
  togglePause: () => void
  reset: () => void
}

const initial = {
  connection: 'idle' as Connection,
  phase: 'speaking' as Phase,
  qIndex: 0,
  elapsed: 0,
  paused: false,
  resumeToken: null,
}

export const useInterviewStore = create<InterviewState>((set) => ({
  ...initial,

  setConnection: (connection) => set({ connection }),
  setPhase: (phase) => set({ phase }),
  setQIndex: (qIndex) => set({ qIndex }),
  setResumeToken: (resumeToken) => set({ resumeToken }),

  // 일시정지 중에는 면접 타이머가 진행되지 않습니다 (§타이머와 인터벌)
  tick: () => set((s) => (s.paused ? s : { elapsed: s.elapsed + 1 })),

  togglePause: () => set((s) => ({ paused: !s.paused })),
  reset: () => set(initial),
}))

export const remainingSeconds = (elapsed: number) => Math.max(0, TOTAL_SECONDS - elapsed)

export const formatClock = (sec: number) =>
  `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`
