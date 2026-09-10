import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { useActiveCard, useAppStore } from '@/store/app'
import { formatClock, useInterviewStore } from '@/store/interview'
import { useVoiceSession } from '@/audio/useVoiceSession'
import { fill } from '@/data/mock'
import { useCamera } from '@/video/useCamera'
import { SelfView, SWAP_TRANSITION } from '@/video/SelfView'
import { useRecorder } from '@/video/useRecorder'
import { useSnapshots } from '@/video/useSnapshots'
import { Avatar, Keylight, Waveform } from '@/components/Stage'

/** 결과 없이 홈으로 돌아갈 때 홈에 남기는 한 줄. 키는 서버의 ended.reason. */
const FINISH_NOTICE: Record<string, string> = {
  credits: '크레딧이 부족해 면접을 시작하지 못했습니다.',
  replaced: '다른 탭에서 같은 면접이 열렸습니다. 새 탭에서 계속 진행해 주세요.',
  failed:
    '면접 서버에 연결하지 못했습니다. 잠시 뒤 다시 시작해 주세요. 답변 전이었다면 크레딧은 돌려드렸고, 답변이 있었다면 한 시간 안에 다시 시작하면 이어집니다.',
  rejected: '이 면접을 시작할 수 없습니다. 준비가 끝났는지 확인해 주세요.',
}

/** 구체 지름의 상한·하한, 거울 배치에서 우상단으로 들어갈 때의 지름. */
const SPHERE_MAX = 216
const SPHERE_MIN = 150
const PIP = 92
/**
 * 좁은 무대 — 무대 영역 폭이 이보다 작으면 셀프뷰 132×99, PiP 64, 질문 18px,
 * 여백 16. 창이 아니라 무대 영역의 폭으로 가른다(ResizeObserver로 재는 값이라
 * 창 폭보다 정확하다). 규격: design-system/ui_kits/web/Interview.jsx
 */
const NARROW_W = 600
const SPHERE_MIN_NARROW = 120
const PIP_NARROW = 64
const SELF_W = 240
const SELF_H = 180
const SELF_W_NARROW = 132
const SELF_H_NARROW = 99
/** 초점(구체 또는 웹캠)과 질문 사이. 질문은 구체 바로 아래 붙는다. */
const GAP = 44
/** 질문 자리 — 두 줄 높이를 늘 비워 둔다. 자막 길이에 따라 위가 튀면 안 된다. */
const QUESTION_H = 100

/**
 * README §8. 면접 진행 — 화면이 시선을 뺏지 않는 것이 목표입니다.
 *
 * 무대 D(design-system/ui_kits/web/Interview.jsx): 정지한 키라이트, 무광 유리
 * 구체, 구체 바로 아래 붙은 질문, 모래색 파형. 비네트도 헤더 페이드도 없다.
 * 가운데 덩이(초점 + 44 + 질문)를 무대 영역의 세로 중앙에 둔다.
 */
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

  // 이유 없이 끝났으면 정상 종료라 결과를 기다린다. 이유가 있으면(크레딧
  // 부족·다른 탭이 이어받음·연결 실패·거절) 분석할 것이 없거나 판이 아직
  // 살아 있는 것이라 홈으로 돌려보내고, 왜 돌아왔는지를 홈에 남긴다.
  const setNotice = useAppStore((s) => s.setNotice)
  const onFinished = useCallback(
    (reason?: string) => {
      if (!reason) {
        nav('/analyzing')
        return
      }
      setNotice(FINISH_NOTICE[reason] ?? FINISH_NOTICE.rejected)
      nav('/')
    },
    [nav, setNotice],
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
  // 거울 배치 — 웹캠이 가운데, 면접관이 우상단. SelfView 참고.
  const [mirror, setMirror] = useState(false)
  useEffect(() => {
    if (cameraReady) void camera.start()
  }, [cameraReady, camera.start])
  // 카메라가 꺼지면(끄기 버튼이든 장치 쪽 사정이든) 가운데가 비므로 면접관을
  // 제자리로 돌린다.
  useEffect(() => {
    if (camera.state !== 'on') setMirror(false)
  }, [camera.state])

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

  // 시선·표정 판독용 스냅샷. 녹화와 별개로 3초마다 한 장 — 서버가 영상
  // 디코더 없이 Gemini로 판독하도록 화면이 프레임을 직접 보낸다. 카메라만
  // 켜져 있으면 찍는다. 앞서 있던 브라우저 안 얼굴 추적과 정면 기준선은
  // 걷어냈다 — 판독이 지원자 기준으로 방향을 읽어 기준선이 필요 없다.
  useSnapshots(
    camera.stream,
    sessionId ? `/api/interviews/${card.id}/frames?session=${sessionId}` : null,
    elapsedNow,
  )

  // 무대 영역의 크기. 구체 지름과 두 배치의 좌표가 여기서 나온다 — 창 크기가
  // 바뀌면 다시 잰다.
  const area = useRef<HTMLDivElement>(null)
  const [box, setBox] = useState({ w: 0, h: 0 })
  useLayoutEffect(() => {
    const el = area.current
    if (!el) return
    const measure = () => setBox({ w: el.clientWidth, h: el.clientHeight })
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const speaking = phase === 'speaking'
  const narrow = box.w < NARROW_W
  const pip = narrow ? PIP_NARROW : PIP
  const edge = narrow ? 16 : 30
  // 가운데 덩이 = 초점(구체 또는 웹캠) + 44 + 질문. 세로 중앙.
  // 구체는 세로의 40%이되 좁은 무대에서는 가로의 절반을 넘지 않는다.
  const sphere = Math.max(
    narrow ? SPHERE_MIN_NARROW : SPHERE_MIN,
    Math.min(SPHERE_MAX, Math.round(box.h * 0.4), Math.round(box.w * 0.5)),
  )
  // 거울은 세로에서 정한 높이의 4:3이되 가로 여백을 남기고 폭에 맞춘다.
  const mirrorW = Math.max(
    0,
    Math.min(
      Math.round((Math.max(160, Math.min(420, box.h - 60 - GAP - QUESTION_H)) * 4) / 3),
      box.w - edge * 2,
    ),
  )
  const mirrorH = Math.round((mirrorW * 3) / 4)
  const focusH = mirror ? mirrorH : sphere
  const blockTop = Math.max(narrow ? 32 : 60, Math.round((box.h - (focusH + GAP + QUESTION_H)) / 2))
  const questionTop = blockTop + focusH + GAP
  const clock = <span className="num text-[13px]" style={{ color: 'var(--stage-dim)' }}>{formatClock(elapsed)}</span>

  return (
    <div
      className="fixed inset-0 z-60 flex flex-col overflow-hidden"
      style={{ background: 'var(--stage-bg)', color: 'var(--stage-ink-warm)' }}
    >
      {/* 키라이트 — 정지, 면접관이 말할 때 조금 밝아진다. */}
      <Keylight width={1100} height={700} top="-20%" alpha={speaking ? 0.1 : 0.06} />

      {/* 상단 — 상태 문장과 시계. 거울 배치에서는 우상단에 면접관이 들어오므로
          시계가 상태 문장 옆으로 온다. */}
      <div className="relative z-5 flex items-center" style={{ padding: narrow ? '14px 16px' : '22px 30px' }}>
        <span
          className="rounded-full"
          style={{
            width: 7,
            height: 7,
            background: speaking ? 'var(--stage-amber)' : 'var(--stage-mint)',
            boxShadow: `0 0 10px ${speaking ? 'var(--stage-amber)' : 'var(--stage-mint)'}`,
            transition: 'background .6s, box-shadow .6s',
          }}
        />
        <span className="ml-[9px] text-[13.5px]">
          {speaking ? '면접관이 말하고 있습니다' : '듣고 있습니다'}
        </span>
        {connection === 'reconnecting' && (
          <span className="ml-2 text-[12.5px]" style={{ color: 'var(--stage-dim)' }}>
            · 연결을 복구하는 중입니다
          </span>
        )}
        {mirror && (
          <>
            <span className="mx-3" style={{ width: 1, height: 12, background: 'rgba(255,255,255,.18)' }} />
            {clock}
          </>
        )}
        <div className="flex-1" />
        {!mirror && clock}
      </div>

      {/* 무대 — 구체·웹캠·질문이 절대 좌표로 놓인다. */}
      <div ref={area} className="relative min-h-0 flex-1">
        {/* 면접관 — 기본 가운데, 거울이면 우상단 92(좁은 무대 64). */}
        <div
          className="absolute"
          style={{
            width: sphere,
            height: sphere,
            transformOrigin: 'top left',
            transition: SWAP_TRANSITION,
            zIndex: mirror ? 4 : 1,
            ...(mirror
              ? {
                  left: `calc(100% - ${edge}px - ${pip}px)`,
                  top: narrow ? 8 : 14,
                  transform: `translate(0, 0) scale(${pip / sphere})`,
                }
              : { left: '50%', top: blockTop, transform: 'translate(-50%, 0) scale(1)' }),
          }}
        >
          <Avatar levels={levels} speaking={speaking} size={sphere} />
        </div>

        <SelfView
          camera={camera}
          mirror={mirror}
          narrow={narrow}
          visible={selfVisible}
          top={blockTop}
          width={mirror ? mirrorW : narrow ? SELF_W_NARROW : SELF_W}
          height={mirror ? mirrorH : narrow ? SELF_H_NARROW : SELF_H}
          onMirror={() => setMirror((m) => !m)}
          onHide={() => setSelfVisible((v) => !v)}
          onStop={camera.stop}
        />

        {/* 질문 — 면접관이 실제로 하고 있는 말. 뼈대질문 문장이 아닙니다.
            가운데 것(구체 또는 웹캠) 바로 아래 44px에 붙고, 자리는 늘 비워 둔다. */}
        <div
          className="absolute flex flex-col items-center gap-[18px]"
          style={{
            left: '50%',
            top: questionTop,
            transform: 'translateX(-50%)',
            width: narrow ? 'calc(100% - 32px)' : 'min(680px, calc(100% - 64px))',
            minHeight: QUESTION_H,
            transition: 'top .45s ease-in-out',
          }}
        >
          <span
            style={{
              width: 28,
              height: 1,
              background: speaking ? 'var(--stage-amber)' : 'var(--stage-mint)',
              transition: 'background 1s ease',
            }}
          />
          {showCaption && caption && (
            <p
              key={askedCount}
              className="m-0 break-keep text-center leading-[1.55] font-semibold tracking-[-.02em]"
              style={{
                fontSize: narrow ? 18 : 'clamp(20px, 2.7vh, 25px)',
                color: 'var(--stage-paper)',
                animation: 'dm-fade .6s ease',
              }}
            >
              {fill(caption, card.company, card.role)}
            </p>
          )}
        </div>
      </div>

      {/* 하단 상태 영역 — 들을 때 파형, 말할 때 안내 한 줄. */}
      <div className="relative flex items-center justify-center" style={{ height: narrow ? 84 : 104 }}>
        {phase === 'listening' ? (
          <Waveform levels={levels} height={40} />
        ) : (
          <span className="text-[12.5px] tracking-[.02em]" style={{ color: 'var(--stage-dim-2)' }}>
            답변이 끝나면 마이크가 열립니다
          </span>
        )}
      </div>

      {/* 하단 컨트롤 — 종료 버튼 하나. 질문 번호·단계·남은 시간 같은 진행
          표시는 두지 않는다. 실제 면접에서 지원자가 보는 것은 면접관뿐이다. */}
      <div className="relative flex justify-end" style={{ padding: narrow ? '0 16px 20px' : '0 30px 26px' }}>
        {/* 멈췄다 이어가는 길은 두지 않는다 — 면접은 한 번에 끝까지 간다.
            중간에 그만두면 그때까지의 답변으로 리포트를 받는다. */}
        <button
          onClick={end}
          className="tap44 rounded-full px-5 py-[10px] text-[13px]"
          style={{ color: 'var(--stage-dim)', border: '1px solid var(--stage-line-warm)' }}
        >
          종료하고 리포트 받기
        </button>
      </div>
    </div>
  )
}
