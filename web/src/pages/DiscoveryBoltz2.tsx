// STEP 1-4 친화도: NVIDIA BioNeMo Boltz-2 NIM 으로 복합체와 예측 pIC50 을 받고 ChEMBL 실측과 대조합니다.
import { Suspense, lazy, useEffect, useMemo, useRef, useState } from 'react'
import * as d3 from 'd3'
import { Card, Loading } from '../components/ui'
import { KV, pathOf, Progress, RunButton, SkillBox, SourceChip, StepPage, pulseReward } from '../components/DiscoveryShell'
import { useBrain } from '../lib/brain'
import {
  fmtS, getCatalog, rewardFromPic50, runStep, saveRun, setStore, useDiscovery,
  type BoltzResult, type Catalog, type Envelope,
} from '../lib/discovery'

const Mol3D = lazy(() => import('../components/Mol3D'))

function Scatter({ points, live, onPick }: {
  points: { id: string; exp: number; pred: number; p: number }[]
  live: { pred: number; exp: number | null; label: string } | null
  onPick: (p: { id: string; exp: number; pred: number; p: number }) => void
}) {
  const box = useRef<HTMLDivElement>(null)
  const [w, setW] = useState(560)
  const [hover, setHover] = useState<string | null>(null)
  useEffect(() => {
    const el = box.current
    if (!el) return
    const ro = new ResizeObserver((e) => setW(Math.max(300, e[0].contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  const h = 320
  const m = { l: 46, r: 14, t: 12, b: 38 }
  const dom: [number, number] = [4, 12]
  const x = d3.scaleLinear().domain(dom).range([m.l, w - m.r])
  const y = d3.scaleLinear().domain(dom).range([h - m.b, m.t])
  return (
    <div ref={box}>
      <svg width={w} height={h}>
        <g className="axis">
          {x.ticks(5).map((t) => (
            <g key={`x${t}`}>
              <line x1={x(t)} x2={x(t)} y1={m.t} y2={h - m.b} stroke="rgba(120,170,255,0.12)" strokeDasharray="2 4" />
              <text x={x(t)} y={h - 18} textAnchor="middle">{t}</text>
            </g>
          ))}
          {y.ticks(5).map((t) => (
            <g key={`y${t}`}>
              <line x1={m.l} x2={w - m.r} y1={y(t)} y2={y(t)} stroke="rgba(120,170,255,0.12)" strokeDasharray="2 4" />
              <text x={m.l - 8} y={y(t) + 4} textAnchor="end">{t}</text>
            </g>
          ))}
          <text x={(w + m.l) / 2} y={h - 4} textAnchor="middle" fill="var(--text-3)" fontSize={10.5}>ChEMBL 실측 pChEMBL 중앙값</text>
          <text x={12} y={m.t + 8} fill="var(--text-3)" fontSize={10.5} transform={`rotate(-90 12 ${m.t + 8})`}>Boltz-2 예측 pIC50</text>
        </g>
        <line x1={x(dom[0])} y1={y(dom[0])} x2={x(dom[1])} y2={y(dom[1])} stroke="#6c7aa8" strokeDasharray="5 4" opacity={0.7} />
        {points.map((p) => (
          <circle key={p.id} cx={x(p.exp)} cy={y(p.pred)} r={hover === p.id ? 7 : 4.5}
            fill={hover === p.id ? '#ffcc4d' : '#37e6ff'} opacity={0.55 + 0.4 * p.p} style={{ cursor: 'pointer' }}
            onMouseEnter={() => setHover(p.id)} onMouseLeave={() => setHover(null)} onClick={() => onPick(p)}>
            <title>{`${p.id}\n실측 ${p.exp} · 예측 ${p.pred} · 결합 확률 ${p.p}`}</title>
          </circle>
        ))}
        {live && live.exp != null && (
          <g>
            <circle cx={x(live.exp)} cy={y(live.pred)} r={10} fill="none" stroke="#76b900" strokeWidth={2} className="breathe" />
            <circle cx={x(live.exp)} cy={y(live.pred)} r={5} fill="#76b900" />
            <text x={x(live.exp) + 14} y={y(live.pred) + 4} fill="#c8f36b" fontSize={11}>{live.label}</text>
          </g>
        )}
      </svg>
    </div>
  )
}

export default function DiscoveryBoltz2() {
  const { sim } = useBrain()
  const { target, ligand, runs, envs } = useDiscovery()
  const [cat, setCat] = useState<Catalog | null>(null)
  const [busy, setBusy] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [err, setErr] = useState<string | null>(null)
  const [fresh, setFresh] = useState(false)
  const env = (envs.boltz2 ?? null) as Envelope<BoltzResult> | null
  const res = (runs.boltz2 ?? env?.measured ?? null) as BoltzResult | null
  const isLive = Boolean(runs.boltz2)

  useEffect(() => { getCatalog().then(setCat).catch(() => setErr('목록을 불러오지 못했습니다')) }, [])
  useEffect(() => {
    if (!busy) return
    const t0 = Date.now()
    const id = setInterval(() => setElapsed((Date.now() - t0) / 1000), 100)
    return () => clearInterval(id)
  }, [busy])

  async function run() {
    setBusy(true); setErr(null); setElapsed(0)
    sim?.stimulate('layer', 'memory', 0.7, 8)
    const beat = setInterval(() => sim?.stimulate('layer', 'deliberate', 0.75, 6), 1000)
    try {
      const params: Record<string, unknown> = { target, ligand, no_cache: fresh }
      if (runs.msa?.a3m) params.a3m = runs.msa.a3m
      else if (runs.msa?.a3m_key) params.a3m_key = runs.msa.a3m_key
      const out = await runStep<BoltzResult>('boltz2', params, (e) => saveRun('boltz2', e as Envelope))
      saveRun('boltz2', out as Envelope)
      const a = out.result?.affinity
      if (a) {
        pulseReward(sim, 0.75 * rewardFromPic50(a.pic50) + 0.25 * (a.probability_binary ?? 0),
          `예측 pIC50 ${a.pic50} · 결합 확률 ${a.probability_binary}`, 'Boltz-2')
      }
      if (out.error) setErr(out.error)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally { clearInterval(beat); setBusy(false) }
  }

  const traces = useMemo(() => (res?.ca?.length ? [{ key: 'ca', points: res.ca, color: '#37e6ff', values: res.plddt_per_residue, opacity: 0.9 }] : []), [res])
  const mols = useMemo(() => (res?.ligand_atoms?.length ? [{ key: 'lig', atoms: res.ligand_atoms, bonds: res.ligand_bonds, color: '#ff4fd8', active: true }] : []), [res])
  const focus = useMemo(() => {
    const pts = res?.ligand_atoms ?? []
    if (!pts.length) return null
    return [0, 1, 2].map((i) => pts.reduce((s, p) => s + (p[i + 1] as number), 0) / pts.length)
  }, [res])
  const bench = cat?.benchmark
  const live = res?.affinity.pic50 != null
    ? { pred: res.affinity.pic50, exp: res.chembl?.median_pchembl ?? null, label: `${cat?.ligands[res.ligand]?.ko ?? res.ligand} (이번 실행)` }
    : null
  const pairs = useMemo(() => Object.entries(cat?.pairs ?? {}).filter(([, p]) => p.chembl_median != null || p.role !== '재도킹 패널(FAERS 데모 약물)'), [cat])

  return (
    <StepPage
      eyebrow="STEP 1 · 시판 전 탐색 · 4단계"
      title={<>친화도를 예측하고 <span style={{ color: 'var(--c-sense)' }}>실측값과 대조</span>합니다</>}
      lede={<>NVIDIA BioNeMo <b>Boltz-2</b> NIM 으로 복합체 구조와 예측 pIC50 을 함께 받습니다. 예측값은 ChEMBL 실측 pChEMBL 중앙값과 나란히 놓고 봅니다.
        예측 pIC50 은 예측이며 측정값이 아닙니다. 벤치마크는 PARP1 한 표적, 화합물 {bench?.n ?? 39}종 기준입니다.</>}
      right={<span className="chip nv">health.api.nvidia.com · Boltz-2</span>}
      current="boltz2"
      center={
        <>
          <Card title="예측 복합체" sub={res ? `잔기 ${res.n_residues}개 · ipTM ${res.scores.iptm ?? '–'} · pLDDT ${res.scores.plddt ?? '–'}` : '실행하면 라이브 복합체가 그려집니다'}
            right={<div className="row" style={{ gap: 6 }}><SourceChip env={env} />{!isLive && res && <span className="chip warn" style={{ fontSize: 10.5 }}>지난 측정</span>}</div>}>
            {res ? (
              <Suspense fallback={<Loading label="3D 준비 중" />}>
                <Mol3D traces={traces} mols={mols} focus={focus} radius={24} height={330} spin />
              </Suspense>
            ) : <div className="shimmer" style={{ height: 330 }} />}
            <div className="note" style={{ marginTop: 8 }}>CA 골격은 pLDDT 색, 분홍은 예측 리간드입니다. 구조 신뢰도(pLDDT)는 결합 세기를 말하지 않습니다.</div>
          </Card>
          <Card title={`친화도 벤치마크 · PARP1 ${bench?.n ?? 39}종`}
            sub={bench ? `Spearman ${bench.spearman} · Pearson ${bench.pearson} · MAE ${bench.mae} log · 상위 25% EF ${bench.ef_top25} (${bench.hit}/${bench.k})` : ''}
            right={<span className="chip" style={{ fontSize: 10.5 }}>점을 누르면 그 결합력으로 보상 회로가 뜁니다</span>}>
            {bench ? (
              <Scatter points={bench.points.map((p) => ({ id: p.id, exp: p.exp, pred: p.pred, p: p.p }))} live={live}
                onPick={(p) => pulseReward(sim, rewardFromPic50(p.pred), `${p.id} · 예측 pIC50 ${p.pred} (실측 ${p.exp})`, 'Boltz-2 벤치마크')} />
            ) : <div className="shimmer" style={{ height: 320 }} />}
            <div className="note" style={{ marginTop: 6 }}>
              점선은 예측 = 실측 선입니다. pIC50 ≥ 7 기준 민감도 {bench?.sens ?? '–'} / 특이도 {bench?.spec ?? '–'} 입니다.
              서로 다른 화합물의 예측값을 비교하는 것은 이 벤치마크 범위(PARP1, n={bench?.n ?? 39}) 안에서만 뜻이 있습니다.
            </div>
          </Card>
        </>
      }
      side={
        <>
          <Card title="라이브 실행" sub="NVIDIA BioNeMo NIM 호출">
            <div className="stack" style={{ gap: 8, marginBottom: 10 }}>
              <span className="mono dim" style={{ fontSize: 10.5, letterSpacing: 0.4, textTransform: 'uppercase' }}>표적 · 리간드</span>
              <select className="input" value={`${target}--${ligand}`} onChange={(e) => {
                const [tg, lg] = e.target.value.split('--')
                setStore({ target: tg, ligand: lg })
              }}>
                {pairs.map(([k, p]) => (
                  <option key={k} value={k}>{cat?.targets[p.target]?.label ?? p.target} · {cat?.ligands[p.ligand]?.ko ?? p.ligand}{p.chembl_median != null ? ` — ChEMBL ${p.chembl_median}` : ''}</option>
                ))}
              </select>
            </div>
            <RunButton busy={busy} onClick={run} label="Boltz-2 실행" fresh={fresh} setFresh={setFresh}
              sub={<>친화도 예측은 리간드 하나에만 겁니다(predict_affinity)</>} />
            <div className="divider" />
            <Progress env={env} busy={busy} elapsed={elapsed} />
            {err && <div className="note" style={{ color: 'var(--warn)', marginTop: 8 }}>{err}</div>}
            {env?.note && <div className="note" style={{ color: 'var(--warn)', marginTop: 8 }}>{env.note}</div>}
          </Card>
          <Card title="요청" sub={<span className="mono" style={{ fontSize: 10.5 }} title={env?.endpoint ?? undefined}>{pathOf(env?.endpoint) || '/v1/biology/mit/boltz2/predict'}</span>}>
            <KV rows={[
              ['sequence', `${env?.request?.sequence_len ?? cat?.targets[target]?.sequence_len ?? '–'} aa`],
              ['msa', String(env?.request?.msa ?? (runs.msa ? 'a3m' : 'none'))],
              ['predict_affinity', 'true (리간드 1개)'],
              ['recycling / sampling', `${env?.request?.recycling_steps ?? 3} / ${env?.request?.sampling_steps ?? 50}`],
              ['output', String(env?.request?.output_format ?? 'mmcif')],
            ]} />
          </Card>
          <Card title="측정값" sub="이번 실행">
            <KV rows={[
              ['예측 pIC50', res?.affinity.pic50 ?? '–'],
              ['결합 확률', res?.affinity.probability_binary ?? '–'],
              ['ipTM / pLDDT', res ? `${res.scores.iptm ?? '–'} / ${res.scores.plddt ?? '–'}` : '–'],
              ['ChEMBL 실측 중앙값', res?.chembl ? `${res.chembl.median_pchembl} (n=${res.chembl.n})` : '없음'],
              ['소요', busy ? `${elapsed.toFixed(1)}초` : env?.source === 'cache' ? '캐시(같은 입력)' : fmtS(env?.elapsed_s)],
            ]} />
            <div className="divider" />
            <div className="row between">
              <span className="chip warn" style={{ fontSize: 10.5 }}>지난 측정</span>
              <span className="num dim" style={{ fontSize: 11.5 }}>
                {(env?.measured as BoltzResult | null)?.affinity.pic50 != null ? `예측 pIC50 ${(env!.measured as BoltzResult).affinity.pic50}` : '–'}
              </span>
            </div>
          </Card>
          <Card title="따라간 NVIDIA 공식 스킬">
            <SkillBox skills={env?.skills ?? cat?.skills.boltz2 ?? []} />
          </Card>
        </>
      }
    />
  )
}
