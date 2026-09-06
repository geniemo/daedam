// Recreation of web/src/screens/Landing.tsx (2a 라이브 데모, 구현본). Avatar/Waveform from components/stage; Metric compact from Report.jsx.
const KakaoMark = ({ size = 18 }) => <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true"><path d="M12 18.75c-.591 0-1.1697-.0413-1.7317-.1209-.5626.3965-3.813 2.6797-4.1198 2.7225 0 0-.1258.0489-.2328-.0141s-.0876-.2282-.0876-.2282c.0322-.2198.8426-3.0183.992-3.5333-2.7452-1.36-4.5701-3.7686-4.5701-6.5135C2.25 6.8168 6.6152 3.375 12 3.375s9.75 3.4418 9.75 7.6875c0 4.2457-4.3652 7.6875-9.75 7.6875z" fill="#191600" /></svg>;
const GoogleMark = ({ size = 18 }) => <svg viewBox="0 0 118 120" width={size} height={size} aria-hidden="true"><path d="M117.6,61.3636364 C117.6,57.1090909 117.218182,53.0181818 116.509091,49.0909091 L60,49.0909091 L60,72.3 L92.2909091,72.3 C90.9,79.8 86.6727273,86.1545455 80.3181818,90.4090909 L80.3181818,105.463636 L99.7090909,105.463636 C111.054545,95.0181818 117.6,79.6363636 117.6,61.3636364 L117.6,61.3636364 Z" fill="#4285F4" /><path d="M60,120 C76.2,120 89.7818182,114.627273 99.7090909,105.463636 L80.3181818,90.4090909 C74.9454545,94.0090909 68.0727273,96.1363636 60,96.1363636 C44.3727273,96.1363636 31.1454545,85.5818182 26.4272727,71.4 L6.38181818,71.4 L6.38181818,86.9454545 C16.2545455,106.554545 36.5454545,120 60,120 L60,120 Z" fill="#34A853" /><path d="M26.4272727,71.4 C25.2272727,67.8 24.5454545,63.9545455 24.5454545,60 C24.5454545,56.0454545 25.2272727,52.2 26.4272727,48.6 L26.4272727,33.0545455 L6.38181818,33.0545455 C2.31818182,41.1545455 0,50.3181818 0,60 C0,69.6818182 2.31818182,78.8454545 6.38181818,86.9454545 L26.4272727,71.4 L26.4272727,71.4 Z" fill="#FBBC05" /><path d="M60,23.8636364 C68.8090909,23.8636364 76.7181818,26.8909091 82.9363636,32.8363636 L100.145455,15.6272727 C89.7545455,5.94545455 76.1727273,0 60,0 C36.5454545,0 16.2545455,13.4454545 6.38181818,33.0545455 L26.4272727,48.6 C31.1454545,34.4181818 44.3727273,23.8636364 60,23.8636364 L60,23.8636364 Z" fill="#EA4335" /></svg>;
const LABEL = { kakao: '카카오로 시작하기', google: 'Google로 시작하기' };
function LoginButton({ provider }) {
  const kakao = provider === 'kakao', Mark = kakao ? KakaoMark : GoogleMark;
  return (
    <a href="#" onClick={e => e.preventDefault()} style={{ position: 'relative', display: 'flex', height: 50, minWidth: 236, alignItems: 'center', justifyContent: 'center', borderRadius: 'var(--radius-control)', paddingLeft: 44, paddingRight: 20, fontSize: 14.5, fontWeight: 600, color: kakao ? 'var(--color-kakao-ink)' : 'var(--color-ink)', background: kakao ? 'var(--color-kakao)' : 'var(--color-surface)', border: kakao ? 0 : '1px solid var(--color-field)', boxSizing: 'border-box' }}>
      <span style={{ position: 'absolute', left: 16, display: 'flex', alignItems: 'center' }}><Mark /></span>{LABEL[provider]}
    </a>
  );
}
const Logo = () => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
    <svg width="26" height="26" viewBox="0 0 24 24" aria-hidden="true" style={{ flexShrink: 0 }}><path d="M9 3.51A9 9 0 0 0 9 20.49Z" fill="var(--color-ink)" /><path d="M10.6 3.11A9 9 0 1 1 10.6 20.89Z" fill="var(--color-accent)" /></svg>
    <span style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-.02em', color: 'var(--color-ink)' }}>대담</span>
  </div>
);
const DEMO_INTERVAL_MS = 5200;
/* 제목의 회사 — 2.6초마다 바뀐다(데모 창 주기의 절반). 이름은 6자 이하로 둔다: 44px 한 줄(약 520px)에 "미리 + 타일 + 이름"이 들어가야 한다.
   mark는 로고 자리의 모노그램. 실제 로고는 상표라 여기서 그리지 않는다 — data-logo-slot 타일을 이미지로 바꿔 넣는다. */
const COMPANY_INTERVAL_MS = 2600;
const COMPANIES = [{ key: 'skhynix', name: 'SK하이닉스', mark: 'SK' }, { key: 'samsung', name: '삼성전자', mark: '삼' }, { key: 'naver', name: '네이버', mark: 'N' }, { key: 'hyundai', name: '현대자동차', mark: '현' }, { key: 'kakao', name: '카카오', mark: 'K' }, { key: 'lg', name: 'LG전자', mark: 'LG' }];
/** 로고 슬롯. 바깥 <image-slot>에 실제 로고 파일을 끌어다 놓으면 저장되고, 비어 있을 땐 모노그램이 보인다. 최종 서버에서는 <img src="/logos/{key}.svg">으로. */
const CompanyLogo = ({ company, size = 38, mono = false, variant = 'strip' }) => (
  <span style={{ position: 'relative', display: 'inline-flex', width: size, height: size, flexShrink: 0, alignItems: 'center', justifyContent: 'center', borderRadius: 'var(--radius-card)', border: '1px solid var(--color-line)', background: 'var(--color-surface)', overflow: 'hidden', boxSizing: 'border-box' }}>
    <span style={{ fontSize: Math.round(size * 0.42), fontWeight: 700, letterSpacing: '-.02em', lineHeight: 1, color: 'var(--color-ink)' }}>{company.mark}</span>
    {/* 빈 슬롯은 자기 점선·안내문을 그리므로 채워질 때까지 투명하게 둔다(landing.html의 image-slot:not([data-filled]) 규칙). 투명해도 드롭은 받는다. */}
    <image-slot id={'logo-' + variant + '-' + company.key} shape="rect" fit="contain" placeholder={company.name + ' 로고'} className={mono ? 'logo-mono' : ''} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', background: 'transparent' }}></image-slot>
  </span>
);
const Monogram = ({ mark }) => <CompanyLogo company={COMPANIES.find(c => c.mark === mark)} variant="hero" />;
const DEMOS = [
  { company: '누리테크', role: '서비스기획', question: '저희가 올해 공개한 파트너 정산 서비스를 써보셨다면, 어떤 점을 먼저 개선하시겠습니까?', source: '2026년 3월 보도자료 · 채용공고 우대사항' },
  { company: '세종바이오', role: '마케팅', question: '지원서에 쓰신 SNS 캠페인 경험을, 처방약 광고 규제가 있는 저희 업계에서는 어떻게 바꿔 적용하시겠어요?', source: '지원서 경험 2 · 회사 IR 자료' },
  { company: '한빛금융', role: 'IT기획', question: '작년 저희 앱 장애 때 고객 공지가 늦었다는 지적이 있었는데, 기획자로서 무엇을 먼저 바꾸시겠습니까?', source: '2025년 11월 뉴스 · 인재상 "책임"' },
  { company: '오름소프트', role: '백엔드 개발', question: '지원서의 트래픽 3배 처리 경험에서, 병목이 DB였는지 애플리케이션이었는지 어떻게 판단하셨나요?', source: '지원서 경험 1 · 기술 블로그' },
];
function useTyped(text, speedMs = 28) {
  const [shown, setShown] = React.useState(0);
  React.useEffect(() => { setShown(0); let i = 0; const t = setInterval(() => { i += 1; setShown(i); if (i >= text.length) clearInterval(t); }, speedMs); return () => clearInterval(t); }, [text, speedMs]);
  return text.slice(0, shown);
}
/** 진폭을 따라 부푸는 층 — 무대 D와 같은 방식(ref→style). */
function Glow({ level, speaking, base = 1, gain = .16, minOp = .6, maxOp = 1, style }) {
  const el = React.useRef(null); const sp = React.useRef(speaking); sp.current = speaking;
  React.useEffect(() => { let raf; const loop = () => { if (el.current) { const l = sp.current ? level.current : level.current * .35; el.current.style.transform = 'scale(' + (base + l * gain) + ')'; el.current.style.opacity = String(minOp + l * (maxOp - minOp)); } raf = requestAnimationFrame(loop); }; raf = requestAnimationFrame(loop); return () => cancelAnimationFrame(raf); }, []);
  return <div ref={el} style={style} />;
}
/**
 * 면접 무대 D의 축소판 — 실제 면접장과 같은 것을 보여준다. 정지한 키라이트, 무광 유리 구체, 구체 아래 붙은 질문.
 * 타이핑이 끝나면 "듣고 있습니다"로 넘어가고 파형이 돈다.
 */
function LiveDemo({ demo }) {
  const typed = useTyped(demo.question), done = typed.length >= demo.question.length, sp = !done;
  const level = React.useRef(0);
  React.useEffect(() => { let raf; const loop = () => { const s = performance.now() / 1000; level.current = Math.max(0, Math.sin(s * 5.3) * .5 + Math.sin(s * 9.1) * .3 + .3); raf = requestAnimationFrame(loop); }; raf = requestAnimationFrame(loop); return () => cancelAnimationFrame(raf); }, []);
  const bars = React.useRef([]);
  React.useEffect(() => { let raf; const loop = () => { const t = performance.now() / 1000; bars.current.forEach((el, i) => { if (!el) return; const ph = Math.sin(t * 6 + i * .7) * .5 + .5; el.style.transform = 'scaleY(' + Math.min(1, .18 + level.current * (.35 + .65 * ph) * .82) + ')'; }); raf = requestAnimationFrame(loop); }; raf = requestAnimationFrame(loop); return () => cancelAnimationFrame(raf); }, []);
  const S = 150; // 구체 지름
  return (
    <div style={{ position: 'relative', display: 'flex', minHeight: 440, width: '100%', maxWidth: 640, flexDirection: 'column', overflow: 'hidden', borderRadius: 'var(--radius-card)', border: '1px solid rgba(255,255,255,.08)', background: 'var(--stage-bg)', color: 'var(--stage-ink-warm)', boxSizing: 'border-box' }}>
      {/* 키라이트 — 정지, 말할 때 조금 따뜻해진다 */}
      <div style={{ pointerEvents: 'none', position: 'absolute', left: '50%', top: '-30%', width: 760, height: 460, transform: 'translateX(-50%)', background: 'radial-gradient(ellipse at 50% 0%, rgba(var(--stage-keylight-rgb),' + (sp ? '.10' : '.06') + '), transparent 62%)', transition: 'background 1.4s ease' }} />
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center', padding: '18px 22px' }}>
        <span style={{ width: 7, height: 7, borderRadius: '50%', background: sp ? 'var(--stage-amber)' : 'var(--stage-mint)', boxShadow: '0 0 10px ' + (sp ? 'var(--stage-amber)' : 'var(--stage-mint)'), transition: 'background .6s, box-shadow .6s' }} />
        <span style={{ marginLeft: 9, fontSize: 13, color: 'var(--stage-ink-warm)' }}>{done ? '듣고 있습니다' : '면접관이 말하고 있습니다'}</span>
        <div style={{ flex: 1 }} />
        <span key={demo.company} style={{ fontSize: 12.5, color: 'var(--stage-dim)', animation: 'dm-fade .4s ease' }}>{demo.company} · {demo.role}</span>
      </div>
      <div style={{ position: 'relative', display: 'flex', flex: 1, flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 28, padding: '8px 24px 0' }}>
        <div style={{ position: 'relative', width: S, height: S, flexShrink: 0 }}>
          <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'var(--gradient-sphere)', boxShadow: 'inset 0 1px 0 rgba(255,255,255,.10), inset 0 -18px 34px rgba(0,0,0,.42), 0 22px 50px -22px rgba(0,0,0,.9)', animation: 'dm-breathe 6s ease-in-out infinite' }} />
          <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'var(--gradient-sphere-sheen)' }} />
          <Glow level={level} speaking={sp} minOp={sp ? .6 : .28} maxOp={sp ? 1 : .5} style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: sp ? 'var(--gradient-voice-amber)' : 'var(--gradient-voice-mint)', transition: 'background 1.4s ease, opacity 1s ease' }} />
          <div style={{ position: 'absolute', inset: -76, borderRadius: '50%', background: sp ? 'radial-gradient(circle, rgba(var(--stage-keylight-rgb),.13), transparent 60%)' : 'radial-gradient(circle, rgba(var(--stage-mint-rgb),.09), transparent 60%)', transition: 'background 1.4s ease' }} />
        </div>
        {/* 질문 — 구체 바로 아래. 두 줄 높이를 늘 비워 둔다 */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, minHeight: 78, maxWidth: 520 }}>
          <span style={{ width: 24, height: 1, background: sp ? 'var(--stage-amber)' : 'var(--stage-mint)', transition: 'background 1s ease' }} />
          <p style={{ margin: 0, textAlign: 'center', fontSize: 18, lineHeight: 1.6, fontWeight: 600, letterSpacing: '-.02em', color: 'var(--stage-paper)', wordBreak: 'keep-all' }}>{typed}{!done && <span style={{ marginLeft: 2, display: 'inline-block', width: 2, height: 16, verticalAlign: -2, background: 'var(--stage-amber)' }} />}</p>
        </div>
      </div>
      <div style={{ position: 'relative', display: 'flex', height: 72, alignItems: 'center', justifyContent: 'center' }}>
        {done ? <div style={{ display: 'flex', alignItems: 'center', gap: 3, height: 28 }}>{Array.from({ length: 16 }, (_, i) => <div key={i} ref={el => bars.current[i] = el} style={{ width: 3, height: 28, background: 'var(--stage-sand)', transformOrigin: 'center', transform: 'scaleY(.18)', willChange: 'transform' }} />)}</div> : <span style={{ fontSize: 12, color: 'var(--stage-dim-2)' }}>답변이 끝나면 마이크가 열립니다</span>}
      </div>
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 8, padding: '0 22px 16px' }}><span style={{ fontSize: 12.5, color: 'var(--stage-dim)' }}>이 질문의 출처</span><span key={demo.company} style={{ fontSize: 12.5, color: 'var(--stage-ink-warm)', animation: 'dm-fade .4s ease' }}>{demo.source}</span></div>
    </div>
  );
}
function StepFrame({ label, title, body, children }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '360px minmax(0,1fr)', alignItems: 'center', gap: 56, borderTop: '1px solid var(--color-line)', padding: '64px 0' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <span className="num" style={{ fontSize: 12, fontWeight: 600, letterSpacing: '.05em', color: 'var(--color-accent)' }}>{label}</span>
        <h2 style={{ margin: 0, fontSize: 28, lineHeight: 1.3, fontWeight: 700, letterSpacing: '-.03em', color: 'var(--color-ink)', wordBreak: 'keep-all' }}>{title}</h2>
        <p style={{ margin: 0, fontSize: 16, lineHeight: 1.8, color: 'var(--color-body-2)', wordBreak: 'keep-all' }}>{body}</p>
      </div>
      <div style={{ minWidth: 0 }}>{children}</div>
    </div>
  );
}
const RESEARCH_STEPS = [['채용공고와 직무기술서 분석', '요구 역량 12개를 추출하고 우선순위를 매겼습니다.'], ['최근 1년 뉴스 · IR · 기술 블로그 수집', '파트너 정산 서비스 공개(3월)와 물류 자회사 설립(7월)을 확인했습니다.'], ['인재상 · 조직문화 정리', '채용 페이지와 재직자 인터뷰에서 반복되는 표현을 모았습니다.'], ['지원서와 대조 · 검증이 필요한 항목 추출', '경험 1의 성과 수치와 본인 기여도를 확인할 질문이 필요합니다.'], ['질문 준비', '4단계에 걸쳐 8개 질문과 꼬리질문을 준비합니다.']];
function ResearchLog() {
  const [at, setAt] = React.useState(2);
  React.useEffect(() => { const t = setInterval(() => setAt(v => (v >= RESEARCH_STEPS.length ? 0 : v + 1)), 2200); return () => clearInterval(t); }, []);
  return (
    <div style={{ borderRadius: 'var(--radius-card)', border: '1px solid var(--color-line)', background: 'var(--color-surface)', padding: 22 }}>
      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}><span style={{ fontSize: 17, fontWeight: 700, letterSpacing: '-.02em' }}>누리테크</span><span style={{ fontSize: 12.5, color: 'var(--color-muted)' }}>서비스기획 · 신입</span></div>
        <div style={{ flex: 1 }} /><span className="num" style={{ fontSize: 11.5, color: 'var(--color-faint)' }}>3분 40초 경과</span>
      </div>
      <div style={{ marginBottom: 18 }}><IndeterminateBar /></div>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {RESEARCH_STEPS.map(([title, result], i) => { const state = i < at ? 'done' : i === at ? 'now' : 'wait'; return (
          <div key={title} style={{ display: 'flex', gap: 12, padding: '10px 0', borderBottom: i < RESEARCH_STEPS.length - 1 ? '1px solid var(--color-hair)' : 0 }}>
            <span style={{ marginTop: 2 }}>{state === 'done' ? <CheckDot /> : state === 'now' ? <Spinner /> : <EmptyDot />}</span>
            <div style={{ display: 'flex', minHeight: 40, flexDirection: 'column', gap: 3 }}>
              <span style={{ fontSize: 13.5, fontWeight: 600, transition: 'color .3s', color: state === 'done' ? 'var(--color-ink)' : state === 'now' ? 'var(--color-accent)' : 'var(--color-faintest)' }}>{title}</span>
              <span style={{ minHeight: 18, fontSize: 12, lineHeight: 1.5, color: 'var(--color-faint)', opacity: state === 'done' ? 1 : 0, transition: 'opacity .4s' }}>{result}</span>
            </div>
          </div>); })}
      </div>
    </div>
  );
}
const DIALOGUE = [['면접관', '그 프로젝트에서 가장 어려웠던 판단은 무엇이었나요?'], ['나', '분류 기준을 바꾸는 게 가장 어려웠습니다. 팀원들은 기존 기준을 유지하자고 했는데…'], ['면접관', '팀원들을 어떤 근거로 설득하셨나요? 비교 자료가 있었습니까?'], ['나', '음… 3개월 데이터로 두 기준을 나눠 봤을 때 회전율 차이가…']];
function Dialogue() {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
      {DIALOGUE.map(([who, text], i) => { const iv = who === '면접관'; const c = iv ? 'var(--color-accent)' : 'var(--color-listening)'; return (
        <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 8, borderRadius: 'var(--radius-card)', border: '1px solid var(--color-line)', background: 'var(--color-surface)', padding: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}><span style={{ width: 5, height: 5, borderRadius: '50%', background: c }} /><span style={{ fontSize: 11.5, fontWeight: 600, color: c }}>{who}</span>{i === 2 && <span style={{ marginLeft: 'auto', borderRadius: 'var(--radius-chip)', border: '1px solid var(--color-line-2)', padding: '2px 6px', fontSize: 10.5, color: 'var(--color-faint)' }}>꼬리질문</span>}</div>
          <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.7, fontWeight: iv ? 600 : 400, color: iv ? 'var(--color-ink)' : 'var(--color-body-2)' }}>{text}</p>
        </div>); })}
    </div>
  );
}
function ScoreCard() {
  const Metric = window.DaedamMetric;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18, borderRadius: 'var(--radius-card)', border: '1px solid var(--color-line)', background: 'var(--color-surface)', padding: 22 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}><span style={{ fontSize: 12, color: 'var(--color-faint)' }}>18분 12초 · 답변 8개</span><span style={{ fontSize: 17, fontWeight: 700, letterSpacing: '-.02em' }}>누리테크 · 서비스기획</span></div>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3 }}><div style={{ display: 'flex', alignItems: 'baseline', gap: 3 }}><span className="num" style={{ fontSize: 40, lineHeight: 1, fontWeight: 700, letterSpacing: '-.05em' }}>80</span><span style={{ fontSize: 13, color: 'var(--color-faint)' }}>/ 100</span></div><span style={{ fontSize: 11, color: 'var(--color-faintest)' }}>답변 점수의 평균</span></div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
        <Metric compact label="말하기 속도" value={312} unit="음절/분" low={280} high={360} range="280~360 권장" />
        <Metric compact label="필러 워드" value={3.4} unit="회/분" high={3} range="분당 3회 이하" />
        <Metric compact label="답변까지" value={2.4} unit="초" high={3} range="3초 이내" />
      </div>
    </div>
  );
}
function CoachCard() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, borderRadius: 'var(--radius-card)', border: '1px solid var(--color-line)', background: 'var(--color-surface)', padding: 22 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}><span className="num" style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--color-faintest)' }}>Q3</span><span style={{ minWidth: 0, flex: 1, fontSize: 13.5, fontWeight: 600 }}>물류 데이터 분석 프로젝트에서 본인이 맡은 역할</span><span className="num" style={{ fontSize: 11.5, color: 'var(--color-faintest)' }}>84.0초</span><span className="num" style={{ fontSize: 15, fontWeight: 700 }}>88</span></div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, borderRadius: 'var(--radius-control)', border: '1px solid var(--color-line-2)', background: 'var(--color-surface-2)', padding: '10px 13px' }}><span style={{ display: 'flex', width: 26, height: 26, alignItems: 'center', justifyContent: 'center', borderRadius: '50%', background: 'var(--color-ink)' }}><Icon name="play" size={12} color="#fff" /></span><div style={{ flex: 1, height: 3, background: 'var(--color-line-3)' }} /><span style={{ fontSize: 11.5, color: 'var(--color-muted)' }}>내 답변 다시 듣기</span></div>
      <div style={{ borderLeft: '2px solid var(--color-positive)', paddingLeft: 14 }}><div style={{ marginBottom: 5, fontSize: 11.5, fontWeight: 700, color: 'var(--color-positive)' }}>잘한 점</div><p style={{ margin: 0, fontSize: 13, lineHeight: 1.75, color: 'var(--color-body)' }}>문제 인식, 조치, 결과가 순서대로 나왔습니다.</p></div>
      <div style={{ borderLeft: '2px solid var(--color-accent)', paddingLeft: 14 }}><div style={{ marginBottom: 5, fontSize: 11.5, fontWeight: 700, color: 'var(--color-accent)' }}>이렇게 바꿔보세요</div><p style={{ margin: 0, fontSize: 13, lineHeight: 1.75, color: 'var(--color-body)' }}>마지막 문장에 숫자 하나를 붙이세요. 재고가 몇 % 줄었는지, 그 제안이 몇 개 매장에 적용되었는지.</p></div>
    </div>
  );
}
function Landing() {
  const [demo, setDemo] = React.useState(0);
  React.useEffect(() => { const t = setInterval(() => setDemo(i => (i + 1) % DEMOS.length), DEMO_INTERVAL_MS); return () => clearInterval(t); }, [demo]);
  const [co, setCo] = React.useState(0);
  React.useEffect(() => { const t = setInterval(() => setCo(i => (i + 1) % COMPANIES.length), COMPANY_INTERVAL_MS); return () => clearInterval(t); }, []);
  const company = COMPANIES[co];
  const scrollToLogin = () => { const el = document.getElementById('login'); if (el) window.scrollTo({ top: el.getBoundingClientRect().top + window.pageYOffset - window.innerHeight / 2, behavior: 'smooth' }); };
  const fact = (v, l) => <div key={v} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}><span className="num" style={{ fontSize: 22, lineHeight: 1, fontWeight: 700, letterSpacing: '-.03em', color: 'var(--color-ink)' }}>{v}</span><span style={{ fontSize: 13.5, color: 'var(--color-muted)' }}>{l}</span></div>;
  return (
    <main style={{ wordBreak: 'keep-all', animation: 'dm-fade .3s ease' }}>
      <header style={{ position: 'sticky', top: 0, zIndex: 40, height: 64, borderBottom: '1px solid var(--color-line)', background: 'var(--header-bg)', backdropFilter: 'blur(8px)' }}>
        <div style={{ margin: '0 auto', display: 'flex', height: '100%', maxWidth: 1240, alignItems: 'center', padding: '0 32px', boxSizing: 'border-box' }}><Logo /><div style={{ flex: 1 }} /><button onClick={scrollToLogin} style={{ borderRadius: 'var(--radius-control)', border: '1px solid var(--color-field)', background: 'var(--color-surface)', padding: '9px 16px', fontSize: 13.5, fontWeight: 600, color: 'var(--color-ink)' }}>로그인</button></div>
      </header>
      <section style={{ margin: '0 auto', display: 'grid', maxWidth: 1240, gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)', alignItems: 'center', gap: 56, padding: '72px 32px 80px', boxSizing: 'border-box' }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ marginBottom: 22, display: 'flex', alignItems: 'center', gap: 8 }}><AccentDot size={5} /><span style={{ fontSize: 12.5, fontWeight: 600, letterSpacing: '.04em', color: 'var(--color-accent)' }}>AI 음성 모의면접</span></div>
          <h1 style={{ margin: 0, fontSize: 44, lineHeight: 1.22, fontWeight: 700, letterSpacing: '-.04em', color: 'var(--color-ink)' }}>
            대담과 함께 미리<br />
            {/* 바뀌는 줄 — 회사와 "면접장에"가 한 줄에 있어야 명사구가 갈라지지 않는다. 높이 1.22em 고정, key 리마운트로 회사만 dm-fade. */}
            <span style={{ display: 'inline-flex', height: '1.22em', alignItems: 'center', gap: '0.27em', verticalAlign: 'top', whiteSpace: 'nowrap' }}><span key={company.name} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.22em', animation: 'dm-fade .4s ease' }}><Monogram mark={company.mark} />{company.name}</span>면접장에</span><br />
            들어가세요
          </h1>
          <p style={{ margin: '22px 0 0', maxWidth: 460, fontSize: 18, lineHeight: 1.7, color: 'var(--color-body-2)' }}>몇 번이든 다시 연습하세요.</p>
          <div id="login" style={{ marginTop: 36, display: 'flex', flexWrap: 'wrap', gap: 10 }}><LoginButton provider="kakao" /><LoginButton provider="google" /></div>
          <div style={{ marginTop: 40, display: 'flex', flexWrap: 'wrap', gap: 28 }}>{fact('4단계', '자기소개 · 직무역량 · 인성 · 마무리')}{fact('6가지', '음성 지표를 권장 범위와 비교')}{fact('답변마다', '녹음을 다시 듣고 문장을 고치기')}</div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <LiveDemo demo={DEMOS[demo]} />
          <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 6 }}>{DEMOS.map((item, i) => <button key={item.company} onClick={() => setDemo(i)} style={{ borderRadius: 9999, border: '1px solid ' + (i === demo ? 'var(--color-ink)' : 'var(--color-line)'), background: i === demo ? 'var(--color-ink)' : 'transparent', color: i === demo ? '#fff' : 'var(--color-muted)', padding: '6px 13px', fontSize: 13, transition: 'color .3s, background .3s, border-color .3s' }}>{item.company}</button>)}</div>
        </div>
      </section>
      <section style={{ margin: '0 auto', maxWidth: 1240, padding: '0 32px 40px', boxSizing: 'border-box' }}>
        <StepFrame label="01 회사 조사" title="실제와 같은 면접관과 대화하세요" body="공신력 있는 근거를 통해 기업을 조사합니다. 실제 면접관이 할 법한 질문을 받아보세요."><ResearchLog /></StepFrame>
        <StepFrame label="02 음성 면접" title="얼버무린 자리를 먼저 들켜보세요" body="파고드는 꼬리질문을 받아보세요. 숫자가 빠지면 숫자를, 근거가 빠지면 근거를 되묻습니다. 모의면접에서 먼저 당황해보세요."><Dialogue /></StepFrame>
        <StepFrame label="03 답변 코칭" title="정확한 지표와 함께 리뷰하고 개선하세요" body="녹음을 다시 들으면서 답변마다 잘한 점과 빠진 것을 확인하고, 다음 면접장에서 그대로 말할 수 있게 고쳐 쓴 문장을 받으세요."><div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}><ScoreCard /><CoachCard /></div></StepFrame>
      </section>
      <section style={{ borderTop: '1px solid var(--color-line)', background: 'var(--color-surface)' }}>
        <div style={{ margin: '0 auto', display: 'flex', maxWidth: 1240, flexDirection: 'column', alignItems: 'center', padding: '96px 32px', textAlign: 'center' }}><h2 style={{ margin: 0, fontSize: 34, lineHeight: 1.3, fontWeight: 700, letterSpacing: '-.04em', color: 'var(--color-ink)' }}>연습은 여기서 끝내고<br />합격 소식을 전하세요</h2></div>
        <div style={{ margin: '0 auto', display: 'flex', maxWidth: 1240, flexWrap: 'wrap', gap: 16, padding: '0 32px 40px', fontSize: 13, color: 'var(--color-muted)' }}><span>면접 중 음성과 웹캠 영상이 기록되고, 답변 분석에 쓰입니다.</span><div style={{ flex: 1 }} /><a href="#" onClick={e => e.preventDefault()} style={{ color: 'var(--color-faint)' }}>이용약관</a><a href="#" onClick={e => e.preventDefault()} style={{ color: 'var(--color-faint)' }}>개인정보처리방침</a></div>
      </section>
    </main>
  );
}
window.DaedamLanding = Landing;
if (document.getElementById('root') && !window.DaedamNoMount) ReactDOM.createRoot(document.getElementById('root')).render(<Landing />);
