// 반응형 점검 — 세 폭(390·768·1280)으로 주요 화면을 찍는다. 서버에 붙어 읽기만 한다.
//   node scripts/responsive.mjs [baseURL]
// 스크린샷은 .shots/ 아래. 어느 화면도 가로로 넘치면 실패로 센다.
import { chromium } from 'playwright'
import { mkdir, rm } from 'node:fs/promises'

const BASE = process.argv[2] ?? 'http://127.0.0.1:8000'
const OUT = '.shots'
// 로그인이 걸린 서버면 세션 쿠키 값을 파일로 준다: SESSION_COOKIE_FILE=/path
const COOKIE = process.env.SESSION_COOKIE_FILE
  ? (await import('node:fs/promises')).readFile(process.env.SESSION_COOKIE_FILE, 'utf8').then((s) => s.trim())
  : null
const WIDTHS = [
  { name: 'phone', width: 390, height: 844, scale: 2 },
  { name: 'tablet', width: 768, height: 1024, scale: 1 },
  { name: 'desktop', width: 1280, height: 800, scale: 1 },
]

await rm(OUT, { recursive: true, force: true })
await mkdir(OUT, { recursive: true })

const browser = await chromium.launch({
  args: ['--no-sandbox', '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'],
})

// 면접 화면은 소켓을 열자마자 서버가 면접을 시작한다(크레딧·Live API). 배치만
// 보려는 것이므로 소켓을 가짜로 바꿔 세션·말차례·자막만 흘려 넣는다.
const FAKE_WS = `
  class FakeSocket {
    constructor() {
      this.readyState = 1
      setTimeout(() => {
        this.onopen && this.onopen()
        const send = (m) => this.onmessage && this.onmessage({ data: JSON.stringify(m) })
        send({ type: 'session', sessionId: 'fake', elapsedSeconds: 83, asked: 3, caption: '' })
        send({ type: 'phase', value: 'speaking' })
        send({ type: 'caption', text: '지원서에 적으신 물류 데이터 분석 프로젝트에서 본인이 맡은 역할을 설명해 주세요.', final: true })
      }, 50)
    }
    send() {}
    close() {}
  }
  FakeSocket.OPEN = 1
  window.WebSocket = FakeSocket
`

let failed = 0
for (const size of WIDTHS) {
  const context = await browser.newContext({
    viewport: { width: size.width, height: size.height },
    deviceScaleFactor: size.scale,
  })
  await context.grantPermissions(['microphone', 'camera'], { origin: BASE })
  if (COOKIE) {
    const { hostname } = new URL(BASE)
    await context.addCookies([{ name: 'session', value: await COOKIE, domain: hostname, path: '/' }])
  }
  await context.addInitScript(FAKE_WS)
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push(`[pageerror] ${page.url()} ${e.message}`))

  const shot = async (name, opts = {}) => {
    const file = `${OUT}/${size.name}-${name}.png`
    await page.screenshot({ path: file, ...opts })
    const [scroll, view] = await page.evaluate(() => [
      document.documentElement.scrollWidth,
      document.documentElement.clientWidth,
    ])
    const wide = scroll > view
    if (wide) failed += 1
    console.log(`${wide ? '✗' : 'ok'} ${file}${wide ? ` — 가로 넘침 ${scroll} > ${view}` : ''}`)
  }
  // 라우터 안에서 옮긴다 — 새로 고치면 스토어(활성 카드)가 비어 홈으로 돌아간다.
  const go = async (path) => {
    await page.evaluate((p) => {
      window.history.pushState({}, '', p)
      window.dispatchEvent(new PopStateEvent('popstate'))
    }, path)
    await page.waitForTimeout(800)
  }

  console.log(`\n▸ ${size.name} ${size.width}×${size.height}`)
  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.waitForSelector('text=내 면접')
  await page.waitForTimeout(600)
  await shot('home', { fullPage: true })

  // 준비 완료 — 다음 면접 카드의 시작 버튼.
  const start = page.locator('button:has-text("면접 시작하기")').first()
  if (await start.count()) {
    await start.click()
    await page.waitForSelector('text=시작 전 확인')
    await page.locator('button:has-text("카메라 켜기")').click()
    await page.waitForTimeout(800)
    await shot('ready', { fullPage: true })

    // 면접 — 카메라를 켠 채로 라우터 안에서 옮긴다(가짜 소켓).
    await go('/interview')
    await page.waitForSelector('text=종료하고 리포트 받기')
    await page.waitForTimeout(1200)
    await shot('interview')
    const mirror = page.locator('button:has-text("내 모습 크게 보기")')
    if (await mirror.count()) {
      await mirror.click()
      await page.waitForTimeout(900)
      await shot('interview-mirror')
    }
    await go('/')
    await page.waitForSelector('text=내 면접')
  }

  // 리포트 — 기록 띠의 "리포트 보기".
  const report = page.locator('button:has-text("리포트 보기")').first()
  if (await report.count()) {
    await report.click()
    await page.waitForSelector('text=답변별 피드백', { timeout: 15000 })
    await page.waitForTimeout(600)
    await shot('report-top')
    await shot('report', { fullPage: true })
    await go('/')
    await page.waitForSelector('text=내 면접')
  }

  // 리서치 진행 — 첫 카드로 그린다. 조사 중인 카드가 없어도 배치는 같다.
  await go('/research')
  await page.waitForSelector('text=면접관이 준비하고 있습니다')
  await shot('research', { fullPage: true })
  await go('/review')
  await page.waitForSelector('text=면접 준비 리서치', { timeout: 15000 })
  await page.waitForTimeout(600)
  await shot('review')
  await go('/register/1')
  await page.waitForSelector('text=어느 회사에 지원하시나요')
  await shot('register-1', { fullPage: true })
  await go('/account')
  await page.waitForSelector('text=내 정보')
  await shot('account', { fullPage: true })

  // 랜딩·온보딩 — 로그인 상태를 가짜로 만든다.
  await page.route('**/api/auth/me', (route) => route.fulfill({ status: 401, body: '' }))
  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.waitForSelector('text=AI 음성 모의면접')
  await page.waitForTimeout(1500)
  await shot('landing-top')
  await shot('landing', { fullPage: true })
  await page.unroute('**/api/auth/me')
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 'u', name: '', onboarded: false }) }),
  )
  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.waitForSelector('text=면접관이 어떻게')
  await shot('onboarding', { fullPage: true })

  if (errors.length) {
    failed += 1
    console.log('  page errors:', errors.join('\n  '))
  }
  await context.close()
}

await browser.close()
if (failed) {
  console.log(`\n${failed} problem(s)`)
  process.exit(1)
}
console.log('\nall sizes ok')
