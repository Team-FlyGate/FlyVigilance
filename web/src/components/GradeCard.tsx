import { useEffect, useState } from 'react'
import { api, fmt } from '../lib/data'
import type { EvidenceGrade, LitArticle } from '../lib/types'

// 한 글자 등급은 팀 시제품 호환용입니다. 화면의 중심은 PV 분류(라벨 상태 × SDR)입니다
export const GRADE_COLOR: Record<string, string> = { A: '#ff5d6c', B: '#ffb547', C: '#ffe066', L: '#37e6ff', D: '#6c7aa8', U: '#4a5878' }
export const PV_COLOR: Record<string, string> = {
  review_sdr: '#ff4fd8', potential_candidate: '#ffe066', undetermined: '#8a96b8',
  identified_candidate: '#ffb547', known_no_sdr: '#37e6ff', none: '#6c7aa8',
}
const LABEL_STEPS: [string, string][] = [['ar_postmarketing', '시판 후'], ['ar_unspecified', '이상반응'], ['ar_clinical_trials', '임상시험'], ['warnings_precautions', '경고·주의'], ['boxed', '박스 경고']]
const LIT_KO: Record<string, string> = { supports: '분석 연구가 지지', mixed: '분석 연구 결과 혼재', not_supported: '분석 연구가 지지 안 함', no_analytic: '분석 연구 없음', not_judged: '판단하지 못함', not_read: '읽지 않음' }
const DESIGN_KO: Record<string, string> = {
  meta_analysis: '메타분석', rct: 'RCT', cohort: '코호트', case_control: '환자대조군', pharmacovigilance: 'PV DB 연구',
  case_series: '증례군', case_report: '증례보고', review: '리뷰', preclinical: '전임상', other: '기타',
}
const ADDR_KO: Record<string, string> = { focus: '직접 다룸', reported: '보고함', passing: '지나가는 언급', unrelated: '무관' }

export function GradeLegend() {
  return (
    <div className="stack" style={{ gap: 6 }}>
      <div className="row wrap" style={{ gap: 6 }}>
        {[['review_sdr', '1 검토가 필요한 SDR · 라벨 미기재 + SDR'], ['potential_candidate', '2 잠재적 위해성 후보 · 인과 미확립 단서'],
          ['identified_candidate', '3 규명된 위해성 후보 · 라벨 기재 + SDR'], ['known_no_sdr', '4 알려진 위험 · SDR 없음'], ['none', '5 해당 없음']].map(([k, t]) => (
          <span key={k} className="chip" style={{ fontSize: 10, color: PV_COLOR[k], borderColor: PV_COLOR[k] + '66' }}>{t}</span>
        ))}
      </div>
      <div className="dim" style={{ fontSize: 10.5 }}>
        숫자는 PV 검토 우선순위입니다. SDR(불균형 보고 신호)은 통계 기준을 넘은 상태이며, 검증을 거쳐야 검증된 신호가 됩니다(EU GVP Module IX).
        분류는 모두 '후보'이고 실제 분류는 허가권자와 규제기관이 정합니다.
      </div>
    </div>
  )
}

function Articles({ arts }: { arts: LitArticle[] }) {
  if (!arts.length) return null
  return (
    <table className="tbl" style={{ fontSize: 11 }}>
      <thead><tr><th>PMID</th><th>설계</th><th>다루는가</th><th className="r">연관 보고 p</th></tr></thead>
      <tbody>{arts.map((a) => (
        <tr key={a.pmid} title={a.title} style={{ opacity: a.addresses === 'passing' || a.addresses === 'unrelated' ? 0.5 : 1 }}>
          <td><a href={`https://pubmed.ncbi.nlm.nih.gov/${a.pmid}/`} target="_blank" rel="noreferrer">{a.pmid}</a> <span className="dim">{a.year}</span></td>
          <td>{DESIGN_KO[a.design] ?? a.design} <span className={`chip ${a.design_source === 'jev' ? 'jev' : ''}`} style={{ fontSize: 9 }}>{a.design_source === 'jev' ? '모델' : a.design_source === 'none' ? '-' : 'PubMed 유형'}</span></td>
          <td className="dim">{a.addresses ? ADDR_KO[a.addresses] ?? a.addresses : '-'}</td>
          <td className="r num" style={{ color: (a.supports ?? 0) >= 0.5 ? 'var(--ok)' : 'var(--text-3)' }}>{a.supports == null ? '-' : a.supports.toFixed(2)}</td>
        </tr>
      ))}</tbody>
    </table>
  )
}

export function GradeView({ g, compact = false }: { g: EvidenceGrade; compact?: boolean }) {
  const c = PV_COLOR[g.pv_class] ?? '#8a96b8'
  const lit = g.axes.literature
  const bias = g.flags?.reporting_bias
  const step = LABEL_STEPS.findIndex(([k]) => k === g.axes.label_status)
  // 지식 기반 판별: 약·반응 이름으로 공인된 연관인지 보는 참고 축입니다(분류 규칙에는 쓰지 않습니다)
  const kn = (g.axes as { knowledge?: { p: number | null; latency_ms?: number } }).knowledge
  return (
    <div className="stack fade-in" style={{ gap: 10 }}>
      <div className="row" style={{ gap: 14, alignItems: 'flex-start' }}>
        <div style={{ width: 58, height: 58, borderRadius: 14, display: 'grid', placeItems: 'center', fontFamily: 'var(--font)', fontSize: 30, fontWeight: 700,
          color: '#081020', background: c, boxShadow: `0 0 26px -6px ${c}`, flex: 'none' }} title="PV 검토 우선순위">{g.review_priority}</div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 600 }}>{g.pv_class_name}</div>
          <div className="dim" style={{ fontSize: 11.5, marginTop: 2 }}>{g.pv_hint}</div>
          <div className="mono dim" style={{ fontSize: 10.5, marginTop: 4 }}>{g.drug} × {g.pt} · 시제품 호환 등급 <b style={{ color: GRADE_COLOR[g.grade] }}>{g.grade}</b> · <span className="chip ev" style={{ fontSize: 9.5 }}>{g.id}</span></div>
        </div>
      </div>
      <div className="row wrap" style={{ gap: 6 }}>
        {g.flags?.severity_boxed && <span className="chip bad" style={{ fontSize: 10 }}>심각성 · 박스 경고</span>}
        {g.flags?.dme && <span className="chip bad" style={{ fontSize: 10 }}>EMA DME · 1건만으로도 검토</span>}
        {bias && (bias.flag_lawyer || bias.flag_consumer) && <span className="chip warn" style={{ fontSize: 10 }}>보고 편향 의심 · {bias.flag_lawyer ? `변호사 ${fmt.pct(bias.lawyer_share, 0)}` : `소비자 ${fmt.pct(bias.consumer_share, 0)}`}</span>}
        {g.flags?.indication_term && <span className="chip warn" style={{ fontSize: 10 }}>적응증 용어와 겹침</span>}
      </div>
      <div className="grid g3" style={{ gap: 8 }}>
        <div style={{ padding: 8, borderRadius: 10, border: '1px solid var(--line)' }}>
          <div className="dim mono" style={{ fontSize: 9.5 }}>라벨 상태 · FDA 허가 라벨</div>
          <div className="row" style={{ gap: 3, marginTop: 6 }}>{LABEL_STEPS.map((_, i) => <span key={i} style={{ flex: 1, height: 6, borderRadius: 3, background: step >= 0 && i <= step ? c : 'rgba(120,170,255,0.12)' }} />)}</div>
          <div style={{ fontSize: 11.5, marginTop: 4 }}>{g.axes.label_status_name}</div>
        </div>
        <div style={{ padding: 8, borderRadius: 10, border: '1px solid var(--line)' }}>
          <div className="dim mono" style={{ fontSize: 9.5 }}>보고 통계 · FAERS</div>
          <div style={{ fontSize: 12, marginTop: 6, color: g.axes.signal === 'strong' ? '#ff9ce8' : undefined }}>{g.axes.signal_name}</div>
          {g.stats && <div className="num dim" style={{ fontSize: 10.5 }}>PRR {fmt.f(g.stats.prr)} · IC₀₂₅ {fmt.f(g.stats.ic025)} · a {fmt.int(g.stats.a)}</div>}
          {bias && (bias.flag_lawyer || bias.flag_consumer) && <div className="num dim" style={{ fontSize: 10.5 }}>변호사 보고 제외 PRR {bias.no_lawyer.prr == null ? '-' : fmt.f(bias.no_lawyer.prr)} · {bias.no_lawyer.sdr ? 'SDR 유지' : 'SDR 사라짐'}</div>}
        </div>
        <div style={{ padding: 8, borderRadius: 10, border: '1px solid var(--line)' }}>
          <div className="dim mono" style={{ fontSize: 9.5 }}>문헌 · 참고 축</div>
          <div style={{ fontSize: 12, marginTop: 6 }}>{LIT_KO[lit.analytic_status] ?? lit.analytic_status}</div>
          <div className="num dim" style={{ fontSize: 10.5 }}>분석 {lit.analytic_supportive}/{lit.analytic_read} · 증례 {lit.anecdotal_supportive} · 읽음 {lit.read}</div>
        </div>
      </div>
      {kn?.p != null && (
        <div className="row" style={{ gap: 10, alignItems: 'center', padding: 8, borderRadius: 10, border: '1px solid var(--line)' }}>
          <span className="dim mono" style={{ fontSize: 9.5, whiteSpace: 'nowrap' }}>지식 기반 판별 · 참고</span>
          <div className="bar" style={{ flex: 1, height: 6 }}><i style={{ width: `${kn.p * 100}%`, background: 'var(--jev)' }} /></div>
          <span className="num" style={{ fontSize: 12 }}>{kn.p.toFixed(2)}</span>
          <span className="dim" style={{ fontSize: 10.5 }}>공인된 연관일 확률{kn.latency_ms ? ` · ${Math.round(kn.latency_ms)} ms` : ''}</span>
        </div>
      )}
      {g.disclaimer && <div style={{ fontSize: 11.5, padding: 8, borderRadius: 8, border: '1px solid rgba(255,224,102,0.4)' }}><b style={{ color: '#ffe066' }}>그 반응에 붙은 인과 미확립 단서 · </b><span className="dim">"{g.disclaimer.quote}"</span></div>}
      {!compact && g.literature?.articles?.length ? <Articles arts={g.literature.articles} /> : null}
      <div className="row wrap" style={{ gap: 4 }}>{g.basis.map((b) => <span key={b} className="chip ev">{b}</span>)}</div>
      {g.gaps.length > 0 && <ul style={{ margin: 0, paddingLeft: 16, fontSize: 11, color: 'var(--text-3)' }}>{g.gaps.map((x) => <li key={x}>{x}</li>)}</ul>}
      <div className="note">{g.caution}</div>
    </div>
  )
}

export default function GradeCard({ drug, pt }: { drug: string; pt: string }) {
  const [g, setG] = useState<EvidenceGrade | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    setG(null); setErr(null)
    api<EvidenceGrade>(`/api/grade?drug=${encodeURIComponent(drug)}&pt=${encodeURIComponent(pt)}`).then(setG).catch((e) => setErr(String(e)))
  }, [drug, pt])
  if (err) return <div style={{ color: 'var(--bad)', fontSize: 12 }}>{err}</div>
  if (!g) return <div className="row dim mono" style={{ fontSize: 11.5 }}><span className="spin" />FDA 허가 라벨 조회 · 문헌 읽기 · 규칙 분류 중</div>
  return <GradeView g={g} />
}
