import { useEffect } from 'react'
import { useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { listInterviews } from '@/api/preparation'
import { useAppStore } from '@/store/app'
import { AccentDot, Icon, ProgressBar } from '@/components/ui'
import { Avatar, Keylight } from '@/components/Stage'
import { initialCards } from '@/data/mock'
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
  const resetRegister = useAppStore((s) => s.resetRegister)
  const notice = useAppStore((s) => s.notice)
  const setNotice = useAppStore((s) => s.setNotice)

  // 등록 폼은 스토어에 남는다. 새로 등록하러 들어갈 때 비우지 않으면 앞 회사의
  // 회사명·직무·채용공고·지원서가 그대로 떠 있다.
  const startRegister = () => {
    resetRegister()
    nav('/register/1')
  }

  // 목록의 진실은 서버 파일이다. 프론트 메모리로 들고 있으면 새로고침에
  // 사라지고, 준비 데이터가 없는 면접을 시작하려다 브리지에서 거절당한다.
  const { data, isError, isPending } = useQuery({ queryKey: ['interviews'], queryFn: listInterviews })

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
        // 면접을 마쳤으면 리포트로 간다. 그다음이 준비 완료, 그다음이 준비 중.
        status: item.interviewCount > 0 ? 'done' : item.ready ? 'ready' : 'researching',
        score: item.score ?? undefined,
        interviewCount: item.interviewCount,
        analyzed: item.analyzed,
      })),
    )
  }, [data, isError, setCards])

  // 홈 카드 클릭: ready → 준비 완료 / researching → 리서치 진행 / done → 리포트
  const open = (card: CardT) => {
    setActiveCard(card.id)
    nav(card.status === 'ready' ? '/ready' : card.status === 'researching' ? '/research' : '/report')
  }

  // 준비 완료된 것 중 가장 최근 하나가 "다음 면접"이다 — 목록은 서버가 최근순으로
  // 준다. 나머지는 격자로.
  const featured = cards.find((c) => c.status === 'ready')
  const rest = cards.filter((c) => c !== featured)
  // 빈 상태에서는 카드가 주인공이다 — 상단 버튼·부제를 숨겨 같은 행동이 둘
  // 되지 않게. 목록을 아직 못 받았을 때는 비었다고 말하지 않는다.
  const empty = !isPending && cards.length === 0

  return (
    <main className="mx-auto max-w-(--container-home) px-8 pt-[44px] pb-20">
      <div className="mb-[28px] flex items-end gap-4">
        <div className="flex flex-col gap-[6px]">
          <h1 className="m-0 text-[27px] leading-tight font-bold tracking-[-.03em]">내 면접</h1>
          {!empty && (
            <p className="m-0 text-[14px] text-muted">
              회사를 등록하면 그 회사에 맞춘 질문으로 면접을 준비합니다.
            </p>
          )}
        </div>
        <div className="flex-1" />
        {!empty && (
          <button
            onClick={startRegister}
            className="rounded-control bg-ink px-5 py-[11px] text-[14px] font-semibold text-white"
          >
            회사 등록하기
          </button>
        )}
      </div>

      {/* 면접 화면이 결과 없이 돌려보낸 이유. 닫을 때까지 남는다 — 새로고침에는
          사라지는데, 그건 이미 읽었다는 뜻으로 본다. */}
      {notice && (
        <div className="mb-[18px] flex items-start gap-3 rounded-control border border-accent-line bg-accent-bg px-[14px] py-[11px] text-[13px] leading-[1.6] text-accent">
          <span className="flex-1">{notice}</span>
          <button type="button" onClick={() => setNotice(null)} className="text-[12px] font-semibold text-accent">
            닫기
          </button>
        </div>
      )}

      {empty && <Empty onRegister={startRegister} />}

      {featured && (
        <Featured
          card={featured}
          onStart={() => open(featured)}
          onReview={() => {
            setActiveCard(featured.id)
            nav('/review')
          }}
        />
      )}

      {!empty && (
        <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))' }}>
          {rest.map((c) => (
            <CompanyCard key={c.id} card={c} onClick={() => open(c)} />
          ))}
          <button
            onClick={startRegister}
            className="flex min-h-[172px] items-center justify-center rounded-card border border-dashed border-field text-[13.5px] text-faint"
          >
            + 새 회사 등록
          </button>
        </div>
      )}
    </main>
  )
}

/**
 * 다음 면접 — 준비 완료된 것 중 가장 최근 하나. 무대 미리 보기 + 시작.
 * 시작은 준비 완료 화면(시작 전 확인)으로 간다 — 마이크를 확인하지 않고
 * 면접장에 들어가는 길은 없다.
 */
function Featured({ card, onStart, onReview }: { card: CardT; onStart: () => void; onReview: () => void }) {
  return (
    <div className="mb-4 grid overflow-hidden rounded-card border border-line bg-surface shadow-card" style={{ gridTemplateColumns: '300px minmax(0, 1fr)' }}>
      <div
        className="relative flex min-h-[196px] items-center justify-center overflow-hidden"
        style={{ background: 'var(--stage-bg)' }}
      >
        <Keylight width={520} height={300} top="-40%" alpha={0.09} />
        <div className="relative">
          <Avatar size={96} speaking glow={0.5} bloom={false} />
        </div>
        <div className="absolute flex items-center gap-[7px]" style={{ left: 18, bottom: 16 }}>
          <span
            className="rounded-full"
            style={{ width: 6, height: 6, background: 'var(--stage-amber)', boxShadow: '0 0 8px var(--stage-amber)' }}
          />
          <span className="text-[12px]" style={{ color: 'var(--stage-ink-warm)' }}>
            면접관이 기다리고 있습니다
          </span>
        </div>
      </div>
      <div className="flex flex-col gap-[6px] px-6 py-[22px]">
        <div className="flex items-center gap-[6px]">
          <AccentDot />
          <span className="text-[12px] font-semibold tracking-[.05em] text-accent">다음 면접</span>
        </div>
        <div className="mt-[2px] text-[22px] font-bold tracking-[-.025em]">{card.company}</div>
        <div className="text-[13.5px] text-muted">
          {card.role} · {card.date} 등록
        </div>
        <div className="flex-1" />
        <div className="mt-[14px] flex items-center gap-[10px]">
          <button
            onClick={onStart}
            className="rounded-control bg-ink px-[22px] py-[12px] text-[14px] font-semibold text-white"
          >
            면접 시작하기
          </button>
          <button
            onClick={onReview}
            className="rounded-control border border-field bg-surface px-4 py-[10px] text-[13.5px] font-semibold text-ink"
          >
            준비 내용 보기
          </button>
          <div className="flex-1" />
          <span className="text-[12.5px] text-faint">15분 내외 · 한국어 음성</span>
        </div>
      </div>
    </div>
  )
}

/** 첫 방문 — 등록한 회사가 없다. */
function Empty({ onRegister }: { onRegister: () => void }) {
  return (
    <div className="flex flex-col items-center rounded-card border border-line bg-surface px-8 py-14 text-center shadow-card">
      <div className="mb-[22px]">
        <Avatar size={72} speaking glow={0.5} bloom={false} />
      </div>
      <h2 className="m-0 text-[19px] font-bold tracking-[-.02em]">첫 회사를 등록해 보세요</h2>
      <p className="mt-[10px] mb-0 max-w-[420px] text-[13.5px] leading-[1.75] text-muted">
        회사를 등록하면 대담의 노하우를 통해 면접을 준비합니다.
        <br />
        준비가 끝나면 면접을 시작해보세요.
      </p>
      <button
        onClick={onRegister}
        className="mt-6 rounded-control bg-ink px-[26px] py-3 text-[14px] font-semibold text-white"
      >
        회사 등록하기
      </button>
    </div>
  )
}

function CompanyCard({ card, onClick }: { card: CardT; onClick: () => void }) {
  // 서버 목록에는 진행률이 없다 — 준비 중이라는 사실만 안다. 0%를 지어내
  // 보여주면 멈춘 것처럼 읽히므로, 진행률을 아는 경우에만 바를 그린다.
  const pct = card.pct

  return (
    <div
      onClick={onClick}
      className="flex min-h-[172px] cursor-pointer flex-col rounded-card border border-line bg-surface p-5 shadow-card"
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
            <div className="flex-1" />
            <span className="flex items-center gap-1 text-[13px] font-semibold">
              시작하기 <Icon name="arrow-right" size={13} />
            </span>
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
            <span className="flex items-center gap-1 text-[12px] text-faint">
              자세히 보기 <Icon name="arrow-right" size={12} />
            </span>
          </div>
          {pct !== undefined && <ProgressBar pct={pct} />}
        </div>
      )}

      {card.status === 'done' && (
        <div className="flex items-end border-t border-hair-2 pt-[11px]">
          <div className="flex flex-col gap-[3px]">
            <span className="text-[12px] text-faint">
              {/* 몇 번 봤는지가 이 카드의 이력이다 — 다시 볼수록 늘어난다. */}
              {(card.interviewCount ?? 1) > 1 ? `면접 ${card.interviewCount}회` : '면접 완료'}
            </span>
            <span className="flex items-center gap-1 text-[12.5px] text-muted">
              리포트 보기 <Icon name="arrow-right" size={12} />
            </span>
          </div>
          <div className="flex-1" />
          {card.score !== undefined ? (
            <div className="flex items-baseline gap-[3px]">
              <span className="num text-[28px] leading-none font-bold tracking-[-.04em]">
                {card.score}
              </span>
              <span className="text-[12px] text-faint">점</span>
            </div>
          ) : card.analyzed ? (
            /* 분석은 끝났는데 채점할 답변이 없었다. 아무 말 없이 끝난 면접은
               애초에 여기 잡히지 않는다 — 서버가 "가장 최근"에서 뺀다. */
            <span className="text-[12.5px] text-faint">답변 없음</span>
          ) : (
            <span className="text-[12.5px] text-faint">분석 중</span>
          )}
        </div>
      )}
    </div>
  )
}
