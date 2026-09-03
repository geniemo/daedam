// 온보딩 확정안 (3c 두 단계). 로직·카피는 Onboarding.tsx 기준, 화면만 이름 → 동의 두 단계로 나눈다.
const Logo = ({ dark }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
    <span style={{ display: 'flex', width: 26, height: 26, alignItems: 'center', justifyContent: 'center', border: '1.5px solid ' + (dark ? 'var(--color-stage-ink)' : 'var(--color-ink)') }}><span style={{ width: 10, height: 10, background: 'var(--color-accent)' }} /></span>
    <span style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-.02em', color: dark ? 'var(--color-stage-ink)' : 'var(--color-ink)' }}>대담</span>
  </div>
);

function Avatar({ size = 206, speaking = true }) {
  const s = size / 206;
  return (
    <div style={{ position: 'relative', width: 340 * s, height: 340 * s, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ position: 'absolute', width: 340 * s, height: 340 * s, borderRadius: '50%', background: 'var(--gradient-talk-glow)', opacity: speaking ? .3 : 0, transition: 'opacity .6s', animation: 'dm-pulse2 2.6s ease-in-out infinite' }} />
      <div style={{ position: 'absolute', width: 270 * s, height: 270 * s, borderRadius: '50%', border: '1px solid var(--color-talk-ring)', opacity: speaking ? .5 : 0, transition: 'opacity .6s', animation: 'dm-pulse 2.2s ease-in-out infinite' }} />
      <div style={{ position: 'absolute', width: 246 * s, height: 246 * s, borderRadius: '50%', border: '1.5px solid var(--color-hear-ring)', opacity: speaking ? 0 : .5, transition: 'opacity .6s', animation: 'dm-pulse 2.2s ease-in-out infinite' }} />
      <div data-avatar-slot="true" style={{ position: 'relative', width: size, height: size, borderRadius: '50%', background: 'var(--gradient-avatar)', border: '1px solid var(--color-stage-line)', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', animation: 'dm-breathe 4.5s ease-in-out infinite' }}>
        <div style={{ position: 'absolute', inset: 0, background: 'var(--gradient-avatar-highlight)' }} />
        <div style={{ width: 96 * s, height: 96 * s, borderRadius: '50%', border: '1px solid var(--color-avatar-inner-ring)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><div style={{ width: 44 * s, height: 44 * s, borderRadius: '50%', background: 'var(--color-avatar-core)', transform: speaking ? 'scale(1)' : 'scale(.82)', transition: 'transform .6s' }} /></div>
      </div>
    </div>
  );
}

/** 타자 효과. 이름을 치면 면접관이 그 이름으로 부른다. */
function useTyped(text, speed = 30) {
  const [n, setN] = React.useState(0);
  React.useEffect(() => { setN(0); let i = 0; const t = setInterval(() => { i += 1; setN(i); if (i >= text.length) clearInterval(t); }, speed); return () => clearInterval(t); }, [text]);
  return text.slice(0, n);
}

/** 이름 정규화: 공백 제거. 면접관은 성을 뺀 이름으로 부른다(Chrome.tsx의 slice(-2,-1)와 같은 규칙: 마지막 두 글자). */
const givenName = (name) => { const t = name.trim(); if (!t) return ''; return t.length >= 3 ? t.slice(-2) : t; };

/* ── 공통 폼: Onboarding.tsx 그대로. 이름 · 동의 2건 · 안내 · 버튼 · 다른 계정 ── */
function OnboardingForm({ name, setName, terms, setTerms, privacy, setPrivacy, dark }) {
  const ready = name.trim().length > 0 && terms && privacy;
  const [focus, setFocus] = React.useState(false);
  const ink = dark ? 'var(--color-stage-ink-2)' : 'var(--color-ink)';
  const muted = dark ? 'var(--color-stage-muted-2)' : 'var(--color-muted)';
  const faint = dark ? 'var(--color-stage-muted)' : 'var(--color-faint)';
  const Check = ({ on }) => on
    ? <span style={{ display: 'inline-flex', flexShrink: 0, width: 16, height: 16, alignItems: 'center', justifyContent: 'center', borderRadius: '50%', background: dark ? 'var(--color-accent)' : 'var(--color-ink)', color: '#fff', fontSize: 9 }}>✓</span>
    : <span style={{ display: 'inline-block', flexShrink: 0, width: 16, height: 16, borderRadius: '50%', border: '1.5px solid ' + (dark ? 'var(--color-stage-line)' : 'var(--color-line)'), boxSizing: 'border-box' }} />;
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <label htmlFor="onboard-name" style={{ fontSize: 13, fontWeight: 600, color: ink }}>이름</label>
        <input id="onboard-name" value={name} onChange={e => setName(e.target.value)} placeholder="예: 박지원" autoFocus onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
          style={{ font: 'inherit', fontSize: 14.5, color: ink, background: dark ? 'var(--color-stage-surface)' : 'var(--color-surface)', border: '1px solid ' + (focus ? (dark ? 'var(--color-stage-ink)' : 'var(--color-ink)') : (dark ? 'var(--color-stage-line)' : 'var(--color-field)')), borderRadius: 'var(--radius-control)', padding: '12px 13px', outline: 'none', width: '100%', boxSizing: 'border-box' }} />
      </div>
      <div style={{ marginTop: 22, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {[['이용약관에 동의합니다', terms, () => setTerms(v => !v)], ['개인정보 수집·이용에 동의합니다', privacy, () => setPrivacy(v => !v)]].map(([label, checked, toggle]) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button type="button" onClick={toggle} aria-pressed={checked} style={{ display: 'flex', alignItems: 'center', gap: 10, textAlign: 'left', fontSize: 13.5, color: ink }}><Check on={checked} />{label}</button>
            <div style={{ flex: 1 }} />
            <a href="#" onClick={e => e.preventDefault()} style={{ fontSize: 12.5, color: faint, textDecoration: 'underline' }}>전문 보기</a>
          </div>
        ))}
        <p style={{ margin: 0, fontSize: 12, lineHeight: 1.6, color: faint }}>면접 중 음성과 웹캠 영상이 기록되고, 분석을 위해 Google Gemini로 처리됩니다.</p>
      </div>
      <button disabled={!ready} style={{ marginTop: 26, height: 50, fontSize: 14.5, fontWeight: 600, color: '#fff', background: ready ? (dark ? 'var(--color-accent)' : 'var(--color-ink)') : (dark ? 'var(--color-stage-line)' : 'var(--color-faintest)'), border: 0, borderRadius: 'var(--radius-control)', cursor: ready ? 'pointer' : 'default', transition: 'background .3s' }}>동의하고 시작하기</button>
      <button type="button" style={{ marginTop: 16, alignSelf: 'flex-start', fontSize: 12.5, color: faint }}>다른 계정으로 로그인</button>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   3c · 두 단계 — 이름 → 동의. 한 화면에 한 질문. 진행 점 두 개.
   ═══════════════════════════════════════════════════════════════ */
function OnboardingSteps() {
  const [step, setStep] = React.useState(0);
  const [name, setName] = React.useState('');
  const [terms, setTerms] = React.useState(false);
  const [privacy, setPrivacy] = React.useState(false);
  const [focus, setFocus] = React.useState(false);
  const g = givenName(name);
  const Check = ({ on }) => on
    ? <span style={{ display: 'inline-flex', flexShrink: 0, width: 16, height: 16, alignItems: 'center', justifyContent: 'center', borderRadius: '50%', background: 'var(--color-ink)', color: '#fff', fontSize: 9 }}>✓</span>
    : <span style={{ display: 'inline-block', flexShrink: 0, width: 16, height: 16, borderRadius: '50%', border: '1.5px solid var(--color-line)', boxSizing: 'border-box' }} />;
  return (
    <main style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--color-bg)', wordBreak: 'keep-all' }}>
      <div style={{ display: 'flex', alignItems: 'center', padding: '26px 32px' }}><Logo /><div style={{ flex: 1 }} /><div style={{ display: 'flex', gap: 5 }}>{[0, 1].map(i => <span key={i} style={{ width: 22, height: 2.5, background: i <= step ? 'var(--color-ink)' : 'var(--color-field-2)', transition: 'background .3s' }} />)}</div></div>
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 32px 96px' }}>
        {step === 0 ? (
          <div key="s0" style={{ width: 460, maxWidth: '100%', animation: 'dm-fade .3s ease' }}>
            <span style={{ fontSize: 12, fontWeight: 600, letterSpacing: '.05em', color: 'var(--color-accent)' }}>1 / 2</span>
            <h1 style={{ margin: '10px 0 0', fontSize: 30, lineHeight: 1.3, fontWeight: 700, letterSpacing: '-.035em' }}>면접관이 어떻게<br />부르면 좋을까요</h1>
            <p style={{ margin: '14px 0 32px', fontSize: 14.5, lineHeight: 1.7, color: 'var(--color-body-2)' }}>실명으로 적어 주세요.</p>
            <input value={name} onChange={e => setName(e.target.value)} placeholder="예: 박지원" autoFocus onFocus={() => setFocus(true)} onBlur={() => setFocus(false)} onKeyDown={e => { if (e.key === 'Enter' && name.trim()) setStep(1); }}
              style={{ font: 'inherit', fontSize: 22, fontWeight: 600, letterSpacing: '-.02em', color: 'var(--color-ink)', background: 'transparent', border: 0, borderBottom: '2px solid ' + (focus ? 'var(--color-ink)' : 'var(--color-field)'), padding: '10px 0', outline: 'none', width: '100%', transition: 'border-color .2s' }} />
            <div style={{ marginTop: 36, display: 'flex', alignItems: 'center' }}>
              <button type="button" style={{ fontSize: 12.5, color: 'var(--color-faint)' }}>다른 계정으로 로그인</button>
              <div style={{ flex: 1 }} />
              <button disabled={!name.trim()} onClick={() => setStep(1)} style={{ height: 46, padding: '0 28px', fontSize: 14, fontWeight: 600, color: '#fff', background: name.trim() ? 'var(--color-ink)' : 'var(--color-faintest)', border: 0, borderRadius: 'var(--radius-control)', cursor: name.trim() ? 'pointer' : 'default', transition: 'background .3s' }}>다음</button>
            </div>
          </div>
        ) : (
          <div key="s1" style={{ width: 460, maxWidth: '100%', animation: 'dm-fade .3s ease' }}>
            <span style={{ fontSize: 12, fontWeight: 600, letterSpacing: '.05em', color: 'var(--color-accent)' }}>2 / 2</span>
            <h1 style={{ margin: '10px 0 0', fontSize: 30, lineHeight: 1.3, fontWeight: 700, letterSpacing: '-.035em' }}>{g} 님, 시작하기 전에<br />한 가지만 확인해 주세요</h1>
            <p style={{ margin: '14px 0 28px', fontSize: 14.5, lineHeight: 1.7, color: 'var(--color-body-2)' }}>면접 중 음성과 웹캠 영상이 기록되고, 분석을 위해 Google Gemini로 처리됩니다.</p>
            <div style={{ display: 'flex', flexDirection: 'column', borderTop: '1px solid var(--color-line)' }}>
              {[['이용약관에 동의합니다', terms, () => setTerms(v => !v)], ['개인정보 수집·이용에 동의합니다', privacy, () => setPrivacy(v => !v)]].map(([label, checked, toggle]) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '16px 0', borderBottom: '1px solid var(--color-line)' }}>
                  <button type="button" onClick={toggle} aria-pressed={checked} style={{ display: 'flex', alignItems: 'center', gap: 12, textAlign: 'left', fontSize: 14.5, color: 'var(--color-ink)' }}><Check on={checked} />{label}</button>
                  <div style={{ flex: 1 }} />
                  <a href="#" onClick={e => e.preventDefault()} style={{ fontSize: 12.5, color: 'var(--color-faint)', textDecoration: 'underline' }}>전문 보기</a>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 32, display: 'flex', alignItems: 'center' }}>
              <button type="button" onClick={() => setStep(0)} style={{ fontSize: 13, color: 'var(--color-muted)' }}>← 이름 고치기</button>
              <div style={{ flex: 1 }} />
              <button disabled={!(terms && privacy)} style={{ height: 46, padding: '0 28px', fontSize: 14, fontWeight: 600, color: '#fff', background: terms && privacy ? 'var(--color-ink)' : 'var(--color-faintest)', border: 0, borderRadius: 'var(--radius-control)', cursor: terms && privacy ? 'pointer' : 'default', transition: 'background .3s' }}>동의하고 시작하기</button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<OnboardingSteps />);
