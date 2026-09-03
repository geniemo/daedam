import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { completeOnboarding, logout } from '@/api/auth'
import { CheckDot, EmptyDot } from '@/components/ui'

/**
 * 첫 로그인 뒤 한 번 — 이름 확정과 약관·개인정보 동의.
 *
 * **이름을 소셜 프로필에 안 맡기는 이유**: 카카오는 실명이 아니라 닉네임을
 * 주고, 구글은 "Jiweon Park"처럼 로마자일 수 있다. 이 이름은 면접관이 부르는
 * 호칭이자 음성 인식의 어휘 힌트다 — 표기가 틀리면 전사가 통째로 틀린다
 * (실측 "박지원" → "박지훈").
 *
 * **동의를 라우트가 아니라 게이트(App.tsx)에서 거는 이유**: 주소를 쳐서
 * 건너뛸 수 있으면 동의가 아니다. 음성·영상·얼굴 스틸을 AI로 처리하는
 * 서비스라 동의 없이 면접이 시작되면 안 된다.
 *
 * **화면 하나에 질문 하나** (design_handoff_daedam/HANDOFF-landing-onboarding.md
 * §2 "3c 두 단계"): 이름 → 동의. 한 기둥에 입력·동의 2건·안내·버튼을 다 몰면
 * 빈 공간이 공백으로 읽히고, 나누면 여백으로 읽힌다. 단계는 state 하나다 —
 * 라우트로 나누면 주소로 동의 단계를 건너뛸 수 있게 된다.
 */
export function Onboarding() {
  const queryClient = useQueryClient()
  const [step, setStep] = useState<0 | 1>(0)
  const [name, setName] = useState('')
  const [terms, setTerms] = useState(false)
  const [privacy, setPrivacy] = useState(false)
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)
  const named = name.trim().length > 0
  const agreed = terms && privacy

  const submit = async () => {
    if (!named || !agreed || sending) return
    setSending(true)
    setError('')
    try {
      const me = await completeOnboarding(name)
      // 게이트가 이 캐시를 보고 있다 — 갱신되는 순간 앱으로 넘어간다.
      queryClient.setQueryData(['me'], me)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '잠시 뒤 다시 시도해 주세요')
      setSending(false)
    }
  }

  const switchAccount = async () => {
    await logout()
    window.location.href = '/'
  }

  return (
    <main className="flex min-h-dvh flex-col break-keep">
      {/* 상단 바 — 로고와 진행 막대 두 개. 지금 단계까지가 진하다. */}
      <div className="flex items-center px-8 py-[26px]">
        <div className="flex items-center gap-[10px]">
          <span className="flex h-[26px] w-[26px] items-center justify-center border-[1.5px] border-ink">
            <span className="h-[10px] w-[10px] bg-accent" />
          </span>
          <span className="text-[20px] font-bold tracking-[-.02em] text-ink">대담</span>
        </div>
        <div className="flex-1" />
        <div className="flex gap-[5px]">
          {[0, 1].map((i) => (
            <span
              key={i}
              className={`h-[2.5px] w-[22px] transition-colors duration-300 ${
                i <= step ? 'bg-ink' : 'bg-field-2'
              }`}
            />
          ))}
        </div>
      </div>

      {/* key로 리마운트해서 단계마다 fade가 다시 돈다. */}
      <div className="flex flex-1 items-center justify-center px-8 pb-[96px]">
        {step === 0 ? (
          <div key="name" className="w-[460px] max-w-full animate-dm-fade">
            <StepMark>1 / 2</StepMark>
            <h1 className="mt-[10px] mb-0 text-[30px] leading-[1.3] font-bold tracking-[-.035em] text-ink">
              면접관이 어떻게
              <br />
              부르면 좋을까요
            </h1>
            <p className="mt-[14px] mb-[32px] text-[14.5px] leading-[1.7] text-body-2">
              실명으로 적어 주세요.
            </p>
            {/* 밑줄형 입력. 화면에 이 칸 하나뿐이라 상자가 필요 없다. */}
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && named) setStep(1)
              }}
              placeholder="예: 박지원"
              aria-label="이름"
              autoFocus
              className="w-full border-0 border-b-2 border-field bg-transparent py-[10px] text-[22px] font-semibold tracking-[-.02em] text-ink transition-colors duration-200 focus:border-ink"
            />
            <div className="mt-[36px] flex items-center">
              <button
                type="button"
                onClick={switchAccount}
                className="text-[12.5px] text-faint hover:text-muted"
              >
                다른 계정으로 로그인
              </button>
              <div className="flex-1" />
              <StepButton disabled={!named} onClick={() => setStep(1)}>
                다음
              </StepButton>
            </div>
          </div>
        ) : (
          <div key="consent" className="w-[460px] max-w-full animate-dm-fade">
            <StepMark>2 / 2</StepMark>
            <h1 className="mt-[10px] mb-0 text-[30px] leading-[1.3] font-bold tracking-[-.035em] text-ink">
              {givenName(name)} 님, 시작하기 전에
              <br />
              한 가지만 확인해 주세요
            </h1>
            <p className="mt-[14px] mb-[28px] text-[14.5px] leading-[1.7] text-body-2">
              면접 중 음성과 웹캠 영상이 기록되고, 분석을 위해 Google Gemini로 처리됩니다.
            </p>

            <div className="flex flex-col border-t border-line">
              {[
                ['이용약관에 동의합니다', '/terms', terms, () => setTerms((v) => !v)] as const,
                ['개인정보 수집·이용에 동의합니다', '/privacy', privacy, () => setPrivacy((v) => !v)] as const,
              ].map(([label, href, checked, toggle]) => (
                <div key={href} className="flex items-center gap-[12px] border-b border-line py-[16px]">
                  <button
                    type="button"
                    onClick={toggle}
                    aria-pressed={checked}
                    className="flex items-center gap-[12px] text-left text-[14.5px] text-ink"
                  >
                    {checked ? <CheckDot size={16} /> : <EmptyDot size={16} />}
                    {label}
                  </button>
                  <div className="flex-1" />
                  <a
                    href={href}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[12.5px] text-faint underline hover:text-muted"
                  >
                    전문 보기
                  </a>
                </div>
              ))}
            </div>

            {error && <p className="mt-[18px] mb-0 text-[13px] text-accent">{error}</p>}

            <div className="mt-[32px] flex items-center">
              <button
                type="button"
                onClick={() => setStep(0)}
                className="text-[13px] text-muted hover:text-ink"
              >
                ← 이름 고치기
              </button>
              <div className="flex-1" />
              <StepButton disabled={!agreed || sending} onClick={submit}>
                {sending ? '저장 중…' : '동의하고 시작하기'}
              </StepButton>
            </div>
          </div>
        )}
      </div>
    </main>
  )
}

/** "1 / 2" — 몇 번째 질문인지. 상단 막대와 같은 정보를 글자로 한 번 더. */
function StepMark({ children }: { children: string }) {
  return (
    <span className="num text-[12px] font-semibold tracking-[.05em] text-accent">{children}</span>
  )
}

/** 단계를 넘기는 버튼. 조건이 안 찼으면 흐린 채로 눌리지 않는다. */
function StepButton({
  disabled,
  onClick,
  children,
}: {
  disabled: boolean
  onClick: () => void
  children: string
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`h-[46px] rounded-control px-[28px] text-[14px] font-semibold text-white transition-colors duration-300 ${
        disabled ? 'cursor-default bg-faintest' : 'bg-ink'
      }`}
    >
      {children}
    </button>
  )
}

/**
 * 호칭용 이름 — 성을 뺀 것. "박지원 님"이 아니라 "지원 님".
 *
 * 핸드오프 규칙은 "3자 이상이면 마지막 두 글자"(Chrome.tsx가 이니셜을
 * slice(-2, -1)로 잡는 것과 같은 방향)인데, 한글 이름에만 적용한다 —
 * "Jiweon Park"에서 두 글자를 떼면 "rk 님"이 된다. 로마자·띄어쓴 이름은
 * 그대로 부른다.
 */
function givenName(name: string): string {
  const trimmed = name.trim()
  return /^[가-힣]{3,}$/.test(trimmed) ? trimmed.slice(-2) : trimmed
}
