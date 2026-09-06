// Recreation of web/src/screens/Report.tsx + Delivery.tsx + video/expression.ts. Score = mean of answer scores; no stage scores, no percentile.
const IMPRESSIONS = [{ key: 'confident', label: '자신감' }, { key: 'focused', label: '집중' }, { key: 'tense', label: '긴장' }, { key: 'flustered', label: '당황' }];
const TICK_COLORS = { confident: 'var(--color-accent)', tense: 'color-mix(in srgb, var(--color-accent) 55%, var(--color-surface))', flustered: 'var(--color-ink)' };
const PAD_BEFORE_S = 0.35, PAD_AFTER_S = 0.3;
const fmtAt = s => { const t = Math.max(0, Math.round(s)); return String(Math.floor(t / 60)).padStart(2, '0') + ':' + String(t % 60).padStart(2, '0'); };

/* 시안 값 — 서버 feedback.json의 모양. 종합 = 답변 점수 평균(84·71·88·77 → 80). */
const FEEDBACK = {
  durationS: 1092,
  coaching: {
    score: 80, fillers: 16,
    summary: '직무 경험은 사실 관계가 분명하고 구체적이었습니다. 다만 회사와 직무를 연결해 설명하는 대목에서 준비가 덜 된 인상을 주었습니다.',
    strengths: ['경험을 말할 때 문제 인식, 조치, 결과 순서가 지켜졌습니다.', '모르는 것을 아는 척하지 않았습니다.', '목소리가 처음부터 끝까지 흔들리지 않았습니다.'],
    improvements: ['회사를 조사한 흔적이 답변에 드러나지 않았습니다.', '네 답변 중 둘이 같은 프로젝트를 사례로 썼습니다.', '시선이 오른쪽으로 자주 갔습니다. 카메라 옆 메모를 치우고 다시 연습해 보세요.'],
    answers: [
      { question: '먼저 간단히 자기소개 부탁드립니다.', score: 84, fillers: ['음'], strength: '실제 반영된 결과를 언급해 검증 가능한 인상을 남겼습니다.', gap: '세 프로젝트 중 어느 것을 왜 골라 말했는지가 드러나지 않았습니다.', suggestion: '전공과 프로젝트 횟수를 나열하는 대신, 발주에 실제 반영된 그 한 가지를 앞에 두고 시작하세요. "제 제안이 실제 발주 주기에 반영된 경험이 있습니다"로 열면 첫 문장에서 이미 검증된 사람이라는 인상을 줍니다.' },
      { question: '여러 회사 중 저희 누리테크에 지원하신 이유가 무엇인가요?', score: 71, fillers: ['어', '어'], strength: '', gap: '회사 이름을 바꿔도 성립하는 문장들입니다. 이 회사여야 하는 이유가 없습니다.', suggestion: '올해 공개된 파트너 정산 서비스처럼 이름을 댈 수 있는 사실을 하나 넣고, 그것이 본인 경험과 어디서 만나는지까지 이어가세요.' },
      { question: '지원서에 적으신 물류 데이터 분석 프로젝트에서 본인이 맡은 역할을 설명해 주세요.', score: 88, fillers: [], strength: '문제 인식, 조치, 결과가 순서대로 나왔습니다.', gap: '결과의 크기입니다. 재고가 몇 % 줄었는지 같은 숫자가 없습니다.', suggestion: '마지막 문장에 숫자 하나를 붙이세요. 그 제안이 몇 개 매장에 적용되었는지도 좋습니다.' },
      { question: '그 프로젝트에서 가장 어려웠던 판단은 무엇이었고, 어떤 근거로 결정하셨나요?', score: 77, fillers: ['음', '그'], strength: '', gap: '판단의 재료가 빠졌습니다. 비교 자료에서 어떤 차이가 드러났는지가 없습니다.', suggestion: '왜 소분류가 맞다고 확신했는지를 한 문장으로 넣으세요.' },
    ],
  },
  voice: {
    syllablesPerMinute: 312, meanAnswerS: 70, spokenS: 280, meanStartDelayS: 2.4, pauseRatio: 0.08, loudnessVariation: 0.31,
    answers: [
      { startS: 12, endS: 70, pauses: 1, text: '네, 저는 데이터를 근거로 판단하는 기획자가 되고 싶은 김서연입니다. 학부에서 산업공학을 전공하면서 물류 데이터를 다루는 프로젝트를 세 번 진행했고, 그중 하나는 실제 교내 매점 발주에 반영되었습니다. 음… 이런 경험을 바탕으로 누리테크에서도 현장 데이터를 읽는 기획자가 되고 싶습니다.' },
      { startS: 84, endS: 150, pauses: 3, text: '어… 누리테크는 이 분야에서 데이터를 가장 잘 활용하는 회사라고 생각했습니다. 성장하는 회사이고, 제가 배울 것이 많을 것 같아서 지원하게 되었습니다. 어… 그리고 사내 문화도 수평적이라고 들었습니다.' },
      { startS: 162, endS: 246, pauses: 0, text: '3개월치 출고 데이터를 정리하는 일을 제가 맡았습니다. 기존 분류 기준이 품목 대분류 단위여서 회전율이 낮은 품목이 가려지는 문제가 있었고, 그래서 소분류 단위로 다시 나눴습니다.' },
      { startS: 260, endS: 332, pauses: 2, text: '분류 기준을 바꾸는 게 가장 어려웠습니다. 팀원들은 기존 기준을 유지하자고 했는데, 저는 바꿔야 한다고 생각했습니다.' },
    ],
  },
  gaze: { steady: 0.74, seconds: 640, cells: [0, 0.06, 0, 0.09, 0.74, 0.11, 0, 0, 0] },
  expression: {
    frames: 210, impressions: { confident: 0.21, focused: 0.62, tense: 0.13, flustered: 0.04 },
    series: Array.from({ length: 64 }, (_, i) => ([9, 10, 27, 28, 29, 41].includes(i) ? 'tense' : [30, 31].includes(i) ? 'flustered' : [50, 51, 52, 58].includes(i) ? 'confident' : 'focused')),
    answers: [{ frames: 19, impressions: { focused: 0.6, confident: 0.3, tense: 0.1 } }, { frames: 22, impressions: { focused: 0.4, tense: 0.5, flustered: 0.1 } }, { frames: 28, impressions: { focused: 0.5, confident: 0.5 } }, { frames: 24, impressions: { focused: 0.55, tense: 0.3, flustered: 0.15 } }],
  },
};
const SESSIONS = [{ id: 's2', score: 80, hasFeedback: true }, { id: 's1', score: 74, hasFeedback: true }];

function SessionPicker({ sessions, current, onPick }) {
  if (!sessions || sessions.length < 2) return null;
  return (
    <div style={{ marginBottom: 22, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 12, color: 'var(--color-faint)' }}>지난 면접</span>
      {sessions.map((s, i) => { const active = s.id === current; return (
        <button key={s.id} disabled={!s.hasFeedback} onClick={() => onPick(s.id)} className="num" style={{ borderRadius: 9999, border: '1px solid ' + (active ? 'var(--color-ink)' : 'var(--color-hair-2)'), background: active ? 'var(--color-ink)' : 'transparent', color: active ? '#fff' : s.hasFeedback ? 'var(--color-muted)' : 'var(--color-faintest)', padding: '5px 11px', fontSize: 12, cursor: s.hasFeedback ? 'pointer' : 'default' }}>
          {sessions.length - i}회차{s.score !== null && s.score !== undefined ? ' · ' + s.score + '점' : ''}{!s.hasFeedback ? ' · 분석 중' : ''}
        </button>); })}
    </div>
  );
}

/** 지표 카드. compact = 랜딩 리포트 조각용. value === null이면 판정하지 않는다. */
function Metric({ label, value, unit, low, high, range, compact = false }) {
  const box = compact ? { display: 'flex', flexDirection: 'column', gap: 5, borderRadius: 'var(--radius-card)', border: '1px solid var(--color-line)', background: 'var(--color-surface-2)', padding: 12 } : { display: 'flex', flexDirection: 'column', gap: 7, borderRadius: 'var(--radius-card)', border: '1px solid var(--color-line)', background: 'var(--color-surface)', padding: 16 };
  const labelS = compact ? { fontSize: 11, whiteSpace: 'nowrap', color: 'var(--color-muted)' } : { fontSize: 12.5, color: 'var(--color-muted)' };
  const valueS = compact ? { fontSize: 19, lineHeight: 1, fontWeight: 700, letterSpacing: '-.03em' } : { fontSize: 23, fontWeight: 700, letterSpacing: '-.03em' };
  const unitS = { fontSize: compact ? 10.5 : 12, color: 'var(--color-faint)' };
  const note = compact ? 10.5 : 11.5;
  if (value === null) return (
    <div style={box}><span style={labelS}>{label}</span><span className="num" style={{ ...valueS, color: 'var(--color-faintest)' }}>—</span><div style={{ height: 3, background: 'var(--color-line-3)' }} /><span style={{ fontSize: note, color: 'var(--color-faintest)' }}>이 면접에서는 재지 못했습니다</span></div>
  );
  const tooLow = low !== undefined && value < low, tooHigh = high !== undefined && value > high, ok = !tooLow && !tooHigh;
  const color = ok ? 'var(--color-positive)' : 'var(--color-accent)';
  const ceiling = high ?? (low ?? 1) * 2, filled = Math.min(100, Math.max(4, (value / ceiling) * 100));
  return (
    <div style={box}>
      <span style={labelS}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: compact ? 3 : 4 }}><span className="num" style={valueS}>{value}</span>{unit && <span style={unitS}>{unit}</span>}</div>
      <div style={{ height: 3, background: 'var(--color-line-3)' }}><div style={{ height: '100%', width: filled + '%', background: color }} /></div>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', columnGap: 6, rowGap: 2 }}><span style={{ fontSize: note, fontWeight: 600, whiteSpace: 'nowrap', color }}>{ok ? '적정' : tooHigh ? '다소 많음' : '다소 적음'}</span><span style={{ fontSize: note, whiteSpace: 'nowrap', color: 'var(--color-faintest)' }}>{range}</span></div>
    </div>
  );
}

function Playback({ startS, endS, video = false }) {
  const [playing, setPlaying] = React.useState(false);
  const [at, setAt] = React.useState(startS);
  React.useEffect(() => { if (!playing) return; const t = setInterval(() => setAt(a => { const n = a + 0.25; if (n >= endS) { setPlaying(false); return endS; } return n; }), 250); return () => clearInterval(t); }, [playing, endS]);
  const toggle = () => { if (playing) { setPlaying(false); return; } if (at >= endS - 0.1) setAt(startS); setPlaying(true); };
  const total = endS - startS, done = Math.min(1, Math.max(0, (at - startS) / total));
  const Btn = <button onClick={toggle} style={{ display: 'flex', width: 26, height: 26, alignItems: 'center', justifyContent: 'center', borderRadius: '50%', background: 'var(--color-ink)', color: '#fff', }}>{playing ? <Icon name="pause" size={12} color="#fff" /> : <Icon name="play" size={12} color="#fff" />}</button>;
  const Bar = <div style={{ flex: 1, height: 3, background: 'var(--color-line-3)' }}><div style={{ height: '100%', width: done * 100 + '%', background: 'var(--color-accent)' }} /></div>;
  if (video) return (
    <div style={{ display: 'flex', width: '100%', flexDirection: 'column', gap: 7 }}>
      <div style={{ width: '100%', aspectRatio: '4 / 3', borderRadius: 'var(--radius-control)', border: '1px solid var(--color-line-2)', background: 'var(--color-surface-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: 'var(--color-faintest)' }}>녹화본 · 반전 없음</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>{Btn}{Bar}<span className="num" style={{ fontSize: 11.5, color: 'var(--color-faint)' }}>{total.toFixed(1)}초</span></div>
    </div>
  );
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, borderRadius: 'var(--radius-control)', border: '1px solid var(--color-line-2)', background: 'var(--color-surface-2)', padding: '10px 13px' }}>{Btn}{Bar}<span className="num" style={{ fontSize: 11.5, color: 'var(--color-faint)' }}>{total.toFixed(1)}초</span><span style={{ fontSize: 11.5, color: 'var(--color-muted)' }}>내 답변</span></div>
  );
}

/* ── 전달력 (Delivery.tsx) ── */
function dominantAway(cells) { let best = -1, bestShare = 0; cells.forEach((s, i) => { if (i === 4 || s <= bestShare) return; best = i; bestShare = s; }); if (best < 0 || bestShare < 0.08) return null; return ['왼쪽 위쪽', '위쪽', '오른쪽 위쪽', '왼쫁', '', '오른쪽', '왼쪽 아래쪽', '아래쪽', '오른쪽 아래쪽'][best]; }
function gazeVerdict(g) { const away = dominantAway(g.cells), st = g.steady; if (st >= 0.7) return away ? `정면을 잘 유지했습니다. 가끔 ${away}으로 시선이 갔습니다.` : '정면을 안정적으로 유지했습니다.'; if (st >= 0.4) return away ? `정면 응시가 간헐적으로 흔들리고 ${away}으로 시선이 자주 갔습니다.` : '정면 응시가 간헐적으로 흔들렸습니다.'; return away ? `시선이 정면에 머문 시간이 짧고 ${away}으로 자주 향했습니다.` : '시선이 정면에 머문 시간이 짧았습니다.'; }
const dCard = { display: 'flex', height: '100%', flexDirection: 'column', gap: 14, borderRadius: 'var(--radius-card)', border: '1px solid var(--color-line)', background: 'var(--color-surface)', padding: 18, boxSizing: 'border-box' };
function GazeCard({ gaze }) {
  if (!gaze) return <div style={{ ...dCard, gap: 10 }}><span style={{ fontSize: 13.5, fontWeight: 700 }}>시선 처리</span><p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.7, color: 'var(--color-muted)' }}>시선 기록이 없습니다. 카메라를 켜고 진행하면 다음 면접부터 여기에 시선 분석이 담깁니다.</p></div>;
  const thin = gaze.seconds < 30;
  return (
    <div style={dCard}>
      <div style={{ display: 'flex', alignItems: 'baseline' }}><span style={{ fontSize: 13.5, fontWeight: 700 }}>시선 처리</span><div style={{ flex: 1 }} /><span className="num" style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-accent)' }}>정면 {Math.round(gaze.steady * 100)}%</span></div>
      {thin && <p style={{ margin: 0, fontSize: 12, color: 'var(--color-accent)' }}>얼굴이 보인 시간이 {gaze.seconds}초뿐이라 비율은 참고만 해 주세요.</p>}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
        {gaze.cells.map((share, i) => (
          <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 52, borderRadius: 'var(--radius-chip)', background: share > 0 ? `color-mix(in srgb, var(--color-accent) ${Math.min(100, share * 130)}%, var(--color-surface-2))` : 'var(--color-surface-2)', border: '1px solid ' + (i === 4 ? 'var(--color-accent-line)' : 'var(--color-hair-2)') }}>
            <span className="num" style={{ fontSize: 12.5, fontWeight: 600, color: share > 0.4 ? '#fff' : 'var(--color-muted)' }}>{(share * 100).toFixed(1)}%</span>
            {i === 4 && <span style={{ fontSize: 10.5, color: share > 0.4 ? 'rgba(255,255,255,.8)' : 'var(--color-faint)' }}>정면</span>}
          </div>
        ))}
      </div>
      <span style={{ marginTop: 'auto', fontSize: 12, lineHeight: 1.65, color: 'var(--color-body-2)' }}>{gazeVerdict(gaze)}</span>
    </div>
  );
}
function ExpressionCard({ expression }) {
  if (!expression) return <div style={{ ...dCard, gap: 10 }}><span style={{ fontSize: 13.5, fontWeight: 700 }}>표정</span><p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.7, color: 'var(--color-muted)' }}>표정 판독을 만들지 못했습니다. 카메라를 켜고 진행했다면 다음 리포트부터 담깁니다.</p></div>;
  const thin = expression.frames < 10, series = expression.series || [], moments = series.filter(k => k !== 'focused');
  return (
    <div style={dCard}>
      <span style={{ fontSize: 13.5, fontWeight: 700 }}>표정</span>
      {thin && <p style={{ margin: 0, fontSize: 12, color: 'var(--color-accent)' }}>스냅샷이 {expression.frames}장뿐이라 비율은 참고만 해 주세요.</p>}
      <div style={{ display: 'flex', flex: 1, flexDirection: 'column', justifyContent: 'space-between', padding: '2px 0' }}>
        {IMPRESSIONS.map(im => { const share = expression.impressions[im.key] ?? 0; return (
          <div key={im.key} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ width: 42, flexShrink: 0, fontSize: 12.5, color: 'var(--color-body-2)' }}>{im.label}</span>
            <div style={{ height: 7, flex: 1, borderRadius: 'var(--radius-chip)', background: 'var(--color-hair-2)' }}><div style={{ height: '100%', borderRadius: 'var(--radius-chip)', width: share * 100 + '%', background: 'var(--color-accent)' }} /></div>
            <span className="num" style={{ width: 42, flexShrink: 0, textAlign: 'right', fontSize: 12.5, fontWeight: 600 }}>{(share * 100).toFixed(1)}%</span>
          </div>); })}
      </div>
      {series.length > 0 && moments.length === 0 && <p style={{ margin: 0, fontSize: 12, lineHeight: 1.65, color: 'var(--color-faint)' }}>긴장·당황으로 기운 구간 없이 집중된 흐름이 유지됐습니다.</p>}
      {series.length > 0 && moments.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 10, fontSize: 10.5, color: 'var(--color-faint)' }}>
            {IMPRESSIONS.filter(im => im.key !== 'focused' && moments.includes(im.key)).map(im => <span key={im.key} style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: TICK_COLORS[im.key] }} />{im.label}</span>)}
          </div>
          <div style={{ display: 'flex', overflow: 'hidden', borderRadius: 'var(--radius-chip)', background: 'var(--color-hair-2)', height: 12 }}>{series.map((k, i) => <span key={i} style={{ flex: 1, background: k !== 'focused' ? (TICK_COLORS[k] || 'transparent') : 'transparent' }} />)}</div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 10.5, color: 'var(--color-faintest)' }}><span>면접 시작</span><span>종료</span></div>
        </div>
      )}
    </div>
  );
}
function Delivery({ gaze, expression }) {
  return (
    <section style={{ borderBottom: '1px solid var(--color-line)', padding: '30px 0' }}>
      <div style={{ marginBottom: 18 }}><SectionLabel>전달력</SectionLabel></div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}><GazeCard gaze={gaze} /><ExpressionCard expression={expression} /></div>
    </section>
  );
}

/* ── 빈 리포트 다섯 상태 ── */
function EmptyMark({ status, first }) {
  if (status === 'silent') return <FlatWaveform />;
  const circle = { display: 'flex', alignItems: 'center', justifyContent: 'center', width: 38, height: 38, borderRadius: '50%', boxSizing: 'border-box' };
  if (status === 'failed') return <span style={{ ...circle, border: '1px solid var(--color-line-2)', fontSize: 15, fontWeight: 700, color: 'var(--color-faint)' }}>!</span>;
  if (status === 'absent') return <span style={{ ...circle, border: '1px solid ' + (first ? 'var(--color-accent-line)' : 'var(--color-line-2)'), background: first ? 'var(--color-accent-bg)' : 'transparent' }}>{first ? <AccentDot size={7} /> : <span style={{ fontSize: 15, color: 'var(--color-faintest)' }}>—</span>}</span>;
  return <Spinner size={26} />;
}
function ReportEmpty({ status, refunded, sessions = [], current, onPick, onBack, onAgain }) {
  const first = status === 'absent' && sessions.length === 0;
  const copy = {
    silent: { title: '답변이 녹음되지 않았습니다', body: '다시 시작하기 전에 마이크 테스트로 소리가 잡히는지 확인해 주세요.', again: '다시 면접 보기' },
    failed: { title: '분석 결과를 만들지 못했습니다', body: '녹음과 전사는 남아 있습니다. 잠시 뒤 다시 열어 보세요.', again: '다시 면접 보기' },
    first: { title: '면접을 시작해 보세요', body: '면접을 마치면 답변마다 점수와 코칭이 만들어집니다.', again: '면접 시작하기' },
    absent: { title: '이 회차의 리포트가 없습니다', body: '분석이 끝나기 전에 기록이 끊겼습니다.', again: '다시 면접 보기' },
    running: { title: '답변을 분석하고 있습니다', body: '끝나면 이 화면이 저절로 바뀝니다. 창을 닫아도 계속됩니다.', again: '' },
  }[first ? 'first' : ['silent', 'failed', 'absent'].includes(status) ? status : 'running'];
  return (
    <main style={{ maxWidth: 'var(--container-report)', margin: '0 auto', padding: '40px 32px 80px', animation: 'dm-fade .3s ease' }}>
      <button onClick={onBack} style={{ marginBottom: 24, fontSize: 13, color: 'var(--color-muted)' }}>← 내 면접</button>
      <SessionPicker sessions={sessions} current={current} onPick={onPick} />
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', borderRadius: 'var(--radius-card)', border: '1px solid var(--color-line)', background: 'var(--color-surface)', padding: '48px 32px', textAlign: 'center' }}>
        <EmptyMark status={status} first={first} />
        <h1 style={{ margin: '22px 0 0', fontSize: 19, fontWeight: 700, letterSpacing: '-.02em' }}>{copy.title}</h1>
        <p style={{ margin: '11px 0 0', maxWidth: 430, fontSize: 13.5, lineHeight: 1.8, color: 'var(--color-muted)' }}>{copy.body}</p>
        {status === 'silent' && refunded && <div style={{ marginTop: 18, borderRadius: 'var(--radius-chip)', border: '1px solid var(--color-accent-line)', background: 'var(--color-accent-bg)', padding: '7px 13px', fontSize: 12.5, fontWeight: 600, color: 'var(--color-accent)' }}>크레딧은 돌려드렸습니다</div>}
        <div style={{ marginTop: 26, display: 'flex', alignItems: 'center', gap: 10 }}>
          <OutlineButton onClick={onBack} style={{ padding: '11px 18px' }}>내 면접으로</OutlineButton>
          {copy.again && <PrimaryButton onClick={onAgain} style={{ padding: '11px 22px', fontSize: 13.5 }}>{copy.again}</PrimaryButton>}
        </div>
      </div>
    </main>
  );
}

const Rule = ({ color, titleColor, title, children }) => (
  <div style={{ borderLeft: '2px solid ' + color, paddingLeft: 15 }}>
    <div style={{ marginBottom: 6, fontSize: 11.5, fontWeight: 700, color: titleColor || color }}>{title}</div>
    <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.8, color: 'var(--color-body)' }}>{children}</p>
  </div>
);
function Report({ card, hasVideo = true, sessions = SESSIONS, feedback = FEEDBACK, onBack, onAgain }) {
  const [openQ, setOpenQ] = React.useState(0);
  const [sessionId, setSessionId] = React.useState(sessions[0] && sessions[0].id);
  const { coaching, voice } = feedback;
  const fb = hasVideo ? feedback : { ...feedback, gaze: undefined, expression: undefined, voice: { ...voice, meanStartDelayS: null } };
  const minutes = Math.floor(fb.durationS / 60), seconds = Math.round(fb.durationS % 60);
  const Section = ({ label, children, last }) => (<section style={{ padding: '30px 0', borderBottom: last ? 0 : '1px solid var(--color-line)' }}><div style={{ marginBottom: 18 }}><SectionLabel>{label}</SectionLabel></div>{children}</section>);
  return (
    <main style={{ maxWidth: 'var(--container-report)', margin: '0 auto', padding: '40px 32px 90px', animation: 'dm-fade .3s ease' }}>
      <div style={{ marginBottom: 30 }}><button onClick={onBack} style={{ fontSize: 13, color: 'var(--color-muted)' }}>← 내 면접</button></div>
      <SessionPicker sessions={sessions} current={sessionId} onPick={setSessionId} />
      {/* 무대 띠 — 이 리포트가 어느 면접장에서 나왔는지. 점수와 총평이 어두운 판 위에 */}
      <div style={{ position: 'relative', overflow: 'hidden', borderRadius: 'var(--radius-card)', background: 'var(--stage-bg)', color: 'var(--stage-ink-warm)', padding: '30px 32px', marginBottom: 30, display: 'flex', alignItems: 'flex-start', gap: 34 }}>
        <div style={{ pointerEvents: 'none', position: 'absolute', left: '50%', top: '-60%', width: 900, height: 420, transform: 'translateX(-50%)', background: 'radial-gradient(ellipse at 50% 0%, rgba(var(--stage-keylight-rgb),.09), transparent 62%)' }} />
        <div style={{ position: 'relative', width: 72, height: 72, flexShrink: 0, marginTop: 2 }}>
          <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'var(--gradient-sphere)', boxShadow: 'inset 0 1px 0 rgba(255,255,255,.10), inset 0 -10px 18px rgba(0,0,0,.42)' }} />
          <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', opacity: .55, background: 'var(--gradient-voice-amber)' }} />
        </div>
        <div style={{ position: 'relative', flex: 1, display: 'flex', flexDirection: 'column', gap: 9, minWidth: 0 }}>
          <div className="num" style={{ fontSize: 12.5, color: 'var(--stage-dim)' }}>{minutes}분 {seconds}초 · 답변 {coaching.answers.length}개</div>
          <h1 style={{ margin: 0, fontSize: 25, fontWeight: 700, letterSpacing: '-.03em', color: 'var(--stage-paper)' }}>{card.company} · {card.role}</h1>
          <p style={{ margin: '6px 0 0', maxWidth: 520, fontSize: 14, lineHeight: 1.7, color: 'var(--stage-ink-warm)', wordBreak: 'keep-all' }}>{coaching.summary}</p>
        </div>
        <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}><span className="num" style={{ fontSize: 56, lineHeight: 1, fontWeight: 700, letterSpacing: '-.05em', color: 'var(--stage-paper)' }}>{coaching.score ?? '—'}</span><span style={{ fontSize: 15, color: 'var(--stage-dim)' }}>/ 100</span></div>
          <span style={{ fontSize: 12, color: 'var(--stage-dim-2)' }}>답변 점수의 평균</span>
        </div>
      </div>
      {fb.voice && (
        <Section label="음성 지표">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
            <Metric label="말하기 속도" value={Math.round(fb.voice.syllablesPerMinute)} unit="음절/분" low={280} high={360} range="280~360 권장" />
            <Metric label="답변 길이" value={Math.round(fb.voice.meanAnswerS)} unit="초 평균" low={30} high={90} range="30~90초 권장" />
            <Metric label="필러 워드" value={fb.voice.spokenS > 0 ? Math.round((coaching.fillers / fb.voice.spokenS) * 600) / 10 : 0} unit="회/분" high={3} range="분당 3회 이하 권장" />
            <Metric label="답변까지" value={fb.voice.meanStartDelayS === null ? null : Math.round(fb.voice.meanStartDelayS * 10) / 10} unit="초" high={3} range="3초 이내 권장" />
            <Metric label="답변 중 멈춤" value={Math.round(fb.voice.pauseRatio * 100)} unit="%" high={12} range="12% 이하 권장" />
            <Metric label="목소리 흔들림" value={Math.round(fb.voice.loudnessVariation * 100) / 100} unit="" high={0.45} range="0.45 이하 권장" />
          </div>
        </Section>
      )}
      {(fb.gaze || fb.expression) && <Delivery gaze={fb.gaze} expression={fb.expression} />}
      {(coaching.strengths.length > 0 || coaching.improvements.length > 0) && (
        <Section label="종합 평가">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}><div style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-positive)' }}>잘한 점</div>{coaching.strengths.map(t => <div key={t} style={{ display: 'flex', gap: 8 }}><span style={{ display: 'flex', marginTop: 3 }}><Icon name="check" size={13} color="var(--color-positive)" /></span><span style={{ fontSize: 13.5, lineHeight: 1.65, color: 'var(--color-body-2)' }}>{t}</span></div>)}</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}><div style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-accent)' }}>보완할 점</div>{coaching.improvements.map(t => <div key={t} style={{ display: 'flex', gap: 8 }}><span style={{ display: 'flex', marginTop: 3 }}><Icon name="arrow-right" size={13} color="var(--color-accent)" /></span><span style={{ fontSize: 13.5, lineHeight: 1.65, color: 'var(--color-body-2)' }}>{t}</span></div>)}</div>
          </div>
        </Section>
      )}
      <Section label="답변별 피드백" last>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {coaching.answers.map((a, i) => {
            const open = openQ === i, span = fb.voice && fb.voice.answers[i], ex = fb.expression && fb.expression.answers[i];
            const dominant = ex && ex.frames >= 2 ? IMPRESSIONS.reduce((b, im) => ((ex.impressions[im.key] ?? 0) > (ex.impressions[b.key] ?? 0) ? im : b)) : null;
            return (
              <div key={i} style={{ borderRadius: 'var(--radius-card)', background: 'var(--color-surface)', border: '1px solid ' + (open ? 'var(--color-field)' : 'var(--color-line)') }}>
                <div onClick={() => setOpenQ(open ? -1 : i)} style={{ display: 'flex', alignItems: 'center', gap: 13, padding: '15px 18px', cursor: 'pointer' }}>
                  <span className="num" style={{ width: 22, fontSize: 11.5, fontWeight: 600, color: 'var(--color-faintest)' }}>Q{i + 1}</span>
                  <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 13.5, fontWeight: 600 }}>{open ? '' : a.question}</span>
                  {dominant && <span style={{ borderRadius: 'var(--radius-chip)', background: 'var(--color-surface-2)', padding: '2px 8px', fontSize: 11, color: 'var(--color-body-2)' }}>{dominant.label} 우세</span>}
                  {span && <span className="num" style={{ fontSize: 11.5, color: 'var(--color-faintest)' }}>{(span.endS - span.startS).toFixed(1)}초</span>}
                  <span className="num" style={{ width: 28, textAlign: 'right', fontSize: 15, fontWeight: 700 }}>{a.score}</span>
                  <span style={{ width: 16, display: 'flex' }}><Caret open={open} size={12} /></span>
                </div>
                {open && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: '4px 18px 20px', animation: 'dm-fade .25s ease' }}>
                    <div style={{ borderTop: '1px solid var(--color-hair)', paddingTop: 16, fontSize: 15, lineHeight: 1.6, fontWeight: 600 }}>{a.question}</div>
                    {span && (
                      <div style={hasVideo ? { display: 'grid', gridTemplateColumns: '1fr 248px', gap: 14 } : undefined}>
                        <div style={{ display: 'flex', minWidth: 0, flexDirection: 'column', gap: 6, borderRadius: 'var(--radius-control)', background: 'var(--color-surface-2)', padding: '12px 14px' }}>
                          <span className="num" style={{ fontSize: 11.5, color: 'var(--color-faint)' }}>({fmtAt(span.startS)})</span>
                          <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.85, color: 'var(--color-body-2)' }}>{span.text}</p>
                          <span style={{ fontSize: 11.5, color: 'var(--color-faintest)' }}>{[span.pauses > 0 && '말이 ' + span.pauses + '번 끊겼습니다', a.fillers.length > 0 && '필러 워드 ' + a.fillers.join(' · ')].filter(Boolean).join('  ·  ')}</span>
                        </div>
                        <Playback startS={Math.max(0, span.startS - PAD_BEFORE_S)} endS={span.endS + PAD_AFTER_S} video={hasVideo} />
                      </div>
                    )}
                    {a.strength && <Rule color="var(--color-positive)" title="잘한 점">{a.strength}</Rule>}
                    <Rule color="var(--color-line-2)" titleColor="var(--color-muted)" title="더 듣고 싶었던 것">{a.gap}</Rule>
                    <Rule color="var(--color-accent)" title="이렇게 바꿔보세요">{a.suggestion}</Rule>
                  </div>
                )}
              </div>);
          })}
        </div>
      </Section>
      <div style={{ display: 'flex', alignItems: 'center' }}><button onClick={onBack} style={{ fontSize: 13, color: 'var(--color-muted)' }}>내 면접으로</button><div style={{ flex: 1 }} /><PrimaryButton onClick={onAgain} style={{ padding: '13px 28px' }}>이 회사로 다시 면접 보기</PrimaryButton></div>
    </main>
  );
}
window.DaedamReport = Report;
window.DaedamReportEmpty = ReportEmpty;
window.DaedamMetric = Metric;
window.DaedamSessions = SESSIONS;
