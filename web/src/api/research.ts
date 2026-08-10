// 리서치 API 클라이언트. 서버 계약: server/daedam/server/research_routes.py
// dev에서는 vite 프록시(/api → :8000), 배포에서는 같은 오리진.

import type { ApplicationPart, DocSection, UncertainRef } from '@/data/types'

export interface ResearchStatus {
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
export async function startResearch(
  company: string,
  role: string,
  parts: ApplicationPart[],
): Promise<string> {
  const res = await fetch('/api/research', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ company, role, application: toServerParts(parts) }),
  })
  if (!res.ok) throw new Error(`리서치 시작 실패: ${res.status}`)
  const data = (await res.json()) as { task_id: string }
  return data.task_id
}

/** §서버 연동 2 — 진행률 폴링. 완료되면 report·uncertain이 실려 온다. */
export async function getResearchStatus(taskId: string): Promise<ResearchStatus> {
  const res = await fetch(`/api/research/${taskId}`)
  if (!res.ok) throw new Error(`리서치 조회 실패: ${res.status}`)
  return (await res.json()) as ResearchStatus
}
