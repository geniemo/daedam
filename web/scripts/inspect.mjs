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

await step('등록 STEP 1 — 회사·직무·채용공고 붙여넣기', async () => {
  await page.goto(`${BASE}/register/1`, { waitUntil: 'networkidle' })
  const fields = await page.locator('input').count()
  if (fields !== 2) throw new Error(`입력란이 ${fields}개다 (회사명·직무 둘이어야 한다)`)
  // 채용공고는 파싱 없이 리서치 프롬프트로 나가므로 붙여넣기 한 칸이다.
  if ((await page.locator('textarea').count()) !== 1) throw new Error('채용공고 붙여넣기 칸이 없다')
  // 만들지 않기로 한 파일 업로드가 되살아나지 않았는지 본다.
  for (const gone of ['직무 소개서', '파일 선택', '끌어다 놓']) {
    if (await page.locator(`text=${gone}`).count()) throw new Error(`"${gone}"이 남아 있다`)
  }

  // 회사명·직무 없이는 못 넘어간다. live에서 등록은 20~60분짜리 유료 작업이라
  // 빈 값으로 시작되면 엉뚱한 회사를 조사하게 된다.
  const next = page.locator('text=다음')
  if (!(await next.isDisabled())) throw new Error('빈 값인데 다음이 눌린다')
  await page.locator('input').first().fill('점검회사')
  if (!(await next.isDisabled())) throw new Error('직무가 비었는데 다음이 눌린다')
  await page.locator('input').nth(1).fill('점검직무')
  if (await next.isDisabled()) throw new Error('둘 다 채웠는데 다음이 안 눌린다')
})

await step('등록 STEP 2 — 빈 지원서로 시작해 파트를 추가한다', async () => {
  // 등록 버튼은 누르지 않는다 — 그것이 리서치를 시작한다.
  await page.goto(`${BASE}/register/2`, { waitUntil: 'networkidle' })
  const seeded = await page.locator('input[placeholder="파트 이름"]').count()
  if (seeded) throw new Error(`목업 파트가 ${seeded}개 남아 있다`)

  // 추가하면 펼쳐지고 커서까지 옮겨 간다 — 누른 사람은 바로 이름을 고칠 참이다.
  await page.locator('text=+ 파트 추가').click()
  if ((await page.evaluate(() => document.activeElement?.getAttribute('placeholder'))) !== '파트 이름')
    throw new Error('파트를 추가했는데 커서가 이름으로 안 온다')
  const name = page.locator('input[placeholder="파트 이름"]').first()
  await name.fill('자기소개서')
  if ((await name.inputValue()) !== '자기소개서') throw new Error('파트 이름이 바뀌지 않는다')

  await page.locator('text=+ 항목 추가').click()
  if ((await page.evaluate(() => document.activeElement?.getAttribute('placeholder'))) !== '항목 이름')
    throw new Error('항목을 추가했는데 커서가 이름으로 안 온다')

  // 긴 제목이 카드를 뚫지 않는다 (field-sizing:content + min-w-0).
  await page
    .locator('input[placeholder="항목 이름"]')
    .first()
    .fill('문항 1 — 지원 동기와 입사 후 포부를 아주 길게 적어 넣은 항목 제목입니다')

  // 본문은 내용만큼 자란다.
  const body = page.locator('textarea').first()
  const before = (await body.boundingBox()).height
  await body.fill('가나다라마바사아자차카타파하 '.repeat(30))
  await page.waitForTimeout(200)
  if ((await body.boundingBox()).height <= before) throw new Error('본문 칸이 안 자란다')

  // 파트 삭제는 접기 화살표 옆에 두지 않는다 — 자꾸 잘못 눌렸다.
  const header = await page
    .locator('input[placeholder="파트 이름"]')
    .first()
    .evaluate((el) => el.closest('div[class*="cursor-pointer"]').innerText)
  if (header.includes('파트 삭제')) throw new Error('삭제가 아직 헤더에 있다')

  // 한 번에 지워지지 않고 한 번 더 묻는다.
  await page.locator('text=파트 삭제').click()
  await page.waitForSelector('text=지울까요')
  if ((await page.locator('input[placeholder="파트 이름"]').count()) !== 1)
    throw new Error('묻기도 전에 지워졌다')
  await page.locator('text=취소').click()
  if ((await page.locator('input[placeholder="파트 이름"]').count()) !== 1)
    throw new Error('취소했는데 지워졌다')
})

await step('등록 — 다시 들어가면 앞서 입력한 것이 남지 않는다', async () => {
  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.locator('text=회사 등록하기').click()
  await page.waitForSelector('text=어느 회사에 지원하시나요')
  await page.locator('input').first().fill('앞회사')
  await page.locator('input').nth(1).fill('앞직무')
  await page.locator('textarea').first().fill('앞 공고 내용')
  await page.locator('text=다음').click()
  await page.locator('text=+ 파트 추가').click()

  // 홈으로 나갔다가 다시 등록하러 들어온다.
  await page.locator('text=✕ 나가기').click()
  await page.waitForSelector('text=내 면접')
  await page.locator('text=회사 등록하기').click()
  await page.waitForSelector('text=어느 회사에 지원하시나요')

  const company = await page.locator('input').first().inputValue()
  const role = await page.locator('input').nth(1).inputValue()
  const posting = await page.locator('textarea').first().inputValue()
  if (company || role || posting)
    throw new Error(`앞 입력이 남아 있다: "${company}" / "${role}" / "${posting}"`)

  await page.locator('input').first().fill('새회사')
  await page.locator('input').nth(1).fill('새직무')
  await page.locator('text=다음').click()
  const parts = await page.locator('input[placeholder="파트 이름"]').count()
  if (parts) throw new Error(`앞 지원서 파트가 ${parts}개 남아 있다`)
})

await step('준비 완료 — 첫 카드를 연다', async () => {
  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.locator('text=시작하기 →').first().click()
  await page.waitForSelector('text=시작 전 확인')
  // 지원서 수정은 없앴다. 그 화면은 등록용 초안을 읽어 빈 화면이 떴고,
  // 버튼이 "등록하고 준비 시작"이라 저장하면 리서치가 한 번 더 돌았다.
  if (await page.locator('text=지원서 수정').count()) throw new Error('지원서 수정이 살아 있다')
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
  // 목업이 아니라 서버 리포트가 그려질 때까지 기다린다. 쿼리가 도착하기 전에
  // 세면 목업 블록 수를 재게 된다.
  await page.waitForFunction(() => document.querySelectorAll('textarea').length > 20)
  const boxes = await page.locator('textarea').count()
  const cells = await page.locator('.grid textarea').count()
  if (cells === 0) throw new Error('표가 표로 안 그려졌다 — 문단으로 떨어졌을 것이다')
  // 마크다운 잔해가 편집란에 그대로 보이면 안 된다.
  const body = await page.locator('article').innerText()
  for (const junk of ['**', '<br', '| :---']) {
    if (body.includes(junk)) throw new Error(`"${junk}"가 본문에 남아 있다`)
  }
  return `편집란 ${boxes}개 · 표 칸 ${cells}개`
})

await step('검토 — 고치면 저장 버튼이 바뀐다', async () => {
  const first = page.locator('textarea').first()
  await first.fill((await first.inputValue()) + ' (확인)')
  await page.waitForSelector('text=저장하고 질문 다시 뽑기')
})

await step('리포트 — 면접을 마친 카드가 실제 피드백을 연다', async () => {
  await page.goto(BASE, { waitUntil: 'networkidle' })
  const finished = await page.locator('text=리포트 보기 →').count()
  if (finished === 0) return '면접을 마친 카드가 없어 건너뜀'

  await page.locator('text=리포트 보기 →').first().click()
  await page.waitForSelector('text=답변별 피드백')
  // 점수는 답변 점수의 평균이다 — 화면의 두 숫자가 어긋나면 안 된다.
  const overall = Number(await page.locator('.num').first().innerText())
  const each = await page
    .locator('text=답변별 피드백')
    .locator('..')
    .locator('.num.w-\\[28px\\]')
    .allInnerTexts()
    .catch(() => [])
  if (Number.isNaN(overall)) throw new Error('총점이 숫자가 아니다')
  if (each.length) {
    const mean = Math.round(each.map(Number).reduce((a, b) => a + b, 0) / each.length)
    if (mean !== overall) throw new Error(`총점 ${overall}과 답변 평균 ${mean}이 다르다`)
  }

  // 다시 듣기는 면접 전체 녹음에서 구간만 가져간다.
  const src = await page.locator('audio').first().getAttribute('src')
  if (!src?.endsWith('/audio')) throw new Error(`녹음 주소가 이상하다: ${src}`)
  return `총점 ${overall}`
})

await browser.close()

if (errors.length) {
  console.log(`\n콘솔 오류 ${errors.length}건:`)
  errors.slice(0, 10).forEach((e) => console.log(`  ${e}`))
  process.exitCode = 1
} else {
  console.log('\n콘솔 오류 없음')
}
