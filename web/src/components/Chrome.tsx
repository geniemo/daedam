import { Link, Outlet, useLocation } from 'react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getMe, logout } from '@/api/auth'
import { getCredits } from '@/api/credits'

/**
 * 공통 헤더 (README §공통 헤더).
 * 면접 진행 · 분석 중 · 질문 재생성 화면에서는 숨깁니다.
 */
const HIDDEN_ON = ['/interview', '/analyzing', '/regen']

export function Chrome() {
  const { pathname } = useLocation()
  const hidden = HIDDEN_ON.some((p) => pathname.startsWith(p))
  const queryClient = useQueryClient()
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: getMe, retry: false })
  const { data: credits } = useQuery({ queryKey: ['credits'], queryFn: getCredits })
  const name = me?.name || '지원자'

  return (
    <>
      {!hidden && (
        <header
          className="sticky top-0 z-40 h-16 border-b border-line"
          style={{ background: 'rgba(244,245,247,.92)', backdropFilter: 'blur(8px)' }}
        >
          <div className="mx-auto flex h-full max-w-(--container-home) items-center gap-8 px-8">
            <Link to="/" className="flex items-center gap-[9px]">
              <span className="flex h-[22px] w-[22px] items-center justify-center border-[1.5px] border-ink">
                <span className="h-[8px] w-[8px] bg-accent" />
              </span>
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
                <span className="mr-[4px] rounded-full border border-accent-line bg-accent-bg px-[10px] py-[4px] text-[12px] text-accent">
                  크레딧 <span className="num font-semibold">{credits.balance}</span>
                </span>
              )}
              <span className="text-[13px] text-muted">{name}</span>
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
              {/* 로그인 없이 도는 서버(개발)에서는 나갈 곳이 없으므로 숨긴다. */}
              {me && me.provider !== 'local' && (
                <button
                  onClick={async () => {
                    await logout()
                    // 캐시를 비워야 랜딩으로 돌아간다 — 새로고침 없이.
                    await queryClient.invalidateQueries()
                  }}
                  className="ml-[2px] text-[12.5px] text-faint"
                >
                  로그아웃
                </button>
              )}
            </div>
          </div>
        </header>
      )}
      <Outlet />
    </>
  )
}
