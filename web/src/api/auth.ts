/** 로그인. 계약: server/daedam/server/auth.py */

export interface Me {
  id: string
  name: string
  email: string | null
  avatarUrl: string | null
  /** kakao · google, 또는 로그인 없이 도는 개발 모드의 local. */
  provider: string
  /** 온보딩(이름 입력 + 약관·개인정보 동의)을 마쳤는가. false면 화면이 온보딩으로 보낸다. */
  onboarded: boolean
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

/**
 * 회원 탈퇴. 되돌릴 수 없다.
 *
 * 계정과 함께 준비 데이터·면접 기록·크레딧이 지워지고 녹음 파일도 삭제된다.
 */
export async function withdraw(): Promise<void> {
  const res = await fetch('/api/auth/me', { method: 'DELETE' })
  if (!res.ok) throw new Error(`탈퇴 실패: ${res.status}`)
}

/**
 * 온보딩 제출 — 이름 확정 + 약관·개인정보 동의.
 *
 * 소셜 프로필 이름은 못 믿는다(카카오는 닉네임, 구글은 로마자일 수 있다).
 * 여기서 받은 이름이 면접관 호칭과 전사 어휘 힌트로 나간다.
 */
export async function completeOnboarding(name: string): Promise<Me> {
  const res = await fetch('/api/auth/onboard', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  if (!res.ok) {
    const detail = (await res.json().catch(() => null)) as { detail?: string } | null
    throw new Error(detail?.detail || `온보딩 실패: ${res.status}`)
  }
  return (await res.json()) as Me
}
