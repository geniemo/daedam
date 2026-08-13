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

/** 프로토타입 기본 길이. 백엔드가 붙으면 접속 직후 session 메시지가 덮어씁니다. */
export const TOTAL_SECONDS = 900 // §타이머와 인터벌 — 900초에서 카운트다운
export const QUESTION_COUNT = 8 // 프로토타입 대본의 질문 수

/**
 * 서버가 접속 직후 내려주는 진행 상태 (/ws/interview의 session 메시지).
 *
 * 남은 시간·단계·질문 번호의 출처는 서버 하나입니다. 프론트가 자기 시계로
 * 세면 재접속하거나 서버가 시간 때문에 단계를 건너뛸 때 화면이 어긋납니다.
 */
export interface SessionInfo {
  totalSeconds: number
  elapsedSeconds: number
  /** 단계별 시간 예산(초). 진행 바 칸의 너비이자 채움 기준입니다. */
  stageBudgets: number[]
  stage: number
  asked: number
}

interface InterviewState {
  connection: Connection
  phase: Phase
  /** 지금까지 나간 뼈대질문 수. 화면의 "질문 N"입니다. */
  askedCount: number
  stage: number
  /** 면접관이 실제로 하고 있는 말. 조각으로 와서 이어 붙입니다. */
  caption: string
  /** 직전 조각이 턴의 끝이었는지 — 다음 조각에서 자막을 새로 시작합니다. */
  captionDone: boolean
  elapsed: number
  totalSeconds: number
  stageBudgets: number[] | null
  paused: boolean
  /** 서버가 내려주는 세션 재개 토큰 (유효 2시간). 재연결 시 그대로 돌려보냅니다. */
  resumeToken: string | null

  setConnection: (c: Connection) => void
  setPhase: (p: Phase) => void
  setQuestion: (index: number, stage: number) => void
  appendCaption: (text: string, final: boolean) => void
  applySession: (info: SessionInfo) => void
  setResumeToken: (t: string | null) => void
  tick: () => void
  togglePause: () => void
  reset: () => void
}

const initial = {
  connection: 'idle' as Connection,
  phase: 'speaking' as Phase,
  askedCount: 0,
  stage: 0,
  caption: '',
  captionDone: true,
  elapsed: 0,
  totalSeconds: TOTAL_SECONDS,
  stageBudgets: null,
  paused: false,
  resumeToken: null,
}

export const useInterviewStore = create<InterviewState>((set) => ({
  ...initial,

  setConnection: (connection) => set({ connection }),
  setPhase: (phase) => set({ phase }),
  setQuestion: (index, stage) => set({ askedCount: index + 1, stage }),

  // 전사는 조각으로 흘러오고, 턴이 끝나면 누적 전문이 한 번 더 옵니다
  // (ADK gemini_llm_connection.py — 조각은 finished=false, 마지막은 그때까지
  // 모은 전체 텍스트에 finished=true). 그래서 마지막 것은 이어 붙이지 않고
  // 갈아끼웁니다. 붙이면 같은 말이 두 번 보입니다.
  //
  // 턴이 끝나도 자막을 지우지는 않습니다 — 지원자가 답하는 동안에도 방금
  // 받은 질문을 읽을 수 있어야 합니다. 다음 턴의 첫 조각이 밀어냅니다.
  appendCaption: (text, final) =>
    set((s) => ({
      caption: final ? text || s.caption : (s.captionDone ? '' : s.caption) + text,
      captionDone: final,
    })),

  applySession: (info) =>
    set({
      totalSeconds: info.totalSeconds,
      elapsed: info.elapsedSeconds,
      stageBudgets: info.stageBudgets,
      stage: info.stage,
      askedCount: info.asked,
    }),

  setResumeToken: (resumeToken) => set({ resumeToken }),

  // 일시정지 중에는 면접 타이머가 진행되지 않습니다 (§타이머와 인터벌)
  tick: () => set((s) => (s.paused ? s : { elapsed: s.elapsed + 1 })),

  togglePause: () => set((s) => ({ paused: !s.paused })),
  reset: () => set(initial),
}))

export const remainingSeconds = (elapsed: number, total: number) => Math.max(0, total - elapsed)

/**
 * 경과 시간이 속한 단계. 서버 `SessionFlow.stage_index_at`과 같은 계산입니다.
 *
 * 화면의 단계 표시와 진행 바가 같은 근거를 쓰게 하려고 여기서도 셉니다.
 * 질문이 배달될 때만 갱신하면, 면접관이 꼬리질문을 길게 끄는 동안 라벨은
 * 멈춰 있고 바만 움직여 둘이 어긋납니다.
 */
export function stageAt(elapsed: number, budgets: number[]): number {
  let bound = 0
  for (let i = 0; i < budgets.length; i++) {
    bound += budgets[i]
    if (elapsed < bound) return i
  }
  return budgets.length - 1
}

export const formatClock = (sec: number) =>
  `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`
