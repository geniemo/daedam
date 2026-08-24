import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getMe, logout, withdraw } from '@/api/auth'
import { getCredits } from '@/api/credits'
import { OutlineButton, SectionLabel } from '@/components/ui'

const PROVIDER_LABEL: Record<string, string> = {
  kakao: '카카오',
  google: 'Google',
  local: '로그인 없이 실행 중',
}

/**
 * 내 정보.
 *
 * 프로필은 읽기 전용이다 — 이름·사진·이메일이 전부 카카오·구글에서 오므로
 * 여기서 고쳐 봐야 다음 로그인에 덮인다. 고치려면 제공자 쪽에서 고쳐야 한다는
 * 사실을 화면이 말해 준다.
 */
export function Account() {
  const nav = useNavigate()
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: getMe, retry: false })
  const { data: credits } = useQuery({ queryKey: ['credits'], queryFn: getCredits })
  const queryClient = useQueryClient()

  return (
    <main className="mx-auto max-w-(--container-doc) px-8 pt-[44px] pb-20 animate-dm-fade">
      <button onClick={() => nav('/')} className="mb-4 text-[13px] text-muted">
        ← 내 면접
      </button>
      <h1 className="m-0 text-[24px] font-bold tracking-[-.03em]">내 정보</h1>

      <section className="mt-[22px] flex items-center gap-[14px] border-b border-line pb-[26px]">
        {me?.avatarUrl ? (
          <img
            src={me.avatarUrl}
            alt=""
            className="h-[52px] w-[52px] rounded-full border border-field object-cover"
          />
        ) : (
          <span className="flex h-[52px] w-[52px] items-center justify-center rounded-full border border-field bg-surface text-[17px] font-semibold text-muted">
            {(me?.name || '지원자').slice(-2, -1)}
          </span>
        )}
        <span className="flex flex-col gap-[4px]">
          <span className="text-[17px] font-semibold text-ink">{me?.name || '지원자'}</span>
          <span className="text-[13px] text-muted">
            {me?.email || '이메일을 받지 않았습니다'}
          </span>
        </span>
      </section>

      <section className="border-b border-line py-[26px]">
        <div className="mb-[14px]">
          <SectionLabel>연결된 계정</SectionLabel>
        </div>
        <div className="flex items-center gap-[12px]">
          <span className="flex flex-1 flex-col gap-[3px]">
            <span className="text-[14px] font-semibold text-ink">
              {PROVIDER_LABEL[me?.provider ?? ''] ?? me?.provider}
            </span>
            <span className="text-[12.5px] text-muted">
              이름과 사진은 여기서 옵니다. 바꾸시려면 해당 서비스에서 바꿔 주세요.
            </span>
          </span>
          {me && me.provider !== 'local' && (
            <OutlineButton
              onClick={async () => {
                await logout()
                await queryClient.invalidateQueries()
              }}
              className="px-[14px] py-[9px] text-[12.5px]"
            >
              로그아웃
            </OutlineButton>
          )}
        </div>
      </section>

      <section className="border-b border-line py-[26px]">
        <div className="mb-[14px] flex items-center">
          <SectionLabel>크레딧</SectionLabel>
          <div className="flex-1" />
          <button onClick={() => nav('/credits')} className="text-[12.5px] text-muted">
            충전하기 →
          </button>
        </div>
        <div className="mb-[16px] flex items-baseline gap-[6px]">
          <span className="num text-[30px] leading-none font-bold tracking-[-.04em]">
            {credits?.balance ?? '—'}
          </span>
          <span className="text-[13px] text-faint">개 보유</span>
        </div>
        {credits?.history.length ? (
          <ul className="m-0 flex list-none flex-col gap-[9px] p-0">
            {credits.history.slice(0, 8).map((event, index) => (
              <li key={`${event.at}-${index}`} className="flex items-center gap-[10px]">
                <span className="flex-1 text-[13px] text-body-2">{event.label}</span>
                <span className="num text-[12px] text-faint">
                  {new Date(event.at).toLocaleDateString('ko-KR')}
                </span>
                <span
                  className={`num w-[46px] text-right text-[13px] font-semibold ${
                    event.delta > 0 ? 'text-positive' : 'text-muted'
                  }`}
                >
                  {event.delta > 0 ? `+${event.delta}` : event.delta}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="m-0 text-[13px] text-faint">아직 내역이 없습니다.</p>
        )}
      </section>

      {me && me.provider !== 'local' && <Withdraw onDone={() => nav('/')} />}
    </main>
  )
}

/**
 * 회원 탈퇴.
 *
 * 되돌릴 수 없으므로 무엇이 지워지는지 먼저 적고, 그것을 읽었다는 표시를
 * 받은 뒤에만 버튼이 눌린다. 닉네임을 받아 적게 하는 방식도 있지만 이
 * 규모에서는 과하다 — 실수로 누르는 것만 막으면 된다.
 */
function Withdraw({ onDone }: { onDone: () => void }) {
  const [open, setOpen] = useState(false)
  const [agreed, setAgreed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const queryClient = useQueryClient()

  if (!open) {
    return (
      <section className="py-[26px]">
        <button onClick={() => setOpen(true)} className="text-[12.5px] text-faint underline">
          회원 탈퇴
        </button>
      </section>
    )
  }

  return (
    <section className="mt-[26px] rounded-card border border-accent-line bg-accent-bg p-[18px]">
      <h2 className="m-0 text-[15px] font-bold text-ink">회원 탈퇴</h2>
      <p className="mt-[10px] mb-0 text-[13px] leading-[1.75] text-body-2">
        탈퇴하시면 아래가 <strong>모두 삭제되고 되돌릴 수 없습니다.</strong>
      </p>
      <ul className="mt-[10px] mb-0 flex list-none flex-col gap-[5px] p-0 text-[13px] text-body-2">
        {[
          '등록하신 회사와 리서치 결과, 만들어 둔 질문',
          '면접 기록 — 녹음된 음성과 전사, 답변 리포트',
          '남아 있는 크레딧',
        ].map((item) => (
          <li key={item} className="flex gap-[7px]">
            <span className="text-faint">·</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>

      <label className="mt-[16px] flex cursor-pointer items-start gap-[8px] text-[13px] text-body-2">
        <input
          type="checkbox"
          checked={agreed}
          onChange={(e) => setAgreed(e.target.checked)}
          className="mt-[3px]"
        />
        <span>위 내용을 확인했으며 삭제에 동의합니다.</span>
      </label>

      {error && <p className="mt-[10px] mb-0 text-[13px] text-accent">{error}</p>}

      <div className="mt-[16px] flex items-center gap-[8px]">
        <button
          disabled={!agreed || busy}
          onClick={async () => {
            setBusy(true)
            setError('')
            try {
              await withdraw()
              await queryClient.invalidateQueries()
              onDone()
            } catch {
              setError('탈퇴하지 못했습니다. 잠시 후 다시 시도해 주세요.')
              setBusy(false)
            }
          }}
          className={`rounded-control px-[18px] py-[10px] text-[13.5px] font-semibold text-white ${
            agreed && !busy ? 'bg-ink' : 'bg-faintest'
          }`}
        >
          {busy ? '삭제 중' : '탈퇴하기'}
        </button>
        <OutlineButton
          onClick={() => {
            setOpen(false)
            setAgreed(false)
          }}
          className="px-[16px] py-[10px] text-[13.5px]"
        >
          취소
        </OutlineButton>
      </div>
    </section>
  )
}
