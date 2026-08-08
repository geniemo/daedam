import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useActiveCard, useAnnotationCounts, useAppStore } from '@/store/app'
import { doc, fill, uncertainRefs } from '@/data/mock'
import { blockId } from '@/data/types'
import type { DocBlock } from '@/data/types'

/**
 * README §6. 리포트 검토
 *
 * 설계 근거: 질문 생성의 입력은 리포트 원문 + 사용자 정정 사항 두 개입니다.
 * 리포트에서 사실을 추출한 별도 목록을 만들어 그것만 편집하게 하면 사용자가
 * 고친 것과 질문에 들어가는 것이 달라집니다. 그래서 문서 자체가 검토 대상이고,
 * 사용자 입력은 원문을 수정하지 않는 주석(delta)으로만 쌓입니다.
 */
export function Review() {
  const nav = useNavigate()
  const card = useActiveCard()
  const { flags, memos, toggleFlag, addMemo, removeMemo } = useAppStore()
  const { flagged, memoed } = useAnnotationCounts()
  const [memoOpenId, setMemoOpenId] = useState<string | null>(null)
  const [memoDraft, setMemoDraft] = useState('')

  const edited = flagged + memoed > 0
  const F = (t: string) => fill(t, card.company, card.role)

  const scrollTo = (id: string) => {
    const el = document.getElementById(id)
    if (!el) return
    window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - 96, behavior: 'smooth' })
  }

  return (
    <>
      <div className="mx-auto flex max-w-(--container-review) items-start gap-9 px-8 pt-[34px] pb-[130px]">
        {/* 좌측 사이드바 */}
        <aside className="sticky top-[88px] flex w-[236px] shrink-0 flex-col gap-5">
          <div className="flex flex-col gap-[8px]">
            <div className="text-[11.5px] font-semibold tracking-[.04em] text-accent">
              확인이 필요한 대목 {uncertainRefs.length}
            </div>
            {uncertainRefs.map((r) => (
              <div
                key={r.title}
                onClick={() => scrollTo(blockId(r.si, r.bi))}
                className="cursor-pointer rounded-control border border-accent-line bg-accent-bg px-3 py-[11px]"
              >
                <div className="text-[12.5px] font-semibold">{r.title}</div>
                <div className="mt-[3px] text-[11.5px] leading-[1.55] text-faint">{r.reason}</div>
              </div>
            ))}
          </div>

          <div className="flex flex-col gap-[7px] border-t border-line pt-5">
            <div className="text-[11.5px] font-semibold text-faint">목차</div>
            {doc.map((s, i) => (
              <button
                key={s.title}
                onClick={() => scrollTo(`sec-${i}`)}
                className="text-left text-[12.5px] text-muted"
              >
                {s.title}
              </button>
            ))}
          </div>
        </aside>

        {/* 우측 문서 */}
        <article className="flex-1 rounded-card border border-line bg-surface px-10 py-9">
          <div className="text-[11.5px] text-faintest">8월 4일 생성</div>
          <h1 className="mt-[6px] mb-[8px] text-[23px] leading-[1.4] font-bold tracking-[-.03em]">
            {card.company} 면접 준비 리서치
          </h1>
          <p className="m-0 text-[13px] text-muted">
            사실과 다른 대목에 표시하거나, 알고 계신 내용을 메모로 남겨 주세요.
          </p>

          {doc.map((section, si) => (
            <section key={section.title} id={`sec-${si}`}>
              <h2 className="mt-[30px] mb-[6px] border-b border-hair-2 pb-[10px] text-[16px] font-bold tracking-[-.02em]">
                {section.title}
              </h2>
              {section.blocks.map((block, bi) => {
                const id = blockId(si, bi)
                // 출처를 뺀 나머지가 주석 대상입니다.
                if (block.type === 'refs') {
                  return (
                    <div key={id} className="flex flex-col gap-[6px] py-[9px] pl-3">
                      {block.refs.map((r) => (
                        <div key={r.n} className="flex gap-[6px]">
                          <span className="num w-5 shrink-0 text-[11.5px] text-faintest">{r.n}</span>
                          <span className="text-[12.5px] text-muted">{r.label}</span>
                        </div>
                      ))}
                    </div>
                  )
                }
                return (
                  <AnnotatableBlock
                    key={id}
                    id={id}
                    block={block}
                    render={F}
                    flagged={!!flags[id]}
                    memos={memos[id] ?? []}
                    memoOpen={memoOpenId === id}
                    memoDraft={memoDraft}
                    onToggleFlag={() => toggleFlag(id)}
                    onOpenMemo={() => {
                      setMemoOpenId(memoOpenId === id ? null : id)
                      setMemoDraft('')
                    }}
                    onDraft={setMemoDraft}
                    onSubmitMemo={() => {
                      const v = memoDraft.trim()
                      if (!v) return
                      addMemo(id, v)
                      setMemoOpenId(null)
                      setMemoDraft('')
                    }}
                    onRemoveMemo={(i) => removeMemo(id, i)}
                  />
                )
              })}
            </section>
          ))}
        </article>
      </div>

      {/* 하단 고정 바 */}
      <div
        className="fixed inset-x-0 bottom-0 z-30 border-t border-line"
        style={{ background: 'rgba(255,255,255,.94)', backdropFilter: 'blur(8px)' }}
      >
        <div className="mx-auto flex max-w-(--container-review) items-center px-8 py-[14px]">
          <span className="text-[13px] text-muted">
            {edited ? `정정 ${flagged}건 · 메모 ${memoed}건` : '표시하거나 메모한 대목이 없습니다'}
          </span>
          <div className="flex-1" />
          <button onClick={() => nav('/ready')} className="mr-4 text-[13px] text-muted">
            돌아가기
          </button>
          {edited ? (
            <button
              onClick={() => nav('/regen')}
              className="rounded-control border border-ink bg-ink px-5 py-[10px] text-[13.5px] font-semibold text-white"
            >
              질문 다시 뽑기
            </button>
          ) : (
            <button
              onClick={() => nav('/ready')}
              className="rounded-control border border-field bg-surface px-5 py-[10px] text-[13.5px] font-semibold text-ink"
            >
              이대로 진행
            </button>
          )}
        </div>
      </div>
    </>
  )
}

interface BlockProps {
  id: string
  block: Exclude<DocBlock, { type: 'refs' }>
  render: (t: string) => string
  flagged: boolean
  memos: string[]
  memoOpen: boolean
  memoDraft: string
  onToggleFlag: () => void
  onOpenMemo: () => void
  onDraft: (v: string) => void
  onSubmitMemo: () => void
  onRemoveMemo: (i: number) => void
}

function AnnotatableBlock({
  id,
  block,
  render,
  flagged,
  memos,
  memoOpen,
  memoDraft,
  onToggleFlag,
  onOpenMemo,
  onDraft,
  onSubmitMemo,
  onRemoveMemo,
}: BlockProps) {
  return (
    <div
      id={id}
      className="flex gap-[14px] border-l-2 py-[9px] pr-[10px] pl-3"
      style={{
        borderLeftColor: flagged ? 'var(--color-accent)' : 'transparent',
        background: flagged ? 'var(--color-accent-bg-2)' : 'transparent',
      }}
    >
      <div className="flex flex-1 flex-col gap-2">
        {block.type === 'p' && (
          <p
            className="m-0 text-[14px] leading-[1.9]"
            style={{ color: flagged ? '#A9B2C0' : 'var(--color-body)' }}
          >
            {render(block.text)}
          </p>
        )}

        {block.type === 'li' && (
          <div className="flex gap-[8px]">
            <span className="text-[12px] text-field">—</span>
            <span
              className="text-[14px] leading-[1.85]"
              style={{ color: flagged ? '#A9B2C0' : 'var(--color-body)' }}
            >
              {render(block.text)}
            </span>
          </div>
        )}

        {block.type === 'table' && (
          <div className="overflow-hidden rounded-control border border-hair-2">
            <div
              className="grid bg-surface-2 px-3 py-[8px] text-[11.5px] font-semibold text-muted"
              style={{ gridTemplateColumns: '96px 1fr 120px' }}
            >
              {block.head.map((h) => (
                <span key={h}>{h}</span>
              ))}
            </div>
            {block.rows.map((r) => (
              <div
                key={r.a}
                className="grid border-t border-hair-3 px-3 py-[8px] text-[12.5px]"
                style={{ gridTemplateColumns: '96px 1fr 120px' }}
              >
                <span className="num">{r.a}</span>
                <span>{render(r.b)}</span>
                <span>{r.c}</span>
              </div>
            ))}
          </div>
        )}

        {flagged && (
          <span className="w-fit rounded-chip border border-accent-line bg-accent-bg px-2 py-[3px] text-[11px] font-semibold text-accent">
            사실과 다름으로 표시함
          </span>
        )}

        {memos.map((m, i) => (
          <div
            key={`${m}-${i}`}
            className="flex items-start gap-3 rounded-control border border-hair-2 bg-surface-2 px-3 py-[10px]"
          >
            <div className="flex flex-1 flex-col gap-[4px]">
              <span className="text-[11px] font-semibold text-accent">메모</span>
              <span className="text-[13px] text-body-2">{m}</span>
            </div>
            <button onClick={() => onRemoveMemo(i)} className="text-[11.5px] text-faint">
              삭제
            </button>
          </div>
        ))}

        {memoOpen && (
          <div className="flex gap-[6px]">
            <input
              autoFocus
              value={memoDraft}
              onChange={(e) => onDraft(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && onSubmitMemo()}
              placeholder="아는 내용이나 정정할 내용을 적어 주세요"
              className="flex-1 rounded-control border border-field-2 px-[11px] py-[9px] text-[13px]"
            />
            <button
              onClick={onSubmitMemo}
              className="rounded-control bg-ink px-[14px] py-[9px] text-[12.5px] font-semibold text-white"
            >
              남기기
            </button>
          </div>
        )}
      </div>

      <div className="flex shrink-0 flex-col gap-[6px] pt-[3px]">
        <button
          onClick={onToggleFlag}
          className="rounded-chip border px-[9px] py-[5px] text-[11.5px] whitespace-nowrap"
          style={
            flagged
              ? {
                  color: 'var(--color-accent)',
                  borderColor: 'var(--color-accent-line)',
                  background: 'var(--color-accent-bg)',
                }
              : {
                  color: 'var(--color-faint)',
                  borderColor: 'var(--color-line)',
                  background: '#fff',
                }
          }
        >
          {flagged ? '표시 해제' : '사실과 다름'}
        </button>
        <button
          onClick={onOpenMemo}
          className="rounded-chip border border-line bg-surface px-[9px] py-[5px] text-[11.5px] whitespace-nowrap text-faint"
        >
          메모
        </button>
      </div>
    </div>
  )
}
