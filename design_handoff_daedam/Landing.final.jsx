// 랜딩 확정안 (2a 라이브 데모 + 벅차오름 카피). 이 파일의 화면이 구현 대상이다.
const KakaoMark = ({ size = 18 }) => <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true"><path d="M12 18.75c-.591 0-1.1697-.0413-1.7317-.1209-.5626.3965-3.813 2.6797-4.1198 2.7225 0 0-.1258.0489-.2328-.0141s-.0876-.2282-.0876-.2282c.0322-.2198.8426-3.0183.992-3.5333-2.7452-1.36-4.5701-3.7686-4.5701-6.5135C2.25 6.8168 6.6152 3.375 12 3.375s9.75 3.4418 9.75 7.6875c0 4.2457-4.3652 7.6875-9.75 7.6875z" fill="#191600" /></svg>;
const GoogleMark = ({ size = 18 }) => <svg viewBox="0 0 118 120" width={size} height={size} aria-hidden="true"><path d="M117.6,61.3636364 C117.6,57.1090909 117.218182,53.0181818 116.509091,49.0909091 L60,49.0909091 L60,72.3 L92.2909091,72.3 C90.9,79.8 86.6727273,86.1545455 80.3181818,90.4090909 L80.3181818,105.463636 L99.7090909,105.463636 C111.054545,95.0181818 117.6,79.6363636 117.6,61.3636364 L117.6,61.3636364 Z" fill="#4285F4" /><path d="M60,120 C76.2,120 89.7818182,114.627273 99.7090909,105.463636 L80.3181818,90.4090909 C74.9454545,94.0090909 68.0727273,96.1363636 60,96.1363636 C44.3727273,96.1363636 31.1454545,85.5818182 26.4272727,71.4 L6.38181818,71.4 L6.38181818,86.9454545 C16.2545455,106.554545 36.5454545,120 60,120 L60,120 Z" fill="#34A853" /><path d="M26.4272727,71.4 C25.2272727,67.8 24.5454545,63.9545455 24.5454545,60 C24.5454545,56.0454545 25.2272727,52.2 26.4272727,48.6 L26.4272727,33.0545455 L6.38181818,33.0545455 C2.31818182,41.1545455 0,50.3181818 0,60 C0,69.6818182 2.31818182,78.8454545 6.38181818,86.9454545 L26.4272727,71.4 L26.4272727,71.4 Z" fill="#FBBC05" /><path d="M60,23.8636364 C68.8090909,23.8636364 76.7181818,26.8909091 82.9363636,32.8363636 L100.145455,15.6272727 C89.7545455,5.94545455 76.1727273,0 60,0 C36.5454545,0 16.2545455,13.4454545 6.38181818,33.0545455 L26.4272727,48.6 C31.1454545,34.4181818 44.3727273,23.8636364 60,23.8636364 L60,23.8636364 Z" fill="#EA4335" /></svg>;

function LoginButton({ provider, dark }) {
  const kakao = provider === 'kakao';
  const Mark = kakao ? KakaoMark : GoogleMark;
  return (
    <a href="#" onClick={e => e.preventDefault()} style={{ position: 'relative', display: 'flex', height: 50, minWidth: 236, alignItems: 'center', justifyContent: 'center', borderRadius: 'var(--radius-control)', fontSize: 14.5, fontWeight: 600, color: kakao ? 'var(--color-kakao-ink)' : 'var(--color-ink)', background: kakao ? 'var(--color-kakao)' : 'var(--color-surface)', border: kakao ? 0 : '1px solid ' + (dark ? 'var(--color-surface)' : 'var(--color-field)'), paddingLeft: 44, paddingRight: 20 }}>
      <span style={{ position: 'absolute', left: 16, display: 'flex', alignItems: 'center' }}><Mark /></span>
      {kakao ? '카카오로 시작하기' : 'Google로 시작하기'}
    </a>
  );
}
const Logo = ({ dark }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
    <span style={{ display: 'flex', width: 26, height: 26, alignItems: 'center', justifyContent: 'center', border: '1.5px solid ' + (dark ? 'var(--color-stage-ink)' : 'var(--color-ink)') }}><span style={{ width: 10, height: 10, background: 'var(--color-accent)' }} /></span>
    <span style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-.02em', color: dark ? 'var(--color-stage-ink)' : 'var(--color-ink)' }}>대담</span>
  </div>
);


/* ── 카피 3안. 같은 레이아웃에서 문구만 바뀐다. 제품 사실(단계·지표·규격)은 공통. ── */
const COPY = {
  calm: {
    label: '담백',
    h1: ['지원한 회사가', '실제로 물어볼 것을', '묻습니다'],
    sub: '회사와 직무를 등록하면 공개된 자료를 조사해 질문을 만듭니다. 음성으로 면접을 진행하고, 끝나면 답변마다 무엇이 부족했는지 짚어 드립니다.',
    note: '첫 면접은 무료 크레딧으로 · 15~20분 · 한국어 음성',
    s1: ['질문에는 근거가 있습니다', '채용공고, 최근 1년 뉴스와 IR, 인재상, 그리고 당신의 지원서를 함께 읽습니다. 조사가 끝나면 리포트를 직접 확인하고 틀린 대목을 고칠 수 있습니다.'],
    s2: ['답변을 따라 파고듭니다', '준비된 질문에서 시작하지만 대본을 읽지 않습니다. 답변에서 빠진 것을 면접관이 되묻습니다. 실제 면접처럼 단계도 남은 시간도 알려주지 않습니다.'],
    s3: ['점수보다 고쳐 쓴 문장', '종합 점수와 음성 지표는 한눈에. 답변마다 잘한 점, 더 듣고 싶었던 것, 그리고 이렇게 바꿔보세요 — 실제로 말할 수 있는 문장으로.'],
    close: ['다음 면접까지 며칠 남았든,', '오늘 한 번 보고 가세요'],
    closeSub: '등록부터 리포트까지 30분. 같은 회사로 다시 보면 회차별로 비교됩니다.',
  },
  bold: {
    label: '벅차오름',
    h1: ['대담과 함께', '미리 면접장에', '들어가세요'],
    sub: '몇 번이든 다시 연습하세요.',
    subs: {
      scene: '몇 번이든 다시 연습하세요.',
      moment: '진짜 면접장에서 "음…" 하고 멈추는 순간을 여기서 먼저 겪으세요.',
      after: '면접장을 나서며 후회할 질문을 오늘 먼저 받으세요.',
    },
    note: '',
    s1: ['실제와 같은 면접관과 대화하세요', '공신력 있는 근거를 통해 기업을 조사합니다. 실제 면접관이 할 법한 질문을 받아보세요.'],
    s2: ['얼버무린 자리를 먼저 들켜보세요', '파고드는 꼬리질문을 받아보세요. 숫자가 빠지면 숫자를, 근거가 빠지면 근거를 되묻습니다. 모의면접에서 먼저 당황해보세요.'],
    s3: ['정확한 지표와 함께 리뷰하고 개선하세요', '녹음을 다시 들으면서 답변마다 잘한 점과 빠진 것을 확인하고, 다음 면접장에서 그대로 말할 수 있게 고쳐 쓴 문장을 받으세요.'],
    close: ['연습은 여기서 끝내고', '합격 소식을 전하세요'],
    closeSub: '',
  },
  direct: {
    label: '직설',
    h1: ['이 질문에', '지금 답할 수', '있습니까'],
    sub: '이 질문은 실제 채용공고와 올해 보도자료에서 나왔습니다. 면접관은 이런 것을 묻습니다. 당신이 지원한 회사로 바꾸면, 그 회사의 질문이 나옵니다.',
    note: '지원 회사 등록 → 조사 → 음성 면접 → 리포트 · 첫 면접 무료',
    s1: ['회사를 조사한 흔적이 없는 답변은 들립니다', '면접관은 30초 안에 압니다. 대담은 채용공고와 최근 1년 뉴스, IR, 인재상, 그리고 당신의 지원서를 먼저 읽고 질문을 만듭니다. 조사 리포트는 당신도 봅니다.'],
    s2: ['"음…"이 몇 번이었는지 아십니까', '말하기 속도, 답변까지 걸린 시간, 멈춤, 필러 워드, 목소리 흔들림 — 여섯 가지를 재고 권장 범위와 비교합니다. 카메라를 켜면 시선과 표정도.'],
    s3: ['같은 질문을 다시 받았을 때 할 말', '답변마다 잘한 점, 더 듣고 싶었던 것, 이렇게 바꿔보세요. 고쳐 쓴 문장은 다음 면접장에서 그대로 쓸 수 있는 것만 씁니다.'],
    close: ['면접은 당일에 잘 볼 수 없습니다.', '그 전에 한 번.'],
    closeSub: '등록부터 리포트까지 30분. 회차가 쌓이면 무엇이 나아졌는지 숫자로 보입니다.',
  },
};
const CopyCtx = React.createContext(COPY.bold);
const useCopy = () => React.useContext(CopyCtx);

/* ── 회사 이름이 바뀌면 질문이 바뀐다 — "그 회사에 맞춘 질문"을 말이 아니라 예시로. ── */
const DEMOS = [
  { company: '누리테크', role: '서비스기획', q: '저희가 올해 공개한 파트너 정산 서비스를 써보셨다면, 어떤 점을 먼저 개선하시겠습니까?', src: '2026년 3월 보도자료 · 채용공고 우대사항' },
  { company: '세종바이오', role: '마케팅', q: '지원서에 쓰신 SNS 캠페인 경험을, 처방약 광고 규제가 있는 저희 업계에서는 어떻게 바꿔 적용하시겠어요?', src: '지원서 경험 2 · 회사 IR 자료' },
  { company: '한빛금융', role: 'IT기획', q: '작년 저희 앱 장애 때 고객 공지가 늦었다는 지적이 있었는데, 기획자로서 무엇을 먼저 바꾸시겠습니까?', src: '2025년 11월 뉴스 · 인재상 "책임"' },
  { company: '오름소프트', role: '백엔드 개발', q: '지원서의 트래픽 3배 처리 경험에서, 병목이 DB였는지 애플리케이션이었는지 어떻게 판단하셨나요?', src: '지원서 경험 1 · 기술 블로그' },
];

/** 타자 효과 — 면접관이 지금 묻고 있다는 느낌. 진폭처럼 60fps 값은 아니라 state로 충분. */
function useTyped(text, speed = 28) {
  const [n, setN] = React.useState(0);
  React.useEffect(() => { setN(0); let i = 0; const t = setInterval(() => { i += 1; setN(i); if (i >= text.length) clearInterval(t); }, speed); return () => clearInterval(t); }, [text]);
  return text.slice(0, n);
}

function Avatar({ size = 206, speaking = true, level = 0.6 }) {
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

function Waveform({ active, color = 'var(--color-accent)', height = 38, width = 3, count = 16 }) {
  const bars = React.useRef([]);
  React.useEffect(() => {
    let raf; const loop = () => { const t = performance.now() / 1000; const lv = active ? Math.max(0, Math.sin(t * 5.3) * .5 + Math.sin(t * 9.1) * .3 + .3) : 0; bars.current.forEach((el, i) => { if (!el) return; const ph = Math.sin(t * 6 + i * .7) * .5 + .5; el.style.transform = 'scaleY(' + Math.min(1, .22 + lv * (.35 + .65 * ph) * .78) + ')'; }); raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop); return () => cancelAnimationFrame(raf);
  }, [active]);
  return <div style={{ display: 'flex', alignItems: 'center', gap: 3, height }}>{Array.from({ length: count }, (_, i) => <div key={i} ref={el => bars.current[i] = el} style={{ width, height, background: color, transformOrigin: 'center', transform: 'scaleY(.22)' }} />)}</div>;
}

/* ── 리포트 조각들 — 결과가 어떻게 보이는지 증명. 실제 Report.tsx 규격 그대로. ── */
function ScoreCard() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18, padding: 22, borderRadius: 'var(--radius-card)', border: '1px solid var(--color-line)', background: 'var(--color-surface)' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}><span style={{ fontSize: 12, color: 'var(--color-faint)' }}>18분 12초 · 답변 8개</span><span style={{ fontSize: 17, fontWeight: 700, letterSpacing: '-.02em' }}>누리테크 · 서비스기획</span></div>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3 }}><div style={{ display: 'flex', alignItems: 'baseline', gap: 3 }}><span className="num" style={{ fontSize: 40, lineHeight: 1, fontWeight: 700, letterSpacing: '-.05em' }}>80</span><span style={{ fontSize: 13, color: 'var(--color-faint)' }}>/ 100</span></div><span style={{ fontSize: 11, color: 'var(--color-faintest)' }}>답변 점수의 평균</span></div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
        {[['말하기 속도', '312', '음절/분', 62, true, '280~360 권장'], ['필러 워드', '3.4', '회/분', 78, false, '분당 3회 이하'], ['답변까지', '2.4', '초', 40, true, '3초 이내']].map(([l, v, u, p, ok, r]) => (
          <div key={l} style={{ display: 'flex', flexDirection: 'column', gap: 5, padding: 12, borderRadius: 'var(--radius-card)', border: '1px solid var(--color-line)', background: 'var(--color-surface-2)' }}>
            <span style={{ fontSize: 11, color: 'var(--color-muted)', whiteSpace: 'nowrap' }}>{l}</span>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 3 }}><span className="num" style={{ fontSize: 19, fontWeight: 700, letterSpacing: '-.03em', lineHeight: 1 }}>{v}</span><span style={{ fontSize: 10.5, color: 'var(--color-faint)' }}>{u}</span></div>
            <div style={{ height: 3, background: 'var(--color-line-3)' }}><div style={{ height: '100%', width: p + '%', background: ok ? 'var(--color-positive)' : 'var(--color-accent)', animation: 'dm-grow .7s ease' }} /></div>
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}><span style={{ fontSize: 10.5, fontWeight: 600, whiteSpace: 'nowrap', color: ok ? 'var(--color-positive)' : 'var(--color-accent)' }}>{ok ? '적정' : '다소 많음'}</span><span style={{ fontSize: 10.5, whiteSpace: 'nowrap', color: 'var(--color-faintest)' }}>{r}</span></div>
          </div>
        ))}
      </div>
    </div>
  );
}
function CoachCard() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, padding: 22, borderRadius: 'var(--radius-card)', border: '1px solid var(--color-line)', background: 'var(--color-surface)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}><span className="num" style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--color-faintest)' }}>Q3</span><span style={{ flex: 1, minWidth: 0, fontSize: 13.5, fontWeight: 600, wordBreak: 'keep-all' }}>물류 데이터 분석 프로젝트에서 본인이 맡은 역할</span><span className="num" style={{ fontSize: 11.5, color: 'var(--color-faintest)' }}>84.0초</span><span className="num" style={{ fontSize: 15, fontWeight: 700 }}>88</span></div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, borderRadius: 'var(--radius-control)', border: '1px solid var(--color-line-2)', background: 'var(--color-surface-2)', padding: '10px 13px' }}>
        <span style={{ display: 'flex', width: 26, height: 26, alignItems: 'center', justifyContent: 'center', borderRadius: '50%', background: 'var(--color-ink)', color: '#fff', fontSize: 9 }}>▶</span>
        <div style={{ flex: 1, height: 3, background: 'var(--color-line-3)' }}><div style={{ height: '100%', width: '0%', background: 'var(--color-accent)' }} /></div>
        <span style={{ fontSize: 11.5, color: 'var(--color-muted)' }}>내 답변 다시 듣기</span>
      </div>
      <div style={{ borderLeft: '2px solid var(--color-positive)', paddingLeft: 14 }}><div style={{ marginBottom: 5, fontSize: 11.5, fontWeight: 700, color: 'var(--color-positive)' }}>잘한 점</div><p style={{ margin: 0, fontSize: 13, lineHeight: 1.75, color: 'var(--color-body)' }}>문제 인식, 조치, 결과가 순서대로 나왔습니다.</p></div>
      <div style={{ borderLeft: '2px solid var(--color-accent)', paddingLeft: 14 }}><div style={{ marginBottom: 5, fontSize: 11.5, fontWeight: 700, color: 'var(--color-accent)' }}>이렇게 바꿔보세요</div><p style={{ margin: 0, fontSize: 13, lineHeight: 1.75, color: 'var(--color-body)' }}>마지막 문장에 숫자 하나를 붙이세요. 재고가 몇 % 줄었는지, 그 제안이 몇 개 매장에 적용되었는지.</p></div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   2a · 데모가 돌아가는 랜딩 — 밝은 바탕. 첫 화면에 면접관 창이 떠 있고
   4초마다 회사가 바뀌며 질문이 타이핑된다. 아래로 세 단계가 실제 화면 조각으로.
   ═══════════════════════════════════════════════════════════════════ */
function LiveDemo({ idx }) {
  const d = DEMOS[idx];
  const typed = useTyped(d.q);
  const done = typed.length >= d.q.length;
  return (
    <div style={{ position: 'relative', width: '100%', maxWidth: 640, borderRadius: 'var(--radius-card)', background: 'var(--color-stage)', border: '1px solid var(--color-stage-line)', overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: 440 }}>
      <div style={{ position: 'absolute', inset: 0, background: 'var(--gradient-stage-vignette)' }} />
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center', padding: '18px 22px' }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: done ? 'var(--color-listening)' : 'var(--color-accent)', transition: 'background .4s' }} />
        <span style={{ marginLeft: 8, fontSize: 13, color: 'var(--color-stage-ink)' }}>{done ? '듣고 있습니다' : '면접관이 말하고 있습니다'}</span>
        <div style={{ flex: 1 }} />
        <span key={idx} style={{ fontSize: 12.5, color: 'var(--color-stage-muted-2)', animation: 'dm-fade .4s ease' }}>{d.company} · {d.role}</span>
      </div>
      <div style={{ position: 'relative', flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Avatar size={150} speaking={!done} /></div>
      <div style={{ position: 'relative', margin: '0 auto', minHeight: 78, maxWidth: 520, padding: '0 24px', display: 'flex', alignItems: 'flex-start', justifyContent: 'center' }}>
        <p style={{ margin: 0, textAlign: 'center', fontSize: 16.5, lineHeight: 1.65, fontWeight: 500, letterSpacing: '-.01em', color: 'var(--color-stage-ink)' }}>{typed}<span style={{ display: done ? 'none' : 'inline-block', width: 2, height: 16, marginLeft: 2, verticalAlign: '-2px', background: 'var(--color-accent)' }} /></p>
      </div>
      <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10, height: 92, justifyContent: 'center' }}>
        {done ? <Waveform active color="var(--color-accent)" height={28} /> : <span style={{ fontSize: 12, color: 'var(--color-stage-muted-3)' }}>답변이 끝나면 마이크가 열립니다</span>}
      </div>
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 8, padding: '0 22px 16px' }}>
        <span style={{ fontSize: 11, color: 'var(--color-stage-muted)' }}>이 질문의 출처</span>
        <span key={idx} style={{ fontSize: 11, color: 'var(--color-stage-muted-2)', animation: 'dm-fade .4s ease' }}>{d.src}</span>
      </div>
    </div>
  );
}
function StepFrame({ n, title, body, children }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 48, alignItems: 'center', padding: '56px 0', borderTop: '1px solid var(--color-line)' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <span className="num" style={{ fontSize: 12, fontWeight: 600, letterSpacing: '.05em', color: 'var(--color-accent)' }}>{n}</span>
        <h2 style={{ margin: 0, fontSize: 25, lineHeight: 1.3, fontWeight: 700, letterSpacing: '-.03em' }}>{title}</h2>
        <p style={{ margin: 0, fontSize: 14.5, lineHeight: 1.75, color: 'var(--color-body-2)' }}>{body}</p>
      </div>
      <div>{children}</div>
    </div>
  );
}
function ResearchLog() {
  const steps = [['채용공고와 직무기술서 분석', '요구 역량 12개를 추출하고 우선순위를 매겼습니다.'], ['최근 1년 뉴스 · IR · 기술 블로그 수집', '파트너 정산 서비스 공개(3월)와 물류 자회사 설립(7월)을 확인했습니다.'], ['인재상 · 조직문화 정리', '채용 페이지와 재직자 인터뷰에서 반복되는 표현을 모았습니다.'], ['지원서와 대조 · 검증이 필요한 항목 추출', '경험 1의 성과 수치와 본인 기여도를 확인할 질문이 필요합니다.'], ['질문 준비', '4단계에 걸쳐 8개 질문과 꼬리질문을 준비합니다.']];
  const [k, setK] = React.useState(2);
  React.useEffect(() => { const t = setInterval(() => setK(v => v >= 5 ? 0 : v + 1), 2200); return () => clearInterval(t); }, []);
  return (
    <div style={{ padding: 22, borderRadius: 'var(--radius-card)', border: '1px solid var(--color-line)', background: 'var(--color-surface)' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 16 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}><span style={{ fontSize: 17, fontWeight: 700, letterSpacing: '-.02em' }}>누리테크</span><span style={{ fontSize: 12.5, color: 'var(--color-muted)' }}>서비스기획 · 신입</span></div>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 11.5, color: 'var(--color-faint)' }}>3분 40초 경과</span>
      </div>
      <div style={{ height: 3, background: 'var(--color-hair-2)', overflow: 'hidden', marginBottom: 18 }}><div style={{ width: '25%', height: '100%', background: 'var(--color-accent)', animation: 'dm-slide 1.6s ease-in-out infinite' }} /></div>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {steps.map(([t, r], i) => { const st = i < k ? 'done' : i === k ? 'now' : 'wait'; return (
          <div key={t} style={{ display: 'flex', gap: 12, padding: '10px 0', borderBottom: i < steps.length - 1 ? '1px solid var(--color-hair)' : 0 }}>
            <span style={{ marginTop: 2 }}>{st === 'done' ? <span style={{ display: 'inline-flex', width: 14, height: 14, alignItems: 'center', justifyContent: 'center', borderRadius: '50%', background: 'var(--color-ink)', color: '#fff', fontSize: 9 }}>✓</span> : st === 'now' ? <span style={{ display: 'inline-block', width: 13, height: 13, borderRadius: '50%', border: '1.5px solid var(--color-accent)', borderTopColor: 'transparent', animation: 'dm-spin 1s linear infinite' }} /> : <span style={{ display: 'inline-block', width: 13, height: 13, borderRadius: '50%', border: '1.5px solid var(--color-line)' }} />}</span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minHeight: 40 }}><span style={{ fontSize: 13.5, fontWeight: 600, color: st === 'done' ? 'var(--color-ink)' : st === 'now' ? 'var(--color-accent)' : 'var(--color-faintest)', transition: 'color .3s' }}>{t}</span><span style={{ fontSize: 12, lineHeight: 1.5, color: 'var(--color-faint)', opacity: st === 'done' && r ? 1 : 0, transition: 'opacity .4s', minHeight: 18 }}>{r || ' '}</span></div>
          </div>); })}
      </div>
    </div>
  );
}
function LandingLiveDemo() {
  const c = useCopy();
  const [idx, setIdx] = React.useState(0);
  React.useEffect(() => { const t = setInterval(() => setIdx(i => (i + 1) % DEMOS.length), 5200); return () => clearInterval(t); }, []);
  return (
    <main style={{ background: 'var(--color-bg)', color: 'var(--color-ink)', wordBreak: 'keep-all' }}>
      <header style={{ position: 'sticky', top: 0, zIndex: 40, height: 64, background: 'var(--header-bg)', backdropFilter: 'blur(8px)', borderBottom: '1px solid var(--color-line)' }}>
        <div style={{ maxWidth: 1160, margin: '0 auto', height: '100%', padding: '0 32px', display: 'flex', alignItems: 'center' }}><Logo /><div style={{ flex: 1 }} /><a href="#login" onClick={e => { e.preventDefault(); window.scrollTo({ top: 0, behavior: 'smooth' }); }} style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--color-ink)', padding: '9px 16px', border: '1px solid var(--color-field)', borderRadius: 'var(--radius-control)', background: 'var(--color-surface)' }}>로그인</a></div>
      </header>
      <section style={{ maxWidth: 1160, margin: '0 auto', padding: '72px 32px 80px', display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)', gap: 56, alignItems: 'center' }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 22 }}>
            <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--color-accent)' }} />
            <span style={{ fontSize: 12.5, fontWeight: 600, letterSpacing: '.04em', color: 'var(--color-accent)' }}>AI 음성 모의면접</span>
          </div>
          <h1 key={c.label} style={{ margin: 0, fontSize: 44, lineHeight: 1.22, fontWeight: 700, letterSpacing: '-.04em', wordBreak: 'keep-all', animation: 'dm-fade .4s ease' }}>{c.h1[0]}<br />{c.h1[1]} {c.h1[2]}</h1>
          <p style={{ margin: '22px 0 0', fontSize: 16, lineHeight: 1.75, color: 'var(--color-body-2)', maxWidth: 440 }}>{c.sub}</p>
          <div id="login" style={{ marginTop: 36, display: 'flex', gap: 10, flexWrap: 'wrap' }}><LoginButton provider="kakao" /><LoginButton provider="google" /></div>
          {c.note && <p style={{ margin: '16px 0 0', fontSize: 12.5, color: 'var(--color-faint)' }}>{c.note}</p>}
          <div style={{ marginTop: 40, display: 'flex', gap: 28 }}>
            {[['4단계', '자기소개 · 직무역량 · 인성 · 마무리'], ['6가지', '음성 지표를 권장 범위와 비교'], ['답변마다', '녹음을 다시 듣고 문장을 고치기']].map(([v, l]) => <div key={v} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}><span className="num" style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-.03em', lineHeight: 1 }}>{v}</span><span style={{ fontSize: 12, color: 'var(--color-muted)' }}>{l}</span></div>)}
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <LiveDemo idx={idx} />
          <div style={{ display: 'flex', gap: 6, justifyContent: 'center' }}>{DEMOS.map((d, i) => <button key={d.company} onClick={() => setIdx(i)} style={{ padding: '5px 11px', fontSize: 12, borderRadius: 9999, border: '1px solid ' + (i === idx ? 'var(--color-ink)' : 'var(--color-line)'), background: i === idx ? 'var(--color-ink)' : 'transparent', color: i === idx ? '#fff' : 'var(--color-muted)', transition: 'all .3s' }}>{d.company}</button>)}</div>
        </div>
      </section>
      <section style={{ maxWidth: 1160, margin: '0 auto', padding: '0 32px 40px' }}>
        <StepFrame n="01 회사 조사" title={c.s1[0]} body={c.s1[1]}><ResearchLog /></StepFrame>
        <StepFrame n="02 음성 면접" title={c.s2[0]} body={c.s2[1]}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {[['면접관', '그 프로젝트에서 가장 어려웠던 판단은 무엇이었나요?', 'var(--color-accent)'], ['나', '분류 기준을 바꾸는 게 가장 어려웠습니다. 팀원들은 기존 기준을 유지하자고 했는데…', 'var(--color-listening)'], ['면접관', '팀원들을 어떤 근거로 설득하셨나요? 비교 자료가 있었습니까?', 'var(--color-accent)'], ['나', '음… 3개월 데이터로 두 기준을 나눠 봤을 때 회전율 차이가…', 'var(--color-listening)']].map(([w, t, c], i) => (
              <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 18, borderRadius: 'var(--radius-card)', border: '1px solid var(--color-line)', background: 'var(--color-surface)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}><span style={{ width: 5, height: 5, borderRadius: '50%', background: c }} /><span style={{ fontSize: 11.5, fontWeight: 600, color: c }}>{w}</span>{i === 2 && <span style={{ marginLeft: 'auto', fontSize: 10.5, color: 'var(--color-faint)', border: '1px solid var(--color-line-2)', borderRadius: 2, padding: '2px 6px' }}>꼬리질문</span>}</div>
                <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.7, color: w === '면접관' ? 'var(--color-ink)' : 'var(--color-body-2)', fontWeight: w === '면접관' ? 600 : 400 }}>{t}</p>
              </div>
            ))}
          </div>
        </StepFrame>
        <StepFrame n="03 답변 코칭" title={c.s3[0]} body={c.s3[1]}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}><ScoreCard /><CoachCard /></div>
        </StepFrame>
      </section>
      <section style={{ borderTop: '1px solid var(--color-line)', background: 'var(--color-surface)' }}>
        <div style={{ maxWidth: 1160, margin: '0 auto', padding: '96px 32px', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
          <h2 style={{ margin: 0, fontSize: 34, lineHeight: 1.3, fontWeight: 700, letterSpacing: '-.04em' }}>{c.close[0]}<br />{c.close[1]}</h2>
          {c.closeSub && <p style={{ margin: '14px 0 0', fontSize: 14.5, color: 'var(--color-muted)' }}>{c.closeSub}</p>}
        </div>
        <div style={{ maxWidth: 1160, margin: '0 auto', padding: '0 32px 40px', display: 'flex', gap: 16, fontSize: 12, color: 'var(--color-faintest)' }}><span>면접 중 음성과 웹캠 영상이 기록되고, 답변 분석에 쓰입니다.</span><div style={{ flex: 1 }} /><a href="#" style={{ color: 'var(--color-faint)' }}>이용약관</a><a href="#" style={{ color: 'var(--color-faint)' }}>개인정보처리방침</a></div>
      </section>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<CopyCtx.Provider value={{ ...COPY.bold, sub: COPY.bold.subs.scene }}><LandingLiveDemo /></CopyCtx.Provider>);
