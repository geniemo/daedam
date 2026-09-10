// 전환·빈 상태 갤러리 — Progress.tsx(Analyzing 3상태 · Regen 2상태)와 ApplicationGuide.tsx(지원서 가이드 모달). 화면에 잠깐만 보이는 것들을 한 장에.
function Analyzing({ stopped }) {
  const stage = { position: 'relative', overflow: 'hidden', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 18, background: 'var(--stage-bg)', color: 'var(--stage-ink-warm)', textAlign: 'center', padding: '0 32px', minHeight: 320, borderRadius: 'var(--radius-card)' };
  const light = <div style={{ pointerEvents: 'none', position: 'absolute', left: '50%', top: '-40%', width: 700, height: 400, transform: 'translateX(-50%)', background: 'radial-gradient(ellipse at 50% 0%, rgba(var(--stage-keylight-rgb),.07), transparent 62%)' }} />;
  if (stopped) { const { silent, refunded } = stopped; return (
    <div style={stage}>{light}
      {silent && <div style={{ display: 'flex', alignItems: 'center', gap: 3, height: 20 }}>{Array.from({ length: 16 }, (_, i) => <div key={i} style={{ width: 3, height: 2, background: 'rgba(255,255,255,.18)' }} />)}</div>}
      <h1 style={{ margin: 0, fontSize: 19, fontWeight: 600, color: 'var(--stage-paper)', wordBreak: 'keep-all', maxWidth: 420 }}>{silent ? '답변이 녹음되지 않았습니다' : '분석 결과를 만들지 못했습니다'}</h1>
      <p style={{ margin: 0, maxWidth: 420, fontSize: 13.5, lineHeight: 1.8, color: 'var(--stage-dim)', wordBreak: 'keep-all' }}>{silent ? (refunded ? '크레딧은 돌려드렸습니다. ' : '') + '마이크를 확인한 뒤 다시 시작해 주세요.' : '녹음과 전사는 남아 있습니다. 잠시 뒤 리포트를 다시 열어 보세요.'}</p>
      <button style={{ marginTop: 8, borderRadius: 999, border: '1px solid var(--stage-line-warm)', padding: '10px 20px', fontSize: 13.5, fontWeight: 600, color: 'var(--stage-ink-warm)' }}>내 면접으로</button>
    </div>); }
  return (
    <div style={stage}>{light}
      <div style={{ position: 'relative', width: 96, height: 96 }}>
        <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'var(--gradient-sphere)', boxShadow: 'var(--shadow-sphere)', animation: 'dm-breathe 7s ease-in-out infinite' }} />
        <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'var(--gradient-sphere-sheen)' }} />
        <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', opacity: .22, background: 'var(--gradient-voice-amber)' }} />
      </div>
      <h1 style={{ margin: 0, fontSize: 19, fontWeight: 600, color: 'var(--stage-paper)', wordBreak: 'keep-all', maxWidth: 420 }}>면접이 끝났습니다. 수고하셨습니다</h1>
      <p style={{ margin: 0, fontSize: 13.5, color: 'var(--stage-dim)', wordBreak: 'keep-all' }}>답변을 평가 중입니다</p>
      <div style={{ width: 240, height: 2, background: 'rgba(255,255,255,.08)', overflow: 'hidden' }}><div style={{ width: '25%', height: '100%', background: 'var(--stage-amber)', animation: 'dm-slide 1.6s ease-in-out infinite' }} /></div>
    </div>
  );
}
function Regen({ failed }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, padding: '64px 32px', textAlign: 'center', borderRadius: 'var(--radius-card)', border: '1px solid var(--color-line)', background: 'var(--color-bg)', minHeight: 320, boxSizing: 'border-box', justifyContent: 'center' }}>
      {!failed && <span style={{ width: 34, height: 34, borderRadius: '50%', border: '2px solid var(--color-line)', borderTopColor: 'var(--color-accent)', boxSizing: 'border-box', animation: 'dm-spin 1s linear infinite' }} />}
      <h1 style={{ margin: '8px 0 0', fontSize: 18, fontWeight: 700 }}>{failed ? '질문을 다시 뽑지 못했습니다' : '고치신 내용으로 질문을 다시 뽑고 있습니다'}</h1>
      <p style={{ margin: 0, fontSize: 13.5, color: 'var(--color-muted)' }}>{failed ? '고치신 리포트는 저장돼 있습니다.' : '잠시만 기다려 주세요'}</p>
      {failed && <OutlineButton style={{ marginTop: 8, padding: '10px 20px' }}>준비 완료로 돌아가기</OutlineButton>}
    </div>
  );
}
const EXAMPLE = [
  { name: '자기소개서', items: [{ title: '1. 지원하신 직무 분야의 전문성을 키우기 위해 꾸준히 노력한 경험', body: '저의 전문성 영역은 결함 데이터의 본질적 특성을 분석하여 적합한 검출 모델을 선택, 구현하는 것입니다. 출발점은 연구실의 딥페이크 탐지 연구였습니다. …' }, { title: '2. 팀워크를 발휘해 사람들을 연결하고 공동 목표 달성에 기여한 경험', body: '산학협력 프로젝트에서 5인 팀의 팀장 겸 IPS 알고리즘 개발을 담당했습니다. …' }] },
  { name: '경력 · 프로젝트', items: [{ title: '졸업작품 — 딥페이크 탐지 모델의 일반화 성능 개선', body: '생성형 AI가 이미지에 남기는 인위적 흔적을 탐지하는 딥페이크 탐지 모델의 일반화 성능 개선 프로젝트를 수행했습니다. 초기에는 …' }] },
];
function ApplicationGuide() {
  const b = t => <b style={{ fontWeight: 600, color: 'var(--color-ink)' }}>{t}</b>;
  const p = { margin: 0, fontSize: 14, lineHeight: 1.75, color: 'var(--color-body)' };
  return (
    <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '32px 24px', background: 'var(--overlay-dialog-bg)', borderRadius: 'var(--radius-card)', minHeight: 320 }}>
      <div style={{ display: 'flex', width: '100%', maxWidth: 640, flexDirection: 'column', overflow: 'hidden', borderRadius: 'var(--radius-card)', border: '1px solid var(--color-line)', background: 'var(--color-surface)', animation: 'dm-fade .3s ease' }}>
        <div style={{ display: 'flex', alignItems: 'center', borderBottom: '1px solid var(--color-line)', padding: '18px 26px' }}><h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, letterSpacing: '-.02em', color: 'var(--color-ink)' }}>지원서는 이렇게 넣습니다</h2><div style={{ flex: 1 }} /><button style={{ fontSize: 13, color: 'var(--color-muted)' }}>닫기</button></div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 26, padding: '22px 26px', wordBreak: 'keep-all' }}>
          <section style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <p style={p}>{b('파트')}는 회사 양식의 큰 묶음이고, {b('항목')}은 그 안의 문항 하나입니다. 자기소개서에 문항이 셋이면 파트 하나에 항목 셋, 경력·프로젝트는 파트를 따로 만들어 건마다 항목으로 둡니다.</p>
            <p style={p}>면접관은 {b('항목 하나하나를 근거로')} 질문과 꼬리질문을 하기 때문에 요약하지 말고 {b('제출한 그대로')} 붙여넣는 것이 좋습니다.</p>
            <p style={p}>지원서 PDF가 있으면 {b('PDF로 불러오기')}로 문항을 채운 뒤 확인만 하면 됩니다. 인적사항·학력 같은 부분은 빼고 가져옵니다.</p>
          </section>
          <section style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <SectionLabel>예시</SectionLabel>
            {EXAMPLE.map(part => (
              <div key={part.name} style={{ borderRadius: 'var(--radius-card)', border: '1px solid var(--color-line)', background: 'var(--color-surface)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 9, borderBottom: '1px solid var(--color-hair)', padding: '12px 16px' }}><span style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-ink)' }}>{part.name}</span><span className="num" style={{ borderRadius: 'var(--radius-chip)', border: '1px solid var(--color-line)', padding: '1px 6px', fontSize: 11, color: 'var(--color-faint)' }}>{part.items.length}</span><span style={{ fontSize: 11.5, color: 'var(--color-faintest)' }}>← 파트</span></div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '12px 16px' }}>
                  {part.items.map(item => (
                    <div key={item.title} style={{ borderRadius: 'var(--radius-control)', border: '1px solid var(--color-line-2)', background: 'var(--color-surface-2)', padding: '10px 13px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-body)' }}>{item.title}</span><span style={{ fontSize: 11.5, color: 'var(--color-faintest)' }}>← 항목</span></div>
                      <p style={{ margin: '6px 0 0', fontSize: 12.5, lineHeight: 1.7, color: 'var(--color-muted)' }}>{item.body}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </section>
        </div>
      </div>
    </div>
  );
}
/** 리서치 진행 — 구체가 어둡게 "읽고 있는" 무대 위에 진행 로그. 기다림이 면접관의 준비로 읽힌다. */
const RSTEPS = [['채용공고와 직무기술서 분석', '요구 역량 12개를 추출하고 우선순위를 매겼습니다.'], ['최근 1년 뉴스 · IR · 기술 블로그 수집', '파트너 정산 서비스 공개(3월)와 물류 자회사 설립(7월)을 확인했습니다.'], ['인재상 · 조직문화 정리', ''], ['지원서와 대조 · 검증이 필요한 항목 추출', ''], ['질문 준비', '']];
function ResearchStage() {
  const narrow = useNarrow();
  const [at, setAt] = React.useState(2);
  React.useEffect(() => { const t = setInterval(() => setAt(v => (v >= RSTEPS.length ? 0 : v + 1)), 2200); return () => clearInterval(t); }, []);
  return (
    <div style={{ position: 'relative', overflow: 'hidden', borderRadius: 'var(--radius-card)', background: 'var(--stage-bg)', color: 'var(--stage-ink-warm)', display: 'grid', gridTemplateColumns: narrow ? '1fr' : '300px minmax(0,1fr)', minHeight: 360 }}>
      <div style={{ pointerEvents: 'none', position: 'absolute', left: '30%', top: '-40%', width: 700, height: 400, transform: 'translateX(-50%)', background: 'radial-gradient(ellipse at 50% 0%, rgba(var(--stage-keylight-rgb),.07), transparent 62%)' }} />
      <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 22, padding: 28 }}>
        <div style={{ position: 'relative', width: 128, height: 128 }}>
          <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'var(--gradient-sphere)', boxShadow: 'var(--shadow-sphere)', animation: 'dm-breathe 7s ease-in-out infinite' }} />
          <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'var(--gradient-sphere-sheen)' }} />
          <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', opacity: .22, background: 'var(--gradient-voice-amber)', animation: 'dm-breathe 7s ease-in-out infinite' }} />
        </div>
        <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', gap: 6 }}><span style={{ fontSize: 15, fontWeight: 600, color: 'var(--stage-paper)' }}>면접관이 준비하고 있습니다</span><span className="num" style={{ fontSize: 12, color: 'var(--stage-dim)' }}>3분 40초 경과 · 창을 닫아도 계속됩니다</span></div>
      </div>
      <div style={{ position: 'relative', padding: narrow ? '0 20px 22px' : '26px 28px 26px 0', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 14 }}><span style={{ fontSize: 17, fontWeight: 700, letterSpacing: '-.02em', color: 'var(--stage-paper)' }}>누리테크</span><span style={{ marginLeft: 8, fontSize: 12.5, color: 'var(--stage-dim)' }}>서비스기획 · 신입</span></div>
        <div style={{ height: 2, background: 'rgba(255,255,255,.08)', overflow: 'hidden', marginBottom: 14 }}><div style={{ width: '25%', height: '100%', background: 'var(--stage-amber)', animation: 'dm-slide 1.6s ease-in-out infinite' }} /></div>
        {RSTEPS.map(([t, r], i) => { const s = i < at ? 'done' : i === at ? 'now' : 'wait'; return (
          <div key={t} style={{ display: 'flex', gap: 12, padding: '9px 0', borderBottom: i < RSTEPS.length - 1 ? '1px solid rgba(255,255,255,.07)' : 0 }}>
            <span style={{ marginTop: 3, width: 13, height: 13, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', border: s === 'wait' ? '1.5px solid rgba(255,255,255,.14)' : s === 'now' ? '1.5px solid var(--stage-amber)' : 0, borderTopColor: s === 'now' ? 'transparent' : undefined, background: s === 'done' ? 'var(--stage-amber)' : 'transparent', animation: s === 'now' ? 'dm-spin 1s linear infinite' : 'none', boxSizing: 'border-box' }}>{s === 'done' && <svg width="8" height="8" viewBox="0 0 24 24"><path d="M5 12.5l4.2 4.2L19 7.5" fill="none" stroke="#0C0F19" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" /></svg>}</span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minHeight: 36 }}><span style={{ fontSize: 13.5, fontWeight: 600, color: s === 'done' ? 'var(--stage-ink-warm)' : s === 'now' ? 'var(--stage-amber)' : 'rgba(255,255,255,.28)', transition: 'color .3s' }}>{t}</span><span style={{ fontSize: 12, color: 'var(--stage-dim)', opacity: s === 'done' && r ? 1 : 0, transition: 'opacity .4s' }}>{r || ' '}</span></div>
          </div>); })}
      </div>
    </div>
  );
}
function Gallery() {
  const narrow = useNarrow();
  const cap = t => <div style={{ fontSize: 12, color: 'var(--color-muted)', marginBottom: 10 }}>{t}</div>;
  return (
    <main style={{ maxWidth: 1160, margin: '0 auto', padding: narrow ? '28px 16px 60px' : '40px 32px 80px', display: 'flex', flexDirection: 'column', gap: 40 }}>
      <div><h1 style={{ margin: 0, fontSize: 27, fontWeight: 700, letterSpacing: '-.03em' }}>전환 화면과 빈 상태</h1><p style={{ margin: '6px 0 0', fontSize: 14, color: 'var(--color-muted)' }}>Progress.tsx · ApplicationGuide.tsx. 실제로는 전체 화면(fixed inset 0)이지만 여기서는 카드 크기로 줄였다.</p></div>
      <div>{cap('리서치 진행 — v2: 면접관이 준비하는 무대. 구체는 어둡게, 진행 로그는 오른쪽')}<ResearchStage /></div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(300px, 100%), 1fr))', gap: 16 }}>
        <div>{cap('분석 중 — 진행률 없음, 불확정 막대')}<Analyzing /></div>
        <div>{cap('분석 중 → 답변이 녹음되지 않았습니다 (크레딧 반환)')}<Analyzing stopped={{ silent: true, refunded: true }} /></div>
        <div>{cap('분석 중 → 분석 결과를 만들지 못했습니다')}<Analyzing stopped={{ silent: false }} /></div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(300px, 100%), 1fr))', gap: 16 }}>
        <div>{cap('질문 재생성 — 검토에서 리포트를 고쳤을 때만')}<Regen /></div>
        <div>{cap('질문 재생성 실패')}<Regen failed /></div>
      </div>
      <div>{cap('지원서 가이드 — 등록 2단계의 "?"가 연다. 시스템의 유일한 화면 위 다이얼로그. Esc로 닫힘')}<ApplicationGuide /></div>
    </main>
  );
}
ReactDOM.createRoot(document.getElementById('root')).render(<Gallery />);
