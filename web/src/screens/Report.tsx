import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useActiveCard } from '@/store/app'
import { SectionLabel } from '@/components/ui'
import {
  STAGE_NAMES,
  answerData,
  fill,
  questions,
  reportOverall,
  stageScores,
  strengths,
  voiceMetrics,
  waveformBars,
  weaknesses,
} from '@/data/mock'

/** README §10. 피드백 리포트 — 코칭 중심. 점수에서 시작해 답변별 개선 제안으로. */
export function Report() {
  const nav = useNavigate()
  const card = useActiveCard()
  const [openQ, setOpenQ] = useState(0)
  const F = (t: string) => fill(t, card.company, card.role)

  return (
    <main className="mx-auto max-w-(--container-report) px-8 pt-10 pb-[90px] animate-dm-fade">
      <div className="mb-[30px] flex items-center gap-[14px]">
        <button onClick={() => nav('/')} className="text-[13px] text-muted">
          ← 내 면접
        </button>
        <div className="flex-1" />
        <button className="text-[12.5px] text-muted">공유</button>
        <button className="text-[12.5px] text-muted">PDF로 저장</button>
      </div>

      {/* 헤더 */}
      <div className="flex items-start gap-[34px] border-b border-line pb-[30px]">
        <div className="flex flex-1 flex-col gap-[9px]">
          <div className="text-[12.5px] text-faint">
            {card.date.replace(' 면접', '').replace(' 등록', '')} 면접 · {reportOverall.duration} ·
            질문 {questions.length}개
          </div>
          <h1 className="m-0 text-[25px] font-bold tracking-[-.03em]">
            {card.company} · {card.role}
          </h1>
          <p className="mt-[6px] mb-0 max-w-[480px] text-[14px] leading-[1.7] text-body-2">
            {reportOverall.summary}
          </p>
        </div>
        <div className="flex flex-col items-end gap-[4px]">
          <div className="flex items-baseline gap-[4px]">
            <span className="num text-[52px] leading-none font-bold tracking-[-.05em]">
              {reportOverall.score}
            </span>
            <span className="text-[15px] text-faint">/ 100</span>
          </div>
          <span className="text-[12.5px] font-semibold text-accent">{reportOverall.percentile}</span>
        </div>
      </div>

      {/* 단계별 점수 */}
      <section className="border-b border-line py-[30px]">
        <div className="mb-[18px]">
          <SectionLabel>단계별 점수</SectionLabel>
        </div>
        <div className="flex flex-col gap-[14px]">
          {stageScores.map((s) => (
            <div key={s.name} className="flex items-center gap-4">
              <span className="w-[96px] text-[13.5px] font-semibold">{s.name}</span>
              <div className="flex-1 bg-line-3" style={{ height: 6 }}>
                <div className="h-full animate-dm-grow bg-ink" style={{ width: `${s.score}%` }} />
              </div>
              <span className="num w-[34px] text-right text-[15px] font-bold">{s.score}</span>
              <span className="w-[76px] text-right text-[12px] text-faint">{s.note}</span>
            </div>
          ))}
        </div>
      </section>

      {/* 음성 지표 */}
      <section className="border-b border-line py-[30px]">
        <div className="mb-[18px]">
          <SectionLabel>음성 지표</SectionLabel>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {voiceMetrics.map((m) => {
            const color = m.tone === 'positive' ? 'var(--color-positive)' : 'var(--color-accent)'
            return (
              <div
                key={m.label}
                className="flex flex-col gap-[7px] rounded-card border border-line bg-surface p-4"
              >
                <span className="text-[12.5px] text-muted">{m.label}</span>
                <div className="flex items-baseline gap-[4px]">
                  <span className="num text-[23px] font-bold tracking-[-.03em]">{m.value}</span>
                  {m.unit && <span className="text-[12px] text-faint">{m.unit}</span>}
                </div>
                <div className="bg-line-3" style={{ height: 3 }}>
                  <div className="h-full" style={{ width: `${m.w}%`, background: color }} />
                </div>
                <div className="flex items-center gap-[6px]">
                  <span className="text-[11.5px] font-semibold" style={{ color }}>
                    {m.verdict}
                  </span>
                  <span className="text-[11.5px] text-faintest">{m.range}</span>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {/* 내용 평가 */}
      <section className="border-b border-line py-[30px]">
        <div className="mb-[18px]">
          <SectionLabel>내용 평가</SectionLabel>
        </div>
        <div className="grid grid-cols-2 gap-[14px]">
          <div className="flex flex-col gap-3">
            <div className="text-[13px] font-bold text-positive">잘한 점</div>
            {strengths.map((t) => (
              <div key={t} className="flex gap-[8px]">
                <span className="text-[12px] text-positive">✓</span>
                <span className="text-[13.5px] leading-[1.65] text-body-2">{t}</span>
              </div>
            ))}
          </div>
          <div className="flex flex-col gap-3">
            <div className="text-[13px] font-bold text-accent">보완할 점</div>
            {weaknesses.map((t) => (
              <div key={t} className="flex gap-[8px]">
                <span className="text-[12px] text-accent">→</span>
                <span className="text-[13.5px] leading-[1.65] text-body-2">{t}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 답변별 피드백 */}
      <section className="py-[30px]">
        <div className="mb-[18px]">
          <SectionLabel>답변별 피드백</SectionLabel>
        </div>
        <div className="flex flex-col gap-[10px]">
          {answerData.map((a, i) => {
            const q = questions[i]
            const open = openQ === i
            return (
              <div
                key={i}
                className="rounded-card bg-surface"
                style={{ border: `1px solid ${open ? 'var(--color-field)' : 'var(--color-line)'}` }}
              >
                <div
                  onClick={() => setOpenQ(open ? -1 : i)}
                  className="flex cursor-pointer items-center gap-[13px] px-[18px] py-[15px]"
                >
                  <span className="num w-[22px] text-[11.5px] font-semibold text-faintest">
                    Q{i + 1}
                  </span>
                  <span className="w-[74px] text-[11.5px] text-faint">{STAGE_NAMES[q.s]}</span>
                  {/* 펼치면 헤더의 질문 요약을 비웁니다 — 바로 아래 전체 질문이 나오므로 */}
                  <span className="flex-1 truncate text-[13.5px] font-semibold">
                    {open ? '' : F(q.short)}
                  </span>
                  <span className="num text-[11.5px] text-faintest">{a.dur}</span>
                  <span className="num w-[28px] text-right text-[15px] font-bold">{a.score}</span>
                  <span className="w-[12px] text-[11px] text-faintest">{open ? '▲' : '▼'}</span>
                </div>

                {open && (
                  <div className="flex animate-dm-fade flex-col gap-4 px-[18px] pt-[4px] pb-5">
                    <div className="border-t border-hair pt-4 text-[15px] leading-[1.6] font-semibold">
                      {F(q.q)}
                    </div>

                    <PlaybackBar seed={i} duration={a.dur} />

                    <div className="flex flex-col gap-[6px]">
                      <span className="text-[11.5px] font-semibold text-faint">내 답변</span>
                      <p className="m-0 text-[13.5px] leading-[1.85] text-body-2">
                        {F(a.transcript)}
                      </p>
                      <span className="text-[11.5px] text-faintest">
                        전체 스크립트 보기 · 필러 워드 {a.filler}회 표시
                      </span>
                    </div>

                    <div className="border-l-2 border-accent pl-[15px]">
                      <div className="mb-[6px] text-[11.5px] font-bold text-accent">
                        이렇게 바꿔보세요
                      </div>
                      <p className="m-0 text-[13.5px] leading-[1.8] text-body">{F(a.coach)}</p>
                    </div>

                    <div className="flex flex-wrap gap-[6px]">
                      {a.tags.map((t) => (
                        <span
                          key={t}
                          className="rounded-chip border border-line-2 bg-surface-2 px-[9px] py-[4px] text-[11.5px] text-muted"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </section>

      <div className="flex items-center">
        <button onClick={() => nav('/')} className="text-[13px] text-muted">
          내 면접으로
        </button>
        <div className="flex-1" />
        <button
          onClick={() => nav('/ready')}
          className="rounded-control bg-ink px-7 py-[13px] text-[14px] font-semibold text-white"
        >
          이 회사로 다시 면접 보기
        </button>
      </div>
    </main>
  )
}

/** 재생 바 — 녹음 파일 URL은 §서버 연동 6에서 내려옵니다. */
function PlaybackBar({ seed, duration }: { seed: number; duration: string }) {
  const bars = waveformBars(seed)
  return (
    <div className="flex items-center gap-3 rounded-control border border-line-2 bg-surface-2 px-[13px] py-[10px]">
      <button
        className="flex items-center justify-center rounded-full bg-ink text-white"
        style={{ width: 26, height: 26, fontSize: 9 }}
      >
        ▶
      </button>
      <div className="flex flex-1 items-center gap-[2px]" style={{ height: 24 }}>
        {bars.map((h, i) => (
          <div key={i} className="flex-1 bg-field" style={{ height: `${h}%` }} />
        ))}
      </div>
      <span className="num text-[11.5px] text-faint">{duration}</span>
      <span className="bg-line" style={{ width: 1, height: 12 }} />
      <span className="text-[11.5px] text-muted">질문 음성</span>
    </div>
  )
}
