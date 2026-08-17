import type { ReactNode, TextareaHTMLAttributes, InputHTMLAttributes } from 'react'

/* Shared primitives. Exact values come from README §Design Tokens and the
   per-screen specs; §Shadows: 그림자를 쓰지 않습니다 — depth is borders and
   background contrast only. */

export function Card({
  children,
  className = '',
  onClick,
}: {
  children: ReactNode
  className?: string
  onClick?: () => void
}) {
  return (
    <div
      onClick={onClick}
      className={`rounded-card border border-line bg-surface ${onClick ? 'cursor-pointer' : ''} ${className}`}
    >
      {children}
    </div>
  )
}

export function PrimaryButton({
  children,
  onClick,
  className = '',
}: {
  children: ReactNode
  onClick?: () => void
  className?: string
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-control bg-ink font-semibold text-white ${className}`}
    >
      {children}
    </button>
  )
}

export function OutlineButton({
  children,
  onClick,
  className = '',
}: {
  children: ReactNode
  onClick?: () => void
  className?: string
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-control border border-field bg-surface font-semibold text-ink ${className}`}
    >
      {children}
    </button>
  )
}

/** 3px 진행 바. 트랙 #EEF0F4 / 채움 #B57F1C */
export function ProgressBar({
  pct,
  className = '',
  height = 3,
}: {
  pct: number
  className?: string
  height?: number
}) {
  return (
    <div className={`w-full bg-hair-2 ${className}`} style={{ height }}>
      <div
        className="h-full bg-accent"
        style={{ width: `${pct}%`, transition: 'width .4s ease' }}
      />
    </div>
  )
}

/**
 * 총량을 모르는 작업용 막대. 채움 비율 대신 조각이 지나간다.
 *
 * ProgressBar와 굵기·색이 같아 화면에서 같은 자리를 차지하지만, 약속하는 것이
 * 다르다 — 이건 "얼마나 남았다"가 아니라 "아직 돌고 있다"만 말한다.
 */
export function IndeterminateBar({ height = 3 }: { height?: number }) {
  return (
    <div className="w-full overflow-hidden bg-hair-2" style={{ height }}>
      <div className="animate-dm-slide h-full bg-accent" style={{ width: '25%' }} />
    </div>
  )
}

/** 강조 점 + 라벨 — "면접 준비 완료" 등 */
export function AccentDot({ size = 5 }: { size?: number }) {
  return (
    <span
      className="inline-block shrink-0 rounded-full bg-accent"
      style={{ width: size, height: size }}
    />
  )
}

export function Spinner({ size = 13 }: { size?: number }) {
  return (
    <span
      className="inline-block shrink-0 animate-dm-spin rounded-full border-accent"
      style={{ width: size, height: size, borderWidth: 1.5, borderTopColor: 'transparent' }}
    />
  )
}

export function CheckDot({ size = 14 }: { size?: number }) {
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center rounded-full bg-ink text-white"
      style={{ width: size, height: size, fontSize: 9 }}
    >
      ✓
    </span>
  )
}

export function EmptyDot({ size = 13 }: { size?: number }) {
  return (
    <span
      className="inline-block shrink-0 rounded-full border-line"
      style={{ width: size, height: size, borderWidth: 1.5 }}
    />
  )
}

export function Label({ children }: { children: ReactNode }) {
  return <div className="text-[13px] font-semibold">{children}</div>
}

/** 섹션 라벨 — 12px/600 #8E98A8 letter-spacing .04em */
export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="text-[12px] font-semibold tracking-[.04em] text-faint">{children}</div>
  )
}

export function TextField(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`rounded-control border border-field bg-surface px-[13px] py-[12px] text-[14.5px] ${props.className ?? ''}`}
    />
  )
}

/**
 * 여러 줄 입력란. 내용만큼 세로로 자란다.
 *
 * 지원서 항목 본문이 200자를 넘는 일이 흔한데 고정 높이면 좁은 창으로 긴 글을
 * 스크롤하며 쓰게 된다. field-sizing:content가 내용에 맞춰 늘리고, min-h가
 * 빈 칸일 때의 바닥이 된다. resize-y는 남겨 둔다 — 사용자가 더 줄이거나
 * 늘리고 싶을 때가 있다.
 */
export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`min-h-[140px] resize-y rounded-control border border-field-2 bg-surface px-[11px] py-[10px] text-[13.5px] leading-[1.65] [field-sizing:content] ${props.className ?? ''}`}
    />
  )
}

/** 칩 · 배지 — 2px radius */
export function Chip({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={`rounded-chip border border-line-2 bg-surface-2 px-[9px] py-[4px] text-[11.5px] text-muted ${className}`}
    >
      {children}
    </span>
  )
}

/** 텍스트 아이콘 (§Assets: 아이콘류는 모두 텍스트 문자입니다) */
export const Caret = ({ open, className = '' }: { open: boolean; className?: string }) => (
  <span className={className}>{open ? '▲' : '▼'}</span>
)
