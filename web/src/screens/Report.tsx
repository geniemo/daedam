import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { audioUrl, getFeedback, listSessions, videoUrl } from '@/api/preparation'
import type { Feedback, FeedbackStatus, InterviewSession } from '@/api/preparation'
import { useActiveCard } from '@/store/app'
import { AccentDot, SectionLabel, Spinner } from '@/components/ui'
import { Delivery } from './Delivery'

/**
 * README §10. 피드백 리포트 — 코칭 중심. 점수에서 시작해 답변별 개선 제안으로.
 *
 * 모든 값은 서버가 만든 feedback.json에서 온다. 지어내지 않기로 한 것 둘:
 * **백분위**는 비교할 모집단이 없고, **단계별 점수**는 전사에 단계 정보가
 * 없어서 낼 수 없다. 자리를 비워 두는 편이 그럴듯한 숫자를 채우는 것보다 낫다.
 */
export function Report() {
  const nav = useNavigate()
  const card = useActiveCard()
  // 어느 회차를 보고 있는가. 고르지 않았으면 이력의 첫 줄 — 가장 최근 회차다.
  const [sessionId, setSessionId] = useState<string | undefined>(undefined)
  const { data: sessions, isPending: loadingSessions } = useQuery({
    queryKey: ['sessions', card.id],
    queryFn: () => listSessions(card.id),
    retry: false,
  })
  // 서버에 맡기지 않고 이력에서 고르는 이유: 서버의 "가장 최근"은 아무 말 없이
  // 끝난 면접까지 포함한다(분석 화면이 그걸 알아야 무슨 일이 있었는지 말한다).
  // 리포트는 회차로 세는 것만 보면 된다 — 없던 면접의 빈 화면을 띄우지 않는다.
  const shown = sessionId ?? sessions?.[0]?.id
  const { data, isError } = useQuery({
    queryKey: ['feedback', card.id, shown],
    queryFn: () => getFeedback(card.id, shown),
    retry: false,
    // 이력이 오기 전에 물으면 서버 기준의 최근 회차를 한 번 받아 왔다가 다시
    // 그린다 — 없던 면접의 빈 화면이 잠깐 스쳤다.
    enabled: !loadingSessions,
    // 분석은 수십 초 걸린다. 폴링이 없으면 그 사이에 들어온 화면이 "불러오는
    // 중"에 머문 채 스스로 바뀌지 않는다 — 끝난 줄 모르고 새로고침하게 된다.
    refetchInterval: (query) => (query.state.data?.status === 'running' ? 2000 : false),
  })

  const feedback = data?.status === 'done' ? data.feedback : undefined
  if (!feedback) {
    return (
      <ReportEmpty
        status={isError ? 'failed' : data?.status}
        refunded={data?.refunded === true}
        sessions={sessions ?? []}
        current={data?.sessionId}
        onPick={setSessionId}
        onLeave={() => nav('/')}
        onAgain={() => nav('/ready')}
      />
    )
  }

  return (
    <ReportBody
      feedback={feedback}
      interviewId={card.id}
      sessionId={data?.sessionId}
      video={data?.hasVideo ? { startS: data.videoStartS ?? 0 } : null}
      sessions={sessions ?? []}
      onPick={setSessionId}
      onLeave={() => nav('/')}
      onAgain={() => nav('/ready')}
      company={card.company}
      role={card.role}
    />
  )
}

/**
 * 지난 면접 고르기. 판이 둘 이상일 때만 나온다.
 *
 * 같은 준비 데이터로 몇 번이든 면접할 수 있고, 지난번보다 나아졌는지가 이
 * 서비스의 재방문 이유다. 분석이 끝나지 않은 회차는 고를 수 없다 — 눌러 봐야
 * 빈 화면이다.
 *
 * 아무 말 없이 끝난 면접은 여기 오지 않는다. 서버가 이력에서 뺀다.
 */
function SessionPicker({
  sessions,
  current,
  onPick,
}: {
  sessions: InterviewSession[]
  current: string | undefined
  onPick: (id: string | undefined) => void
}) {
  if (sessions.length < 2) return null
  return (
    <div className="mb-[22px] flex flex-wrap items-center gap-2">
      <span className="text-[12px] text-faint">지난 면접</span>
      {sessions.map((session, index) => {
        const active = session.id === current
        return (
          <button
            key={session.id}
            disabled={!session.hasFeedback}
            onClick={() => onPick(session.id)}
            className={`num rounded-full border px-[11px] py-[5px] text-[12px] ${
              active
                ? 'border-ink bg-ink text-white'
                : session.hasFeedback
                  ? 'border-hair-2 text-muted'
                  : 'border-hair-2 text-faintest'
            }`}
          >
            {`${sessions.length - index}회차`}
            {session.score !== null && ` · ${session.score}점`}
            {!session.hasFeedback && ' · 분석 중'}
          </button>
        )
      })}
    </div>
  )
}

/**
 * 결과가 없을 때의 화면.
 *
 * 이유가 다섯이고 할 말이 전부 다르다 — 만드는 중 / 만들다 실패 / 한 마디도
 * 남기지 않음 / 아직 한 번도 안 봄 / 회차는 있는데 결과가 없음. 앞서는 제목 한
 * 줄로 뭉쳐 두었고, 그래서 방금 면접을 마친 사람에게 "아직 면접을 진행하지
 * 않았습니다"라고 했다. 무엇이 일어났는지와 다음에 무엇을 하면 되는지를
 * 한 줄씩만 둔다 — 빈 화면에서 읽히는 분량이 그 정도다.
 *
 * 지난 회차 고르기를 여기에도 둔다. 마지막 회차가 비어 있다고 그 앞의 리포트
 * 까지 막히면, 결과가 있는데도 볼 길이 없는 화면이 된다.
 */
function ReportEmpty({
  status,
  refunded,
  sessions,
  current,
  onPick,
  onLeave,
  onAgain,
}: {
  status: FeedbackStatus['status'] | undefined
  /** 크레딧을 되돌린 사실이 원장에 있는가. 돈 이야기라 참일 때만 말한다. */
  refunded: boolean
  sessions: InterviewSession[]
  current: string | undefined
  onPick: (id: string | undefined) => void
  onLeave: () => void
  onAgain: () => void
}) {
  // absent에는 갈래가 둘 있다. 회차가 하나도 없으면 첫 면접으로 미는 자리이고,
  // 회차는 있는데 결과만 없으면(분석 도중 기록이 끊긴 경우) 그 사실을 말해야
  // 한다 — 회차 칩이 떠 있는데 "본 적이 없습니다"라고 하면 앞뒤가 안 맞는다.
  const first = status === 'absent' && sessions.length === 0
  const copy = {
    silent: {
      title: '답변이 녹음되지 않았습니다',
      body: '다시 시작하기 전에 마이크 테스트로 소리가 잡히는지 확인해 주세요.',
      again: '다시 면접 보기',
    },
    failed: {
      title: '분석 결과를 만들지 못했습니다',
      body: '녹음과 전사는 남아 있습니다. 잠시 뒤 다시 열어 보세요.',
      again: '다시 면접 보기',
    },
    first: {
      title: '면접을 시작해 보세요',
      body: '면접을 마치면 답변마다 점수와 코칭이 만들어집니다.',
      again: '면접 시작하기',
    },
    absent: {
      title: '이 회차의 리포트가 없습니다',
      body: '분석이 끝나기 전에 기록이 끊겼습니다.',
      again: '다시 면접 보기',
    },
    running: {
      title: '답변을 분석하고 있습니다',
      body: '끝나면 이 화면이 저절로 바뀝니다. 창을 닫아도 계속됩니다.',
      again: '',
    },
  }[
    first
      ? 'first'
      : status === 'silent' || status === 'failed' || status === 'absent'
        ? status
        : 'running'
  ]

  return (
    <main className="mx-auto max-w-(--container-report) px-8 pt-10 pb-20 animate-dm-fade">
      <button onClick={onLeave} className="mb-6 text-[13px] text-muted">
        ← 내 면접
      </button>

      <SessionPicker sessions={sessions} current={current} onPick={onPick} />

      <div className="flex flex-col items-center rounded-card border border-line bg-surface px-8 py-[48px] text-center">
        <EmptyMark status={status} first={first} />
        <h1 className="mt-[22px] mb-0 text-[19px] font-bold tracking-[-.02em]">{copy.title}</h1>
        <p className="mt-[11px] mb-0 max-w-[430px] text-[13.5px] leading-[1.8] text-muted">
          {copy.body}
        </p>

        {/* 아무 말도 못 한 면접에서 사용자가 가장 먼저 묻는 것이 크레딧이다.
            되돌린 기록이 원장에 있을 때만 말한다 — 짐작으로 안심시키지 않는다. */}
        {status === 'silent' && refunded && (
          <div className="mt-[18px] rounded-chip border border-accent-line bg-accent-bg px-[13px] py-[7px] text-[12.5px] font-semibold text-accent">
            크레딧은 돌려드렸습니다
          </div>
        )}

        <div className="mt-[26px] flex items-center gap-[10px]">
          <button
            onClick={onLeave}
            className="rounded-control border border-field bg-surface px-[18px] py-[11px] text-[13.5px] font-semibold text-ink"
          >
            내 면접으로
          </button>
          {copy.again && (
            <button
              onClick={onAgain}
              className="rounded-control bg-ink px-[22px] py-[11px] text-[13.5px] font-semibold text-white"
            >
              {copy.again}
            </button>
          )}
        </div>
      </div>
    </main>
  )
}

/**
 * 빈 화면 위의 표식.
 *
 * 무응답에는 면접 화면의 파형을 그대로 쓰되 전부 눕혀 둔다 — 막대가 움직이는
 * 것이 "듣고 있다"였으니, 눕은 막대는 설명 없이도 "아무것도 들어오지 않았다"로
 * 읽힌다. 규격은 Interview.tsx의 파형과 같다(3px 폭 16개, 간격 3px).
 */
function EmptyMark({
  status,
  first,
}: {
  status: FeedbackStatus['status'] | undefined
  /** 판이 하나도 없는 첫 면접인가. absent의 두 갈래를 가른다. */
  first: boolean
}) {
  if (status === 'silent') {
    return (
      <div className="flex items-center" style={{ gap: 3, height: 38 }}>
        {Array.from({ length: 16 }, (_, i) => (
          <div key={i} className="bg-line" style={{ width: 3, height: 2 }} />
        ))}
      </div>
    )
  }
  if (status === 'failed') {
    return (
      <span
        className="flex items-center justify-center rounded-full border border-line-2 text-[15px] font-bold text-faint"
        style={{ width: 38, height: 38 }}
      >
        !
      </span>
    )
  }
  if (status === 'absent') {
    return (
      <span
        className={`flex items-center justify-center rounded-full ${
          first ? 'border border-accent-line bg-accent-bg' : 'border border-line-2'
        }`}
        style={{ width: 38, height: 38 }}
      >
        {first ? <AccentDot size={7} /> : <span className="text-[15px] text-faintest">—</span>}
      </span>
    )
  }
  return <Spinner size={26} />
}

function ReportBody({
  feedback,
  interviewId,
  sessionId,
  sessions,
  video,
  company,
  role,
  onPick,
  onLeave,
  onAgain,
}: {
  feedback: Feedback
  interviewId: string
  sessionId: string | undefined
  sessions: InterviewSession[]
  /** 웹캠 녹화가 있으면 그 원점. 없으면 null이고 소리만 다시 듣는다. */
  video: { startS: number } | null
  company: string
  role: string
  onPick: (id: string | undefined) => void
  onLeave: () => void
  onAgain: () => void
}) {
  const [openQ, setOpenQ] = useState(0)
  const { coaching, voice } = feedback
  const minutes = Math.floor(feedback.durationS / 60)
  const seconds = Math.round(feedback.durationS % 60)

  return (
    <main className="mx-auto max-w-(--container-report) px-8 pt-10 pb-[90px] animate-dm-fade">
      <div className="mb-[30px] flex items-center gap-[14px]">
        <button onClick={onLeave} className="text-[13px] text-muted">
          ← 내 면접
        </button>
      </div>

      <SessionPicker sessions={sessions} current={sessionId} onPick={onPick} />

      {/* 헤더 */}
      <div className="flex items-start gap-[34px] border-b border-line pb-[30px]">
        <div className="flex flex-1 flex-col gap-[9px]">
          <div className="text-[12.5px] text-faint">
            {minutes}분 {seconds}초 · 답변 {coaching.answers.length}개
          </div>
          <h1 className="m-0 text-[25px] font-bold tracking-[-.03em]">
            {company} · {role}
          </h1>
          <p className="mt-[6px] mb-0 max-w-[520px] text-[14px] leading-[1.7] text-body-2">
            {coaching.summary}
          </p>
        </div>
        {/* 점수는 답변 점수의 평균입니다 — 아래 답변별 점수와 반드시 맞습니다. */}
        <div className="flex flex-col items-end gap-[4px]">
          <div className="flex items-baseline gap-[4px]">
            <span className="num text-[52px] leading-none font-bold tracking-[-.05em]">
              {coaching.score ?? '—'}
            </span>
            <span className="text-[15px] text-faint">/ 100</span>
          </div>
          <span className="text-[12px] text-faintest">답변 점수의 평균</span>
        </div>
      </div>

      {voice && (
        <section className="border-b border-line py-[30px]">
          <div className="mb-[18px]">
            <SectionLabel>음성 지표</SectionLabel>
          </div>
          {/* 3열 두 줄 — 핸드오프 §10의 배치입니다. 값만 두지 않고 권장 범위와
              판정을 함께 보여줘야 숫자가 좋은지 나쁜지 읽힙니다.

              범위는 일반 대화의 관찰값보다 조금 좁게 잡았습니다. 면접은 평소
              대화보다 또렷해야 하는 자리라서입니다. 근거는 카드마다 아래 주석에
              적었습니다 — 지어낸 숫자가 아니어야 판정을 신뢰할 수 있습니다. */}
          <div className="grid grid-cols-3 gap-3">
            {/* 한국어 뉴스 아나운서가 353~357 음절/분(말소리와 음성과학).
                또렷하게 들리는 상한이 그쯤이라 360을 위로 두고, 아래는 그보다
                한참 느리면 답답하게 들리는 선에서 280으로 잡았습니다. */}
            <Metric
              label="말하기 속도"
              value={Math.round(voice.syllablesPerMinute)}
              unit="음절/분"
              low={280}
              high={360}
              range="280~360 권장"
            />
            {/* 면접 코칭의 통념(1~2분)보다 아래를 넉넉히 열었습니다. 30초면
                근거를 갖춘 답을 할 수 있고, 90초를 넘으면 듣는 쪽이 놓칩니다. */}
            <Metric
              label="답변 길이"
              value={Math.round(voice.meanAnswerS)}
              unit="초 평균"
              low={30}
              high={90}
              range="30~90초 권장"
            />
            {/* 보통 화자가 분당 5회, 이상적으로는 1회라고 봅니다(Quantified
                Communications). 그 사이에서 조금 빡빡하게 3회로 잡았습니다. */}
            <Metric
              label="필러 워드"
              value={
                voice.spokenS > 0
                  ? Math.round((coaching.fillers / voice.spokenS) * 60 * 10) / 10
                  : 0
              }
              unit="회/분"
              high={3}
              range="분당 3회 이하 권장"
            />
            {/* 일상 대화는 0.2초 안에 답하고 0.7초를 넘으면 머뭇거림으로 읽힙니다
                (Stivers et al., PNAS 2009). 면접은 생각할 시간이 필요한 자리라
                그 기준을 그대로 쓰지 않고 3초로 넉넉히 뒀습니다. */}
            <Metric
              label="답변까지"
              value={voice.meanStartDelayS === null ? null : Math.round(voice.meanStartDelayS * 10) / 10}
              unit="초"
              high={3}
              range="3초 이내 권장"
            />
            {/* 여기만 외부 근거가 없습니다. 서버가 0.8초 이상 비었을 때만
                멈춤으로 세는데(숨과 어절 경계를 빼기 위해서입니다), 그러면
                "자연스러운 발화의 침묵 23.9~31.9%"(Journal of Psycholinguistic
                Research) 같은 관찰값과 재는 대상이 달라 그대로 쓸 수 없습니다.
                실측 면접 한 판이 5.7%라 그 위로 잠정선을 뒀습니다 — 면접이
                쌓이면 분포를 보고 다시 정합니다(목소리 흔들림과 같습니다). */}
            <Metric
              label="답변 중 멈춤"
              value={Math.round(voice.pauseRatio * 100)}
              unit="%"
              high={12}
              range="12% 이하 권장"
            />
            {/* 이 값만 외부 근거가 없습니다. 우리 녹음에서 관찰한 범위로 잠정
                선을 뒀습니다 — 면접이 쌓이면 분포를 보고 다시 정합니다. */}
            <Metric
              label="목소리 흔들림"
              value={Math.round(voice.loudnessVariation * 100) / 100}
              unit=""
              high={0.45}
              range="0.45 이하 권장"
            />
          </div>
        </section>
      )}

      {feedback.gaze && <Delivery gaze={feedback.gaze} />}

      {(coaching.strengths.length > 0 || coaching.improvements.length > 0) && (
        <section className="border-b border-line py-[30px]">
          <div className="mb-[18px]">
            <SectionLabel>내용 평가</SectionLabel>
          </div>
          <div className="grid grid-cols-2 gap-[14px]">
            <div className="flex flex-col gap-3">
              <div className="text-[13px] font-bold text-positive">잘한 점</div>
              {coaching.strengths.map((text) => (
                <div key={text} className="flex gap-[8px]">
                  <span className="text-[12px] text-positive">✓</span>
                  <span className="text-[13.5px] leading-[1.65] text-body-2">{text}</span>
                </div>
              ))}
            </div>
            <div className="flex flex-col gap-3">
              <div className="text-[13px] font-bold text-accent">보완할 점</div>
              {coaching.improvements.map((text) => (
                <div key={text} className="flex gap-[8px]">
                  <span className="text-[12px] text-accent">→</span>
                  <span className="text-[13.5px] leading-[1.65] text-body-2">{text}</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      <section className="py-[30px]">
        <div className="mb-[18px]">
          <SectionLabel>답변별 피드백</SectionLabel>
        </div>
        <div className="flex flex-col gap-[10px]">
          {coaching.answers.map((answer, index) => {
            const open = openQ === index
            // 음성 구간과 코칭은 같은 순서로 나온다 — 둘 다 면접 순서다.
            const span = voice?.answers[index]
            return (
              <div
                key={index}
                className="rounded-card bg-surface"
                style={{ border: `1px solid ${open ? 'var(--color-field)' : 'var(--color-line)'}` }}
              >
                <div
                  onClick={() => setOpenQ(open ? -1 : index)}
                  className="flex cursor-pointer items-center gap-[13px] px-[18px] py-[15px]"
                >
                  <span className="num w-[22px] text-[11.5px] font-semibold text-faintest">
                    Q{index + 1}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-[13.5px] font-semibold">
                    {open ? '' : answer.question}
                  </span>
                  {span && (
                    <span className="num text-[11.5px] text-faintest">
                      {(span.endS - span.startS).toFixed(1)}초
                    </span>
                  )}
                  <span className="num w-[28px] text-right text-[15px] font-bold">
                    {answer.score}
                  </span>
                  <span className="w-[12px] text-[11px] text-faintest">{open ? '▲' : '▼'}</span>
                </div>

                {open && (
                  <div className="flex animate-dm-fade flex-col gap-4 px-[18px] pt-[4px] pb-5">
                    <div className="border-t border-hair pt-4 text-[15px] leading-[1.6] font-semibold">
                      {answer.question}
                    </div>

                    {span && (
                      /* 전사와 영상을 나란히 둔다. 위아래로 쌓으면 "내가 이 말을
                         할 때 어떻게 보였나"를 한눈에 맞춰 볼 수 없다. */
                      <div className={video ? 'grid grid-cols-[1fr_248px] gap-[14px]' : ''}>
                        <div className="flex min-w-0 flex-col gap-[6px] rounded-control bg-surface-2 px-[14px] py-[12px]">
                          <span className="num text-[11.5px] text-faint">
                            ({formatAt(span.startS)})
                          </span>
                          <p className="m-0 text-[13.5px] leading-[1.85] text-body-2">
                            {span.text}
                          </p>
                          <span className="text-[11.5px] text-faintest">
                            {[
                              span.pauses > 0 && `말이 ${span.pauses}번 끊겼습니다`,
                              answer.fillers.length > 0 &&
                                `필러 워드 ${answer.fillers.join(' · ')}`,
                            ]
                              .filter(Boolean)
                              .join('  ·  ')}
                          </span>
                        </div>

                        {video ? (
                          <Playback
                            src={videoUrl(interviewId, sessionId)}
                            /* 영상의 0초는 녹화가 시작된 순간이라 원점이 다르다.
                               빼 주지 않으면 답변마다 몇 초씩 어긋난다. */
                            startS={Math.max(0, span.startS - video.startS - PAD_BEFORE_S)}
                            endS={Math.max(0, span.endS - video.startS + PAD_AFTER_S)}
                            video
                          />
                        ) : (
                          <Playback
                            src={audioUrl(interviewId, sessionId)}
                            startS={Math.max(0, span.startS - PAD_BEFORE_S)}
                            endS={span.endS + PAD_AFTER_S}
                          />
                        )}
                      </div>
                    )}

                    {answer.strength && (
                      <div className="border-l-2 border-positive pl-[15px]">
                        <div className="mb-[6px] text-[11.5px] font-bold text-positive">
                          잘한 점
                        </div>
                        <p className="m-0 text-[13.5px] leading-[1.8] text-body">
                          {answer.strength}
                        </p>
                      </div>
                    )}

                    <div className="border-l-2 border-line-2 pl-[15px]">
                      <div className="mb-[6px] text-[11.5px] font-bold text-muted">
                        더 듣고 싶었던 것
                      </div>
                      <p className="m-0 text-[13.5px] leading-[1.8] text-body">{answer.gap}</p>
                    </div>

                    <div className="border-l-2 border-accent pl-[15px]">
                      <div className="mb-[6px] text-[11.5px] font-bold text-accent">
                        이렇게 바꿔보세요
                      </div>
                      <p className="m-0 text-[13.5px] leading-[1.8] text-body">
                        {answer.suggestion}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </section>

      <div className="flex items-center">
        <button onClick={onLeave} className="text-[13px] text-muted">
          내 면접으로
        </button>
        <div className="flex-1" />
        <button
          onClick={onAgain}
          className="rounded-control bg-ink px-7 py-[13px] text-[14px] font-semibold text-white"
        >
          이 회사로 다시 면접 보기
        </button>
      </div>
    </main>
  )
}

/**
 * 재생할 때 답변 앞뒤로 물리는 시간.
 *
 * 구간의 시작은 **소리가 문턱을 넘은 첫 프레임**입니다(eval/voice.py의
 * `speech_spans`). "안녕하세요"의 첫 음절처럼 조용하게 시작하는 말은 그 문턱
 * 아래로 깔려서, 그대로 자르면 "ㄴ녕하세요"로 들립니다. 실측에서 0.2초쯤
 * 잘렸습니다.
 *
 * 구간 자체는 손대지 않습니다 — 지표는 **소리가 난 시간**을 재는 것이 맞고,
 * 여기서 넓히면 말하기 속도와 멈춤 비율이 함께 틀어집니다. 듣기 좋으라고
 * 재생에서만 물립니다.
 */
const PAD_BEFORE_S = 0.35
const PAD_AFTER_S = 0.3

/** 초 → "02:10". 답변이 면접의 어느 지점인지 한눈에 보이게 합니다. */
function formatAt(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

/**
 * 지표 카드 하나.
 *
 * 숫자만 두면 좋은지 나쁜지 읽히지 않습니다. 권장 범위를 함께 보여주고,
 * 그 범위 안이면 초록·밖이면 강조색으로 판정을 답니다. 막대는 범위 대비
 * 위치라 한눈에 어느 쪽으로 벗어났는지 보입니다.
 *
 * 잴 수 없는 값(`value === null`)은 판정하지 않습니다 — 0으로 채우면
 * "바로 대답했다"는 거짓말이 됩니다.
 */
function Metric({
  label,
  value,
  unit,
  low,
  high,
  range,
}: {
  label: string
  value: number | null
  unit: string
  low?: number
  high?: number
  range: string
}) {
  if (value === null) {
    return (
      <div className="flex flex-col gap-[7px] rounded-card border border-line bg-surface p-4">
        <span className="text-[12.5px] text-muted">{label}</span>
        <span className="num text-[23px] font-bold tracking-[-.03em] text-faintest">—</span>
        <div className="bg-line-3" style={{ height: 3 }} />
        <span className="text-[11.5px] text-faintest">이 면접에서는 재지 못했습니다</span>
      </div>
    )
  }

  const tooLow = low !== undefined && value < low
  const tooHigh = high !== undefined && value > high
  const ok = !tooLow && !tooHigh
  const color = ok ? 'var(--color-positive)' : 'var(--color-accent)'
  const verdict = ok ? '적정' : tooHigh ? '다소 많음' : '다소 적음'
  // 막대는 권장 상한 대비 위치. 하한만 있는 지표는 상한을 그 두 배로 본다.
  const ceiling = high ?? (low ?? 1) * 2
  const filled = Math.min(100, Math.max(4, (value / ceiling) * 100))

  return (
    <div className="flex flex-col gap-[7px] rounded-card border border-line bg-surface p-4">
      <span className="text-[12.5px] text-muted">{label}</span>
      <div className="flex items-baseline gap-[4px]">
        <span className="num text-[23px] font-bold tracking-[-.03em]">{value}</span>
        {unit && <span className="text-[12px] text-faint">{unit}</span>}
      </div>
      <div className="bg-line-3" style={{ height: 3 }}>
        <div className="h-full" style={{ width: `${filled}%`, background: color }} />
      </div>
      <div className="flex items-center gap-[6px]">
        <span className="text-[11.5px] font-semibold" style={{ color }}>
          {verdict}
        </span>
        <span className="text-[11.5px] text-faintest">{range}</span>
      </div>
    </div>
  )
}

/**
 * 답변 한 구간만 다시 보기·듣기.
 *
 * 녹음은 면접 전체가 한 파일이라, 구간의 시작으로 옮겨 재생하고 끝에서
 * 멈춘다. 서버가 Range 요청을 받으므로 20분짜리를 통째로 받지 않는다.
 *
 * 웹캠 녹화가 있으면 그쪽을 쓴다. 녹화에 마이크 소리가 같이 담겨 있어서
 * 요소 하나로 끝난다 — 영상과 오디오를 따로 맞출 일이 없다.
 */
function Playback({
  src,
  startS,
  endS,
  video: isVideo = false,
}: {
  src: string
  startS: number
  endS: number
  video?: boolean
}) {
  const audio = useRef<HTMLVideoElement>(null)
  const [playing, setPlaying] = useState(false)
  const [at, setAt] = useState(startS)

  // 구간 끝에서 멈춘다. timeupdate는 250ms쯤마다 오므로 조금 지나쳐 멈춘다.
  useEffect(() => {
    const element = audio.current
    if (!element) return
    const onTime = () => {
      setAt(element.currentTime)
      if (element.currentTime >= endS) {
        element.pause()
        setPlaying(false)
      }
    }
    element.addEventListener('timeupdate', onTime)
    return () => element.removeEventListener('timeupdate', onTime)
  }, [endS])

  const toggle = () => {
    const element = audio.current
    if (!element) return
    if (playing) {
      element.pause()
      setPlaying(false)
      return
    }
    // 늘 구간 앞에서 다시 시작한다 — 끝까지 들은 뒤 또 누르는 것이 보통이다.
    if (element.currentTime < startS || element.currentTime >= endS - 0.1) {
      element.currentTime = startS
    }
    void element.play()
    setPlaying(true)
  }

  const total = endS - startS
  const done = Math.min(1, Math.max(0, (at - startS) / total))

  if (isVideo) {
    return (
      <div className="flex w-full flex-col gap-[7px]">
        {/* 녹화본은 거울을 쓰지 않는다 — 면접관이 본 방향 그대로여야
            "내가 어떻게 보였는가"를 판단할 수 있다. */}
        <video
          ref={audio}
          src={src}
          preload="metadata"
          className="w-full rounded-control border border-line-2 bg-surface-2 object-cover"
          style={{ aspectRatio: '4 / 3' }}
        />
        <div className="flex items-center gap-3">
          <button
            onClick={toggle}
            className="flex items-center justify-center rounded-full bg-ink text-white"
            style={{ width: 26, height: 26, fontSize: 9 }}
          >
            {playing ? '❚❚' : '▶'}
          </button>
          <div className="flex-1 bg-line-3" style={{ height: 3 }}>
            <div className="h-full bg-accent" style={{ width: `${done * 100}%` }} />
          </div>
          <span className="num text-[11.5px] text-faint">{total.toFixed(1)}초</span>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-3 rounded-control border border-line-2 bg-surface-2 px-[13px] py-[10px]">
      <video ref={audio} src={src} preload="none" className="hidden" />
      <button
        onClick={toggle}
        className="flex items-center justify-center rounded-full bg-ink text-white"
        style={{ width: 26, height: 26, fontSize: 9 }}
      >
        {playing ? '❚❚' : '▶'}
      </button>
      <div className="flex-1 bg-line-3" style={{ height: 3 }}>
        <div className="h-full bg-accent" style={{ width: `${done * 100}%` }} />
      </div>
      <span className="num text-[11.5px] text-faint">{total.toFixed(1)}초</span>
      <span className="text-[11.5px] text-muted">내 답변</span>
    </div>
  )
}
