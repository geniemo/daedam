import { useEffect } from 'react'
import type { FaceFrame } from './useFaceTracking'

/**
 * 표정 판독용 스냅샷 — 3초마다 한 장을 찍어 올립니다.
 *
 * **녹화(cam.webm)가 있는데 따로 찍는 이유**: 판독은 서버의 Gemini 호출이
 * 하는데, 서버가 영상에서 프레임을 뽑으려면 디코더(opencv급 의존성)가
 * 필요합니다. 화면은 프레임을 이미 손에 들고 있으므로 찍는 쪽이 보내는 것이
 * 쌉니다. 320×240 JPEG이 장당 15KB 안팎 — 20분에 6MB로, 영상(60MB) 옆에서
 * 오차 수준입니다.
 *
 * **시선 기준선과 무관합니다.** 시선은 "정면 대비 벗어남"이라 기준선이 필요
 * 하지만, 표정 판독은 프레임 그 자체를 읽습니다. 카메라만 켜져 있으면 찍습니다.
 *
 * **영상 조각과 달리 한 장쯤 잃어도 됩니다.** WebM 조각은 중간이 비면 파일이
 * 통째로 깨져서 순서 보장·중단 규칙이 필요했지만(useRecorder), 스냅샷은 장마다
 * 독립이라 실패를 그냥 놓아 보냅니다 — 3초 간격의 표본에서 한 장의 구멍은
 * 잡음입니다. 재시도·큐가 없는 것은 빠뜨린 게 아니라 그래서입니다.
 *
 * **깜빡임을 피해 찍습니다.** 스틸은 깜빡임 중간과 "눈을 감고 생각함"을 구분
 * 못 합니다 — 실측 프로브에서 판독이 "눈을 감으며"를 자주 적은 이유의 하나.
 * 얼굴 추적이 이미 프레임마다 눈감김 세기를 갖고 있으므로, 찍는 순간 눈이
 * 감겨 있으면 잠깐(최대 0.45초) 미뤘다가 뜬 프레임을 찍습니다.
 */

/** 촬영 간격. 지속 인상의 비율에는 5초로도 충분하지만(오차 ±5%p, 판독기
 *  흔들림과 같은 급) 답변별 해상도와 단발 순간 포착이 그만큼 덜 얇아진다. */
export const SNAPSHOT_INTERVAL_S = 3

/** 판독에 보내는 크기. 프로브를 이 크기로 실측했다 — 장당 258토큰. */
const WIDTH = 320
const HEIGHT = 240

/** 이 위면 깜빡임 중으로 보고 촬영을 잠깐 미룬다. */
const BLINK_LIMIT = 0.35
const BLINK_RETRY_MS = 150
const BLINK_RETRIES = 3

function blinkOf(frame: FaceFrame): number {
  const s = frame.shapes
  return ((s.eyeBlinkLeft ?? 0) + (s.eyeBlinkRight ?? 0)) / 2
}

export function useSnapshots(
  stream: MediaStream | null,
  /** POST 받을 주소(세션 포함). 없으면 찍지 않는다. */
  uploadUrl: string | null,
  /** 얼굴 추적의 최신 프레임. 추적이 꺼져 있으면 빈 값이라 그냥 찍는다. */
  latest: () => FaceFrame,
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

    const shoot = (retriesLeft: number) => {
      if (stop || !ctx) return
      if (blinkOf(latest()) > BLINK_LIMIT && retriesLeft > 0) {
        window.setTimeout(() => shoot(retriesLeft - 1), BLINK_RETRY_MS)
        return
      }
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

    const timer = window.setInterval(() => shoot(BLINK_RETRIES), SNAPSHOT_INTERVAL_S * 1000)
    return () => {
      stop = true
      window.clearInterval(timer)
      video.pause()
      video.srcObject = null
    }
  }, [stream, uploadUrl, latest, elapsedNow])
}
