import { useEffect } from 'react'

/**
 * 지원서 입력 가이드 — 등록 2단계의 "?"가 연다.
 *
 * 등록 화면은 파트·항목이라는 우리 말로 지원서를 받는데, 처음 온 사람은 그게
 * 회사 양식의 무엇에 해당하는지 모른다. 그래서 "파트 추가"를 누르고 멈춘다.
 * 설명 한 문단과 **채워진 예시 하나**를 보여 주는 것이 가장 빠르다 — 규칙을
 * 읽는 것보다 완성된 모양을 보는 쪽이 따라 하기 쉽다.
 *
 * 화면 위에 덮는 창으로 둔다. 별도 경로로 가면 쓰던 입력이 눈앞에서 사라지고,
 * 돌아왔을 때 어디까지 썼는지 다시 찾아야 한다.
 */

/**
 * 예시 지원서 — 제작자의 실제 지원서(SK하이닉스 기반기술)에서 세 항목을 골라
 * 앞부분만 남긴 것. 소속 기관명만 일반 명사로 바꿨다. 구조를 보여 주는 자리라
 * 본문은 두세 문장에서 끊는다.
 */
const EXAMPLE = [
  {
    name: '자기소개서',
    items: [
      {
        title: '1. 지원하신 직무 분야의 전문성을 키우기 위해 꾸준히 노력한 경험',
        body: '저의 전문성 영역은 결함 데이터의 본질적 특성을 분석하여 적합한 검출 모델을 선택, 구현하는 것입니다. 출발점은 연구실의 딥페이크 탐지 연구였습니다. EfficientNet에 원본 이미지를 학습시켰으나 cross-dataset AUC 0.58에 그쳤고, 더 큰 모델을 적용해도 성능은 오히려 하락했습니다. 모델이 아닌 데이터에 원인이 있다고 보고 …',
      },
      {
        title: '2. 팀워크를 발휘해 사람들을 연결하고 공동 목표 달성에 기여한 경험',
        body: '산학협력 프로젝트에서 5인 팀의 팀장 겸 IPS 알고리즘 개발을 담당했습니다. BLE 비콘 기반 실내 측위 시스템을 개발하는 과정에서 같은 알고리즘 파트 팀원과 기술적 견해 차이가 발생했습니다. 철제 책장의 다중 경로 간섭으로 측위값이 심하게 튀었는데 …',
      },
    ],
  },
  {
    name: '경력 · 프로젝트',
    items: [
      {
        title: '졸업작품 — 딥페이크 탐지 모델의 일반화 성능 개선',
        body: '생성형 AI가 이미지에 남기는 인위적 흔적을 탐지하는 딥페이크 탐지 모델의 일반화 성능 개선 프로젝트를 수행했습니다. 초기에는 …',
      },
    ],
  },
]

export function ApplicationGuide({ onClose }: { onClose?: () => void }) {
  // Esc로도 닫힌다 — 마우스로 구석의 닫기를 찾게 하지 않는다.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose?.()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-60 flex items-center justify-center px-6 py-8"
      style={{ background: 'rgba(22,35,58,.45)' }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="지원서 작성 가이드"
    >
      <div
        onClick={(event) => event.stopPropagation()}
        className="flex max-h-full w-full max-w-[640px] flex-col overflow-hidden rounded-card border border-line bg-surface animate-dm-fade"
      >
        <div className="flex items-center border-b border-line px-[26px] py-[18px]">
          <h2 className="m-0 text-[18px] font-bold tracking-[-.02em] text-ink">지원서는 이렇게 넣습니다</h2>
          <div className="flex-1" />
          <button type="button" onClick={onClose} className="text-[13px] text-muted hover:text-ink">
            닫기
          </button>
        </div>

        <div className="flex flex-col gap-[26px] overflow-y-auto px-[26px] py-[22px] break-keep">
          <section className="flex flex-col gap-[10px]">
            <p className="m-0 text-[14px] leading-[1.75] text-body">
              <b className="font-semibold text-ink">파트</b>는 회사 양식의 큰 묶음이고,{' '}
              <b className="font-semibold text-ink">항목</b>은 그 안의 문항 하나입니다. 자기소개서에
              문항이 셋이면 파트 하나에 항목 셋, 경력·프로젝트는 파트를 따로 만들어 건마다 항목으로
              둡니다.
            </p>
            <p className="m-0 text-[14px] leading-[1.75] text-body">
              면접관은 <b className="font-semibold text-ink">항목 하나하나를 근거로</b> 질문과
              꼬리질문을 하기 때문에 요약하지 말고{' '}
              <b className="font-semibold text-ink">제출한 그대로</b> 붙여넣는 것이 좋습니다.
            </p>
          </section>

          <section className="flex flex-col gap-[10px]">
            <div className="text-[12px] font-semibold tracking-[.04em] text-faint">예시</div>
            {EXAMPLE.map((part) => (
              <div key={part.name} className="rounded-card border border-line bg-surface">
                <div className="flex items-center gap-[9px] border-b border-hair px-[16px] py-[12px]">
                  <span className="text-[14px] font-bold text-ink">{part.name}</span>
                  <span className="num rounded-chip border border-line px-[6px] py-px text-[11px] text-faint">
                    {part.items.length}
                  </span>
                  <span className="text-[11.5px] text-faintest">← 파트</span>
                </div>
                <div className="flex flex-col gap-[8px] px-[16px] py-[12px]">
                  {part.items.map((item) => (
                    <div key={item.title} className="rounded-control border border-line-2 bg-surface-2 px-[13px] py-[10px]">
                      <div className="flex items-center gap-[8px]">
                        <span className="text-[13px] font-semibold text-body">{item.title}</span>
                        <span className="text-[11.5px] text-faintest">← 항목</span>
                      </div>
                      <p className="mt-[6px] mb-0 text-[12.5px] leading-[1.7] text-muted">{item.body}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </section>

        </div>
      </div>
    </div>
  )
}
