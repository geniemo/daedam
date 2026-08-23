/** 크레딧. 계약: server/daedam/server/credit_routes.py */

export interface CreditEvent {
  delta: number
  reason: string
  /** 화면에 그대로 쓰는 한국어 문구. 서버가 만든다. */
  label: string
  at: string
}

export interface CreditState {
  balance: number
  /** 무엇이 몇 크레딧인지. 화면이 자기 숫자를 들면 서버와 어긋난다. */
  costs: { research: number; interview: number }
  history: CreditEvent[]
}

export async function getCredits(): Promise<CreditState | null> {
  const res = await fetch('/api/credits')
  if (!res.ok) return null
  return (await res.json()) as CreditState
}

/** 크레딧이 모자라 막혔을 때 서버가 402와 함께 주는 것. */
export interface Insufficient {
  message: string
  needed: number
  balance: number
}
