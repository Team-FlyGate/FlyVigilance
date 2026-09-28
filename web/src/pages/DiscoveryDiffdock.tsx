// STEP 1-3 결합 포즈: NVIDIA BioNeMo DiffDock NIM 으로 포즈를 계산하고 공결정 포즈와 RMSD 로 채점합니다.
import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import { Card, Loading } from '../components/ui'
import { KV, pathOf, Progress, RunButton, SkillBox, SourceChip, StepPage, pulseReward } from '../components/DiscoveryShell'
import { useBrain } from '../lib/brain'
import {
  fmtS, getCatalog, getScene, rewardFromConfidence, rewardFromRmsd, runStep, saveRun, setStore, useDiscovery,
  type Catalog, type DockResult, type Envelope, type Scene,
} from '../lib/discovery'

const Mol3D = lazy(() => import('../components/Mol3D'))

export default function DiscoveryDiffdock() {
  const { sim } = useBrain()
  const { target, ligand, runs, envs } = useDiscovery()
  const [cat, setCat] = useState<Catalog | null>(null)
  const [scene, setScene] = useState<Scene | null>(null)
  const [busy, setBusy] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [active, setActive] = useState(0)
  const [cycle, setCycle] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [fresh, setFresh] = useState(false)
  const env = (envs.diffdock ?? null) as Envelope<DockResult> | null
  const res = (runs.diffdock ?? env?.measured ?? null) as DockResult | null
  const isLive = Boolean(runs.diffdock)

  useEffect(() => { getCatalog().then(setCat).catch(() => setErr('목록을 불러오지 못했습니다')) }, [])
  useEffect(() => { setScene(null); getScene(target).then(setScene).catch(() => null) }, [target])
  useEffect(() => {
    if (!busy) return
    const t0 = Date.now()
    const id = setInterval(() => setElapsed((Date.now() - t0) / 1000), 100)
    return () => clearInterval(id)
  }, [busy])
  useEffect(() => {
    if (!cycle || !res?.poses.length) return
    const id = setInterval(() => setActive((i) => (i + 1) % res.poses.length), 3200)
    return () => clearInterval(id)
  }, [cycle, res])

  function firePose(i: number) {
    const p = res?.poses[i]
    if (!p) return
    setActive(i)
    const strength = p.rmsd != null ? 0.55 * rewardFromConfidence(p.confidence) + 0.45 * rewardFromRmsd(p.rmsd)
      : rewardFromConfidence(p.confidence)
    pulseReward(sim, strength, `${res?.ligand} 포즈 ${p.rank} · 신뢰도 ${p.confidence}${p.rmsd != null ? ` · RMSD ${p.rmsd} Å` : ''}`, 'DiffDock')
  }

  async function run() {
    setBusy(true); setErr(null); setElapsed(0); setActive(0)
    sim?.stimulate('channel', 'trials', 1.1, 12)
    const beat = setInterval(() => sim?.stimulate('layer', 'reflex', 0.8, 6), 900)
    try {
      const out = await runStep<DockResult>('diffdock', { target, ligand, no_cache: fresh }, (e) => saveRun('diffdock', e as Envelope))
      saveRun('diffdock', out as Envelope)
      const p = out.result?.poses?.[0]
      if (p) {
        pulseReward(sim, p.rmsd != null ? 0.55 * rewardFromConfidence(p.confidence) + 0.45 * rewardFromRmsd(p.rmsd) : rewardFromConfidence(p.confidence),
          `1순위 신뢰도 ${p.confidence}${p.rmsd != null ? ` · RMSD ${p.rmsd} Å` : ''}`, 'DiffDock')
      }
      if (out.error) setErr(out.error)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally { clearInterval(beat); setBusy(false) }
  }

  const mols = useMemo(() => {
    const out: { key: string; atoms: [string, number, number, number][]; bonds: number[][]; color: string; active?: boolean; opacity?: number }[] = []
    if (scene?.xtal_ligand?.atoms?.length) out.push({ key: 'xtal', atoms: scene.xtal_ligand.atoms, bonds: scene.xtal_ligand.bonds, color: '#ff4fd8', opacity: 0.5 })
    res?.poses.forEach((p, i) => out.push({ key: `p${p.rank}`, atoms: p.atoms, bonds: p.bonds,
      color: i === active ? '#76b900' : '#4d8dff', active: i === active, opacity: i === active ? 1 : 0.18 }))
    return out
  }, [res, active, scene])
  const traces = useMemo(() => (scene?.ca?.length ? [{ key: 'ca', points: scene.ca, color: '#37e6ff', opacity: 0.32 }] : []), [scene])
  const pairs = useMemo(() => Object.entries(cat?.pairs ?? {}), [cat])

  const measured = env?.measured as DockResult | null
  const t = cat?.targets[target]
  return (
    <StepPage
      eyebrow="STEP 1 · 시판 전 탐색 · 3단계"
      title={<>결합 포즈를 계산하고 <span style={{ color: 'var(--c-sense)' }}>결정 포즈와 대조</span>합니다</>}
      lede={<>NVIDIA BioNeMo <b>DiffDock</b> NIM 에 수용체 ATOM 좌표와 리간드 SMILES 를 넣어 포즈를 받습니다.
        공결정 리간드를 다시 넣은 재도킹은 <b>도킹 설정이 작동하는지</b> 확인하는 대조 실험이며 전향적 예측이 아닙니다.
        채점 기준은 대칭을 고려한 중원자 RMSD ≤ 2.0 Å(정렬 없음)입니다.</>}
      right={<span className="chip nv">health.api.nvidia.com · DiffDock</span>}
      current="diffdock"
      center={
        <Card title="결합 주머니와 포즈" sub={res ? `${res.n_poses}개 포즈 · ${res.redock ? '공결정 재도킹(대조)' : '탐색적 교차 도킹'} · ${res.criterion}` : '실행하면 라이브 포즈가 들어옵니다'}
          right={<div className="row" style={{ gap: 6 }}>
            <SourceChip env={env} />
            {!isLive && res && <span className="chip warn" style={{ fontSize: 10.5 }}>지난 측정</span>}
            <button className="chip" style={{ cursor: 'pointer' }} onClick={() => setCycle((v) => !v)}>{cycle ? '순환 멈춤' : '순위대로 순환'}</button>
          </div>}>
          {scene ? (
            <Suspense fallback={<Loading label="3D 준비 중" />}>
              <Mol3D traces={traces} mols={mols} cloud={scene.pocket} focus={scene.pocket_center} radius={20} height={430}
                dockIn={res ? `${res.ligand}-${active}` : null} spin />
            </Suspense>
          ) : <div className="shimmer" style={{ height: 430 }} />}
          <div className="row wrap" style={{ gap: 6, marginTop: 10 }}>
            {res?.poses.map((p, i) => (
              <button key={p.rank} className="chip" onClick={() => firePose(i)} style={{
                cursor: 'pointer', fontSize: 11,
                color: i === active ? '#c8f36b' : 'var(--text-2)',
                borderColor: i === active ? 'rgba(118,185,0,0.6)' : 'var(--line-2)',
                background: i === active ? 'rgba(118,185,0,0.12)' : undefined,
              }}>
                {p.rank}순위 · 신뢰도 {p.confidence}{p.rmsd != null ? ` · RMSD ${p.rmsd} Å` : ''}
              </button>
            ))}
          </div>
          <div className="note" style={{ marginTop: 8 }}>
            분홍은 결정 구조의 공결정 리간드, 초록은 선택한 포즈입니다. 포즈를 누르면 그 결합력만큼 보상 회로를 자극합니다.
            DiffDock 신뢰도는 포즈 순위 점수이며 결합 세기가 아닙니다.
          </div>
        </Card>
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
                  <option key={k} value={k}>{cat?.targets[p.target]?.label ?? p.target} · {cat?.ligands[p.ligand]?.ko ?? p.ligand} — {p.role}</option>
                ))}
              </select>
            </div>
            <RunButton busy={busy} onClick={run} label="DiffDock 실행" fresh={fresh} setFresh={setFresh}
              sub={<>{t?.pdb} {t?.chain ? `체인 ${t.chain}` : ''} · 포즈 5개 · steps 18</>} />
            <div className="divider" />
            <Progress env={env} busy={busy} elapsed={elapsed} />
            {err && <div className="note" style={{ color: 'var(--warn)', marginTop: 8 }}>{err}</div>}
            {env?.note && <div className="note" style={{ color: 'var(--warn)', marginTop: 8 }}>{env.note}</div>}
          </Card>
          <Card title="요청" sub={<span className="mono" style={{ fontSize: 10.5 }} title={env?.endpoint ?? undefined}>{pathOf(env?.endpoint) || '/v1/biology/mit/diffdock'}</span>}>
            <KV rows={[
              ['protein', `${env?.request?.protein_atoms ?? '–'} ATOM 줄`],
              ['ligand_file_type', String(env?.request?.ligand_file_type ?? 'txt')],
              ['num_poses', String(env?.request?.num_poses ?? 5)],
              ['steps / divisions', `${env?.request?.steps ?? 18} / ${env?.request?.time_divisions ?? 20}`],
              ['SMILES', <span key="s" className="mono" style={{ fontSize: 9.5 }}>{String(env?.request?.ligand ?? cat?.ligands[ligand]?.smiles ?? '').slice(0, 44)}…</span>],
            ]} />
          </Card>
          <Card title="측정값" sub="이번 실행">
            <KV rows={[
              ['1순위 신뢰도', res?.top1_confidence ?? '–'],
              ['1순위 RMSD', res?.top1_rmsd != null ? `${res.top1_rmsd} Å` : res?.redock ? '–' : '해당 없음(교차 도킹)'],
              ['최소 RMSD', res?.best_rmsd != null ? `${res.best_rmsd} Å` : '–'],
              ['2 Å 기준', res ? (res.top1_success ? '통과' : res.redock ? '미달' : '–') : '–'],
              ['소요', busy ? `${elapsed.toFixed(1)}초` : env?.source === 'cache' ? '캐시(같은 입력)' : fmtS(env?.elapsed_s)],
            ]} />
            <div className="divider" />
            <div className="row between">
              <span className="chip warn" style={{ fontSize: 10.5 }}>지난 측정</span>
              <span className="num dim" style={{ fontSize: 11.5 }}>
                {measured ? `신뢰도 ${measured.top1_confidence} · RMSD ${measured.top1_rmsd ?? '–'}` : '–'}
              </span>
            </div>
            <div className="note" style={{ marginTop: 6 }}>재도킹 패널(덱사메타손·리스페리돈·룩솔리티닙·레날리도마이드·니르마트렐비르)도 같은 방식으로 다시 돌릴 수 있습니다.</div>
          </Card>
          <Card title="따라간 NVIDIA 공식 스킬">
            <SkillBox skills={env?.skills ?? cat?.skills.diffdock ?? []} />
          </Card>
        </>
      }
    />
  )
}
