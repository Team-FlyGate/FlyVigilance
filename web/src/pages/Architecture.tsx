import { useEffect, useState } from 'react'
import BrainView from '../components/BrainView'
import { Card, PageHead } from '../components/ui'
import { useBrain } from '../lib/brain'
import { LAYER_COLOR, fmt, getJSON } from '../lib/data'
import type { Bench, CriticProbe, LiteratureEval, Validation } from '../lib/types'

const SUP: Record<string, string> = { '-': '⁻', '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹' }
// 아주 작은 p 값은 과학 표기로 보여 드립니다 (예: 3.6×10⁻⁴⁸)
function fmtP(p: number): string {
  if (!(p > 0)) return '0'
  if (p >= 0.01) return p.toFixed(2)
  if (p >= 0.001) return p.toFixed(4)
  const e = Math.floor(Math.log10(p))
  return `${(p / 10 ** e).toFixed(1)}×10${String(e).split('').map((c) => SUP[c] ?? c).join('')}`
}
const REFSETS = ['OMOP', 'EU-ADR', 'Harpaz']

interface Node { key: string; x: number; y: number; title: string; short: string; brain: string; agent: string; tech: { t: string; k?: 'nv' | 'jev' | '' }[]; detail: string[] }

const NODES: Node[] = [
  { key: 'sense', short: '데이터 수용', x: 40, y: 190, title: 'Sensory Intake', brain: 'ORN · GRN · JO · VPN', agent: '데이터 스트림 수용 스킬',
    tech: [{ t: 'FAERS ASCII' }, { t: 'openFDA' }, { t: 'PubMed' }],
    detail: ['FAERS 분기 zip 증분 적재 (etl_quarter 감사 테이블)', '채널 = 감각 모달리티: 후각 FAERS, 미각 문헌, 기계감각 임상시험, 온습도 라벨 변경, 시각 디지털', 'deny-by-default 허용 호스트만 호출'] },
  { key: 'encode', short: '정규화 · 중복제거', x: 225, y: 190, title: 'Feature Encoding', brain: 'Antennal lobe PN', agent: '정규화 · 중복제거 · 임베딩',
    tech: [{ t: 'DuckDB' }, { t: 'nemotron-3-embed (planned)', k: 'nv' }],
    detail: ['caseid 최신 버전 + FDA 삭제 목록 반영', '유효성분 우선, 염/수화물 접미사 제거, 상품명→성분 학습 매핑', 'ICH 최소 4요소 규칙 게이트 (모델 미사용)'] },
  { key: 'reflex', short: '반사 판단', x: 410, y: 60, title: 'Reflex Judgment', brain: 'Lateral horn', agent: 'FlyVigilance 반사 판단 · 비자기회귀 판단 모델(Jev)',
    tech: [{ t: '비자기회귀 판단 · Jev (TypeSafe AI)', k: 'jev' }, { t: '결정 정책 (규칙)' }],
    detail: ['상태 1개 + 타입 질문 7개를 한 번에: noul · choice · score', '라벨 근거 주입: 예측성은 모델 기억이 아니라 openFDA 라벨 조회로 정합니다', '중대성, 예측성, WHO-UMC 인과성, 특수상황, 우선순위, 다음 행동, 숙고 필요', '규정 모드(US/KR)별 신속보고 기한은 결정 정책이 붙입니다', 'EMA DME 62개 PT가 보고되면 점수와 관계없이 사람 검토로 보냅니다 (안전망)'] },
  { key: 'memory', short: '신호 기억', x: 410, y: 320, title: 'Signal Memory', brain: 'Mushroom body KC · MBON · DAN', agent: '불균형 분석 · 라벨 · 문헌 기억',
    tech: [{ t: 'PRR · ROR · IC025' }, { t: 'DailyMed' }],
    detail: ['PRR·ROR 95% CI, Yates χ², BCPNN IC₀₂₅ (SQL 계산, 모델 미개입)', 'PV 분류(라벨 상태 × SDR)와 근거 등급 A/B/C/L/D/U: 라벨 절 + 3중 기준 SDR (규칙)', '문헌 읽기: PubMed 출판 유형(규칙) + 초록 설계·결론 판정(비자기회귀 판단 모델)', 'SDR 기준의 참조 세트 성능을 근거 ID로 인용 (metric:)'] },
  { key: 'deliberate', short: 'Nemotron 숙고', x: 610, y: 190, title: 'Deliberation', brain: 'Central complex EPG · PFL · FB', agent: 'NVIDIA Nemotron System-2 평가',
    tech: [{ t: 'Nemotron 3 Super', k: 'nv' }, { t: 'Ultra · Lightning', k: 'nv' }],
    detail: ['승격된 케이스만: 중대+예상외, 우선순위 ≥ 2.5, 저신뢰, 신호 검토', '근거 묶음만 보고 근거 ID가 붙은 주장 JSON 작성', '503이면 Super → Ultra → Lightning 폴백'] },
  { key: 'critic', short: '3단 크리틱', x: 800, y: 190, title: 'Inhibitory Critic', brain: 'GABAergic · APL', agent: '3단 크리틱',
    tech: [{ t: 'rules' }, { t: 'numeric oracle' }, { t: '비자기회귀 판정 (Jev)', k: 'jev' }, { t: 'Nemotron Safety Guard', k: 'nv' }],
    detail: ['T1 근거 ID 실재 · T2 문장 속 숫자를 근거 수치와 대조', 'T3 과잉해석 규칙 13종 위반 확률 (비자기회귀 판단 모델 · 주장별 noul + 규칙 choice)', 'NVIDIA Nemotron Safety Guard 로 개별 치료 조언 차단 · 반려 시 1회 재작성'] },
  { key: 'action', short: '행동 · 사람 큐', x: 985, y: 190, title: 'Action Output', brain: 'Descending neurons', agent: '행동: 신속보고 · 검토 · 모니터 · 종결',
    tech: [{ t: 'human queue' }, { t: 'E2B(R3) draft' }],
    detail: ['신속보고 후보는 15일 시계와 함께 사람 큐', '통과한 메모만 사람에게, 모든 판단은 감사 로그', '환자 개별 치료 조언은 가드레일로 차단'] },
  { key: 'feedback', short: '검토 되먹임', x: 800, y: 400, title: 'Reviewer Feedback', brain: 'Ascending neurons · DAN', agent: '사람 검토 되먹임',
    tech: [{ t: 'threshold tuning' }],
    detail: ['검토자 결정 = 도파민 신호: 라우팅 임계값과 우선순위 보정', '판단 모델 확률의 보정 곡선을 실측 라벨로 추적 (ECE)', '규칙 추가는 사람 승인 후에만'] },
]

const EDGES: [string, string][] = [
  ['sense', 'encode'], ['encode', 'reflex'], ['encode', 'memory'], ['reflex', 'deliberate'], ['memory', 'deliberate'],
  ['reflex', 'action'], ['deliberate', 'critic'], ['critic', 'action'], ['critic', 'deliberate'], ['action', 'feedback'], ['feedback', 'memory'], ['feedback', 'reflex'],
]
const W = 172, H = 104

export default function Architecture() {
  const [sel, setSel] = useState('reflex')
  const [bench, setBench] = useState<Bench | null>(null)
  const [val, setVal] = useState<Validation | null>(null)
  const [lit, setLit] = useState<LiteratureEval | null>(null)
  const [probe, setProbe] = useState<CriticProbe | null>(null)
  const { conn, sim } = useBrain()
  useEffect(() => {
    getJSON<Bench>('/data/bench.json').then(setBench).catch(() => null)
    getJSON<Validation>('/data/validation.json').then(setVal).catch(() => null)
    getJSON<LiteratureEval>('/data/literature_eval.json').then(setLit).catch(() => null)
    getJSON<CriticProbe>('/data/critic_probe.json').then(setProbe).catch(() => null)
  }, [])
  const node = NODES.find((n) => n.key === sel)!
  const layer = conn?.meta.layers.find((l) => l.key === sel)

  // 실측 수치는 JSON 에서 읽습니다. 비교 실험은 모든 조건의 입력에서 결과 코드를 가린 측정(ablation_blind)을 먼저 씁니다
  const ab = bench?.ablation_blind ?? bench?.ablation
  const cond = bench?.ablation_blind ? '결과 코드 가림' : '결과 코드 공개'
  const fv = ab?.flyvigilance, base = ab?.raw_jev, g = ab?.grounding
  const serious = ab ? ab.serious ?? Math.round(ab.n * (bench?.dataset.serious_rate ?? 0)) : 0
  const diff = g ? g.memory_vs_label.memory_expected_label_not + g.memory_vs_label.memory_unexpected_label_listed : 0
  const pOf = (k: string) => { const t = ab?.tests?.[k]; return t ? ` (p = ${fmtP(t.p)})` : '' }
  const followUp = fv?.routes?.follow_up ?? ab?.routes.flyvigilance?.follow_up
  // 참조 세트: 지식 기반 판별(약·반응 이름 사용)의 AUC 와 가장 좋은 불균형 통계의 AUC
  const modes = val ? REFSETS.map((r) => {
    const ms = val.refsets[r]?.methods ?? []
    return { r, named: ms.find((m) => m.key === 'raw_named')?.auc, stat: Math.max(...ms.filter((m) => m.family === 'metric').map((m) => m.auc)) }
  }) : []
  const modesOk = modes.length > 0 && modes.every((m) => m.named !== undefined && Number.isFinite(m.stat))
  // 전향 검증: 2013년 라벨 변경 전 보고만으로 3중 기준 SDR 을 계산한 결과입니다
  const pro = val?.refsets['Harpaz-prospective']?.points.triple
  const planted = probe ? Object.entries(probe.summary).filter(([k]) => k !== 'ctrl') : []
  const ctrl = probe?.summary.ctrl
  const LAYERS: [string, string, string, string][] = [
    ['1', '규칙이 먼저', 'ICH 최소 4요소, 중대성 결과 코드, 역할 코드처럼 규칙으로 되는 일은 모델에 묻지 않습니다',
      ab && followUp !== undefined ? `${ab.n}건 중 최소 요소가 빠진 ${followUp}건은 규칙으로 추가정보 요청에 보냈습니다` : '…'],
    ['2', '기억 대신 조회', '라벨 기재 여부를 모델 기억이 아니라 openFDA 라벨 절 검색으로 정해 상태에 넣습니다',
      g ? `라벨을 찾은 ${g.label_found}건 중 ${diff}건(${fmt.pct(diff / Math.max(1, g.label_found), 0)})에서 모델 기억과 라벨이 달라 라벨 조회값을 썼습니다` : '…'],
    ['3', '규제 용어로 쪼갠 질문', '질문 하나 대신 ICH E2A·WHO-UMC·한국형 알고리즘 항목을 타입 있는 7~9문항으로 한 번에 묻습니다',
      fv && base ? `FlyVigilance vs 모델 단독 · 질문 하나 (${cond}): 사람 우선 ${fv.escalated} vs ${base.escalated}건${pOf('workload_fv_vs_raw')}, 사람에게 바로 간 비중대 ${fv.over_escalated} vs ${base.over_escalated}건${pOf('over_escalation_fv_vs_raw')}` : '…'],
    ['4', '결정 정책과 규정 모드', '확률을 행동으로 바꾸는 규칙표입니다. 미국·한국 신속보고 기준과 기한, 저신뢰 상향, DME 안전망을 담습니다',
      fv && base ? `자동 큐(종결·모니터링)에 남은 중대 사례 ${fv.serious_without_review}건 vs 모델 단독 ${base.serious_without_review}건 / ${serious}건${pOf('serious_unreviewed_fv_vs_raw')} · ${cond}` : '…'],
    ['5', '통계는 SQL', '불균형 순위와 SDR 판정은 PRR·ROR·IC₀₂₅ SQL이 정하고, 모델은 숫자를 바꾸지 않습니다',
      pro ? `전향 검증(Harpaz): 2013년 이전 보고만으로 3중 기준 SDR이 2013년 라벨 변경 ${pro.tp}/${pro.tp + pro.fn}건을 먼저 잡았고, 오경보는 ${pro.fp}/${pro.fp + pro.tn}건입니다 (PPV ${fmt.f(pro.ppv ?? 0)})` : '…'],
    ['6', '두 판별 모드', '약·반응 이름을 쓰는 지식 기반 판별과, 이름을 가리고 보고 통계만 보는 통계 기반 판별을 따로 측정합니다',
      modesOk ? `지식 기반 판별 AUC ${modes.map((m) => `${m.r} ${fmt.f(m.named ?? 0, 3)}`).join(' · ')} (가장 좋은 통계 ${modes.map((m) => fmt.f(m.stat, 3)).join(' · ')})` : '…'],
    ['7', '근거 ID와 3단 크리틱', '모든 주장은 카탈로그의 근거 ID만 인용하고, 숫자는 대조되며, 과잉해석 13규칙과 NVIDIA Nemotron Safety Guard를 통과해야 합니다',
      probe && ctrl ? `실제 사례 ${probe.n_cases}건에 넣은 틀린 주장 ${planted.reduce((a, [, s]) => a + s.correct, 0)}/${planted.reduce((a, [, s]) => a + s.n, 0)} 적발, 정상 대조군 ${ctrl.correct}/${ctrl.n} 통과` : '…'],
    ['8', 'PV 분류와 문헌 읽기', '라벨 상태 × 3중 기준 SDR로 PV 분류와 등급을 매기고, 문헌은 출판 유형 규칙 + 비자기회귀 판단 모델의 설계 판정으로 읽습니다',
      lit ? `설계 판정이 MEDLINE 색인과 ${fmt.pct(lit.accuracy, 1)} 일치 (${fmt.int(lit.n)}편)` : '…'],
  ]
  useEffect(() => { sim?.stimulate('layer', sel, 1.1, 10) }, [sel, sim])

  const pos = (k: string) => { const n = NODES.find((x) => x.key === k)!; return { cx: n.x + W / 2, cy: n.y + H / 2 } }
  const isBack = (a: string, b: string) => pos(b).cx < pos(a).cx || (a === 'critic' && b === 'deliberate')
  const path = (a: string, b: string) => {
    const p = pos(a), q = pos(b)
    if (a === 'critic' && b === 'deliberate') return `M${p.cx},${p.cy - H / 2} C${p.cx},${p.cy - H / 2 - 60} ${q.cx},${q.cy - H / 2 - 60} ${q.cx},${q.cy - H / 2}`
    if (a === 'action' && b === 'feedback') return `M${p.cx},${p.cy + H / 2} C${p.cx},${q.cy} ${q.cx + W / 2 + 40},${q.cy} ${q.cx + W / 2},${q.cy}`
    if (isBack(a, b)) { const my = Math.max(p.cy, q.cy) + 70; return `M${p.cx - W / 2},${p.cy} C${p.cx - W},${my} ${q.cx + W / 2 + 20},${my} ${q.cx + W / 2},${q.cy + (q.cy > p.cy ? -20 : 20)}` }
    const x1 = p.cx + W / 2, x2 = q.cx - W / 2
    return `M${x1},${p.cy} C${(x1 + x2) / 2},${p.cy} ${(x1 + x2) / 2},${q.cy} ${x2},${q.cy}`
  }

  return (
    <div className="page">
      <PageHead eyebrow="Architecture · connectome-routed agent"
        title={<>뇌의 층이 곧 에이전트의 층: <span style={{ color: 'var(--c-sense)' }}>감각 → 반사 → 기억 → 숙고 → 억제 → 행동</span></>}
        lede="MaleCNS 중앙뇌 49,244개 뉴런을 해부학 분류로 9개 기능 층에 배정하고, 같은 9개 층으로 에이전트를 짰습니다. 각 층은 실제로 구현한 스킬, 모델, 계산으로 채웠습니다. 노드를 누르면 해당 뉴런 집단이 오른쪽 커넥텀에서 켜집니다." />

      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.65fr) minmax(340px, 1fr)', alignItems: 'start' }}>
        <Card className="flush">
          <svg viewBox="0 0 1180 560" style={{ width: '100%', display: 'block' }}>
            <defs>
              <filter id="glow"><feGaussianBlur stdDeviation="3" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
              <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="rgba(120,170,255,0.05)" /></pattern>
            </defs>
            <rect width="1180" height="560" fill="url(#grid)" />
            <rect x="20" y="30" width="1150" height="500" rx="18" fill="none" stroke="rgba(120,170,255,0.18)" strokeDasharray="6 6" />
            <text x="36" y="22" fill="var(--text-3)" fontSize="10.5">OPENSHELL-STYLE POLICY BOUNDARY · deny-by-default egress: integrate.api.nvidia.com · api.typesafe.ai · api.fda.gov · eutils.ncbi.nlm.nih.gov</text>
            {EDGES.map(([a, b], i) => {
              const d = path(a, b)
              const c = LAYER_COLOR[a]
              return (
                <g key={i}>
                  <path d={d} fill="none" stroke={c} strokeOpacity={isBack(a, b) ? 0.22 : 0.4} strokeWidth={isBack(a, b) ? 1.1 : 1.8} strokeDasharray={isBack(a, b) ? '4 5' : undefined} />
                  {[0, 1, 2].map((k) => (
                    <circle key={k} r={3} fill={c} filter="url(#glow)">
                      <animateMotion dur={`${2.4 + (i % 3) * 0.4}s`} begin={`${k * 0.8 + i * 0.13}s`} repeatCount="indefinite" path={d} />
                    </circle>
                  ))}
                </g>
              )
            })}
            {NODES.map((n) => {
              const c = LAYER_COLOR[n.key]
              const on = n.key === sel
              return (
                <g key={n.key} transform={`translate(${n.x},${n.y})`} style={{ cursor: 'pointer' }} onClick={() => setSel(n.key)}>
                  <rect width={W} height={H} rx={14} fill={on ? 'rgba(14,22,42,0.98)' : 'rgba(10,16,30,0.92)'} stroke={c} strokeOpacity={on ? 1 : 0.5} strokeWidth={on ? 2 : 1}
                    style={{ filter: on ? `drop-shadow(0 0 14px ${c})` : undefined }} />
                  <rect x={0} y={0} width={4} height={H} rx={2} fill={c} />
                  <text x={16} y={24} fill={c} fontSize={10.5} letterSpacing={1.2}>{n.title.toUpperCase()}</text>
                  <text x={16} y={50} fill="var(--text)" fontSize={16} fontWeight={600} style={{ fontFamily: 'var(--font-kr)' }}>{n.short}</text>
                  <text x={16} y={71} fill="var(--text-3)" fontSize={10.5}>{n.brain.length > 24 ? n.brain.slice(0, 23) + '…' : n.brain}</text>
                  <text x={16} y={92} fill="var(--text-2)" fontSize={11}>{conn ? `${fmt.int(conn.meta.layers.find((l) => l.key === n.key)?.neurons ?? 0)} neurons` : ''}</text>
                </g>
              )
            })}
          </svg>
        </Card>

        <div className="stack" style={{ gap: 16 }}>
          <Card className="flush" style={{ height: 340 }}>
            <BrainView height={340} highlight={sel} view="front" bloom={1.2} autoRotate />
          </Card>
          <Card title={<><span style={{ color: LAYER_COLOR[sel] }}>{node.title}</span> · {node.agent}</>} sub={`${node.brain} — ${layer ? fmt.int(layer.neurons) : '…'} neurons in MaleCNS subgraph`}>
            <div className="row wrap" style={{ gap: 6, marginBottom: 12 }}>{node.tech.map((t) => <span key={t.t} className={`chip ${t.k ?? ''}`}>{t.t}</span>)}</div>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, lineHeight: 1.8, color: 'var(--text-2)' }}>{node.detail.map((d) => <li key={d}>{d}</li>)}</ul>
          </Card>
        </div>
      </div>

      <Card title={<>NVIDIA 스킬 기반 워크플로의 여덟 층 · 비자기회귀 판단 모델 병용 <span className="chip nv" style={{ marginLeft: 8 }}>build.nvidia.com NIM · Agent Skills · NemoClaw/OpenShell/OpenClaw</span></>}
        sub="FlyVigilance는 NVIDIA 스킬 위에 짠 약물감시 워크플로입니다. 글을 써야 하는 일은 NVIDIA Nemotron이, 타입 있는 확률 판단은 비자기회귀 판단 모델(Jev, TypeSafe AI)이 맡습니다. 무엇을, 어떤 근거로, 어떤 형식으로 묻고 답을 어디에 쓸지는 아래 여덟 층이 정합니다. 각 층의 효과는 실측했습니다"
        style={{ marginTop: 16 }}>
        <div className="grid g4" style={{ gap: 12 }}>
          {LAYERS.map(([n, t, d, e]) => (
            <div key={n} style={{ padding: 14, borderRadius: 14, border: '1px solid var(--line-2)', background: 'rgba(10,16,30,0.5)' }}>
              <div className="row" style={{ gap: 8 }}><span style={{ fontFamily: 'var(--font)', fontSize: 20, fontWeight: 700, color: 'var(--c-sense)' }}>{n}</span><b>{t}</b></div>
              <div style={{ fontSize: 12, color: 'var(--text-2)', margin: '6px 0 8px', lineHeight: 1.55 }}>{d}</div>
              <div className="chip ok" style={{ whiteSpace: 'normal', lineHeight: 1.4, fontSize: 10.5 }}>{e}</div>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid g4" style={{ marginTop: 16 }}>
        {[
          { h: 'Data plane', c: 'var(--c-sense)', items: ['FAERS 2012Q4–2026Q2 ASCII', 'DuckDB 계층: raw → core → ref → sig → ops', 'openFDA label · PubMed E-utilities', 'MaleCNS v1.0 flat connectome'] },
          { h: 'Model plane', c: 'var(--nvidia)', items: ['NVIDIA Nemotron 3 Super / Ultra / 3.5 Lightning (NIM): 생성 · System-2 평가 메모 · 국내 서식 구조화', 'NVIDIA Nemotron Safety Guard 8B v3: 주장별 안전 판정 (가드레일)', '비자기회귀 판단 모델 Jev (TypeSafe AI) 병용: 반사 판단 · 과잉해석 판정 · 문헌 설계 판정', 'nemotron-3-embed (의미 검색, 계획)'] },
          { h: 'Control plane', c: 'var(--c-encode)', items: ['결정론적 라우팅 정책 · 규정 모드 US/KR · DME 안전망', '3단 크리틱(13규칙) + 1회 재작성 루프', '참조 세트 검증 (OMOP·EU-ADR·Harpaz, 전향 포함)', 'NVIDIA Agent Skills (SKILL.md) 패키징 · 오프라인 테스트'] },
          { h: 'Connectome plane', c: 'var(--c-memory)', items: ['49,244 neurons · 1.05M signed edges', 'NT 부호: ACh +, GABA/Glu −', '브라우저 실시간 발화율 모델 30 Hz', 'ROI 90개 메시 · 스켈레톤 점구름 44만'] },
        ].map((p) => (
          <Card key={p.h} title={<span style={{ color: p.c }}>{p.h}</span>}>
            <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12.5, lineHeight: 1.8, color: 'var(--text-2)' }}>{p.items.map((i) => <li key={i}>{i}</li>)}</ul>
          </Card>
        ))}
      </div>
    </div>
  )
}
