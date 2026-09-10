// Recreation of web/src/screens/Ready.tsx. Preflight is a gate: mic must be heard + two manual checks. Camera is optional (permission asked here, not in the interview). No gaze baseline — removed upstream.
const STAGE_NAMES = ['자기소개', '직무역량', '인성·컬처핏', '마무리'];

/** 시작 전 확인 한 행. Preflight 바깥에 두어야 재렌더 때 자식(마이크 막대의 ref)이 리마운트되지 않는다. */
function Row({ ok, children, right }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
      {ok ? <CheckDot size={15} /> : <EmptyDot size={15} />}
      <span style={{ fontSize: 13.5, color: ok ? 'var(--color-ink)' : 'var(--color-muted)' }}>{children}</span>
      <div style={{ flex: 1 }} />{right}
    </div>
  );
}
function Preflight({ onReady }) {
  const [heard, setHeard] = React.useState(false);
  const [testing, setTesting] = React.useState(false);
  const [camera, setCamera] = React.useState('off'); // 'off' | 'on' | 'missing' | 'denied'
  const [checked, setChecked] = React.useState({});
  const bar = React.useRef(null);
  const manual = ['조용한 곳에서 진행합니다', '중간에 그만두면 그때까지의 답변으로 리포트를 받습니다'];
  const ready = heard && manual.every(l => checked[l]);
  React.useEffect(() => onReady(ready), [ready]);
  // 킷: 실제 마이크 대신 합성 진폭. 진폭은 ref→style로 간다(원본과 같은 원칙).
  React.useEffect(() => {
    if (!testing) return;
    let raf = 0; const t0 = performance.now();
    const loop = () => { const t = (performance.now() - t0) / 1000; const level = t < 0.8 ? 0.03 : Math.max(0, Math.sin(t * 5.3) * 0.5 + Math.sin(t * 9.1) * 0.3 + 0.3) * 0.7; if (bar.current) bar.current.style.width = Math.round(level * 100) + '%'; if (level >= 0.12) setHeard(h => h || true); raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop); return () => cancelAnimationFrame(raf);
  }, [testing]);
  const link = { fontSize: 12.5, color: 'var(--color-muted)', borderBottom: '1px solid var(--color-field)' };
  const camLabel = { on: '카메라가 켜졌습니다', missing: '카메라를 찾지 못했습니다', denied: '카메라 권한이 막혀 있습니다', off: '카메라로 내 모습을 보며 연습할 수 있습니다' }[camera];
  return (
    <Card style={{ marginBottom: 26, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <SectionLabel>시작 전 확인</SectionLabel>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <Row ok={heard} right={<>
          {testing && <div style={{ width: 90, height: 4, background: 'var(--color-hair-2)' }}><div ref={bar} style={{ height: '100%', width: '0%', background: 'var(--color-accent)' }} /></div>}
          <button onClick={() => { setTesting(t => !t); if (testing && bar.current) bar.current.style.width = '0%'; }} style={link}>{testing ? '테스트 끝내기' : '테스트하기'}</button>
        </>}>{heard ? '마이크가 소리를 잡았습니다' : '마이크를 테스트해 주세요'}</Row>
        {testing && !heard && <p style={{ margin: 0, paddingLeft: 24, fontSize: 12, color: 'var(--color-faint)' }}>아무 말이나 해보세요 — 막대가 움직이면 됩니다.</p>}
        <Row ok={camera === 'on'} right={<button onClick={() => setCamera(c => (c === 'on' ? 'off' : 'on'))} style={link}>{camera === 'on' ? '끄기' : '카메라 켜기'}</button>}>{camLabel}</Row>
        {camera === 'on' && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, paddingLeft: 24 }}>
            <div style={{ width: '100%', maxWidth: 320, aspectRatio: '4 / 3', borderRadius: 'var(--radius-card)', border: '1px solid var(--color-line)', background: 'var(--color-surface-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11.5, color: 'var(--color-faintest)' }}>웹캠 미리보기 · 거울 반전</div>
            <span style={{ fontSize: 12, color: 'var(--color-faint)' }}>얼굴이 가운데에 오고 밝은지 확인해 주세요</span>
          </div>
        )}
        {manual.map(l => (
          <button key={l} onClick={() => setChecked(c => ({ ...c, [l]: !c[l] }))} style={{ display: 'flex', alignItems: 'center', gap: 9, textAlign: 'left' }}>
            {checked[l] ? <CheckDot size={15} /> : <EmptyDot size={15} />}
            <span style={{ fontSize: 13.5, color: checked[l] ? 'var(--color-ink)' : 'var(--color-muted)' }}>{l}</span>
          </button>
        ))}
      </div>
    </Card>
  );
}

function StartInterview({ cost, balance, onStart }) {
  const [confirming, setConfirming] = React.useState(false);
  if (!confirming) return (<>
    <PrimaryButton size="lg" onClick={() => setConfirming(true)}>면접 시작하기</PrimaryButton>
    {cost !== undefined && <span className="num" style={{ fontSize: 12.5, color: 'var(--color-faint)' }}>크레딧 {balance}개 보유 · 면접에 {cost}개</span>}
  </>);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 10, borderRadius: 'var(--radius-card)', border: '1px solid var(--color-accent-line)', background: 'var(--color-accent-bg)', padding: '14px 18px' }}>
      <span style={{ fontSize: 13.5, color: 'var(--color-body-2)' }}>면접을 시작하면 크레딧 <span className="num" style={{ fontWeight: 600 }}>{cost}</span>개가 사용됩니다.</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><OutlineButton onClick={() => setConfirming(false)}>취소</OutlineButton><PrimaryButton size="sm" onClick={onStart} style={{ padding: '10px 24px', fontSize: 13.5 }}>시작하기</PrimaryButton></div>
    </div>
  );
}

/** 문턱 — 밝은 세계에서 어두운 무대로 들어가는 문. 무대 D의 정지 화면 위에 시작 버튼. */
function Threshold({ card, ready, short, credits, onStart, stages = true, stagesAlign = 'center' }) {
  const narrow = useNarrow();
  const [confirming, setConfirming] = React.useState(false);
  const disabled = short || !ready;
  return (
    <div data-threshold="true" style={{ position: 'relative', overflow: 'hidden', borderRadius: 'var(--radius-card)', background: 'var(--stage-bg)', color: 'var(--stage-ink-warm)', marginBottom: 16, minHeight: 300, display: 'flex', flexDirection: 'column' }}>
      <div style={{ pointerEvents: 'none', position: 'absolute', left: '50%', top: '-34%', width: 900, height: 520, transform: 'translateX(-50%)', background: 'radial-gradient(ellipse at 50% 0%, rgba(var(--stage-keylight-rgb),.09), transparent 62%)' }} />
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center', padding: '18px 22px' }}>
        <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--stage-amber)', boxShadow: '0 0 10px var(--stage-amber)' }} />
        <span style={{ marginLeft: 9, fontSize: 13, color: 'var(--stage-ink-warm)' }}>면접관이 기다리고 있습니다</span>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 12.5, color: 'var(--stage-dim)' }}>{card.company} · {card.role}</span>
      </div>
      <div style={{ position: 'relative', flex: 1, display: 'flex', alignItems: 'center', gap: 28, padding: '6px 32px 28px', ...(narrow ? { flexWrap: 'wrap', gap: 18, padding: '22px 20px' } : {}) }}>
        <div style={{ position: 'relative', width: narrow ? 88 : 128, height: narrow ? 88 : 128, flexShrink: 0 }}>
          <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'var(--gradient-sphere)', boxShadow: 'inset 0 1px 0 rgba(255,255,255,.10), inset 0 -16px 30px rgba(0,0,0,.42), 0 20px 44px -20px rgba(0,0,0,.9)', animation: 'dm-breathe 6s ease-in-out infinite' }} />
          <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'var(--gradient-sphere-sheen)' }} />
          <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', opacity: .5, background: 'var(--gradient-voice-amber)' }} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: narrow ? '1 1 160px' : 1, minWidth: 0 }}>
          <span style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-.025em', color: 'var(--stage-paper)', wordBreak: 'keep-all' }}>지금 면접장에 들어갑니다</span>
          <span style={{ fontSize: 13.5, lineHeight: 1.65, color: 'var(--stage-dim)', wordBreak: 'keep-all' }}>면접은 15분 내외로 진행됩니다. 면접관에게 직무역량과 인성 · 컬처핏을 어필해보세요.</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: narrow ? 'stretch' : 'flex-end', gap: 9, flexShrink: 0, flexBasis: narrow ? '100%' : 'auto' }}>
          {disabled ? (<>
            <button disabled style={{ font: 'inherit', fontSize: 15, fontWeight: 600, color: 'rgba(233,227,216,.35)', background: 'rgba(255,255,255,.06)', border: '1px solid rgba(255,255,255,.08)', borderRadius: 'var(--radius-control)', padding: '14px 34px', cursor: 'default' }}>면접 시작하기</button>
            <span className="num" style={{ fontSize: 12.5, color: short ? 'var(--stage-amber)' : 'var(--stage-dim)' }}>{short ? '크레딧이 부족합니다 · 면접에 ' + credits.interview + '개 필요' : '아래 시작 전 확인을 모두 마쳐 주세요'}</span>
          </>) : !confirming ? (<>
            <button onClick={() => setConfirming(true)} style={{ font: 'inherit', fontSize: 15, fontWeight: 600, color: '#0C0F19', background: 'var(--stage-paper)', border: 0, borderRadius: 'var(--radius-control)', padding: '14px 34px', cursor: 'pointer' }}>면접 시작하기</button>
            {credits && <span className="num" style={{ fontSize: 12.5, color: 'var(--stage-dim)' }}>크레딧 {credits.balance}개 보유 · 면접에 {credits.interview}개</span>}
          </>) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 10, borderRadius: 'var(--radius-card)', border: '1px solid rgba(217,168,108,.35)', background: 'rgba(217,168,108,.10)', padding: '14px 18px' }}>
              <span style={{ fontSize: 13.5, color: 'var(--stage-ink-warm)' }}>면접을 시작하면 크레딧 <span className="num" style={{ fontWeight: 600 }}>{credits.interview}</span>개가 사용됩니다.</span>
              <div style={{ display: 'flex', gap: 8 }}><button onClick={() => setConfirming(false)} style={{ font: 'inherit', fontSize: 13.5, fontWeight: 600, color: 'var(--stage-ink-warm)', background: 'transparent', border: '1px solid rgba(255,255,255,.18)', borderRadius: 'var(--radius-control)', padding: '10px 16px', cursor: 'pointer' }}>취소</button><button onClick={onStart} style={{ font: 'inherit', fontSize: 13.5, fontWeight: 600, color: '#0C0F19', background: 'var(--stage-paper)', border: 0, borderRadius: 'var(--radius-control)', padding: '10px 24px', cursor: 'pointer' }}>시작하기</button></div>
            </div>
          )}
        </div>
      </div>
      {/* 단계 줄 — 카드 넷을 쌓는 대신 띠 안에 접어 넣는다. 순서는 전달되고 무게는 없다 */}
      {stages && (
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: stagesAlign === 'center' ? 'center' : 'flex-start', flexWrap: 'wrap', rowGap: 8, columnGap: narrow ? 16 : 0, borderTop: '1px solid rgba(255,255,255,.08)', padding: '12px 22px' }}>
          {STAGE_NAMES.map((n, i) => (
            <div key={n} style={{ display: 'flex', alignItems: 'center', gap: 8, flex: stagesAlign === 'center' ? 'none' : 1, minWidth: 0 }}>
              <span className="num" style={{ fontSize: 11, fontWeight: 600, letterSpacing: '.04em', color: 'var(--stage-dim)' }}>0{i + 1}</span>
              <span style={{ fontSize: 13, color: 'var(--stage-ink-warm)', whiteSpace: 'nowrap' }}>{n}</span>
              {i < STAGE_NAMES.length - 1 && <span style={{ display: narrow ? 'none' : 'block', flex: stagesAlign === 'center' ? 'none' : 1, width: stagesAlign === 'center' ? 28 : undefined, height: 1, background: 'rgba(255,255,255,.08)', margin: '0 14px' }} />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Ready({ card, credits, onBack, onReview, onStart, threshold = true, stages = true, stagesAlign = 'center' }) {
  const narrow = useNarrow();
  const [ready, setReady] = React.useState(false);
  const short = credits && credits.balance < credits.interview;
  return (
    <main style={{ maxWidth: 'var(--container-report)', margin: '0 auto', padding: narrow ? '28px 16px 60px' : '44px 32px 80px', animation: 'dm-fade .3s ease' }}>
      <button onClick={onBack} style={{ marginBottom: 16, fontSize: 13, color: 'var(--color-muted)' }}>← 내 면접</button>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}><AccentDot /><span style={{ fontSize: 12, fontWeight: 600, letterSpacing: '.05em', color: 'var(--color-accent)' }}>면접 준비 완료</span></div>
      <h1 style={{ margin: 0, fontSize: narrow ? 23 : 27, fontWeight: 700, letterSpacing: '-.03em', wordBreak: 'keep-all' }}>{card.company} · {card.role}</h1>
      <div style={{ height: 26 }} />
      {threshold && <Threshold card={card} ready={ready} short={short} credits={credits} onStart={onStart} stages={stages} stagesAlign={stagesAlign} />}
      {!threshold && <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 16 }}>
        {STAGE_NAMES.map((n, i) => (
          <Card key={n} padding="15px 14px" style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span className="num" style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--color-faintest)' }}>0{i + 1}</span>
            <span style={{ fontSize: 14, fontWeight: 700 }}>{n}</span>
          </Card>
        ))}
      </div>}
      <Card style={{ marginBottom: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center' }}><SectionLabel>리서치 리포트</SectionLabel><div style={{ flex: 1 }} /><span style={{ fontSize: 11.5, color: 'var(--color-faintest)' }}>{card.date}</span></div>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12, borderTop: '1px solid var(--color-hair)', paddingTop: 14 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={{ fontSize: 14.5, fontWeight: 700 }}>{card.company} 면접 준비 리서치</span>
            <span style={{ fontSize: 12.5, color: 'var(--color-muted)' }}>사실과 다른 대목은 직접 고칠 수 있습니다</span>
          </div>
          <div style={{ flex: 1 }} />
          <OutlineButton size="sm" onClick={onReview}>리포트 검토</OutlineButton>
        </div>
      </Card>
      <Preflight onReady={setReady} />
      {!threshold && <div style={{ display: 'flex' }}>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 9 }}>
          {short || !ready ? (<>
            <PrimaryButton size="lg" disabled>면접 시작하기</PrimaryButton>
            {short ? <span className="num" style={{ fontSize: 12.5, color: 'var(--color-accent)' }}>크레딧이 부족합니다 · 면접에 {credits.interview}개 필요</span> : <span style={{ fontSize: 12.5, color: 'var(--color-faint)' }}>위의 시작 전 확인을 모두 마쳐 주세요</span>}
          </>) : <StartInterview cost={credits && credits.interview} balance={credits && credits.balance} onStart={onStart} />}
        </div>
      </div>}
    </main>
  );
}
window.DaedamReady = Ready;
