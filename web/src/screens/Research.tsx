import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { getPreparationStatus } from '@/api/preparation'
import { useActiveCard, useAppStore } from '@/store/app'
import { fill, researchSteps } from '@/data/mock'
import { CheckDot, EmptyDot, ProgressBar, SectionLabel, Spinner } from '@/components/ui'

/** README §4. 리서치 진행 */
export function Research() {
  const nav = useNavigate()
  const card = useActiveCard()
  const setCardProgress = useAppStore((s) => s.setCardProgress)
  const [pct, setPct] = useState(card.pct ?? 0)

  // §서버 연동 2 — 1초마다 서버 진행률을 폴링한다. 서버가 없거나 카드가 서버
  // 작업이 아니면(목업 카드, 프론트 단독 실행) 프로토타입의 로컬 타이머
  // (120ms마다 2%)로 돌아간다.
  useEffect(() => {
    let timer: ReturnType<typeof setInterval>

    const finish = () => {
      clearInterval(timer)
      setTimeout(() => nav('/ready'), 300)
    }

    const advanceLocally = () => {
      clearInterval(timer)
      timer = setInterval(() => {
        setPct((p) => {
          const next = Math.min(100, p + 2)
          setCardProgress(card.id, next)
          if (next >= 100) finish()
          return next
        })
      }, 120)
    }

    timer = setInterval(() => {
      getPreparationStatus(card.id)
        .then((s) => {
          setPct(s.pct)
          setCardProgress(card.id, s.pct)
          if (s.status === 'done') finish()
          if (s.status === 'failed') clearInterval(timer)
        })
        .catch(advanceLocally)
    }, 1000)
    return () => clearInterval(timer)
  }, [card.id, nav, setCardProgress])

  const done = Math.floor(pct / 20)
  const remainLabel = pct >= 100 ? '완료' : `약 ${Math.max(1, Math.ceil((100 - pct) / 20))}분 남음`

  return (
    <main className="mx-auto max-w-(--container-doc) px-8 pt-[44px] pb-20 animate-dm-fade">
      <button onClick={() => nav('/')} className="mb-4 text-[13px] text-muted">
        ← 내 면접
      </button>

      <div className="rounded-card border border-line bg-surface p-7">
        <div className="mb-4 flex items-start">
          <div className="flex flex-col gap-[4px]">
            <div className="text-[20px] font-bold">{card.company}</div>
            <div className="text-[13.5px] text-muted">{card.role}</div>
          </div>
          <div className="flex-1" />
          <div className="flex flex-col items-end gap-[3px]">
            <div className="num text-[22px] font-bold text-accent">{pct}%</div>
            <div className="text-[12px] text-faint">{remainLabel}</div>
          </div>
        </div>

        <div className="mb-[26px]">
          <ProgressBar pct={pct} />
        </div>

        <SectionLabel>조사 진행 상황</SectionLabel>

        <div className="mt-2 mb-4">
          {researchSteps.map((step, i) => {
            const state = i < done ? 'done' : i === done ? 'active' : 'wait'
            return (
              <div key={step.label} className="flex gap-[13px] border-b border-hair py-[13px]">
                <div className="pt-[2px]">
                  {state === 'done' ? <CheckDot /> : state === 'active' ? <Spinner /> : <EmptyDot />}
                </div>
                <div className="flex flex-col gap-[4px]">
                  <div
                    className={`text-[14px] font-semibold ${
                      state === 'done' ? 'text-ink' : state === 'active' ? 'text-accent' : 'text-faintest'
                    }`}
                  >
                    {step.label}
                  </div>
                  {/* 아직 실행되지 않은 단계의 결과 문장을 미리 보여주면 안 됩니다.
                      완료된 단계만 결과를 표시합니다. */}
                  {state === 'done' && (
                    <div className="text-[12.5px] leading-[1.5] text-faint">
                      {fill(step.detail, card.company, card.role)}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        <div className="rounded-control border border-hair-2 bg-surface-2 px-[15px] py-[13px] text-[12.5px] text-muted">
          창을 닫아도 준비는 계속됩니다. 완료되면 알려드립니다.
        </div>
      </div>
    </main>
  )
}
