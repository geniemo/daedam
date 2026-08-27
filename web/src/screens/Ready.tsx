import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getCredits } from '@/api/credits'
import { useNavigate } from 'react-router'
import { useActiveCard } from '@/store/app'
import { AccentDot, CheckDot, EmptyDot, OutlineButton, SectionLabel } from '@/components/ui'
import { STAGE_NAMES } from '@/data/mock'

/** 마이크가 실제로 소리를 잡았다고 볼 진폭. 0~1 정규화된 피크 기준. */
const HEARD_LEVEL = 0.12

/**
 * 시작 전 확인 (README §5).
 *
 * 마이크 항목은 실제로 입력을 받아 봐야 체크된다 — 말했을 때 막대가 움직이고
 * 그 순간 체크가 켜진다. 나머지 둘은 사용자가 직접 누른다. 확인하지 않아도
 * 시작은 막지 않는다. 지원자가 준비됐다고 판단하는 것이 이 목록의 목적이지
 * 통과 조건이 아니다.
 */
function Preflight() {
  const [heard, setHeard] = useState(false)
  const [testing, setTesting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [checked, setChecked] = useState<Record<string, boolean>>({})

  const bar = useRef<HTMLDivElement>(null)
  const teardown = useRef<(() => void) | null>(null)

  // 화면을 벗어나면 마이크를 반드시 놓는다 — 안 놓으면 면접 화면이 마이크를
  // 다시 잡을 때 브라우저 표시가 둘이 되고, 탭이 계속 녹음 중으로 남는다.
  useEffect(() => () => teardown.current?.(), [])

  const test = useCallback(async () => {
    setError(null)
    teardown.current?.()
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const ctx = new AudioContext()
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 256
      ctx.createMediaStreamSource(stream).connect(analyser)
      const buf = new Uint8Array(analyser.frequencyBinCount)

      let raf = 0
      const loop = () => {
        analyser.getByteFrequencyData(buf as Uint8Array<ArrayBuffer>)
        let max = 0
        for (let i = 0; i < buf.length; i++) if (buf[i] > max) max = buf[i]
        const level = max / 255
        // 진폭은 React state를 거치지 않는다 — 60fps로 바뀌는 값이라
        // ref → style이 원칙이다 (Interview.tsx의 파형과 같은 이유).
        if (bar.current) bar.current.style.width = `${Math.round(level * 100)}%`
        if (level >= HEARD_LEVEL) setHeard(true)
        raf = requestAnimationFrame(loop)
      }
      raf = requestAnimationFrame(loop)

      teardown.current = () => {
        cancelAnimationFrame(raf)
        stream.getTracks().forEach((t) => t.stop())
        void ctx.close()
        teardown.current = null
      }
      setTesting(true)
    } catch {
      // 권한 거부·장치 없음 모두 여기로 온다. 조용히 넘어가면 면접에서
      // 무음으로 드러나므로 화면에 말한다.
      setError('마이크를 열 수 없습니다. 브라우저 권한을 확인해 주세요.')
    }
  }, [])

  const stop = useCallback(() => {
    teardown.current?.()
    setTesting(false)
    if (bar.current) bar.current.style.width = '0%'
  }, [])

  const manual = ['조용한 곳에서 진행합니다', '중간에 그만두면 그때까지의 답변으로 리포트를 받습니다']

  return (
    <div className="mb-[26px] flex flex-col gap-3 rounded-card border border-line bg-surface p-5">
      <SectionLabel>시작 전 확인</SectionLabel>
      <div className="flex flex-col gap-[10px]">
        <div className="flex items-center gap-[9px]">
          {heard ? <CheckDot size={15} /> : <EmptyDot size={15} />}
          <span className={`text-[13.5px] ${heard ? 'text-ink' : 'text-muted'}`}>
            {heard ? '마이크가 소리를 잡았습니다' : '마이크를 테스트해 주세요'}
          </span>
          <div className="flex-1" />
          {testing && (
            <div className="bg-hair-2" style={{ width: 90, height: 4 }}>
              <div ref={bar} className="h-full bg-accent" style={{ width: '0%' }} />
            </div>
          )}
          <button
            onClick={testing ? stop : test}
            className="border-b border-field text-[12.5px] text-muted"
          >
            {testing ? '테스트 끝내기' : '테스트하기'}
          </button>
        </div>

        {testing && !heard && (
          <p className="m-0 pl-6 text-[12px] text-faint">아무 말이나 해보세요 — 막대가 움직이면 됩니다.</p>
        )}
        {error && <p className="m-0 pl-6 text-[12px] text-accent">{error}</p>}

        {manual.map((label) => (
          <button
            key={label}
            onClick={() => setChecked((c) => ({ ...c, [label]: !c[label] }))}
            className="flex items-center gap-[9px] text-left"
          >
            {checked[label] ? <CheckDot size={15} /> : <EmptyDot size={15} />}
            <span className={`text-[13.5px] ${checked[label] ? 'text-ink' : 'text-muted'}`}>
              {label}
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}

/** README §5. 준비 완료 */
/**
 * 면접 시작 — 누르면 크레딧이 빠지므로 확인을 한 단계 둔다.
 *
 * 리포트의 "이 회사로 다시 면접 보기"에서 두 번만 누르면 여기까지 오는데,
 * 시작하는 순간 되돌릴 수 없는 차감이 일어난다. 잔액을 작은 글씨로 적어 두는
 * 것은 안내지 확인이 아니다 — 얼마가 빠지는지 말하고 한 번 더 받는다.
 *
 * 모달이 아니라 자리에서 펼치는 이유: 이 화면의 다른 확인(회원 탈퇴)과 같은
 * 방식이고, 모달은 마이크 점검 화면 위를 덮어 버린다.
 */
function StartInterview({
  cost,
  balance,
  onStart,
}: {
  cost?: number
  balance?: number
  onStart: () => void
}) {
  const [confirming, setConfirming] = useState(false)

  if (!confirming) {
    return (
      <>
        <button
          onClick={() => setConfirming(true)}
          className="rounded-control bg-ink px-[34px] py-[14px] text-[15px] font-semibold text-white"
        >
          면접 시작하기
        </button>
        {cost !== undefined && (
          <span className="text-[12.5px] text-faint">
            크레딧 {balance}개 보유 · 면접에 {cost}개
          </span>
        )}
      </>
    )
  }

  return (
    <div className="flex flex-col items-end gap-[10px] rounded-card border border-accent-line bg-accent-bg px-[18px] py-[14px]">
      <span className="text-[13.5px] text-body-2">
        면접을 시작하면 크레딧 <span className="num font-semibold">{cost}</span>개가
        사용됩니다.
      </span>
      <div className="flex items-center gap-[8px]">
        <OutlineButton
          onClick={() => setConfirming(false)}
          className="px-[16px] py-[10px] text-[13.5px]"
        >
          취소
        </OutlineButton>
        {/* AudioContext는 이 클릭 핸들러 안에서 생성됩니다 — 밖에서 만들면
            자동재생 정책에 막혀 무음이 됩니다. useVoiceSession 참조. */}
        <button
          onClick={onStart}
          className="rounded-control bg-ink px-[24px] py-[10px] text-[13.5px] font-semibold text-white"
        >
          시작하기
        </button>
      </div>
    </div>
  )
}

export function Ready() {
  const nav = useNavigate()
  const card = useActiveCard()
  const { data: credits } = useQuery({ queryKey: ['credits'], queryFn: getCredits })
  const short = credits !== undefined && credits !== null && credits.balance < credits.costs.interview

  return (
    <main className="mx-auto max-w-(--container-doc) px-8 pt-[44px] pb-20 animate-dm-fade">
      <button onClick={() => nav('/')} className="mb-4 text-[13px] text-muted">
        ← 내 면접
      </button>

      <div className="mb-[6px] flex items-center gap-[6px]">
        <AccentDot />
        <span className="text-[12px] font-semibold tracking-[.05em] text-accent">면접 준비 완료</span>
      </div>
      <h1 className="m-0 text-[27px] font-bold tracking-[-.03em]">
        {card.company} · {card.role}
      </h1>
      <p className="mt-[10px] mb-[30px] text-[14px] text-muted">
        채용공고와 최근 소식, 지원서를 함께 읽고 질문을 준비했습니다. 아래 네 가지와 관련된
        질문을 한국어 음성으로 주고받습니다.
      </p>

      <div className="mb-4 grid grid-cols-4 gap-[10px]">
        {STAGE_NAMES.map((name, i) => (
          <div
            key={name}
            className="flex flex-col gap-[5px] rounded-card border border-line bg-surface px-[14px] py-[15px]"
          >
            {/* 질문 개수와 소요 시간은 적지 않는다. 게이트가 매 턴 다시
                판정하므로 몇 개가 나갈지는 시작 전에 정해져 있지 않다. */}
            <span className="num text-[11.5px] font-semibold text-faintest">0{i + 1}</span>
            <span className="text-[14px] font-bold">{name}</span>
          </div>
        ))}
      </div>

      <div className="mb-4 flex flex-col gap-[14px] rounded-card border border-line bg-surface p-5">
        <div className="flex items-center">
          <SectionLabel>리서치 리포트</SectionLabel>
          <div className="flex-1" />
          <span className="text-[11.5px] text-faintest">{card.date}</span>
        </div>

        <div className="flex items-center border-t border-hair pt-[14px]">
          <div className="flex flex-col gap-[5px]">
            <span className="text-[14.5px] font-bold">
              {card.company} 면접 준비 리서치
            </span>
            <span className="text-[12.5px] text-muted">
              사실과 다른 대목은 직접 고칠 수 있습니다
            </span>
          </div>
          <div className="flex-1" />
          <OutlineButton onClick={() => nav('/review')} className="px-[14px] py-[9px] text-[12.5px]">
            리포트 검토
          </OutlineButton>
        </div>
      </div>

      <Preflight />

      {/* 지원서 수정 버튼이 있던 자리. STEP 2는 등록용 초안(스토어의 parts)을
          읽지 이 면접의 지원서를 읽지 않아 빈 화면이 떴고, 그 화면의 버튼은
          "등록하고 준비 시작"이라 저장하면 새 면접이 하나 더 생겼다 —
          live 모드에서는 리서치가 한 번 더 도는 것과 같다. */}
      <div className="flex items-center">
        <div className="flex-1" />
        <div className="flex flex-col items-end gap-[9px]">
          {/* 여기서 막는다. 면접 화면까지 들어갔다가 소켓이 닫히면 마이크
              권한을 물어본 뒤에 못 한다고 말하는 꼴이 된다. */}
          {short ? (
            <>
              <button
                disabled
                className="rounded-control bg-faintest px-[34px] py-[14px] text-[15px] font-semibold text-white"
              >
                면접 시작하기
              </button>
              <span className="text-[12.5px] text-accent">
                크레딧이 부족합니다 · 면접에 {credits?.costs.interview}개 필요
              </span>
            </>
          ) : (
            <StartInterview
              cost={credits?.costs.interview}
              balance={credits?.balance}
              onStart={() => nav('/interview')}
            />
          )}
        </div>
      </div>
    </main>
  )
}
