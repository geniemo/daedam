// Recreation of web/src/screens/Home.tsx. Card states: ready / researching / done(score · 답변 없음 · 분석 중). notice = 면접 화면이 결과 없이 돌려보낸 이유.
function CompanyCard({ card, onClick }) {
  const pct = card.pct;
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
          {card.score !== undefined ? (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 3 }}><span className="num" style={{ fontSize: 28, lineHeight: 1, fontWeight: 700, letterSpacing: '-.04em' }}>{card.score}</span><span style={{ fontSize: 12, color: 'var(--color-faint)' }}>점</span></div>
          ) : card.analyzed ? <span style={{ fontSize: 12.5, color: 'var(--color-faint)' }}>답변 없음</span> : <span style={{ fontSize: 12.5, color: 'var(--color-faint)' }}>분석 중</span>}
        </div>
      )}
    </Card>
  );
}

/** 다음 면접 — 준비 완료된 것 중 가장 최근 하나. 무대 미리 보기 + 시작. */
function Featured({ card, onOpen, onStart }) {
  return (
    <Card padding={0} style={{ marginBottom: 16, display: 'grid', gridTemplateColumns: '300px minmax(0, 1fr)', overflow: 'hidden' }}>
      <div style={{ position: 'relative', minHeight: 196, background: 'var(--stage-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
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
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 14 }}>
          <PrimaryButton size="lg" onClick={() => onStart(card)}>면접 시작하기</PrimaryButton>
          <OutlineButton onClick={() => onOpen(card)}>준비 내용 보기</OutlineButton>
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 12.5, color: 'var(--color-faint)' }}>15분 내외 · 한국어 음성</span>
        </div>
      </div>
    </Card>
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
function Home({ cards, notice, onDismissNotice, onOpen, onStart, onRegister }) {
  const featured = cards.find(c => c.status === 'ready');
  const rest = cards.filter(c => c !== featured);
  const empty = cards.length === 0; // 빈 상태: 카드가 주인공 — 상단 버튼·부제를 숨겨 같은 행동이 둘 되지 않게
  return (
    <main style={{ maxWidth: 'var(--container-home)', margin: '0 auto', padding: '44px 32px 80px' }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16, marginBottom: 28 }}>
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
      {featured && <Featured card={featured} onOpen={onOpen} onStart={onStart || onOpen} />}
      {cards.length > 0 && <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))' }}>
        {rest.map(c => <CompanyCard key={c.id} card={c} onClick={() => onOpen(c)} />)}
        <button onClick={onRegister} style={{ display: 'flex', minHeight: 172, alignItems: 'center', justifyContent: 'center', borderRadius: 'var(--radius-card)', border: '1px dashed var(--color-field)', fontSize: 13.5, color: 'var(--color-faint)' }}>+ 새 회사 등록</button>
      </div>}
    </main>
  );
}
window.DaedamHome = Home;
