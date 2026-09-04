import { useEffect, useRef } from 'react'
import type { Camera } from './useCamera'

/**
 * 면접 화면 오른쪽의 내 얼굴.
 *
 * **거울처럼 좌우를 뒤집습니다.** 사람은 자기 모습을 거울로 봐 왔으므로 뒤집지
 * 않으면 어색합니다. 다만 뒤집는 것은 **미리보기뿐**입니다 — 녹화본은 면접관이
 * 보는 방향 그대로여야 나중에 리뷰가 됩니다.
 *
 * 아바타의 가운데 정렬을 건드리지 않으려고 absolute로 띄웁니다. 흐름에 넣으면
 * 면접관이 화면 왼쪽으로 밀려납니다.
 *
 * **자리는 우측 상단입니다.** 카메라가 화면 위에 달려 있으므로, 셀프뷰를 아래나
 * 옆에 두면 그걸 보는 동안 녹화본에서 시선이 아래로 깔립니다 — 눈맞춤을 연습해야
 * 하는 제품에서 정반대를 훈련시키는 셈입니다. 위쪽에 두면 자기를 볼 때도 시선이
 * 카메라 축 근처에 머뭅니다. 상태바(py-22 + 내용) 아래로 74px 내려 겹침을 피합니다.
 *
 * 크기는 160×120입니다. 면접 중 셀프뷰가 하는 일은 분석이 아니라 **구도 확인**
 * 입니다 — 화면에 잘 들어와 있나, 자세가 무너졌나. 얼굴을 뜯어보는 것은 리포트의
 * 녹화본이 할 일이고, 여기를 키울수록 면접관 대신 자기 얼굴을 봅니다.
 */
export function SelfView({
  camera,
  visible,
  onHide,
  onStop,
}: {
  camera: Camera
  /** 화면에 보일지. 꺼도 촬영은 계속됩니다. */
  visible: boolean
  onHide: () => void
  onStop: () => void
}) {
  const video = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const el = video.current
    if (!el) return
    el.srcObject = camera.stream
    if (camera.stream) void el.play().catch(() => {})
  }, [camera.stream])

  if (camera.state !== 'on') return null

  return (
    <div className="absolute top-[74px] right-[30px] z-4">
      <div
        className="relative overflow-hidden rounded-card border border-stage-line"
        style={{ width: 160, height: 120, background: '#0B1220' }}
      >
        {/* 스트림은 계속 물려 둔다. 요소를 떼면 다시 붙일 때 첫 프레임이
            늦고, 무엇보다 촬영이 이어진다는 사실이 코드에서 흐려진다. */}
        <video
          ref={video}
          muted
          playsInline
          className="h-full w-full object-cover"
          style={{ transform: 'scaleX(-1)', opacity: visible ? 1 : 0 }}
        />
        {!visible && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-[5px] px-2 text-center">
            <span className="text-[12px] text-stage-muted-2">내 화면을 가렸습니다</span>
            {/* 가린 것과 끈 것을 구별해 말한다. 여기서 뭉개면 "껐는데 찍혔다"가
                된다 — 얼굴 영상에서 만들면 안 되는 오해다. */}
            <span className="text-[11px] text-stage-muted-3">촬영은 계속됩니다</span>
          </div>
        )}
      </div>

      {/* 기록 중이라는 사실을 눈에 보이게 둔다 — 카메라가 켜져 있으면 3초마다
          스냅샷이 올라가 리포트의 시선·표정이 된다(useSnapshots). */}
      <div className="mt-[7px] flex items-center justify-end gap-[6px]">
        <span
          className="inline-block rounded-full"
          style={{ width: 5, height: 5, background: 'var(--color-listening)' }}
        />
        <span className="text-[11px] text-stage-muted-3">시선·표정 기록 중</span>
      </div>

      <div className="mt-[5px] flex items-center justify-end gap-[9px] whitespace-nowrap">
        <button onClick={onHide} className="text-[12px] text-stage-muted-2">
          {visible ? '내 화면 가리기' : '다시 보기'}
        </button>
        <span className="text-stage-line">·</span>
        <button onClick={onStop} className="text-[12px] text-stage-muted-3">
          카메라 끄기
        </button>
      </div>
    </div>
  )
}
