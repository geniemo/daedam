import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useActiveCard, useAppStore } from '@/store/app'
import { formatClock, useInterviewStore } from '@/store/interview'
import { useVoiceSession } from '@/audio/useVoiceSession'
import { fill } from '@/data/mock'
import { useCamera } from '@/video/useCamera'
import { SelfView } from '@/video/SelfView'
import { useRecorder } from '@/video/useRecorder'
import { useSnapshots } from '@/video/useSnapshots'
import { useFaceTracking } from '@/video/useFaceTracking'
import { useGazeLog } from '@/video/useGazeLog'
import { Avatar, Waveform } from '@/components/Stage'

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

      {/* 무대의 중심 — 랜딩의 데모 창과 같은 비네트(index.css). */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{ background: 'var(--gradient-stage-vignette)' }}
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
