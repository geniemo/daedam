// Render every screen through React to catch runtime errors without a browser.
// Not part of the app build — run with `node scripts/smoke.mjs`.
import { createServer } from 'vite'
import { createElement } from 'react'
import { renderToString } from 'react-dom/server'

const vite = await createServer({ server: { middlewareMode: true }, appType: 'custom' })

const load = (p) => vite.ssrLoadModule(p)
// Import directly (not via ssrLoadModule) so the router context instance is the
// same one the components get when Vite externalizes their bare import.
const { createMemoryRouter, RouterProvider } = await import('react-router')
// 앱이 App.tsx에서 감싸는 것과 같은 프로바이더. 서버에서 데이터를 읽는 화면은
// 이것 없이는 렌더 자체가 안 된다 — 하네스가 앱과 같은 껍데기를 써야 한다.
const { QueryClient, QueryClientProvider } = await import('@tanstack/react-query')

// [visited url, route pattern, module, export]. The pattern must match App.tsx —
// a static route alongside the dynamic one would out-rank it and swallow the param.
const screens = [
  ['/', '/', '/src/screens/Home.tsx', 'Home'],
  ['/register/1', '/register/:step', '/src/screens/Register.tsx', 'Register'],
  ['/register/2', '/register/:step', '/src/screens/Register.tsx', 'Register'],
  ['/research', '/research', '/src/screens/Research.tsx', 'Research'],
  ['/ready', '/ready', '/src/screens/Ready.tsx', 'Ready'],
  ['/review', '/review', '/src/screens/Review.tsx', 'Review'],
  ['/regen', '/regen', '/src/screens/Progress.tsx', 'Regen'],
  ['/interview', '/interview', '/src/screens/Interview.tsx', 'Interview'],
  ['/analyzing', '/analyzing', '/src/screens/Progress.tsx', 'Analyzing'],
  ['/report', '/report', '/src/screens/Report.tsx', 'Report'],
]

const { Chrome } = await load('/src/components/Chrome.tsx')

// 카드가 있어야 열리는 화면들은 App.tsx의 RequireCard가 지킨다. 여기서는 화면
// 컴포넌트를 직접 그리므로 그 가드를 지나지 않는다 — 라우터가 보장하는 전제를
// 하네스가 대신 세워 준다. 카드를 안 세우면 화면 본문을 한 줄도 안 그려 본다.
//
// setState가 아니라 초기 상태 객체를 채우는 이유: renderToString은 SSR이고,
// zustand는 그때 현재 상태가 아니라 생성 시점 상태를 읽는다.
//   node_modules/zustand/esm/react.mjs:9   selector(api.getInitialState())
//   node_modules/zustand/esm/vanilla.mjs:13  () => initialState  (생성 시점 클로저)
// setState는 매번 새 객체를 만들므로(vanilla.mjs Object.assign({}, state, partial))
// 이 객체를 참조하는 것은 SSR 스냅샷뿐이다 — 여기만 정확히 채운다.
const { useAppStore } = await load('/src/store/app.ts')
const { initialCards } = await load('/src/data/mock.ts')
Object.assign(useAppStore.getInitialState(), {
  cards: initialCards,
  activeCardId: initialCards[0].id,
})

let failed = 0
for (const [url, pattern, file, name] of screens) {
  try {
    const mod = await load(file)
    const Screen = mod[name]
    if (!Screen) throw new Error(`export ${name} not found in ${file}`)
    const router = createMemoryRouter(
      [{ element: createElement(Chrome), children: [{ path: pattern, element: createElement(Screen) }] }],
      { initialEntries: [url] },
    )
    const html = renderToString(
      createElement(
        QueryClientProvider,
        { client: new QueryClient({ defaultOptions: { queries: { retry: false } } }) },
        createElement(RouterProvider, { router }),
      ),
    )
    const len = html.length
    if (len < 200) throw new Error(`suspiciously short output (${len} chars)`)
    console.log(`ok    ${url.padEnd(14)} ${name.padEnd(10)} ${len} chars`)
  } catch (err) {
    failed++
    console.log(`FAIL  ${url.padEnd(14)} ${name}`)
    console.log(`      ${err.message.split('\n')[0]}`)
  }
}

await vite.close()
console.log(failed ? `\n${failed} screen(s) failed` : '\nall screens rendered')
process.exit(failed ? 1 : 0)
