// STEP 1-2 구조 예측: NVIDIA BioNeMo OpenFold3 NIM 에 MSA 정렬을 넣어 복합체 구조를 예측합니다.
import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import { Card, Loading } from '../components/ui'
import { KV, pathOf, Progress, RunButton, SkillBox, SourceChip, StepPage, pulseReward, stimulateLayer } from '../components/DiscoveryShell'
import { useBrain } from '../lib/brain'
import {
  fmtS, getCatalog, plddtColor, rewardFromPlddt, rewardFromRmsd, runStep, saveRun, useDiscovery,
  type Catalog, type Envelope, type Of3Result,
} from '../lib/discovery'

const Mol3D = lazy(() => import('../components/Mol3D'))

function PlddtStrip({ values }: { values: number[] }) {
  const n = values.length
  return (
    <div>
      <div style={{ display: 'flex', height: 26, gap: 0, borderRadius: 6, overflow: 'hidden', background: 'rgba(10,16,30,0.6)' }}>
        {values.map((v, i) => (
          <i key={i} title={`잔기 ${i + 1} · pLDDT ${v}`} style={{ flex: '1 1 0', background: plddtColor(v), opacity: 0.35 + 0.65 * Math.min(1, v / 100) }} />
        ))}
      </div>
      <div className="row between mono dim" style={{ fontSize: 10, marginTop: 3 }}><span>잔기 1</span><span>잔기 {n}</span></div>
      <div className="row wrap" style={{ gap: 10, marginTop: 4 }}>
        {[['≥90 매우 높음', '#37e6ff'], ['70–90 높음', '#76b900'], ['50–70 보통', '#ffcc4d'], ['<50 낮음', '#ff5d6c']].map(([t, c]) => (
          <span key={t} className="row" style={{ gap: 5, fontSize: 10.5, color: 'var(--text-3)' }}><i className="legend-dot" style={{ background: c }} />{t}</span>
        ))}
      </div>
    </div>
  )
}

export default function DiscoveryOpenfold3() {
  const { sim } = useBrain()
  const { target, ligand, runs, envs } = useDiscovery()
  const [cat, setCat] = useState<Catalog | null>(null)
  const [busy, setBusy] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [overlay, setOverlay] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [fresh, setFresh] = useState(false)
  const env = (envs.openfold3 ?? null) as Envelope<Of3Result> | null
  const res = (runs.openfold3 ?? env?.measured ?? null) as Of3Result | null
  const isLive = Boolean(runs.openfold3)
  const msa = runs.msa

  useEffect(() => { getCatalog().then(setCat).catch(() => setErr('목록을 불러오지 못했습니다')) }, [])
  useEffect(() => {
    if (!busy) return
    const t0 = Date.now()
    const id = setInterval(() => setElapsed((Date.now() - t0) / 1000), 100)
    return () => clearInterval(id)
  }, [busy])

  async function run() {
    setBusy(true); setErr(null); setElapsed(0)
    stimulateLayer(sim, 'encode', 1.2, 14)
    const beat = setInterval(() => stimulateLayer(sim, 'encode', 0.85, 6), 1000)
    try {
      const params: Record<string, unknown> = { target, ligand, no_cache: fresh }
      if (msa?.a3m) params.a3m = msa.a3m
      else if (msa?.a3m_key) params.a3m_key = msa.a3m_key
      else params.a3m_measured = true
      const out = await runStep<Of3Result>('openfold3', params, (e) => saveRun('openfold3', e as Envelope))
      saveRun('openfold3', out as Envelope)
      if (out.result) {
        stimulateLayer(sim, 'memory', 0.8, 8)
        pulseReward(sim, 0.5 * rewardFromPlddt(out.result.scores.plddt) + 0.5 * rewardFromRmsd(out.result.ca_rmsd),
          `pLDDT ${out.result.scores.plddt} · CA RMSD ${out.result.ca_rmsd} Å`, 'OpenFold3')
      }
      if (out.error) setErr(out.error)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally { clearInterval(beat); setBusy(false) }
  }

  const traces = useMemo(() => {
    if (!res) return []
    const out = [{ key: 'pred', points: res.ca, color: '#37e6ff', values: res.plddt_per_residue, opacity: 0.95 }]
    if (overlay && res.xtal_ca?.length) out.push({ key: 'xtal', points: res.xtal_ca, color: '#6c7aa8', opacity: 0.5, values: undefined as never })
    return out
  }, [res, overlay])
  const mols = useMemo(() => {
    if (!res) return []
    const out = []
    if (res.ligand_atoms?.length) out.push({ key: 'pred-lig', atoms: res.ligand_atoms, bonds: res.ligand_bonds, color: '#76b900', active: true })
    if (overlay && res.xtal_ligand?.atoms?.length) out.push({ key: 'xtal-lig', atoms: res.xtal_ligand.atoms, bonds: res.xtal_ligand.bonds, color: '#ff4fd8', opacity: 0.55 })
    return out
  }, [res, overlay])
  const focus = useMemo(() => {
    const pts = res?.ligand_atoms?.length ? res.ligand_atoms.map((a) => [a[1], a[2], a[3]]) : res?.ca ?? []
    if (!pts.length) return null
    return [0, 1, 2].map((i) => pts.reduce((s, p) => s + p[i], 0) / pts.length)
  }, [res])

  const measured = cat?.measured.openfold3
  const of2 = cat?.measured.openfold2_failed
  return (
    <StepPage
      eyebrow="STEP 1 · 시판 전 탐색 · 2단계"
      title={<>정렬을 넣어 <span style={{ color: 'var(--c-sense)' }}>복합체 구조</span>를 예측합니다</>}
      lede={<>1단계에서 받은 A3M 정렬을 그대로 <b>OpenFold3</b> NIM 의 <span className="mono">msa.uniref30</span> 에 넣고, 단백질과 니라파립을 함께 예측합니다.
        예측 구조는 공개 결정 구조 4R6E 와 겹쳐 CA RMSD 로 채점합니다. 4R6E 는 공개 구조이므로 학습 데이터에 있었을 수 있고, 이 값은 맹검 예측 성능이 아닙니다.</>}
      right={<span className="chip nv">health.api.nvidia.com · OpenFold3</span>}
      current="openfold3"
      center={
        <Card title="예측 구조 · pLDDT 색" sub={res ? `잔기 ${res.n_residues}개 · 결정 구조 대비 CA RMSD ${res.ca_rmsd ?? '–'} Å (대응 CA ${res.n_ca}개)` : '실행하면 라이브 구조가 그려집니다'}
          right={<div className="row" style={{ gap: 6 }}>
            <SourceChip env={env} />
            {!isLive && res && <span className="chip warn" style={{ fontSize: 10.5 }}>지난 측정</span>}
            <button className="chip" style={{ cursor: 'pointer' }} onClick={() => setOverlay((v) => !v)}>{overlay ? '결정 구조 겹침 끄기' : '결정 구조 4R6E 겹치기'}</button>
          </div>}>
          {res ? (
            <Suspense fallback={<Loading label="3D 준비 중" />}>
              <Mol3D traces={traces} mols={mols} focus={focus} radius={34} height={420} spin />
            </Suspense>
          ) : <div className="shimmer" style={{ height: 420 }} />}
          <div className="row wrap" style={{ gap: 12, margin: '8px 0 12px' }}>
            <span className="row" style={{ gap: 5, fontSize: 11 }}><i className="legend-dot" style={{ background: '#37e6ff' }} />예측 CA 골격(pLDDT 색)</span>
            <span className="row" style={{ gap: 5, fontSize: 11 }}><i className="legend-dot" style={{ background: '#6c7aa8' }} />결정 구조 4R6E 체인 A</span>
            <span className="row" style={{ gap: 5, fontSize: 11 }}><i className="legend-dot" style={{ background: '#76b900' }} />예측 리간드</span>
            <span className="row" style={{ gap: 5, fontSize: 11 }}><i className="legend-dot" style={{ background: '#ff4fd8' }} />공결정 리간드</span>
          </div>
          {res && <PlddtStrip values={res.plddt_per_residue} />}
        </Card>
      }
      side={
        <>
          <Card title="라이브 실행" sub="NVIDIA BioNeMo NIM 호출">
            <RunButton busy={busy} onClick={run} label="OpenFold3 실행" fresh={fresh} setFresh={setFresh}
              sub={msa ? <>1단계 정렬 {msa.sequences}줄을 넣습니다</> : <>1단계를 먼저 돌리면 라이브 정렬을 넘깁니다(지금은 지난 측정 정렬 사용)</>} />
            <div className="divider" />
            <Progress env={env} busy={busy} elapsed={elapsed} />
            {err && <div className="note" style={{ color: 'var(--warn)', marginTop: 8 }}>{err}</div>}
            {env?.note && <div className="note" style={{ color: 'var(--warn)', marginTop: 8 }}>{env.note}</div>}
          </Card>
          <Card title="요청" sub={<span className="mono" style={{ fontSize: 10.5 }} title={env?.endpoint ?? undefined}>{pathOf(env?.endpoint) || '/v1/biology/openfold/openfold3/predict'}</span>}>
            <KV rows={[
              ['input_id', String(env?.request?.input_id ?? `${target}_${ligand}`)],
              ['output', String(env?.request?.output_format ?? 'pdb')],
              ['molecules', `단백질 + 리간드 (${ligand})`],
              ['msa', res?.msa_source === 'a3m' || msa ? 'a3m · uniref30' : '단일 서열'],
              ['diffusion_samples', '1'],
            ]} />
          </Card>
          <Card title="측정값" sub="이번 실행">
            <KV rows={[
              ['pLDDT', res?.scores.plddt ?? '–'],
              ['pTM / ipTM', res ? `${res.scores.ptm ?? '–'} / ${res.scores.iptm ?? '–'}` : '–'],
              ['CA RMSD (4R6E)', res?.ca_rmsd != null ? `${res.ca_rmsd} Å` : '–'],
              ['리간드 RMSD', res?.ligand_rmsd != null ? `${res.ligand_rmsd} Å` : '–'],
              ['소요', busy ? `${elapsed.toFixed(1)}초` : env?.source === 'cache' ? '캐시(같은 입력)' : fmtS(env?.elapsed_s)],
            ]} />
            <div className="divider" />
            <div className="row between">
              <span className="chip warn" style={{ fontSize: 10.5 }}>지난 측정</span>
              <span className="num dim" style={{ fontSize: 11.5 }}>{measured ? `pLDDT ${measured.plddt} · CA RMSD ${measured.ca_rmsd_vs_4R6E} Å` : '–'}</span>
            </div>
            {of2 && <div className="note" style={{ marginTop: 6 }}>구조 예측은 OpenFold3 로 실행합니다. OpenFold2 엔드포인트는 측정 당시 HTTP {of2.http}({of2.attempts}회 시도)을 냈습니다.</div>}
          </Card>
          <Card title="따라간 NVIDIA 공식 스킬">
            <SkillBox skills={env?.skills ?? cat?.skills.openfold3 ?? []} />
          </Card>
        </>
      }
    />
  )
}
