/** 로그인. 계약: server/daedam/server/auth.py */

export interface Me {
  id: string
  name: string
  email: string | null
  avatarUrl: string | null
  /** kakao · google, 또는 로그인 없이 도는 개발 모드의 local. */
  provider: string
}

/**
 * 지금 로그인한 사용자. 안 했으면 null — 화면이 랜딩을 그린다.
 *
 * 401이 아니라 null인 이유: 로그인하지 않은 것은 오류가 아니라 정상 상태다.
 * 서버에 로그인 설정이 없으면(개발) 기본 사용자가 돌아온다.
 */
export async function getMe(): Promise<Me | null> {
  const res = await fetch('/api/auth/me')
  if (!res.ok) return null
  return (await res.json()) as Me | null
}

/** 화면이 그릴 로그인 버튼 목록. 비어 있으면 서버가 로그인을 요구하지 않는다. */
export async function getProviders(): Promise<string[]> {
  const res = await fetch('/api/auth/providers')
  if (!res.ok) return []
  return ((await res.json()) as { providers: string[] }).providers
}

/** 제공자로 보낸다. SPA 밖으로 나갔다 콜백으로 돌아온다. */
export const loginUrl = (provider: string) => `/api/auth/${provider}/login`

export async function logout(): Promise<void> {
  await fetch('/api/auth/logout', { method: 'POST' })
}
