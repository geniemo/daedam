import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { getPreparationStatus } from '@/api/preparation'
import { useActiveCard, useAppStore } from '@/store/app'
import { CheckDot, IndeterminateBar, ProgressBar, SectionLabel, Spinner } from '@/components/ui'

/**
 * README §4. 리서치 진행
 *
 * 이 화면이 보여줄 수 있는 것은 실측으로 정해졌다. Deep Research는 **진행 중에
 * 아무것도 내보내지 않는다** — 15초 간격으로 6분 30초를 물었는데 스텝이
 * user_input 하나에서 안 변했고, 완료되는 순간 다섯 개가 한꺼번에 나타났다.
 * 진행률 필드도 없다(Interaction 타입에 없음).
 *
 * 그래서 진행 중에 참인 것은 둘뿐이다: 상태(조사 중)와 경과 시간. 나머지를
 * 채우려 들면 예전의 가짜 5단계로 돌아간다. 대신 "지금은 세부가 안 보인다"를
 * 화면이 직접 말한다 — 안 그러면 멈춘 것처럼 읽힌다.
 *
 * 조사 목록은 서버가 줄 때만 그린다(fixture, 또는 나중에 스트리밍이 되면).
 */
export function Research() {
  const nav = useNavigate()
  const card = useActiveCard()
  const setCardProgress = useAppStore((s) => s.setCardProgress)
  // pct는 서버가 알 때만 온다. Deep Research는 진행률을 주지 않으므로
  // live에서는 null이고, 그때 막대를 그리지 않는다.
  const [pct, setPct] = useState<number | null>(card.pct ?? null)
  const [activity, setActivity] = useState<string[]>([])
  const [phase, setPhase] = useState('')
  const [elapsed, setElapsed] = useState(0)
  const [failed, setFailed] = useState(false)
  const feed = useRef<HTMLDivElement>(null)

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
          const next = Math.min(100, (p ?? 0) + 2)
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
          if (s.pct !== null) setCardProgress(card.id, s.pct)
          if (s.activity) setActivity(s.activity)
          if (s.phase) setPhase(s.phase)
          if (s.elapsedS !== undefined) setElapsed(s.elapsedS)
          if (s.status === 'done') finish()
          if (s.status === 'failed') {
            // 실패를 말하지 않으면 화면이 0%인 채로 얼어붙어 멈춘 것처럼
            // 보인다. 실제로 폴링이 한 번 삐끗했을 때 그렇게 보였다.
            clearInterval(timer)
            setFailed(true)
          }
        })
        .catch(advanceLocally)
    }, 1000)
    return () => clearInterval(timer)
  }, [card.id, nav, setCardProgress])

  // 새 단계가 들어오면 목록 바닥으로 따라간다 — 지금 하는 일이 마지막 줄이라
  // 스크롤이 위에 머물면 새로 들어온 줄을 못 본다.
  useEffect(() => {
    const box = feed.current
    if (box) box.scrollTop = box.scrollHeight
  }, [activity.length])

  // 남은 시간은 적지 않는다. Deep Research는 진행률을 주지 않고 통상 20~60분이라
  // 분 단위로 약속하면 매번 어긋난다. 대신 경과 시간은 사실이라 그대로 쓴다.
  const elapsedLabel = `${Math.floor(elapsed / 60)}분 ${Math.floor(elapsed % 60)}초 경과`
  const stateLabel = failed ? '중단됨' : phase || '준비 중'

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
          {/* 퍼센트는 서버가 알 때만 보여줍니다. 모를 때 경과 시간으로 어림한
              숫자를 띄우면 매 회차 어긋난 진행률을 약속하게 됩니다. */}
          <div className="flex flex-col items-end gap-[3px]">
            {pct === null || failed ? (
              <div className={`text-[15px] font-semibold ${failed ? 'text-muted' : 'text-accent'}`}>
                {stateLabel}
              </div>
            ) : (
              <div className="num text-[22px] font-bold text-accent">{pct}%</div>
            )}
            <div className="num text-[12px] text-faint">
              {elapsed > 0 && !failed ? elapsedLabel : ''}
            </div>
          </div>
        </div>

        <div className="mb-[26px]">
          {failed ? (
            <div className="w-full bg-hair-2" style={{ height: 3 }} />
          ) : pct === null ? (
            <>
              <IndeterminateBar />
              {activity.length > 0 && (
                <div className="num mt-[8px] text-[12px] text-faint">
                  조사 {activity.length}단계 진행
                </div>
              )}
            </>
          ) : (
            <ProgressBar pct={pct} />
          )}
        </div>

        <SectionLabel>조사 진행 상황</SectionLabel>

        {/* 조사가 길어지면 단계가 스무 줄 넘게 쌓인다. 화면을 통째로 늘리는
            대신 이 상자 안에서만 스크롤한다. */}
        <div ref={feed} className="mt-2 mb-4 max-h-[320px] overflow-y-auto">
          {failed ? (
            <div className="flex flex-col gap-[8px] py-[13px]">
              <span className="text-[14px] font-semibold">준비가 중단되었습니다</span>
              <span className="text-[13px] leading-[1.6] text-muted">
                조사가 진행 중이었다면 서버가 다시 시작될 때 이어서 받습니다. 홈에서 이 면접을
                다시 열어 확인해 주세요.
              </span>
            </div>
          ) : activity.length === 0 ? (
            // Deep Research는 진행 중에 세부를 공개하지 않습니다. 채울 수 없는
            // 목록을 걸어 두면 멈춘 것처럼 보이므로, 그 사실을 그대로 말합니다.
            <div className="flex flex-col gap-[8px] py-[13px]">
              <div className="flex items-center gap-[13px]">
                <Spinner />
                <span className="text-[14px] font-semibold text-accent">
                  조사를 시작하고 있습니다
                </span>
              </div>
              <span className="pl-[29px] text-[12.5px] leading-[1.6] text-faint">
                보통 10~40분 걸립니다. 조사 에이전트가 단계를 넘길 때마다 여기에 쌓입니다.
              </span>
            </div>
          ) : (
            // 마지막 줄이 지금 하는 일, 나머지는 이미 한 일. 앞으로 무엇을 할지는
            // 우리도 모르므로 대기 항목을 두지 않는다. 줄은 조사 에이전트가 자기
            // 단계에 붙인 제목 그대로다 — 우리가 지어낸 이름이 아니다.
            activity.map((line, i) => {
              const current = i === activity.length - 1
              return (
                <div key={`${i}-${line}`} className="flex gap-[13px] border-b border-hair py-[13px]">
                  <div className="pt-[2px]">{current ? <Spinner /> : <CheckDot />}</div>
                  <div
                    className={`text-[13.5px] leading-[1.5] ${
                      current ? 'font-semibold text-accent' : 'text-muted'
                    }`}
                  >
                    {line}
                  </div>
                </div>
              )
            })
          )}
        </div>

        {failed ? (
          <button
            onClick={() => nav('/')}
            className="rounded-control border border-field bg-surface px-5 py-[10px] text-[13.5px] font-semibold"
          >
            내 면접으로 돌아가기
          </button>
        ) : (
          <div className="rounded-control border border-hair-2 bg-surface-2 px-[15px] py-[13px] text-[12.5px] text-muted">
            창을 닫아도 준비는 계속됩니다. 완료되면 알려드립니다.
          </div>
        )}
      </div>
    </main>
  )
}
