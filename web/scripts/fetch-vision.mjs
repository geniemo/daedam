// MediaPipe 실행 파일과 얼굴 모델을 public/vision/에 놓는다.
//
// 26MB짜리 서드파티 바이너리라 저장소에 넣지 않는다. WASM은 설치된 패키지에서
// 복사하고(버전이 package.json과 자동으로 맞는다), 모델만 구글에서 받는다.
// 이미 있으면 아무것도 하지 않으므로 빌드마다 네트워크를 타지 않는다.
import { copyFile, mkdir, stat, writeFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'

const require = createRequire(import.meta.url)
const OUT = 'public/vision'
const MODEL_URL =
  'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'

const exists = async (p) => (await stat(p).catch(() => null)) !== null

await mkdir(OUT, { recursive: true })

const wasmDir = join(dirname(require.resolve('@mediapipe/tasks-vision')), 'wasm')
for (const name of [
  'vision_wasm_internal.wasm',
  'vision_wasm_internal.js',
  'vision_wasm_nosimd_internal.wasm',
  'vision_wasm_nosimd_internal.js',
]) {
  const to = join(OUT, name)
  if (await exists(to)) continue
  await copyFile(join(wasmDir, name), to)
  console.log(`복사 ${name}`)
}

const model = join(OUT, 'face_landmarker.task')
if (!(await exists(model))) {
  const res = await fetch(MODEL_URL)
  if (!res.ok) throw new Error(`얼굴 모델을 받지 못했습니다: ${res.status}`)
  await writeFile(model, Buffer.from(await res.arrayBuffer()))
  console.log('내려받음 face_landmarker.task')
}
console.log('vision 자산 준비 완료')
