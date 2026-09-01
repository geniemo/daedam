import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { getFeedback, getPreparationStatus } from '@/api/preparation'
import { useActiveCard } from '@/store/app'

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

/**
 * README §9. 분석 중 — 헤더 숨김, 면접 화면과 같은 어두운 배경
 *
 * 가짜 타이머가 아니라 서버를 기다린다. 지표 계산은 순식간이지만 코칭은 Grok
 * 호출이라 수십 초 걸린다. 타이머로 넘기면 아직 없는 리포트를 열게 된다.
 */
export function Analyzing() {
  const nav = useNavigate()
  const card = useActiveCard()
  const queryClient = useQueryClient()
  // 기다려도 결과가 오지 않는 경우가 둘이고 할 말이 다르다 — 만들다 실패한
  // 것과, 한 마디도 안 해서 만들 것이 없는 것. 후자에는 되돌린 크레딧까지
  // 같이 들고 있는다(서버 원장이 알려 준다 — 짐작으로 안심시키지 않는다).
  const [stopped, setStopped] = useState<{ silent: boolean; refunded: boolean } | null>(null)

  useEffect(() => {
    let alive = true
    // 면접이 끝나면 두 가지가 이미 바뀌어 있다 — 시작할 때 빠진 크레딧과,
    // 방금 늘어난 면접 횟수. 캐시를 비우지 않으면 헤더의 잔액과 홈 카드가
    // 새로고침 전까지 옛 값을 보여준다.
    const refresh = () => queryClient.invalidateQueries()
    const timer = setInterval(async () => {
      try {
        const status = await getFeedback(card.id)
        if (!alive) return
        if (status.status === 'done') {
          clearInterval(timer)
          await refresh()
          nav('/report')
        } else if (status.status !== 'running') {
          // 기다려서 해결되지 않는 상태다(failed·silent·absent). 화면을 붙잡고
          // 있지 않는다. 무응답이면 브리지가 크레딧을 되돌려 두었으므로,
          // 실패든 아니든 잔액은 갱신해야 헤더가 옛 값을 보여주지 않는다.
          clearInterval(timer)
          await refresh()
          setStopped({
            silent: status.status === 'silent',
            refunded: status.refunded === true,
          })
        }
      } catch {
        // 서버가 없으면(프론트 단독 실행) 목업 리포트라도 보여준다.
        clearInterval(timer)
        if (alive) nav('/report')
      }
    }, 1500)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [card.id, nav, queryClient])

  if (stopped) {
    // 면접 화면과 같은 어두운 배경 위다. 여기서 리포트로 보내면 같은 말을 다시
    // 만나므로, 무엇이 일어났는지 여기서 말하고 나가는 길만 준다.
    const { silent, refunded } = stopped
    return (
      <div className="fixed inset-0 z-60 flex flex-col items-center justify-center gap-[18px] bg-stage px-8 text-center">
        {silent && (
          /* 눕은 파형 — 조금 전까지 이 자리에서 움직이던 막대다. */
          <div className="flex items-center" style={{ gap: 3, height: 20 }}>
            {Array.from({ length: 16 }, (_, i) => (
              <div key={i} className="bg-stage-line" style={{ width: 3, height: 2 }} />
            ))}
          </div>
        )}
        <h1 className="m-0 text-[19px] font-semibold text-stage-ink-2">
          {silent ? '답변이 녹음되지 않았습니다' : '분석 결과를 만들지 못했습니다'}
        </h1>
        <p className="m-0 max-w-[420px] text-[13.5px] leading-[1.8] text-stage-muted">
          {silent
            ? `${refunded ? '크레딧은 돌려드렸습니다. ' : ''}마이크를 확인한 뒤 다시 시작해 주세요.`
            : '녹음과 전사는 남아 있습니다. 잠시 뒤 리포트를 다시 열어 보세요.'}
        </p>
        <button
          onClick={() => nav('/')}
          className="mt-2 rounded-control border border-stage-line px-5 py-[10px] text-[13.5px] font-semibold text-stage-ink-2"
        >
          내 면접으로
        </button>
      </div>
    )
  }

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
      {/* 진행률을 만들지 않는다. 코칭이 언제 끝날지 서버도 모른다 — 끝나면
          바로 넘어가므로 막대가 차오르는 그림은 약속만 하고 못 지킨다. */}
      <p className="m-0 text-[13.5px] text-stage-muted">답변을 분석하고 있습니다</p>
      <div className="overflow-hidden bg-stage-line-2" style={{ width: 240, height: 2.5 }}>
        <div className="animate-dm-slide h-full bg-accent" style={{ width: '25%' }} />
      </div>
    </div>
  )
}
