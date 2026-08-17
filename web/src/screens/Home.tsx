import { useEffect } from 'react'
import { useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { listInterviews } from '@/api/preparation'
import { useAppStore } from '@/store/app'
import { AccentDot, ProgressBar } from '@/components/ui'
import { initialCards, researchSteps } from '@/data/mock'
import type { Card as CardT } from '@/data/types'

/** 저장 시각(epoch 초) → "8월 17일". 카드 우상단에 붙는다. */
const savedLabel = (savedAt: number) => {
  const date = new Date(savedAt * 1000)
  return `${date.getMonth() + 1}월 ${date.getDate()}일`
}

/** README §1. 홈 — 내 면접 */
export function Home() {
  const nav = useNavigate()
  const cards = useAppStore((s) => s.cards)
  const setActiveCard = useAppStore((s) => s.setActiveCard)
  const setCards = useAppStore((s) => s.setCards)

  // 목록의 진실은 서버 파일이다. 프론트 메모리로 들고 있으면 새로고침에
  // 사라지고, 준비 데이터가 없는 면접을 시작하려다 브리지에서 거절당한다.
  const { data, isError } = useQuery({ queryKey: ['interviews'], queryFn: listInterviews })

  useEffect(() => {
    // 서버가 없으면(프론트 단독 실행) 목업으로 화면 모양만 유지한다. 성공했는데
    // 목록이 비어 있는 것은 정상이다 — 그때 목업을 넣으면 없는 면접이 생긴다.
    if (isError) {
      setCards(initialCards)
      return
    }
    if (!data) return
    setCards(
      data.map((item) => ({
        id: item.id,
        company: item.company,
        role: item.role,
        date: savedLabel(item.savedAt),
        // 질문 풀까지 있어야 시작할 수 있다 — 아니면 아직 준비 중이다.
        status: item.ready ? 'ready' : 'researching',
      })),
    )
  }, [data, isError, setCards])

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
  // 서버 목록에는 진행률이 없다 — 준비 중이라는 사실만 안다. 0%를 지어내
  // 보여주면 멈춘 것처럼 읽히므로, 진행률을 아는 경우에만 바를 그린다.
  const pct = card.pct
  const stepLabel =
    pct === undefined ? null : researchSteps[Math.min(4, Math.floor(pct / 20))].label

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
            <span className="num text-[12.5px] text-muted">
              면접 준비 중{pct === undefined ? '' : ` · ${pct}%`}
            </span>
            <div className="flex-1" />
            <span className="text-[12px] text-faint">자세히 보기 →</span>
          </div>
          {pct !== undefined && <ProgressBar pct={pct} />}
          {stepLabel && <div className="text-[12.5px] text-muted">{stepLabel}</div>}
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
