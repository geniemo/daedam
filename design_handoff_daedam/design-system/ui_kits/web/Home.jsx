// Recreation of web/src/screens/Home.tsx. 홈 비교 3안 — variant: 'strip'(기록 띠, 추천) · 'rail'(오른쪽 기록 레일) · 'dense'(카드 밀도).
// 공통: 다음 면접(무대 미리 보기) + 회사 카드. 허전함의 원인은 층이 하나라는 것 — 회사 목록만 있고 "쌓인 기록"이 없다.
const RECORDS = [
  { id: 'r1', company: '오름소프트', n: 1, score: 80, date: '7월 19일' },
  { id: 'r2', company: '한빛금융', n: 1, score: 74, date: '7월 21일', gap: '회사를 조사한 흔적이 답변에 드러나지 않았습니다' },
  { id: 'r3', company: '한빛금융', n: 2, score: 80, date: '7월 28일', gap: '회사를 조사한 흔적이 답변에 드러나지 않았습니다' },
];
const recurring = recs => { const m = {}; recs.forEach(r => { if (r.gap) m[r.gap] = (m[r.gap] || 0) + 1; }); const top = Object.entries(m).sort((a, b) => b[1] - a[1])[0]; return top && top[1] >= 2 ? { text: top[0], count: top[1] } : null; };
const Num = ({ v, unit, size = 22 }) => <span style={{ display: 'flex', alignItems: 'baseline', gap: 3 }}><span className="num" style={{ fontSize: size, lineHeight: 1, fontWeight: 700, letterSpacing: '-.04em' }}>{v}</span>{unit && <span style={{ fontSize: 12, color: 'var(--color-faint)' }}>{unit}</span>}</span>;
/** 최근 회차 점수 막대 — 높이가 점수. 100 기준. */
const Bars = ({ recs, h = 40 }) => (
  <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: h }}>
    {recs.map((r, i) => <div key={r.id} title={r.company + ' ' + r.n + '회차'} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}><span className="num" style={{ fontSize: 10.5, color: i === recs.length - 1 ? 'var(--color-ink)' : 'var(--color-faint)', fontWeight: i === recs.length - 1 ? 600 : 400 }}>{r.score}</span><div style={{ width: 14, height: Math.round((h - 16) * r.score / 100), borderRadius: 2, background: i === recs.length - 1 ? 'var(--color-accent)' : 'var(--color-line)' }} /></div>)}
  </div>
);

function CompanyCard({ card, onClick, dense }) {
  const pct = card.pct, rec = RECORDS.filter(r => r.company === card.company).slice(-1)[0];
  return (
    <Card onClick={onClick} style={{ minHeight: 172, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <div style={{ fontSize: 17, fontWeight: 700, letterSpacing: '-.02em' }}>{card.company}</div>
          <div style={{ fontSize: 13, color: 'var(--color-muted)' }}>{card.role}</div>
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ fontSize: 11.5, color: 'var(--color-faint)' }}>{card.date}</div>
      </div>
      <div style={{ flex: 1 }} />
      {dense && card.status === 'done' && rec && rec.gap && <p style={{ margin: '12px 0 12px', fontSize: 12.5, lineHeight: 1.6, color: 'var(--color-body-2)', display: 'flex', gap: 7 }}><span style={{ display: 'flex', marginTop: 3, flexShrink: 0 }}><Icon name="arrow-right" size={12} color="var(--color-accent)" /></span><span>{rec.gap}</span></p>}
      {dense && card.status === 'ready' && <p className="num" style={{ margin: '12px 0 12px', fontSize: 12.5, color: 'var(--color-muted)' }}>질문 8개 · 4단계 · 리서치 리포트 {card.date}</p>}
      {card.status === 'ready' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><AccentDot /><span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--color-accent)' }}>면접 준비 완료</span></div>
          <div style={{ display: 'flex', alignItems: 'center', borderTop: '1px solid var(--color-hair-2)', paddingTop: 11 }}><div style={{ flex: 1 }} /><span style={{ fontSize: 13, fontWeight: 600 }}>시작하기 →</span></div>
        </div>
      )}
      {card.status === 'researching' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
          <div style={{ display: 'flex', alignItems: 'center' }}><span className="num" style={{ fontSize: 12.5, color: 'var(--color-muted)' }}>면접 준비 중{pct === undefined ? '' : ' · ' + pct + '%'}</span><div style={{ flex: 1 }} /><span style={{ fontSize: 12, color: 'var(--color-faint)' }}>자세히 보기 →</span></div>
          {pct !== undefined && <ProgressBar pct={pct} />}
        </div>
      )}
      {card.status === 'done' && (
        <div style={{ display: 'flex', alignItems: 'flex-end', borderTop: '1px solid var(--color-hair-2)', paddingTop: 11 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <span style={{ fontSize: 12, color: 'var(--color-faint)' }}>{(card.interviewCount ?? 1) > 1 ? '면접 ' + card.interviewCount + '회' : '면접 완료'}</span>
            <span style={{ fontSize: 12.5, color: 'var(--color-muted)' }}>리포트 보기 →</span>
          </div>
          <div style={{ flex: 1 }} />
          {card.score !== undefined ? <Num v={card.score} unit="점" size={28} /> : card.analyzed ? <span style={{ fontSize: 12.5, color: 'var(--color-faint)' }}>답변 없음</span> : <span style={{ fontSize: 12.5, color: 'var(--color-faint)' }}>분석 중</span>}
        </div>
      )}
    </Card>
  );
}

/** 다음 면접 — 준비 완료된 것 중 가장 최근 하나. 무대 미리 보기 + 시작. dense면 준비된 것의 목록이 붙는다. */
function Featured({ card, onOpen, onStart, dense, compact }) {
  const ref = React.useRef(null); const [stack, setStack] = React.useState(false);
  React.useEffect(() => { const el = ref.current; if (!el) return; const ro = new ResizeObserver(([e]) => setStack(e.contentRect.width < 720)); ro.observe(el); return () => ro.disconnect(); }, []);
  return (
    <Card rootRef={ref} padding={0} style={{ marginBottom: 16, display: 'grid', gridTemplateColumns: stack ? '1fr' : (compact ? '220px' : '300px') + ' minmax(0, 1fr)', overflow: 'hidden', wordBreak: 'keep-all' }}>
      <div style={{ position: 'relative', minHeight: stack ? 150 : 196, background: 'var(--stage-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
        <div style={{ pointerEvents: 'none', position: 'absolute', left: '50%', top: '-40%', width: 520, height: 300, transform: 'translateX(-50%)', background: 'radial-gradient(ellipse at 50% 0%, rgba(var(--stage-keylight-rgb),.09), transparent 62%)' }} />
        <div style={{ position: 'relative', width: 96, height: 96 }}>
          <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'var(--gradient-sphere)', boxShadow: 'inset 0 1px 0 rgba(255,255,255,.10), inset 0 -12px 22px rgba(0,0,0,.42), 0 16px 34px -16px rgba(0,0,0,.9)', animation: 'dm-breathe 6s ease-in-out infinite' }} />
          <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'var(--gradient-sphere-sheen)' }} />
          <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', opacity: .5, background: 'var(--gradient-voice-amber)' }} />
        </div>
        <div style={{ position: 'absolute', left: 18, bottom: 16, display: 'flex', alignItems: 'center', gap: 7 }}><span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--stage-amber)', boxShadow: '0 0 8px var(--stage-amber)' }} /><span style={{ fontSize: 12, color: 'var(--stage-ink-warm)' }}>면접관이 기다리고 있습니다</span></div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', padding: '22px 24px', gap: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><AccentDot /><span style={{ fontSize: 12, fontWeight: 600, letterSpacing: '.05em', color: 'var(--color-accent)' }}>다음 면접</span></div>
        <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-.025em', marginTop: 2 }}>{card.company}</div>
        <div style={{ fontSize: 13.5, color: 'var(--color-muted)' }}>{card.role} · {card.date} 등록</div>
        {dense && (
          <div style={{ display: 'flex', gap: 22, marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--color-hair)' }}>
            {[['질문', '8개 · 4단계'], ['리서치 리포트', card.date + ' 생성 · 확인 필요 2곳'], ['지난 회차', '첫 면접']].map(([k, v]) => <div key={k} style={{ display: 'flex', flexDirection: 'column', gap: 3 }}><span style={{ fontSize: 11.5, color: 'var(--color-faint)' }}>{k}</span><span className="num" style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-body)' }}>{v}</span></div>)}
          </div>
        )}
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 10, marginTop: 14 }}>
          <PrimaryButton size="lg" onClick={() => onStart(card)} style={{ whiteSpace: 'nowrap' }}>면접 시작하기</PrimaryButton>
          <OutlineButton onClick={() => onOpen(card)} style={{ whiteSpace: 'nowrap' }}>준비 내용 보기</OutlineButton>
        </div>
        <span style={{ fontSize: 12.5, color: 'var(--color-faint)', marginTop: 10, whiteSpace: 'nowrap' }}>15분 내외 · 한국어 음성</span>
      </div>
    </Card>
  );
}

/** A. 기록 띠 — 면접 횟수·평균·최근, 회차 막대, 반복된 보완점. 한 줄로 "쌓인 것"을 보인다. */
function RecordStrip({ recs, onReport }) {
  const narrow = useNarrow();
  const avg = Math.round(recs.reduce((s, r) => s + r.score, 0) / recs.length), last = recs[recs.length - 1], rep = recurring(recs);
  return (
    <Card padding={narrow ? '16px 18px' : '18px 22px'} style={{ marginBottom: 16, display: 'grid', gridTemplateColumns: narrow ? '1fr' : 'auto auto auto 1fr', alignItems: 'center', gap: narrow ? 16 : 36 }}>
      <div style={{ display: 'flex', gap: 28 }}>
        {[['면접', recs.length, '회'], ['평균', avg, '점'], ['최근', last.score, '점']].map(([k, v, u]) => <div key={k} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}><span style={{ fontSize: 11.5, color: 'var(--color-faint)' }}>{k}</span><Num v={v} unit={u} /></div>)}
      </div>
      {!narrow && <div style={{ width: 1, height: 44, background: 'var(--color-hair-2)' }} />}
      <Bars recs={recs} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 0, justifyContent: narrow ? 'space-between' : 'flex-end' }}>
        {rep ? <div style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0 }}><span style={{ display: 'flex', flexShrink: 0 }}><Icon name="arrow-right" size={13} color="var(--color-accent)" /></span><span style={{ fontSize: 13, color: 'var(--color-body-2)', ...(narrow ? { lineHeight: 1.5, wordBreak: 'keep-all' } : { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }) }}>{rep.text}</span><span className="num" style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--color-accent)', flexShrink: 0 }}>{rep.count}회 지적</span></div> : <span style={{ fontSize: 13, color: 'var(--color-faint)' }}>반복된 보완점이 아직 없습니다</span>}
        <button onClick={onReport} style={{ fontSize: 12.5, color: 'var(--color-muted)', flexShrink: 0, borderBottom: '1px solid var(--color-field)' }}>리포트 보기</button>
      </div>
    </Card>
  );
}
/** B. 오른쪽 레일 — 기록 목록 · 크레딧 · 반복된 보완점. */
function Rail({ recs, credits, onReport }) {
  const rep = recurring(recs);
  return (
    <aside style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Card style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center' }}><SectionLabel>기록</SectionLabel><div style={{ flex: 1 }} /><span className="num" style={{ fontSize: 11.5, color: 'var(--color-faint)' }}>면접 {recs.length}회</span></div>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {[...recs].reverse().map((r, i) => <button key={r.id} onClick={onReport} style={{ display: 'grid', gridTemplateColumns: '1fr 72px 28px', alignItems: 'center', gap: 10, padding: '10px 0', borderTop: i ? '1px solid var(--color-hair)' : 0, textAlign: 'left' }}><span style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}><span style={{ fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.company} <span style={{ fontWeight: 400, color: 'var(--color-muted)' }}>{r.n}회차</span></span><span className="num" style={{ fontSize: 11.5, color: 'var(--color-faint)' }}>{r.date}</span></span><span style={{ height: 4, background: 'var(--color-line-3)' }}><span style={{ display: 'block', height: '100%', width: r.score + '%', background: 'var(--color-ink)' }} /></span><span className="num" style={{ fontSize: 14, fontWeight: 700, textAlign: 'right' }}>{r.score}</span></button>)}
        </div>
      </Card>
      {rep && <Card style={{ display: 'flex', flexDirection: 'column', gap: 8 }}><SectionLabel>반복된 보완점</SectionLabel><p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.65, color: 'var(--color-body-2)' }}>{rep.text}</p><span className="num" style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--color-accent)' }}>리포트 {rep.count}건에서</span></Card>}
      <Card style={{ display: 'flex', alignItems: 'center', gap: 12 }}><div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}><span style={{ fontSize: 11.5, color: 'var(--color-faint)' }}>크레딧</span><Num v={credits.balance} unit={'개 · 면접 ' + Math.floor(credits.balance / credits.interview) + '회 분량'} size={20} /></div><div style={{ flex: 1 }} /><OutlineButton size="sm">충전</OutlineButton></Card>
    </aside>
  );
}
/** 첫 방문 — 등록한 회사가 없다. */
function Empty({ onRegister }) {
  return (
    <Card style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', padding: '56px 32px' }}>
      <div style={{ position: 'relative', width: 72, height: 72, marginBottom: 22 }}>
        <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'var(--gradient-sphere)', boxShadow: 'inset 0 1px 0 rgba(255,255,255,.10), inset 0 -10px 18px rgba(0,0,0,.42)' }} />
        <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', opacity: .5, background: 'var(--gradient-voice-amber)' }} />
      </div>
      <h2 style={{ margin: 0, fontSize: 19, fontWeight: 700, letterSpacing: '-.02em' }}>첫 회사를 등록해 보세요</h2>
      <p style={{ margin: '10px 0 0', maxWidth: 420, fontSize: 13.5, lineHeight: 1.75, color: 'var(--color-muted)' }}>회사를 등록하면 대담의 노하우를 통해 면접을 준비합니다.<br />준비가 끝나면 면접을 시작해보세요.</p>
      <div style={{ marginTop: 24 }}><PrimaryButton onClick={onRegister} style={{ padding: '12px 26px' }}>회사 등록하기</PrimaryButton></div>
    </Card>
  );
}
function Home({ cards, notice, onDismissNotice, onOpen, onStart, onRegister, onReport, credits = { balance: 7, interview: 3 }, variant = 'strip' }) {
  const narrow = useNarrow();
  const featured = cards.find(c => c.status === 'ready');
  const rest = cards.filter(c => c !== featured);
  const empty = cards.length === 0;
  const recs = RECORDS, hasRecs = !empty && recs.length > 0;
  const grid = <div style={{ display: 'grid', gap: 16, gridTemplateColumns: variant === 'rail' && !narrow ? 'repeat(2, minmax(0, 1fr))' : 'repeat(auto-fill, minmax(min(340px, 100%), 1fr))' }}>
    {rest.map(c => <CompanyCard key={c.id} card={c} dense={variant === 'dense'} onClick={() => onOpen(c)} />)}
    <button onClick={onRegister} style={{ display: 'flex', minHeight: 172, alignItems: 'center', justifyContent: 'center', borderRadius: 'var(--radius-card)', border: '1px dashed var(--color-field)', fontSize: 13.5, color: 'var(--color-faint)' }}>+ 새 회사 등록</button>
  </div>;
  return (
    <main style={{ maxWidth: 'var(--container-home)', margin: '0 auto', padding: narrow ? '28px 20px 60px' : '44px 32px 80px' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: 16, marginBottom: 28 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <h1 style={{ margin: 0, fontSize: 27, lineHeight: 1.25, fontWeight: 700, letterSpacing: '-.03em' }}>내 면접</h1>
          {!empty && <p style={{ margin: 0, fontSize: 14, color: 'var(--color-muted)' }}>회사를 등록하면 그 회사에 맞춘 질문으로 면접을 준비합니다.</p>}
        </div>
        <div style={{ flex: 1 }} />
        {!empty && <PrimaryButton onClick={onRegister} style={{ padding: '11px 20px' }}>회사 등록하기</PrimaryButton>}
      </div>
      {notice && (
        <div style={{ marginBottom: 18, display: 'flex', alignItems: 'flex-start', gap: 12, borderRadius: 'var(--radius-control)', border: '1px solid var(--color-accent-line)', background: 'var(--color-accent-bg)', padding: '11px 14px', fontSize: 13, lineHeight: 1.6, color: 'var(--color-accent)' }}>
          <span style={{ flex: 1 }}>{notice}</span>
          <button onClick={onDismissNotice} style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-accent)' }}>닫기</button>
        </div>
      )}
      {empty && <Empty onRegister={onRegister} />}
      {!empty && variant === 'strip' && hasRecs && <RecordStrip recs={recs} onReport={onReport} />}
      {!empty && variant === 'rail' ? (
        <div style={{ display: 'grid', gridTemplateColumns: narrow ? '1fr' : 'minmax(0, 1fr) 300px', gap: 16, alignItems: 'start' }}>
          <div style={{ minWidth: 0 }}>{featured && <Featured compact card={featured} onOpen={onOpen} onStart={onStart || onOpen} />}{grid}</div>
          {hasRecs && <Rail recs={recs} credits={credits} onReport={onReport} />}
        </div>
      ) : !empty && (<>
        {featured && <Featured card={featured} onOpen={onOpen} onStart={onStart || onOpen} dense={variant === 'dense'} />}
        {grid}
      </>)}
    </main>
  );
}
window.DaedamHome = Home;
