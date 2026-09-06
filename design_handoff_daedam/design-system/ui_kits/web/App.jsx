// Kit shell — App.tsx routing + Progress.tsx Analyzing. Composes Home / Ready / Interview / Report.
const CARDS = [
  { id: 'nuri', company: '누리테크', role: '서비스기획 · 신입', date: '8월 4일', status: 'ready' },
  { id: 'sejong', company: '세종바이오', role: '마케팅 · 신입', date: '8월 6일', status: 'researching' },
  { id: 'hanbit', company: '한빛금융', role: 'IT기획 · 신입', date: '7월 28일', status: 'done', score: 80, interviewCount: 2 },
  { id: 'oreum', company: '오름소프트', role: '백엔드 개발 · 신입', date: '7월 19일', status: 'done', score: 80, interviewCount: 1 },
  { id: 'daon', company: '다온커머스', role: '데이터 분석 · 신입', date: '7월 12일', status: 'done', analyzed: true, interviewCount: 1 },
];
// hanbit = 영상 있는 리포트(2회차), oreum = 오디오만(답변까지 지표 측정 불가), daon = 답변 없음(silent · 크레딧 반환)
function Analyzing() {
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 60, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 22, background: 'var(--stage-bg)', color: 'var(--stage-ink-warm)', animation: 'dm-fade .8s ease', padding: '0 32px', textAlign: 'center' }}>
      <div style={{ pointerEvents: 'none', position: 'absolute', left: '50%', top: '-20%', width: 1100, height: 700, transform: 'translateX(-50%)', background: 'radial-gradient(ellipse at 50% 0%, rgba(var(--stage-keylight-rgb),.07), transparent 62%)' }} />
      <div style={{ position: 'relative', width: 128, height: 128 }}>
        <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'var(--gradient-sphere)', boxShadow: 'var(--shadow-sphere)', animation: 'dm-breathe 7s ease-in-out infinite' }} />
        <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'var(--gradient-sphere-sheen)' }} />
        <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', opacity: .22, background: 'var(--gradient-voice-amber)', animation: 'dm-breathe 7s ease-in-out infinite' }} />
      </div>
      <h1 style={{ margin: 0, fontSize: 19, fontWeight: 600, color: 'var(--stage-paper)', wordBreak: 'keep-all', maxWidth: 420 }}>면접이 끝났습니다. 수고하셨습니다</h1>
      <p style={{ margin: 0, fontSize: 13.5, color: 'var(--stage-dim)', wordBreak: 'keep-all' }}>답변을 평가 중입니다</p>
      <div style={{ width: 240, height: 2, background: 'rgba(255,255,255,.08)', overflow: 'hidden' }}><div style={{ width: '25%', height: '100%', background: 'var(--stage-amber)', animation: 'dm-slide 1.6s ease-in-out infinite' }} /></div>
    </div>
  );
}
function App() {
  const [screen, setScreen] = React.useState('home');
  const [card, setCard] = React.useState(CARDS[0]);
  const [notice, setNotice] = React.useState(null);
  const go = s => { window.scrollTo(0, 0); setScreen(s); };
  // 문턱 → 무대: 어두운 띠의 자리에서 시작해 화면 전체로 커지는 판(.55s). 끝나면 면접 화면으로.
  const [expand, setExpand] = React.useState(null);
  const enterStage = () => {
    const band = document.querySelector('[data-threshold]'); if (!band) { go('interview'); return; }
    const r = band.getBoundingClientRect();
    // 확장은 단일 마운트 + CSS 키프레임. 상태 쓰기 둘이 경쟁하지 않으므로(rAF vs setTimeout) 덮개가 남을 수 없다.
    setExpand({ x: r.left, y: r.top, w: r.width, h: r.height });
    setTimeout(() => { go('interview'); setExpand(null); }, 460);
  };
  const open = c => { setCard(c); go(c.status === 'ready' ? 'ready' : c.status === 'done' ? 'report' : 'home'); };
  const chrome = screen !== 'interview' && screen !== 'analyzing';
  React.useEffect(() => { if (screen === 'analyzing') { const t = setTimeout(() => go('report'), 2600); return () => clearTimeout(t); } }, [screen]);
  return (
    <div style={{ minHeight: '100vh' }}>
      {chrome && <Chrome name="김서연" credits={7} onHome={() => go('home')} />}
      {screen === 'home' && (<>
        <window.DaedamHome cards={CARDS} notice={notice} onDismissNotice={() => setNotice(null)} onOpen={open} onStart={c => { setCard(c); go('ready'); }} onRegister={() => {}} />
      </>)}
      {screen === 'ready' && <window.DaedamReady card={card} credits={{ balance: 7, interview: 3 }} onBack={() => go('home')} onReview={() => {}} onStart={enterStage} />}
      {screen === 'interview' && <window.DaedamInterview company={card.company} onEnd={() => go('analyzing')} />}
      {screen === 'analyzing' && <Analyzing />}
      {expand && (<>
        <style>{`@keyframes dExpand{from{left:${expand.x}px;top:${expand.y}px;width:${expand.w}px;height:${expand.h}px;border-radius:4px}to{left:0;top:0;width:100vw;height:100vh;border-radius:0}}`}</style>
        <div style={{ position: 'fixed', zIndex: 70, pointerEvents: 'none', background: 'var(--stage-bg)', left: 0, top: 0, width: '100vw', height: '100vh', animation: 'dExpand .45s cubic-bezier(.2,.7,.2,1) both' }} />
      </>)}
      {screen === 'report' && (card.id === 'daon'
        ? <window.DaedamReportEmpty status="silent" refunded sessions={[]} onBack={() => go('home')} onAgain={() => go('ready')} />
        : <window.DaedamReport card={card} hasVideo={card.id !== 'oreum'} sessions={card.id === 'hanbit' ? window.DaedamSessions : [window.DaedamSessions[0]]} onBack={() => go('home')} onAgain={() => go('ready')} />)}
    </div>
  );
}
ReactDOM.createRoot(document.getElementById('root')).render(<App />);
