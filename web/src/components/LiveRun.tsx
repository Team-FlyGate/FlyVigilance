import { useEffect, useState, type ReactNode } from 'react'
import { Card } from './ui'
import { useBrain } from '../lib/brain'
import {
  SOURCE_LABEL, fmtS, getCatalog, getMeasured, runCritic, runParams, runStep, saveRun, useDiscovery,
  type BoltzResult, type Catalog, type Claim, type CriticResult, type DockResult, type Envelope, type MsaResult, type Of3Result, type StepKind,
} from '../lib/discovery'
import type { StepId } from './HeroDocking'
import TargetPicker from './TargetPicker'

// STEP 1 단계 페이지의 "라이브 실행" 카드. 3D 장면과 아래 분석은 그대로 두고, 그 단계의 NIM 을 지금 다시 불러
// 이번 실행과 지난 측정을 나란히 보여 줍니다. 서버는 /api/discovery/* (NVIDIA 키는 서버에만 있고 호출 횟수 제한이 걸려 있습니다).
// 실패하거나 키가 없으면 지난 측정을 그대로 두고 이유를 한 줄로 알려 줍니다.

const KIND: Record<StepId, StepKind | 'critic'> = { msa: 'msa', of3: 'openfold3', dd: 'diffdock', bz: 'boltz2', critic: 'critic' }
const HOST: Record<StepKind | 'critic', string> = {
  msa: 'health.api.nvidia.com · MSA-Search', openfold3: 'health.api.nvidia.com · OpenFold3', diffdock: 'health.api.nvidia.com · DiffDock',
  boltz2: 'health.api.nvidia.com · Boltz-2', critic: 'integrate.api.nvidia.com · Nemotron 3 Super',
}

type Row = [string, (r: never) => ReactNode]
const n = (v: number | null | undefined, d = 2) => (v === null || v === undefined ? '–' : v.toFixed(d))
const ROWS: Record<StepKind, Row[]> = {
  msa: [['상동 서열', (r: MsaResult) => `${r.homologs}개`], ['평균 깊이', (r: MsaResult) => n(r.mean_depth, 1)], ['열 커버리지', (r: MsaResult) => n(r.coverage, 2)], ['소요', (r: MsaResult) => fmtS(r.seconds)]],
  openfold3: [['pLDDT', (r: Of3Result) => n(r.scores.plddt ?? r.mean_plddt, 2)], ['pTM · ipTM', (r: Of3Result) => `${n(r.scores.ptm, 3)} · ${n(r.scores.iptm, 3)}`],
    ['Cα RMSD (4R6E)', (r: Of3Result) => (r.ca_rmsd === null ? '–' : `${n(r.ca_rmsd)} Å`)], ['리간드 RMSD', (r: Of3Result) => (r.ligand_rmsd === null ? '–' : `${n(r.ligand_rmsd)} Å`)], ['소요', (r: Of3Result) => fmtS(r.seconds)]],
  diffdock: [['1순위 신뢰도', (r: DockResult) => n(r.top1_confidence, 3)], ['1순위 RMSD', (r: DockResult) => (r.redock ? (r.top1_rmsd === null ? '–' : `${n(r.top1_rmsd)} Å`) : '해당 없음(교차 도킹)')],
    ['최소 RMSD', (r: DockResult) => (r.best_rmsd === null ? '–' : `${n(r.best_rmsd)} Å`)], ['2 Å 기준', (r: DockResult) => (r.redock ? (r.top1_success ? '통과' : '미달') : '–')], ['소요', (r: DockResult) => fmtS(r.seconds)]],
  boltz2: [['예측 pIC50', (r: BoltzResult) => n(r.affinity.pic50)], ['결합 확률', (r: BoltzResult) => n(r.affinity.probability_binary, 3)],
    ['ipTM · pLDDT', (r: BoltzResult) => `${n(r.scores.iptm, 3)} · ${n(r.scores.plddt, 3)}`], ['ChEMBL 실측 중앙값', (r: BoltzResult) => (r.chembl ? `${r.chembl.median_pchembl} (n=${r.chembl.n})` : '없음')], ['소요', (r: BoltzResult) => fmtS(r.seconds)]],
}

export default function LiveRun({ step, drug }: { step: StepId; drug: string }) {
  const kind = KIND[step]
  const { sim } = useBrain()
  const { runs, envs, customTarget, customLigand, target: pickT, ligand: pickL } = useDiscovery()
  // 화면에서 단백질이나 약물을 찾아 골랐으면(검색) 그 값으로 부르고, 지난 측정 비교는 두지 않습니다
  const custom = !!(customTarget || customLigand)
  const [cat, setCat] = useState<Catalog | null>(null)
  // 마지막 응답을 받은 시각(같은 값이 와도 새로 받았다는 것을 보여 줍니다)
  const [lastAt, setLastAt] = useState<Date | null>(null)
  const [fresh, setFresh] = useState(false)
  const [busy, setBusy] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [err, setErr] = useState<string | null>(null)
  const [critic, setCritic] = useState<CriticResult | null>(null)
  const [extra, setExtra] = useState('')
  const [showReq, setShowReq] = useState(false)

  useEffect(() => { getCatalog().then(setCat).catch(() => setErr('라이브 서버에 닿지 못했습니다 · 지난 측정만 보여 줍니다')) }, [])
  useEffect(() => {
    if (!busy) return
    const t0 = Date.now(), id = setInterval(() => setElapsed((Date.now() - t0) / 1000), 200)
    return () => clearInterval(id)
  }, [busy])

  const env = kind === 'critic' ? undefined : envs[kind]
  // 위 표적 · 리간드 선택기(TargetPicker)에서 고른 값을 그대로 씁니다. 전에는 MSA · OpenFold3 가 PARP1 로 고정돼
  // 선택기에서 Factor Xa 를 골라도 PARP1 을 다시 불러 '바뀌는 게 없어' 보였습니다
  const target = pickT || 'parp1'
  const lig = kind === 'msa' ? undefined : pickL || (cat?.ligands[drug] ? drug : 'niraparib')
  const [past, setPast] = useState<unknown>(null)
  useEffect(() => {
    if (kind === 'critic' || !cat) return
    let live = true
    setPast(null)
    if (custom) return
    getMeasured(kind, target, lig).then((r) => { if (live) setPast(r.measured) }).catch(() => {})
    return () => { live = false }
  }, [kind, cat, target, lig, custom])
  // 이번 실행 결과는 지금 고른 쌍과 같을 때만 보여 줍니다(다른 쌍을 고르면 비웁니다)
  const sameParams = env && (custom ? !!(env.params?.custom_target || env.params?.custom_ligand) : (env.params?.target ?? 'parp1') === target && (kind === 'msa' || env.params?.ligand === lig))
  // 소요 시간은 결과 안에 없으면 봉투의 elapsed_s(서버가 잰 왕복 시간)로 채웁니다
  const liveRes = sameParams && env?.result ? { ...env.result, seconds: (env.result as { seconds?: number | null }).seconds ?? env.elapsed_s } : undefined
  const pastRes = (sameParams ? env?.measured : null) ?? past
  // 이번 실행과 지난 측정이 모든 지표에서 같은지(소요 시간 제외)
  const same = kind !== 'critic' && liveRes && pastRes ? ROWS[kind].filter(([k]) => k !== '소요').every(([, f]) => String(f(liveRes as never)) === String(f(pastRes as never))) : false
  const tLabel = customTarget ? customTarget.label : cat?.targets[target]?.label ?? target
  const lLabel = customLigand ? customLigand.name : lig ? cat?.ligands[lig]?.ko ?? lig : null

  async function run() {
    setBusy(true); setErr(null); setElapsed(0)
    sim?.stimulate('layer', kind === 'critic' ? 'critic' : 'sense', 1.1, 12)
    try {
      if (kind === 'critic') {
        const claims: Claim[] | undefined = extra.trim() ? [{ id: 'cx', text: extra.trim(), evidence: [], kind: 'overclaim' }] : undefined
        const r = await runCritic({ ...(claims ? { claims } : {}), runs: runs as Record<string, unknown> })
        setCritic(r)
        sim?.stimulate('layer', 'critic', r.issues.length ? 1.4 : 0.6, 16)
        return
      }
      const params: Record<string, unknown> = custom ? runParams() : kind === 'msa' ? { target } : { target, ligand: lig }
      params.no_cache = fresh
      // 앞 단계 MSA 를 이번 세션에서 돌렸으면 그 정렬을 넘기고, 아니면 지난 측정 정렬을 씁니다(OpenFold3 · Boltz-2)
      if (kind === 'openfold3' || kind === 'boltz2') {
        // 이번 세션 MSA 는 같은 표적일 때만 넘기고, 지난 측정 정렬은 PARP1 것이라 PARP1 일 때만 씁니다(다른 표적에 PARP1 정렬을 붙이지 않게)
        // 표적을 바꾸면 저장소가 앞 단계 결과를 비우므로(selectTarget), 남아 있는 MSA 는 지금 표적(직접 찾은 단백질 포함)의 것입니다
        const msaSame = Boolean(runs.msa) && (custom || (envs.msa?.params?.target ?? 'parp1') === target)
        if (msaSame && runs.msa?.a3m) params.a3m = runs.msa.a3m
        else if (msaSame && runs.msa?.a3m_key) params.a3m_key = runs.msa.a3m_key
        else if (kind === 'openfold3' && !custom && target === 'parp1') params.a3m_measured = true
      }
      const out = await runStep(kind, params, (e) => saveRun(kind, e as Envelope))
      saveRun(kind, out as Envelope)
      if (out.state === 'done') setLastAt(new Date())
      if (out.state === 'pending') setErr('NIM 계산이 5분 안에 끝나지 않았습니다 · 잠시 뒤 다시 누르면 이어서 받습니다')
      if (out.error) setErr(out.error)
      sim?.stimulate('layer', 'action', 0.9, 10)
    } catch (e) {
      const m = e instanceof Error ? e.message : String(e)
      setErr(m.includes('429') || m.includes('rate limit') ? '호출 횟수 제한에 걸렸습니다 · 1분 뒤 다시 눌러 주세요'
        : m.includes('not configured') || m.includes('503') ? '서버에 NVIDIA 키가 없습니다 · 지난 측정을 보여 줍니다' : m)
    } finally { setBusy(false) }
  }

  const src = env?.source ? SOURCE_LABEL[env.source] : null
  const status = busy ? <span className="chip warn">계산 중 · {elapsed.toFixed(0)}초{env?.state === 'pending' ? ' · NIM 대기열' : ''}</span>
    : err ? <span className="chip bad">실패 · 지난 측정 표시 중</span>
    : critic && (critic.judge.error || !critic.judge.model) ? <span className="chip warn">3단 미판정</span>
    : (sameParams && env?.state === 'done') || critic ? <span className={`chip ${src?.cls ?? 'ok'}`}>{src?.text ?? '완료'}</span>
    : <span className="chip">대기</span>

  return (
    <Card title="라이브 실행" sub={<span className="mono" style={{ fontSize: 11 }}>{HOST[kind]}</span>} right={status} style={{ marginBottom: 16 }}>
      {kind !== 'critic' && <div style={{ marginBottom: 12 }}><TargetPicker cat={cat} /></div>}
      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.4fr)', gap: 18, alignItems: 'start' }}>
        <div className="stack" style={{ gap: 10 }}>
          {kind !== 'critic' && (
            <div style={{ fontSize: 12.5 }}>이번에 부를 입력: <b>{tLabel}</b>{kind !== 'msa' && lLabel ? <> + <b>{lLabel}</b></> : null}
              <span className="mono dim" style={{ fontSize: 11 }}> · 위 선택기에서 바꿉니다</span></div>
          )}
          {(kind === 'openfold3' || kind === 'boltz2') && (
            <div className="mono dim" style={{ fontSize: 11 }}>MSA 입력: {runs.msa && (custom || (envs.msa?.params?.target ?? 'parp1') === target) ? '이번 세션의 MSA-Search 결과'
              : !custom && target === 'parp1' ? '지난 측정 정렬(MSA 단계를 먼저 돌리면 그 결과를 넘깁니다)' : '없음(단일 서열) · 이 표적으로 MSA 단계를 먼저 돌리면 그 정렬을 넘깁니다'}</div>
          )}
          {kind === 'critic' && (
            <label className="stack" style={{ gap: 4 }}>
              <span className="mono dim" style={{ fontSize: 10.5, letterSpacing: 1.2 }}>과잉해석 직접 넣어 보기 (비우면 앞 단계 결과로 주장을 만듭니다)</span>
              <input id="live-critic-claim" value={extra} onChange={(e) => setExtra(e.target.value)} disabled={busy}
                placeholder="예: 니라파립은 Vina PARP1 -10.178, Factor Xa -7.967 이므로 PARP1 에 선택적이다"
                style={{ background: 'var(--bg-2, #0b1222)', color: 'var(--text)', border: '1px solid var(--line)', borderRadius: 8, padding: '8px 10px', fontSize: 12.5 }} />
            </label>
          )}
          <div className="row wrap" style={{ gap: 10, alignItems: 'center' }}>
            <button className="btn nv" onClick={run} disabled={busy || !cat}>{busy ? '실행 중…' : kind === 'critic' ? '크리틱 3단 실행' : '지금 NIM 부르기'}</button>
            {kind !== 'critic' && <label className="row mono dim" style={{ gap: 6, fontSize: 11, alignItems: 'center' }}>
              <input id={`live-fresh-${kind}`} type="checkbox" checked={fresh} onChange={(e) => setFresh(e.target.checked)} disabled={busy} /> 캐시 무시
            </label>}
          </div>
          {err && <div style={{ fontSize: 12.5, color: 'var(--bad)' }}>{err}</div>}
          {env?.skills?.length ? <div className="mono dim" style={{ fontSize: 10.5 }}>따라간 스킬: {env.skills.map((s) => s.name).join(' · ')}</div> : null}
        </div>

        <div className="stack" style={{ gap: 8 }}>
          {kind === 'critic' ? <CriticOut r={critic} /> : (
            <>
              <div key={lastAt?.getTime() ?? 0} className="grid mono fade-in" style={{ gridTemplateColumns: 'minmax(0, 1.2fr) 1fr 1fr', gap: '6px 12px', fontSize: 12.5 }}>
                <span className="dim" style={{ fontSize: 10.5 }}>지표</span><span className="dim" style={{ fontSize: 10.5 }}>이번 실행</span><span className="dim" style={{ fontSize: 10.5 }}>지난 측정</span>
                {ROWS[kind].map(([k, f]) => (
                  <Frag key={k} k={k} live={liveRes ? f(liveRes as never) : '–'} past={pastRes ? f(pastRes as never) : '–'} />
                ))}
              </div>
              {liveRes && lastAt && (
                <div className="fade-in" style={{ fontSize: 12, lineHeight: 1.55 }}>
                  <span className={`chip ${src?.cls ?? 'ok'}`} style={{ fontSize: 10, marginRight: 6 }}>{src?.text ?? '응답'}</span>
                  {lastAt.toLocaleTimeString('ko-KR', { hour12: false })}에 받은 응답{env?.req_id ? <span className="mono dim"> · 요청 {env.req_id.slice(0, 8)}</span> : null}
                  {env?.source === 'cache' && <div className="dim">같은 입력의 이전 라이브 결과를 캐시에서 꺼냈습니다. '캐시 무시'를 켜면 NIM 을 새로 부릅니다</div>}
                  {kind === 'openfold3' && liveRes && (() => {
                    const r = liveRes as unknown as Of3Result, rows = Number((env?.request as { molecules?: { msa_rows?: number }[] } | undefined)?.molecules?.[0]?.msa_rows ?? 0)
                    const pl = r.scores.plddt ?? r.mean_plddt, ip = r.scores.iptm
                    return <>
                      {pl !== null && pl < 70 && rows <= 1 && <div style={{ color: 'var(--warn)' }}>MSA 없이 단일 서열로 예측해 신뢰도가 낮습니다(pLDDT {pl.toFixed(1)}). MSA 단계에서 이 표적을 먼저 돌리면 그 정렬을 넣어 다시 예측합니다</div>}
                      {ip !== null && ip < 0.3 && <div style={{ color: 'var(--warn)' }}>ipTM {ip.toFixed(2)} · 단백질-리간드 접촉면 신뢰도가 낮습니다. 이 리간드가 이 단백질에 붙는다는 근거로 쓰면 안 됩니다</div>}
                    </>
                  })()}
                  {same && env?.source !== 'cache' && <div className="dim">지난 측정과 값이 같습니다. 같은 서열 · 같은 데이터베이스 · 같은 설정이면 NIM 결과가 같게 나옵니다(재현성). 다른 표적을 골라 보면 값이 바뀝니다</div>}
                </div>
              )}
              {env?.request && (
                <div>
                  <button className="chip" style={{ cursor: 'pointer', fontSize: 10.5 }} onClick={() => setShowReq((v) => !v)}>{showReq ? '요청 숨기기' : '보낸 요청 보기'}</button>
                  {showReq && <pre className="mono" style={{ fontSize: 10.5, maxHeight: 180, overflow: 'auto', marginTop: 6, padding: 10, borderRadius: 8, background: 'rgba(5,9,18,0.6)', border: '1px solid var(--line)' }}>
                    {env.endpoint}{'\n'}{JSON.stringify(env.request, null, 2)}</pre>}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </Card>
  )
}

function Frag({ k, live, past }: { k: string; live: ReactNode; past: ReactNode }) {
  return <><span>{k}</span><b style={{ color: live === '–' ? 'var(--text-3)' : 'var(--text)' }}>{live}</b><span className="dim">{past}</span></>
}

function CriticOut({ r }: { r: CriticResult | null }) {
  // Nemotron(3단)이 돌지 않았으면(키 없음 · 오류) 규칙 1 · 2단만 본 것이므로 '통과'라고 쓰지 않습니다
  const noJudge = Boolean(r && (r.judge.error || !r.judge.model))
  if (!r) return <div className="dim" style={{ fontSize: 12.5 }}>실행하면 1단 근거 ID → 2단 숫자 대조 → 3단 Nemotron 과잉해석 판정 순서로 돌고, 주장마다 통과 · 반려가 여기에 나옵니다.</div>
  return (
    <div className="stack" style={{ gap: 6 }}>
      {noJudge && <div style={{ fontSize: 12.5, color: 'var(--warn)' }}>3단 Nemotron 판정이 돌지 않았습니다{r.judge.error ? ` (${r.judge.error})` : ''} · 1 · 2단 규칙 검사 결과만 보입니다</div>}
      <div className="mono" style={{ fontSize: 12 }}>과잉해석 {r.score.caught}/{r.score.n_over} 반려 · 정상 {r.score.passed}/{r.score.n_valid} 통과 · {r.judge.model ?? '–'} · {(r.total_ms / 1000).toFixed(1)}초</div>
      {r.claims.map((c) => {
        const issue = r.issues.find((i) => i.claim === c.id)
        const bad = c.verdict === 'REJECT' || Boolean(issue)
        return (
          <div key={c.id} style={{ padding: '8px 10px', borderRadius: 10, fontSize: 12.5, border: `1px solid ${bad ? 'rgba(255,93,108,0.45)' : 'rgba(61,220,151,0.35)'}` }}>
            <span className={`chip ${bad ? 'bad' : noJudge ? 'warn' : 'ok'}`} style={{ fontSize: 10, marginRight: 8 }}>{bad ? `반려${issue ? ` · ${issue.tier}단 ${issue.rule}` : ''}` : noJudge ? '규칙 통과 · 3단 미판정' : '통과'}</span>{c.text}
            {issue && <div className="dim" style={{ fontSize: 11.5, marginTop: 4 }}>{issue.detail_ko ?? issue.detail}</div>}
          </div>
        )
      })}
    </div>
  )
}
