import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getProviders, loginUrl } from '@/api/auth'
import { GoogleMark, KakaoMark } from '@/components/ProviderMark'
import { Avatar, Waveform } from '@/components/Stage'
import { AccentDot, CheckDot, EmptyDot, IndeterminateBar, Spinner } from '@/components/ui'
import { Metric } from '@/screens/Report'

/**
 * 로그인하지 않은 사람이 보는 첫 화면.
 * 규격: design_handoff_daedam/HANDOFF-landing-onboarding.md §1 (2a 라이브 데모).
 *
 * 앞서는 560px 글 기둥 하나라 1440px 화면이 비어 보였다. 지금은 밝은 바탕을
 * 유지하되 히어로 우측에 **스스로 돌아가는 면접관 창**을 둔다. 회사가 바뀌면
 * 질문이 바뀐다 — "그 회사에 맞춘 질문"을 말이 아니라 예시로 보여준다. 아래로
 * 01·02·03 단계가 실제 화면 조각으로 이어진다.
 *
 * 마케팅 페이지가 아니라 제품의 첫 화면으로 만든다 — 같은 타이포와 같은 여백을
 * 쓰고, 데모 창은 면접 화면과 같은 아바타·파형(components/Stage.tsx)을 그린다.
 * 브랜드 색이 들어오는 곳은 로그인 버튼뿐이다. 카카오·구글이 자기 색과 표기를
 * 규정하기 때문이다. 별도 로그인 페이지는 없다 — 헤더 "로그인"은 히어로의
 * 소셜 버튼으로 내려보낸다.
 */
export function Landing() {
  const { data: providers } = useQuery({ queryKey: ['providers'], queryFn: getProviders })
  const [demo, setDemo] = useState(0)
  // 회사가 돌아간다. 손으로 고르면 그 시점부터 다시 센다 — 고르자마자 넘어가면
  // 고른 보람이 없다.
  useEffect(() => {
    const timer = setInterval(() => setDemo((i) => (i + 1) % DEMOS.length), DEMO_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [demo])

  const scrollToLogin = () =>
    document.getElementById('login')?.scrollIntoView({ behavior: 'smooth', block: 'center' })

  return (
    <main className="break-keep animate-dm-fade">
      {/* 헤더 — 공통 헤더(Chrome.tsx)와 같은 규격. 로그인 전이라 메뉴는 없다. */}
      <header
        className="sticky top-0 z-40 h-16 border-b border-line"
        style={{ background: 'var(--header-bg)', backdropFilter: 'blur(8px)' }}
      >
        <div className="mx-auto flex h-full max-w-(--container-home) items-center px-8">
          <Logo />
          <div className="flex-1" />
          <button
            type="button"
            onClick={scrollToLogin}
            className="rounded-control border border-field bg-surface px-4 py-[9px] text-[13.5px] font-semibold text-ink"
          >
            로그인
          </button>
        </div>
      </header>

      {/* 히어로 — 왼쪽 카피, 오른쪽 데모 창. 1000px 아래에서는 카피가 위. */}
      <section className="mx-auto grid max-w-(--container-home) grid-cols-[minmax(0,1fr)_minmax(0,1fr)] items-center gap-[56px] px-8 pt-[72px] pb-20 max-[1000px]:grid-cols-1">
        <div className="flex flex-col">
          <div className="mb-[22px] flex items-center gap-2">
            <AccentDot size={5} />
            <span className="text-[12.5px] font-semibold tracking-[.04em] text-accent">
              AI 음성 모의면접
            </span>
          </div>
          <h1 className="m-0 text-[44px] leading-[1.22] font-bold tracking-[-.04em] text-ink">
            대담과 함께
            <br />
            미리 면접장에 들어가세요
          </h1>
          <p className="mt-[22px] mb-0 max-w-[440px] text-[16px] leading-[1.75] text-body-2">
            몇 번이든 다시 연습하세요.
          </p>

          <div id="login" className="mt-9 flex flex-wrap gap-[10px]">
            {(providers ?? []).map((provider) => (
              <LoginButton key={provider} provider={provider} />
            ))}
            {providers?.length === 0 && (
              /* 서버에 로그인 설정이 없다 — 개발 중이거나 설정을 빠뜨린 것이다.
                 버튼을 그리면 눌러도 404가 나므로 사실을 적는다. */
              <p className="m-0 text-[13px] text-faint">
                로그인 설정이 없는 서버입니다. 새로고침하면 바로 들어갑니다.
              </p>
            )}
          </div>

          {/* 제품 사실 셋. 숫자는 실제 단계 수·지표 수다 — 지어낸 값이 아니다. */}
          <div className="mt-10 flex flex-wrap gap-7">
            {[
              ['4단계', '자기소개 · 직무역량 · 인성 · 마무리'],
              ['6가지', '음성 지표를 권장 범위와 비교'],
              ['답변마다', '녹음을 다시 듣고 문장을 고치기'],
            ].map(([value, label]) => (
              <div key={value} className="flex flex-col gap-1">
                <span className="num text-[22px] leading-none font-bold tracking-[-.03em] text-ink">
                  {value}
                </span>
                <span className="text-[12px] text-muted">{label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <LiveDemo demo={DEMOS[demo]} />
          <div className="flex flex-wrap justify-center gap-[6px]">
            {DEMOS.map((item, i) => (
              <button
                key={item.company}
                type="button"
                onClick={() => setDemo(i)}
                className={`rounded-full border px-[11px] py-[5px] text-[12px] transition-colors duration-300 ${
                  i === demo ? 'border-ink bg-ink text-white' : 'border-line bg-transparent text-muted'
                }`}
              >
                {item.company}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* 단계 셋 — 각각 실제 화면의 조각으로 증명한다. */}
      <section className="mx-auto max-w-(--container-home) px-8 pb-10">
        <StepFrame
          label="01 회사 조사"
          title="실제와 같은 면접관과 대화하세요"
          body="공신력 있는 근거를 통해 기업을 조사합니다. 실제 면접관이 할 법한 질문을 받아보세요."
        >
          <ResearchLog />
        </StepFrame>
        <StepFrame
          label="02 음성 면접"
          title="얼버무린 자리를 먼저 들켜보세요"
          body="파고드는 꼬리질문을 받아보세요. 숫자가 빠지면 숫자를, 근거가 빠지면 근거를 되묻습니다. 모의면접에서 먼저 당황해보세요."
        >
          <Dialogue />
        </StepFrame>
        <StepFrame
          label="03 답변 코칭"
          title="정확한 지표와 함께 리뷰하고 개선하세요"
          body="녹음을 다시 들으면서 답변마다 잘한 점과 빠진 것을 확인하고, 다음 면접장에서 그대로 말할 수 있게 고쳐 쓴 문장을 받으세요."
        >
          <div className="flex flex-col gap-3">
            <ScoreCard />
            <CoachCard />
          </div>
        </StepFrame>
      </section>

      {/* 마무리 띠와 푸터 — 부제도 버튼도 없다. 로그인은 위에서 이미 청했다. */}
      <section className="border-t border-line bg-surface">
        <div className="mx-auto flex max-w-(--container-home) flex-col items-center px-8 py-24 text-center">
          <h2 className="m-0 text-[34px] leading-[1.3] font-bold tracking-[-.04em] text-ink">
            연습은 여기서 끝내고
            <br />
            합격 소식을 전하세요
          </h2>
        </div>
        <div className="mx-auto flex max-w-(--container-home) flex-wrap gap-4 px-8 pb-10 text-[12px] text-faintest">
          <span>면접 중 음성과 웹캠 영상이 기록되고, 답변 분석에 쓰입니다.</span>
          <div className="flex-1" />
          <a href="/terms" className="text-faint hover:text-muted">
            이용약관
          </a>
          <a href="/privacy" className="text-faint hover:text-muted">
            개인정보처리방침
          </a>
        </div>
      </section>
    </main>
  )
}

function Logo() {
  return (
    <div className="flex items-center gap-[10px]">
      <span className="flex h-[26px] w-[26px] items-center justify-center border-[1.5px] border-ink">
        <span className="h-[10px] w-[10px] bg-accent" />
      </span>
      <span className="text-[20px] font-bold tracking-[-.02em] text-ink">대담</span>
    </div>
  )
}

const LABEL: Record<string, string> = { kakao: '카카오로 시작하기', google: 'Google로 시작하기' }

function LoginButton({ provider }: { provider: string }) {
  // 카카오는 지정 노란색과 검정 글자를, 구글은 흰 바탕에 테두리를 요구한다.
  // 제품 팔레트를 여기서만 벗어나는 이유가 그것이다.
  const kakao = provider === 'kakao'
  const Mark = kakao ? KakaoMark : provider === 'google' ? GoogleMark : null
  return (
    <a
      href={loginUrl(provider)}
      className={`relative flex h-[50px] min-w-[236px] items-center justify-center rounded-control pr-5 pl-11 text-[14.5px] font-semibold ${
        kakao ? 'bg-kakao text-kakao-ink' : 'border border-field bg-surface text-ink'
      }`}
    >
      {/* 상징은 왼쪽에 고정하고 글자는 버튼 가운데에 둔다. 둘을 한 줄로 묶으면
          라벨 길이가 달라서 버튼마다 상징의 위치가 어긋난다. */}
      {Mark && (
        <span className="absolute left-4 flex items-center">
          <Mark />
        </span>
      )}
      {LABEL[provider] ?? `${provider}로 시작하기`}
    </a>
  )
}

/* ── 데모 창 — 회사가 바뀌면 질문이 바뀐다 ─────────────────────────────── */

/** 다음 회사로 넘어가는 간격. 가장 긴 질문을 다 치고(28ms × 63자 ≈ 1.8초) 파형이
    한동안 보일 만큼. */
const DEMO_INTERVAL_MS = 5200

/** 시안 값이다. 실제 서비스가 만든 질문이 아니라 고정 예시로 둔다. */
const DEMOS = [
  {
    company: '누리테크',
    role: '서비스기획',
    question: '저희가 올해 공개한 파트너 정산 서비스를 써보셨다면, 어떤 점을 먼저 개선하시겠습니까?',
    source: '2026년 3월 보도자료 · 채용공고 우대사항',
  },
  {
    company: '세종바이오',
    role: '마케팅',
    question:
      '지원서에 쓰신 SNS 캠페인 경험을, 처방약 광고 규제가 있는 저희 업계에서는 어떻게 바꿔 적용하시겠어요?',
    source: '지원서 경험 2 · 회사 IR 자료',
  },
  {
    company: '한빛금융',
    role: 'IT기획',
    question:
      '작년 저희 앱 장애 때 고객 공지가 늦었다는 지적이 있었는데, 기획자로서 무엇을 먼저 바꾸시겠습니까?',
    source: '2025년 11월 뉴스 · 인재상 "책임"',
  },
  {
    company: '오름소프트',
    role: '백엔드 개발',
    question:
      '지원서의 트래픽 3배 처리 경험에서, 병목이 DB였는지 애플리케이션이었는지 어떻게 판단하셨나요?',
    source: '지원서 경험 1 · 기술 블로그',
  },
]

/** 타자 효과 — 면접관이 지금 묻고 있다는 느낌. 진폭처럼 60fps 값은 아니라 state로 충분하다. */
function useTyped(text: string, speedMs = 28): string {
  const [shown, setShown] = useState(0)
  useEffect(() => {
    setShown(0)
    let i = 0
    const timer = setInterval(() => {
      i += 1
      setShown(i)
      if (i >= text.length) clearInterval(timer)
    }, speedMs)
    return () => clearInterval(timer)
  }, [text, speedMs])
  return text.slice(0, shown)
}

/**
 * 면접 화면(Interview.tsx)의 축소판. 상태 줄 · 아바타 · 자막 · 파형 · 출처.
 * 타이핑이 끝나면 "듣고 있습니다"로 넘어가고 파형이 돈다 — 실제 면접의 말차례와
 * 같은 순서다.
 */
function LiveDemo({ demo }: { demo: (typeof DEMOS)[number] }) {
  const typed = useTyped(demo.question)
  const done = typed.length >= demo.question.length
  return (
    <div className="relative flex min-h-[440px] w-full max-w-[640px] flex-col overflow-hidden rounded-card border border-stage-line bg-stage">
      <div
        className="pointer-events-none absolute inset-0"
        style={{ background: 'var(--gradient-stage-vignette)' }}
      />
      <div className="relative flex items-center px-[22px] py-[18px]">
        <span
          className="rounded-full"
          style={{
            width: 6,
            height: 6,
            background: done ? 'var(--color-listening)' : 'var(--color-accent)',
            transition: 'background .4s',
          }}
        />
        <span className="ml-2 text-[13px] text-stage-ink">
          {done ? '듣고 있습니다' : '면접관이 말하고 있습니다'}
        </span>
        <div className="flex-1" />
        <span key={demo.company} className="animate-dm-fade-slow text-[12.5px] text-stage-muted-2">
          {demo.company} · {demo.role}
        </span>
      </div>
      <div className="relative flex flex-1 items-center justify-center">
        <Avatar size={150} speaking={!done} />
      </div>
      {/* 자리를 늘 비워 둔다 — 자막 길이에 따라 아바타가 위아래로 튀면 안 된다. */}
      <div className="relative mx-auto flex min-h-[78px] max-w-[520px] items-start justify-center px-6">
        <p className="m-0 text-center text-[16.5px] leading-[1.65] font-medium tracking-[-.01em] text-stage-ink">
          {typed}
          {!done && (
            <span className="ml-[2px] inline-block w-[2px] bg-accent align-[-2px]" style={{ height: 16 }} />
          )}
        </p>
      </div>
      <div className="relative flex h-[92px] items-center justify-center">
        {done ? (
          <Waveform active height={28} />
        ) : (
          <span className="text-[12px] text-stage-muted-3">답변이 끝나면 마이크가 열립니다</span>
        )}
      </div>
      <div className="relative flex items-center gap-2 px-[22px] pb-4">
        <span className="text-[11px] text-stage-muted">이 질문의 출처</span>
        <span key={demo.company} className="animate-dm-fade-slow text-[11px] text-stage-muted-2">
          {demo.source}
        </span>
      </div>
    </div>
  )
}

/* ── 단계 섹션 ───────────────────────────────────────────────────────── */

function StepFrame({
  label,
  title,
  body,
  children,
}: {
  label: string
  title: string
  body: string
  children: ReactNode
}) {
  return (
    <div className="grid grid-cols-[300px_minmax(0,1fr)] items-center gap-12 border-t border-line py-14 max-[900px]:grid-cols-1">
      <div className="flex flex-col gap-3">
        <span className="num text-[12px] font-semibold tracking-[.05em] text-accent">{label}</span>
        <h2 className="m-0 text-[25px] leading-[1.3] font-bold tracking-[-.03em] text-ink">{title}</h2>
        <p className="m-0 text-[14.5px] leading-[1.75] text-body-2">{body}</p>
      </div>
      <div className="min-w-0">{children}</div>
    </div>
  )
}

/** 시안 값. 조사가 실제로 하는 일의 순서를 예시로 보여준다. */
const RESEARCH_STEPS = [
  ['채용공고와 직무기술서 분석', '요구 역량 12개를 추출하고 우선순위를 매겼습니다.'],
  ['최근 1년 뉴스 · IR · 기술 블로그 수집', '파트너 정산 서비스 공개(3월)와 물류 자회사 설립(7월)을 확인했습니다.'],
  ['인재상 · 조직문화 정리', '채용 페이지와 재직자 인터뷰에서 반복되는 표현을 모았습니다.'],
  ['지원서와 대조 · 검증이 필요한 항목 추출', '경험 1의 성과 수치와 본인 기여도를 확인할 질문이 필요합니다.'],
  ['질문 준비', '4단계에 걸쳐 8개 질문과 꼬리질문을 준비합니다.'],
]

/**
 * 리서치 진행 카드의 목업. 2.2초마다 다음 단계로, 다 끝나면 처음으로.
 * **행 높이는 고정**이다 — 결과 문장이 늘 자리를 차지하고 완료될 때 나타난다.
 * 줄이 생겼다 사라지면 카드가 위아래로 튄다.
 */
function ResearchLog() {
  const [at, setAt] = useState(2)
  useEffect(() => {
    const timer = setInterval(() => setAt((v) => (v >= RESEARCH_STEPS.length ? 0 : v + 1)), 2200)
    return () => clearInterval(timer)
  }, [])
  return (
    <div className="rounded-card border border-line bg-surface p-[22px]">
      <div className="mb-4 flex items-start">
        <div className="flex flex-col gap-[3px]">
          <span className="text-[17px] font-bold tracking-[-.02em] text-ink">누리테크</span>
          <span className="text-[12.5px] text-muted">서비스기획 · 신입</span>
        </div>
        <div className="flex-1" />
        <span className="num text-[11.5px] text-faint">3분 40초 경과</span>
      </div>
      <div className="mb-[18px]">
        <IndeterminateBar />
      </div>
      <div className="flex flex-col">
        {RESEARCH_STEPS.map(([title, result], i) => {
          const state = i < at ? 'done' : i === at ? 'now' : 'wait'
          return (
            <div
              key={title}
              className={`flex gap-3 py-[10px] ${i < RESEARCH_STEPS.length - 1 ? 'border-b border-hair' : ''}`}
            >
              <span className="mt-[2px]">
                {state === 'done' ? <CheckDot /> : state === 'now' ? <Spinner /> : <EmptyDot />}
              </span>
              <div className="flex min-h-[40px] flex-col gap-[3px]">
                <span
                  className={`text-[13.5px] font-semibold transition-colors duration-300 ${
                    state === 'done' ? 'text-ink' : state === 'now' ? 'text-accent' : 'text-faintest'
                  }`}
                >
                  {title}
                </span>
                <span
                  className="min-h-[18px] text-[12px] leading-[1.5] text-faint transition-opacity duration-400"
                  style={{ opacity: state === 'done' ? 1 : 0 }}
                >
                  {result}
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/** 시안 값. 꼬리질문이 어떻게 파고드는지 한 왕복으로 보여준다. */
const DIALOGUE = [
  ['면접관', '그 프로젝트에서 가장 어려웠던 판단은 무엇이었나요?'],
  ['나', '분류 기준을 바꾸는 게 가장 어려웠습니다. 팀원들은 기존 기준을 유지하자고 했는데…'],
  ['면접관', '팀원들을 어떤 근거로 설득하셨나요? 비교 자료가 있었습니까?'],
  ['나', '음… 3개월 데이터로 두 기준을 나눠 봤을 때 회전율 차이가…'],
]

function Dialogue() {
  return (
    <div className="grid grid-cols-2 gap-3 max-[600px]:grid-cols-1">
      {DIALOGUE.map(([who, text], i) => {
        const interviewer = who === '면접관'
        return (
          <div key={i} className="flex flex-col gap-2 rounded-card border border-line bg-surface p-[18px]">
            <div className="flex items-center gap-[7px]">
              <span
                className={`rounded-full ${interviewer ? 'bg-accent' : 'bg-listening'}`}
                style={{ width: 5, height: 5 }}
              />
              <span className={`text-[11.5px] font-semibold ${interviewer ? 'text-accent' : 'text-listening'}`}>
                {who}
              </span>
              {i === 2 && (
                <span className="ml-auto rounded-chip border border-line-2 px-[6px] py-[2px] text-[10.5px] text-faint">
                  꼬리질문
                </span>
              )}
            </div>
            <p className={`m-0 text-[13.5px] leading-[1.7] ${interviewer ? 'font-semibold text-ink' : 'text-body-2'}`}>
              {text}
            </p>
          </div>
        )
      })}
    </div>
  )
}

/**
 * 리포트 머리 부분의 축소판. 지표 카드는 Report.tsx의 Metric 그대로다 — 판정과
 * 막대가 실제 리포트와 같은 규칙으로 나온다. 숫자만 시안 값이다.
 */
function ScoreCard() {
  return (
    <div className="flex flex-col gap-[18px] rounded-card border border-line bg-surface p-[22px]">
      <div className="flex items-start">
        <div className="flex flex-col gap-[5px]">
          <span className="text-[12px] text-faint">18분 12초 · 답변 8개</span>
          <span className="text-[17px] font-bold tracking-[-.02em] text-ink">누리테크 · 서비스기획</span>
        </div>
        <div className="flex-1" />
        <div className="flex flex-col items-end gap-[3px]">
          <div className="flex items-baseline gap-[3px]">
            <span className="num text-[40px] leading-none font-bold tracking-[-.05em] text-ink">80</span>
            <span className="text-[13px] text-faint">/ 100</span>
          </div>
          <span className="text-[11px] text-faintest">답변 점수의 평균</span>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Metric compact label="말하기 속도" value={312} unit="음절/분" low={280} high={360} range="280~360 권장" />
        <Metric compact label="필러 워드" value={3.4} unit="회/분" high={3} range="분당 3회 이하" />
        <Metric compact label="답변까지" value={2.4} unit="초" high={3} range="3초 이내" />
      </div>
    </div>
  )
}

/** 답변 하나의 코칭 블록. 재생 줄은 Report.tsx Playback의 모양만 — 들을 소리가 없다. */
function CoachCard() {
  return (
    <div className="flex flex-col gap-[14px] rounded-card border border-line bg-surface p-[22px]">
      <div className="flex items-center gap-3">
        <span className="num text-[11.5px] font-semibold text-faintest">Q3</span>
        <span className="min-w-0 flex-1 text-[13.5px] font-semibold text-ink">
          물류 데이터 분석 프로젝트에서 본인이 맡은 역할
        </span>
        <span className="num text-[11.5px] text-faintest">84.0초</span>
        <span className="num text-[15px] font-bold text-ink">88</span>
      </div>
      <div className="flex items-center gap-3 rounded-control border border-line-2 bg-surface-2 px-[13px] py-[10px]">
        <span
          className="flex items-center justify-center rounded-full bg-ink text-white"
          style={{ width: 26, height: 26, fontSize: 9 }}
        >
          ▶
        </span>
        <div className="flex-1 bg-line-3" style={{ height: 3 }} />
        <span className="text-[11.5px] text-muted">내 답변 다시 듣기</span>
      </div>
      <div className="border-l-2 border-positive pl-[14px]">
        <div className="mb-[5px] text-[11.5px] font-bold text-positive">잘한 점</div>
        <p className="m-0 text-[13px] leading-[1.75] text-body">
          문제 인식, 조치, 결과가 순서대로 나왔습니다.
        </p>
      </div>
      <div className="border-l-2 border-accent pl-[14px]">
        <div className="mb-[5px] text-[11.5px] font-bold text-accent">이렇게 바꿔보세요</div>
        <p className="m-0 text-[13px] leading-[1.75] text-body">
          마지막 문장에 숫자 하나를 붙이세요. 재고가 몇 % 줄었는지, 그 제안이 몇 개 매장에
          적용되었는지.
        </p>
      </div>
    </div>
  )
}
