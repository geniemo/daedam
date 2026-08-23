import type { ReactNode } from 'react'
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useQuery } from '@tanstack/react-query'
import { getMe } from '@/api/auth'
import { Chrome } from '@/components/Chrome'
import { useActiveCard } from '@/store/app'
import { Home } from '@/screens/Home'
import { Landing } from '@/screens/Landing'
import { Register } from '@/screens/Register'
import { Research } from '@/screens/Research'
import { Ready } from '@/screens/Ready'
import { Review } from '@/screens/Review'
import { Regen, Analyzing } from '@/screens/Progress'
import { Interview } from '@/screens/Interview'
import { Report } from '@/screens/Report'

/**
 * 로그인한 사람만 앱을 본다.
 *
 * 로그인하지 않은 것은 오류가 아니라 정상 상태다 — 그때는 랜딩을 그린다.
 * 서버에 로그인 설정이 없으면(개발) 기본 사용자가 돌아와 그냥 통과한다.
 *
 * 확인되기 전에는 아무것도 그리지 않는다. 랜딩을 먼저 띄웠다가 홈으로
 * 바뀌면 로그인한 사람이 매번 로그인 화면을 스치게 된다.
 */
function RequireLogin() {
  const { data: me, isPending } = useQuery({ queryKey: ['me'], queryFn: getMe, retry: false })
  if (isPending) return null
  return me ? <Chrome /> : <Landing />
}

/**
 * 활성 카드가 있어야 열리는 화면을 감싼다.
 *
 * 홈 목록은 서버 파일에서 오므로 비어 있을 수 있다(등록된 면접이 하나도 없는
 * 경우). 그때 이 화면들은 `card.company` 같은 걸 그냥 읽어서 흰 화면이 된다.
 * 없는 카드를 지어내 보여주느니 홈으로 돌려보낸다.
 */
function RequireCard({ children }: { children: ReactNode }) {
  const card = useActiveCard()
  return card ? <>{children}</> : <Navigate to="/" replace />
}

// README §Screens: "전체 9개 화면이며, 단일 페이지 안에서 screen state로
// 전환됩니다. 실제 구현에서는 라우트로 분리하는 것을 권합니다."
const needsCard = (element: ReactNode) => <RequireCard>{element}</RequireCard>

const router = createBrowserRouter([
  {
    element: <RequireLogin />,
    children: [
      { path: '/', element: <Home /> },
      { path: '/register/:step', element: <Register /> },
      { path: '/research', element: needsCard(<Research />) },
      { path: '/ready', element: needsCard(<Ready />) },
      { path: '/review', element: needsCard(<Review />) },
      { path: '/regen', element: needsCard(<Regen />) },
      { path: '/interview', element: needsCard(<Interview />) },
      { path: '/analyzing', element: <Analyzing /> },
      { path: '/report', element: needsCard(<Report />) },
    ],
  },
])

// §서버 연동 2 (리서치 진행 폴링) · 3 (리포트 조회)이 붙을 자리.
const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false } },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
