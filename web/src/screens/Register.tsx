import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { startPreparation } from '@/api/preparation'
import { FALLBACK_COMPANY, FALLBACK_ROLE, useAppStore } from '@/store/app'
import { Label, TextArea, TextField } from '@/components/ui'

/** README §2·§3. 등록 STEP 1·2 */
export function Register() {
  const { step } = useParams()
  const isStep2 = step === '2'
  return (
    <>
      <TopBar step={isStep2 ? 2 : 1} />
      {isStep2 ? <Step2 /> : <Step1 />}
    </>
  )
}

function TopBar({ step }: { step: 1 | 2 }) {
  const nav = useNavigate()
  return (
    <div className="mx-auto max-w-(--container-home) px-8 pt-[26px] pb-[34px]">
      <div className="flex items-center">
        <button onClick={() => nav('/')} className="text-[13px] text-muted">
          ✕ 나가기
        </button>
        <div className="flex-1" />
        <div className="flex items-center gap-[10px]">
          <span className="num text-[12.5px] text-muted">{step} / 2</span>
          <div className="flex gap-[5px]">
            {[1, 2].map((i) => (
              <span
                key={i}
                className={i <= step ? 'bg-ink' : 'bg-field-2'}
                style={{ width: 22, height: 2.5 }}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function StepHeading({ step, title, desc }: { step: number; title: string; desc: string }) {
  return (
    <>
      <div className="mb-[10px] text-[12px] font-semibold tracking-[.05em] text-accent">
        STEP {step}
      </div>
      <h1 className="m-0 text-[25px] font-bold tracking-[-.03em]">{title}</h1>
      <p className="mt-[10px] mb-8 text-[14px] leading-[1.6] text-muted">{desc}</p>
    </>
  )
}

function Step1() {
  const nav = useNavigate()
  const { company, role, setCompany, setRole } = useAppStore()

  return (
    <main className="mx-auto max-w-(--container-reg1) px-8 pb-20 animate-dm-fade">
      <StepHeading
        step={1}
        title="어느 회사에 지원하시나요"
        desc="회사와 직무를 알려주시면 그 회사의 채용공고와 최근 소식을 조사해 질문을 준비합니다."
      />

      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-[7px]">
          <Label>회사명</Label>
          <TextField
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="예) 누리테크"
          />
        </div>
        <div className="flex flex-col gap-[7px]">
          <Label>직무</Label>
          <TextField value={role} onChange={(e) => setRole(e.target.value)} placeholder="예) 서비스기획" />
        </div>
        <div className="flex flex-col gap-[7px]">
          <div className="flex items-center gap-[6px]">
            <Label>채용공고 링크</Label>
            <span className="text-[12px] text-faint">선택</span>
          </div>
          <TextField placeholder="https://" />
        </div>
        <div className="flex flex-col gap-[7px]">
          <div className="flex items-center gap-[6px]">
            <Label>직무 소개서 (JD)</Label>
            <span className="text-[12px] text-faint">선택 · 있으면 질문이 더 정확해집니다</span>
          </div>
          <div className="flex items-center gap-[10px] rounded-control border border-dashed border-field bg-surface p-[18px]">
            <span className="text-[13px] text-muted">파일을 끌어다 놓거나</span>
            <button className="rounded-control border border-field bg-surface-2 px-3 py-[6px] text-[12.5px]">
              파일 선택
            </button>
            <div className="flex-1" />
            <button className="border-b border-field text-[12.5px] text-muted">직접 붙여넣기</button>
          </div>
        </div>
      </div>

      <div className="mt-8 flex">
        <div className="flex-1" />
        <button
          onClick={() => nav('/register/2')}
          className="rounded-control bg-ink px-[30px] py-[12px] text-[14px] font-semibold text-white"
        >
          다음
        </button>
      </div>
    </main>
  )
}

/**
 * 이름 옆에 붙는 연필. 이름은 클릭해야 고칠 수 있다는 것을 알리는 표시라,
 * 평소엔 흐리게 두고 그 줄에 마우스를 올리면 진해진다.
 */
function PencilMark() {
  return (
    <svg
      viewBox="0 0 12 12"
      aria-hidden
      className="shrink-0 text-faintest transition-colors group-hover:text-muted"
      style={{ width: 11, height: 11 }}
    >
      <path
        d="M8.2 1.3 10.7 3.8 4.3 10.2 1.3 10.7 1.8 7.7z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function Step2() {
  const nav = useNavigate()
  const { company, role, parts, setParts, submitRegister } = useAppStore()
  const [openPart, setOpenPart] = useState(0)
  const [openItem, setOpenItem] = useState(0)

  const updateItem = (pi: number, ii: number, body: string) =>
    setParts(
      parts.map((p, i) =>
        i !== pi
          ? p
          : {
              ...p,
              items: p.items.map((it, j) =>
                j !== ii ? it : { ...it, body, len: body ? `${body.length}자` : '작성 필요' },
              ),
            },
      ),
    )

  const updateItemTitle = (pi: number, ii: number, title: string) =>
    setParts(
      parts.map((p, i) =>
        i !== pi
          ? p
          : { ...p, items: p.items.map((it, j) => (j !== ii ? it : { ...it, title })) },
      ),
    )

  const addItem = (pi: number) =>
    setParts(
      parts.map((p, i) =>
        i !== pi
          ? p
          : { ...p, items: [...p.items, { title: `${p.name} ${p.items.length + 1}`, body: '', len: '작성 필요' }] },
      ),
    )

  const removeItem = (pi: number, ii: number) =>
    setParts(parts.map((p, i) => (i !== pi ? p : { ...p, items: p.items.filter((_, j) => j !== ii) })))

  const renamePart = (pi: number, name: string) =>
    setParts(parts.map((p, i) => (i !== pi ? p : { ...p, name })))

  const removePart = (pi: number) => {
    setParts(parts.filter((_, i) => i !== pi))
    setOpenPart(-1) // 인덱스가 밀리므로 열린 파트를 붙잡지 않고 접는다
  }

  return (
    <main className="mx-auto max-w-(--container-doc) px-8 pb-20 animate-dm-fade">
      <StepHeading
        step={2}
        title="지원서를 넣어 주세요"
        desc="회사 양식 그대로 파트를 만들고 그 안에 항목을 나눠 넣으면, 항목 하나하나를 파고드는 질문이 만들어집니다."
      />

      <div className="flex flex-col gap-[14px]">
        {parts.map((part, pi) => {
          const open = openPart === pi
          return (
            // key는 인덱스다 — 이름을 키로 쓰면 한 글자 칠 때마다 입력란이
            // 새로 마운트돼 포커스가 날아간다.
            <div key={pi} className="rounded-card border border-line bg-surface">
              <div
                onClick={() => setOpenPart(open ? -1 : pi)}
                className="flex cursor-pointer items-center gap-[9px] border-b border-hair px-[18px] py-[15px]"
              >
                {/* 이름 입력란과 삭제는 아코디언 토글을 타지 않는다.
                    점선 밑줄과 연필이 "고칠 수 있다"를 알린다 — 평범한 글자로
                    두면 눌러볼 생각 자체를 안 한다. */}
                <label className="group flex items-center gap-[5px]" onClick={(e) => e.stopPropagation()}>
                  <input
                    value={part.name}
                    onChange={(e) => renamePart(pi, e.target.value)}
                    placeholder="파트 이름"
                    className="min-w-[40px] rounded-chip border-b border-dashed border-field bg-transparent px-[3px] text-[15px] font-bold outline-none [field-sizing:content] hover:bg-surface-2 focus:border-solid focus:border-accent focus:bg-surface-2"
                  />
                  <PencilMark />
                </label>
                <span className="num rounded-chip border border-line px-[6px] py-px text-[11.5px] text-faint">
                  {part.items.length}
                </span>
                <div className="flex-1" />
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    removePart(pi)
                  }}
                  className="text-[12px] text-faint"
                >
                  파트 삭제
                </button>
                <span className="text-[12px] text-faintest">{open ? '▲' : '▼'}</span>
              </div>

              {open && (
                <div className="flex flex-col gap-[10px] px-[18px] py-4">
                  {part.items.map((item, ii) => {
                    const itemOpen = openItem === ii
                    return (
                      <div key={ii} className="rounded-control border border-line-2 bg-surface-2">
                        {/* 항목 제목은 헤더에만 — 펼쳤을 때 제목 입력란을 두면 같은 문자열이 두 번 보입니다 */}
                        <div
                          onClick={() => setOpenItem(itemOpen ? -1 : ii)}
                          className="flex cursor-pointer items-center gap-[9px] px-[13px] py-[11px]"
                        >
                          <label
                            className="group flex items-center gap-[5px]"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <input
                              value={item.title}
                              onChange={(e) => updateItemTitle(pi, ii, e.target.value)}
                              placeholder="항목 이름"
                              className="min-w-[40px] rounded-chip border-b border-dashed border-field bg-transparent px-[3px] text-[13px] font-semibold text-body outline-none [field-sizing:content] hover:bg-surface focus:border-solid focus:border-accent focus:bg-surface"
                            />
                            <PencilMark />
                          </label>
                          <div className="flex-1" />
                          <span className="text-[11.5px] text-faint">
                            {item.body ? item.len : '비어 있음'}
                          </span>
                          <span className="text-[11px] text-faintest">{itemOpen ? '▲' : '▼'}</span>
                        </div>

                        {itemOpen && (
                          <div className="flex flex-col gap-[9px] px-[13px] pb-[13px]">
                            <TextArea
                              value={item.body}
                              onChange={(e) => updateItem(pi, ii, e.target.value)}
                              placeholder="내용을 붙여넣어 주세요"
                            />
                            <div className="flex items-center">
                              <span className="text-[11.5px] text-faint">
                                {item.body
                                  ? '이 항목을 근거로 꼬리질문이 만들어집니다'
                                  : '비워 두어도 등록할 수 있습니다'}
                              </span>
                              <div className="flex-1" />
                              <button
                                onClick={() => removeItem(pi, ii)}
                                className="text-[12px] text-faint"
                              >
                                삭제
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })}
                  <button
                    onClick={() => addItem(pi)}
                    className="rounded-control border border-dashed border-field-2 py-[10px] text-[12.5px] text-faint"
                  >
                    + 항목 추가
                  </button>
                </div>
              )}
            </div>
          )
        })}

        <button
          onClick={() => setParts([...parts, { name: `파트 ${parts.length + 1}`, items: [] }])}
          className="flex flex-col items-center gap-[4px] rounded-card border border-dashed border-field bg-surface p-[15px]"
        >
          <span className="text-[13px] text-faint">+ 파트 추가</span>
          <span className="text-[12px] text-faintest">경력 · 포트폴리오 · 기타</span>
        </button>
      </div>

      <div className="mt-7 flex items-center gap-4">
        <button onClick={() => nav('/register/1')} className="text-[13.5px] text-muted">
          ← 이전
        </button>
        <div className="flex-1" />
        <button
          onClick={async () => {
            // §서버 연동 1 — 리서치를 시작하고 task_id를 카드 id로 쓴다.
            // 서버가 없으면(프론트 단독 실행) 프로토타입의 로컬 진행으로 돌아간다.
            const taskId = await startPreparation(
              company.trim() || FALLBACK_COMPANY,
              role.trim() || FALLBACK_ROLE,
              parts,
            ).catch(() => undefined)
            submitRegister(taskId)
            nav('/research')
          }}
          className="rounded-control bg-ink px-[26px] py-[12px] text-[14px] font-semibold text-white"
        >
          등록하고 준비 시작
        </button>
      </div>
    </main>
  )
}
