import { Link, Outlet, useLocation } from 'react-router'

/**
 * 공통 헤더 (README §공통 헤더).
 * 면접 진행 · 분석 중 · 질문 재생성 화면에서는 숨깁니다.
 */
const HIDDEN_ON = ['/interview', '/analyzing', '/regen']

export function Chrome() {
  const { pathname } = useLocation()
  const hidden = HIDDEN_ON.some((p) => pathname.startsWith(p))

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
              <span className="text-[13px] text-muted">김서연</span>
              <span className="flex h-[30px] w-[30px] items-center justify-center rounded-full border border-field bg-surface text-[12px] font-semibold text-muted">
                서
              </span>
            </div>
          </div>
        </header>
      )}
      <Outlet />
    </>
  )
}
