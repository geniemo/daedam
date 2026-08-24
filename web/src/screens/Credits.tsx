import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CouponError, getCredits, redeemCoupon } from '@/api/credits'
import { OutlineButton, SectionLabel, TextField } from '@/components/ui'

/**
 * 크레딧 충전.
 *
 * **결제는 아직 없다.** 국내 PG는 사업자등록증이 있어야 계약되므로, 지금
 * 크레딧을 늘리는 길은 쿠폰 코드뿐이다. 가격표를 먼저 보여주는 이유는 결제가
 * 붙었을 때 무엇을 사게 되는지가 지금도 궁금하기 때문이고, 값은 서버가
 * 내려준다 — 화면이 자기 숫자를 들고 있으면 서버와 어긋난 안내를 하게 된다.
 */
export function Credits() {
  const nav = useNavigate()
  const queryClient = useQueryClient()
  const { data: credits } = useQuery({ queryKey: ['credits'], queryFn: getCredits })

  return (
    <main className="mx-auto max-w-(--container-doc) px-8 pt-[44px] pb-20 animate-dm-fade">
      <button onClick={() => nav('/')} className="mb-4 text-[13px] text-muted">
        ← 내 면접
      </button>
      <h1 className="m-0 text-[24px] font-bold tracking-[-.03em]">크레딧</h1>

      <div className="mt-[22px] flex items-baseline gap-[7px] border-b border-line pb-[26px]">
        <span className="num text-[44px] leading-none font-bold tracking-[-.05em]">
          {credits?.balance ?? '—'}
        </span>
        <span className="text-[14px] text-faint">개 보유</span>
      </div>

      <section className="border-b border-line py-[26px]">
        <div className="mb-[14px]">
          <SectionLabel>무엇에 쓰이나요</SectionLabel>
        </div>
        <ul className="m-0 flex list-none flex-col gap-[10px] p-0">
          <Cost label="회사 등록" detail="공개 자료 조사 + 질문 생성" credits={credits?.costs.research} />
          <Cost label="면접 1회" detail="음성 면접 + 답변 코칭 리포트" credits={credits?.costs.interview} />
        </ul>
      </section>

      <Redeem
        onDone={() => {
          // 잔액이 실린 화면이 여럿이다(헤더·준비 화면). 통째로 다시 읽는다.
          void queryClient.invalidateQueries()
        }}
      />

      <section className="border-t border-line pt-[26px]">
        <div className="mb-[14px]">
          <SectionLabel>충전하기</SectionLabel>
        </div>
        {/* 값은 서버의 costs에서 유도한다 — 등록 1 + 면접 1을 한 팩으로. */}
        <div className="flex flex-col gap-[10px]">
          <Pack
            title="10 크레딧"
            detail={
              credits
                ? `회사 ${Math.floor(10 / credits.costs.research)}곳 등록 + 면접 ${Math.floor(
                    (10 - credits.costs.research) / credits.costs.interview,
                  )}회`
                : ''
            }
            price="9,900원"
          />
          <Pack title="30 크레딧" detail="크레딧당 897원 · 9% 저렴" price="26,900원" />
        </div>
        <p className="mt-[14px] mb-0 text-[12.5px] leading-[1.7] text-faint">
          결제는 준비 중입니다. 지금은 위의 코드 입력으로만 충전할 수 있습니다.
        </p>
      </section>
    </main>
  )
}

function Cost({
  label,
  detail,
  credits,
}: {
  label: string
  detail: string
  credits?: number
}) {
  return (
    <li className="flex items-center gap-[12px]">
      <span className="flex flex-1 flex-col gap-[2px]">
        <span className="text-[14px] font-semibold text-ink">{label}</span>
        <span className="text-[12.5px] text-muted">{detail}</span>
      </span>
      <span className="num text-[15px] font-semibold text-accent">
        {credits ?? '—'} 크레딧
      </span>
    </li>
  )
}

function Pack({ title, detail, price }: { title: string; detail: string; price: string }) {
  return (
    <div className="flex items-center gap-[12px] rounded-card border border-line bg-surface px-[16px] py-[14px]">
      <span className="flex flex-1 flex-col gap-[2px]">
        <span className="num text-[15px] font-semibold text-ink">{title}</span>
        <span className="text-[12.5px] text-muted">{detail}</span>
      </span>
      <span className="num text-[15px] font-semibold text-ink">{price}</span>
      {/* 결제가 붙기 전까지 눌리지 않는다 — 눌러서 아무 일도 안 나는 것보다
          비활성이 정직하다. */}
      <span className="rounded-control border border-field-2 px-[13px] py-[7px] text-[12.5px] text-faintest">
        준비 중
      </span>
    </div>
  )
}

function Redeem({ onDone }: { onDone: () => void }) {
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [granted, setGranted] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    if (!code.trim() || busy) return
    setBusy(true)
    setError('')
    setGranted(null)
    try {
      const { granted: amount } = await redeemCoupon(code)
      setGranted(amount)
      setCode('')
      onDone()
    } catch (e) {
      setError(e instanceof CouponError ? e.detail.message : '충전하지 못했습니다.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="border-b border-line py-[26px]">
      <div className="mb-[14px]">
        <SectionLabel>코드가 있으신가요</SectionLabel>
      </div>
      <div className="flex gap-[8px]">
        <TextField
          value={code}
          onChange={(e) => setCode(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && void submit()}
          placeholder="코드 입력"
          // 손으로 옮겨 적는 값이라 대문자로 보여준다. 서버도 정규화한다.
          className="num flex-1 uppercase"
          autoCapitalize="characters"
          spellCheck={false}
        />
        <OutlineButton onClick={() => void submit()} className="px-[20px] py-[12px] text-[14px]">
          {busy ? '확인 중' : '충전'}
        </OutlineButton>
      </div>
      {error && <p className="mt-[10px] mb-0 text-[13px] text-accent">{error}</p>}
      {granted !== null && !error && (
        <p className="mt-[10px] mb-0 text-[13px] text-positive">
          <span className="num font-semibold">{granted}</span> 크레딧이 충전되었습니다.
        </p>
      )}
    </section>
  )
}
