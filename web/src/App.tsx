import { useEffect, useState, type ReactNode } from 'react'
import { BrainProvider } from './lib/brain'
import { api, type Health } from './lib/data'
import Overview from './pages/Overview'
import Discovery from './pages/Discovery'
import DiscoveryStep from './pages/DiscoveryStep'
import DiscoveryEvidence from './pages/DiscoveryEvidence'
import Agent from './pages/Agent'
import CliTutorial from './pages/CliTutorial'
import MissionControl from './pages/MissionControl'
import Architecture from './pages/Architecture'
import LiveTriage from './pages/LiveTriage'
import SignalLab from './pages/SignalLab'
import TimeMachine from './pages/TimeMachine'
import Warehouse from './pages/Warehouse'
import Benchmarks from './pages/Benchmarks'
import Problem from './pages/Problem'
import Skills from './pages/Skills'
import CallLog from './pages/CallLog'
import KoreanPV from './pages/KoreanPV'
import Validation from './pages/Validation'
import Glossary from './pages/Glossary'
import Term from './components/Term'

const I = (d: string) => (
  <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
)

interface Page { id: string; label: string; en: string; icon: ReactNode; el: () => ReactNode; hot?: boolean }

// 메뉴는 네 묶음입니다: 개요(문제 정의 · 용어 풀이 포함) · STEP 1 시판 전 · STEP 2 시판 후 · 에이전트
const GROUPS: { step?: string; name?: string; color?: string; pages: Page[] }[] = [
  { pages: [
    { id: 'overview', label: '개요', en: 'Discovery → Vigilance', icon: I('M3 11 12 4l9 7M5 10v10h5v-6h4v6h5V10'), el: () => <Overview /> },
    { id: 'problem', label: '문제 정의', en: 'Why it matters', icon: I('M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z'), el: () => <Problem /> },
    { id: 'glossary', label: '용어 풀이', en: 'Glossary · 약어와 전문 용어', icon: I('M4 19.5V5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2Zm0 0a2 2 0 0 0 2 2h13M9 8h6M9 12h4'), el: () => <Glossary /> },
  ] },
  { step: 'STEP 1 · 시판 전', name: 'FlyDiscovery', color: 'var(--c-sense)', pages: [
    { id: 'discovery', label: '후보 탐색 개요', en: 'Discovery · 약물 패널', icon: I('M12 3l7.8 4.5v9L12 21l-7.8-4.5v-9ZM12 8.5l3 1.75v3.5L12 15.5l-3-1.75v-3.5Z'), el: () => <Discovery /> },
    { id: 'd-msa', label: 'MSA-Search', en: '01 · 상동 서열 정렬', icon: I('M4 6h16M4 10h10M4 14h16M4 18h7'), el: () => <DiscoveryStep key="msa" step="msa" /> },
    { id: 'd-of3', label: 'OpenFold3', en: '02 · 복합체 구조 예측', icon: I('M6 4c6 0 6 4 12 4M6 10c6 0 6 4 12 4M6 16c6 0 6 4 12 4'), el: () => <DiscoveryStep key="of3" step="of3" /> },
    { id: 'd-diffdock', label: 'DiffDock', en: '03 · 도킹 · 재도킹', icon: I('M12 3a9 9 0 1 0 9 9M12 8a4 4 0 1 0 4 4M3 3l6 6'), el: () => <DiscoveryStep key="dd" step="dd" /> },
    { id: 'd-boltz', label: 'Boltz-2', en: '04 · 친화도 예측 · 실측 대조', icon: I('M4 20 20 4M6 14l2 2M10 10l2 2M14 6l2 2'), el: () => <DiscoveryStep key="bz" step="bz" /> },
    { id: 'd-critic', label: '크리틱', en: '05 · 근거를 넘는 주장 반려', icon: I('M9 12l2 2 4-4M12 3 4 7v6c0 4 3.5 7 8 8 4.5-1 8-4 8-8V7l-8-4Z'), el: () => <DiscoveryStep key="critic" step="critic" /> },
    { id: 'd-evidence', label: '근거 검증', en: '06 · 검증 → 선택성 → 후보 카드', icon: I('M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14ZM21 21l-5-5M8 11l2 2 4-4'), el: () => <DiscoveryEvidence /> },
  ] },
  { step: 'STEP 2 · 시판 후', name: 'FlyVigilance', color: 'var(--nvidia)', pages: [
    { id: 'mission', label: '관제 센터', en: 'Mission Control', icon: I('M12 3a9 9 0 1 0 9 9M12 7a5 5 0 1 0 5 5M12 11a1 1 0 1 0 1 1M21 3l-7.5 7.5'), el: () => <MissionControl /> },
    { id: 'triage', label: '사례 분류 (트리아지)', en: 'Live Triage · 보고 한 건', icon: I('M3 12h4l3-8 4 16 3-8h4'), el: () => <LiveTriage /> },
    { id: 'korea', label: '국내 보고 · 인과성', en: 'Korean PV Intake', icon: I('M4 4h16v16H4zM8 9h8M8 13h8M8 17h5'), el: () => <KoreanPV /> },
    { id: 'signals', label: '신호 연구실', en: 'Signal Lab', icon: I('M4 20V10M10 20V4M16 20v-7M22 20H2'), el: () => <SignalLab /> },
    { id: 'timemachine', label: '신호 타임머신', en: 'Signal Time Machine', icon: I('M12 7v5l3 2M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5'), el: () => <TimeMachine /> },
    { id: 'validation', label: '검증', en: 'Reference Validation', icon: I('M9 12l2 2 4-4M4 4h16v16H4z'), el: () => <Validation /> },
    { id: 'bench', label: '벤치마크', en: 'Measured Performance', icon: I('M3 3v18h18M7 15l4-4 3 3 6-7'), el: () => <Benchmarks /> },
    { id: 'warehouse', label: '데이터 웨어하우스', en: 'PV Warehouse', icon: I('M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3ZM4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6'), el: () => <Warehouse /> },
  ] },
  { step: '에이전트 · NVIDIA', name: 'NemoClaw', color: '#e2a74e', pages: [
    { id: 'cli', label: 'FlyGate Agent CLI', en: '한 줄 설치 · 실제 터미널 · 튜토리얼', icon: <span className="mono" aria-hidden="true">›_</span>, el: () => <CliTutorial />, hot: true },
    { id: 'agent', label: '에이전트 구성', en: 'NemoClaw · OpenShell', icon: I('M12 3 4 7v10l8 4 8-4V7l-8-4ZM4 7l8 4 8-4M12 11v10'), el: () => <Agent /> },
    { id: 'skills', label: 'NVIDIA 스킬 · 거버넌스', en: 'Skills & Guardrails', icon: I('M12 2 3 7v6c0 5 4 8 9 9 5-1 9-4 9-9V7l-9-5ZM9 12l2 2 4-4'), el: () => <Skills /> },
    { id: 'calls', label: 'NVIDIA 호출 로그', en: 'API call log · 요청 ID · 증거 대응표', icon: I('M4 5h16M4 10h16M4 15h10M4 20h7M17 15l2 2 3-4'), el: () => <CallLog /> },
    { id: 'architecture', label: '아키텍처 · 층 구성', en: 'Connectome-routed Architecture', icon: I('M4 6h6v6H4zM14 12h6v6h-6zM10 9h2a2 2 0 0 1 2 2v4M17 12V6h-3'), el: () => <Architecture /> },
  ] },
]
const PAGES = GROUPS.flatMap((g) => g.pages)

function useHashPage() {
  const get = () => (location.hash.replace('#/', '').split('?')[0] || 'overview')
  const [page, setPage] = useState(get)
  useEffect(() => {
    const on = () => setPage(get())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return [page, (p: string) => { location.hash = `/${p}` }] as const
}

export default function App() {
  const [page, go] = useHashPage()
  const [health, setHealth] = useState<Health | null>(null)
  const [healthErr, setHealthErr] = useState(false)
  useEffect(() => { api<Health>('/api/health').then(setHealth).catch(() => setHealthErr(true)) }, [])
  const cur = PAGES.find((p) => p.id === page) ?? PAGES[0]
  useEffect(() => { document.querySelector('.main')?.scrollTo({ top: 0 }) }, [page])
  useEffect(() => { document.title = cur.id === 'overview' ? 'Project-FlyGate' : `${cur.label} · Project-FlyGate` }, [cur])
  const live = (on: boolean | undefined) => (on ? 'online' : healthErr ? 'offline' : '…')

  return (
    <BrainProvider>
      <div className="app-bg" />
      <div className="shell">
        <nav className="nav">
          <div className="brand">
            <svg className="brand-mark" viewBox="0 0 64 64"><defs><radialGradient id="bm" cx="50%" cy="45%" r="55%"><stop offset="0" stopColor="#9ffcff" /><stop offset="0.55" stopColor="#2bd9ff" /><stop offset="1" stopColor="#0a1830" /></radialGradient></defs><rect width="64" height="64" rx="14" fill="#0a1122" /><ellipse cx="32" cy="30" rx="20" ry="15" fill="url(#bm)" opacity=".9" /><path d="M12 30c6-8 14-8 20 0s14 8 20 0" stroke="#76b900" strokeWidth="3" fill="none" strokeLinecap="round" /><circle cx="32" cy="46" r="4" fill="#ffb547" /></svg>
            <div>
              <div className="brand-name">FlyGate</div>
              <div className="brand-sub" style={{ letterSpacing: 0.4, textTransform: 'none' }}>Discovery → Vigilance</div>
            </div>
          </div>
          {GROUPS.map((g, gi) => (
            <div key={gi} style={{ display: 'contents' }}>
              {g.step && <div className="nav-grp"><span>{g.step}</span><b style={{ color: g.color }}>{g.name}</b></div>}
              {g.pages.map((p) => (
                <button key={p.id} className={`nav-item ${p.hot ? 'nav-hot' : ''} ${p.id === cur.id ? 'active' : ''}`} onClick={() => go(p.id)}>
                  {p.icon}
                  <span className="lbl">{p.label}<small>{p.en}</small></span>
                </button>
              ))}
            </div>
          ))}
          <a className="nav-item nav-reel" href="/showreel/FlyGate_showreel_v4.2.0.html" target="_blank" rel="noreferrer">
            <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><circle cx="12" cy="12" r="9" /><path d="m10 8 6 4-6 4V8Z" fill="currentColor" /></svg>
            <span className="lbl">쇼릴 영상<small>FlyGate · v4.2 · 4분 4초</small></span>
          </a>
          <div className="nav-foot">
            <div className="status-row"><span className={`dot ${health?.jev ? 'on pulse' : healthErr ? 'off' : ''}`} /><Term k="NAR">비자기회귀 판단 모델</Term> {live(health?.jev)}</div>
            <div className="status-row"><span className={`dot ${health?.nim ? 'on pulse' : healthErr ? 'off' : ''}`} />NVIDIA <Term k="NIM" /> {live(health?.nim)}</div>
            <a className="status-row status-link" href="#/agent"><span className="dot" style={{ background: '#e2a74e' }} />OpenShell 정책 →</a>
            <div className="status-row"><span className="dot on" /><Term k="MaleCNS">MaleCNS v1.0</Term> · <Term k="FAERS" /> {health?.signals_asof ?? '2026Q2'}</div>
            <div style={{ marginTop: 6, lineHeight: 1.5 }}>NVIDIA Korea Agentic AI Hackathon 2026</div>
          </div>
        </nav>
        <main className="main">{cur.el()}</main>
      </div>
    </BrainProvider>
  )
}
