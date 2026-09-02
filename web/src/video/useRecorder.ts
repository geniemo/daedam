import { useEffect, useRef, useState } from 'react'

/**
 * 웹캠을 녹화해 서버로 이어 올립니다.
 *
 * **면접 도중에 조각으로 올립니다.** 끝나고 한 번에 올리면 20분치 60MB를
 * 마지막에 밀어야 하고, 그 사이 창을 닫으면 통째로 날아갑니다. 오디오 녹음이
 * 이미 조각으로 이어 쓰는 구조라(server/recording.py) 결을 맞춥니다.
 *
 * **순서가 전부입니다.** MediaRecorder는 첫 조각에만 WebM 헤더를 넣으므로,
 * 이어 붙인 바이트가 곧 파일입니다. 중간이 비면 파일 전체가 깨집니다. 그래서
 *
 *   - 큐에 쌓고 **한 번에 하나씩** 순서대로 보냅니다 (병렬 전송 금지)
 *   - 한 조각이 끝내 실패하면 **건너뛰지 않고 녹화를 멈춥니다**
 *
 * 잘린 파일은 재생되지만 구멍 난 파일은 안 됩니다. 그래서 실패했을 때 남는 것이
 * "그때까지의 온전한 영상"이 되도록 합니다.
 *
 * 미리보기와 달리 좌우를 뒤집지 않습니다 — 녹화본은 면접관이 보는 방향이어야
 * 나중에 리뷰가 됩니다. 뒤집기는 SelfView의 CSS에만 있습니다.
 *
 * **소리를 같이 담습니다.** 카메라만 담으면 리포트에서 무성 영상이 되고, 소리를
 * 맞추려면 요소 둘을 동기화해야 합니다. 음성 세션이 이미 잡아 둔 마이크 트랙을
 * 빌려 한 파일에 넣으면 재생이 요소 하나로 끝납니다. 5초 조각에 오디오가 붙어야
 * 20KB쯤 늘 뿐입니다.
 *
 * **시작 시각을 함께 올립니다.** 답변 구간(`span.startS`)은 서버가 받은 오디오
 * 바이트로 센 시각이고 영상의 t=0은 녹화가 시작된 순간이라, 원점이 다릅니다.
 * 그 차이를 첫 조각에 실어 보내야 리포트가 답변 위치로 정확히 감을 수 있습니다.
 */

/** 한 조각의 길이. 짧으면 요청이 잦고, 길면 마지막에 날아가는 양이 늘어난다. */
const SLICE_MS = 5000

/** 조각당 재시도 횟수. 이걸 넘기면 녹화를 멈춘다 — 건너뛰면 파일이 깨진다. */
const RETRIES = 2

/** 선호 코덱. 지원하지 않으면 브라우저 기본값으로 떨어진다. */
const CANDIDATES = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm']

export type RecorderState = 'idle' | 'recording' | 'stopped' | 'failed'

function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === 'undefined') return undefined
  return CANDIDATES.find((t) => MediaRecorder.isTypeSupported(t))
}

export function useRecorder(
  stream: MediaStream | null,
  uploadUrl: string | null,
  /** 이 트랙을 같이 담는다 — 소리 있는 클립이 된다. */
  audioTrack: () => MediaStream | null,
  /**
   * 면접 경과 초를 돌려주는 함수. 녹화가 시작되는 **그 순간**에 한 번만
   * 불립니다 — 그 값이 영상과 전사의 원점 차이입니다.
   */
  startS: () => number,
) {
  const [state, setState] = useState<RecorderState>('idle')
  const recorder = useRef<MediaRecorder | null>(null)
  // 보내는 중인 약속. 다음 조각은 이것이 끝난 뒤에 나간다 — 순서 보장.
  const tail = useRef<Promise<void>>(Promise.resolve())
  const broken = useRef(false)

  useEffect(() => {
    if (!stream || !uploadUrl) return
    const mimeType = pickMimeType()
    if (mimeType === undefined) {
      setState('failed')
      return
    }

    broken.current = false
    tail.current = Promise.resolve()

    // **녹화가 시작되는 지금**의 경과 초를 잡아 둔다. send() 안에서 읽으면 첫
    // 조각이 올라가는 시점(SLICE_MS 뒤)의 값이 찍혀서 영상 전체가 그만큼 밀린
    // 것으로 기록된다 — 실측에서 정확히 5.00초가 박혔고, 리포트의 답변 클립이
    // 5초씩 어긋났다.
    const originS = startS()
    let first = true
    const send = async (blob: Blob) => {
      // 원점은 첫 조각에만 싣는다. 서버가 그때 한 번만 적어 둔다.
      const url = first ? `${uploadUrl}&startS=${originS.toFixed(2)}` : uploadUrl
      for (let attempt = 0; attempt <= RETRIES; attempt++) {
        try {
          const res = await fetch(url, { method: 'POST', body: blob })
          if (res.ok) {
            first = false
            return
          }
          // 4xx는 다시 보내도 같다 — 상한을 넘었거나 내 세션이 아니다.
          if (res.status >= 400 && res.status < 500) break
        } catch {
          // 네트워크 실패는 다시 해볼 값어치가 있다.
        }
      }
      // 여기 왔다는 것은 이 조각을 못 올렸다는 뜻이다. 다음 조각을 이어 붙이면
      // 파일에 구멍이 생기므로 녹화 자체를 멈춘다.
      broken.current = true
      setState('failed')
      try {
        recorder.current?.stop()
      } catch {
        // 이미 멈춰 있으면 그만.
      }
    }

    // 카메라 영상 + 마이크 소리를 한 스트림으로 묶는다. 마이크가 아직 없으면
    // 영상만 담는다 — 소리가 없다고 녹화를 포기할 이유는 없다.
    const mic = audioTrack()
    const combined = new MediaStream([
      ...stream.getVideoTracks(),
      ...(mic ? mic.getAudioTracks() : []),
    ])

    let rec: MediaRecorder
    try {
      rec = new MediaRecorder(combined, {
        mimeType,
        videoBitsPerSecond: 500_000,
        audioBitsPerSecond: 32_000,
      })
    } catch {
      setState('failed')
      return
    }
    recorder.current = rec

    rec.ondataavailable = (event) => {
      if (broken.current || event.data.size === 0) return
      // 큐에 매단다. 앞의 것이 끝나야 다음이 나가므로 서버에 순서대로 도착한다.
      tail.current = tail.current.then(() => send(event.data))
    }
    rec.onerror = () => setState('failed')

    rec.start(SLICE_MS)
    setState('recording')

    return () => {
      try {
        if (rec.state !== 'inactive') rec.stop()
      } catch {
        // 스트림이 이미 끊겼으면 그만.
      }
      recorder.current = null
      setState((s) => (s === 'failed' ? s : 'stopped'))
    }
  }, [stream, uploadUrl, audioTrack, startS])

  return { state }
}
