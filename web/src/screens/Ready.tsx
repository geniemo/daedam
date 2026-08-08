import { useNavigate } from 'react-router'
import { useActiveCard, useAnnotationCounts } from '@/store/app'
import { AccentDot, CheckDot, OutlineButton, SectionLabel } from '@/components/ui'
import { STAGE_NAMES, questions, uncertainRefs } from '@/data/mock'

/** README §5. 준비 완료 */
export function Ready() {
  const nav = useNavigate()
  const card = useActiveCard()
  const { flagged, memoed } = useAnnotationCounts()
  const corrections = flagged + memoed

  return (
    <main className="mx-auto max-w-(--container-doc) px-8 pt-[44px] pb-20 animate-dm-fade">
      <button onClick={() => nav('/')} className="mb-4 text-[13px] text-muted">
        ← 내 면접
      </button>

      <div className="mb-[6px] flex items-center gap-[6px]">
        <AccentDot />
        <span className="text-[12px] font-semibold tracking-[.05em] text-accent">면접 준비 완료</span>
      </div>
      <h1 className="m-0 text-[27px] font-bold tracking-[-.03em]">
        {card.company} · {card.role}
      </h1>
      <p className="mt-[10px] mb-[30px] text-[14px] text-muted">
        채용공고와 최근 소식, 지원서를 함께 읽고 질문을 준비했습니다. 한국어 음성으로 15~20분간
        진행됩니다.
      </p>

      <div className="mb-4 grid grid-cols-4 gap-[10px]">
        {STAGE_NAMES.map((name, i) => (
          <div
            key={name}
            className="flex flex-col gap-[5px] rounded-card border border-line bg-surface px-[14px] py-[15px]"
          >
            <span className="num text-[11.5px] font-semibold text-faintest">0{i + 1}</span>
            <span className="text-[14px] font-bold">{name}</span>
            <span className="text-[11.5px] text-faint">
              {questions.filter((q) => q.s === i).length}개 질문
            </span>
          </div>
        ))}
      </div>

      <div className="mb-4 flex flex-col gap-[14px] rounded-card border border-line bg-surface p-5">
        <div className="flex items-center">
          <SectionLabel>리서치 리포트</SectionLabel>
          <div className="flex-1" />
          <span className="text-[11.5px] text-faintest">8월 4일 생성</span>
        </div>

        {corrections > 0 && (
          <div className="rounded-control border border-accent-line bg-accent-bg px-3 py-[10px] text-[12.5px] text-body-2">
            남기신 정정 사항 {corrections}건을 함께 넘겨 질문을 다시 뽑았습니다.
          </div>
        )}

        <div className="flex items-center border-t border-hair pt-[14px]">
          <div className="flex flex-col gap-[5px]">
            <span className="text-[14.5px] font-bold">
              {card.company} 면접 준비 리서치
            </span>
            <span className="text-[12.5px] font-semibold text-accent">
              확인이 필요한 대목 {uncertainRefs.length}곳
            </span>
          </div>
          <div className="flex-1" />
          <OutlineButton onClick={() => nav('/review')} className="px-[14px] py-[9px] text-[12.5px]">
            리포트 열기
          </OutlineButton>
        </div>
      </div>

      <div className="mb-[26px] flex flex-col gap-3 rounded-card border border-line bg-surface p-5">
        <SectionLabel>시작 전 확인</SectionLabel>
        <div className="flex flex-col gap-[10px]">
          <div className="flex items-center gap-[9px]">
            <CheckDot size={15} />
            <span className="text-[13.5px] text-ink">마이크가 연결되어 있습니다</span>
            <div className="flex-1" />
            {/* README §Fidelity — 마이크 테스트 화면은 의도적으로 미완성입니다 */}
            <button className="border-b border-field text-[12.5px] text-muted">테스트하기</button>
          </div>
          {['조용한 곳에서 진행하시길 권합니다', '중간에 멈추면 이어서 진행할 수 있습니다'].map((t) => (
            <div key={t} className="flex items-center gap-[9px]">
              <span
                className="inline-block shrink-0 rounded-full border-field"
                style={{ width: 15, height: 15, borderWidth: 1.5 }}
              />
              <span className="text-[13.5px] text-muted">{t}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center">
        <button onClick={() => nav('/register/2')} className="text-[13px] text-muted">
          지원서 수정
        </button>
        <div className="flex-1" />
        {/* AudioContext는 이 클릭 핸들러 안에서 생성됩니다 — 밖에서 만들면
            자동재생 정책에 막혀 무음이 됩니다. useVoiceSession 참조. */}
        <button
          onClick={() => nav('/interview')}
          className="rounded-control bg-ink px-[34px] py-[14px] text-[15px] font-semibold text-white"
        >
          면접 시작하기
        </button>
      </div>
    </main>
  )
}
