import { useEffect, useMemo, useRef, useState } from 'react'
import DockingView, { type RedockScene } from './DockingView'
import ConnectomePanel from './ConnectomePanel'
import Step2Handoff from './Step2Handoff'
import { Card } from './ui'
import { useBrain } from '../lib/brain'
import { api, getJSON } from '../lib/data'
import type { Ligand } from '../lib/molScene'

// STEP 1 직접 도킹: 표적(결정 구조 14개)과 약물(결정 리간드 + 약물 패널 소분자)을 고르면
// 재도킹으로 받아 둔 조합은 저장된 결과를, 새 조합은 서버(/api/dock)가 DiffDock NIM 을 실시간으로 불러 장면에 도킹합니다.

interface Library { targets: { key: string; gene: string; target: string; pdb: string; native: string }[]; ligands: { name: string; smiles: string; source: string; native_target: string | null }[] }
interface DockResult { poses: Ligand[]; confidence: (number | null)[]; seconds: number; cached?: boolean }
interface DockMatrix { results: Record<string, DockResult>; updated?: string }

const cap = (s: string) => s.split(' ').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')

export default function DockPlayground({ scenes }: { scenes: Record<string, RedockScene> }) {
  const [lib, setLib] = useState<Library | null>(null)
  const [matrix, setMatrix] = useState<DockMatrix | null>(null)
  const [target, setTarget] = useState('parp1-4r6e--niraparib')
  const [ligand, setLigand] = useState('talazoparib')
  const [scene, setScene] = useState<RedockScene | null>(null)
  const [status, setStatus] = useState<{ kind: 'idle' | 'saved' | 'live' | 'running' | 'error'; text: string }>({ kind: 'idle', text: '' })
  const [play, setPlay] = useState(0)
  const [settled, setSettled] = useState(false)
  const { sim } = useBrain()
  // 선택성 히트맵의 칸을 누르면 그 조합을 이 장면에서 바로 도킹합니다
  const [auto, setAuto] = useState(0)
  const cardRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const on = (e: Event) => { const d = (e as CustomEvent<{ target: string; ligand: string }>).detail; setTarget(d.target); setLigand(d.ligand); setAuto((n) => n + 1) }
    window.addEventListener('fd-dock', on)
    return () => window.removeEventListener('fd-dock', on)
  }, [])
  useEffect(() => {
    getJSON<Library>('/discovery/data/dock_library.json').then(setLib).catch(() => null)
    getJSON<DockMatrix>('/discovery/data/dock_matrix.json').then(setMatrix).catch(() => null)
  }, [])
  const t = lib?.targets.find((x) => x.key === target)
  const l = lib?.ligands.find((x) => x.name === ligand)
  const saved = !!t && !!l && t.native === l.name

  const base = scenes[target]
  const pocketDist = useMemo(() => {
    if (!scene) return null
    const a = scene.pose.atoms, c = [0, 1, 2].map((i) => a.reduce((s, x) => s + Number(x[i]), 0) / a.length)
    return Math.hypot(c[0], c[1], c[2])
  }, [scene])

  const run = async () => {
    if (!t || !l || !base) return
    setSettled(false)
    sim?.stimulate('layer', 'sense', 0.45, 8)
    if (saved) {
      setScene(base); setPlay((p) => p + 1); setStatus({ kind: 'saved', text: `저장된 재도킹 결과 · PDB ${t.pdb}` })
      return
    }
    const show = (r: DockResult) => {
      setScene({ ...base, drug: l.name, note: '', top1_rmsd: null, success: null, pose: r.poses[0], alt_poses: r.poses.slice(1),
        poses: r.confidence.map((c, i) => ({ rank: i + 1, confidence: c, rmsd: null })) })
      setPlay((p) => p + 1)
    }
    // 1) 미리 계산한 조합 (NVIDIA 키 없이 동작) → 2) 서버 실시간 호출 → 3) 실패하면 이 표적의 저장된 재도킹 결과
    const pre = matrix?.results[`${target}|${l.name}`]
    if (pre) { show(pre); setStatus({ kind: 'saved', text: `DiffDock NIM 미리 계산 결과 · ${pre.seconds}s` }); return }
    setStatus({ kind: 'running', text: 'DiffDock NIM 호출 중…' })
    try {
      const r = await api<DockResult>('/api/dock', { target, smiles: l.smiles })
      show(r)
      setStatus({ kind: 'live', text: r.cached ? `실시간 DiffDock NIM · 캐시 (${r.seconds}s)` : `실시간 DiffDock NIM · ${r.seconds}s` })
    } catch {
      setScene(base); setPlay((p) => p + 1)
      setStatus({ kind: 'saved', text: `실시간 도킹을 쓸 수 없어 ${cap(t.native)} 저장된 재도킹 결과를 보여 드립니다` })
    }
  }
  useEffect(() => { if (auto) { void run(); cardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }) } }, [auto]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (base && !scene) { setScene(base); setStatus({ kind: 'saved', text: `저장된 재도킹 결과 · PDB ${base.pdb}` }) } }, [base, scene])
  useEffect(() => { if (settled && sim) { sim.stimulate('layer', 'reflex', 0.6, 8); setTimeout(() => sim.stimulate('layer', 'memory', 0.5, 8), 250) } }, [settled, sim])

  return (
    <div ref={cardRef} style={{ scrollMarginTop: 16 }}>
    <Card title="직접 도킹해 보기" sub="표적과 약물을 고르면, 받아 둔 조합은 저장된 결과로, 새 조합은 DiffDock NIM 을 실시간으로 불러 도킹합니다"
      right={<span className="chip nv"><span className="dot on pulse" style={{ background: 'var(--nvidia)' }} />BioNeMo NIM · live</span>} style={{ marginBottom: 16 }}>
      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.5fr) minmax(300px, 1fr)', gap: 16 }}>
        <div style={{ position: 'relative' }}>
          {scene && <div style={{ position: 'absolute', left: 16, top: 14, zIndex: 2, pointerEvents: 'none' }}>
            <div style={{ fontFamily: 'var(--font)', fontSize: 20, fontWeight: 600 }}>{cap(scene.drug)} <span className="dim" style={{ fontWeight: 400 }}>→</span> {scene.gene}</div>
            <div className="mono dim" style={{ fontSize: 11 }}>{scene.target} · PDB {scene.pdb}</div>
          </div>}
          {scene ? <DockingView scene={scene} height={480} playKey={play} onSettled={() => setSettled(true)} /> : <div className="shimmer" style={{ height: 480 }} />}
        </div>
        <div className="stack" style={{ gap: 12 }}>
          <label className="stack" style={{ gap: 4 }}>
            <span className="mono dim" style={{ fontSize: 10.5 }}>표적 · 결정 구조</span>
            <select className="input" value={target} onChange={(e) => setTarget(e.target.value)}>
              {lib?.targets.map((x) => <option key={x.key} value={x.key}>{x.gene} · {x.pdb} — {x.target}</option>)}
            </select>
          </label>
          <label className="stack" style={{ gap: 4 }}>
            <span className="mono dim" style={{ fontSize: 10.5 }}>약물 · SMILES</span>
            <select className="input" value={ligand} onChange={(e) => setLigand(e.target.value)}>
              {lib?.ligands.map((x) => <option key={x.name} value={x.name}>{cap(x.name)} · {x.source}{t?.native === x.name ? ' · 저장됨' : ''}</option>)}
            </select>
          </label>
          <button className="btn nv" disabled={status.kind === 'running' || !lib} onClick={run}>
            {status.kind === 'running' ? '도킹 중…' : saved ? '저장된 결과 보기' : matrix?.results[`${target}|${ligand}`] ? '도킹 결과 보기 ▶' : 'DiffDock NIM 으로 도킹 ▶'}
          </button>
          <div className="row wrap" style={{ gap: 6 }}>
            {status.kind !== 'idle' && <span className={`chip ${status.kind === 'error' ? 'bad' : status.kind === 'live' ? 'nv' : status.kind === 'running' ? 'jev' : ''}`}>{status.text}</span>}
          </div>
          {scene && (
            <div className="stack" style={{ gap: 6 }}>
              <span className="mono dim" style={{ fontSize: 10.5 }}>포즈 신뢰도{scene.success !== null ? ' · 결정 구조 대비 RMSD' : ''}</span>
              {scene.poses.map((p) => (
                <div key={p.rank} style={{ display: 'grid', gridTemplateColumns: '48px 1fr 52px 60px', gap: 8, alignItems: 'center' }}>
                  <span className="mono dim" style={{ fontSize: 10.5 }}>pose {p.rank}</span>
                  <div className="pbar" style={{ height: 6 }}><i style={{ width: settled ? `${Math.max(0, Math.min(1, ((p.confidence ?? -3) + 3) / 4.5)) * 100}%` : '0%', background: p.rank === 1 ? 'var(--jev)' : 'var(--c-encode)', transition: 'width .6s' }} /></div>
                  <span className="num" style={{ fontSize: 11, textAlign: 'right' }}>{p.confidence === null ? '–' : p.confidence.toFixed(2)}</span>
                  <span className="num" style={{ fontSize: 11, textAlign: 'right', color: p.rmsd === null ? 'var(--text-3)' : p.rmsd <= 2 ? 'var(--ok)' : 'var(--bad)' }}>{p.rmsd === null ? '' : `${p.rmsd.toFixed(2)} Å`}</span>
                </div>
              ))}
              {pocketDist !== null && settled && <div className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>1순위 포즈 중심 ↔ 결정 리간드 자리 {pocketDist.toFixed(2)} Å</div>}
            </div>
          )}
          {scene && settled && <Step2Handoff drug={scene.drug} />}
          <ConnectomePanel height={170} focus={settled ? '반사 · 기억 · 포즈 판단' : '감각 입력 · 포즈 탐색'} />
        </div>
      </div>
    </Card>
    </div>
  )
}
