import { useNavigate } from 'react-router'
import { useAppStore } from '@/store/app'
import { AccentDot, ProgressBar } from '@/components/ui'
import { researchSteps } from '@/data/mock'
import type { Card as CardT } from '@/data/types'

/** README §1. 홈 — 내 면접 */
export function Home() {
  const nav = useNavigate()
  const cards = useAppStore((s) => s.cards)
  const setActiveCard = useAppStore((s) => s.setActiveCard)

  // 홈 카드 클릭: ready → 준비 완료 / researching → 리서치 진행 / done → 리포트
  const open = (card: CardT) => {
    setActiveCard(card.id)
    nav(card.status === 'ready' ? '/ready' : card.status === 'researching' ? '/research' : '/report')
  }

  return (
    <main className="mx-auto max-w-(--container-home) px-8 pt-[44px] pb-20">
      <div className="mb-[28px] flex items-end gap-4">
        <div className="flex flex-col gap-[6px]">
          <h1 className="m-0 text-[27px] leading-tight font-bold tracking-[-.03em]">내 면접</h1>
          <p className="m-0 text-[14px] text-muted">
            회사를 등록하면 그 회사에 맞춘 질문으로 면접을 준비합니다.
          </p>
        </div>
        <div className="flex-1" />
        <button
          onClick={() => nav('/register/1')}
          className="rounded-control bg-ink px-5 py-[11px] text-[14px] font-semibold text-white"
        >
          회사 등록하기
        </button>
      </div>

      <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))' }}>
        {cards.map((c) => (
          <CompanyCard key={c.id} card={c} onClick={() => open(c)} />
        ))}
        <button
          onClick={() => nav('/register/1')}
          className="flex min-h-[172px] items-center justify-center rounded-card border border-dashed border-field text-[13.5px] text-faint"
        >
          + 새 회사 등록
        </button>
      </div>
    </main>
  )
}

function CompanyCard({ card, onClick }: { card: CardT; onClick: () => void }) {
  const pct = card.pct ?? 0
  // 진행 중인 단계 라벨 — 20%마다 한 단계
  const stepLabel = researchSteps[Math.min(4, Math.floor(pct / 20))].label

  return (
    <div
      onClick={onClick}
      className="flex min-h-[172px] cursor-pointer flex-col rounded-card border border-line bg-surface p-5"
    >
      <div className="flex items-start gap-3">
        <div className="flex flex-col gap-[3px]">
          <div className="text-[17px] font-bold tracking-[-.02em]">{card.company}</div>
          <div className="text-[13px] text-muted">{card.role}</div>
        </div>
        <div className="flex-1" />
        <div className="text-[11.5px] text-faint">{card.date}</div>
      </div>

      <div className="flex-1" />

      {card.status === 'ready' && (
        <div className="flex flex-col gap-[11px]">
          <div className="flex items-center gap-[6px]">
            <AccentDot />
            <span className="text-[12.5px] font-semibold text-accent">면접 준비 완료</span>
          </div>
          <div className="flex items-center border-t border-hair-2 pt-[11px]">
            <span className="text-[12.5px] text-muted">4단계 · 15~20분</span>
            <div className="flex-1" />
            <span className="text-[13px] font-semibold">시작하기 →</span>
          </div>
        </div>
      )}

      {card.status === 'researching' && (
        <div className="flex flex-col gap-[9px]">
          <div className="flex items-center">
            <span className="num text-[12.5px] text-muted">면접 준비 중 · {pct}%</span>
            <div className="flex-1" />
            <span className="text-[12px] text-faint">자세히 보기 →</span>
          </div>
          <ProgressBar pct={pct} />
          <div className="text-[12.5px] text-muted">{stepLabel}</div>
        </div>
      )}

      {card.status === 'done' && (
        <div className="flex items-end border-t border-hair-2 pt-[11px]">
          <div className="flex flex-col gap-[3px]">
            <span className="text-[12px] text-faint">면접 완료</span>
            <span className="text-[12.5px] text-muted">리포트 보기 →</span>
          </div>
          <div className="flex-1" />
          <div className="flex items-baseline gap-[3px]">
            <span className="num text-[28px] leading-none font-bold tracking-[-.04em]">
              {card.score}
            </span>
            <span className="text-[12px] text-faint">점</span>
          </div>
        </div>
      )}
    </div>
  )
}
