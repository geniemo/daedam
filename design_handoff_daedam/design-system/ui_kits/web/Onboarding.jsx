// Recreation of web/src/screens/Onboarding.tsx (3c 두 단계, 구현본). 이름 → 동의. 단계는 state 하나.
const StepMark = ({ children }) => <span className="num" style={{ fontSize: 12, fontWeight: 600, letterSpacing: '.05em', color: 'var(--color-accent)' }}>{children}</span>;
const StepButton = ({ disabled, onClick, children }) => (
  <button disabled={disabled} onClick={onClick} style={{ height: 46, borderRadius: 'var(--radius-control)', padding: '0 28px', fontSize: 14, fontWeight: 600, color: '#fff', background: disabled ? 'var(--color-faintest)' : 'var(--color-ink)', cursor: disabled ? 'default' : 'pointer', transition: 'background .3s' }}>{children}</button>
);
const givenName = name => { const t = name.trim(); return /^[가-힣]{3,}$/.test(t) ? t.slice(-2) : t; };
const h1S = { margin: '10px 0 0', fontSize: 30, lineHeight: 1.3, fontWeight: 700, letterSpacing: '-.035em', color: 'var(--color-ink)' };
const pS = { fontSize: 14.5, lineHeight: 1.7, color: 'var(--color-body-2)' };
function Onboarding({ onDone }) {
  const narrow = useNarrow();
  const [step, setStep] = React.useState(0);
  const [name, setName] = React.useState('');
  const [terms, setTerms] = React.useState(false);
  const [privacy, setPrivacy] = React.useState(false);
  const [focus, setFocus] = React.useState(false);
  const [sending, setSending] = React.useState(false);
  const named = name.trim().length > 0, agreed = terms && privacy;
  const submit = () => { if (!agreed || sending) return; setSending(true); setTimeout(() => onDone && onDone(name), 900); };
  return (
    <main style={{ display: 'flex', minHeight: '100vh', flexDirection: 'column', wordBreak: 'keep-all' }}>
      <div style={{ display: 'flex', alignItems: 'center', padding: narrow ? '18px 20px' : '26px 32px' }}>
        <svg width="26" height="26" viewBox="0 0 24 24" aria-hidden="true" style={{ flexShrink: 0 }}><path d="M9 3.51A9 9 0 0 0 9 20.49Z" fill="var(--color-ink)" /><path d="M10.6 3.11A9 9 0 1 1 10.6 20.89Z" fill="var(--color-accent)" /></svg>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', gap: 5 }}>{[0, 1].map(i => <span key={i} style={{ height: 2.5, width: 22, background: i <= step ? 'var(--color-ink)' : 'var(--color-field-2)', transition: 'background .3s' }} />)}</div>
      </div>
      <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center', padding: narrow ? '0 20px 64px' : '0 32px 96px' }}>
        {step === 0 ? (
          <div key="name" style={{ width: 460, maxWidth: '100%', animation: 'dm-fade .3s ease' }}>
            <StepMark>1 / 2</StepMark>
            <h1 style={h1S}>면접관이 어떻게<br />부르면 좋을까요</h1>
            <p style={{ ...pS, margin: '14px 0 32px' }}>실명으로 적어 주세요.</p>
            <input value={name} onChange={e => setName(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && named) setStep(1); }} onFocus={() => setFocus(true)} onBlur={() => setFocus(false)} placeholder="예: 박지원" aria-label="이름" autoFocus style={{ width: '100%', border: 0, borderBottom: '2px solid ' + (focus ? 'var(--color-ink)' : 'var(--color-field)'), background: 'transparent', padding: '10px 0', fontSize: 22, fontWeight: 600, letterSpacing: '-.02em', color: 'var(--color-ink)', outline: 'none', transition: 'border-color .2s', boxSizing: 'border-box' }} />
            <div style={{ marginTop: 36, display: 'flex', alignItems: 'center' }}>
              <button style={{ fontSize: 12.5, color: 'var(--color-faint)' }}>다른 계정으로 로그인</button>
              <div style={{ flex: 1 }} />
              <StepButton disabled={!named} onClick={() => setStep(1)}>다음</StepButton>
            </div>
          </div>
        ) : (
          <div key="consent" style={{ width: 460, maxWidth: '100%', animation: 'dm-fade .3s ease' }}>
            <StepMark>2 / 2</StepMark>
            <h1 style={h1S}>{givenName(name)} 님, 시작하기 전에<br />한 가지만 확인해 주세요</h1>
            <p style={{ ...pS, margin: '14px 0 28px' }}>면접 중 음성과 웹캠 영상이 기록되고, 분석을 위해 Google Gemini로 처리됩니다.</p>
            <div style={{ display: 'flex', flexDirection: 'column', borderTop: '1px solid var(--color-line)' }}>
              {[['이용약관에 동의합니다', terms, () => setTerms(v => !v)], ['개인정보 수집·이용에 동의합니다', privacy, () => setPrivacy(v => !v)]].map(([label, checked, toggle]) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 12, borderBottom: '1px solid var(--color-line)', padding: '16px 0' }}>
                  <button onClick={toggle} aria-pressed={checked} style={{ display: 'flex', alignItems: 'center', gap: 12, textAlign: 'left', fontSize: 14.5, color: 'var(--color-ink)' }}>{checked ? <CheckDot size={16} /> : <EmptyDot size={16} />}{label}</button>
                  <div style={{ flex: 1 }} />
                  <a href="#" onClick={e => e.preventDefault()} style={{ fontSize: 12.5, color: 'var(--color-faint)', textDecoration: 'underline' }}>전문 보기</a>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 32, display: 'flex', alignItems: 'center' }}>
              <button onClick={() => setStep(0)} style={{ fontSize: 13, color: 'var(--color-muted)' }}>← 이름 고치기</button>
              <div style={{ flex: 1 }} />
              <StepButton disabled={!agreed || sending} onClick={submit}>{sending ? '저장 중…' : '동의하고 시작하기'}</StepButton>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
window.DaedamOnboarding = Onboarding;
if (document.getElementById('root') && !window.DaedamNoMount) ReactDOM.createRoot(document.getElementById('root')).render(<Onboarding onDone={() => location.reload()} />);
