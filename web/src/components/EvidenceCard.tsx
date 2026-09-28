import { useEffect, useState } from 'react'
import { Card } from './ui'
import { getJSON } from '../lib/data'
import { DRUG_LABEL, HERO_DRUGS, useHeroDrug } from './HeroDocking'
import Step2Handoff from './Step2Handoff'

// 후보 근거 카드: STEP 1 이 STEP 2 로 넘기는 후보 한 장. 구조 · 계산 · 실험 · 선택성 근거와 발견 신뢰도,
// 그리고 이 근거로 말해도 되는 주장 / 안 되는 주장을 나란히 적습니다. 값은 evidence_cards.json(build_evidence_cards.py) 그대로입니다.

interface Ex { n: number; median: number; max: number; types: string[]; docs: number }
interface CardData {
  name: string; label: string; target: string; chembl: string; crystal_pdb: string; receptor_pdb: string
  structure: { method: string; resolution: number | null; organism: string | null; verdict: string; reasons: string[] }
  validation: { grade: string; crystal_hits: number; runs: number; pairwise_median: number | null; confidence_mean: number | null; confidence_sd: number | null }
  computational: { vina: number | null; dd_conf: number; dd_rmsd: number | null; boltz_pic50: number | null; xa_dd_conf: number; xa_vina: number | null }
  experimental: Record<string, Ex>
  selectivity: { gene: string; docking: number | null; chembl: Ex | null; status: 'supported' | 'exploratory' | 'measured-weak' | 'no-data' }[]
  confidence: { level: 'HIGH' | 'MEDIUM' | 'LOW'; score: number; checks: { name: string; ok: boolean; detail: string }[] }
  allowed: string[]; not_allowed: { rule: string; claim: string }[]
}

const GENE = (g: string) => (g === 'F10' ? 'Factor Xa' : g)
const STATUS: Record<string, [string, string]> = {
  supported: ['실측 결합', 'var(--ok)'], 'measured-weak': ['측정됨 · 약함', 'var(--jev)'], exploratory: ['탐색적 (도킹만)', 'var(--text-3)'], 'no-data': ['기록 없음', 'var(--text-3)'],
}
const LEVEL_COLOR = { HIGH: 'var(--ok)', MEDIUM: 'var(--jev)', LOW: 'var(--bad)' }

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="stack" style={{ gap: 5 }}>
      <span className="mono" style={{ fontSize: 10, letterSpacing: 1.6, color: 'var(--text-3)' }}>{title}</span>
      {children}
    </div>
  )
}
function Row({ k, v, ok }: { k: string; v: React.ReactNode; ok?: boolean }) {
  return (
    <div className="row between" style={{ fontSize: 12.5, gap: 10 }}>
      <span className="dim">{k}</span>
      <span className="num" style={{ textAlign: 'right' }}>{v}{ok !== undefined && <span style={{ marginLeft: 6, color: ok ? 'var(--ok)' : 'var(--bad)' }}>{ok ? '✓' : '✕'}</span>}</span>
    </div>
  )
}

export default function EvidenceCard() {
  const [f, setF] = useState<{ strong_pchembl: number; cards: Record<string, CardData> } | null>(null)
  const [drug, setDrug] = useHeroDrug()
  useEffect(() => { getJSON<{ strong_pchembl: number; cards: Record<string, CardData> }>('/discovery/data/evidence_cards.json').then(setF).catch(() => null) }, [])
  const c = f?.cards[drug] ?? f?.cards.niraparib
  if (!f || !c) return null
  const s = c.structure, v = c.validation, x = c.computational, p1 = c.experimental.PARP1
  return (
    <Card title={`후보 근거 카드 · ${c.label} → ${c.target}`}
      sub="STEP 2 로 넘기기 전에 이 후보에 대해 무엇을 말해도 되는지 정합니다. 구조 · 계산 · 실험 · 선택성 근거를 한 장에 모았습니다"
      right={<div className="row" style={{ gap: 6 }}>
        {HERO_DRUGS.filter((d) => f.cards[d]).map((d) => (
          <button key={d} className={`chip ${d === c.name ? 'jev' : ''}`} style={{ cursor: 'pointer', fontWeight: d === c.name ? 700 : 500 }} onClick={() => setDrug(d)}>{DRUG_LABEL[d]}</button>
        ))}
      </div>}
      style={{ marginBottom: 16 }}>
      <div className="grid fade-in" key={c.name} style={{ gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.15fr)', gap: 22 }}>
        <div className="stack" style={{ gap: 16 }}>
          <Section title="STRUCTURE">
            <Row k="결정 구조" v={`PDB ${c.crystal_pdb} · ${s.method} ${s.resolution ?? '–'} Å`} ok={s.verdict === '도킹 가능'} />
            <Row k="생물종" v={s.organism ?? '–'} />
            <Row k="공결정 리간드" v="있음" ok />
            {s.reasons.length > 0 && <span style={{ fontSize: 11.5, color: 'var(--jev)' }}>주의: {s.reasons.join(', ')}</span>}
          </Section>
          <Section title="COMPUTATIONAL">
            {x.vina !== null && <Row k="Vina" v={`${x.vina} kcal/mol`} />}
            <Row k={`DiffDock (${c.receptor_pdb})`} v={`신뢰도 ${x.dd_conf} · 결정 자리 ${x.dd_rmsd ?? '–'} Å`} />
            <Row k="반복 재도킹" v={`${v.crystal_hits}/${v.runs}회 정답 · 등급 ${v.grade}`} ok={v.grade === 'HIGH'} />
            <Row k="포즈 수렴" v={`반복 간 ${v.pairwise_median ?? '–'} Å`} />
            <Row k="신뢰도 흔들림" v={`표준편차 ${v.confidence_sd ?? '–'}`} />
            {x.boltz_pic50 !== null && <Row k="Boltz-2 예측" v={`pIC50 ${x.boltz_pic50.toFixed(2)} (예측)`} />}
          </Section>
        </div>
        <div className="stack" style={{ gap: 16 }}>
          <Section title="EXPERIMENTAL · ChEMBL">
            <Row k="PARP1 기록" v={p1 ? `${p1.n}건 · 문헌 ${p1.docs}편` : '없음'} ok={!!p1 && p1.median >= f.strong_pchembl} />
            {p1 && <Row k="pChEMBL" v={`중앙값 ${p1.median} · 최대 ${p1.max}`} />}
            {p1 && <Row k="측정 종류" v={p1.types.join(' · ')} />}
            <span className="mono dim" style={{ fontSize: 10 }}>{c.chembl} · pChEMBL = -log(몰 농도) · {f.strong_pchembl} 이상 = 1 µM 보다 강함</span>
          </Section>
          <Section title="SELECTIVITY">
            {c.selectivity.map((r) => (
              <div key={r.gene} style={{ display: 'grid', gridTemplateColumns: '78px 1fr auto', gap: 8, fontSize: 12.5, alignItems: 'baseline' }}>
                <b>{GENE(r.gene)}</b>
                <span className="num dim" style={{ fontSize: 11 }}>{r.docking !== null ? `도킹 ${r.docking}` : '도킹 안 함'}{r.chembl ? ` · 실측 ${r.chembl.median} (${r.chembl.n})` : ''}</span>
                <span style={{ fontSize: 11.5, color: STATUS[r.status][1] }}>{STATUS[r.status][0]}</span>
              </div>
            ))}
          </Section>
          <Section title="DISCOVERY CONFIDENCE">
            <div className="row" style={{ gap: 10, alignItems: 'center' }}>
              <div style={{ flex: 1, height: 10, borderRadius: 5, background: 'rgba(120,170,255,0.12)', overflow: 'hidden' }}>
                <div style={{ width: `${(c.confidence.score / 3) * 100}%`, height: '100%', background: LEVEL_COLOR[c.confidence.level], opacity: 0.85 }} />
              </div>
              <b className="mono" style={{ color: LEVEL_COLOR[c.confidence.level] }}>{c.confidence.level}</b>
            </div>
            {c.confidence.checks.map((k) => (
              <div key={k.name} style={{ fontSize: 11.5 }}><span style={{ color: k.ok ? 'var(--ok)' : 'var(--bad)', marginRight: 6 }}>{k.ok ? '✓' : '✕'}</span><b>{k.name}</b> <span className="dim">{k.detail}</span></div>
            ))}
          </Section>
        </div>
        <div className="stack" style={{ gap: 10 }}>
          <Section title="ALLOWED CLAIM">
            {c.allowed.map((a, i) => (
              <div key={i} style={{ padding: '8px 10px', borderRadius: 9, background: 'rgba(61,220,151,0.06)', border: '1px solid rgba(61,220,151,0.3)', fontSize: 12.5, lineHeight: 1.55 }}>“{a}”</div>
            ))}
          </Section>
          <Section title="NOT ALLOWED">
            {c.not_allowed.map((a, i) => (
              <div key={i} style={{ padding: '8px 10px', borderRadius: 9, background: 'rgba(255,93,108,0.05)', border: '1px solid rgba(255,93,108,0.3)', fontSize: 12.5, lineHeight: 1.55 }}>
                <span className="mono" style={{ fontSize: 10, color: 'var(--bad)', marginRight: 6 }}>{a.rule}</span>“{a.claim}”
              </div>
            ))}
          </Section>
          <Step2Handoff drug={c.name} />
        </div>
      </div>
    </Card>
  )
}
