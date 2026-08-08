import { createBrowserRouter, RouterProvider } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Chrome } from '@/components/Chrome'
import { Home } from '@/screens/Home'
import { Register } from '@/screens/Register'
import { Research } from '@/screens/Research'
import { Ready } from '@/screens/Ready'
import { Review } from '@/screens/Review'
import { Regen, Analyzing } from '@/screens/Progress'
import { Interview } from '@/screens/Interview'
import { Report } from '@/screens/Report'

// README §Screens: "전체 9개 화면이며, 단일 페이지 안에서 screen state로
// 전환됩니다. 실제 구현에서는 라우트로 분리하는 것을 권합니다."
const router = createBrowserRouter([
  {
    element: <Chrome />,
    children: [
      { path: '/', element: <Home /> },
      { path: '/register/:step', element: <Register /> },
      { path: '/research', element: <Research /> },
      { path: '/ready', element: <Ready /> },
      { path: '/review', element: <Review /> },
      { path: '/regen', element: <Regen /> },
      { path: '/interview', element: <Interview /> },
      { path: '/analyzing', element: <Analyzing /> },
      { path: '/report', element: <Report /> },
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
