// 서버에 붙은 상태로 읽기만 하는 화면 점검.
//   node scripts/inspect.mjs [baseURL]
//
// drive.mjs와 다른 점: 등록을 누르지 않는다. 등록은 리서치를 시작하는데
// RESEARCH_MODE=live에서는 그것이 작업당 $1~7이다. 여기서는 홈 목록을 서버에서
// 받아 카드를 열어보는 것까지만 한다 — SSR 스모크가 못 잡는 effect·쿼리 오류를
// 잡는 것이 목적이다.
import { chromium } from 'playwright'

const BASE = process.argv[2] ?? 'http://localhost:5173'
const browser = await chromium.launch({ args: ['--no-sandbox'] })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

const errors = []
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
page.on('pageerror', (e) => errors.push(`[pageerror] ${e.message}`))

const step = async (name, fn) => {
  process.stdout.write(`▸ ${name} … `)
  try {
    await fn()
    console.log('ok')
  } catch (err) {
    console.log(`FAIL — ${err.message.split('\n')[0]}`)
    process.exitCode = 1
  }
}

await step('홈 — 서버 목록으로 카드가 그려진다', async () => {
  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.waitForSelector('text=내 면접')
  const cards = await page.locator('text=시작하기 →').count()
  if (cards === 0) throw new Error('준비 완료 카드가 하나도 없다')
  console.log(`(카드 ${cards}장) `)
})

await step('준비 완료 — 첫 카드를 연다', async () => {
  await page.locator('text=시작하기 →').first().click()
  await page.waitForSelector('text=시작 전 확인')
})

await step('시작 전 확인 — 체크 항목을 누를 수 있다', async () => {
  await page.locator('text=조용한 곳에서 진행합니다').click()
  await page.waitForTimeout(120)
})

await step('검토 — 실제 리포트를 읽어 편집란으로 연다', async () => {
  await page.locator('text=리포트 검토').click()
  await page.waitForSelector('textarea, text=고친 내용이 없습니다')
  const boxes = await page.locator('textarea').count()
  if (boxes === 0) throw new Error('편집 가능한 블록이 없다')
  console.log(`(편집란 ${boxes}개) `)
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
