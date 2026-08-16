import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { getPreparationStatus } from '@/api/preparation'
import { useActiveCard } from '@/store/app'

/**
 * §타이머와 인터벌 — 프로토타입의 속도는 시연용입니다.
 * 실제로는 서버 작업 진행률로 대체됩니다.
 */
function useProgress(stepMs: number, stepPct: number, onDone: () => void) {
  const [pct, setPct] = useState(0)
  useEffect(() => {
    const id = setInterval(() => {
      setPct((p) => {
        const next = Math.min(100, p + stepPct)
        if (next >= 100) {
          clearInterval(id)
          setTimeout(onDone, 250)
        }
        return next
      })
    }, stepMs)
    // 화면을 벗어날 때 모든 인터벌을 정리해야 합니다
    return () => clearInterval(id)
  }, [stepMs, stepPct, onDone])
  return pct
}

/**
 * README §7. 질문 재생성 — 검토에서 리포트를 고쳤을 때만 거칩니다. 헤더 숨김.
 *
 * 가짜 타이머가 아니라 서버 진행률을 봅니다. 생성은 실제로 Grok 호출이라
 * 몇 초 걸리고, 끝나기 전에 준비 완료 화면으로 보내면 옛 질문이 보입니다.
 */
export function Regen() {
  const nav = useNavigate()
  const card = useActiveCard()
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let alive = true
    const id = setInterval(async () => {
      try {
        const status = await getPreparationStatus(card.id)
        if (!alive) return
        if (status.status === 'done') {
          clearInterval(id)
          nav('/ready')
        } else if (status.status === 'failed') {
          clearInterval(id)
          setFailed(true)
        }
      } catch {
        // 서버가 없으면(프론트 단독 실행) 폴링이 계속 실패한다 — 화면을 붙잡고
        // 있지 말고 준비 완료로 보낸다.
        clearInterval(id)
        if (alive) nav('/ready')
      }
    }, 1000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [card.id, nav])

  return (
    <main className="mx-auto flex max-w-(--container-reg1) flex-col items-center gap-4 px-8 py-[120px] text-center">
      {!failed && (
        <span
          className="animate-dm-spin rounded-full border-line"
          style={{ width: 34, height: 34, borderWidth: 2, borderTopColor: 'var(--color-accent)' }}
        />
      )}
      <h1 className="m-0 mt-2 text-[18px] font-bold">
        {failed ? '질문을 다시 뽑지 못했습니다' : '고치신 내용으로 질문을 다시 뽑고 있습니다'}
      </h1>
      <p className="m-0 text-[13.5px] text-muted">
        {failed ? '고치신 리포트는 저장돼 있습니다.' : '잠시만 기다려 주세요'}
      </p>
      {failed && (
        <button
          onClick={() => nav('/ready')}
          className="mt-2 rounded-control border border-field bg-surface px-5 py-[10px] text-[13.5px] font-semibold"
        >
          준비 완료로 돌아가기
        </button>
      )}
    </main>
  )
}

/** README §9. 분석 중 — 헤더 숨김, 면접 화면과 같은 어두운 배경 */
export function Analyzing() {
  const nav = useNavigate()
  const pct = useProgress(70, 4, () => nav('/report'))

  return (
    <div className="fixed inset-0 z-60 flex flex-col items-center justify-center gap-[18px] bg-stage">
      <span
        className="animate-dm-breathe rounded-full border border-stage-line"
        style={{
          width: 96,
          height: 96,
          background: 'linear-gradient(160deg, #233047, #16223A)',
          animationDuration: '3s',
        }}
      />
      <h1 className="m-0 text-[19px] font-semibold text-stage-ink-2">
        면접이 끝났습니다. 수고하셨습니다
      </h1>
      <p className="m-0 text-[13.5px] text-stage-muted">답변을 분석하고 있습니다 · 약 1분</p>
      <div className="bg-stage-line-2" style={{ width: 240, height: 2.5 }}>
        <div className="h-full bg-accent" style={{ width: `${pct}%`, transition: 'width .3s ease' }} />
      </div>
    </div>
  )
}
