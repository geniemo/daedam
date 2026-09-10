import { Link, Outlet, useLocation } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { getMe } from '@/api/auth'
import { getCredits } from '@/api/credits'
import { Symbol } from '@/components/Logo'

/**
 * 공통 헤더 (README §공통 헤더).
 * 면접 진행 · 분석 중 · 질문 재생성 화면에서는 숨깁니다.
 */
const HIDDEN_ON = ['/interview', '/analyzing', '/regen']

export function Chrome() {
  const { pathname } = useLocation()
  const hidden = HIDDEN_ON.some((p) => pathname.startsWith(p))
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: getMe, retry: false })
  const { data: credits } = useQuery({ queryKey: ['credits'], queryFn: getCredits })
  const name = me?.name || '지원자'

  return (
    <>
      {!hidden && (
        <header
          className="sticky top-0 z-40 h-16 border-b border-line"
          style={{ background: 'var(--header-bg)', backdropFilter: 'blur(8px)' }}
        >
          {/* 좁은 화면은 여백 16, 이름 글자를 숨기고 아바타만 남긴다. */}
          <div className="mx-auto flex h-full max-w-(--container-home) items-center gap-4 px-4 md:gap-8 md:px-8">
            <Link to="/" className="flex items-center gap-[9px]">
              <Symbol size={22} />
              <span className="text-[17px] font-bold tracking-[-.02em] text-ink">대담</span>
            </Link>
            <nav>
              <Link to="/" className="text-[14px] font-semibold text-ink">
                내 면접
              </Link>
            </nav>
            <div className="flex-1" />
            <div className="flex items-center gap-[10px]">
              {/* 남은 횟수는 다음 행동을 정하는 정보라 늘 보인다. */}
              {credits && (
                <Link
                  to="/credits"
                  className="mr-[4px] rounded-full border border-accent-line bg-accent-bg px-[10px] py-[4px] text-[12px] text-accent"
                >
                  크레딧 <span className="num font-semibold">{credits.balance}</span>
                </Link>
              )}
              <Link to="/account" className="hidden text-[13px] text-muted md:inline">
                {name}
              </Link>
              {/* 로그아웃은 [내 정보] 안으로 옮겼다 — 헤더에 두면 로그인·탈퇴·
                  프로필이 두 곳에 흩어진다. */}
              <Link to="/account">
                {me?.avatarUrl ? (
                  <img
                    src={me.avatarUrl}
                    alt=""
                    className="h-[30px] w-[30px] rounded-full border border-field object-cover"
                  />
                ) : (
                  <span className="flex h-[30px] w-[30px] items-center justify-center rounded-full border border-field bg-surface text-[12px] font-semibold text-muted">
                    {name.slice(-2, -1)}
                  </span>
                )}
              </Link>
            </div>
          </div>
        </header>
      )}
      <Outlet />
    </>
  )
}
