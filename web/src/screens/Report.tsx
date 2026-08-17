import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { audioUrl, getFeedback } from '@/api/preparation'
import type { Feedback } from '@/api/preparation'
import { useActiveCard } from '@/store/app'
import { SectionLabel } from '@/components/ui'

/**
 * README §10. 피드백 리포트 — 코칭 중심. 점수에서 시작해 답변별 개선 제안으로.
 *
 * 모든 값은 서버가 만든 feedback.json에서 온다. 지어내지 않기로 한 것 둘:
 * **백분위**는 비교할 모집단이 없고, **단계별 점수**는 전사에 단계 정보가
 * 없어서 낼 수 없다. 자리를 비워 두는 편이 그럴듯한 숫자를 채우는 것보다 낫다.
 */
export function Report() {
  const nav = useNavigate()
  const card = useActiveCard()
  const { data, isError } = useQuery({
    queryKey: ['feedback', card.id],
    queryFn: () => getFeedback(card.id),
    retry: false,
  })

  const feedback = data?.status === 'done' ? data.feedback : undefined
  if (!feedback) {
    return (
      <main className="mx-auto max-w-(--container-report) px-8 pt-10 pb-20 animate-dm-fade">
        <button onClick={() => nav('/')} className="mb-6 text-[13px] text-muted">
          ← 내 면접
        </button>
        <h1 className="m-0 text-[20px] font-bold">
          {isError || data?.status === 'failed'
            ? '분석 결과를 만들지 못했습니다'
            : data?.status === 'absent'
              ? '아직 면접을 진행하지 않았습니다'
              : '분석 결과를 불러오는 중입니다'}
        </h1>
      </main>
    )
  }

  return <ReportBody feedback={feedback} interviewId={card.id} onLeave={() => nav('/')} onAgain={() => nav('/ready')} company={card.company} role={card.role} />
}

function ReportBody({
  feedback,
  interviewId,
  company,
  role,
  onLeave,
  onAgain,
}: {
  feedback: Feedback
  interviewId: string
  company: string
  role: string
  onLeave: () => void
  onAgain: () => void
}) {
  const [openQ, setOpenQ] = useState(0)
  const { coaching, voice } = feedback
  const minutes = Math.floor(feedback.durationS / 60)
  const seconds = Math.round(feedback.durationS % 60)

  return (
    <main className="mx-auto max-w-(--container-report) px-8 pt-10 pb-[90px] animate-dm-fade">
      <div className="mb-[30px] flex items-center gap-[14px]">
        <button onClick={onLeave} className="text-[13px] text-muted">
          ← 내 면접
        </button>
      </div>

      {/* 헤더 */}
      <div className="flex items-start gap-[34px] border-b border-line pb-[30px]">
        <div className="flex flex-1 flex-col gap-[9px]">
          <div className="text-[12.5px] text-faint">
            {minutes}분 {seconds}초 · 답변 {coaching.answers.length}개
          </div>
          <h1 className="m-0 text-[25px] font-bold tracking-[-.03em]">
            {company} · {role}
          </h1>
          <p className="mt-[6px] mb-0 max-w-[520px] text-[14px] leading-[1.7] text-body-2">
            {coaching.summary}
          </p>
        </div>
        {/* 점수는 답변 점수의 평균입니다 — 아래 답변별 점수와 반드시 맞습니다. */}
        <div className="flex flex-col items-end gap-[4px]">
          <div className="flex items-baseline gap-[4px]">
            <span className="num text-[52px] leading-none font-bold tracking-[-.05em]">
              {coaching.score ?? '—'}
            </span>
            <span className="text-[15px] text-faint">/ 100</span>
          </div>
          <span className="text-[12px] text-faintest">답변 점수의 평균</span>
        </div>
      </div>

      {voice && (
        <section className="border-b border-line py-[30px]">
          <div className="mb-[18px]">
            <SectionLabel>음성 지표</SectionLabel>
          </div>
          <div className="grid grid-cols-4 gap-3">
            <Metric
              label="말하기 속도"
              value={Math.round(voice.syllablesPerMinute)}
              unit="음절/분"
              note="280~340이 듣기 편한 범위"
            />
            <Metric
              label="답변 길이"
              value={voice.meanAnswerS.toFixed(1)}
              unit="초 평균"
              note={`답변 ${voice.answers.length}개 기준`}
            />
            <Metric
              label="답변 중 멈춤"
              value={Math.round(voice.pauseRatio * 100)}
              unit="%"
              note="0.35초 이상 끊긴 시간"
            />
            <Metric
              label="목소리 흔들림"
              value={voice.loudnessVariation.toFixed(2)}
              unit=""
              note="0에 가까울수록 고름"
            />
          </div>
        </section>
      )}

      {(coaching.strengths.length > 0 || coaching.improvements.length > 0) && (
        <section className="border-b border-line py-[30px]">
          <div className="mb-[18px]">
            <SectionLabel>내용 평가</SectionLabel>
          </div>
          <div className="grid grid-cols-2 gap-[14px]">
            <div className="flex flex-col gap-3">
              <div className="text-[13px] font-bold text-positive">잘한 점</div>
              {coaching.strengths.map((text) => (
                <div key={text} className="flex gap-[8px]">
                  <span className="text-[12px] text-positive">✓</span>
                  <span className="text-[13.5px] leading-[1.65] text-body-2">{text}</span>
                </div>
              ))}
            </div>
            <div className="flex flex-col gap-3">
              <div className="text-[13px] font-bold text-accent">보완할 점</div>
              {coaching.improvements.map((text) => (
                <div key={text} className="flex gap-[8px]">
                  <span className="text-[12px] text-accent">→</span>
                  <span className="text-[13.5px] leading-[1.65] text-body-2">{text}</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      <section className="py-[30px]">
        <div className="mb-[18px]">
          <SectionLabel>답변별 피드백</SectionLabel>
        </div>
        <div className="flex flex-col gap-[10px]">
          {coaching.answers.map((answer, index) => {
            const open = openQ === index
            // 음성 구간과 코칭은 같은 순서로 나온다 — 둘 다 면접 순서다.
            const span = voice?.answers[index]
            return (
              <div
                key={index}
                className="rounded-card bg-surface"
                style={{ border: `1px solid ${open ? 'var(--color-field)' : 'var(--color-line)'}` }}
              >
                <div
                  onClick={() => setOpenQ(open ? -1 : index)}
                  className="flex cursor-pointer items-center gap-[13px] px-[18px] py-[15px]"
                >
                  <span className="num w-[22px] text-[11.5px] font-semibold text-faintest">
                    Q{index + 1}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-[13.5px] font-semibold">
                    {open ? '' : answer.question}
                  </span>
                  {span && (
                    <span className="num text-[11.5px] text-faintest">
                      {(span.endS - span.startS).toFixed(1)}초
                    </span>
                  )}
                  <span className="num w-[28px] text-right text-[15px] font-bold">
                    {answer.score}
                  </span>
                  <span className="w-[12px] text-[11px] text-faintest">{open ? '▲' : '▼'}</span>
                </div>

                {open && (
                  <div className="flex animate-dm-fade flex-col gap-4 px-[18px] pt-[4px] pb-5">
                    <div className="border-t border-hair pt-4 text-[15px] leading-[1.6] font-semibold">
                      {answer.question}
                    </div>

                    {span && (
                      <>
                        <Playback
                          src={audioUrl(interviewId)}
                          startS={span.startS}
                          endS={span.endS}
                        />
                        <div className="flex flex-col gap-[6px]">
                          <span className="text-[11.5px] font-semibold text-faint">내 답변</span>
                          <p className="m-0 text-[13.5px] leading-[1.85] text-body-2">
                            {span.text}
                          </p>
                          {span.pauses > 0 && (
                            <span className="text-[11.5px] text-faintest">
                              말이 {span.pauses}번 끊겼습니다
                            </span>
                          )}
                        </div>
                      </>
                    )}

                    {answer.strength && (
                      <div className="border-l-2 border-positive pl-[15px]">
                        <div className="mb-[6px] text-[11.5px] font-bold text-positive">
                          잘한 점
                        </div>
                        <p className="m-0 text-[13.5px] leading-[1.8] text-body">
                          {answer.strength}
                        </p>
                      </div>
                    )}

                    <div className="border-l-2 border-line-2 pl-[15px]">
                      <div className="mb-[6px] text-[11.5px] font-bold text-muted">
                        더 듣고 싶었던 것
                      </div>
                      <p className="m-0 text-[13.5px] leading-[1.8] text-body">{answer.gap}</p>
                    </div>

                    <div className="border-l-2 border-accent pl-[15px]">
                      <div className="mb-[6px] text-[11.5px] font-bold text-accent">
                        이렇게 바꿔보세요
                      </div>
                      <p className="m-0 text-[13.5px] leading-[1.8] text-body">
                        {answer.suggestion}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </section>

      <div className="flex items-center">
        <button onClick={onLeave} className="text-[13px] text-muted">
          내 면접으로
        </button>
        <div className="flex-1" />
        <button
          onClick={onAgain}
          className="rounded-control bg-ink px-7 py-[13px] text-[14px] font-semibold text-white"
        >
          이 회사로 다시 면접 보기
        </button>
      </div>
    </main>
  )
}

function Metric({
  label,
  value,
  unit,
  note,
}: {
  label: string
  value: string | number
  unit: string
  note: string
}) {
  return (
    <div className="flex flex-col gap-[7px] rounded-card border border-line bg-surface p-4">
      <span className="text-[12.5px] text-muted">{label}</span>
      <div className="flex items-baseline gap-[4px]">
        <span className="num text-[23px] font-bold tracking-[-.03em]">{value}</span>
        {unit && <span className="text-[12px] text-faint">{unit}</span>}
      </div>
      <span className="text-[11.5px] leading-[1.5] text-faintest">{note}</span>
    </div>
  )
}

/**
 * 답변 한 구간만 다시 듣기.
 *
 * 녹음은 면접 전체가 한 파일이라, 구간의 시작으로 옮겨 재생하고 끝에서
 * 멈춘다. 서버가 Range 요청을 받으므로 20분짜리를 통째로 받지 않는다.
 */
function Playback({ src, startS, endS }: { src: string; startS: number; endS: number }) {
  const audio = useRef<HTMLAudioElement>(null)
  const [playing, setPlaying] = useState(false)
  const [at, setAt] = useState(startS)

  // 구간 끝에서 멈춘다. timeupdate는 250ms쯤마다 오므로 조금 지나쳐 멈춘다.
  useEffect(() => {
    const element = audio.current
    if (!element) return
    const onTime = () => {
      setAt(element.currentTime)
      if (element.currentTime >= endS) {
        element.pause()
        setPlaying(false)
      }
    }
    element.addEventListener('timeupdate', onTime)
    return () => element.removeEventListener('timeupdate', onTime)
  }, [endS])

  const toggle = () => {
    const element = audio.current
    if (!element) return
    if (playing) {
      element.pause()
      setPlaying(false)
      return
    }
    // 늘 구간 앞에서 다시 시작한다 — 끝까지 들은 뒤 또 누르는 것이 보통이다.
    if (element.currentTime < startS || element.currentTime >= endS - 0.1) {
      element.currentTime = startS
    }
    void element.play()
    setPlaying(true)
  }

  const total = endS - startS
  const done = Math.min(1, Math.max(0, (at - startS) / total))

  return (
    <div className="flex items-center gap-3 rounded-control border border-line-2 bg-surface-2 px-[13px] py-[10px]">
      <audio ref={audio} src={src} preload="none" />
      <button
        onClick={toggle}
        className="flex items-center justify-center rounded-full bg-ink text-white"
        style={{ width: 26, height: 26, fontSize: 9 }}
      >
        {playing ? '❚❚' : '▶'}
      </button>
      <div className="flex-1 bg-line-3" style={{ height: 3 }}>
        <div className="h-full bg-accent" style={{ width: `${done * 100}%` }} />
      </div>
      <span className="num text-[11.5px] text-faint">{total.toFixed(1)}초</span>
      <span className="text-[11.5px] text-muted">내 답변</span>
    </div>
  )
}
