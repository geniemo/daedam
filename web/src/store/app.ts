import { create } from 'zustand'
import type { ApplicationPart, Card } from '@/data/types'
import { initialCards, initialParts } from '@/data/mock'

// README §State Management, minus the fields that became routes
// (`screen`, `regStep`) and minus everything that changes at audio rate —
// waveform amplitudes and ring scale live in refs, never here. See
// `src/audio/useAudioLevels.ts` for why.

/** 빈 폼 데모용 기본값 — 등록과 서버 요청이 같은 값을 쓴다. */
export const FALLBACK_COMPANY = '누리테크'
export const FALLBACK_ROLE = '서비스기획 · 신입'

interface AppState {
  cards: Card[]
  activeCardId: string | null

  /* 등록 폼 */
  company: string
  role: string
  parts: ApplicationPart[]

  setActiveCard: (id: string) => void
  /** 서버 목록으로 카드를 갈아끼운다. 홈이 마운트될 때 한 번 — 파일이 진실이다. */
  setCards: (cards: Card[]) => void
  setCompany: (v: string) => void
  setRole: (v: string) => void
  setParts: (parts: ApplicationPart[]) => void
  resetRegister: () => void
  /** 등록 완료 → researching 카드를 목록 맨 앞에 넣고 id 반환.
      서버 리서치가 시작됐으면 task_id를 카드 id로 쓴다. */
  submitRegister: (id?: string) => string
  setCardProgress: (id: string, pct: number) => void
}

export const useAppStore = create<AppState>((set, get) => ({
  cards: initialCards,
  activeCardId: initialCards[0].id,

  company: '',
  role: '',
  parts: initialParts,

  setActiveCard: (id) => set({ activeCardId: id }),

  // 활성 카드가 새 목록에 없으면 첫 카드로 옮긴다 — 없는 카드를 가리킨 채로
  // 두면 useActiveCard의 폴백이 조용히 엉뚱한 면접을 열어 준다.
  setCards: (cards) =>
    set((s) => ({
      cards,
      activeCardId: cards.some((c) => c.id === s.activeCardId)
        ? s.activeCardId
        : (cards[0]?.id ?? null),
    })),
  setCompany: (company) => set({ company }),
  setRole: (role) => set({ role }),
  setParts: (parts) => set({ parts }),
  resetRegister: () => set({ company: '', role: '' }),

  submitRegister: (id) => {
    const { company, role, cards } = get()
    const name = company.trim() || FALLBACK_COMPANY
    const position = role.trim() || FALLBACK_ROLE
    const cardId = id ?? `new${Date.now()}`
    set({
      cards: [{ id: cardId, company: name, role: position, date: '방금 등록', status: 'researching', pct: 0 }, ...cards],
      activeCardId: cardId,
    })
    return cardId
  },

  setCardProgress: (id, pct) =>
    set((s) => ({
      cards: s.cards.map((c) =>
        c.id === id ? { ...c, pct, status: pct >= 100 ? 'ready' : 'researching' } : c,
      ),
    })),
}))

/** 활성 카드. 없으면 첫 카드로 폴백 — 프로토타입과 동일한 동작. */
export const useActiveCard = () =>
  useAppStore((s) => s.cards.find((c) => c.id === s.activeCardId) ?? s.cards[0])
