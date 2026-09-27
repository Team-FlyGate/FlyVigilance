import { useEffect, useState, type ReactNode } from 'react'
import { BrainProvider } from './lib/brain'
import { api, type Health } from './lib/data'
import MissionControl from './pages/MissionControl'
import Architecture from './pages/Architecture'
import LiveTriage from './pages/LiveTriage'
import SignalLab from './pages/SignalLab'
import TimeMachine from './pages/TimeMachine'
import Warehouse from './pages/Warehouse'
import Benchmarks from './pages/Benchmarks'
import Problem from './pages/Problem'
import Skills from './pages/Skills'
import KoreanPV from './pages/KoreanPV'

const I = (d: string) => (
  <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
)

const PAGES: { id: string; label: string; en: string; icon: ReactNode; sec?: string; el: () => ReactNode }[] = [
  { id: 'mission', label: '관제 센터', en: 'Mission Control', sec: 'Operate', icon: I('M12 3a9 9 0 1 0 9 9M12 7a5 5 0 1 0 5 5M12 11a1 1 0 1 0 1 1M21 3l-7.5 7.5'), el: () => <MissionControl /> },
  { id: 'triage', label: '라이브 트리아지', en: 'Live Triage', icon: I('M3 12h4l3-8 4 16 3-8h4'), el: () => <LiveTriage /> },
  { id: 'korea', label: '국내 보고 · 인과성', en: 'Korean PV Intake', icon: I('M4 4h16v16H4zM8 9h8M8 13h8M8 17h5'), el: () => <KoreanPV /> },
  { id: 'signals', label: '신호 연구실', en: 'Signal Lab', icon: I('M4 20V10M10 20V4M16 20v-7M22 20H2'), el: () => <SignalLab /> },
  { id: 'timemachine', label: '신호 타임머신', en: 'Signal Time Machine', icon: I('M12 7v5l3 2M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5'), el: () => <TimeMachine /> },
  { id: 'problem', label: '문제 정의', en: 'Why it matters', sec: 'Design', icon: I('M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z'), el: () => <Problem /> },
  { id: 'architecture', label: '아키텍처', en: 'Connectome Architecture', icon: I('M4 6h6v6H4zM14 12h6v6h-6zM10 9h2a2 2 0 0 1 2 2v4M17 12V6h-3'), el: () => <Architecture /> },
  { id: 'warehouse', label: '데이터 웨어하우스', en: 'PV Warehouse', icon: I('M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3ZM4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6'), el: () => <Warehouse /> },
  { id: 'bench', label: '벤치마크', en: 'Measured Performance', icon: I('M3 3v18h18M7 15l4-4 3 3 6-7'), el: () => <Benchmarks /> },
  { id: 'skills', label: 'NVIDIA 스킬 · 거버넌스', en: 'Skills & Guardrails', icon: I('M12 2 3 7v6c0 5 4 8 9 9 5-1 9-4 9-9V7l-9-5ZM9 12l2 2 4-4'), el: () => <Skills /> },
]

function useHashPage() {
  const get = () => (location.hash.replace('#/', '') || 'mission')
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

  return (
    <BrainProvider>
      <div className="app-bg" />
      <div className="shell">
        <nav className="nav">
          <div className="brand">
            <svg className="brand-mark" viewBox="0 0 64 64"><defs><radialGradient id="bm" cx="50%" cy="45%" r="55%"><stop offset="0" stopColor="#9ffcff" /><stop offset="0.55" stopColor="#2bd9ff" /><stop offset="1" stopColor="#0a1830" /></radialGradient></defs><rect width="64" height="64" rx="14" fill="#0a1122" /><ellipse cx="32" cy="30" rx="20" ry="15" fill="url(#bm)" opacity=".9" /><path d="M12 30c6-8 14-8 20 0s14 8 20 0" stroke="#76b900" strokeWidth="3" fill="none" strokeLinecap="round" /><circle cx="32" cy="46" r="4" fill="#ffb547" /></svg>
            <div>
              <div className="brand-name">FlyVigilance</div>
              <div className="brand-sub">connectome-routed PV agent</div>
            </div>
          </div>
          {PAGES.map((p) => (
            <div key={p.id} style={{ display: 'contents' }}>
              {p.sec && <div className="nav-sec">{p.sec}</div>}
              <button className={`nav-item ${p.id === cur.id ? 'active' : ''}`} onClick={() => go(p.id)}>
                {p.icon}
                <span className="lbl">{p.label}<small>{p.en}</small></span>
              </button>
            </div>
          ))}
          <a className="nav-item" href="/showreel/index.html" target="_blank" rel="noreferrer" style={{ marginTop: 10, textDecoration: 'none', borderColor: 'rgba(255,79,216,0.35)' }}>
            <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><circle cx="12" cy="12" r="9" /><path d="m10 8 6 4-6 4V8Z" fill="currentColor" /></svg>
            <span className="lbl">쇼릴 영상<small>2:30 motion showreel</small></span>
          </a>
          <div className="nav-foot">
            <div className="status-row"><span className={`dot ${health?.jev ? 'on pulse' : healthErr ? 'off' : ''}`} />Jev System-1 {health?.jev ? 'online' : healthErr ? 'offline' : '…'}</div>
            <div className="status-row"><span className={`dot ${health?.nim ? 'on pulse' : healthErr ? 'off' : ''}`} />NVIDIA NIM {health?.nim ? 'online' : healthErr ? 'offline' : '…'}</div>
            <div className="status-row"><span className="dot on" />MaleCNS v1.0 · FAERS {health?.signals_asof ?? '2026Q2'}</div>
            <div style={{ marginTop: 8, lineHeight: 1.5 }}>NVIDIA Korea Agentic AI Hackathon 2026</div>
          </div>
        </nav>
        <main className="main">{cur.el()}</main>
      </div>
    </BrainProvider>
  )
}
