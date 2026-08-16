import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { getInterview, saveReport } from '@/api/preparation'
import { useActiveCard } from '@/store/app'
import { doc as mockDoc } from '@/data/mock'
import type { DocBlock, DocSection } from '@/data/types'

/**
 * README §6. 리포트 검토
 *
 * 설계 근거: 질문 생성의 입력은 리포트 원문입니다. 원문은 그대로 두고 주석만
 * 쌓으면 사용자가 고친 것과 질문에 들어가는 것이 갈립니다. 그래서 문서 자체가
 * 편집 대상이고, 저장하면 그 리포트로 질문을 다시 뽑습니다.
 */
export function Review() {
  const nav = useNavigate()
  const card = useActiveCard()
  const [draft, setDraft] = useState<DocSection[] | null>(null)
  const [saving, setSaving] = useState(false)

  // 서버가 없으면(프론트 단독 실행) 목업 문서로 화면 모양만 유지합니다.
  const { data } = useQuery({
    queryKey: ['interview', card.id],
    queryFn: () => getInterview(card.id),
    retry: false,
  })
  const original = data?.report ?? mockDoc
  const sections = draft ?? original

  // 다른 면접으로 옮길 때만 초안을 버립니다. data 참조가 바뀔 때마다 버리면
  // 재조회 한 번에 고친 내용이 통째로 날아갑니다.
  useEffect(() => setDraft(null), [card.id])

  const edited = useMemo(
    () => draft !== null && JSON.stringify(draft) !== JSON.stringify(original),
    [draft, original],
  )

  const scrollTo = (id: string) => {
    const el = document.getElementById(id)
    if (!el) return
    window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - 96, behavior: 'smooth' })
  }

  /** 블록 하나를 갈아끼운 새 문서. 원본 배열은 건드리지 않습니다. */
  const replaceBlock = (si: number, bi: number, block: DocBlock) =>
    setDraft(
      sections.map((section, i) =>
        i !== si
          ? section
          : { ...section, blocks: section.blocks.map((b, j) => (j === bi ? block : b)) },
      ),
    )

  const submit = async () => {
    if (!edited || !draft) {
      nav('/ready')
      return
    }
    setSaving(true)
    try {
      await saveReport(card.id, draft)
      // 고친 근거로 질문을 다시 뽑는 동안 진행 화면을 보여줍니다.
      nav('/regen')
    } catch {
      // 저장이 실패했는데 조용히 넘어가면 고친 내용이 사라진 줄도 모릅니다.
      setSaving(false)
      alert('리포트를 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.')
    }
  }

  return (
    <>
      <div className="mx-auto flex max-w-(--container-review) items-start gap-9 px-8 pt-[34px] pb-[130px]">
        {/* 좌측 사이드바 */}
        <aside className="sticky top-[88px] flex w-[236px] shrink-0 flex-col gap-5">
          <div className="rounded-control border border-line bg-surface-2 px-3 py-[11px]">
            <div className="text-[12.5px] font-semibold">직접 고칠 수 있습니다</div>
            <div className="mt-[3px] text-[11.5px] leading-[1.55] text-faint">
              사실과 다른 대목을 눌러 고쳐 주세요. 저장하면 고친 내용으로 질문을 다시 뽑습니다.
            </div>
          </div>

          <div className="flex flex-col gap-[7px] border-t border-line pt-5">
            <div className="text-[11.5px] font-semibold text-faint">목차</div>
            {sections.map((s, i) => (
              <button
                key={`${s.title}-${i}`}
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
          <h1 className="mt-[6px] mb-[8px] text-[23px] leading-[1.4] font-bold tracking-[-.03em]">
            {card.company} 면접 준비 리서치
          </h1>
          <p className="m-0 text-[13px] text-muted">
            사실과 다른 대목을 직접 고쳐 주세요. 고치지 않아도 그대로 진행할 수 있습니다.
          </p>

          {sections.map((section, si) => (
            <section key={`${section.title}-${si}`} id={`sec-${si}`}>
              <h2 className="mt-[30px] mb-[6px] border-b border-hair-2 pb-[10px] text-[16px] font-bold tracking-[-.02em]">
                {section.title}
              </h2>
              {section.blocks.map((block, bi) => (
                <EditableBlock
                  key={`${si}-${bi}`}
                  block={block}
                  onChange={(next) => replaceBlock(si, bi, next)}
                />
              ))}
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
            {edited ? '고친 내용이 있습니다' : '고친 내용이 없습니다'}
          </span>
          <div className="flex-1" />
          <button onClick={() => nav('/ready')} className="mr-4 text-[13px] text-muted">
            돌아가기
          </button>
          <button
            onClick={submit}
            disabled={saving}
            className={`rounded-control px-5 py-[10px] text-[13.5px] font-semibold ${
              edited
                ? 'border border-ink bg-ink text-white'
                : 'border border-field bg-surface text-ink'
            }`}
          >
            {saving ? '저장하는 중…' : edited ? '저장하고 질문 다시 뽑기' : '이대로 진행'}
          </button>
        </div>
      </div>
    </>
  )
}

/**
 * 편집 가능한 블록 하나.
 *
 * 문단은 자라는 textarea로, 표는 칸마다 입력란으로 엽니다. 출처는 고칠 대상이
 * 아니라 읽기 전용입니다 — 사용자가 고칠 것은 사실이지 인용 번호가 아닙니다.
 */
function EditableBlock({
  block,
  onChange,
}: {
  block: DocBlock
  onChange: (block: DocBlock) => void
}) {
  if (block.type === 'refs') {
    return (
      <div className="flex flex-col gap-[6px] py-[9px] pl-3">
        {block.refs.map((r) => (
          <div key={r.n} className="flex gap-[6px]">
            <span className="num w-5 shrink-0 text-[11.5px] text-faintest">{r.n}</span>
            <span className="text-[12.5px] text-muted">{r.label}</span>
          </div>
        ))}
      </div>
    )
  }

  if (block.type === 'table') {
    return (
      <div className="py-[9px] pl-3">
        <div className="overflow-hidden rounded-control border border-hair-2">
          <div
            className="grid bg-surface-2 px-3 py-[8px] text-[11.5px] font-semibold text-muted"
            style={{ gridTemplateColumns: '96px 1fr 120px' }}
          >
            {block.head.map((h) => (
              <span key={h}>{h}</span>
            ))}
          </div>
          {block.rows.map((row, ri) => (
            <div
              key={ri}
              className="grid border-t border-hair-3 px-3 py-[8px] text-[12.5px]"
              style={{ gridTemplateColumns: '96px 1fr 120px' }}
            >
              {(['a', 'b', 'c'] as const).map((key) => (
                <input
                  key={key}
                  value={row[key]}
                  onChange={(e) =>
                    onChange({
                      ...block,
                      rows: block.rows.map((r, i) =>
                        i === ri ? { ...r, [key]: e.target.value } : r,
                      ),
                    })
                  }
                  className={`${key === 'a' ? 'num ' : ''}mr-2 rounded-chip bg-transparent px-[3px] outline-none hover:bg-surface-2 focus:bg-surface-2`}
                />
              ))}
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-[8px] py-[9px] pr-[10px] pl-3">
      {block.type === 'li' && <span className="pt-[6px] text-[12px] text-field">—</span>}
      {/* 점선 밑줄이 "여기는 고칠 수 있다"를 알립니다. field-sizing:content로
          내용만큼만 자라서 문단 높이가 원문과 같이 갑니다. */}
      <textarea
        value={block.text}
        onChange={(e) => onChange({ ...block, text: e.target.value })}
        rows={1}
        className="flex-1 resize-none rounded-control border border-transparent border-b-field bg-transparent px-1 text-[14px] leading-[1.9] text-body outline-none [field-sizing:content] hover:bg-surface-2 focus:border-accent focus:bg-surface-2"
      />
    </div>
  )
}
