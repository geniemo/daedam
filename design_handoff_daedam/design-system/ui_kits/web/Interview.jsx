// 면접 화면 — 확정안 D v2. 정지한 키라이트, 무광 유리 구체, 구체 아래 붙은 질문(Pretendard 25/600), 모래색 파형, 셀프뷰 240×180.
// 거울 배치: 웹캠이 가운데로, 구체는 우상단 92로 — 두 상자가 .45s에 자리를 트레이드하고 질문은 가운데 것 아래를 따라간다.
const D = { bg: 'var(--stage-bg)', ink: 'var(--stage-ink-warm)', paper: 'var(--stage-paper)', dim: 'var(--stage-dim)', dim2: 'var(--stage-dim-2)', line: 'rgba(255,255,255,.12)', amber: 'var(--stage-amber)', mint: 'var(--stage-mint)', sand: 'var(--stage-sand)' };
const SWAP = 'left .45s ease-in-out, top .45s ease-in-out, width .45s ease-in-out, height .45s ease-in-out, transform .45s ease-in-out, opacity .45s ease';
const SPHERE = 216, PIP = 92, GAP = 44, QH = 100;

function Breathe({ level, speaking, base = 1, gain = .16, minOp = .6, maxOp = 1, style }) {
  const el = React.useRef(null); const sp = React.useRef(speaking); sp.current = speaking;
  React.useEffect(() => { let raf; const loop = () => { if (el.current) { const l = sp.current ? level.current.output : level.current.input * .35; el.current.style.transform = 'scale(' + (base + l * gain) + ')'; el.current.style.opacity = String(minOp + l * (maxOp - minOp)); } raf = requestAnimationFrame(loop); }; raf = requestAnimationFrame(loop); return () => cancelAnimationFrame(raf); }, []);
  return <div ref={el} style={style} />;
}
/** 무광 유리 구체 + 안의 불. size로 축소(PiP 92). */
function Wave({ level }) {
  const bars = React.useRef([]);
  React.useEffect(() => { let raf; const loop = () => { const t = performance.now() / 1000; bars.current.forEach((el, i) => { if (!el) return; const ph = Math.sin(t * 6 + i * .7) * .5 + .5; el.style.transform = 'scaleY(' + Math.min(1, .18 + level.current.input * (.35 + .65 * ph) * .82) + ')'; }); raf = requestAnimationFrame(loop); }; raf = requestAnimationFrame(loop); return () => cancelAnimationFrame(raf); }, []);
  return <div style={{ display: 'flex', alignItems: 'center', gap: 3, height: 40 }}>{Array.from({ length: 16 }, (_, i) => <div key={i} ref={el => bars.current[i] = el} style={{ width: 3, height: 40, background: D.sand, transformOrigin: 'center', transform: 'scaleY(.18)', willChange: 'transform' }} />)}</div>;
}
const Act = ({ onClick, dim, children }) => <button onClick={onClick} style={{ fontSize: 12, color: dim ? D.dim2 : D.ink }}>{children}</button>;
const Sep = ({ hide }) => hide ? null : <span style={{ color: 'rgba(255,255,255,.18)' }}>·</span>;
const Rec = () => <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 5, height: 5, borderRadius: '50%', background: D.mint }} /><span style={{ fontSize: 11, color: D.dim }}>시선·표정 기록 중</span></div>;

function Interview({ company, reconnecting = false, onEnd }) {
  const [phase, setPhase] = React.useState('speaking');
  const [elapsed, setElapsed] = React.useState(0);
  const [qi, setQi] = React.useState(0);
  const [camera, setCamera] = React.useState(true);
  const [selfVisible, setSelfVisible] = React.useState(true);
  const [mirror, setMirror] = React.useState(false);
  const levels = React.useRef({ input: 0, output: 0 });
  const phaseRef = React.useRef(phase); phaseRef.current = phase;
  const area = React.useRef(null);
  const [box, setBox] = React.useState(() => ({ w: window.innerWidth, h: Math.max(320, window.innerHeight - 64 - 104 - 60) }));
  const questions = ['먼저 간단히 자기소개 부탁드립니다.', '여러 회사 중 저희 ' + company + '에 지원하신 이유가 무엇인가요?', '지원서에 적으신 물류 데이터 분석 프로젝트에서 본인이 맡은 역할을 설명해 주세요.'];
  React.useEffect(() => {
    const t = setInterval(() => setElapsed(e => { const n = e + 1, c = n % 14; setPhase(c < 5 ? 'speaking' : 'listening'); if (c === 0) setQi(q => (q + 1) % questions.length); return n; }), 1000);
    let raf; const loop = () => { const s = performance.now() / 1000; const a = Math.max(0, Math.sin(s * 5.3) * .5 + Math.sin(s * 9.1) * .3 + .3); levels.current = phaseRef.current === 'speaking' ? { output: a, input: 0 } : { output: 0, input: a }; raf = requestAnimationFrame(loop); }; raf = requestAnimationFrame(loop);
    const measure = () => { if (area.current) setBox({ w: area.current.clientWidth, h: area.current.clientHeight }); }; measure(); const ro = new ResizeObserver(measure); if (area.current) ro.observe(area.current); window.addEventListener('resize', measure);
    return () => { clearInterval(t); cancelAnimationFrame(raf); ro.disconnect(); window.removeEventListener('resize', measure); };
  }, []);
  const sp = phase === 'speaking';
  const narrow = box.w < 600; // 좁은 무대 — 셀프뷰 132×99, PiP 64, 질문 18px, 여백 16
  const pip = narrow ? 64 : PIP, edge = narrow ? 16 : 30, camW = narrow ? 132 : 240, camH = narrow ? 99 : 180;
  const clock = Math.floor(elapsed / 60) + ':' + String(elapsed % 60).padStart(2, '0');
  // 가운데 덩이 = 초점(구체 또는 웹캠) + 44 + 질문. 세로 중앙.
  const sphere = Math.max(narrow ? 120 : 150, Math.min(SPHERE, Math.round(box.h * .4), Math.round(box.w * .5)));
  const mirrorW = Math.min(Math.round(Math.max(160, Math.min(420, box.h - 60 - GAP - QH)) * 4 / 3), box.w - (narrow ? 32 : 64)), mirrorH = Math.round(mirrorW * 3 / 4);
  const focusH = mirror ? mirrorH : sphere;
  const blockTop = Math.max(narrow ? 32 : 60, Math.round((box.h - (focusH + GAP + QH)) / 2));
  const qTop = blockTop + focusH + GAP;
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 60, display: 'flex', flexDirection: 'column', background: D.bg, color: D.ink, overflow: 'hidden', ...(window.__DAEDAM_W ? { left: '50%', right: 'auto', width: window.__DAEDAM_W, transform: 'translateX(-50%)' } : {}) }}>
      <style>{`@keyframes dLight{from{opacity:0}to{opacity:1}}`}</style>
      <div style={{ pointerEvents: 'none', position: 'absolute', left: '50%', top: '-20%', width: 1100, height: 700, transform: 'translateX(-50%)', background: 'radial-gradient(ellipse at 50% 0%, rgba(var(--stage-keylight-rgb),' + (sp ? '.10' : '.06') + '), transparent 62%)', transition: 'background 1.4s ease' }} />
      <div style={{ position: 'relative', zIndex: 5, display: 'flex', alignItems: 'center', padding: narrow ? '14px 16px' : '22px 30px' }}>
        <span style={{ width: 7, height: 7, borderRadius: '50%', background: sp ? D.amber : D.mint, boxShadow: '0 0 10px ' + (sp ? D.amber : D.mint), transition: 'background .6s, box-shadow .6s' }} />
        <span style={{ marginLeft: 9, fontSize: 13.5 }}>{sp ? '면접관이 말하고 있습니다' : '듣고 있습니다'}</span>
        {reconnecting && <span style={{ marginLeft: 8, fontSize: 12.5, color: D.dim }}>· 연결을 복구하는 중입니다</span>}
        {mirror && <><span style={{ width: 1, height: 12, background: 'rgba(255,255,255,.18)', margin: '0 12px' }} /><span className="num" style={{ fontSize: 13, color: D.dim }}>{clock}</span></>}
        <div style={{ flex: 1 }} />
        {!mirror && <span className="num" style={{ fontSize: 13, color: D.dim }}>{clock}</span>}
      </div>
      <div ref={area} style={{ position: 'relative', flex: 1, minHeight: 0 }}>
        {/* 구체 — 기본 가운데, 거울이면 우상단 92 */}
        <div style={{ position: 'absolute', width: sphere, height: sphere, transformOrigin: 'top left', transition: SWAP, zIndex: mirror ? 4 : 1, ...(mirror ? { left: 'calc(100% - ' + edge + 'px - ' + pip + 'px)', top: narrow ? 8 : 14, transform: 'translate(0,0) scale(' + (pip / sphere) + ')' } : { left: '50%', top: blockTop, transform: 'translate(-50%, 0) scale(1)' }) }}>
          <Avatar levels={levels} speaking={sp} size={sphere} />
        </div>
        {/* 웹캠 — 기본 우상단 240×180, 거울이면 가운데 4:3 */}
        {camera && (
          <div style={{ position: 'absolute', display: 'flex', flexDirection: 'column', gap: 7, transition: SWAP, zIndex: mirror ? 2 : 4, ...(mirror ? { left: '50%', top: blockTop, width: mirrorW, transform: 'translateX(-50%)' } : { left: 'calc(100% - ' + edge + 'px - ' + camW + 'px)', top: narrow ? 8 : 14, width: camW, transform: 'translateX(0)' }) }}>
            <div style={{ position: 'relative', overflow: 'hidden', borderRadius: 8, border: '1px solid ' + D.line, width: '100%', height: mirror ? mirrorH : camH, background: 'rgba(0,0,0,.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'height .45s ease-in-out', boxShadow: '0 30px 70px -30px rgba(0,0,0,.9)' }}>
              {mirror || selfVisible ? <span style={{ fontSize: 11, color: D.dim }}>웹캠 · 거울 반전</span> : <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5, textAlign: 'center' }}><span style={{ fontSize: 12, color: D.ink }}>내 화면을 가렸습니다</span><span style={{ fontSize: 11, color: D.dim }}>촬영은 계속됩니다</span></div>}
            </div>
            <div key={String(mirror)} style={{ display: 'flex', flexDirection: 'column', gap: 5, animation: 'dm-fade .3s ease .3s both' }}>
              {mirror ? (
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 9, rowGap: 4, whiteSpace: 'nowrap' }}><Rec /><div style={{ flex: 1 }} /><Act onClick={() => setMirror(false)}>면접관 크게 보기</Act><Sep /><Act onClick={() => setCamera(false)} dim>카메라 끄기</Act></div>
              ) : (<>
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}><Rec /></div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: narrow ? 4 : 9, whiteSpace: 'nowrap', ...(narrow ? { flexDirection: 'column', alignItems: 'flex-end' } : {}) }}><Act onClick={() => setMirror(true)}>내 모습 크게 보기</Act><Sep hide={narrow} /><Act onClick={() => setSelfVisible(v => !v)}>{selfVisible ? '내 화면 가리기' : '다시 보기'}</Act><Sep hide={narrow} /><Act onClick={() => setCamera(false)} dim>카메라 끄기</Act></div>
              </>)}
            </div>
          </div>
        )}
        {/* 질문 — 가운데 것(구체 또는 웹캠) 바로 아래 44px. 두 줄 높이를 늘 비워 둔다 */}
        <div style={{ position: 'absolute', left: '50%', top: qTop, transform: 'translateX(-50%)', width: narrow ? 'calc(100% - 32px)' : 'min(680px, calc(100% - 64px))', transition: 'top .45s ease-in-out', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18, minHeight: QH }}>
          <span style={{ width: 28, height: 1, background: sp ? D.amber : D.mint, transition: 'background 1s ease' }} />
          <p key={qi} style={{ margin: 0, textAlign: 'center', fontSize: narrow ? 18 : 'clamp(20px, 2.7vh, 25px)', lineHeight: 1.55, fontWeight: 600, letterSpacing: '-.02em', color: D.paper, wordBreak: 'keep-all', animation: 'dm-fade .6s ease' }}>{questions[qi]}</p>
        </div>
      </div>
      <div style={{ position: 'relative', display: 'flex', height: narrow ? 84 : 104, alignItems: 'center', justifyContent: 'center' }}>
        {sp ? <span style={{ fontSize: 12.5, color: D.dim2, letterSpacing: '.02em' }}>답변이 끝나면 마이크가 열립니다</span> : <Wave level={levels} />}
      </div>
      <div style={{ position: 'relative', padding: narrow ? '0 16px 20px' : '0 30px 26px', display: 'flex', justifyContent: 'flex-end' }}>
        <button onClick={onEnd} style={{ font: 'inherit', fontSize: 13, color: D.dim, background: 'transparent', border: '1px solid ' + D.line, borderRadius: 999, padding: '10px 20px', cursor: 'pointer' }}>종료하고 리포트 받기</button>
      </div>
    </div>
  );
}
window.DaedamInterview = Interview;
