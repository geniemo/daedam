import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { completeOnboarding, logout } from '@/api/auth'
import { CheckDot, EmptyDot, PrimaryButton, TextField } from '@/components/ui'

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
 */
export function Onboarding() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [terms, setTerms] = useState(false)
  const [privacy, setPrivacy] = useState(false)
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)
  const ready = name.trim().length > 0 && terms && privacy

  const submit = async () => {
    if (!ready || sending) return
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

  return (
    <main className="mx-auto flex min-h-dvh max-w-[560px] flex-col justify-center px-8 py-16 animate-dm-fade">
      <div className="flex items-center gap-[10px]">
        <span className="flex h-[26px] w-[26px] items-center justify-center border-[1.5px] border-ink">
          <span className="h-[10px] w-[10px] bg-accent" />
        </span>
        <span className="text-[20px] font-bold tracking-[-.02em] text-ink">대담</span>
      </div>

      <h1 className="mt-[26px] mb-0 text-[28px] leading-[1.35] font-bold tracking-[-.03em] text-ink">
        시작하기 전에
      </h1>
      <p className="mt-[14px] mb-0 text-[14.5px] leading-[1.75] text-body-2">
        면접관이 부를 이름을 확인하고, 면접 기록이 어떻게 다뤄지는지에 동의해
        주세요. 한 번만 묻습니다.
      </p>

      <div className="mt-[30px] flex flex-col gap-[8px]">
        <label className="text-[13px] font-semibold text-ink" htmlFor="onboard-name">
          이름
        </label>
        <TextField
          id="onboard-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="예: 박지원"
          autoFocus
        />
        <p className="m-0 text-[12.5px] leading-[1.6] text-muted">
          면접관이 이 이름으로 부르고, 음성 인식이 이 표기를 힌트로 씁니다.
          실제 면접처럼 한글 실명을 권합니다.
        </p>
      </div>

      <div className="mt-[22px] flex flex-col gap-[10px]">
        {[
          ['이용약관에 동의합니다', '/terms', terms, () => setTerms((v) => !v)] as const,
          ['개인정보 수집·이용에 동의합니다', '/privacy', privacy, () => setPrivacy((v) => !v)] as const,
        ].map(([label, href, checked, toggle]) => (
          <div key={href} className="flex items-center gap-[10px]">
            <button
              type="button"
              onClick={toggle}
              aria-pressed={checked}
              className="flex items-center gap-[10px] text-left text-[13.5px] text-ink"
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
        <p className="m-0 text-[12px] leading-[1.6] text-faint">
          면접 중 음성·웹캠 영상과 얼굴 스틸이 기록되고, 분석을 위해 Google
          Gemini로 처리됩니다. 자세한 내용은 개인정보처리방침에 있습니다.
        </p>
      </div>

      {error && <p className="mt-[14px] mb-0 text-[13px] text-accent">{error}</p>}

      <PrimaryButton
        onClick={submit}
        className={`mt-[26px] h-[50px] text-[14.5px] ${ready && !sending ? '' : 'cursor-default opacity-40'}`}
      >
        {sending ? '저장 중…' : '동의하고 시작하기'}
      </PrimaryButton>

      <button
        type="button"
        onClick={async () => {
          await logout()
          window.location.href = '/'
        }}
        className="mt-[16px] self-start text-[12.5px] text-faint hover:text-muted"
      >
        다른 계정으로 로그인
      </button>
    </main>
  )
}
