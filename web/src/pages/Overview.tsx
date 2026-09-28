import { useEffect, useState, type ReactNode } from 'react'
import { Card, PageHead } from '../components/ui'
import { api, fmt, getJSON, type SignalRow } from '../lib/data'
import type { Ablation, Bench, CriticProbe, DiscoveryMeasurements, DockEval, Escalation, LiteratureEval, Validation } from '../lib/types'
import Term from '../components/Term'

// 개요: STEP 1 시판 전(후보 물질)과 STEP 2 시판 후(허가 약물)를 데모 약물 니라파립으로 이어 시판 전 탐색에서 STEP 2 시판 후 감시까지 한 화면에 보여 줍니다.
// 수치는 정적 데이터(/data, /discovery/data)나 API 에서 읽습니다. 파일이 없으면 '…' 로 남깁니다.

const REPO = 'https://github.com/Team-FlyGate/Project-FlyGate'
const REEL = '/showreel/FlyGate_showreel_v4.1.0.html'
const DIAGRAM = '/images/flygate_agent_diagram_v1.1.0.png'
const MSA_SECONDS = 63.6 // MSA-Search 실측 시간입니다 (fly_discovery/README.md, measurements.json 에는 없는 값)

type Kind = 'data' | 'nim' | 'jev' | 'rule' | 'critic' | 'human'
const KIND: Record<Kind, { c: string; t: string }> = {
  data: { c: '#37e6ff', t: '데이터 · 조회' },
  nim: { c: '#76b900', t: 'NVIDIA NIM' },
  jev: { c: '#ffb547', t: '비자기회귀 판단 모델' },
  rule: { c: '#8a97bd', t: '규칙 · SQL' },
  critic: { c: '#ff5d6c', t: '크리틱' },
  human: { c: '#f4f7ff', t: '사람' },
}
interface Step { name: string; tech: string; kind: Kind; val: ReactNode }

function Flow({ steps }: { steps: Step[] }) {
  return (
    <div className="flow">
      {steps.map((s, i) => (
        <div key={s.name} style={{ display: 'contents' }}>
          {i > 0 && <div className="flow-arrow" />}
          <div className="flow-step" style={{ boxShadow: `inset 3px 0 0 ${KIND[s.kind].c}` }}>
            <div className="fs-name">{s.name}</div>
            <div className="fs-tech" style={{ color: KIND[s.kind].c }}>{s.tech}</div>
            <div className="fs-val">{s.val}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

const SUP: Record<string, string> = { '-': '⁻', 0: '⁰', 1: '¹', 2: '²', 3: '³', 4: '⁴', 5: '⁵', 6: '⁶', 7: '⁷', 8: '⁸', 9: '⁹' }
function fmtP(p: number) {
  if (p >= 0.001) return `p = ${p.toPrecision(2)}`
  let e = Math.floor(Math.log10(p))
  let m = Math.round(p / 10 ** e)
  if (m === 10) { m = 1; e += 1 }
  return `p ≈ ${m}×10${String(e).split('').map((c) => SUP[c]).join('')}`
}

const tile = { padding: '12px 14px', borderRadius: 12, border: '1px solid var(--line)', background: 'rgba(8,13,26,0.55)' }

function Versus({ label, fv, raw, p, sub }: { label: string; fv: ReactNode; raw: ReactNode; p?: number; sub?: ReactNode }) {
  return (
    <div style={tile}>
      <div className="mono dim" style={{ fontSize: 10.5, letterSpacing: 0.6 }}>{label}</div>
      <div className="row" style={{ gap: 8, alignItems: 'baseline', marginTop: 4 }}>
        <span className="num" style={{ fontSize: 26, color: 'var(--c-sense)', fontWeight: 600 }}>{fv}</span>
        <span className="dim" style={{ fontSize: 12 }}>vs</span>
        <span className="num" style={{ fontSize: 18, color: 'var(--text-2)' }}>{raw}</span>
      </div>
      {p !== undefined && <span className="chip ok" style={{ fontSize: 10.5, padding: '1px 8px', margin: '4px 0 2px' }}><Term k="McNemar">McNemar</Term> {fmtP(p)}</span>}
      {sub && <div style={{ fontSize: 11.5, color: 'var(--text-2)', lineHeight: 1.45, marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

function Fact({ value, label, sub, color }: { value: ReactNode; label: ReactNode; sub: ReactNode; color: string }) {
  return (
    <div style={{ ...tile, boxShadow: `inset 3px 0 0 ${color}` }}>
      <div className="mono dim" style={{ fontSize: 10.5, letterSpacing: 0.6 }}>{label}</div>
      <div className="num" style={{ fontSize: 24, fontWeight: 600, marginTop: 2, color }}>{value}</div>
      <div style={{ fontSize: 11.5, color: 'var(--text-2)', lineHeight: 1.45 }}>{sub}</div>
    </div>
  )
}

// 결과 코드를 가린 트리아지에서 중대 사례가 사람 우선 검토나 System-2 검토에 도달한 수입니다 (자동 큐 = 종결 · 모니터링)
function reachedReview(serious: number | undefined, e: Escalation | undefined) {
  if (serious === undefined || !e) return undefined
  const rs = e.routes_serious
  return rs ? serious - (rs.close ?? 0) - (rs.monitor ?? 0) : serious - e.serious_without_review
}

export default function Overview() {
  const [bench, setBench] = useState<Bench | null>(null)
  const [val, setVal] = useState<Validation | null>(null)
  const [lit, setLit] = useState<LiteratureEval | null>(null)
  const [probe, setProbe] = useState<CriticProbe | null>(null)
  const [skills, setSkills] = useState<number | null>(null)
  const [disc, setDisc] = useState<DiscoveryMeasurements | null>(null)
  const [dock, setDock] = useState<Record<string, DockEval> | null>(null)
  const [nirTp, setNirTp] = useState<SignalRow | null>(null)
  useEffect(() => {
    getJSON<Bench>('/data/bench.json').then(setBench).catch(() => null)
    getJSON<Validation>('/data/validation.json').then(setVal).catch(() => null)
    getJSON<LiteratureEval>('/data/literature_eval.json').then(setLit).catch(() => null)
    getJSON<CriticProbe>('/data/critic_probe.json').then(setProbe).catch(() => null)
    getJSON<unknown[]>('/data/skills.json').then((s) => setSkills(s.length)).catch(() => null)
    getJSON<DiscoveryMeasurements>('/discovery/data/measurements.json').then(setDisc).catch(() => null)
    getJSON<Record<string, DockEval>>('/discovery/data/dd_eval_all.json').then(setDock).catch(() => null)
    api<{ rows: SignalRow[] }>('/api/signals/NIRAPARIB').then((r) => setNirTp(r.rows.find((x) => x.pt === 'thrombocytopenia') ?? null)).catch(() => null)
  }, [])

  // STEP 1 수치 (fly_discovery/measurements)
  const of3 = disc?.openfold3_msa
  const bm = disc?.parp1_affinity_benchmark
  const nirDock = dock?.['parp1-4r6e-chain-a--niraparib']
  const redock = dock ? Object.values(dock).filter((x) => x.rmsd_xtal !== null) : []
  const superKey = disc ? Object.keys(disc.critic_eval).find((k) => k.includes('super')) : undefined
  const critic1 = superKey ? disc!.critic_eval[superKey] : undefined
  const reject1 = critic1?.rows.find((r) => r[1] === 'REJECT' && r[0].includes('선택적')) ?? critic1?.rows.find((r) => r[1] === 'REJECT')

  // STEP 2 수치 (bench · validation · literature · critic probe)
  const blind = bench?.ablation_blind
  const ab: Ablation | undefined = blind ?? bench?.ablation
  const t = ab?.tests
  const serious = ab?.serious
  const fvReach = reachedReview(serious, ab?.flyvigilance)
  const rawReach = reachedReview(serious, ab?.raw_jev)
  const jt = bench?.jev_triage
  const nt = bench?.nemotron
  const KNOW = ['OMOP', 'EU-ADR', 'Harpaz']
  const know = val ? KNOW.filter((k) => val.refsets[k]).map((k) => {
    const r = val.refsets[k]
    const m = r.methods.find((x) => x.key === 'raw_named')
    const best = r.methods.filter((x) => x.family === 'metric').sort((a, b) => b.auc - a.auc)[0]
    return { k, m, best }
  }) : []
  const knowLabel = know.find((x) => x.m)?.m?.label ?? 'FlyVigilance · 지식 기반 판별 (이름 사용)'
  const pro = val?.refsets['Harpaz-prospective']
  const probes = probe ? Object.entries(probe.summary) : []
  const wrong = probes.filter(([k]) => k !== 'ctrl').reduce((a, [, s]) => ({ n: a.n + s.n, ok: a.ok + s.correct }), { n: 0, ok: 0 })
  const ctrl = probe?.summary.ctrl
  const p1 = probe?.cases[0]?.probes.find((p) => p.id === 'p1')
  const p1Issue = p1?.issues.find((i) => i.source === 'T3')

  const d = (x: number | undefined, digits = 2) => (x === undefined ? '…' : x.toFixed(digits))
  const step1: Step[] = [
    { name: '표적 · PARP1', tech: 'PDB 4R6E', kind: 'data', val: <>니라파립 <Term k="cocrystal">공결정 구조</Term> · <Term k="PDB">PDB</Term></> },
    { name: 'MSA-Search', tech: 'BioNeMo NIM', kind: 'nim', val: <><Term k="MSA">상동 서열</Term> {of3?.msa_homologs ?? '…'}개 · {MSA_SECONDS}초</> },
    { name: 'OpenFold3', tech: 'BioNeMo NIM', kind: 'nim', val: <><Term k="pLDDT" /> {of3?.plddt ?? '…'} · <Term k="CA">CA</Term> {d(of3?.ca_rmsd_vs_4R6E, 1)} Å</> },
    { name: 'DiffDock', tech: 'BioNeMo NIM', kind: 'nim', val: <><Term k="docking">재도킹</Term> <Term k="RMSD" /> {nirDock?.rmsd_xtal ?? '…'} <Term k="angstrom">Å</Term></> },
    { name: 'Boltz-2', tech: 'BioNeMo NIM', kind: 'nim', val: <><Term k="ChEMBL" /> 대비 <Term k="spearman">ρ</Term> {d(bm?.spearman, 3)} · {bm?.n ?? '…'}종</> },
    { name: '전통 기준 채점', tech: '규칙', kind: 'rule', val: <>포즈 ≤ 2 Å {redock.filter((x) => (x.rmsd_xtal ?? 9) <= 2).length}/{redock.length || '…'}</> },
    { name: '크리틱', tech: 'Nemotron 3 Super', kind: 'critic', val: <><Term k="overclaim">과잉해석</Term> {critic1 ? `${critic1.caught}/${critic1.n_over}` : '…'} 반려</> },
  ]
  const step2: Step[] = [
    { name: '접수 · FAERS', tech: 'DuckDB SQL', kind: 'data', val: nirTp ? <>니라파립 × 혈소판감소증 {fmt.int(nirTp.a)}건</> : 'FAERS 2012Q4–2026Q2' },
    { name: '규칙 게이트', tech: '규칙', kind: 'rule', val: <Term k="ICH4" /> },
    { name: '라벨 근거', tech: 'openFDA 조회', kind: 'data', val: <><Term k="label">라벨</Term> 절을 조회해 주입</> },
    { name: '타입 판단 7문항', tech: '비자기회귀 판단 모델', kind: 'jev', val: <>한 번 호출 · <Term k="pct">p50</Term> {jt ? Math.round(jt.latency_ms.p50) : '…'} ms</> },
    { name: '결정 정책', tech: '규칙', kind: 'rule', val: <><Term k="expedited">신속보고</Term> 기한 US · KR</> },
    { name: 'Nemotron 숙고', tech: 'Nemotron 3 Super', kind: 'nim', val: <><Term k="evidenceId">근거 ID</Term> 붙은 주장 메모</> },
    { name: '크리틱 3단', tech: '규칙 · 판단 · Safety Guard', kind: 'critic', val: <>틀린 주장 {probe ? `${wrong.ok}/${wrong.n}` : '…'} 반려</> },
    { name: '사람 검토 큐', tech: '사람', kind: 'human', val: <>보고 · <Term k="causality">인과성</Term> 최종 판정</> },
  ]

  return (
    <div className="page">
      <PageHead eyebrow="Project-FlyGate · NVIDIA Korea Agentic AI Hackathon 2026"
        title={<>시판 전 <span style={{ color: 'var(--c-sense)' }}>표적 결합</span>부터 <span style={{ color: 'var(--nvidia)' }}>시판 후 이상사례</span>까지, 약물 전 주기의 근거를 봅니다</>}
        lede={<><b>STEP 1 FlyDiscovery</b>는 시판 전 후보 물질이 <Term k="target">표적</Term>(약이 붙어 작용하는 단백질)에 붙는지를 BioNeMo <Term k="NIM" ko />로 예측해 전통 기준으로 채점하고,
          <b> STEP 2 FlyVigilance</b>는 시판 후 허가 약물의 <Term k="FAERS" ko /> 이상사례 보고를 분류하고 신호를 평가합니다. 데모에서는 이미 허가된 <Term k="niraparib">니라파립</Term>(PARP1 억제 항암제)으로 시판 전 단계를 되짚어 재현하고, 같은 약의 실제 시판 후 보고로 이어 봅니다. NVIDIA 스킬(build.nvidia.com NIM, <Term k="AgentSkills" />, <Term k="NemoClaw" /> · <Term k="OpenShell" /> · <Term k="OpenClaw" />) 위에 만든
          에이전트 워크플로이며, NVIDIA <Term k="Nemotron" />과 함께 <b style={{ color: 'var(--jev)' }}><Term k="NAR">비자기회귀 판단 모델</Term></b>(글을 생성하지 않고 확률을 한 번에 돌려주는 모델)을 써서 빠른 속도와 통계적으로 유의한 개선을 얻었습니다.</>}
        right={<div className="stack" style={{ gap: 8, alignItems: 'flex-end' }}>
          <a className="btn primary" href={REEL} target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>▶ 쇼릴 영상 v4.1</a>
          <div className="row" style={{ gap: 8 }}>
            <a className="btn ghost" href={REPO} target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>GitHub 저장소</a>
            <a className="btn ghost" href={`${REPO}/tree/main/docs`} target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>문서</a>
          </div>
        </div>} />

      <Card style={{ marginBottom: 16 }}>
        <div className="row between" style={{ marginBottom: 10 }}>
          <div className="row" style={{ gap: 10 }}>
            <span className="chip" style={{ color: 'var(--c-sense)', borderColor: 'rgba(55,230,255,0.45)' }}>STEP 1 · 시판 전</span>
            <b style={{ fontFamily: 'var(--font)', fontSize: 15 }}>FlyDiscovery</b>
            <span className="dim" style={{ fontSize: 12.5 }}>후보가 표적에 붙는지 구조 예측 → <Term k="docking">도킹</Term> → <Term k="affinity">친화도</Term> 순서로 잽니다</span>
          </div>
          <a href="#/discovery" style={{ fontSize: 12.5, textDecoration: 'none' }}>워크벤치 열기 →</a>
        </div>
        <Flow steps={step1} />
        <div className="row" style={{ gap: 12, margin: '14px 0' }}>
          <div style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, transparent, rgba(55,230,255,0.4))' }} />
          <span className="chip" style={{ fontSize: 12, color: 'var(--text)', borderColor: 'var(--line-2)' }}>데모 약물 니라파립 · 시판 후 보고로 이어집니다 ↓</span>
          <div style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, rgba(118,185,0,0.4), transparent)' }} />
        </div>
        <div className="row between" style={{ marginBottom: 10 }}>
          <div className="row" style={{ gap: 10 }}>
            <span className="chip nv">STEP 2 · 시판 후</span>
            <b style={{ fontFamily: 'var(--font)', fontSize: 15 }}>FlyVigilance</b>
            <span className="dim" style={{ fontSize: 12.5 }}>
              보고마다 <Term k="reflex">반사 판단</Term>으로 경로를 정하고, 필요한 건만 Nemotron 숙고(<Term k="System2" />)와 사람에게 올립니다
              {nirTp && <> · 니라파립 × 혈소판감소증 <Term k="PRR" /> {nirTp.prr.toFixed(2)}, <Term k="IC025" /> {nirTp.ic025.toFixed(2)}{nirTp.evans && nirTp.ror_sig && nirTp.ic_sig ? <> (<Term k="triple">3중 기준</Term> <Term k="SDR" ko />)</> : ''}</>}
            </span>
          </div>
          <a href="#/triage" style={{ fontSize: 12.5, textDecoration: 'none' }}>사례 분류(트리아지) 실행 →</a>
        </div>
        <Flow steps={step2} />
        <div className="row wrap" style={{ gap: 14, marginTop: 12 }}>
          {Object.values(KIND).map((k) => (
            <span key={k.t} className="row" style={{ gap: 6, fontSize: 11.5, color: 'var(--text-3)' }}><span className="legend-dot" style={{ background: k.c }} />{k.t}</span>
          ))}
        </div>
      </Card>

      <Card title="실측 결과" style={{ marginBottom: 16 }}
        sub={ab ? <>{blind ? <><Term k="blind">결과 코드를 가린</Term> <Term k="triage">트리아지</Term>(사례 분류)</> : '결과 코드를 보여 준 트리아지'} · FAERS {bench?.dataset.source.split(' ')[1] ?? ''} 실제 사례 {ab.n}건{serious !== undefined ? `, 중대 ${serious}건` : ''} ·
          FlyVigilance <span style={{ color: 'var(--c-sense)' }}>■</span> vs 모델 단독 · 질문 하나 <span style={{ color: 'var(--text-2)' }}>■</span></> : '불러오는 중'}
        right={bench?.ablation_generated ? <span className="chip">{bench.ablation_generated}</span> : undefined}>
        <div className="grid g4" style={{ gap: 12 }}>
          <Versus label="검토에 도달한 중대 사례" fv={fvReach !== undefined ? `${fvReach}/${serious}` : '…'} raw={rawReach !== undefined ? `${rawReach}/${serious}` : '…'}
            p={t?.serious_unreviewed_fv_vs_raw?.p}
            sub={fvReach !== undefined && rawReach !== undefined && serious !== undefined ? <><Term k="autoqueue">자동 큐</Term>(종결 · 모니터링)에 남은 중대 사례 {serious - fvReach}건 vs {serious - rawReach}건</> : undefined} />
          <Versus label="사람에게 바로 올린 비중대 사례" fv={ab?.flyvigilance.over_escalated ?? '…'} raw={ab?.raw_jev.over_escalated ?? '…'} p={t?.over_escalation_fv_vs_raw?.p}
            sub="검토자가 먼저 볼 필요가 없는 보고를 걸러 냅니다" />
          <Versus label="사람 우선 검토량" fv={ab?.flyvigilance.escalated ?? '…'} raw={ab?.raw_jev.escalated ?? '…'} p={t?.workload_fv_vs_raw?.p}
            sub={<>나머지 중대 사례는 <Term k="System2" />(숙고 단계) 검토로 갑니다</>} />
          <Fact color="#ffb547" label={<>반사 트리아지 · <Term k="q7">7문항</Term> 지연 <Term k="pct">p50</Term></>} value={jt ? `${fmt.int(Math.round(jt.latency_ms.p50))} ms` : '…'}
            sub={nt ? <>타입 판단 한 번 호출 · 같은 7문항을 <Term k="AR">자기회귀</Term>로 생성하면 {fmt.int(Math.round(nt.triage.latency_ms.p50))} ms (Nemotron 3.5 Lightning, n={nt.triage.n})</> : '…'} />
        </div>
        <div className="grid g4" style={{ gap: 12, marginTop: 12 }}>
          <div style={{ ...tile, boxShadow: 'inset 3px 0 0 #4d8dff' }}>
            <div className="mono dim" style={{ fontSize: 10.5, letterSpacing: 0.6 }}><Term k="refset">참조 세트</Term> <Term k="AUC" /> · {knowLabel}</div>
            <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>AUC 0.5 무작위 · 1 완벽</div>
            <div className="stack" style={{ gap: 3, marginTop: 6 }}>
              {know.length ? know.map(({ k, m, best }) => (
                <div key={k} className="row" style={{ gap: 8, fontSize: 12 }}>
                  <span style={{ width: 58, color: 'var(--text-2)' }}>{k}</span>
                  <span className="num" style={{ fontSize: 16, fontWeight: 600, color: '#4d8dff' }}>{m ? m.auc.toFixed(3) : '–'}</span>
                  <span className="dim num" style={{ fontSize: 11 }}>최고 통계 {best ? `${best.label} ${best.auc.toFixed(3)}` : '–'}</span>
                </div>
              )) : '…'}
            </div>
          </div>
          <Fact color="#ff4fd8" label={<><Term k="prospective">전향 검증</Term> · 2013년 이전 보고만 · 3중 기준 SDR</>} value={pro ? `${pro.points.triple.tp}/${pro.pos}` : '…'}
            sub={pro ? <>2013년 라벨 변경을 미리 표시 · 오경보 {pro.points.triple.fp}/{pro.neg} · <Term k="PPV" />(양성 예측도) {fmt.f(pro.points.triple.ppv ?? 0, 2)}</> : '…'} />
          <Fact color="#ffb547" label={<>문헌 설계 분류 · <Term k="PubMed">MEDLINE</Term> 색인과 일치</>} value={lit ? fmt.pct(lit.accuracy, 1) : '…'}
            sub={lit ? <>{fmt.int(lit.n)}편 · 호출당 초록 {lit.articles_per_call}편</> : '…'} />
          <Fact color="#ff5d6c" label={<><Term k="critic">크리틱</Term> 주입 시험 · 틀린 주장 반려</>} value={probe ? `${wrong.ok}/${wrong.n}` : '…'}
            sub={<>정상 대조 {ctrl ? `${ctrl.correct}/${ctrl.n}` : '…'} 통과 · 근거 ID · 숫자 대조 · 과잉해석 규칙 · <Term k="guard">Safety Guard</Term></>} />
        </div>
      </Card>

      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)', gap: 16, marginBottom: 16, alignItems: 'stretch' }}>
        <Card title="에이전트 구성도" sub={<>NemoClaw 네 층: <Term k="LLM" /> 엔드포인트 · OpenClaw 하네스 · OpenShell <Term k="sandbox">샌드박스</Term> · NemoClaw 블루프린트</>}
          right={<a href="#/agent" style={{ fontSize: 12.5, textDecoration: 'none' }}>에이전트 구성 →</a>}>
          <a href={DIAGRAM} target="_blank" rel="noreferrer" style={{ display: 'block' }}>
            <img src={DIAGRAM} alt="Project-FlyGate 에이전트 구성도: NVIDIA NIM 엔드포인트, egress 허용 목록, OpenShell 샌드박스 안의 OpenClaw 하네스와 두 워크플로, NemoClaw 블루프린트"
              loading="lazy" style={{ width: '100%', display: 'block', borderRadius: 10, background: '#fff' }} />
          </a>
        </Card>

        <Card title="기술 스택" sub="각 부품이 맡은 일">
          <div className="stack" style={{ gap: 10, fontSize: 12.5 }}>
            {([
              ['Agent Skills', `${skills ?? '…'}개 SKILL.md`, '능력마다 입력 · 출력 계약과 허용 호스트를 적었습니다', 'skills', 'nv'],
              ['Nemotron 3', 'Super · Ultra · 3.5 Lightning', '숙고 메모와 국내 보고 서식 구조화처럼 글을 쓰는 일', 'triage', 'nv'],
              ['Safety Guard', 'Nemotron Safety Guard', '메모의 주장마다 안전 검사', 'skills', 'nv'],
              ['BioNeMo NIM', 'MSA-Search · OpenFold3 · DiffDock · Boltz-2', 'STEP 1 구조 예측, 도킹, 친화도 예측', 'discovery', 'nv'],
              ['NemoClaw', 'OpenShell · OpenClaw', '샌드박스, 바이너리별 egress 허용 목록, 워크스페이스, 예약 실행', 'agent', 'nv'],
              ['판단 모델', '비자기회귀 · Jev (TypeSafe AI)', 'FlyVigilance 안의 타입 있는 확률 판단: 반사 트리아지, 크리틱의 과잉해석 판정, 문헌 설계 분류', 'triage', 'jev'],
            ] as const).map(([k, v, s, href, cls]) => (
              <a key={k} href={`#/${href}`} style={{ display: 'grid', gridTemplateColumns: '112px 1fr', gap: 10, textDecoration: 'none', color: 'inherit' }}>
                <span className={`chip ${cls}`} style={{ justifyContent: 'center', alignSelf: 'start' }}>{k}</span>
                <span><b style={{ fontWeight: 600 }}>{v}</b><br /><span className="dim" style={{ fontSize: 11.5 }}>{s}</span></span>
              </a>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid g2" style={{ alignItems: 'stretch' }}>
        <Card title="두 단계의 공통 원칙" sub="주장마다 근거 ID를 붙이고, 근거를 넘는 주장은 크리틱이 반려합니다">
          <div className="grid g2" style={{ gap: 10 }}>
            <div style={{ padding: '10px 12px', borderRadius: 11, border: '1px solid rgba(255,93,108,0.3)', background: 'rgba(255,93,108,0.05)' }}>
              <div className="row between"><span className="mono" style={{ fontSize: 10.5, color: 'var(--c-sense)' }}>STEP 1 · 도킹 해석</span><span className="chip bad" style={{ fontSize: 10 }}>반려</span></div>
              <div style={{ fontSize: 12.5, margin: '6px 0 4px' }}>“{reject1?.[0] ?? '…'}”</div>
              <div className="dim" style={{ fontSize: 11.5 }}>두 숫자는 모두 실측이지만 다른 단백질의 도킹 점수는 서로 비교할 수 없습니다</div>
            </div>
            <div style={{ padding: '10px 12px', borderRadius: 11, border: '1px solid rgba(255,93,108,0.3)', background: 'rgba(255,93,108,0.05)' }}>
              <div className="row between"><span className="mono" style={{ fontSize: 10.5, color: 'var(--nvidia)' }}>STEP 2 · 신호 해석</span><span className="chip bad" style={{ fontSize: 10 }}>반려{p1Issue ? ` · T3 ${p1Issue.rule}${p1Issue.p !== null ? ` p ${p1Issue.p.toFixed(2)}` : ''}` : ''}</span></div>
              <div className="mono" style={{ fontSize: 11.5, margin: '6px 0 4px', color: 'var(--text)' }}>“{p1?.text ?? '…'}”</div>
              <div className="dim" style={{ fontSize: 11.5 }}>불균형 지표는 보고 연관성이지 이 환자의 인과가 아닙니다 (규칙 R1)</div>
            </div>
            <div className="note"><b>STEP 1</b> 과잉해석 {critic1 ? `${critic1.caught}/${critic1.n_over}` : '…'} 반려 · 정상 주장 {critic1 ? `${critic1.passed}/${critic1.n_valid}` : '…'} 통과 (Nemotron 3 Super)</div>
            <div className="note"><b>STEP 2</b> 틀린 주장 {probe ? `${wrong.ok}/${wrong.n}` : '…'} 반려 · 정상 대조 {ctrl ? `${ctrl.correct}/${ctrl.n}` : '…'} 통과 (실제 사례 {probe?.n_cases ?? '…'}건)</div>
          </div>
        </Card>

        <Card title="전문가 검토로 강화한 부분" sub="면허 약사의 검토 의견을 반영해 규칙과 평가를 보강했습니다">
          <div className="stack" style={{ gap: 6, fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
            {([
              ['SDR 용어 · PV 분류', <>불균형 신호를 SDR로 부르고, 라벨 상태 × SDR로 검토 우선순위를 나눕니다(<Term k="pvclass">PV 분류</Term>)</>],
              ['EMA DME 안전망', <><Term k="EMA" />가 지정한 특별 주의 이상사례(<Term k="DME" />) 62개 <Term k="MedDRA">PT</Term>(이상반응 표준 용어)를 안전망으로 따로 표시합니다</>],
              ['보고자 편향 표시', <>예: 이소트레티노인 × 염증성 장질환 보고의 95%가 변호사 보고임을 표시합니다(<Term k="bias">보고 편향</Term>)</>],
              ['라벨 대조', <><Term k="contraindication">금기</Term>는 “라벨에 있음”으로 세지 않습니다</>],
              ['국내 15일 규칙', '15일 신속보고는 인과성이 배제되지 않을 때 적용합니다'],
              ['평가 설계', '결과 코드를 가린 조건으로 트리아지를 잽니다'],
            ] as [string, ReactNode][]).map(([k, v]) => (
              <div key={k} style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 10 }}>
                <b style={{ color: 'var(--text)', fontWeight: 600 }}>{k}</b><span>{v}</span>
              </div>
            ))}
          </div>
          <div className="row" style={{ gap: 8, marginTop: 12 }}>
            <a className="btn ghost" href={`${REPO}#readme`} target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>README</a>
          </div>
        </Card>
      </div>
    </div>
  )
}
