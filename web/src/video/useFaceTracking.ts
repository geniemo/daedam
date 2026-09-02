import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * 얼굴 랜드마크 추적 — 시선과 표정의 원료.
 *
 * **지연 로딩입니다.** MediaPipe 실행 파일과 얼굴 모델이 합쳐 7MB(gzip 기준
 * WASM 3.3MB + 모델 3.8MB)입니다. 앱 번들이 119KB인 것과 비교하면 60배라,
 * 카메라를 켠 사람만 받아야 합니다. import도 동적으로 합니다 — 정적으로 두면
 * 카메라를 안 쓰는 사람의 첫 화면까지 무거워집니다.
 *
 * 자산은 우리 서버에서 나갑니다(`public/vision/`). CDN을 물리면 배포가 외부
 * 하나에 더 매이고, 지금 구조는 `dist/`를 FastAPI에 얹은 컨테이너 하나입니다.
 * 26MB짜리 바이너리라 저장소에는 넣지 않고 빌드 전에 받아 옵니다
 * (`scripts/fetch-vision.mjs`).
 *
 * **화면을 다시 그리지 않습니다.** 프레임마다 나오는 값이라 React state에 넣으면
 * 초당 15번 렌더가 돕니다. 오디오 레벨과 같은 규칙으로 ref에 담고, 읽는 쪽이
 * 필요할 때 꺼내 씁니다(`latest()`).
 */

/** 모델을 돌리는 주기. 카메라가 15fps라 그보다 자주 볼 이유가 없습니다. */
const INTERVAL_MS = 66

export interface FaceFrame {
  /** 이 프레임의 시각(performance.now 기준 ms). */
  at: number
  /** 얼굴을 찾았는가. 못 찾으면 아래 값들은 직전 값입니다. */
  found: boolean
  /**
   * 시선 신호. 머리 방향과 눈동자 방향을 합친 2차원 값입니다.
   * 화면 좌표가 아니라 **보정으로 화면에 대응시킬 원료**입니다.
   * 오른쪽·아래가 양수입니다.
   */
  gaze: { x: number; y: number }
  /**
   * 화면(카메라 프레임) 안에서 얼굴이 있는 자리. 0~1이고 0.5가 한가운데입니다.
   * 기준선을 잡을 때 "얼굴을 가운데 두었는가"를 이걸로 봅니다 — 구석에서 잡은
   * 기준선은 면접 내내 어긋난 원점이 됩니다.
   */
  center: { x: number; y: number }
  /** 표정 계수 이름 → 0~1. MediaPipe 블렌드셰이프 그대로입니다. */
  shapes: Record<string, number>
}

export type TrackingState = 'idle' | 'loading' | 'running' | 'failed'

const EMPTY: FaceFrame = {
  at: 0,
  found: false,
  gaze: { x: 0, y: 0 },
  center: { x: 0.5, y: 0.5 },
  shapes: {},
}

/** 블렌드셰이프 배열을 이름→값 맵으로. 없는 이름은 0으로 읽힙니다. */
function toMap(categories: { categoryName: string; score: number }[]): Record<string, number> {
  const out: Record<string, number> = {}
  for (const c of categories) out[c.categoryName] = c.score
  return out
}

/**
 * 얼굴 랜드마크 번호 (MediaPipe FaceMesh 규약).
 *
 * 홍채는 `refineLandmarks`가 켜져 있을 때만 나오는 468~477번입니다.
 * 눈구석은 눈의 가로 크기를 재는 데 씁니다 — 화면에 가까이 앉으면 얼굴이
 * 크게 잡히므로, 눈 크기로 나눠야 거리에 상관없는 값이 됩니다.
 */
const IRIS_LEFT = 468
const IRIS_RIGHT = 473
const EYE_LEFT_OUTER = 33
const EYE_LEFT_INNER = 133
const EYE_RIGHT_INNER = 362
const EYE_RIGHT_OUTER = 263
const EYE_LEFT_TOP = 159
const EYE_LEFT_BOTTOM = 145
const EYE_RIGHT_TOP = 386
const EYE_RIGHT_BOTTOM = 374

/** 머리 회전이 시선 신호에 더할 수 있는 최대치. 홍채 오프셋과 같은 규모로 묶는다. */
const HEAD_LIMIT = 0.15

type Landmark = { x: number; y: number }

/** 눈 안에서 홍채가 어디에 있는가 — 0.5가 한가운데입니다. */
function irisOffset(marks: Landmark[], iris: number, a: number, b: number, top: number, bottom: number) {
  const width = marks[b].x - marks[a].x
  const height = marks[bottom].y - marks[top].y
  if (!width || !height) return null
  return {
    x: (marks[iris].x - (marks[a].x + marks[b].x) / 2) / width,
    y: (marks[iris].y - (marks[top].y + marks[bottom].y) / 2) / height,
  }
}

/**
 * 머리 방향 + 홍채 위치 → 시선 신호.
 *
 * **홍채를 씁니다.** 앞서는 블렌드셰이프(`eyeLookOutLeft` 등)를 썼는데, 그건
 * 아바타 얼굴을 움직이려고 만든 값이라 거칠고 잘 포화됩니다. 같은 모델이 주는
 * 홍채 좌표가 훨씬 곧습니다 — 눈구석 사이에서 홍채가 어디쯤인지가 곧 눈이
 * 어디를 보는지입니다.
 *
 * 눈 크기로 나눠 거리에 무디게 만들고, 두 눈의 평균을 씁니다. 머리 회전을
 * 더하는 것은 고개를 돌려 보는 경우를 놓치지 않기 위해서입니다.
 *
 * **부호와 배율은 신경 쓰지 않습니다.** 분류가 최근접이라 보정점과 같은 좌표계에
 * 있기만 하면 됩니다 — 뒤집혀 있어도 같은 칸으로 갑니다.
 */
function gazeFrom(marks: Landmark[] | null, matrix: number[] | null) {
  let eye = { x: 0, y: 0 }
  if (marks && marks.length > IRIS_RIGHT) {
    const left = irisOffset(marks, IRIS_LEFT, EYE_LEFT_OUTER, EYE_LEFT_INNER, EYE_LEFT_TOP, EYE_LEFT_BOTTOM)
    const right = irisOffset(marks, IRIS_RIGHT, EYE_RIGHT_INNER, EYE_RIGHT_OUTER, EYE_RIGHT_TOP, EYE_RIGHT_BOTTOM)
    const both = [left, right].filter((v): v is { x: number; y: number } => v !== null)
    if (both.length) {
      eye = {
        x: both.reduce((a, v) => a + v.x, 0) / both.length,
        y: both.reduce((a, v) => a + v.y, 0) / both.length,
      }
    }
  }
  // 4×4 변환 행렬에서 머리의 좌우·상하 회전을 꺼낸다(열 우선).
  //
  // **기여도를 묶는다.** 얼굴이 잠깐 잘못 잡히면 이 항이 통째로 튀어서, 실측에서
  // 벗어남 거리가 3.3까지 갔다(홍채 오프셋만으로는 0.25를 넘기 어렵다). 시선의
  // 본체는 홍채이고 머리는 거드는 값이라 상한을 둔다.
  const clamp = (v: number) => Math.max(-HEAD_LIMIT, Math.min(HEAD_LIMIT, v))
  const headX = matrix ? clamp(Math.asin(Math.max(-1, Math.min(1, matrix[8]))) * 0.35) : 0
  const headY = matrix ? clamp(Math.asin(Math.max(-1, Math.min(1, -matrix[9]))) * 0.35) : 0
  return { x: eye.x + headX, y: eye.y + headY }
}

/** 코끝 랜드마크. 얼굴이 프레임 어디에 있는지의 대표점으로 씁니다. */
const NOSE_TIP = 1

function centerFrom(marks: Landmark[] | null) {
  if (!marks || marks.length <= NOSE_TIP) return { x: 0.5, y: 0.5 }
  return { x: marks[NOSE_TIP].x, y: marks[NOSE_TIP].y }
}

export function useFaceTracking(stream: MediaStream | null, enabled: boolean) {
  const [state, setState] = useState<TrackingState>('idle')
  /** 초당 몇 프레임을 실제로 처리했는가 — 이 기능이 돌아가는지의 유일한 증거. */
  const [fps, setFps] = useState(0)
  const frame = useRef<FaceFrame>(EMPTY)

  const latest = useCallback(() => frame.current, [])

  useEffect(() => {
    if (!stream || !enabled) return
    let stop = false
    let timer = 0
    let video: HTMLVideoElement | null = null
    let landmarker: { detectForVideo: (v: HTMLVideoElement, t: number) => unknown; close: () => void } | null =
      null

    const run = async () => {
      setState('loading')
      try {
        const vision = await import('@mediapipe/tasks-vision')
        const files = await vision.FilesetResolver.forVisionTasks('/vision')
        const made = await vision.FaceLandmarker.createFromOptions(files, {
          baseOptions: { modelAssetPath: '/vision/face_landmarker.task', delegate: 'GPU' },
          runningMode: 'VIDEO',
          numFaces: 1,
          // 홍채 좌표(468~477)가 시선의 원료다. 이게 없으면 블렌드셰이프로
          // 떨어지는데 그쪽은 거칠어 9칸을 못 가른다.
          outputFaceBlendshapes: true,
          outputFacialTransformationMatrixes: true,
        })
        if (stop) {
          made.close()
          return
        }
        landmarker = made as unknown as typeof landmarker

        // 모델은 <video>에서 읽는다. 화면에 붙이지 않고 메모리에만 둔다 —
        // 미리보기는 SelfView가 따로 그린다.
        video = document.createElement('video')
        video.srcObject = stream
        video.muted = true
        video.playsInline = true
        await video.play()

        let counted = 0
        let since = performance.now()
        setState('running')

        timer = window.setInterval(() => {
          if (stop || !video || !landmarker) return
          const now = performance.now()
          let result: {
            faceLandmarks?: { x: number; y: number }[][]
            faceBlendshapes?: { categories: { categoryName: string; score: number }[] }[]
            facialTransformationMatrixes?: { data: number[] }[]
          }
          try {
            result = landmarker.detectForVideo(video, now) as typeof result
          } catch {
            return
          }
          const categories = result.faceBlendshapes?.[0]?.categories
          if (categories) {
            frame.current = {
              at: now,
              found: true,
              gaze: gazeFrom(
                result.faceLandmarks?.[0] ?? null,
                result.facialTransformationMatrixes?.[0]?.data ?? null,
              ),
              center: centerFrom(result.faceLandmarks?.[0] ?? null),
              shapes: toMap(categories),
            }
          } else {
            frame.current = { ...frame.current, at: now, found: false }
          }
          counted += 1
          if (now - since >= 1000) {
            setFps(Math.round((counted * 1000) / (now - since)))
            counted = 0
            since = now
          }
        }, INTERVAL_MS)
      } catch {
        if (!stop) setState('failed')
      }
    }
    void run()

    return () => {
      stop = true
      window.clearInterval(timer)
      landmarker?.close()
      video?.pause()
      if (video) video.srcObject = null
    }
  }, [stream, enabled])

  return { state, fps, latest }
}
