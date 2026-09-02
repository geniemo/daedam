import { useQuery } from '@tanstack/react-query'
import { getProviders, loginUrl } from '@/api/auth'
import { GoogleMark, KakaoMark } from '@/components/ProviderMark'

/**
 * 로그인하지 않은 사람이 보는 첫 화면.
 *
 * 앞서는 `/`가 곧 카드 목록이라 로그인 안 한 사람이 볼 화면이 없었다.
 *
 * 마케팅 페이지가 아니라 제품의 첫 화면으로 만든다 — 같은 타이포와 같은 여백을
 * 쓰고, 강조색은 면접 화면과 같은 자리에만 둔다. 브랜드 색이 들어오는 곳은
 * 로그인 버튼 하나뿐이다. 카카오·구글이 자기 색과 표기를 규정하기 때문이다.
 */
export function Landing() {
  const { data: providers } = useQuery({ queryKey: ['providers'], queryFn: getProviders })

  return (
    <main className="mx-auto flex min-h-dvh max-w-[560px] flex-col justify-center px-8 py-16 animate-dm-fade">
      <div className="flex items-center gap-[10px]">
        <span className="flex h-[26px] w-[26px] items-center justify-center border-[1.5px] border-ink">
          <span className="h-[10px] w-[10px] bg-accent" />
        </span>
        <span className="text-[20px] font-bold tracking-[-.02em] text-ink">대담</span>
      </div>

      <h1 className="mt-[26px] mb-0 text-[34px] leading-[1.32] font-bold tracking-[-.035em] text-ink">
        지원한 회사가
        <br />
        실제로 물어볼 것을 묻습니다
      </h1>
      <p className="mt-[18px] mb-0 text-[15px] leading-[1.75] text-body-2">
        회사와 직무를 등록하면 공개된 자료를 조사해 질문을 만듭니다. 음성으로 면접을
        진행하고, 끝나면 답변마다 무엇이 부족했는지 짚어 드립니다.
      </p>

      {/* 준비 → 면접 → 리포트. 화면 순서가 곧 제품의 순서라 번호를 매긴다. */}
      <ol className="mt-[34px] mb-0 flex list-none flex-col gap-[14px] p-0">
        {[
          ['회사 조사', '채용공고와 공개 자료에서 질문의 근거를 모읍니다'],
          ['음성 면접', '준비된 질문에서 시작해 답변을 따라 꼬리질문을 이어갑니다'],
          ['답변 코칭', '말하기 속도·머뭇거림과 답변 내용을 함께 봅니다'],
        ].map(([title, detail], index) => (
          <li key={title} className="flex gap-[14px]">
            <span className="num mt-[3px] text-[12px] font-semibold text-accent tabular-nums">
              0{index + 1}
            </span>
            <span className="flex flex-col gap-[3px]">
              <span className="text-[14px] font-semibold text-ink">{title}</span>
              <span className="text-[13.5px] leading-[1.6] text-muted">{detail}</span>
            </span>
          </li>
        ))}
      </ol>

      <div className="mt-[38px] flex flex-col gap-[10px]">
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

      <p className="mt-[22px] mb-0 text-[12px] leading-[1.7] text-faintest">
        면접 중 음성이 녹음되고, 답변 분석에 쓰입니다.
      </p>
    </main>
  )
}

const LABEL: Record<string, string> = { kakao: '카카오로 시작하기', google: 'Google로 시작하기' }

function LoginButton({ provider }: { provider: string }) {
  // 카카오는 지정 노란색(#FEE500)과 검정 글자를, 구글은 흰 바탕에 테두리를
  // 요구한다. 제품 팔레트를 여기서만 벗어나는 이유가 그것이다.
  const kakao = provider === 'kakao'
  const Mark = kakao ? KakaoMark : provider === 'google' ? GoogleMark : null
  return (
    <a
      href={loginUrl(provider)}
      className={`relative flex h-[50px] items-center justify-center rounded-control text-[14.5px] font-semibold ${
        kakao ? 'text-[#191600]' : 'border border-field bg-surface text-ink'
      }`}
      style={kakao ? { background: '#FEE500' } : undefined}
    >
      {/* 상징은 왼쪽에 고정하고 글자는 버튼 가운데에 둔다. 둘을 한 줄로 묶으면
          라벨 길이가 달라서 버튼마다 상징의 위치가 어긋난다. */}
      {Mark && (
        <span className="absolute left-[16px] flex items-center">
          <Mark />
        </span>
      )}
      {LABEL[provider] ?? `${provider}로 시작하기`}
    </a>
  )
}
