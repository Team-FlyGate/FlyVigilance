import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import DockingView, { type RedockScene } from '../components/DockingView'
import HeroDocking, { type HeroExtras, type HeroScene, type StepId } from '../components/HeroDocking'
import { Card, Kpi, Loading, PageHead } from '../components/ui'
import { getJSON } from '../lib/data'
import Step2Handoff from '../components/Step2Handoff'
import type { DiscoveryMeasurements, DockEval } from '../lib/types'
import Term from '../components/Term'
import { t } from '../lib/i18n'
import { dataText } from '../lib/discovery'

// STEP 1 FlyDiscovery: 개요 페이지와, 다섯 단계 페이지(DiscoveryStep.tsx)가 함께 쓰는 데이터 · 부품입니다.
// 데이터는 모두 fly_discovery/measurements/ 의 실측 JSON 이고, scripts/sync-discovery.mjs 가 /discovery/data/ 로 복사합니다.

export const PAGE = '/discovery/index.html'
// 다섯 단계 메뉴 ↔ 페이지 id (App.tsx 의 STEP 1 묶음)
export const STEP_PAGES: Record<StepId, string> = { msa: 'd-msa', of3: 'd-of3', dd: 'd-diffdock', bz: 'd-boltz', critic: 'd-critic' }
const DWELL_MS = 6000

interface ScenesFile { pocket_radius_A: number; scenes: Record<string, RedockScene> }
interface PanelRow {
  drug: string; cases: number; serious: number; molecule_type: string | null; mechanism: string | null
  docking: { status: 'measured' | 'not_run' | 'not_applicable'; gene?: string; pdb?: string; top1_rmsd?: number; success?: boolean }
}
interface PanelFile { n_cases: number; n_primary_suspect_drugs: number; rows: PanelRow[] }
type CriticFile = Record<string, { sec: number; caught: number; n_over: number; passed: number; n_valid: number; rows: [string, string, string][] }>

export const title = (s: string) => s.split('\\').map((x) => x.charAt(0).toUpperCase() + x.slice(1).toLowerCase()).join(' / ')
const short = (k: string) => (k.includes('super') ? 'Nemotron 3 Super' : k.includes('lightning') ? 'Nemotron 3.5 Lightning' : k.replace('nvidia/', ''))

export function useDiscoveryData() {
  const [m, setM] = useState<DiscoveryMeasurements | null>(null)
  const [dock, setDock] = useState<Record<string, DockEval> | null>(null)
  const [scenes, setScenes] = useState<ScenesFile | null>(null)
  const [hero, setHero] = useState<HeroScene | null>(null)
  const [panel, setPanel] = useState<PanelFile | null>(null)
  const [critic, setCritic] = useState<CriticFile | null>(null)
  const [missing, setMissing] = useState(false)
  useEffect(() => {
    getJSON<DiscoveryMeasurements>('/discovery/data/measurements.json').then(setM).catch(() => setMissing(true))
    getJSON<Record<string, DockEval>>('/discovery/data/dd_eval_all.json').then(setDock).catch(() => null)
    getJSON<ScenesFile>('/discovery/data/redock_scenes.json').then(setScenes).catch(() => null)
    getJSON<HeroScene>('/discovery/data/hero_scene.json').then(setHero).catch(() => null)
    getJSON<PanelFile>('/discovery/data/drug_panel.json').then(setPanel).catch(() => null)
    getJSON<CriticFile>('/discovery/data/critic_v2.json').then(setCritic).catch(() => null)
  }, [])
  const critics = critic ? Object.entries(critic).sort((a, b) => b[1].caught - a[1].caught) : []
  const [bestName, best] = critics[0] ?? []
  const bm = m?.parp1_affinity_benchmark
  const extras: HeroExtras | null = m ? {
    boltz: (() => { const r = m.diffdock_boltz2_chembl.find((x) => x[0] === 'niraparib@parp1'); return r ? { pic50: r[3], p: r[4], chembl: r[5], n: r[6] } : null })(),
    bench: bm ? { n: bm.n, spearman: bm.spearman, mae: bm.mae } : null,
    critic: best ? { model: short(bestName!), caught: best.caught, n_over: best.n_over, passed: best.passed, n_valid: best.n_valid, sec: best.sec, rows: best.rows } : null,
  } : null
  const redockList = useMemo(() => (scenes ? Object.entries(scenes.scenes) : []), [scenes])
  return { m, dock, scenes, hero, panel, critic, missing, extras, best, bestName: bestName ? short(bestName) : '', redockList }
}

export function MissingCard() {
  return (
    <Card title={t('FlyDiscovery 데이터를 찾지 못했습니다', 'FlyDiscovery data not found')} sub={t('web/public/discovery/ 가 비어 있습니다', 'web/public/discovery/ is empty')}>
      {t(<div className="note">원본은 <span className="mono">fly_discovery/</span>에 있고, <span className="mono">npm run dev</span> · <span className="mono">npm run build</span> 전에
        <span className="mono"> scripts/sync-discovery.mjs</span>가 복사합니다. 직접 실행하려면 <span className="mono">cd web && npm run sync-discovery</span>를 실행하세요.</div>,
      <div className="note">The source lives in <span className="mono">fly_discovery/</span>, and <span className="mono">scripts/sync-discovery.mjs</span> copies it before
        <span className="mono"> npm run dev</span> · <span className="mono">npm run build</span>. To run it yourself, use <span className="mono">cd web && npm run sync-discovery</span>.</div>)}
    </Card>
  )
}

export function Tile({ tech, name, value, sub, color }: { tech: string; name: string; value: ReactNode; sub: ReactNode; color: string }) {
  return (
    <div className="card" style={{ padding: '12px 14px', boxShadow: `var(--shadow), inset 3px 0 0 ${color}` }}>
      <div className="row between" style={{ gap: 6 }}>
        <b style={{ fontFamily: 'var(--font)', fontSize: 14 }}>{name}</b>
        <span className="mono" style={{ fontSize: 9.5, letterSpacing: 0.6, color, textTransform: 'uppercase', whiteSpace: 'nowrap' }}>{tech}</span>
      </div>
      <div className="num" style={{ fontSize: 21, fontWeight: 600, margin: '6px 0 2px' }}>{value}</div>
      <div style={{ fontSize: 11.5, color: 'var(--text-2)', lineHeight: 1.45 }}>{sub}</div>
    </div>
  )
}

// 같은 출처의 iframe 이라 문서 높이를 읽어 iframe 높이를 맞춥니다
function AutoFrame({ src }: { src: string }) {
  const ref = useRef<HTMLIFrameElement>(null)
  const [h, setH] = useState(1900)
  useEffect(() => {
    const f = ref.current
    if (!f) return
    let ro: ResizeObserver | null = null
    const onLoad = () => {
      try {
        const doc = f.contentDocument
        if (!doc?.body) return
        const fit = () => setH((old) => {
          const next = Math.min(8000, Math.max(900, doc.documentElement.scrollHeight))
          return Math.abs(next - old) > 2 ? next : old
        })
        fit()
        ro?.disconnect()
        ro = new ResizeObserver(fit)
        ro.observe(doc.body)
      } catch { /* 다른 출처로 옮겨 가면 기본 높이를 씁니다 */ }
    }
    f.addEventListener('load', onLoad)
    return () => { f.removeEventListener('load', onLoad); ro?.disconnect() }
  }, [])
  return <iframe ref={ref} src={src} title={t('FlyDiscovery 워크벤치', 'FlyDiscovery workbench')} style={{ width: '100%', height: h, border: 0, display: 'block', background: 'var(--bg)' }} />
}

function verdictChip(s: RedockScene) {
  if (s.success === null || s.top1_rmsd === null) return <span className="chip jev">{t('도킹 완료', 'Docked')}</span>
  return s.success ? <span className="chip ok">✓ {s.top1_rmsd.toFixed(2)} Å</span> : <span className="chip bad">✗ {s.top1_rmsd.toFixed(2)} Å</span>
}

function PoseMeter({ s, settled }: { s: RedockScene; settled: boolean }) {
  const conf = s.poses.map((p) => p.confidence ?? 0)
  const lo = Math.min(-3, ...conf), hi = Math.max(1.2, ...conf)
  return (
    <div className="stack" style={{ gap: 7 }}>
      {s.poses.map((p) => {
        const v = ((p.confidence ?? lo) - lo) / (hi - lo)
        const ok = (p.rmsd ?? 99) <= 2
        return (
          <div key={p.rank} style={{ display: 'grid', gridTemplateColumns: '44px 1fr 44px 58px', gap: 8, alignItems: 'center' }}>
            <span className="mono dim" style={{ fontSize: 10.5 }}>pose {p.rank}</span>
            <div className="pbar" style={{ height: 6 }}><i style={{ width: settled ? `${v * 100}%` : '0%', background: p.rank === 1 ? 'var(--jev)' : 'var(--c-encode)', transition: `width .6s ease ${p.rank * 0.08}s` }} /></div>
            <span className="num" style={{ fontSize: 10.5, textAlign: 'right' }}>{p.confidence === null ? '–' : p.confidence.toFixed(2)}</span>
            <span className="num" style={{ fontSize: 10.5, textAlign: 'right', color: settled ? (ok ? 'var(--ok)' : 'var(--bad)') : 'var(--text-3)' }}>{p.rmsd === null ? '–' : `${p.rmsd.toFixed(2)} Å`}</span>
          </div>
        )
      })}
    </div>
  )
}

/** 재도킹 벤치: 가운데 장면 + 오른쪽 Docking Stream. DiffDock 페이지에서 씁니다 */
export function RedockBench({ list, pocketR }: { list: [string, RedockScene][]; pocketR?: number }) {
  const [idx, setIdx] = useState(0)
  const [play, setPlay] = useState(0)
  const [settled, setSettled] = useState(false)
  const [played, setPlayed] = useState(1)
  useEffect(() => {
    if (!list.length) return
    const id = setTimeout(() => { setIdx((k) => (k + 1) % list.length); setPlayed((n) => Math.min(list.length, n + 1)); setPlay((p) => p + 1) }, DWELL_MS)
    return () => clearTimeout(id)
  }, [list.length, play])
  useEffect(() => setSettled(false), [idx, play])
  const cur = list[idx]?.[1] ?? null
  const feed = list.length ? Array.from({ length: Math.min(played, 7) }, (_, k) => list[(idx - k + list.length) % list.length]) : []
  const all = list.map(([, s]) => s)
  const pass = all.filter((s) => s.success).length
  const soluble = all.filter((s) => !s.membrane), membrane = all.filter((s) => s.membrane)
  return (
    <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.75fr) minmax(320px, 1fr)', marginBottom: 16 }}>
      <Card className="flush" style={{ minHeight: 600 }}>
        {cur && <>
          <div style={{ position: 'absolute', left: 20, top: 16, zIndex: 2, pointerEvents: 'none' }}>
            <div className="eyebrow" style={{ color: 'var(--text-3)' }}>Live redock · DiffDock NIM · {t('포즈 5개 중 1순위', 'top-ranked of 5 poses')}</div>
            <div style={{ fontFamily: 'var(--font)', fontSize: 22, fontWeight: 600, marginTop: 4 }}>{title(cur.drug)} <span className="dim" style={{ fontWeight: 400 }}>→</span> {cur.gene}</div>
            <div className="mono dim" style={{ fontSize: 11, marginTop: 2 }}>{cur.target} · PDB {cur.pdb} chain {cur.chain}{cur.membrane ? t(' · 세포막 단백질', ' · membrane protein') : ''}</div>
            <div style={{ marginTop: 10, minHeight: 28 }}>{settled ? <span className="fade-in">{verdictChip(cur)}</span> : <span className="chip"><span className="dot on pulse" style={{ background: 'var(--jev)' }} />docking…</span>}</div>
            {cur.note && <div className="dim" style={{ fontSize: 11.5, marginTop: 6, maxWidth: 360 }}>{dataText(cur.note)}</div>}
          </div>
          <div style={{ position: 'absolute', right: 16, bottom: 16, zIndex: 2, width: 330, padding: 14, borderRadius: 14, background: 'rgba(5,9,18,0.72)', border: '1px solid var(--line)', backdropFilter: 'blur(10px)' }}>
            <div className="row between" style={{ marginBottom: 8 }}>
              <span className="eyebrow" style={{ color: 'var(--text-2)' }}>Pose confidence</span>
              <span className="mono dim" style={{ fontSize: 10 }}>{t('conf · RMSD vs 결정 구조', 'conf · RMSD vs crystal structure')}</span>
            </div>
            <PoseMeter s={cur} settled={settled} />
          </div>
          <div style={{ position: 'absolute', left: 16, bottom: 16, zIndex: 2, pointerEvents: 'none' }} className="stack">
            <span className="eyebrow" style={{ color: 'var(--text-3)' }}>Legend</span>
            <div className="stack" style={{ gap: 4, fontSize: 11.5 }}>
              <span><span className="legend-dot" style={{ background: 'var(--jev)', marginRight: 8 }} />{t('DiffDock 1순위 포즈 (예측)', 'DiffDock top-ranked pose (predicted)')}</span>
              <span><span className="legend-dot" style={{ background: '#e8eefc', opacity: 0.6, marginRight: 8 }} />{t('결정 구조 리간드 (정답)', 'Crystal-structure ligand (ground truth)')}</span>
              <span><span className="legend-dot" style={{ background: 'var(--c-encode)', marginRight: 8 }} />{t('포켓 원자', 'Pocket atoms')} · {t(`${pocketR ?? 9} Å 이내`, `within ${pocketR ?? 9} Å`)}</span>
              <span><span className="legend-dot" style={{ background: 'var(--c-sense)', marginRight: 8 }} />{t('수용체 리본 (결정 구조)', 'Receptor ribbon (crystal structure)')}</span>
            </div>
          </div>
        </>}
        {cur ? <DockingView scene={cur} height={600} playKey={play} onSettled={() => setSettled(true)} /> : <div className="shimmer" style={{ height: 600 }} />}
      </Card>
      <Card title="Docking Stream" sub={t('공결정 구조의 원래 리간드를 DiffDock NIM으로 다시 도킹한 실측 결과를 차례로 재생합니다. 누르면 그 장면으로 넘어갑니다', 'Replays measured results of redocking each co-crystal structure’s original ligand with the DiffDock NIM (NVIDIA Inference Microservice). Click an entry to jump to that scene')}
        right={<span className="chip nv"><span className="dot on pulse" style={{ background: 'var(--nvidia)' }} />live replay</span>}>
        {list.length ? (
          <div className="stack" style={{ gap: 8 }}>
            <div className="row wrap" style={{ gap: 6 }}>
              <span className="chip ok">{t('통과', 'Pass')} {pass}</span><span className="chip bad">{t('실패', 'Fail')} {all.length - pass}</span>
              <span className="chip">{t('가용성 단백질', 'Soluble proteins')} {soluble.filter((s) => s.success).length}/{soluble.length}</span>
              <span className="chip">{t('세포막 단백질', 'Membrane proteins')} {membrane.filter((s) => s.success).length}/{membrane.length}</span>
            </div>
            <div className="mono dim" style={{ fontSize: 10.5 }}>{t(`재생 ${Math.min(played, list.length)}/${list.length}건 · 기준 1순위 포즈 중원자 RMSD ≤ 2 Å`, `Played ${Math.min(played, list.length)}/${list.length} · criterion: top-ranked pose heavy-atom RMSD ≤ 2 Å`)}</div>
            {feed.map(([key, s], k) => (
              <button key={`${key}-${k === 0 ? play : k}`} className={k === 0 ? 'fade-in' : ''} onClick={() => { setIdx(list.findIndex(([kk]) => kk === key)); setPlay((p) => p + 1) }}
                style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 10, padding: '9px 12px', borderRadius: 11, textAlign: 'left', cursor: 'pointer',
                  background: k === 0 ? 'rgba(55,230,255,0.07)' : 'rgba(10,16,30,0.5)', border: `1px solid ${k === 0 ? 'rgba(55,230,255,0.3)' : 'var(--line)'}`, opacity: 1 - k * 0.1 }}>
                <div style={{ minWidth: 0 }}>
                  <div className="row" style={{ gap: 8 }}>
                    <span className="chip" style={{ fontSize: 9.5 }}>{s.membrane ? t('세포막', 'Membrane') : t('가용성', 'Soluble')}</span>
                    <b style={{ fontSize: 12.5, fontFamily: 'var(--font)' }}>{title(s.drug)}</b>
                  </div>
                  <div className="dim" style={{ fontSize: 11.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.gene} · {s.target}</div>
                  <div className="mono dim" style={{ fontSize: 9.5 }}>PDB {s.pdb} · conf {s.poses[0]?.confidence?.toFixed(2) ?? '–'}</div>
                </div>
                <div style={{ textAlign: 'right' }}>{k === 0 && !settled ? <span className="chip">docking…</span> : verdictChip(s)}</div>
              </button>
            ))}
          </div>
        ) : <div className="shimmer" style={{ height: 300 }} />}
      </Card>
    </div>
  )
}

export function CriticStream({ rows }: { rows: [string, string, string][] }) {
  const [i, setI] = useState(0)
  useEffect(() => {
    if (!rows.length) return
    const id = setInterval(() => setI((k) => k + 1), 2600)
    return () => clearInterval(id)
  }, [rows.length])
  const feed = Array.from({ length: Math.min(4, rows.length) }, (_, k) => rows[(i - k + rows.length * 10) % rows.length])
  return (
    <div className="stack" style={{ gap: 8 }}>
      {feed.map((r, k) => {
        const pass = r[1] === 'PASS'
        return (
          <div key={`${i - k}`} className={k === 0 ? 'fade-in' : ''} style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 10, alignItems: 'center',
            padding: '9px 12px', borderRadius: 11, opacity: 1 - k * 0.18,
            background: k === 0 ? 'rgba(55,230,255,0.07)' : 'rgba(10,16,30,0.5)', border: `1px solid ${k === 0 ? 'rgba(55,230,255,0.3)' : 'var(--line)'}` }}>
            <span style={{ fontSize: 12.5 }}>{dataText(r[0])}</span>
            <span className="row" style={{ gap: 6 }}>
              <span className="mono dim" style={{ fontSize: 10 }}>{t('정답', 'Truth')}</span><span className={`chip ${pass ? 'ok' : 'bad'}`}>{pass ? 'PASS' : 'REJECT'}</span>
              {r[2] !== 'NONE' && <span className="mono" style={{ fontSize: 10.5, color: r[2] === r[1] ? 'var(--ok)' : 'var(--bad)' }}>{t('모델', 'Model')} {r[2]} {r[2] === r[1] ? '✓' : '✗'}</span>}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export function DrugPanel({ panel }: { panel: PanelFile | null }) {
  return (
    <Card title={t('약물 패널', 'Drug panel')} sub={panel ? t(`FAERS 2026Q2 데모 케이스 ${panel.n_cases}건의 주의심약물 ${panel.n_primary_suspect_drugs}종 중 케이스 상위 20종과 재도킹 약물 · 분자 종류와 기전은 ChEMBL`, `Top 20 of ${panel.n_primary_suspect_drugs} primary suspect drugs by case count across ${panel.n_cases} FAERS (FDA Adverse Event Reporting System) 2026Q2 demo cases, plus the redocked drugs · molecule type and mechanism from ChEMBL`) : ''} style={{ marginBottom: 16 }}>
      {panel ? (
        <div className="stack" style={{ gap: 0 }}>
          <div className="mono dim" style={{ display: 'grid', gridTemplateColumns: '1.3fr 0.7fr 0.8fr 2.4fr 1.3fr', gap: 12, fontSize: 10.5, padding: '6px 4px', textTransform: 'uppercase', letterSpacing: 0.6 }}>
            <span>{t('약물', 'Drug')}</span><span>{t('케이스 · 중대', 'Cases · serious')}</span><span>{t('분자', 'Molecule')}</span><span>{t('작용 기전', 'Mechanism of action')}</span><span>{t('재도킹', 'Redock')}</span>
          </div>
          {panel.rows.map((r) => {
            const d = r.docking
            const type = r.molecule_type === 'Small molecule' ? [t('소분자', 'Small molecule'), 'var(--c-sense)'] : r.molecule_type === 'Antibody' ? [t('항체', 'Antibody'), 'var(--c-feedback)'] : r.molecule_type === 'Protein' ? [t('단백질 · 펩타이드', 'Protein · peptide'), 'var(--c-feedback)'] : [t('기타', 'Other'), 'var(--text-3)']
            return (
              <div key={r.drug} style={{ display: 'grid', gridTemplateColumns: '1.3fr 0.7fr 0.8fr 2.4fr 1.3fr', gap: 12, fontSize: 12.5, padding: '8px 4px', borderTop: '1px solid var(--line)', alignItems: 'baseline' }}>
                <span className="row" style={{ gap: 8 }}><b style={{ fontFamily: 'var(--font)' }}>{title(r.drug)}</b><Step2Handoff drug={r.drug.split('\\')[0].toLowerCase()} compact /></span>
                <span className="num">{r.cases} <span className="dim">· {r.serious}</span></span>
                <span style={{ color: type[1] }}>{type[0]}</span>
                <span className="dim">{r.mechanism ?? '—'}</span>
                <span className="num" style={{ color: d.status === 'measured' ? (d.success ? 'var(--ok)' : 'var(--bad)') : 'var(--text-3)' }}>
                  {d.status === 'measured' ? `${d.gene} · ${d.pdb} · ${d.top1_rmsd?.toFixed(2)} Å ${d.success ? '✓' : '✗'}` : d.status === 'not_run' ? t('미조회', 'Not run') : t('대상 아님', 'Not applicable')}
                </span>
              </div>
            )
          })}
        </div>
      ) : <div className="shimmer" style={{ height: 200 }} />}
    </Card>
  )
}

export default function Discovery() {
  const { m, hero, panel, missing, extras, redockList } = useDiscoveryData()
  const [showBench, setShowBench] = useState(false)
  const all = redockList.map(([, s]) => s)
  const pass = all.filter((s) => s.success).length
  const soluble = all.filter((s) => !s.membrane), membrane = all.filter((s) => s.membrane)
  const of3 = m?.openfold3_msa, bm = m?.parp1_affinity_benchmark

  return (
    <div className="page">
      <PageHead eyebrow={t('Project-FlyGate · STEP 1 FlyDiscovery · 개요', 'Project-FlyGate · STEP 1 FlyDiscovery · Overview')}
        title={t(<>시판 전 후보 물질을 <span style={{ color: 'var(--nvidia)' }}>NVIDIA BioNeMo <Term k="NIM" /></span>으로 평가합니다</>,
          <>Evaluating pre-market drug candidates with <span style={{ color: 'var(--nvidia)' }}>NVIDIA BioNeMo <Term k="NIM" /></span></>)}
        lede={t(<>후보 물질이 <Term k="target">표적</Term>(약이 붙어 작용하는 단백질)에 어떻게 붙는지 다섯 단계(<Term k="MSA">MSA-Search</Term> 상동 서열 정렬 → <Term k="OpenFold3" /> 구조 예측 → <Term k="DiffDock" /> 도킹 → <Term k="Boltz2" /> 친화도 예측 → <Term k="critic">크리틱</Term>)로 계산하고, 단계마다 그 분야의 전통 기준으로 채점합니다. NIM은 NVIDIA가 AI 모델을 API로 바로 부를 수 있게 포장한 추론 마이크로서비스입니다.
          결과를 더 내기보다 <b style={{ color: 'var(--c-sense)' }}>결과가 말해도 되는 범위</b>를 정하는 것이 목표입니다. 데모 약물 니라파립은 <a href="#/mission">STEP 2 FlyVigilance</a>의 시판 후 보고로 이어집니다.
          왼쪽 메뉴에서 단계별 화면을 따로 볼 수 있습니다.</>,
          <>We compute how a candidate compound binds to its <Term k="target">target</Term> (the protein a drug acts on) in five steps (<Term k="MSA">MSA-Search</Term> multiple sequence alignment of homologs → <Term k="OpenFold3" /> structure prediction → <Term k="DiffDock" /> docking → <Term k="Boltz2" /> affinity prediction → <Term k="critic">critic</Term>), and score each step against that field’s established benchmark. NIM (NVIDIA Inference Microservice) packages AI models so they can be called directly as APIs.
          The goal is not to produce more results but to define <b style={{ color: 'var(--c-sense)' }}>how far the results can speak</b>. The demo drug, niraparib, carries through to post-market reports in <a href="#/mission">STEP 2 FlyVigilance</a>; any candidate can run through the same pipeline.
          Each step has its own page in the left menu.</>)}
        right={<div className="row wrap" style={{ justifyContent: 'flex-end', maxWidth: 380 }}>
          <span className="chip nv">NVIDIA BioNeMo NIM</span><span className="chip nv">MSA-Search · OpenFold3</span><span className="chip nv">DiffDock · Boltz-2</span>
          <span className="chip bad">{t('Nemotron 크리틱', 'Nemotron critic')}</span><span className="chip">RCSB PDB · ChEMBL</span><span className="chip">FDDD · MaleCNS</span>
        </div>} />

      {missing ? <MissingCard /> : !m ? <Loading /> : (
        <>
          <Card title={t(<>데모 약물 <span style={{ color: 'var(--jev)' }}>니라파립 × PARP1</span> · 다섯 단계 자동 재생</>, <>Demo drug <span style={{ color: 'var(--jev)' }}>niraparib × PARP1</span> · five-step autoplay</>)}
            sub={t('OpenFold3 NIM 이 예측한 복합체를 가운데 두고 단계마다 NIM 실측 결과를 겹쳐 봅니다. 단계를 누르면 그 단계 페이지로 갑니다', 'The complex predicted by the OpenFold3 NIM sits in the center, with each step’s measured NIM results layered on top. Click a step to open its page')}
            right={<span className="chip nv"><span className="dot on pulse" style={{ background: 'var(--nvidia)' }} />{t('BioNeMo NIM 실측', 'BioNeMo NIM measured')}</span>} style={{ marginBottom: 16 }}>
            {hero && extras ? <HeroDocking hero={hero} extras={extras} nav={STEP_PAGES} /> : <div className="shimmer" style={{ height: 620 }} />}
          </Card>

          <div className="grid g4" style={{ marginBottom: 16 }}>
            <Kpi label={<>OpenFold3 · <Term k="pLDDT" /></>} hint={t('구조 예측 신뢰도 · 0~100, 90 이상이면 매우 믿을 만합니다', 'Structure-prediction confidence (predicted local distance difference test) · 0–100; 90 or above is very reliable')} value={of3?.plddt ?? 0} color="var(--c-sense)" format={(n) => n.toFixed(2)}
              sub={of3 ? t(`4R6E 대비 Cα RMSD ${of3.ca_rmsd_vs_4R6E} Å · MSA 상동 서열 ${of3.msa_homologs}개`, `Cα RMSD (root-mean-square deviation) vs 4R6E ${of3.ca_rmsd_vs_4R6E} Å · ${of3.msa_homologs} MSA homologs`) : '…'} />
            <Kpi label={<><Term k="docking">Redock</Term> pass · <Term k="RMSD" /> ≤ 2 Å</>} hint={t('정답 결정 구조의 제자리를 2 Å 안으로 되찾은 약물 수', 'Number of drugs whose docked pose landed within 2 Å of the crystal-structure position')} value={pass} color="var(--nvidia)" format={(n) => `${Math.round(n)} / ${all.length || '–'}`}
              sub={t(`가용성 ${soluble.filter((s) => s.success).length}/${soluble.length} · 세포막 ${membrane.filter((s) => s.success).length}/${membrane.length}`, `Soluble ${soluble.filter((s) => s.success).length}/${soluble.length} · membrane ${membrane.filter((s) => s.success).length}/${membrane.length}`)} />
            <Kpi label={<>Boltz-2 vs <Term k="ChEMBL" /> · <Term k="spearman">Spearman</Term></>} hint={t('예측 친화도 순위와 실측 순위의 일치 정도 · 1이면 완전 일치', 'Agreement between predicted and measured affinity rankings · 1 means perfect agreement')} value={bm?.spearman ?? 0} color="var(--jev)" format={(n) => `ρ ${n.toFixed(3)}`}
              sub={bm ? t(`PARP1 ${bm.n}종 · MAE ${bm.mae} log · 상위 25% EF ${bm.ef_top25}`, `${bm.n} PARP1 inhibitors · MAE ${bm.mae} log · top-25% EF ${bm.ef_top25}`) : '…'} />
            <Kpi label={<><Term k="critic">Critic</Term> · <Term k="overclaim">{t('과잉해석', 'Overclaims')}</Term> {t('반려', 'rejected')}</>} hint={t('근거가 허락하는 범위를 넘는 주장을 걸러 낸 수', 'Claims rejected for going beyond what the evidence supports')} value={extras?.critic?.caught ?? 0} color="var(--bad)" format={(n) => `${Math.round(n)} / ${extras?.critic?.n_over ?? '–'}`}
              sub={extras?.critic ? t(`${extras.critic.model} · 정상 주장 ${extras.critic.passed}/${extras.critic.n_valid} 통과`, `${extras.critic.model} · valid claims passed ${extras.critic.passed}/${extras.critic.n_valid}`) : '…'} />
          </div>

          <DrugPanel panel={panel} />

          <div className="note" style={{ marginBottom: 16 }}>
            {t(<><b>측정 범위</b> · 재도킹은 결정 구조에 원래 리간드를 다시 넣어 도킹 설정이 작동하는지 보는 대조 실험이라, 새 후보의 결합을 예측했다는 뜻은 아닙니다.
            장면에서 리본을 그려 나가는 순서, 포즈가 날아오는 경로, 카메라는 연출이고, 도착한 좌표와 수치는 NIM 응답 · RCSB · ChEMBL 그대로입니다.
            {m.openfold2.status === 'FAILED' && <> 구조 예측은 OpenFold3로 실행했습니다(OpenFold2 엔드포인트는 측정 당시 HTTP {m.openfold2.http}을 반환).</>}</>,
            <><b>Scope of measurement</b> · Redocking puts a crystal structure’s original ligand back in to confirm the docking setup works; it is a control experiment, not a prediction of how a new candidate binds.
            In the scenes, the ribbon-drawing order, the pose flight paths and the camera are choreography; the final coordinates and numbers are exactly as returned by NIM · RCSB · ChEMBL.
            {m.openfold2.status === 'FAILED' && <> Structure prediction ran on OpenFold3 (the OpenFold2 endpoint returned HTTP {m.openfold2.http} at measurement time).</>}</>)}
          </div>

          <div className="row" style={{ gap: 10, marginBottom: 12 }}>
            <button className="btn" onClick={() => setShowBench((v) => !v)}>{showBench ? t('워크벤치 접기', 'Collapse workbench') : t('니라파립 워크벤치 전체 보기 ↓', 'Open the full niraparib workbench ↓')}</button>
            <a className="btn ghost" href={PAGE} target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>{t('새 창에서 열기 ↗', 'Open in new window ↗')}</a>
          </div>
          {showBench && <Card className="flush" style={{ overflow: 'hidden' }}><AutoFrame src={PAGE} /></Card>}
        </>
      )}
    </div>
  )
}
