import { useEffect } from 'react'
import { useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { listInterviews, listRecords } from '@/api/preparation'
import type { InterviewRecord, RecordSummary } from '@/api/preparation'
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
  // 쌓인 기록 — 회사를 가로질러 센다. 없거나 서버가 없으면 띠를 그리지 않는다.
  const { data: records } = useQuery({ queryKey: ['records'], queryFn: listRecords, retry: false })

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
  const hasRecords = !empty && records !== undefined && records.records.length > 0

  return (
    <main className="mx-auto max-w-(--container-home) px-5 pt-7 pb-[60px] md:px-8 md:pt-[44px] md:pb-20">
      <div className="mb-[28px] flex flex-wrap items-end gap-4">
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

      {hasRecords && (
        <RecordStrip
          summary={records}
          onReport={() => {
            // 가장 최근 회차의 리포트. 리포트 화면은 회차를 고르지 않으면
            // 그 회사의 가장 최근 회차를 연다 — 곧 이 기록이다.
            setActiveCard(records.records[records.records.length - 1].interviewId)
            nav('/report')
          }}
        />
      )}

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
        /* min(340px, 100%) — 340보다 좁은 화면에서도 한 열이 넘치지 않는다. */
        <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(min(340px, 100%), 1fr))' }}>
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
 * 기록 띠 — 면접 횟수·평균·최근, 회차별 점수 막대, 반복된 보완점.
 *
 * 회사 목록만 있으면 층이 하나라 허전하다 — "쌓인 것"을 한 줄로 보인다.
 * 데이터는 서버가 리포트를 가로질러 집계한다(`/api/interviews/records`).
 * 좁은 화면에서는 세 덩이가 세로로 쌓이고 세로 구분선이 빠진다.
 */
function RecordStrip({ summary, onReport }: { summary: RecordSummary; onReport: () => void }) {
  const { records, recurring } = summary
  const average = Math.round(records.reduce((sum, item) => sum + item.score, 0) / records.length)
  const last = records[records.length - 1]
  const totals = [
    { label: '면접', value: records.length, unit: '회' },
    { label: '평균', value: average, unit: '점' },
    { label: '최근', value: last.score, unit: '점' },
  ]

  return (
    <div className="mb-4 grid items-center gap-4 rounded-card border border-line bg-surface px-[18px] py-4 shadow-card md:grid-cols-[auto_auto_auto_1fr] md:gap-9 md:px-[22px] md:py-[18px]">
      <div className="flex gap-7">
        {totals.map(({ label, value, unit }) => (
          <div key={label} className="flex flex-col gap-[6px]">
            <span className="text-[11.5px] text-faint">{label}</span>
            <Num value={value} unit={unit} />
          </div>
        ))}
      </div>
      <div className="hidden h-11 w-px bg-hair-2 md:block" />
      <Bars records={records} />
      <div className="flex min-w-0 items-center justify-between gap-[14px] md:justify-end">
        {recurring ? (
          <div className="flex min-w-0 items-center gap-[9px]">
            <span className="flex shrink-0">
              <Icon name="arrow-right" size={13} color="var(--color-accent)" />
            </span>
            <span className="min-w-0 break-keep text-[13px] leading-[1.5] text-body-2 md:truncate">
              {recurring.text}
            </span>
            <span className="num shrink-0 text-[11.5px] font-semibold text-accent">{recurring.count}회 지적</span>
          </div>
        ) : (
          <span className="text-[13px] text-faint">반복된 보완점이 아직 없습니다</span>
        )}
        <button onClick={onReport} className="shrink-0 border-b border-field text-[12.5px] text-muted">
          리포트 보기
        </button>
      </div>
    </div>
  )
}

/** 큰 숫자 + 단위. 기록 띠의 세 값. */
function Num({ value, unit, size = 22 }: { value: number; unit?: string; size?: number }) {
  return (
    <span className="flex items-baseline gap-[3px]">
      <span className="num leading-none font-bold tracking-[-.04em]" style={{ fontSize: size }}>
        {value}
      </span>
      {unit && <span className="text-[12px] text-faint">{unit}</span>}
    </span>
  )
}

/** 띠 한 줄에 들어가는 막대 수. 열 개면 200px — 좁은 화면 한 열에도 들어간다. */
const BARS_SHOWN = 10

/** 회차 점수 막대 — 높이가 점수(100 기준), 마지막만 앰버. 오래된 것은 잘라 낸다. */
function Bars({ records, height = 40 }: { records: InterviewRecord[]; height?: number }) {
  const shown = records.slice(-BARS_SHOWN)
  return (
    <div className="flex items-end gap-[6px]" style={{ height }}>
      {shown.map((item, i) => {
        const last = i === shown.length - 1
        return (
          <div key={item.sessionId} title={`${item.company} ${item.n}회차`} className="flex flex-col items-center gap-1">
            <span className={`num text-[10.5px] ${last ? 'font-semibold text-ink' : 'text-faint'}`}>{item.score}</span>
            <div
              className={`rounded-[2px] ${last ? 'bg-accent' : 'bg-line'}`}
              style={{ width: 14, height: Math.round(((height - 16) * item.score) / 100) }}
            />
          </div>
        )
      })}
    </div>
  )
}

/**
 * 다음 면접 — 준비 완료된 것 중 가장 최근 하나. 무대 미리 보기 + 시작.
 * 시작은 준비 완료 화면(시작 전 확인)으로 간다 — 마이크를 확인하지 않고
 * 면접장에 들어가는 길은 없다.
 *
 * 카드 폭이 720 미만이면 무대가 위로 올라가는 세로 쌓기다. 창이 아니라 카드
 * 폭으로 가르므로 컨테이너 쿼리다 — 그 폭에서 300px 무대와 글 두 줄이 나란히
 * 서지 못한다.
 */
function Featured({ card, onStart, onReview }: { card: CardT; onStart: () => void; onReview: () => void }) {
  return (
    <div className="@container mb-4">
      <div className="grid overflow-hidden rounded-card border border-line bg-surface shadow-card @min-[720px]:grid-cols-[300px_minmax(0,1fr)]">
        <div
          className="relative flex min-h-[150px] items-center justify-center overflow-hidden @min-[720px]:min-h-[196px]"
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
        <div className="flex flex-col gap-[6px] px-6 py-[22px] break-keep">
          <div className="flex items-center gap-[6px]">
            <AccentDot />
            <span className="text-[12px] font-semibold tracking-[.05em] text-accent">다음 면접</span>
          </div>
          <div className="mt-[2px] text-[22px] font-bold tracking-[-.025em]">{card.company}</div>
          <div className="text-[13.5px] text-muted">
            {card.role} · {card.date} 등록
          </div>
          <div className="flex-1" />
          <div className="mt-[14px] flex flex-wrap items-center gap-[10px]">
            <button
              onClick={onStart}
              className="rounded-control bg-ink px-[22px] py-[12px] text-[14px] font-semibold whitespace-nowrap text-white"
            >
              면접 시작하기
            </button>
            <button
              onClick={onReview}
              className="rounded-control border border-field bg-surface px-4 py-[10px] text-[13.5px] font-semibold whitespace-nowrap text-ink"
            >
              준비 내용 보기
            </button>
          </div>
          <span className="mt-[10px] text-[12.5px] whitespace-nowrap text-faint">15분 내외 · 한국어 음성</span>
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
