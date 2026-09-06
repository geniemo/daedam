import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { getPreparationStatus } from '@/api/preparation'
import { useActiveCard, useAppStore } from '@/store/app'
import { Icon } from '@/components/ui'
import { Avatar, Keylight, StageBar } from '@/components/Stage'

/**
 * README §4. 리서치 진행 — 면접관이 준비하는 무대.
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
 * 기다림은 무대 위에서다 — 구체가 어둡게 "읽고 있는" 옆에 진행 로그가 쌓이면
 * 기다림이 면접관의 준비로 읽힌다.
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

  return (
    <main className="mx-auto max-w-(--container-report) px-8 pt-[44px] pb-20 animate-dm-fade">
      <button onClick={() => nav('/')} className="mb-4 text-[13px] text-muted">
        ← 내 면접
      </button>

      <div
        className="relative grid min-h-[360px] overflow-hidden rounded-card"
        style={{
          gridTemplateColumns: '300px minmax(0, 1fr)',
          background: 'var(--stage-bg)',
          color: 'var(--stage-ink-warm)',
        }}
      >
        <Keylight width={700} height={400} top="-40%" left="30%" alpha={0.07} />

        {/* 왼쪽 — 면접관. 불이 잦아든 채 자료를 읽고 있다. */}
        <div className="relative flex flex-col items-center justify-center gap-[22px] p-7 text-center">
          <Avatar size={128} speaking glow={failed ? 0.08 : 0.22} bloom={false} />
          <div className="flex flex-col gap-[6px]">
            <span className="text-[15px] font-semibold" style={{ color: 'var(--stage-paper)' }}>
              {failed ? '준비가 중단되었습니다' : '면접관이 준비하고 있습니다'}
            </span>
            {!failed && (
              <span className="num text-[12px]" style={{ color: 'var(--stage-dim)' }}>
                {elapsed > 0 ? `${elapsedLabel} · ` : ''}창을 닫아도 계속됩니다
              </span>
            )}
          </div>
        </div>

        {/* 오른쪽 — 진행 로그. */}
        <div className="relative flex flex-col pt-[26px] pr-7 pb-[26px]">
          <div className="mb-[14px] flex items-baseline">
            <span className="text-[17px] font-bold tracking-[-.02em]" style={{ color: 'var(--stage-paper)' }}>
              {card.company}
            </span>
            <span className="ml-2 text-[12.5px]" style={{ color: 'var(--stage-dim)' }}>
              {card.role}
            </span>
            <div className="flex-1" />
            {/* 퍼센트는 서버가 알 때만 보여준다. 모를 때 경과 시간으로 어림한
                숫자를 띄우면 매 회차 어긋난 진행률을 약속하게 된다. */}
            <span className="num text-[12.5px]" style={{ color: failed ? 'var(--stage-dim-2)' : 'var(--stage-amber)' }}>
              {failed ? '중단됨' : pct === null ? phase || '준비 중' : `${pct}%`}
            </span>
          </div>

          <div className="mb-[14px]">
            {failed ? (
              <div style={{ height: 2, background: 'rgba(255,255,255,.08)' }} />
            ) : (
              <StageBar pct={pct} />
            )}
          </div>

          {/* 조사가 길어지면 단계가 스무 줄 넘게 쌓인다. 화면을 통째로 늘리는
              대신 이 상자 안에서만 스크롤한다. */}
          <div ref={feed} className="max-h-[320px] overflow-y-auto">
            {failed ? (
              <div className="flex flex-col items-start gap-[10px] py-[9px]">
                <span className="text-[13.5px] leading-[1.6]" style={{ color: 'var(--stage-dim)' }}>
                  조사가 진행 중이었다면 서버가 다시 시작될 때 이어서 받습니다. 홈에서 이 면접을
                  다시 열어 확인해 주세요.
                </span>
                <button
                  onClick={() => nav('/')}
                  className="mt-1 rounded-full px-5 py-[10px] text-[13.5px] font-semibold"
                  style={{ border: '1px solid var(--stage-line-warm)' }}
                >
                  내 면접으로 돌아가기
                </button>
              </div>
            ) : activity.length === 0 ? (
              // Deep Research는 진행 중에 세부를 공개하지 않는다. 채울 수 없는
              // 목록을 걸어 두면 멈춘 것처럼 보이므로, 그 사실을 그대로 말한다.
              <div className="flex gap-3 py-[9px]">
                <StageDot state="now" />
                <div className="flex flex-col gap-[2px]">
                  <span className="text-[13.5px] font-semibold" style={{ color: 'var(--stage-amber)' }}>
                    조사를 시작하고 있습니다
                  </span>
                  <span className="text-[12px] leading-[1.6]" style={{ color: 'var(--stage-dim)' }}>
                    보통 10~40분 걸립니다. 조사 에이전트가 단계를 넘길 때마다 여기에 쌓입니다.
                  </span>
                </div>
              </div>
            ) : (
              // 마지막 줄이 지금 하는 일, 나머지는 이미 한 일. 앞으로 무엇을 할지는
              // 우리도 모르므로 대기 항목을 두지 않는다. 줄은 조사 에이전트가 자기
              // 단계에 붙인 제목 그대로다 — 우리가 지어낸 이름이 아니다.
              activity.map((line, i) => {
                const current = i === activity.length - 1
                return (
                  <div
                    key={`${i}-${line}`}
                    className="flex gap-3 py-[9px]"
                    style={{ borderBottom: current ? undefined : '1px solid rgba(255,255,255,.07)' }}
                  >
                    <StageDot state={current ? 'now' : 'done'} />
                    <span
                      className="text-[13.5px] leading-[1.5] font-semibold"
                      style={{ color: current ? 'var(--stage-amber)' : 'var(--stage-ink-warm)', transition: 'color .3s' }}
                    >
                      {line}
                    </span>
                  </div>
                )
              })
            )}
          </div>
        </div>
      </div>
    </main>
  )
}

/** 무대 위의 행 표식 — 끝난 단계는 앰버로 채우고, 지금 것은 앰버 링이 돈다. */
function StageDot({ state }: { state: 'done' | 'now' }) {
  return (
    <span
      className="mt-[3px] flex shrink-0 items-center justify-center rounded-full"
      style={{
        width: 13,
        height: 13,
        border: state === 'now' ? '1.5px solid var(--stage-amber)' : 0,
        borderTopColor: state === 'now' ? 'transparent' : undefined,
        background: state === 'done' ? 'var(--stage-amber)' : 'transparent',
        animation: state === 'now' ? 'dm-spin 1s linear infinite' : 'none',
      }}
    >
      {state === 'done' && <Icon name="check" size={8} stroke={3} color="#0C0F19" />}
    </span>
  )
}
