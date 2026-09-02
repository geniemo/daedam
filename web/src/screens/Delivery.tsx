import { IMPRESSIONS } from '@/video/expression'
import { SectionLabel } from '@/components/ui'
import type { ExpressionReport, GazeReport } from '@/api/preparation'

/**
 * 리포트의 전달력 — 시선과 표정.
 *
 * 두 지표는 같은 스냅샷 판독에서 옵니다. 시선은 방향(지원자 기준), 표정은 인상
 * 배분입니다. 그래도 **한쪽만 있을 수 있습니다** — 판독이 실패한 판의 시선은
 * 옛 홍채 기록으로 남을 수 있습니다. 빈 쪽은 감추지 않고 무엇이 없는지 말합니다.
 *
 * **시선 격자는 3×3입니다.** 판독의 방향은 다섯(정면·좌·우·상·하)이라 대각 칸이
 * 늘 0인데도 아홉 칸을 유지합니다 — 십자로 줄여 봤더니 데이터에는 정직했지만
 * 보기에 못했습니다(사용자 판정). 격자가 화면 좌표가 아니라 정면 기준의
 * 방향이라는 점은 그대로라, 가운데 칸에만 이름을 적고 나머지는 방향으로 읽게
 * 둡니다.
 *
 * **판독의 관찰(고칠 점)은 여기 없습니다.** 처음엔 이 섹션의 발에 "다음
 * 면접에서"로 뒀는데, 내용 평가의 보완할 점과 조언 목록이 두 집이 돼
 * 어색했습니다(사용자 지적). 서버가 보완할 점에 합쳐 한 집으로 보냅니다 —
 * evaluation.py 참고. 이 섹션은 관찰된 사실만 그립니다.
 *
 * **시선의 한 줄 평은 등급이 아니라 서술입니다.** 면접에서 정면을 몇 % 봐야
 * 하는지에 대한 근거가 문헌에 없어서(찾아봤고 없습니다) 관찰된 쏠림만 적습니다.
 */

/**
 * 흐름 띠의 "이탈 순간" 색. **막대는 강조색 하나입니다** — 길이가 이미 크기를
 * 말하는데 색까지 갈리면 진한 색의 작은 값이 가장 세 보입니다(실측: 잉크색
 * 당황 11%가 카드에서 제일 도드라졌다). 카테고리 색은 "어떤 순간이었나"를
 * 답하는 띠와 범례에만 씁니다.
 */
const TICK_COLORS: Record<string, string> = {
  confident: 'var(--color-accent)',
  tense: 'color-mix(in srgb, var(--color-accent) 55%, var(--color-surface))',
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

function GazeCard({ gaze }: { gaze?: GazeReport }) {
  if (!gaze) {
    return (
      <div className="flex flex-col gap-[10px] rounded-card border border-line bg-surface p-[18px]">
        <span className="text-[13.5px] font-bold">시선 처리</span>
        <p className="m-0 text-[12.5px] leading-[1.7] text-muted">
          시선 기록이 없습니다. 카메라를 켜고 진행하면 다음 면접부터 여기에
          시선 분석이 담깁니다.
        </p>
      </div>
    )
  }
  // 얼굴이 잡힌 시간이 짧으면 나머지 숫자를 믿을 수 없다. 감추지 않고 말한다.
  const thin = gaze.seconds < 30
  return (
    <div className="flex h-full flex-col gap-[14px] rounded-card border border-line bg-surface p-[18px]">
      <div className="flex items-baseline">
        <span className="text-[13.5px] font-bold">시선 처리</span>
        <div className="flex-1" />
        <span className="num text-[13px] font-semibold text-accent">
          정면 {Math.round(gaze.steady * 100)}%
        </span>
      </div>
      {thin && (
        <p className="m-0 text-[12px] text-accent">
          얼굴이 보인 시간이 {gaze.seconds}초뿐이라 비율은 참고만 해 주세요.
        </p>
      )}
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
      <span className="mt-auto text-[12px] leading-[1.65] text-body-2">{gazeVerdict(gaze)}</span>
    </div>
  )
}

function ExpressionCard({ expression }: { expression?: ExpressionReport }) {
  if (!expression) {
    return (
      <div className="flex flex-col gap-[10px] rounded-card border border-line bg-surface p-[18px]">
        <span className="text-[13.5px] font-bold">표정</span>
        {/* 판독이 없으면 없다고 말한다 — 근육 신호로 대신 채우지 않는다.
            그쪽은 차분한 얼굴에서 전부 한 칸으로 몰리는 것이 실측됐다. */}
        <p className="m-0 text-[12.5px] leading-[1.7] text-muted">
          표정 판독을 만들지 못했습니다. 카메라를 켜고 진행했다면 다음
          리포트부터 담깁니다.
        </p>
      </div>
    )
  }
  const thin = expression.frames < 10
  const series = expression.series ?? []
  const moments = series.filter((key) => key !== 'focused')
  return (
    <div className="flex h-full flex-col gap-[14px] rounded-card border border-line bg-surface p-[18px]">
      <span className="text-[13.5px] font-bold">표정</span>
      {thin && (
        <p className="m-0 text-[12px] text-accent">
          스냅샷이 {expression.frames}장뿐이라 비율은 참고만 해 주세요.
        </p>
      )}

      {/* 카드 높이는 옆의 격자가 정한다. 막대 목록이 남는 높이를 나눠 가지게
          해서 막대와 띠 사이에 죽은 공백이 생기지 않게 한다 — 띠를 바닥에
          붙였더니(mt-auto) 가운데가 통째로 비었다(실측 스크린샷). */}
      <div className="flex flex-1 flex-col justify-between py-[2px]">
        {IMPRESSIONS.map((impression) => {
          const share = expression.impressions[impression.key] ?? 0
          return (
            <div key={impression.key} className="flex items-center gap-[10px]">
              <span className="w-[42px] shrink-0 text-[12.5px] text-body-2">
                {impression.label}
              </span>
              <div className="h-[7px] flex-1 rounded-chip bg-hair-2">
                <div
                  className="h-full rounded-chip"
                  style={{ width: `${share * 100}%`, background: 'var(--color-accent)' }}
                />
              </div>
              <span className="num w-[42px] shrink-0 text-right text-[12.5px] font-semibold">
                {(share * 100).toFixed(1)}%
              </span>
            </div>
          )
        })}
      </div>

      {/* 흐름. 기본 상태(집중)는 조용한 트랙이고 **이탈 순간만** 색이 선다 —
          "언제 긴장했나"가 이 띠의 질문이라서다. 우세를 전부 칠하면 이탈이
          없는 면접에서 통짜 단색 블록이 된다(실측 스크린샷). 조용한 트랙은
          조용했다는 말 그 자체다. */}
      {series.length > 0 && moments.length === 0 && (
        /* 이탈 순간이 하나도 없으면 트랙을 그리지 않는다. 조용한 회색 띠는
           "내내 안정"이 아니라 고장으로 읽혔다(실측 — "띠가 아예 비어있는데?").
           없는 것은 말로 하는 편이 낫다. */
        <p className="m-0 text-[12px] leading-[1.65] text-faint">
          긴장·당황으로 기운 구간 없이 집중된 흐름이 유지됐습니다.
        </p>
      )}
      {series.length > 0 && moments.length > 0 && (
        <div className="flex flex-col gap-[6px]">
          {moments.length > 0 && (
            <div className="flex items-center justify-end gap-[10px] text-[10.5px] text-faint">
              {IMPRESSIONS.filter(
                (impression) =>
                  impression.key !== 'focused' && moments.includes(impression.key),
              ).map((impression) => (
                <span key={impression.key} className="flex items-center gap-[4px]">
                  <span
                    className="inline-block rounded-full"
                    style={{ width: 6, height: 6, background: TICK_COLORS[impression.key] }}
                  />
                  {impression.label}
                </span>
              ))}
            </div>
          )}
          <div className="flex overflow-hidden rounded-chip bg-hair-2" style={{ height: 12 }}>
            {series.map((key, i) => (
              <span
                key={i}
                className="flex-1"
                style={{
                  background: key !== 'focused' ? (TICK_COLORS[key] ?? 'transparent') : 'transparent',
                }}
              />
            ))}
          </div>
          <div className="flex items-center justify-between text-[10.5px] text-faintest">
            <span>면접 시작</span>
            <span>종료</span>
          </div>
        </div>
      )}
    </div>
  )
}

export function Delivery({
  gaze,
  expression,
}: {
  gaze?: GazeReport
  expression?: ExpressionReport
}) {
  return (
    <section className="border-b border-line py-[30px]">
      <div className="mb-[18px]">
        <SectionLabel>전달력</SectionLabel>
      </div>
      {/* 두 카드의 바닥이 맞아야 한 층으로 읽힌다 — 기본 stretch를 그대로 쓴다. */}
      <div className="grid grid-cols-2 gap-[14px]">
        <GazeCard gaze={gaze} />
        <ExpressionCard expression={expression} />
      </div>
    </section>
  )
}
