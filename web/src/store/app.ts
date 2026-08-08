import { create } from 'zustand'
import type { ApplicationPart, Card } from '@/data/types'
import { initialCards, initialParts } from '@/data/mock'

// README §State Management, minus the fields that became routes
// (`screen`, `regStep`) and minus everything that changes at audio rate —
// waveform amplitudes and ring scale live in refs, never here. See
// `src/audio/useAudioLevels.ts` for why.

interface AppState {
  cards: Card[]
  activeCardId: string | null

  /* 등록 폼 */
  company: string
  role: string
  parts: ApplicationPart[]

  /* §6 리포트 검토 — 원문을 수정하지 않는 주석(delta)으로만 쌓인다 */
  flags: Record<string, boolean>
  memos: Record<string, string[]>

  setActiveCard: (id: string) => void
  setCompany: (v: string) => void
  setRole: (v: string) => void
  setParts: (parts: ApplicationPart[]) => void
  resetRegister: () => void
  /** 등록 완료 → researching 카드를 목록 맨 앞에 넣고 id 반환 */
  submitRegister: () => string
  setCardProgress: (id: string, pct: number) => void

  toggleFlag: (blockId: string) => void
  addMemo: (blockId: string, text: string) => void
  removeMemo: (blockId: string, index: number) => void
  clearAnnotations: () => void
}

export const useAppStore = create<AppState>((set, get) => ({
  cards: initialCards,
  activeCardId: initialCards[0].id,

  company: '',
  role: '',
  parts: initialParts,

  flags: {},
  memos: {},

  setActiveCard: (id) => set({ activeCardId: id }),
  setCompany: (company) => set({ company }),
  setRole: (role) => set({ role }),
  setParts: (parts) => set({ parts }),
  resetRegister: () => set({ company: '', role: '' }),

  submitRegister: () => {
    const { company, role, cards } = get()
    const name = company.trim() || '누리테크'
    const position = role.trim() || '서비스기획 · 신입'
    const id = `new${Date.now()}`
    set({
      cards: [{ id, company: name, role: position, date: '방금 등록', status: 'researching', pct: 0 }, ...cards],
      activeCardId: id,
    })
    return id
  },

  setCardProgress: (id, pct) =>
    set((s) => ({
      cards: s.cards.map((c) =>
        c.id === id ? { ...c, pct, status: pct >= 100 ? 'ready' : 'researching' } : c,
      ),
    })),

  toggleFlag: (blockId) => set((s) => ({ flags: { ...s.flags, [blockId]: !s.flags[blockId] } })),

  addMemo: (blockId, text) =>
    set((s) => ({ memos: { ...s.memos, [blockId]: [...(s.memos[blockId] ?? []), text] } })),

  removeMemo: (blockId, index) =>
    set((s) => ({
      memos: { ...s.memos, [blockId]: (s.memos[blockId] ?? []).filter((_, i) => i !== index) },
    })),

  clearAnnotations: () => set({ flags: {}, memos: {} }),
}))

/** 활성 카드. 없으면 첫 카드로 폴백 — 프로토타입과 동일한 동작. */
export const useActiveCard = () =>
  useAppStore((s) => s.cards.find((c) => c.id === s.activeCardId) ?? s.cards[0])

/** 하단 고정 바 요약 (§6): "정정 N건 · 메모 M건" */
export const useAnnotationCounts = () =>
  useAppStore((s) => ({
    flagged: Object.values(s.flags).filter(Boolean).length,
    memoed: Object.values(s.memos).reduce((n, list) => n + list.length, 0),
  }))
