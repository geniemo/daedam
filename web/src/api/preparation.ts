// 리서치 API 클라이언트. 서버 계약: server/daedam/server/preparation_routes.py
// dev에서는 vite 프록시(/api → :8000), 배포에서는 같은 오리진.

import type { Insufficient } from '@/api/credits'
import type { ApplicationPart, DocSection, UncertainRef } from '@/data/types'

/**
 * 크레딧이 모자라 등록이 막혔다.
 *
 * 일반 실패와 갈라 두는 이유: 화면이 "다시 시도"가 아니라 "충전"을 안내해야
 * 하고, 재시도해 봐야 같은 결과다.
 */
export class InsufficientCreditsError extends Error {
  detail: Insufficient

  constructor(detail: Insufficient) {
    super(detail.message)
    this.name = 'InsufficientCreditsError'
    this.detail = detail
  }
}

export interface PreparationStatus {
  status: 'running' | 'done' | 'failed'
  /**
   * 0~100. **null일 수 있다.** Deep Research는 진행률을 주지 않으므로 live에서는
   * 서버도 모른다. 그때 화면은 막대 대신 단계와 경과 시간을 보여준다.
   */
  pct: number | null
  /** 리서치가 지금까지 실제로 한 조사. 오래된 것부터. 없으면 빈 배열. */
  activity?: string[]
  /** 관측된 현재 단계 — 스텝 종류에서 나온다. */
  phase?: string
  /** 시작 후 경과 초. */
  elapsedS?: number
  report?: DocSection[]
  uncertain?: UncertainRef[]
}

/** 스토어의 파트 구조(name)를 서버 형태(part)로 바꾼다. `len`은 화면 전용이라 버린다. */
const toServerParts = (parts: ApplicationPart[]) =>
  parts.map((part) => ({
    part: part.name,
    items: part.items.map(({ title, body }) => ({ title, body })),
  }))

/** §서버 연동 1 — 회사 등록 + 리서치 시작. task_id를 돌려준다. */
export async function startPreparation(
  company: string,
  role: string,
  parts: ApplicationPart[],
  /** 채용공고 링크 또는 본문. 서버가 파싱 없이 리서치 프롬프트에 그대로 싣는다. */
  posting = '',
  /** 지원자 이름. 면접관이 부르고 전사 어휘 힌트로도 나간다. */
  name = '',
): Promise<string> {
  const res = await fetch('/api/preparation', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      company,
      role,
      application: toServerParts(parts),
      posting,
      name,
    }),
  })
  if (res.status === 402) {
    const body = (await res.json()) as { detail: Insufficient }
    throw new InsufficientCreditsError(body.detail)
  }
  if (!res.ok) throw new Error(`리서치 시작 실패: ${res.status}`)
  const data = (await res.json()) as { task_id: string }
  return data.task_id
}

/** §서버 연동 2 — 진행률 폴링. 완료되면 report·uncertain이 실려 온다. */
export async function getPreparationStatus(taskId: string): Promise<PreparationStatus> {
  const res = await fetch(`/api/preparation/${taskId}`)
  if (!res.ok) throw new Error(`리서치 조회 실패: ${res.status}`)
  return (await res.json()) as PreparationStatus
}

/** 면접이 끝난 뒤 만들어진 피드백. 계약: server/daedam/server/evaluation.py */
export interface Feedback {
  durationS: number
  utterances: { speaker: 'interviewer' | 'applicant'; text: string; at: number }[]
  /** 녹음이 없으면 통째로 빠진다 — 지표는 소리가 있어야 낼 수 있다. */
  voice?: {
    syllablesPerMinute: number
    meanAnswerS: number
    /** 멈춘 시간을 뺀 실제 발화 시간(초). 분당 지표의 분모. */
    spokenS: number
    pauseRatio: number
    loudness: number
    loudnessVariation: number
    /** 질문이 끝나고 답을 시작하기까지의 평균 초. 잴 수 없으면 null. */
    meanStartDelayS: number | null
    answers: {
      startS: number
      endS: number
      text: string
      pauses: number
      startDelayS: number | null
    }[]
  }
  /**
   * 시선. 판독(expression)이 있으면 그 시선 방향에서 오고 — 지원자 기준
   * 좌우라 홍채 기하의 뒤집힘이 없습니다 — 판독 없는 지난 판만 홍채
   * 기록(eval/gaze.py)에서 옵니다.
   */
  gaze?: GazeReport
  /**
   * 표정 — 스냅샷을 VLM이 면접관의 눈으로 읽은 것. 카메라를 켠 경우에만
   * 오고, 판독이 실패하면 빠집니다. 계약: server/daedam/eval/expression.py
   */
  expression?: ExpressionReport
  coaching: {
    /** 답변 점수의 평균. 평가할 답변이 없으면 null — 0점과 다르다. */
    score: number | null
    /** 말버릇으로 쓴 낱말의 총 개수. 목록이 아니라 문맥으로 센다. */
    fillers: number
    summary: string
    strengths: string[]
    improvements: string[]
    answers: {
      question: string
      score: number
      strength: string
      gap: string
      suggestion: string
      /** 이 답변에서 말버릇으로 쓴 낱말. 나온 순서대로. */
      fillers: string[]
    }[]
  }
}

export interface GazeReport {
  /** 얼굴이 보인 초 수. 적으면 나머지 비율을 믿을 수 없습니다. */
  seconds: number
  /** 3×3 칸마다 머문 비율. 합이 1이고 4번이 정면입니다. */
  cells: number[]
  /** 정면에 머문 비율. */
  steady: number
  /** 답변마다 같은 모양으로 하나씩. 음성 지표의 답변과 순서가 같습니다. */
  answers: Omit<GazeReport, 'answers'>[]
}

export interface ExpressionReport {
  /** 판독에 쓰인 스냅샷 수. 적으면 아래 비율을 믿을 수 없습니다. */
  frames: number
  /** 인상 키 → 비율(합 1). 키는 video/expression.ts의 IMPRESSIONS와 같습니다. */
  impressions: Record<string, number>
  /**
   * 시간 순서를 담은 인상 띠(48칸). 비율만으로는 "언제" 그랬는지가 사라집니다 —
   * 긴장 20%가 첫 답변에 몰렸는지 내내 흩어져 있었는지는 다른 이야기입니다.
   */
  series?: string[]
  /**
   * 프레임을 통틀어 판독이 짚은 잘한 점·고칠 점. 화면이 직접 그리지는
   * 않습니다 — 서버가 종합 평가의 두 목록에 합쳐 보냅니다(evaluation.py).
   */
  strengths?: string[]
  observations: string[]
  /** 답변마다 하나씩. 음성 지표의 답변과 순서가 같습니다. */
  answers: { frames: number; impressions: Record<string, number> }[]
}

export interface FeedbackStatus {
  /**
   * running 만드는 중 · done 완료 · failed 실패 · silent 면접은 했는데 한 마디도
   * 남기지 않아 만들 것이 없음 · absent 아직 면접 안 함.
   *
   * silent와 absent를 가르는 것이 요점이다. 둘 다 "피드백이 없다"지만 화면이 할
   * 말이 정반대다 — 방금 면접을 마친 사람에게 "아직 면접을 진행하지 않았습니다"는
   * 거짓말이다.
   */
  status: 'running' | 'done' | 'failed' | 'silent' | 'absent'
  /** 어느 판의 피드백인가. absent면 없다. */
  sessionId?: string
  /** silent일 때만 온다. 이 판의 크레딧을 되돌린 기록이 원장에 있는가. */
  refunded?: boolean
  /** 웹캠 녹화가 남아 있는가. 있으면 답변마다 영상으로 되감아 볼 수 있다. */
  hasVideo?: boolean
  /**
   * 녹화가 시작된 시점의 면접 경과 초.
   *
   * 답변 구간은 서버가 받은 오디오로 센 시각이고 영상의 0초는 녹화가 시작된
   * 순간이라 원점이 다르다. 영상에서 답변 위치 = `startS - videoStartS`.
   */
  videoStartS?: number
  feedback?: Feedback
}

/**
 * §서버 연동 6 — 면접 한 판의 피드백. 분석 화면이 기다리며 부르고 리포트가 읽는다.
 *
 * 같은 면접을 여러 번 볼 수 있으므로 어느 판인지 고른다. 생략하면 가장 최근
 * 판이다 — 면접을 막 마친 화면이 원하는 것이 그것이다.
 */
export async function getFeedback(
  interviewId: string,
  sessionId?: string,
): Promise<FeedbackStatus> {
  const query = sessionId ? `?session=${encodeURIComponent(sessionId)}` : ''
  const res = await fetch(`/api/interviews/${interviewId}/feedback${query}`)
  if (!res.ok) throw new Error(`피드백 조회 실패: ${res.status}`)
  return (await res.json()) as FeedbackStatus
}

/** 웹캠 녹화 주소. 오디오와 같은 규칙으로 구간만 받아 온다. */
export const videoUrl = (interviewId: string, sessionId?: string) =>
  `/api/interviews/${interviewId}/video${
    sessionId ? `?session=${encodeURIComponent(sessionId)}` : ''
  }`

/** 녹음 파일 주소. Range 요청을 받으므로 구간만 가져간다. */
export const audioUrl = (interviewId: string, sessionId?: string) =>
  `/api/interviews/${interviewId}/audio${
    sessionId ? `?session=${encodeURIComponent(sessionId)}` : ''
  }`

/**
 * 면접 한 회차. 계약: server/daedam/server/interview_routes.py
 *
 * 답변이 하나도 없는 면접은 이 목록에 오지 않는다 — 서버가 뺀다. 회차 번호를
 * 이 목록의 길이로 매기므로, 오면 한 적 없는 회차가 생긴다.
 */
export interface InterviewSession {
  id: string
  /** ISO 8601. 이력 목록의 날짜 표시에 쓴다. */
  startedAt: string
  endedAt: string | null
  score: number | null
  /** 피드백이 만들어졌는가. 없으면 아직 분석 중이거나 실패한 것이다. */
  hasFeedback: boolean
}

/** 면접 이력 — 최근 판이 앞에 온다. */
export async function listSessions(id: string): Promise<InterviewSession[]> {
  const res = await fetch(`/api/interviews/${id}/sessions`)
  if (!res.ok) throw new Error(`면접 이력 조회 실패: ${res.status}`)
  return (await res.json()) as InterviewSession[]
}

/** 서버가 들고 있는 면접 하나. 계약: server/daedam/server/interview_routes.py */
export interface StoredInterview {
  id: string
  company: string
  role: string
  /** 질문 풀까지 준비돼 면접을 시작할 수 있는지. 브리지의 시작 조건과 같다. */
  ready: boolean
  /**
   * 가장 최근 면접의 점수. **null인 이유가 둘이다** — 아직 분석 전이거나,
   * 분석은 끝났는데 채점할 답변이 없었거나. 둘을 가르는 것이 `analyzed`다.
   */
  score: number | null
  /** 가장 최근 면접의 분석이 끝났는가. 끝났는데 점수가 없으면 답변이 없던 것이다. */
  analyzed: boolean
  /** 지금까지 마친 면접 수. 0이면 아직 한 번도 안 본 면접이다. */
  interviewCount: number
  /** 마지막 저장 시각(epoch 초). 목록 정렬과 화면의 날짜 표시에 쓴다. */
  savedAt: number
}

/** 홈 목록 — 저장소에 있는 면접. 프론트 메모리가 아니라 파일이 진실이다. */
export async function listInterviews(): Promise<StoredInterview[]> {
  const res = await fetch('/api/interviews')
  if (!res.ok) throw new Error(`면접 목록 조회 실패: ${res.status}`)
  return (await res.json()) as StoredInterview[]
}

export interface InterviewDetail extends StoredInterview {
  report: DocSection[]
  uncertain: UncertainRef[]
  sessions: InterviewSession[]
}

/** 검토 화면이 읽을 면접 하나 — 리포트 원문까지. */
export async function getInterview(id: string): Promise<InterviewDetail> {
  const res = await fetch(`/api/interviews/${id}`)
  if (!res.ok) throw new Error(`면접 조회 실패: ${res.status}`)
  return (await res.json()) as InterviewDetail
}

/**
 * 검토로 고친 리포트를 저장하고 질문을 다시 뽑게 한다.
 *
 * 질문은 리포트를 근거로 만들어졌으므로, 사실을 고치면 그 질문은 낡은 근거
 * 위에 서 있다. 저장과 재생성이 한 요청인 이유가 그것이다.
 */
export async function saveReport(id: string, report: DocSection[]): Promise<void> {
  const res = await fetch(`/api/interviews/${id}/report`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ report }),
  })
  if (!res.ok) throw new Error(`리포트 저장 실패: ${res.status}`)
}
