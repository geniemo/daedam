// 리서치 API 클라이언트. 서버 계약: server/daedam/server/preparation_routes.py
// dev에서는 vite 프록시(/api → :8000), 배포에서는 같은 오리진.

import type { ApplicationPart, DocSection, UncertainRef } from '@/data/types'

export interface PreparationStatus {
  status: 'running' | 'done' | 'failed'
  pct: number
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
): Promise<string> {
  const res = await fetch('/api/preparation', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ company, role, application: toServerParts(parts) }),
  })
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

/** 서버가 들고 있는 면접 하나. 계약: server/daedam/server/interview_routes.py */
export interface StoredInterview {
  id: string
  company: string
  role: string
  /** 질문 풀까지 준비돼 면접을 시작할 수 있는지. 브리지의 시작 조건과 같다. */
  ready: boolean
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
