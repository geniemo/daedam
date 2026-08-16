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
