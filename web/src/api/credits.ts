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

/** 쿠폰이 안 될 때 서버가 400과 함께 주는 것. */
export interface CouponRejected {
  /** not_found · expired · exhausted · already_used */
  reason: string
  /** 화면에 그대로 쓰는 한국어 문구. 서버가 만든다. */
  message: string
}

export class CouponError extends Error {
  detail: CouponRejected

  constructor(detail: CouponRejected) {
    super(detail.message)
    this.name = 'CouponError'
    this.detail = detail
  }
}

/**
 * 쿠폰 코드를 크레딧으로 바꾼다.
 *
 * 결제(PG)가 붙기 전까지 크레딧을 늘릴 수 있는 유일한 길이다 — 국내 PG는
 * 사업자등록증이 있어야 계약된다.
 */
export async function redeemCoupon(
  code: string,
): Promise<{ granted: number; balance: number }> {
  const res = await fetch('/api/credits/redeem', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  })
  if (res.status === 400) {
    const body = (await res.json()) as { detail: CouponRejected }
    throw new CouponError(body.detail)
  }
  if (!res.ok) throw new Error(`충전 실패: ${res.status}`)
  return (await res.json()) as { granted: number; balance: number }
}
