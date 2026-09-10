import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getCredits } from '@/api/credits'
import { useNavigate } from 'react-router'
import { useActiveCard, useAppStore } from '@/store/app'
import { useNarrow } from '@/hooks/useNarrow'
import { useCamera } from '@/video/useCamera'
import { AccentDot, CheckDot, EmptyDot, OutlineButton, SectionLabel } from '@/components/ui'
import { Avatar, Keylight } from '@/components/Stage'
import { STAGE_NAMES } from '@/data/mock'

/** 마이크가 실제로 소리를 잡았다고 볼 진폭. 0~1 정규화된 피크 기준. */
const HEARD_LEVEL = 0.12

/** 문턱 띠가 화면 전체로 커지는 시간. 끝나면 면접 화면으로 넘어간다. */
const EXPAND_MS = 460

/**
 * 시작 전 확인 (README §5).
 *
 * 마이크 항목은 실제로 입력을 받아 봐야 체크된다 — 말했을 때 막대가 움직이고
 * 그 순간 체크가 켜진다. 나머지 둘은 사용자가 직접 누른다.
 *
 * **셋을 다 마쳐야 시작할 수 있다.** 앞서는 안내일 뿐 통과 조건이 아니었는데,
 * 마이크가 소리를 못 잡은 채로 시작한 면접이 실제로 세 판 나왔다(전사에
 * 면접관 인사만 남고 지원자 답변이 0개). 크레딧을 되돌려 주더라도 사용자가
 * 쓴 시간은 돌아오지 않는다 — 시작 전에 막는 편이 싸다.
 */
function Preflight({ onReady }: { onReady: (ready: boolean) => void }) {
  const [heard, setHeard] = useState(false)
  const [testing, setTesting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [checked, setChecked] = useState<Record<string, boolean>>({})

  const bar = useRef<HTMLDivElement>(null)
  const teardown = useRef<(() => void) | null>(null)

  // 카메라 권한은 **반드시 여기서** 받는다. 면접 화면이 요청하면 첫 질문이
  // 나오는 순간 브라우저 권한 창이 뜬다. 켜 두면 면접 화면이 그대로 이어받는다.
  const camera = useCamera()
  const preview = useRef<HTMLVideoElement>(null)
  const setCameraReady = useAppStore((s) => s.setCameraReady)
  useEffect(() => {
    setCameraReady(camera.state === 'on')
  }, [camera.state, setCameraReady])
  useEffect(() => {
    const el = preview.current
    if (!el) return
    el.srcObject = camera.stream
    if (camera.stream) void el.play().catch(() => {})
  }, [camera.stream])

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

  // 시작 버튼이 이걸 보고 열린다. boolean 하나만 올려 보내므로 부모는 항목
  // 구성을 몰라도 된다 — 항목이 늘어도 여기만 고친다.
  const ready = heard && manual.every((label) => checked[label])
  useEffect(() => onReady(ready), [ready, onReady])

  return (
    <div className="mb-[26px] flex flex-col gap-3 rounded-card border border-line bg-surface p-5 shadow-card">
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

        {/* 카메라는 통과 조건이 아니다 — 없어도 면접은 된다. 다만 쓸 거라면
            권한은 여기서 받아야 한다. */}
        <div className="flex items-center gap-[9px]">
          {camera.state === 'on' ? <CheckDot size={15} /> : <EmptyDot size={15} />}
          <span
            className={`text-[13.5px] ${camera.state === 'on' ? 'text-ink' : 'text-muted'}`}
          >
            {camera.state === 'on'
              ? '카메라가 켜졌습니다'
              : camera.state === 'missing'
                ? '카메라를 찾지 못했습니다'
                : camera.state === 'denied'
                  ? '카메라 권한이 막혀 있습니다'
                  : '카메라로 내 모습을 보며 연습할 수 있습니다'}
          </span>
          <div className="flex-1" />
          <button
            onClick={() => (camera.state === 'on' ? camera.stop() : void camera.start())}
            className="border-b border-field text-[12.5px] text-muted"
          >
            {camera.state === 'on' ? '끄기' : '카메라 켜기'}
          </button>
        </div>

        {/* 얼굴이 화면에 어떻게 담기는지 여기서 확인한다. 썸네일로는 구도도
            조명도 못 본다 — 이 화면에서 카메라 항목이 하는 일이 그것뿐이라
            크게 둔다. 면접 중의 셀프뷰는 반대로 작다(SelfView 참고). */}
        {camera.state === 'on' && (
          <div className="flex flex-col items-center gap-[8px] pl-6">
            <video
              ref={preview}
              muted
              playsInline
              className="w-full max-w-[320px] rounded-card border border-line bg-surface-2 object-cover"
              style={{ aspectRatio: '4 / 3', transform: 'scaleX(-1)' }}
            />
            <span className="text-[12px] text-faint">
              얼굴이 가운데에 오고 밝은지 확인해 주세요
            </span>
          </div>
        )}

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

/**
 * 문턱 — 밝은 세계에서 어두운 무대로 들어가는 문.
 *
 * 무대 D의 정지 화면 위에 시작 버튼을 둔다. 앞서 있던 단계 카드 넷과 하단의
 * 시작 행은 여기 접어 넣었다 — 순서는 전달되고 무게는 없다. 시작을 누르면 이
 * 띠가 화면 전체로 커지면서 면접 화면이 된다(`data-threshold`로 자리를 잰다).
 *
 * 누르면 크레딧이 빠지므로 확인을 한 단계 둔다. 잔액을 작은 글씨로 적어 두는
 * 것은 안내지 확인이 아니다 — 얼마가 빠지는지 말하고 한 번 더 받는다. 모달이
 * 아니라 자리에서 펼치는 이유: 다른 확인(회원 탈퇴)과 같은 방식이고, 모달은
 * 마이크 점검 위를 덮어 버린다.
 */
function Threshold({
  company,
  role,
  ready,
  short,
  cost,
  balance,
  onStart,
}: {
  company: string
  role: string
  /** 시작 전 확인을 다 마쳤는가. */
  ready: boolean
  /** 크레딧이 모자라는가. 확인을 다 마쳐도 열리지 않는다. */
  short: boolean
  cost?: number
  balance?: number
  onStart: () => void
}) {
  const [confirming, setConfirming] = useState(false)
  // 좁은 화면은 구체 88 + 문구 한 줄, 시작 버튼 열은 100% 폭으로 아래.
  const narrow = useNarrow()
  const disabled = short || !ready
  const paperButton = { color: '#0C0F19', background: 'var(--stage-paper)' }

  return (
    <div
      data-threshold="true"
      className="relative mb-4 flex min-h-[300px] flex-col overflow-hidden rounded-card"
      style={{ background: 'var(--stage-bg)', color: 'var(--stage-ink-warm)' }}
    >
      <Keylight width={900} height={520} top="-34%" alpha={0.09} />

      <div className="relative flex items-center px-[22px] py-[18px]">
        <span
          className="rounded-full"
          style={{ width: 7, height: 7, background: 'var(--stage-amber)', boxShadow: '0 0 10px var(--stage-amber)' }}
        />
        <span className="ml-[9px] text-[13px]">면접관이 기다리고 있습니다</span>
        <div className="flex-1" />
        <span className="text-[12.5px]" style={{ color: 'var(--stage-dim)' }}>
          {company} · {role}
        </span>
      </div>

      <div className="relative flex flex-1 flex-wrap items-center gap-[18px] px-5 py-[22px] md:flex-nowrap md:gap-7 md:px-8 md:pt-[6px] md:pb-7">
        <Avatar size={narrow ? 88 : 128} speaking glow={0.5} bloom={false} />
        <div className="flex min-w-0 flex-1 basis-[160px] flex-col gap-2 break-keep md:basis-0">
          <span className="text-[20px] font-bold tracking-[-.025em]" style={{ color: 'var(--stage-paper)' }}>
            지금 면접장에 들어갑니다
          </span>
          <span className="text-[13.5px] leading-[1.65]" style={{ color: 'var(--stage-dim)' }}>
            면접은 15분 내외로 진행됩니다. 면접관에게 직무역량과 인성 · 컬처핏을 어필해보세요.
          </span>
        </div>
        <div className="flex shrink-0 basis-full flex-col items-stretch gap-[9px] md:basis-auto md:items-end">
          {disabled ? (
            <>
              <button
                disabled
                className="cursor-default rounded-control px-[34px] py-[14px] text-[15px] font-semibold"
                style={{
                  color: 'rgba(233,227,216,.35)',
                  background: 'rgba(255,255,255,.06)',
                  border: '1px solid rgba(255,255,255,.08)',
                }}
              >
                면접 시작하기
              </button>
              {/* 크레딧이 먼저다 — 확인을 다 마쳐도 시작할 수 없는 쪽이라
                  그걸 먼저 말해야 헛수고를 안 한다. */}
              <span
                className="num text-[12.5px]"
                style={{ color: short ? 'var(--stage-amber)' : 'var(--stage-dim)' }}
              >
                {short ? `크레딧이 부족합니다 · 면접에 ${cost}개 필요` : '아래 시작 전 확인을 모두 마쳐 주세요'}
              </span>
            </>
          ) : !confirming ? (
            <>
              <button
                onClick={() => setConfirming(true)}
                className="rounded-control px-[34px] py-[14px] text-[15px] font-semibold"
                style={paperButton}
              >
                면접 시작하기
              </button>
              {cost !== undefined && (
                <span className="num text-[12.5px]" style={{ color: 'var(--stage-dim)' }}>
                  크레딧 {balance}개 보유 · 면접에 {cost}개
                </span>
              )}
            </>
          ) : (
            <div
              className="flex flex-col items-stretch gap-[10px] rounded-card px-[18px] py-[14px] md:items-end"
              style={{ border: '1px solid rgba(217,168,108,.35)', background: 'rgba(217,168,108,.10)' }}
            >
              <span className="text-[13.5px]">
                면접을 시작하면 크레딧 <span className="num font-semibold">{cost}</span>개가 사용됩니다.
              </span>
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => setConfirming(false)}
                  className="rounded-control px-4 py-[10px] text-[13.5px] font-semibold"
                  style={{ border: '1px solid rgba(255,255,255,.18)' }}
                >
                  취소
                </button>
                {/* AudioContext는 이 클릭에서 비롯된다 — 사용자 동작 없이 만들면
                    자동재생 정책에 막혀 무음이 된다. useVoiceSession 참조. */}
                <button
                  onClick={onStart}
                  className="rounded-control px-6 py-[10px] text-[13.5px] font-semibold"
                  style={paperButton}
                >
                  시작하기
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 단계 줄 — 질문 개수와 소요 시간은 적지 않는다. 게이트가 매 턴 다시
          판정하므로 몇 개가 나갈지는 시작 전에 정해져 있지 않다. */}
      <div
        className="relative flex flex-wrap items-center justify-center gap-x-4 gap-y-2 px-[22px] py-3 md:gap-x-0"
        style={{ borderTop: '1px solid rgba(255,255,255,.08)' }}
      >
        {STAGE_NAMES.map((name, i) => (
          <div key={name} className="flex items-center gap-2">
            <span className="num text-[11px] font-semibold tracking-[.04em]" style={{ color: 'var(--stage-dim)' }}>
              0{i + 1}
            </span>
            <span className="text-[13px] whitespace-nowrap">{name}</span>
            {/* 연결선은 넓을 때만 — 좁으면 줄이 바뀌므로 선이 이어지지 않는다. */}
            {i < STAGE_NAMES.length - 1 && (
              <span className="mx-[14px] hidden md:block" style={{ width: 28, height: 1, background: 'rgba(255,255,255,.08)' }} />
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

/** README §5. 준비 완료 */
export function Ready() {
  const nav = useNavigate()
  const card = useActiveCard()
  const { data: credits } = useQuery({ queryKey: ['credits'], queryFn: getCredits })
  const short = credits !== undefined && credits !== null && credits.balance < credits.costs.interview
  // 시작 전 확인을 다 마쳤는가. Preflight가 올려 준다.
  const [ready, setReady] = useState(false)

  // 확장 전환 — 문턱 띠의 자리에서 시작해 화면 전체로 커지는 판. 끝나면 면접
  // 화면으로. 단일 마운트 + CSS 키프레임이라 상태 쓰기 둘이 경쟁하지 않는다.
  const [expand, setExpand] = useState<{ x: number; y: number; w: number; h: number } | null>(null)
  const enterStage = () => {
    const band = document.querySelector('[data-threshold]')
    if (!band) {
      nav('/interview')
      return
    }
    const r = band.getBoundingClientRect()
    setExpand({ x: r.left, y: r.top, w: r.width, h: r.height })
    window.setTimeout(() => nav('/interview'), EXPAND_MS)
  }

  return (
    <main className="mx-auto max-w-(--container-report) px-4 pt-7 pb-[60px] animate-dm-fade md:px-8 md:pt-[44px] md:pb-20">
      <button onClick={() => nav('/')} className="mb-4 text-[13px] text-muted">
        ← 내 면접
      </button>

      <div className="mb-[6px] flex items-center gap-[6px]">
        <AccentDot />
        <span className="text-[12px] font-semibold tracking-[.05em] text-accent">면접 준비 완료</span>
      </div>
      <h1 className="m-0 mb-[26px] break-keep text-[23px] font-bold tracking-[-.03em] md:text-[27px]">
        {card.company} · {card.role}
      </h1>

      {/* 여기서 막는다. 면접 화면까지 들어갔다가 소켓이 닫히면 마이크
          권한을 물어본 뒤에 못 한다고 말하는 꼴이 된다. */}
      <Threshold
        company={card.company}
        role={card.role}
        ready={ready}
        short={short}
        cost={credits?.costs.interview}
        balance={credits?.balance}
        onStart={enterStage}
      />

      <div className="mb-4 flex flex-col gap-[14px] rounded-card border border-line bg-surface p-5 shadow-card">
        <div className="flex items-center">
          <SectionLabel>리서치 리포트</SectionLabel>
          <div className="flex-1" />
          <span className="text-[11.5px] text-faintest">{card.date}</span>
        </div>

        <div className="flex flex-wrap items-center gap-3 border-t border-hair pt-[14px]">
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

      {/* 지원서 수정 버튼이 있던 자리. STEP 2는 등록용 초안(스토어의 parts)을
          읽지 이 면접의 지원서를 읽지 않아 빈 화면이 떴고, 그 화면의 버튼은
          "등록하고 준비 시작"이라 저장하면 새 면접이 하나 더 생겼다 —
          live 모드에서는 리서치가 한 번 더 도는 것과 같다. */}
      <Preflight onReady={setReady} />

      {expand && (
        <>
          <style>{`@keyframes dm-expand{from{left:${expand.x}px;top:${expand.y}px;width:${expand.w}px;height:${expand.h}px;border-radius:4px}to{left:0;top:0;width:100vw;height:100vh;border-radius:0}}`}</style>
          <div
            className="pointer-events-none fixed z-70"
            style={{
              left: 0,
              top: 0,
              width: '100vw',
              height: '100vh',
              background: 'var(--stage-bg)',
              animation: 'dm-expand .45s cubic-bezier(.2,.7,.2,1) both',
            }}
          />
        </>
      )}
    </main>
  )
}
