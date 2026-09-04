import { useEffect } from 'react'

/**
 * 시선·표정 판독용 스냅샷 — 3초마다 한 장을 찍어 올립니다.
 *
 * **녹화(cam.webm)가 있는데 따로 찍는 이유**: 판독은 서버의 Gemini 호출이
 * 하는데, 서버가 영상에서 프레임을 뽑으려면 디코더(opencv급 의존성)가
 * 필요합니다. 화면은 프레임을 이미 손에 들고 있으므로 찍는 쪽이 보내는 것이
 * 쌉니다. 320×240 JPEG이 장당 15KB 안팎 — 20분에 6MB로, 영상(60MB) 옆에서
 * 오차 수준입니다.
 *
 * **카메라만 켜져 있으면 찍습니다.** 시선도 표정도 이 스냅샷을 판독기가 읽어서
 * 나옵니다 — 앞서 있던 홍채 추적과 정면 기준선은 걷어냈습니다. 판독이 지원자
 * 기준으로 방향을 읽으므로 기준선이 필요 없습니다(eval/expression.py).
 *
 * **영상 조각과 달리 한 장쯤 잃어도 됩니다.** WebM 조각은 중간이 비면 파일이
 * 통째로 깨져서 순서 보장·중단 규칙이 필요했지만(useRecorder), 스냅샷은 장마다
 * 독립이라 실패를 그냥 놓아 보냅니다 — 3초 간격의 표본에서 한 장의 구멍은
 * 잡음입니다. 재시도·큐가 없는 것은 빠뜨린 게 아니라 그래서입니다.
 */

/** 촬영 간격. 지속 인상의 비율에는 5초로도 충분하지만(오차 ±5%p, 판독기
 *  흔들림과 같은 급) 답변별 해상도와 단발 순간 포착이 그만큼 덜 얇아진다. */
export const SNAPSHOT_INTERVAL_S = 3

/** 판독에 보내는 크기. 프로브를 이 크기로 실측했다 — 장당 258토큰. */
const WIDTH = 320
const HEIGHT = 240

export function useSnapshots(
  stream: MediaStream | null,
  /** POST 받을 주소(세션 포함). 없으면 찍지 않는다. */
  uploadUrl: string | null,
  /** 면접 경과 초 — 답변 구간과 같은 시계여야 분석이 답변별로 나눈다. */
  elapsedNow: () => number,
) {
  useEffect(() => {
    if (!stream || !uploadUrl) return
    let stop = false

    // 모델·미리보기와 별개로 스냅샷 전용 <video>를 하나 더 문다. MediaStream은
    // 소비자가 여럿이어도 프레임을 나눠 준다.
    const video = document.createElement('video')
    video.srcObject = stream
    video.muted = true
    video.playsInline = true
    void video.play().catch(() => {})

    const canvas = document.createElement('canvas')
    canvas.width = WIDTH
    canvas.height = HEIGHT
    const ctx = canvas.getContext('2d')

    const shoot = () => {
      if (stop || !ctx) return
      // 시각은 blob 인코딩(비동기)이 아니라 셔터가 눌린 지금 것을 쓴다.
      const at = elapsedNow()
      if (video.readyState < 2) return // 아직 첫 프레임이 없다
      ctx.drawImage(video, 0, 0, WIDTH, HEIGHT)
      canvas.toBlob(
        (blob) => {
          if (!blob || stop) return
          void fetch(`${uploadUrl}&at=${at.toFixed(1)}`, {
            method: 'POST',
            body: blob,
          }).catch(() => {
            // 한 장의 구멍은 잡음이다 — 위 파일 주석 참고.
          })
        },
        'image/jpeg',
        0.8,
      )
    }

    const timer = window.setInterval(shoot, SNAPSHOT_INTERVAL_S * 1000)
    return () => {
      stop = true
      window.clearInterval(timer)
      video.pause()
      video.srcObject = null
    }
  }, [stream, uploadUrl, elapsedNow])
}
