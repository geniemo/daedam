// Shapes mirror README §State Management. When the ADK backend lands, these
// stay put — only `src/data/mock.ts` gets replaced by API calls.

export type CardStatus = 'ready' | 'researching' | 'done'

export interface Card {
  id: string
  company: string
  role: string
  date: string
  status: CardStatus
  pct?: number
  score?: number
  /** 지금까지 마친 면접 수. 같은 준비 데이터로 몇 번이든 볼 수 있다. */
  interviewCount?: number
}

export interface ApplicationItem {
  title: string
  body: string
  len: string
}

export interface ApplicationPart {
  name: string
  items: ApplicationItem[]
}

export type StageIndex = 0 | 1 | 2 | 3

export interface Question {
  /** stage index — 0 자기소개 / 1 직무역량 / 2 인성·컬처핏 / 3 마무리 */
  s: StageIndex
  q: string
  short: string
}

export interface CompanyContext {
  product: string
  news: string
}


/* ── Research report document (§6 리포트 검토) ───────────────── */

export interface DocParagraph {
  type: 'p' | 'li'
  text: string
}
/**
 * 표. 열 수는 리포트마다 다르므로 고정하지 않는다 — 회사가 바뀌면 Deep
 * Research가 내는 표의 모양도 바뀐다. `rows[i]`의 길이는 `head`와 같다
 * (서버 파서가 짧은 행을 빈 칸으로 채운다).
 */
export interface DocTable {
  type: 'table'
  head: string[]
  rows: string[][]
}
export interface DocRefs {
  type: 'refs'
  refs: { n: string; label: string }[]
}
export type DocBlock = DocParagraph | DocTable | DocRefs

export interface DocSection {
  title: string
  blocks: DocBlock[]
}

/** 확인이 필요한 대목 — 서버가 신뢰도 낮은 블록에 내려주는 플래그 (§서버 연동 3) */
export interface UncertainRef {
  si: number
  bi: number
  title: string
  reason: string
}

/* ── Feedback report (§10) ──────────────────────────────────── */

export interface AnswerFeedback {
  score: number
  dur: string
  filler: number
  transcript: string
  coach: string
  tags: string[]
}

export interface StageScore {
  name: string
  score: number
  note: string
}

export interface VoiceMetric {
  label: string
  value: string
  unit: string
  /** gauge fill, 0–100 */
  w: number
  tone: 'positive' | 'accent'
  verdict: string
  range: string
}

/** Stable id for a document block — annotations hang off this (§서버 연동 3). */
export const blockId = (si: number, bi: number) => `blk-${si}-${bi}`
