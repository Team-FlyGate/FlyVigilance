import { useEffect, useState } from 'react'
import { api, fmt } from '../lib/data'
import type { EvidenceGrade, LitArticle } from '../lib/types'

export const GRADE_COLOR: Record<string, string> = { A: '#ff5d6c', B: '#ffb547', C: '#ffe066', L: '#37e6ff', D: '#6c7aa8', U: '#4a5878' }
const REG_STEPS = ['라벨 미기재', '이상반응 절', '경고·주의', '박스 경고']
const SIG_KO: Record<string, string> = { strong: '3중 신호', weak: '약한 신호 (1~2/3)', none: '신호 없음', insufficient: '보고 부족 (a<3)', unavailable: '통계 없음' }
const LIT_KO: Record<string, string> = { supports: '분석 연구가 지지', mixed: '분석 연구 결과 혼재', not_supported: '분석 연구가 지지 안 함', no_analytic: '분석 연구 없음', not_read: '읽지 않음' }
const DESIGN_KO: Record<string, string> = {
  meta_analysis: '메타분석', rct: 'RCT', cohort: '코호트', case_control: '환자대조군', pharmacovigilance: 'PV DB 연구',
  case_series: '증례군', case_report: '증례보고', review: '리뷰', preclinical: '전임상', other: '기타',
}

export function GradeLegend() {
  return (
    <div className="row wrap" style={{ gap: 6 }}>
      {[['A', '박스 경고 + 신호'], ['B', '라벨 기재 + 신호'], ['C', '신호, 라벨 미기재 또는 인과 미확립'], ['L', '라벨 기재, 신호 미검출'], ['D', '미기재, 신호 없음'], ['U', '판정 불가']].map(([g, t]) => (
        <span key={g} className="chip" style={{ fontSize: 10, color: GRADE_COLOR[g], borderColor: GRADE_COLOR[g] + '66' }}><b>{g}</b> {t}</span>
      ))}
    </div>
  )
}

function Articles({ arts }: { arts: LitArticle[] }) {
  if (!arts.length) return null
  return (
    <table className="tbl" style={{ fontSize: 11 }}>
      <thead><tr><th>PMID</th><th>설계</th><th>판정</th><th className="r">연관 보고 p</th></tr></thead>
      <tbody>{arts.map((a) => (
        <tr key={a.pmid} title={a.title}>
          <td><a href={`https://pubmed.ncbi.nlm.nih.gov/${a.pmid}/`} target="_blank" rel="noreferrer">{a.pmid}</a> <span className="dim">{a.year}</span></td>
          <td>{DESIGN_KO[a.design] ?? a.design}</td>
          <td><span className={`chip ${a.design_source === 'jev' ? 'jev' : ''}`} style={{ fontSize: 9.5 }}>{a.design_source === 'jev' ? 'Jev' : a.design_source === 'none' ? '-' : 'PubMed 유형'}</span></td>
          <td className="r num" style={{ color: a.supports >= 0.5 ? 'var(--ok)' : 'var(--text-3)' }}>{a.supports.toFixed(2)}</td>
        </tr>
      ))}</tbody>
    </table>
  )
}

export function GradeView({ g, compact = false }: { g: EvidenceGrade; compact?: boolean }) {
  const c = GRADE_COLOR[g.grade]
  const lit = g.axes.literature
  return (
    <div className="stack fade-in" style={{ gap: 10 }}>
      <div className="row" style={{ gap: 14, alignItems: 'flex-start' }}>
        <div style={{ width: 58, height: 58, borderRadius: 14, display: 'grid', placeItems: 'center', fontFamily: 'var(--font)', fontSize: 34, fontWeight: 700,
          color: '#081020', background: c, boxShadow: `0 0 26px -6px ${c}`, flex: 'none' }}>{g.grade}</div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 600 }}>{g.grade_name}</div>
          <div className="mono dim" style={{ fontSize: 10.5, marginTop: 2 }}>{g.drug} × {g.pt} · <span className="chip ev" style={{ fontSize: 9.5 }}>{g.id}</span></div>
        </div>
      </div>
      <div className="grid g3" style={{ gap: 8 }}>
        <div style={{ padding: 8, borderRadius: 10, border: '1px solid var(--line)' }}>
          <div className="dim mono" style={{ fontSize: 9.5 }}>규제 축 · 라벨</div>
          <div className="row" style={{ gap: 3, marginTop: 6 }}>{REG_STEPS.map((_, i) => <span key={i} style={{ flex: 1, height: 6, borderRadius: 3, background: i <= g.axes.regulatory && g.axes.regulatory > 0 ? c : 'rgba(120,170,255,0.12)' }} />)}</div>
          <div style={{ fontSize: 11.5, marginTop: 4 }}>{g.axes.regulatory_name}</div>
        </div>
        <div style={{ padding: 8, borderRadius: 10, border: '1px solid var(--line)' }}>
          <div className="dim mono" style={{ fontSize: 9.5 }}>통계 축 · FAERS</div>
          <div style={{ fontSize: 12, marginTop: 6, color: g.axes.signal === 'strong' ? '#ff9ce8' : undefined }}>{SIG_KO[g.axes.signal] ?? g.axes.signal}</div>
          {g.stats && <div className="num dim" style={{ fontSize: 10.5 }}>PRR {fmt.f(g.stats.prr)} · IC₀₂₅ {fmt.f(g.stats.ic025)} · a {fmt.int(g.stats.a)}</div>}
        </div>
        <div style={{ padding: 8, borderRadius: 10, border: '1px solid var(--line)' }}>
          <div className="dim mono" style={{ fontSize: 9.5 }}>문헌 · 참고 축</div>
          <div style={{ fontSize: 12, marginTop: 6 }}>{LIT_KO[lit.analytic_status] ?? lit.analytic_status}</div>
          <div className="num dim" style={{ fontSize: 10.5 }}>분석 {lit.analytic_supportive}/{lit.analytic_read} · 증례 {lit.anecdotal_supportive} · 읽음 {lit.read}</div>
        </div>
      </div>
      {g.disclaimer && <div style={{ fontSize: 11.5, padding: 8, borderRadius: 8, border: '1px solid rgba(255,224,102,0.4)' }}><b style={{ color: '#ffe066' }}>라벨의 인과 미확립 단서 · </b><span className="dim">"{g.disclaimer.quote}"</span></div>}
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
  if (!g) return <div className="row dim mono" style={{ fontSize: 11.5 }}><span className="spin" />라벨 조회 · 문헌 읽기(Jev) · 규칙 등급 계산 중</div>
  return <GradeView g={g} />
}
