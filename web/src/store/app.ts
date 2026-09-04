import { create } from 'zustand'
import type { ApplicationPart, Card } from '@/data/types'
import { initialParts } from '@/data/mock'

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
  /** 채용공고 링크 또는 본문. 파싱하지 않고 리서치 프롬프트로 그대로 나간다. */
  posting: string
  parts: ApplicationPart[]

  /**
   * 시작 전 확인에서 카메라를 켰는가. 면접 화면이 이걸 보고 켠다.
   *
   * 면접 화면이 스스로 권한을 요청하지 않게 하려고 둡니다 — 면접이 시작되는
   * 순간 브라우저 권한 창이 뜨면 첫 질문을 놓칩니다. 권한은 반드시 시작 전에
   * 받고, 여기 남은 표시로 이어받습니다.
   */
  cameraReady: boolean

  /**
   * 홈에 한 번 띄울 안내. 면접 화면이 결과 없이 홈으로 돌려보낼 때(다른 탭이
   * 이어받음·연결 실패·크레딧 부족) 이유를 여기 남긴다 — 말없이 홈에 떨어지면
   * 무슨 일이 있었는지 알 길이 없다.
   */
  notice: string | null

  setNotice: (text: string | null) => void
  setCameraReady: (v: boolean) => void
  setActiveCard: (id: string) => void
  /** 서버 목록으로 카드를 갈아끼운다. 홈이 마운트될 때 한 번 — 파일이 진실이다. */
  setCards: (cards: Card[]) => void
  setCompany: (v: string) => void
  setRole: (v: string) => void
  setPosting: (v: string) => void
  setParts: (parts: ApplicationPart[]) => void
  resetRegister: () => void
  /** 등록 완료 → researching 카드를 목록 맨 앞에 넣고 id 반환.
      서버 리서치가 시작됐으면 task_id를 카드 id로 쓴다. */
  submitRegister: (id?: string) => string
  setCardProgress: (id: string, pct: number) => void
}

export const useAppStore = create<AppState>((set, get) => ({
  cameraReady: false,
  notice: null,
  setNotice: (notice) => set({ notice }),
  // 목록은 서버 파일에서 채운다. 목업으로 시작하면 실제로는 없는 면접이 잠깐
  // 보였다 사라지고, 그 사이에 카드를 누르면 준비 데이터가 없는 면접이 열린다.
  cards: [],
  activeCardId: null,

  company: '',
  role: '',
  posting: '',
  parts: initialParts,

  setCameraReady: (cameraReady) => set({ cameraReady }),
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
  setPosting: (posting) => set({ posting }),
  setParts: (parts) => set({ parts }),
  // parts까지 비운다. 지원서는 회사마다 다시 쓰는 것이고, 남겨 두면 다음 등록
  // 화면에 앞 회사에 낸 지원서가 그대로 떠 있다.
  resetRegister: () => set({ company: '', role: '', posting: '', parts: [] }),

  submitRegister: (id) => {
    const { company, role, cards } = get()
    // 기본값으로 메우지 않는다. 비어 있으면 등록 화면이 막아 주는데, 여기서
    // 다시 메우면 엉뚱한 회사로 리서치가 돌고 live에서는 그것이 유료다.
    const name = company.trim()
    const position = role.trim()
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
