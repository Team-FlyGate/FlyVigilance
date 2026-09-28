import { useEffect, useMemo, useRef, useState } from 'react'
import * as d3 from 'd3'
import { Card, Loading, PageHead } from '../components/ui'
import GradeCard, { GradeLegend } from '../components/GradeCard'
import { api, fmt, getJSON, type SignalRow } from '../lib/data'
import Term from '../components/Term'
import { t } from '../lib/i18n'

interface Resp { drug: string; asof: string; rows: SignalRow[] }
// 니라파립은 FlyDiscovery(PARP1 결합)에서 FlyVigilance(시판 후 이상사례)로 이어지는 Project-FlyGate 의 공통 분자입니다
const PRESETS = ['NIRAPARIB', 'SEMAGLUTIDE', 'TIRZEPATIDE', 'DUPILUMAB', 'METFORMIN', 'CANAGLIFLOZIN', 'PEMBROLIZUMAB', 'ADALIMUMAB', 'MONTELUKAST', 'LEVOFLOXACIN', 'ISOTRETINOIN']

const nsig = (r: SignalRow) => Number(r.evans) + Number(r.ror_sig) + Number(r.ic_sig)
const SIGCOL = ['#4a5878', '#ffcc4d', '#ff8f3a', '#ff4fd8']

function Scatter({ rows, sel, onSel }: { rows: SignalRow[]; sel: string | null; onSel: (pt: string) => void }) {
  const ref = useRef<HTMLDivElement>(null)
  const [w, setW] = useState(600)
  useEffect(() => { const ro = new ResizeObserver((e) => setW(e[0].contentRect.width)); if (ref.current) ro.observe(ref.current); return () => ro.disconnect() }, [])
  const h = 380, m = { l: 50, r: 20, t: 16, b: 38 }
  const x = d3.scaleLinear().domain(d3.extent(rows, (r) => r.ic025) as [number, number]).nice().range([m.l, w - m.r])
  const y = d3.scaleLog().domain([3, (d3.max(rows, (r) => r.a) ?? 10) * 1.3]).range([h - m.b, m.t])
  const labeled = new Set([...rows].filter((r) => nsig(r) === 3).sort((a, b) => b.ic025 - a.ic025).slice(0, 6).map((r) => r.pt))
  const rr = d3.scaleSqrt().domain([0, d3.max(rows, (r) => Math.log2(Math.max(1, r.prr))) ?? 1]).range([3, 16])
  return (
    <div ref={ref}>
      <svg width={w} height={h}>
        <g className="axis">
          {x.ticks(8).map((t) => <g key={t}><line x1={x(t)} x2={x(t)} y1={m.t} y2={h - m.b} strokeDasharray="2 4" /><text x={x(t)} y={h - m.b + 16} textAnchor="middle">{t}</text></g>)}
          {[3, 10, 30, 100, 300, 1000, 3000, 10000, 30000].filter((t) => t <= y.domain()[1]).map((t) => <g key={t}><line x1={m.l} x2={w - m.r} y1={y(t)} y2={y(t)} strokeDasharray="2 4" /><text x={m.l - 6} y={y(t) + 3} textAnchor="end">{fmt.compact(t)}</text></g>)}
          <text x={w - m.r} y={h - 6} textAnchor="end" fill="var(--text-3)">IC₀₂₅ (Bayesian lower bound, log₂) →</text>
          <text x={m.l} y={10} fill="var(--text-3)">co-reported cases (a, log)</text>
        </g>
        <line x1={x(0)} x2={x(0)} y1={m.t} y2={h - m.b} stroke="var(--c-memory)" strokeDasharray="5 4" opacity={0.7} />
        <text x={x(0) + 5} y={m.t + 10} fill="var(--c-memory)" fontSize={10}>IC₀₂₅ = 0</text>
        {rows.map((r) => (
          <g key={r.pt} transform={`translate(${x(r.ic025)},${y(r.a)})`} style={{ cursor: 'pointer' }} onClick={() => onSel(r.pt)}>
            <circle r={rr(Math.log2(Math.max(1, r.prr)))} fill={SIGCOL[nsig(r)]} opacity={sel === r.pt ? 1 : 0.55}
              stroke={sel === r.pt ? '#fff' : 'none'} strokeWidth={1.5} style={{ filter: nsig(r) === 3 ? 'drop-shadow(0 0 6px #ff4fd8)' : undefined }} />
            {(sel === r.pt || labeled.has(r.pt)) && <text x={10} y={4} fill="var(--text)" fontSize={10.5}>{r.pt}</text>}
          </g>
        ))}
      </svg>
    </div>
  )
}

function Forest({ rows }: { rows: SignalRow[] }) {
  const ref = useRef<HTMLDivElement>(null)
  const [w, setW] = useState(600)
  useEffect(() => { const ro = new ResizeObserver((e) => setW(e[0].contentRect.width)); if (ref.current) ro.observe(ref.current); return () => ro.disconnect() }, [])
  const rowH = 22, lw = 190, h = rows.length * rowH + 34
  const hi = Math.min(1000, d3.max(rows, (r) => r.prr_hi) ?? 10)
  const x = d3.scaleLog().domain([0.1, Math.max(10, hi)]).range([lw, w - 60]).clamp(true)
  return (
    <div ref={ref}>
      <svg width={w} height={h}>
        <g className="axis">{[0.1, 0.5, 1, 2, 5, 10, 50, 100, 500].filter((t) => t <= x.domain()[1]).map((t) => (
          <g key={t}><line x1={x(t)} x2={x(t)} y1={0} y2={h - 24} strokeDasharray="2 4" /><text x={x(t)} y={h - 8} textAnchor="middle">{t}</text></g>))}</g>
        <line x1={x(1)} x2={x(1)} y1={0} y2={h - 24} stroke="var(--text-3)" />
        <line x1={x(2)} x2={x(2)} y1={0} y2={h - 24} stroke="var(--c-memory)" strokeDasharray="5 4" />
        {rows.map((r, i) => (
          <g key={r.pt} transform={`translate(0,${i * rowH + 12})`}>
            <text x={lw - 10} y={4} textAnchor="end" fill="var(--text-2)" fontSize={11}>{r.pt.length > 26 ? r.pt.slice(0, 25) + '…' : r.pt}</text>
            <line x1={x(r.prr_lo)} x2={x(r.prr_hi)} y1={0} y2={0} stroke={SIGCOL[nsig(r)]} strokeWidth={2} />
            <rect x={x(r.prr) - 4} y={-4} width={8} height={8} fill={SIGCOL[nsig(r)]} transform={`rotate(45 ${x(r.prr)} 0)`} />
            <text x={w - 54} y={4} fill="var(--text)" fontSize={10.5}>{r.prr.toFixed(2)}</text>
          </g>
        ))}
      </svg>
    </div>
  )
}

export default function SignalLab() {
  const [drugs, setDrugs] = useState<{ drug: string; n: number }[]>([])
  // STEP 1 에서 넘어온 약물(#/signals?drug=…)이 있으면 그 약물로 시작합니다
  const fromHash = () => new URLSearchParams(location.hash.split('?')[1] ?? '').get('drug')?.toUpperCase() || null
  const [drug, setDrug] = useState(() => fromHash() ?? 'NIRAPARIB')
  useEffect(() => { const on = () => { const d = fromHash(); if (d) setDrug(d) }; window.addEventListener('hashchange', on); return () => window.removeEventListener('hashchange', on) }, [])
  const [q, setQ] = useState('')
  const [data, setData] = useState<Resp | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [sel, setSel] = useState<string | null>(null)
  const [onlySig, setOnlySig] = useState(false)
  useEffect(() => { getJSON<{ drug: string; n: number }[]>('/data/faers/drugs.json').then(setDrugs) }, [])
  useEffect(() => { setData(null); setErr(null); setSel(null); api<Resp>(`/api/signals/${encodeURIComponent(drug)}?limit=80`).then(setData).catch((e) => setErr(String(e))) }, [drug])
  const sugg = useMemo(() => q.length < 2 ? [] : drugs.filter((d) => d.drug.includes(q.toUpperCase())).slice(0, 8), [q, drugs])
  const rows = useMemo(() => (data?.rows ?? []).filter((r) => r.prr_lo && Number.isFinite(r.ic025) && (!onlySig || nsig(r) === 3)), [data, onlySig])
  const top = useMemo(() => [...rows].sort((a, b) => b.a - a.a).slice(0, 22), [rows])
  const n = drugs.find((d) => d.drug === drug)?.n
  const selRow = rows.find((r) => r.pt === sel)

  return (
    <div className="page">
      <PageHead eyebrow="Signal Lab · disproportionality"
        title={t(<>통계가 먼저, 모델은 그 다음 <span style={{ color: 'var(--c-memory)' }}>Signal Memory</span></>,
          <>Statistics first, the model second · <span style={{ color: 'var(--c-memory)' }}>Signal Memory</span></>)}
        lede={t(<><Term k="disproportionality">불균형 분석</Term>은 특정 약과 반응이 함께 보고된 비율을 다른 약 전체와 비교합니다. <Term k="PRR" ko />, <Term k="ROR" ko />, <Term k="IC025" ko />는 <Term k="SQL">DuckDB</Term> <Term k="warehouse">웨어하우스</Term>가 전 기간 중복 제거된 케이스로 계산합니다. 모델은 이 숫자를 만들지도 고치지도 않고, <Term k="critic">크리틱</Term>의 <Term k="oracle">숫자 오라클</Term>이 모델 문장의 모든 숫자를 이 표와 대조합니다. 세 기준(<Term k="evans">Evans</Term> ∧ ROR₀₂₅&gt;1 ∧ IC₀₂₅&gt;0)을 모두 넘으면 <Term k="SDR" ko />로 표시합니다. SDR은 검증된 <Term k="signal">신호</Term>가 아니라 검토를 시작할 이유입니다(EU <Term k="GVP">GVP Module IX</Term>).</>,
          <><Term k="disproportionality">Disproportionality analysis</Term> compares how often a drug and a reaction are reported together against all other drugs. The <Term k="PRR">proportional reporting ratio (PRR)</Term>, <Term k="ROR">reporting odds ratio (ROR)</Term> and <Term k="IC025">information component lower bound (IC025)</Term> are computed by the <Term k="SQL">DuckDB</Term> <Term k="warehouse">warehouse</Term> over deduplicated cases for the full period of the <Term k="FAERS">FDA Adverse Event Reporting System (FAERS)</Term>. The model neither produces nor edits these numbers, and the <Term k="critic">critic</Term>’s <Term k="oracle">number oracle</Term> checks every number in the model’s sentences against this table. A pair that passes all three criteria (<Term k="evans">Evans</Term> ∧ ROR₀₂₅&gt;1 ∧ IC₀₂₅&gt;0) is marked as a <Term k="SDR">signal of disproportionate reporting (SDR)</Term>. An SDR is not a validated <Term k="signal">signal</Term>; it is a reason to start a review (EU <Term k="GVP">GVP Module IX</Term>).</>)}
        right={<div className="row" style={{ gap: 8 }}>
          <span className="chip" style={{ color: SIGCOL[3] }}>● 3/3 = SDR</span><span className="chip" style={{ color: SIGCOL[2] }}>● 2/3</span>
          <span className="chip" style={{ color: SIGCOL[1] }}>● 1/3</span><span className="chip" style={{ color: SIGCOL[0] }}>● 0/3</span></div>} />

      <Card style={{ marginBottom: 16 }}>
        <div className="row wrap" style={{ gap: 10 }}>
          <div style={{ position: 'relative', width: 280 }}>
            <input className="input" placeholder={t('약물 검색 (예: WARFARIN)', 'Search drug (e.g. WARFARIN)')} value={q} onChange={(e) => setQ(e.target.value)} />
            {sugg.length > 0 && <div style={{ position: 'absolute', zIndex: 5, top: 42, left: 0, right: 0, background: 'var(--panel-solid)', border: '1px solid var(--line-2)', borderRadius: 10, overflow: 'hidden' }}>
              {sugg.map((s) => <div key={s.drug} onClick={() => { setDrug(s.drug); setQ('') }} style={{ padding: '7px 12px', cursor: 'pointer', fontSize: 12.5, display: 'flex', justifyContent: 'space-between' }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(55,230,255,0.08)')} onMouseLeave={(e) => (e.currentTarget.style.background = '')}>
                <span>{s.drug}</span><span className="num dim">{fmt.compact(s.n)}</span></div>)}
            </div>}
          </div>
          {PRESETS.map((p) => <button key={p} className="chip" style={{ cursor: 'pointer', color: p === drug ? 'var(--c-sense)' : undefined, borderColor: p === drug ? 'var(--c-sense)' : undefined }} onClick={() => setDrug(p)}>{p}</button>)}
          <label className="row" style={{ marginLeft: 'auto', gap: 6, fontSize: 12, cursor: 'pointer' }}><input type="checkbox" checked={onlySig} onChange={(e) => setOnlySig(e.target.checked)} />{t('3중 기준 SDR만', 'Triple-criteria SDRs only')}</label>
        </div>
      </Card>

      {err && <Card><div style={{ color: 'var(--bad)' }}>{err}</div></Card>}
      {!data && !err && <Loading />}
      {data && (
        <div className="grid" style={{ gridTemplateColumns: 'minmax(0,1.3fr) minmax(0,1fr)' }}>
          <Card title={<>{data.drug} <span className="dim" style={{ fontSize: 13, fontWeight: 400 }}>· {n ? `${fmt.int(n)} suspect cases` : ''} · as of {data.asof}</span></>}
            sub={t('점 크기 = log₂ PRR. 오른쪽 위일수록 보고 건수가 많고 베이지안 하한이 높은 반응입니다', 'Dot size = log₂ PRR. Toward the upper right: more reports and a higher Bayesian lower bound')}>
            <Scatter rows={rows} sel={sel} onSel={setSel} />
            {selRow && <div className="fade-in" style={{ marginTop: 10, padding: 12, borderRadius: 12, border: '1px solid var(--line-2)', display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 10 }}>
              <div style={{ gridColumn: 'span 2' }}><div className="dim mono" style={{ fontSize: 10 }}><Term k="MedDRA">PT</Term></div><b>{selRow.pt}</b></div>
              <div><div className="dim mono" style={{ fontSize: 10 }}><Term k="aE">a / E</Term></div><span className="num">{fmt.int(selRow.a)} / {fmt.f(selRow.expected, 1)}</span></div>
              <div><div className="dim mono" style={{ fontSize: 10 }}>PRR [<Term k="CI">95% CI</Term>]</div><span className="num">{fmt.f(selRow.prr)} [{fmt.f(selRow.prr_lo)}–{fmt.f(selRow.prr_hi)}]</span></div>
              <div><div className="dim mono" style={{ fontSize: 10 }}>ROR₀₂₅ · <Term k="chi2">χ²</Term></div><span className="num">{fmt.f(selRow.ror_lo)} · {fmt.f(selRow.chi2, 0)}</span></div>
              <div><div className="dim mono" style={{ fontSize: 10 }}>IC · IC₀₂₅</div><span className="num">{fmt.f(selRow.ic)} · {fmt.f(selRow.ic025)}</span></div>
            </div>}
          </Card>
          <Card title={<><Term k="pvclass">{t('PV 분류', 'PV classification')}</Term> · {t('근거 등급', 'evidence grade')} <span className="dim" style={{ fontSize: 12, fontWeight: 400 }}>· {sel ? `${data.drug} × ${sel}` : t('산점도나 표에서 반응을 고르세요', 'Pick a reaction in the scatter plot or table')}</span></>}
            sub={t(<>규칙으로 매깁니다: <Term k="label">라벨</Term> 상태(규제 축) × <Term k="FAERS" /> <Term k="triple">3중 기준</Term> SDR(통계 축). 문헌은 <Term k="NAR">비자기회귀 판단 모델</Term>이 읽어 참고 축으로 붙입니다</>,
              <>Assigned by rules: <Term k="label">label</Term> status (regulatory axis) × <Term k="FAERS" /> <Term k="triple">triple-criteria</Term> SDR (statistical axis). Literature is read by the <Term k="NAR">non-autoregressive judgment model</Term> and attached as a reference axis</>)} className="span2">
            <GradeLegend />
            <div style={{ marginTop: 12 }}>{sel ? <GradeCard drug={data.drug} pt={sel} /> : <div className="note">{t('팀 시제품(A~D)을 이어받아, 라벨에는 있으나 SDR이 없는 조합(L)과 판정 불가(U)를 나눴습니다. 인과 미확립 단서는 그 반응이 언급된 문장 주변에서만 찾습니다.', 'Building on the team prototype (A–D), pairs that are in the label but have no SDR (L) and pairs that cannot be judged (U) are separated out. Hints that causality is not established are searched only around the sentences that mention the reaction.')}</div>}</div>
          </Card>
          <Card title={<>Forest · PRR with <Term k="CI">95% CI</Term></>} sub={<>{t('보고 건수 상위 반응입니다. 점선 = PRR 2', 'Most-reported reactions. Dashed line = PRR 2')} (<Term k="evans">Evans</Term>)</>}>
            <Forest rows={top} />
          </Card>
          <Card title={<><Term k="disproportionality">Disproportionality</Term> table</>} className="span2" sub={<>{t('SQL 산출값 그대로입니다. 해석 기준: 불균형은 보고 연관성이며, 인과와 발생률은 따로 평가합니다', 'Raw SQL output. How to read it: disproportionality is a reporting association; causality and incidence are assessed separately')} (<Term k="overclaim">R1, R2</Term>)</>}>
            <div style={{ maxHeight: 420, overflow: 'auto' }}>
              <table className="tbl">
                <thead><tr><th>PT</th><th className="r">a</th><th className="r">E</th><th className="r">PRR</th><th className="r">95% CI</th><th className="r">ROR₀₂₅</th><th className="r">χ²</th><th className="r">IC₀₂₅</th><th>SDR criteria</th></tr></thead>
                <tbody>{rows.map((r) => (
                  <tr key={r.pt} onClick={() => setSel(r.pt)} style={{ cursor: 'pointer', background: sel === r.pt ? 'rgba(55,230,255,0.06)' : undefined }}>
                    <td>{r.pt}</td><td className="r num">{fmt.int(r.a)}</td><td className="r num dim">{fmt.f(r.expected, 1)}</td>
                    <td className="r num">{fmt.f(r.prr)}</td><td className="r num dim">{fmt.f(r.prr_lo)}–{fmt.f(r.prr_hi)}</td>
                    <td className="r num">{fmt.f(r.ror_lo)}</td><td className="r num dim">{fmt.f(r.chi2, 0)}</td><td className="r num">{fmt.f(r.ic025)}</td>
                    <td><div className="row" style={{ gap: 3 }}>{[r.evans, r.ror_sig, r.ic_sig].map((s, i) => <span key={i} className="legend-dot" style={{ background: s ? SIGCOL[3] : 'rgba(120,170,255,0.15)' }} />)}</div></td>
                  </tr>))}</tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
