// 서버에 붙은 상태로 읽기만 하는 화면 점검.
//   node scripts/inspect.mjs [baseURL]
//
// drive.mjs와 다른 점: 등록을 누르지 않는다. 등록은 리서치를 시작하는데
// RESEARCH_MODE=live에서는 그것이 작업당 $1~7이다. 여기서는 홈 목록을 서버에서
// 받아 카드를 열어보는 것까지만 한다 — SSR 스모크가 못 잡는 effect·쿼리 오류를
// 잡는 것이 목적이다.
import { chromium } from 'playwright'

const BASE = process.argv[2] ?? 'http://localhost:5173'
// 가짜 마이크로 띄운다. 마이크 테스트가 실제로 소리를 잡는지 보려면 입력이
// 있어야 하는데, 헤드리스에는 장치가 없어서 권한 문제와 구분되지 않는다.
const browser = await chromium.launch({
  args: ['--no-sandbox', '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'],
})
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
await context.grantPermissions(['microphone'], { origin: BASE })
const page = await context.newPage()

const errors = []
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
page.on('pageerror', (e) => errors.push(`[pageerror] ${e.message}`))

// 어느 단계에서도 문서가 가로로 넘치면 안 된다. 편집란이 field-sizing:content라
// 내용이 길어지면 flex 항목(min-width:auto)을 밀어 컨테이너 밖으로 자란다 —
// 실제로 검토 화면이 1180px 자리에 1458px로 부풀어 페이지가 가로 스크롤됐다.
// 세로로 긴 화면이라 눈으로는 잘 안 보이므로 매 단계 재 본다.
const assertNoHScroll = async () => {
  const [scroll, view] = await page.evaluate(() => [
    document.documentElement.scrollWidth,
    window.innerWidth,
  ])
  if (scroll > view + 1) throw new Error(`가로로 넘친다 — 문서 ${scroll}px / 화면 ${view}px`)
}

const step = async (name, fn) => {
  process.stdout.write(`▸ ${name} … `)
  try {
    const note = await fn()
    await assertNoHScroll()
    console.log(note ? `ok (${note})` : 'ok')
  } catch (err) {
    console.log(`FAIL — ${err.message.split('\n')[0]}`)
    process.exitCode = 1
  }
}

await step('카드 없이 연 화면은 홈으로 돌아온다', async () => {
  // 스토어는 빈 목록으로 시작한다. 카드가 있어야 열리는 주소를 바로 치면
  // App.tsx의 RequireCard가 홈으로 보내야 한다 — 없는 카드를 읽다 흰 화면이
  // 되던 자리다.
  await page.goto(`${BASE}/ready`, { waitUntil: 'networkidle' })
  const path = new URL(page.url()).pathname
  if (path !== '/') throw new Error(`홈이 아니라 ${path}에 남았다`)
})

await step('홈 — 서버 목록으로 카드가 그려진다', async () => {
  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.waitForSelector('text=내 면접')
  const cards = await page.locator('text=시작하기 →').count()
  if (cards === 0) throw new Error('준비 완료 카드가 하나도 없다')
  return `카드 ${cards}장`
})

await step('등록 STEP 1 — 회사명과 직무만 묻는다', async () => {
  await page.goto(`${BASE}/register/1`, { waitUntil: 'networkidle' })
  const fields = await page.locator('input').count()
  if (fields !== 2) throw new Error(`입력란이 ${fields}개다 (회사명·직무 둘이어야 한다)`)
  // 라벨로 본다. "채용공고"만 찾으면 설명 문장("그 회사의 채용공고와 최근
  // 소식을 조사해")에 걸린다 — 그 문장은 사실이라 남아야 한다.
  for (const gone of ['채용공고 링크', '직무 소개서', '파일 선택']) {
    if (await page.locator(`text=${gone}`).count()) throw new Error(`"${gone}"이 남아 있다`)
  }
})

await step('등록 STEP 2 — 파트 이름을 눌러 고칠 수 있다', async () => {
  // 등록 버튼은 누르지 않는다 — 그것이 리서치를 시작한다.
  await page.goto(`${BASE}/register/2`, { waitUntil: 'networkidle' })
  const name = page.locator('input[placeholder="파트 이름"]').first()
  await name.fill('자기소개서')
  if ((await name.inputValue()) !== '자기소개서') throw new Error('파트 이름이 바뀌지 않는다')
})

await step('준비 완료 — 첫 카드를 연다', async () => {
  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.locator('text=시작하기 →').first().click()
  await page.waitForSelector('text=시작 전 확인')
})

await step('시작 전 확인 — 마이크가 실제로 소리를 잡는다', async () => {
  await page.locator('text=테스트하기').click()
  // 가짜 장치는 사인파를 흘린다. HEARD_LEVEL(0.12)을 넘으면 문구가 바뀐다.
  await page.waitForSelector('text=마이크가 소리를 잡았습니다', { timeout: 5000 })
  const width = await page.locator('.h-full.bg-accent').first().evaluate((el) => el.style.width)
  return `막대 ${width}`
})

await step('시작 전 확인 — 체크 항목을 누를 수 있다', async () => {
  await page.locator('text=조용한 곳에서 진행합니다').click()
  await page.waitForTimeout(120)
})

await step('검토 — 실제 리포트를 읽어 편집란으로 연다', async () => {
  await page.locator('text=리포트 검토').click()
  await page.waitForSelector('textarea')
  const boxes = await page.locator('textarea').count()
  if (boxes === 0) throw new Error('편집 가능한 블록이 없다')
  return `편집란 ${boxes}개`
})

await step('검토 — 고치면 저장 버튼이 바뀐다', async () => {
  const first = page.locator('textarea').first()
  await first.fill((await first.inputValue()) + ' (확인)')
  await page.waitForSelector('text=저장하고 질문 다시 뽑기')
})

await browser.close()

if (errors.length) {
  console.log(`\n콘솔 오류 ${errors.length}건:`)
  errors.slice(0, 10).forEach((e) => console.log(`  ${e}`))
  process.exitCode = 1
} else {
  console.log('\n콘솔 오류 없음')
}
