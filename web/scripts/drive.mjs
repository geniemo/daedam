// Drive the app end-to-end in headless Chromium and screenshot every screen.
//   node scripts/drive.mjs [baseURL]
// Screenshots land in .shots/ (gitignored).
import { chromium } from 'playwright'
import { mkdir, rm } from 'node:fs/promises'

const BASE = process.argv[2] ?? 'http://localhost:5173'
const OUT = '.shots'

await rm(OUT, { recursive: true, force: true })
await mkdir(OUT, { recursive: true })

const browser = await chromium.launch({ args: ['--no-sandbox'] })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

const errors = []
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
page.on('pageerror', (e) => errors.push(`[pageerror] ${e.message}`))

let n = 0
const shot = async (name, opts = {}) => {
  const file = `${OUT}/${String(++n).padStart(2, '0')}-${name}.png`
  await page.screenshot({ path: file, ...opts })
  console.log(`  📸 ${file}`)
}
const step = (s) => console.log(`\n▸ ${s}`)

/* 1. 홈 */
step('홈 — 내 면접')
await page.goto(BASE, { waitUntil: 'networkidle' })
await page.waitForSelector('text=내 면접')
await shot('home', { fullPage: true })

/* 2. 등록 STEP 1 */
step('등록 STEP 1 — 회사·직무')
await page.click('text=회사 등록하기')
await page.waitForSelector('text=어느 회사에 지원하시나요')
await page.fill('input[placeholder="예) 누리테크"]', '세종바이오')
await page.fill('input[placeholder="예) 서비스기획"]', '마케팅 · 신입')
await shot('register-1')

/* 3. 등록 STEP 2 */
step('등록 STEP 2 — 지원서')
await page.click('text=다음')
await page.waitForSelector('text=지원서를 넣어 주세요')
await shot('register-2', { fullPage: true })

/* 4. 리서치 진행 — 단계가 순차 완료되는지 */
step('리서치 진행')
await page.click('text=등록하고 준비 시작')
await page.waitForSelector('text=조사 진행 상황')
await page.waitForTimeout(1500)
await shot('research-mid')
await page.waitForTimeout(2500)
await shot('research-late')

/* 5. 준비 완료 */
step('준비 완료')
await page.waitForSelector('text=시작 전 확인', { timeout: 20000 })
await shot('ready', { fullPage: true })

/* 6. 리포트 검토 — 주석 달기 */
step('리포트 검토 — 사실과 다름 + 메모')
await page.click('text=리포트 열기')
await page.waitForSelector('text=확인이 필요한 대목')
await shot('review', { fullPage: true })

await page.locator('button:has-text("사실과 다름")').first().click()
await page.locator('button:has-text("메모")').nth(1).click()
await page.fill('input[placeholder="아는 내용이나 정정할 내용을 적어 주세요"]', '2026년 기준으로는 55% 입니다')
await page.click('text=남기기')
await page.waitForSelector('text=정정 1건 · 메모 1건')
await shot('review-annotated')

/* 7. 질문 재생성 */
step('질문 재생성')
await page.click('text=질문 다시 뽑기')
await page.waitForSelector('text=고치신 내용으로 질문을 다시 뽑고 있습니다')
await shot('regen')

/* 8. 면접 진행 */
step('면접 진행 — 발화 / 청취 / 일시정지')
await page.waitForSelector('text=시작 전 확인', { timeout: 20000 })
await shot('ready-after-regen')
await page.click('text=면접 시작하기')
await page.waitForSelector('text=면접관이 말하고 있습니다')
await page.waitForTimeout(1200)
await shot('interview-speaking')

await page.waitForSelector('text=듣고 있습니다', { timeout: 15000 })
await page.waitForTimeout(800)
await shot('interview-listening')

await page.click('button:has-text("일시정지")')
await page.waitForSelector('text=면접을 잠시 멈췄습니다')
await shot('interview-paused')

/* 9. 분석 중 */
step('분석 중')
await page.click('text=종료하고 리포트 받기')
await page.waitForSelector('text=답변을 분석하고 있습니다')
await shot('analyzing')

/* 10. 피드백 리포트 */
step('피드백 리포트')
await page.waitForSelector('text=음성 지표', { timeout: 20000 })
await shot('report', { fullPage: true })
await page.locator('div:has-text("Q5")').last().scrollIntoViewIfNeeded()
await page.click('text=이렇게 바꿔보세요 >> nth=0').catch(() => {})
await shot('report-answer-open')

await browser.close()

console.log(`\n${n} screenshots → ${OUT}/`)
if (errors.length) {
  console.log(`\n⚠ ${errors.length} console error(s):`)
  errors.slice(0, 15).forEach((e) => console.log(`  ${e}`))
  process.exit(1)
}
console.log('✓ no console errors')
