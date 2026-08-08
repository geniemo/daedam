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

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`min-h-[96px] resize-y rounded-control border border-field-2 bg-surface px-[11px] py-[10px] text-[13.5px] leading-[1.65] ${props.className ?? ''}`}
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
