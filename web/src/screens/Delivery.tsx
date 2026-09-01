import { IMPRESSIONS, IMPRESSION_CAPTION } from '@/video/expression'
import { SectionLabel } from '@/components/ui'
import type { GazeReport } from '@/api/preparation'

/**
 * 리포트의 전달력 — 시선과 표정.
 *
 * 두 지표를 나란히 둡니다. 시선은 3×3 격자로, 표정은 막대로 보여줍니다.
 * 격자가 **화면 좌표가 아니라는 것**이 중요합니다 — 정면에서 어느 쪽으로
 * 벗어났는지를 축마다 판정해 아홉 칸에 놓은 것이라, 가운데가 정면입니다.
 * 그래서 가운데 칸에만 이름을 적고 나머지는 방향으로 읽게 둡니다.
 *
 * **한 줄 평은 등급이 아니라 서술입니다.** 면접에서 정면을 몇 % 봐야 하는지에
 * 대한 근거가 문헌에 없어서(찾아봤고 없습니다) "좋다/나쁘다"를 붙이지 않습니다.
 * 대신 관찰된 쏠림을 그대로 적습니다 — 어느 쪽으로 자주 갔는지를 알려주면 다음
 * 면접에서 고칠 것이 생기고, 그건 근거 없이 점수를 매기지 않고도 할 수 있습니다.
 * 음성 지표는 권장 범위에 출처가 있어서 판정("적정")을 달았지만 여기는 다릅니다.
 */
/**
 * 인상마다의 색. 막대와 띠가 같은 색을 써야 둘이 한 이야기로 읽힙니다.
 * 강조색 하나를 진하기로 나눕니다 — 넷에 다른 색을 주면 팔레트가 무너집니다.
 */
const IMPRESSION_COLORS: Record<string, string> = {
  confident: 'var(--color-accent)',
  focused: 'color-mix(in srgb, var(--color-accent) 55%, var(--color-surface))',
  tense: 'color-mix(in srgb, var(--color-accent) 28%, var(--color-surface))',
  flustered: 'var(--color-ink)',
}

/** 격자에서 정면(4) 다음으로 오래 머문 칸의 방향 이름. 없으면 null. */
function dominantAway(cells: number[]): string | null {
  let best = -1
  let bestShare = 0
  cells.forEach((share, i) => {
    if (i === 4 || share <= bestShare) return
    best = i
    bestShare = share
  })
  if (best < 0 || bestShare < 0.08) return null
  return ['왼쪽 위', '위', '오른쪽 위', '왼쪽', '', '오른쪽', '왼쪽 아래', '아래', '오른쪽 아래'][best]
}

/**
 * 시선 한 줄 평.
 *
 * **경계는 잠정입니다.** 면접에서 정면을 몇 % 봐야 하는지에 대한 근거가 문헌에
 * 없습니다(찾아봤고 없습니다). 그래서 "몇 % 이상이면 좋다"고 말하지 않고, 관찰된
 * 쏠림을 그대로 서술합니다 — 방향을 알려주면 다음 면접에서 고칠 것이 생깁니다.
 */
function gazeVerdict(gaze: GazeReport): string {
  const away = dominantAway(gaze.cells)
  const steady = gaze.steady
  if (steady >= 0.7) {
    return away
      ? `정면을 잘 유지했습니다. 가끔 ${away}으로 시선이 갔습니다.`
      : '정면을 안정적으로 유지했습니다.'
  }
  if (steady >= 0.4) {
    return away
      ? `정면 응시가 간헐적으로 흔들리고 ${away}으로 시선이 자주 갔습니다.`
      : '정면 응시가 간헐적으로 흔들렸습니다.'
  }
  return away
    ? `시선이 정면에 머문 시간이 짧고 ${away}으로 자주 향했습니다.`
    : '시선이 정면에 머문 시간이 짧았습니다.'
}

export function Delivery({ gaze }: { gaze: GazeReport }) {
  // 얼굴이 잡힌 시간이 짧으면 나머지 숫자를 믿을 수 없다. 감추지 않고 말한다.
  const thin = gaze.seconds < 30

  return (
    <section className="border-b border-line py-[30px]">
      <div className="mb-[18px]">
        <SectionLabel>전달력</SectionLabel>
      </div>

      {thin && (
        <p className="mt-0 mb-[16px] text-[12.5px] text-accent">
          얼굴이 보인 시간이 {gaze.seconds}초뿐이라 아래 비율은 참고만 해 주세요.
        </p>
      )}

      <div className="grid grid-cols-2 gap-[14px]">
        <div className="flex flex-col gap-[14px] rounded-card border border-line bg-surface p-[18px]">
          <div className="flex items-baseline">
            <span className="text-[13.5px] font-bold">시선 처리</span>
            <div className="flex-1" />
            <span className="num text-[13px] font-semibold text-accent">
              정면 {Math.round(gaze.steady * 100)}%
            </span>
          </div>
          {/* 정면이 가운데다. 색이 짙을수록 오래 머문 칸이다. */}
          <div className="grid grid-cols-3 gap-[6px]">
            {gaze.cells.map((share, i) => (
              <div
                key={i}
                className="flex flex-col items-center justify-center rounded-chip"
                style={{
                  height: 52,
                  background:
                    share > 0
                      ? `color-mix(in srgb, var(--color-accent) ${Math.min(100, share * 130)}%, var(--color-surface-2))`
                      : 'var(--color-surface-2)',
                  border: `1px solid ${i === 4 ? 'var(--color-accent-line)' : 'var(--color-hair-2)'}`,
                }}
              >
                <span
                  className="num text-[12.5px] font-semibold"
                  style={{ color: share > 0.4 ? '#fff' : 'var(--color-muted)' }}
                >
                  {(share * 100).toFixed(1)}%
                </span>
                {i === 4 && (
                  <span
                    className="text-[10.5px]"
                    style={{ color: share > 0.4 ? 'rgba(255,255,255,.8)' : 'var(--color-faint)' }}
                  >
                    정면
                  </span>
                )}
              </div>
            ))}
          </div>
          <span className="text-[12px] leading-[1.65] text-body-2">{gazeVerdict(gaze)}</span>
        </div>

        <div className="flex h-full flex-col gap-[14px] rounded-card border border-line bg-surface p-[18px]">
          <span className="text-[13.5px] font-bold">표정</span>

          {/* 카드 높이는 옆의 격자가 정한다. 막대 목록이 남는 높이를 나눠 가지게
              해서 아래에 죽은 여백이 생기지 않게 한다 — gap을 키우면 화면 폭에
              따라 다시 벌어진다. */}
          <div className="flex flex-1 flex-col justify-between py-[2px]">
            {IMPRESSIONS.map((impression) => {
              const share = gaze.impressions[impression.key] ?? 0
              return (
                <div key={impression.key} className="flex items-center gap-[10px]">
                  <span className="w-[42px] shrink-0 text-[12.5px] text-body-2">
                    {impression.label}
                  </span>
                  <div className="h-[7px] flex-1 rounded-chip bg-hair-2">
                    <div
                      className="h-full rounded-chip"
                      style={{
                        width: `${share * 100}%`,
                        background: IMPRESSION_COLORS[impression.key],
                      }}
                    />
                  </div>
                  <span className="num w-[42px] shrink-0 text-right text-[12.5px] font-semibold">
                    {(share * 100).toFixed(1)}%
                  </span>
                </div>
              )
            })}
          </div>
          {/* 언제 그랬는지. 비율만 두면 카드가 비고, 무엇보다 "긴장이 첫 답변에
              몰렸는지 내내 흩어져 있었는지"를 알 수 없다. */}
          {gaze.series && gaze.series.length > 0 && (
            <div className="flex flex-col gap-[6px]">
              <div className="flex overflow-hidden rounded-chip" style={{ height: 22 }}>
                {gaze.series.map((key, i) => (
                  <span
                    key={i}
                    className="flex-1"
                    style={{ background: IMPRESSION_COLORS[key] ?? 'var(--color-hair-2)' }}
                  />
                ))}
              </div>
              <div className="flex items-center justify-between text-[10.5px] text-faintest">
                <span>면접 시작</span>
                <span>종료</span>
              </div>
            </div>
          )}
          <span className="text-[11.5px] leading-[1.6] text-faintest">{IMPRESSION_CAPTION}</span>
        </div>
      </div>
    </section>
  )
}
