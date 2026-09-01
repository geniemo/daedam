import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * 면접 중 지원자의 카메라.
 *
 * **음성 세션과 수명을 나눕니다.** 카메라는 있으면 좋은 것이고 마이크는 없으면
 * 면접이 안 됩니다. 한 스트림으로 묶으면 카메라 권한 거부가 면접 자체를
 * 막습니다 — 그래서 훅을 따로 둡니다.
 *
 * **끄는 스위치가 둘입니다.** 화면에서 내 얼굴을 안 보는 것과 카메라를 실제로
 * 끄는 것은 다른 요구입니다. 하나로 묶으면 "보기 싫어서 껐는데 계속 찍히고
 * 있었다"가 되고, 그건 얼굴 영상에서 절대 만들면 안 되는 오해입니다.
 *
 *   showSelf — 화면에만 안 보인다. 촬영은 계속된다.
 *   stop()   — 트랙을 실제로 놓는다. 표시등이 꺼진다.
 *
 * 해상도는 640×480 15fps로 고정합니다. 자세·시선·표정을 되돌아보는 용도라
 * 그 이상이 필요 없고, 720p로 올리면 판당 저장이 3배가 됩니다.
 */

/** 녹화·분석이 쓸 규격. 올리면 저장 용량이 그대로 비례해 늘어납니다. */
export const CAMERA_CONSTRAINTS: MediaTrackConstraints = {
  width: { ideal: 640 },
  height: { ideal: 480 },
  frameRate: { ideal: 15, max: 15 },
  facingMode: 'user',
}

export type CameraState = 'idle' | 'starting' | 'on' | 'denied' | 'missing'

export interface Camera {
  /** 미리보기와 분석이 함께 읽는 스트림. 꺼져 있으면 null. */
  stream: MediaStream | null
  state: CameraState
  start: () => Promise<void>
  stop: () => void
}

export function useCamera(): Camera {
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [state, setState] = useState<CameraState>('idle')
  // 시작 요청이 겹쳐 들어와도 스트림을 두 개 잡지 않는다.
  const pending = useRef(false)
  const held = useRef<MediaStream | null>(null)

  const stop = useCallback(() => {
    held.current?.getTracks().forEach((t) => t.stop())
    held.current = null
    setStream(null)
    setState('idle')
  }, [])

  const start = useCallback(async () => {
    if (pending.current || held.current) return
    // 보안 컨텍스트가 아니거나(http) 지원하지 않는 브라우저면 장치가 없는 것과
    // 같다 — 여기서 걸러야 면접 화면이 예외로 죽지 않는다.
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      setState('missing')
      return
    }
    pending.current = true
    setState('starting')
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        video: CAMERA_CONSTRAINTS,
      })
      held.current = media
      setStream(media)
      setState('on')
    } catch (err) {
      // 거부와 장치 없음을 가른다 — 화면이 할 말이 다르다. 권한 거부는
      // 사용자가 되돌릴 수 있고, 장치가 없으면 되돌릴 것이 없다.
      const name = (err as { name?: string })?.name
      setState(name === 'NotFoundError' || name === 'OverconstrainedError' ? 'missing' : 'denied')
    } finally {
      pending.current = false
    }
  }, [])

  // 화면을 벗어나면 반드시 놓는다. 안 놓으면 탭이 계속 촬영 중으로 남고,
  // 브라우저 표시등이 켜진 채라 사용자는 어디서 찍히는지 알 수 없다.
  useEffect(() => () => {
    held.current?.getTracks().forEach((t) => t.stop())
    held.current = null
  }, [])

  return { stream, state, start, stop }
}
