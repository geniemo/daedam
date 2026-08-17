import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { startPreparation } from '@/api/preparation'
import { useAppStore } from '@/store/app'
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
  const { company, role, posting, setCompany, setRole, setPosting } = useAppStore()
  // 회사명과 직무는 리서치 프롬프트의 첫 줄이 됩니다. 비어 있으면 조사할
  // 대상이 없는데, live에서 등록은 20~60분짜리 유료 작업입니다.
  const ready = company.trim() !== '' && role.trim() !== ''

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
        {/* 파싱하지 않고 리서치 프롬프트에 그대로 실립니다. 링크면 조사
            에이전트가 열어 보고, 본문이면 본문대로 읽습니다. 비워 두면
            에이전트가 직접 공고를 찾는데, 유사 직무 공고가 여럿인 회사에서는
            다른 공고의 요구역량으로 질문이 만들어집니다. */}
        <div className="flex flex-col gap-[7px]">
          <div className="flex items-center gap-[6px]">
            <Label>채용공고</Label>
            <span className="text-[12px] text-faint">선택 · 링크 또는 내용을 붙여넣기</span>
          </div>
          <TextArea
            value={posting}
            onChange={(e) => setPosting(e.target.value)}
            placeholder="https://... 또는 공고 내용을 그대로 붙여넣어 주세요"
          />
        </div>
      </div>

      <div className="mt-8 flex">
        <div className="flex-1" />
        <button
          onClick={() => nav('/register/2')}
          disabled={!ready}
          className={`rounded-control px-[30px] py-[12px] text-[14px] font-semibold ${
            ready ? 'bg-ink text-white' : 'bg-field-2 text-faint'
          }`}
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
  const { company, role, posting, parts, setParts, submitRegister } = useAppStore()
  const [openPart, setOpenPart] = useState(0)
  // 어느 파트의 몇 번째 항목이 열렸는지. 인덱스만 들고 있으면 A파트의 첫
  // 항목을 열 때 B파트의 첫 항목도 같이 열린다.
  const [openItem, setOpenItem] = useState('0-0')

  /**
   * 방금 만든 입력란으로 커서를 옮기기 위한 표시.
   *
   * 추가 버튼을 누른 뒤 사용자가 다시 펼치고 눌러야 입력이 시작되는 것이
   * 불편하다는 피드백에서 나왔다. 요소가 마운트될 때 이 표시와 맞으면 스스로
   * 포커스를 가져가고 표시를 지운다.
   */
  const [focusOn, setFocusOn] = useState<string | null>(null)
  // 삭제를 물어보는 중인 파트. 지원서는 다시 쓰기 번거로워 되돌릴 수단이 없다.
  const [confirmPart, setConfirmPart] = useState<number | null>(null)
  const takeFocus = (key: string) => (el: HTMLInputElement | null) => {
    if (!el || focusOn !== key) return
    el.focus()
    el.select()
    setFocusOn(null)
  }

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

  const addItem = (pi: number) => {
    const added = parts[pi].items.length
    setParts(
      parts.map((p, i) =>
        i !== pi
          ? p
          : { ...p, items: [...p.items, { title: `${p.name} ${added + 1}`, body: '', len: '작성 필요' }] },
      ),
    )
    // 펼치고 커서까지 옮겨 준다 — 누른 사람은 바로 이름을 고칠 참이다.
    setOpenItem(`${pi}-${added}`)
    setFocusOn(`item-${pi}-${added}`)
  }

  const addPart = () => {
    const added = parts.length
    setParts([...parts, { name: `파트 ${added + 1}`, items: [] }])
    setOpenPart(added)
    setFocusOn(`part-${added}`)
  }

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
                {/* min-w-0가 없으면 field-sizing:content가 내용만큼 자라며
                    행 밖으로 밀고 나간다 — 긴 이름이 카드를 뚫는다. */}
                <label
                  className="group flex min-w-0 items-center gap-[5px]"
                  onClick={(e) => e.stopPropagation()}
                >
                  <input
                    ref={takeFocus(`part-${pi}`)}
                    value={part.name}
                    onChange={(e) => renamePart(pi, e.target.value)}
                    placeholder="파트 이름"
                    className="w-full min-w-[40px] rounded-chip border-b border-dashed border-field bg-transparent px-[3px] text-[15px] font-bold outline-none [field-sizing:content] hover:bg-surface-2 focus:border-solid focus:border-accent focus:bg-surface-2"
                  />
                  <PencilMark />
                </label>
                <span className="num rounded-chip border border-line px-[6px] py-px text-[11.5px] text-faint">
                  {part.items.length}
                </span>
                <div className="flex-1" />
                {/* 파트 삭제는 여기 없다. 접기·펼치기 화살표 바로 옆이라 자꾸
                    잘못 눌렸다. 펼친 안쪽으로 옮기고 한 번 더 묻는다. */}
                <span className="text-[12px] text-faintest">{open ? '▲' : '▼'}</span>
              </div>

              {open && (
                <div className="flex flex-col gap-[10px] px-[18px] py-4">
                  {part.items.map((item, ii) => {
                    const itemKey = `${pi}-${ii}`
                    const itemOpen = openItem === itemKey
                    return (
                      <div key={ii} className="rounded-control border border-line-2 bg-surface-2">
                        {/* 항목 제목은 헤더에만 — 펼쳤을 때 제목 입력란을 두면 같은 문자열이 두 번 보입니다 */}
                        <div
                          onClick={() => setOpenItem(itemOpen ? '' : itemKey)}
                          className="flex cursor-pointer items-center gap-[9px] px-[13px] py-[11px]"
                        >
                          <label
                            className="group flex min-w-0 flex-1 items-center gap-[5px]"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <input
                              ref={takeFocus(`item-${pi}-${ii}`)}
                              value={item.title}
                              onChange={(e) => updateItemTitle(pi, ii, e.target.value)}
                              placeholder="항목 이름"
                              className="w-full min-w-[40px] rounded-chip border-b border-dashed border-field bg-transparent px-[3px] text-[13px] font-semibold text-body outline-none [field-sizing:content] hover:bg-surface focus:border-solid focus:border-accent focus:bg-surface"
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

                  <div className="flex items-center border-t border-hair pt-[10px]">
                    <div className="flex-1" />
                    {confirmPart === pi ? (
                      <div className="flex items-center gap-[10px]">
                        <span className="text-[12px] text-muted">
                          이 파트와 항목 {part.items.length}개를 지울까요?
                        </span>
                        <button
                          onClick={() => {
                            removePart(pi)
                            setConfirmPart(null)
                          }}
                          className="text-[12px] font-semibold text-accent"
                        >
                          지우기
                        </button>
                        <button
                          onClick={() => setConfirmPart(null)}
                          className="text-[12px] text-faint"
                        >
                          취소
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setConfirmPart(pi)}
                        className="text-[12px] text-faint"
                      >
                        파트 삭제
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )
        })}

        <button
          onClick={addPart}
          className="flex items-center justify-center rounded-card border border-dashed border-field bg-surface p-[15px]"
        >
          <span className="text-[13px] text-faint">+ 파트 추가</span>
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
              company.trim(),
              role.trim(),
              parts,
              posting,
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
