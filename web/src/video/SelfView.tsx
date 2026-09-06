import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import type { Camera } from './useCamera'

/** 두 배치 사이의 자리 바꿈. 면접 화면의 구체와 같은 값이어야 둘이 함께 움직인다. */
export const SWAP_TRANSITION =
  'left .45s ease-in-out, top .45s ease-in-out, width .45s ease-in-out, height .45s ease-in-out, transform .45s ease-in-out'

/**
 * 면접 화면의 내 얼굴.
 *
 * **거울처럼 좌우를 뒤집습니다.** 사람은 자기 모습을 거울로 봐 왔으므로 뒤집지
 * 않으면 어색합니다. 다만 뒤집는 것은 **미리보기뿐**입니다 — 녹화본은 면접관이
 * 보는 방향 그대로여야 나중에 리뷰가 됩니다.
 *
 * **배치가 둘입니다.** 기본은 우상단 240×180 — 면접 중 셀프뷰가 하는 일은
 * 분석이 아니라 구도 확인이라 작습니다. "내 모습 크게 보기"를 누르면 웹캠이
 * 가운데 4:3으로 오고 면접관은 우상단 92px로 들어갑니다(거울 배치) — 표정을
 * 보며 연습하는 사람용입니다. PiP를 키우는 대신 자리를 바꾸는 이유: 오래 볼
 * 화면은 카메라 축 근처에 있어야 녹화된 시선이 정면으로 남습니다. 두 상자는
 * 마운트를 바꾸지 않고 .45s에 동시에 자리를 트레이드합니다 — 좌표는 면접
 * 화면이 재서 내려줍니다.
 *
 * 기본 배치에서 우상단인 것도 같은 이유입니다. 카메라가 화면 위에 달려 있으므로
 * 셀프뷰를 아래에 두면 그걸 보는 동안 녹화본에서 시선이 아래로 깔립니다.
 */
export function SelfView({
  camera,
  mirror,
  visible,
  top,
  width,
  height,
  onMirror,
  onHide,
  onStop,
}: {
  camera: Camera
  /** 거울 배치 — 웹캠이 가운데. */
  mirror: boolean
  /** 화면에 보일지. 꺼도 촬영은 계속됩니다. 거울 배치에서는 늘 보입니다. */
  visible: boolean
  /** 거울 배치일 때 상자의 윗변(면접 화면의 무대 영역 기준). */
  top: number
  width: number
  height: number
  onMirror: () => void
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

  const shown = mirror || visible
  return (
    <div
      className="absolute flex flex-col gap-[7px]"
      style={{
        transition: SWAP_TRANSITION,
        zIndex: mirror ? 2 : 4,
        ...(mirror
          ? { left: '50%', top, width, transform: 'translateX(-50%)' }
          : { left: 'calc(100% - 30px - 240px)', top: 14, width: 240, transform: 'translateX(0)' }),
      }}
    >
      <div
        className="relative w-full overflow-hidden"
        style={{
          height,
          borderRadius: 8,
          border: '1px solid var(--stage-line-warm)',
          background: 'rgba(0,0,0,.45)',
          boxShadow: '0 30px 70px -30px rgba(0,0,0,.9)',
          transition: 'height .45s ease-in-out',
        }}
      >
        {/* 스트림은 계속 물려 둔다. 요소를 떼면 다시 붙일 때 첫 프레임이
            늦고, 무엇보다 촬영이 이어진다는 사실이 코드에서 흐려진다. */}
        <video
          ref={video}
          muted
          playsInline
          className="h-full w-full object-cover"
          style={{ transform: 'scaleX(-1)', opacity: shown ? 1 : 0 }}
        />
        {!shown && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-[5px] px-2 text-center">
            <span className="text-[12px]" style={{ color: 'var(--stage-ink-warm)' }}>
              내 화면을 가렸습니다
            </span>
            {/* 가린 것과 끈 것을 구별해 말한다. 여기서 뭉개면 "껐는데 찍혔다"가
                된다 — 얼굴 영상에서 만들면 안 되는 오해다. */}
            <span className="text-[11px]" style={{ color: 'var(--stage-dim)' }}>
              촬영은 계속됩니다
            </span>
          </div>
        )}
      </div>

      {/* 라벨은 도착 자리에서 다시 나타난다 — 움직이는 동안 글자가 상자를
          따라다니면 어지럽다. */}
      <div
        key={String(mirror)}
        className="flex flex-col gap-[5px]"
        style={{ animation: 'dm-fade .3s ease .3s both' }}
      >
        {mirror ? (
          <div className="flex items-center gap-[9px] whitespace-nowrap">
            <Recording />
            <div className="flex-1" />
            <Action onClick={onMirror}>면접관 크게 보기</Action>
            <Sep />
            <Action onClick={onStop} dim>
              카메라 끄기
            </Action>
          </div>
        ) : (
          <>
            <div className="flex justify-end">
              <Recording />
            </div>
            <div className="flex justify-end gap-[9px] whitespace-nowrap">
              <Action onClick={onMirror}>내 모습 크게 보기</Action>
              <Sep />
              <Action onClick={onHide}>{visible ? '내 화면 가리기' : '다시 보기'}</Action>
              <Sep />
              <Action onClick={onStop} dim>
                카메라 끄기
              </Action>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

/** 기록 중이라는 사실을 눈에 보이게 둔다 — 카메라가 켜져 있으면 3초마다
    스냅샷이 올라가 리포트의 시선·표정이 된다(useSnapshots). */
function Recording() {
  return (
    <div className="flex items-center gap-[6px]">
      <span className="inline-block rounded-full" style={{ width: 5, height: 5, background: 'var(--stage-mint)' }} />
      <span className="text-[11px]" style={{ color: 'var(--stage-dim)' }}>
        시선·표정 기록 중
      </span>
    </div>
  )
}

function Action({ onClick, dim, children }: { onClick: () => void; dim?: boolean; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-[12px]"
      style={{ color: dim ? 'var(--stage-dim-2)' : 'var(--stage-ink-warm)' }}
    >
      {children}
    </button>
  )
}

const Sep = () => <span style={{ color: 'rgba(255,255,255,.18)' }}>·</span>
