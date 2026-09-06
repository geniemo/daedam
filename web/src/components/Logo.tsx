/**
 * 심볼 C3 — 원 하나를 세로로 갈라 왼쪽 조각은 잉크(면접관), 오른쪽 조각은
 * 앰버(지원자). 자른 선이 지름보다 왼쪽(x=9.0 / 10.6)에 있어 앰버가 반원보다
 * 조금 넓고 틈은 1.6이다. 규격: design_handoff_daedam/design-system/assets/logo.
 *
 * 헤더 22 · 랜딩·온보딩 26. 이전의 사각 표식은 폐기.
 */
export function Symbol({ size = 22, onDark = false }: { size?: number; onDark?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" className="shrink-0">
      <path d="M9 3.51A9 9 0 0 0 9 20.49Z" fill={onDark ? 'var(--stage-paper)' : 'var(--color-ink)'} />
      <path d="M10.6 3.11A9 9 0 1 1 10.6 20.89Z" fill={onDark ? 'var(--stage-amber)' : 'var(--color-accent)'} />
    </svg>
  )
}

/** 심볼 + 워드마크 "대담". 간격 10, 워드마크 Pretendard 700/-.02em. */
export function Logo({ size = 26, wordmark = 20 }: { size?: number; wordmark?: number }) {
  return (
    <div className="flex items-center gap-[10px]">
      <Symbol size={size} />
      <span className="font-bold tracking-[-.02em] text-ink" style={{ fontSize: wordmark }}>
        대담
      </span>
    </div>
  )
}
