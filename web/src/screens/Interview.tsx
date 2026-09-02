import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { useActiveCard, useAppStore } from '@/store/app'
import { formatClock, useInterviewStore } from '@/store/interview'
import { useVoiceSession, type Levels } from '@/audio/useVoiceSession'
import { fill } from '@/data/mock'
import { useCamera } from '@/video/useCamera'
import { SelfView } from '@/video/SelfView'
import { useRecorder } from '@/video/useRecorder'
import { useSnapshots } from '@/video/useSnapshots'
import { useFaceTracking } from '@/video/useFaceTracking'
import { useGazeLog } from '@/video/useGazeLog'

/** README §8. 면접 진행 — 화면이 시선을 뺏지 않는 것이 목표입니다. */
export function Interview({ showCaption = true }: { showCaption?: boolean }) {
  const nav = useNavigate()
  const card = useActiveCard()

  // 진행 상태는 전부 서버가 내려준 것입니다 (§/ws/interview의 session·question
  // 메시지). 화면이 자체 대본을 그리면 실제 면접과 어긋납니다 — 면접관은
  // 뼈대질문을 그대로 읽지 않고, 꼬리질문에는 대본 자체가 없습니다.
  //
  // 단계와 남은 시간은 보여주지 않습니다. 면접을 끝내는 것은 지원자의 버튼이라
  // "남은 시간"이 없고, 단계는 서버가 질문을 고르는 내부 사정이지 지원자가
  // 의식할 것이 아닙니다 — 실제 면접에서도 "지금은 인성 단계입니다"라고 알려
  // 주지 않습니다.
  const phase = useInterviewStore((s) => s.phase)
  const caption = useInterviewStore((s) => s.caption)
  // 화면에 번호로 띄우지는 않는다. 새 뼈대질문마다 자막 fade를 다시 돌리는
  // key로만 쓴다.
  const askedCount = useInterviewStore((s) => s.askedCount)
  const elapsed = useInterviewStore((s) => s.elapsed)
  const connection = useInterviewStore((s) => s.connection)

  // 크레딧이 없어 면접이 열리지도 않은 경우는 분석할 것이 없다 — 홈으로
  // 돌려보낸다. 그 밖에는 정상 종료라 결과를 기다린다.
  const onFinished = useCallback(
    (reason?: string) => nav(reason === 'credits' ? '/' : '/analyzing'),
    [nav],
  )
  const { levels, end, micStream } = useVoiceSession(card.id, onFinished)

  // 카메라는 음성 세션과 따로 돈다 — 못 켜도 면접은 그대로 진행된다.
  //
  // **여기서 권한을 요청하지 않는다.** 시작 전 확인에서 이미 켰을 때만 이어
  // 받는다(store의 cameraReady). 면접이 시작되는 순간 브라우저 권한 창이 뜨면
  // 첫 질문을 놓친다.
  const cameraReady = useAppStore((s) => s.cameraReady)
  const camera = useCamera()
  const [selfVisible, setSelfVisible] = useState(true)
  useEffect(() => {
    if (cameraReady) void camera.start()
  }, [cameraReady, camera.start])

  // 녹화는 서버가 판 id를 알려준 뒤에 시작한다. 그전에 올리면 어느 판인지
  // 정할 수 없어 404가 나고, 그 404가 녹화를 영구히 죽인다(useRecorder 참고).
  const sessionId = useInterviewStore((s) => s.sessionId)
  // 경과 시간은 store에서 읽되 **구독하지 않는다** — 매초 바뀌는 값이라
  // 구독하면 녹화 훅의 의존성이 초마다 흔들려 MediaRecorder가 다시 선다.
  const elapsedNow = useCallback(() => useInterviewStore.getState().elapsed, [])
  useRecorder(
    camera.stream,
    sessionId ? `/api/interviews/${card.id}/video?session=${sessionId}` : null,
    micStream,
    elapsedNow,
  )

  // 시선·표정은 정면 기준을 잡은 경우에만 잰다. 기준이 없으면 "벗어났다"의
  // 원점이 없어서 그럴듯한 헛숫자가 나온다.
  const baseline = useAppStore((s) => s.baseline)
  const face = useFaceTracking(camera.stream, camera.state === 'on' && baseline !== null)
  const gaze = useGazeLog(face.latest, baseline, elapsedNow)

  // 표정 판독용 스냅샷. 녹화와 별개로 3초마다 한 장 — 서버가 영상 디코더 없이
  // Gemini로 판독하도록 화면이 프레임을 직접 보낸다. 시선과 달리 기준선이
  // 필요 없어서 카메라만 켜져 있으면 찍는다.
  useSnapshots(
    camera.stream,
    sessionId ? `/api/interviews/${card.id}/frames?session=${sessionId}` : null,
    face.latest,
    elapsedNow,
  )

  // 주기적으로 통째로 덮어쓴다. 영상과 달리 이어 붙이는 것이 아니라 순서를
  // 걱정할 필요가 없고, 창을 닫아도 마지막으로 올린 데까지는 남는다.
  useEffect(() => {
    if (!sessionId || !baseline) return
    const url = `/api/interviews/${card.id}/gaze?session=${sessionId}`
    const put = () => {
      const log = gaze.snapshot()
      if (!log) return
      void fetch(url, {
        method: 'PUT',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(log),
      }).catch(() => {
        // 실패해도 다음 주기에 통째로 다시 보낸다 — 놓친 조각이라는 개념이 없다.
      })
    }
    const timer = window.setInterval(put, 30_000)
    return () => {
      window.clearInterval(timer)
      put() // 면접이 끝나는 순간의 마지막 한 번
    }
  }, [card.id, sessionId, baseline, gaze])

  return (
    <div className="fixed inset-0 z-60 flex flex-col bg-stage">
      {/* 상단 오버레이 */}
      <div className="absolute top-0 right-0 left-0 z-3 flex items-center px-[30px] py-[22px]">
        <div className="flex items-center gap-[8px]">
          <span
            className="rounded-full"
            style={{
              width: 6,
              height: 6,
              background: phase === 'speaking' ? 'var(--color-accent)' : 'var(--color-listening)',
            }}
          />
          <span className="text-[13.5px] text-stage-ink">
            {phase === 'speaking' ? '면접관이 말하고 있습니다' : '듣고 있습니다'}
          </span>
          {connection === 'reconnecting' && (
            <span className="text-[12.5px] text-stage-muted-3">· 연결을 복구하는 중입니다</span>
          )}
        </div>
        <div className="flex-1" />
        <span className="num text-[13px] text-stage-ink">{formatClock(elapsed)}</span>
      </div>

      {/* 무대의 중심. 없으면 어두운 판 위에 원이 떠 있기만 한다. */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            'radial-gradient(58% 44% at 50% 42%, rgba(35,48,71,.6), transparent 70%)',
        }}
      />

      {/* 아바타 영역 */}
      <div className="relative flex flex-1 items-center justify-center">
        <Avatar levels={levels} speaking={phase === 'speaking'} />
        <SelfView
          camera={camera}
          visible={selfVisible}
          measuring={baseline !== null}
          onHide={() => setSelfVisible((v) => !v)}
          onStop={camera.stop}
        />
      </div>

      {/* 자막 — 면접관이 실제로 하고 있는 말. 뼈대질문 문장이 아닙니다.
          자리를 늘 비워 둔다. 조건부로 넣고 빼면 위의 flex-1이 밀려서
          자막이 바뀔 때마다 아바타가 위아래로 튄다. */}
      <div className="relative mx-auto flex min-h-[92px] max-w-[660px] items-start justify-center px-8">
        {showCaption && caption && (
          <p
            key={askedCount}
            className="m-0 animate-dm-fade-slow text-center text-[17px] leading-[1.65] font-medium tracking-[-.01em] text-stage-ink"
          >
            {fill(caption, card.company, card.role)}
          </p>
        )}
      </div>

      {/* 하단 상태 영역 */}
      <div className="relative flex h-[104px] items-center justify-center">
        {phase === 'listening' ? (
          <Waveform levels={levels} />
        ) : (
          <span className="text-[12.5px] text-stage-muted-3">답변이 끝나면 마이크가 열립니다</span>
        )}
      </div>

      {/* 하단 컨트롤 — 종료 버튼 하나. 질문 번호·단계·남은 시간 같은 진행
          표시는 두지 않는다. 실제 면접에서 지원자가 보는 것은 면접관뿐이다. */}
      <div className="relative px-[30px] pb-[26px]">
        <div className="flex items-center justify-end">
          {/* 멈췄다 이어가는 길은 두지 않는다 — 면접은 한 번에 끝까지 간다.
              중간에 그만두면 그때까지의 답변으로 리포트를 받는다. */}
          <button
            onClick={end}
            className="tap44 rounded-control border border-stage-line px-[18px] py-[9px] text-[13px] text-stage-muted-2"
          >
            종료하고 리포트 받기
          </button>
        </div>
      </div>

    </div>
  )
}

/**
 * 아바타 + 발화 링.
 *
 * README §Assets는 링을 순수 CSS 애니메이션으로 정의하지만, 여기서는 실제
 * 오디오 진폭으로 구동합니다. 값이 60fps로 바뀌므로 React state를 거치지 않고
 * ref → style에 직접 씁니다.
 *
 * **말할 때와 들을 때 둘 다 살아 있어야 합니다.** 앞서는 링이 speaking일 때만
 * 붙어서, 지원자가 답하는 동안(면접 시간의 절반) 아바타가 정지한 검은 원이
 * 됐습니다. 지금은 링 두 벌이 늘 붙어 있고 rAF 루프가 불투명도로 건넵니다 —
 * 마운트를 여닫으면 전환할 때 툭 끊깁니다.
 *
 * 색이 갈립니다: 면접관이 말할 때는 강조색(머스터드), 지원자가 말할 때는
 * 듣는 색(초록)입니다. 내 목소리가 면접관에게 가 닿는 것이 보여야 대화가 됩니다.
 *
 * `data-avatar-slot="true"` 컨테이너 내부만 교체하면 실제 아바타로 대체됩니다.
 * 링·자막·컨트롤은 이 컨테이너 바깥에 있습니다.
 */
function Avatar({ levels, speaking }: { levels: React.RefObject<Levels>; speaking: boolean }) {
  const talkGlow = useRef<HTMLDivElement>(null)
  const talkRing = useRef<HTMLDivElement>(null)
  const hearRing = useRef<HTMLDivElement>(null)
  const core = useRef<HTMLDivElement>(null)
  // 루프가 phase마다 다시 붙지 않도록 ref로 읽는다.
  const isSpeaking = useRef(speaking)
  isSpeaking.current = speaking

  useEffect(() => {
    let raf = 0
    const loop = () => {
      const talking = isSpeaking.current
      const out = levels.current.output
      const inp = levels.current.input

      if (talkGlow.current) {
        talkGlow.current.style.transform = `scale(${1 + out * 0.26})`
        talkGlow.current.style.opacity = String(talking ? 0.06 + out * 0.26 : 0)
      }
      if (talkRing.current) {
        talkRing.current.style.transform = `scale(${1 + out * 0.14})`
        talkRing.current.style.opacity = String(talking ? 0.14 + out * 0.36 : 0)
      }
      // 듣는 링은 지원자 목소리를 받는다. 조용해도 완전히 꺼지지 않는다 —
      // 꺼두면 "듣고 있다"가 화면에서 사라진다.
      if (hearRing.current) {
        hearRing.current.style.transform = `scale(${1 + inp * 0.1})`
        hearRing.current.style.opacity = String(talking ? 0 : 0.28 + inp * 0.62)
      }
      // 가운데 표식이 말차례를 쥔다. 면접관이 말하면 부풀고, 들을 때는 잦아든다.
      if (core.current) {
        const level = talking ? out : inp * 0.4
        core.current.style.transform = `scale(${(talking ? 1 : 0.82) + level * 0.22})`
      }
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [levels])

  return (
    <div className="relative flex items-center justify-center" style={{ width: 340, height: 340 }}>
      <div
        ref={talkGlow}
        className="absolute rounded-full"
        style={{
          width: 340,
          height: 340,
          background: 'radial-gradient(circle, rgba(181,127,28,.5), transparent 68%)',
          opacity: 0,
        }}
      />
      <div
        ref={talkRing}
        className="absolute rounded-full"
        style={{ width: 270, height: 270, border: '1px solid rgba(181,127,28,.34)', opacity: 0 }}
      />
      <div
        ref={hearRing}
        className="absolute rounded-full"
        style={{ width: 246, height: 246, border: '1.5px solid rgba(78,158,126,.9)', opacity: 0 }}
      />

      <div
        data-avatar-slot="true"
        className="relative flex animate-dm-breathe items-center justify-center overflow-hidden rounded-full"
        style={{
          width: 206,
          height: 206,
          background: 'linear-gradient(160deg, #233047, #16223A)',
          border: '1px solid #2E3F5C',
        }}
      >
        <div
          className="absolute inset-0"
          style={{
            background: 'radial-gradient(circle at 34% 28%, rgba(255,255,255,.07), transparent 58%)',
          }}
        />
        <div
          className="flex items-center justify-center rounded-full"
          style={{ width: 96, height: 96, border: '1px solid rgba(232,236,243,.22)' }}
        >
          <div
            ref={core}
            className="rounded-full"
            style={{
              width: 44,
              height: 44,
              background: 'rgba(181,127,28,.85)',
              transition: 'background .4s ease',
            }}
          />
        </div>
      </div>
    </div>
  )
}

/**
 * 마이크 입력 파형 — 3px 폭 막대 16개, 높이 38px.
 * 진폭은 입력 AnalyserNode에서 옵니다. 막대별 위상차로 파도 모양을 만듭니다.
 */
const BAR_COUNT = 16

function Waveform({ levels }: { levels: React.RefObject<Levels> }) {
  const bars = useRef<(HTMLDivElement | null)[]>([])

  useEffect(() => {
    let raf = 0
    const loop = () => {
      const level = levels.current.input
      const t = performance.now() / 1000
      for (let i = 0; i < BAR_COUNT; i++) {
        const el = bars.current[i]
        if (!el) continue
        const phase = Math.sin(t * 6 + i * 0.7) * 0.5 + 0.5
        const scale = 0.22 + level * (0.35 + 0.65 * phase) * 0.78
        el.style.transform = `scaleY(${Math.min(1, scale)})`
      }
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [levels])

  return (
    <div className="flex items-center" style={{ gap: 3, height: 38 }}>
      {Array.from({ length: BAR_COUNT }, (_, i) => (
        <div
          key={i}
          ref={(el) => {
            bars.current[i] = el
          }}
          className="bg-accent"
          style={{ width: 3, height: 38, transformOrigin: 'center', transform: 'scaleY(0.22)' }}
        />
      ))}
    </div>
  )
}
