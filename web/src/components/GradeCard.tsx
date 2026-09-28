import { useEffect, useState } from 'react'
import { api, fmt } from '../lib/data'
import type { EvidenceGrade, LitArticle } from '../lib/types'
import Term from './Term'
import { isEn, t } from '../lib/i18n'

// 한 글자 등급은 팀 시제품 호환용입니다. 화면의 중심은 PV 분류(라벨 상태 × SDR)입니다
export const GRADE_COLOR: Record<string, string> = { A: '#ff5d6c', B: '#ffb547', C: '#ffe066', L: '#37e6ff', D: '#6c7aa8', U: '#4a5878' }
export const PV_COLOR: Record<string, string> = {
  review_sdr: '#ff4fd8', potential_candidate: '#ffe066', undetermined: '#8a96b8',
  identified_candidate: '#ffb547', known_no_sdr: '#37e6ff', none: '#6c7aa8',
}
const LABEL_STEPS: [string, string][] = [['ar_postmarketing', '시판 후'], ['ar_unspecified', '이상반응'], ['ar_clinical_trials', '임상시험'], ['warnings_precautions', '경고·주의'], ['boxed', '박스 경고']]
const LIT_KO: Record<string, string> = { supports: '분석 연구가 지지', mixed: '분석 연구 결과 혼재', not_supported: '분석 연구가 지지 안 함', no_analytic: '분석 연구 없음', not_judged: '판단하지 못함', not_read: '읽지 않음' }
const LIT_EN: Record<string, string> = { supports: 'Analytic studies support it', mixed: 'Analytic studies are mixed', not_supported: 'Analytic studies do not support it', no_analytic: 'No analytic studies', not_judged: 'Could not be judged', not_read: 'Not read' }
const DESIGN_KO: Record<string, string> = {
  meta_analysis: '메타분석', rct: 'RCT', cohort: '코호트', case_control: '환자대조군', pharmacovigilance: 'PV DB 연구',
  case_series: '증례군', case_report: '증례보고', review: '리뷰', preclinical: '전임상', other: '기타',
}
const DESIGN_EN: Record<string, string> = {
  meta_analysis: 'Meta-analysis', rct: 'RCT', cohort: 'Cohort', case_control: 'Case-control', pharmacovigilance: 'PV database study',
  case_series: 'Case series', case_report: 'Case report', review: 'Review', preclinical: 'Preclinical', other: 'Other',
}
const ADDR_KO: Record<string, string> = { focus: '직접 다룸', reported: '보고함', passing: '지나가는 언급', unrelated: '무관' }
const ADDR_EN: Record<string, string> = { focus: 'Main focus', reported: 'Reports it', passing: 'Passing mention', unrelated: 'Unrelated' }

// 서버(api/_fv/grade.py)가 한국어로 주는 이름 · 설명 · 공백 문구를 영어 화면에서 바꿔 보여 줍니다.
// 이름은 키(pv_class, label_status, signal)로 찾고, 공백 문구는 원문 그대로 또는 정해진 틀(정규식)로 찾습니다.
const PV_CLASS_EN: Record<string, [string, string]> = {
  review_sdr: ['SDR needing review · new signal candidate', 'A new signal candidate: not on the label, yet an SDR (signal of disproportionate reporting) was detected, so it is reviewed first'],
  potential_candidate: ['Potential risk candidate', 'On the label, but the label states causality has not been established for this reaction'],
  undetermined: ['Undetermined', 'The label or FAERS statistics could not be confirmed. A person needs to check'],
  identified_candidate: ['Identified risk candidate', 'On the label and an SDR was detected. The known risk matches the reports'],
  known_no_sdr: ['Known risk · no SDR', 'A reaction listed in the approved label (clinical evidence). Common reactions usually do not produce an SDR'],
  none: ['Not applicable', 'Not on the label and no SDR. This means there is no current evidence, not that the drug is safe (R4)'],
}
const LABEL_STATUS_EN: Record<string, string> = {
  boxed: 'Boxed warning', warnings_precautions: 'Warnings & precautions', ar_clinical_trials: 'Adverse reactions (clinical trials)',
  ar_unspecified: 'Adverse reactions (unspecified)', ar_postmarketing: 'Adverse reactions (post-marketing spontaneous reports)', unlisted: 'Not on the label',
  no_label: 'Label not available',
}
const SIG_EN: Record<string, string> = { strong: 'SDR on all three criteria', weak: 'Some criteria met (not an SDR)', none: 'No SDR', insufficient: 'Too few reports (a<3)', unavailable: 'No statistics' }
const GAP_EN: Record<string, string> = {
  'FAERS 통계 부족: 동시 보고 3건 미만이거나 웨어하우스 상위 반응 목록 밖입니다': 'Insufficient FAERS statistics: fewer than 3 co-reports, or outside the warehouse top-reaction list',
  '미국 FDA 허가 라벨(openFDA drug/label)을 찾지 못했습니다. 국내 허가사항은 의약품안전나라에서 확인해야 합니다': 'The US FDA label (openFDA drug/label) was not found. The Korean label must be checked on the MFDS (Ministry of Food and Drug Safety) drug portal',
  '라벨 검색은 PT 문자열과 동의어 목록 기준입니다. 라벨이 다른 표현으로 적었을 수 있습니다': 'Label search uses the PT (preferred term) string and a synonym list. The label may use different wording',
  '라벨 기재가 시판 후 자발보고 절에만 있습니다(분모가 없고 빈도·인과를 확립하지 못한다는 정형 문구가 붙는 절)': 'Listed only in the post-marketing spontaneous-report section (no denominator; carries boilerplate saying frequency and causality cannot be established)',
  '금기 절에 환자 조건으로만 언급되어 있습니다. 금기 절은 이상반응 기재가 아닙니다': 'Mentioned only as a patient condition in the contraindications section, which is not an adverse-reaction listing',
  '이 반응명이 효능·효과(적응증)에도 나옵니다. 적응증 교란이나 효과 부족일 수 있습니다': 'This reaction name also appears in the indications. It may reflect confounding by indication or lack of effect',
  '변호사 보고를 빼면 SDR 이 사라집니다(소송으로 자극된 보고일 가능성)': 'The SDR disappears when lawyer reports are excluded (reports may be litigation-driven)',
  '문헌을 읽지 못했습니다': 'Literature could not be read',
  '문헌은 찾았지만 판단 모델 호출에 실패해 연관 보고 여부를 판단하지 못했습니다': 'Literature was found, but the judgment model call failed, so association could not be assessed',
  '상위 문헌에 이 약과 이 반응을 실제로 다룬 분석 연구(RCT·코호트·환자대조군·메타분석)가 없습니다': 'No analytic study (RCT, cohort, case-control, meta-analysis) among the top articles actually addresses this drug and reaction',
  'SDR 부재는 안전성의 증거가 아닙니다 (R4)': 'Absence of an SDR is not evidence of safety (R4)',
  '논문에 실린 증례는 제약사가 FAERS 에도 보고하는 경우가 많습니다. 미국 21 CFR 314.80 은 과학 문헌의 이상사례 정보를 검토하도록 의무로 두기 때문입니다. 그래서 문헌 편수와 FAERS 건수를 서로 독립된 근거로 더하지 않습니다.':
    'Published case reports are often also submitted to FAERS by manufacturers, because US 21 CFR 314.80 requires review of adverse-event information in the scientific literature. Literature counts and FAERS counts are therefore not added as independent evidence.',
}
const CAUTION_EN = "A population-level evidence classification and a 'candidate' only. It does not establish causality for this individual case; the actual classification is decided by the marketing authorization holder and regulators. Never cite the class without its evidence and gaps."
export function gapEn(x: string): string {
  if (!isEn()) return x
  if (GAP_EN[x]) return GAP_EN[x]
  let m = x.match(/^보고 편향 의심: 이 조합 보고의 (\S+)가 (변호사|소비자) 보고입니다\(FAERS 전체 변호사 (\S+)\)\. PRR 이 크다고 근거가 단단한 것은 아닙니다$/)
  if (m) return `Suspected reporting bias: ${m[1]} of reports for this pair come from ${m[2] === '변호사' ? 'lawyers' : 'consumers'} (lawyers are ${m[3]} of all FAERS reports). A large PRR (proportional reporting ratio) does not make the evidence strong`
  m = x.match(/^분석 연구 (\S+)편 중 (\S+)편만 연관을 지지합니다 \(문헌 결과 혼재 또는 반론\)$/)
  if (m) return `Only ${m[2]} of ${m[1]} analytic studies support the association (mixed or contrary literature)`
  return x
}

export function GradeLegend() {
  return (
    <div className="stack" style={{ gap: 6 }}>
      <div className="row wrap" style={{ gap: 6 }}>
        {[['review_sdr', t('1 검토가 필요한 SDR · 라벨 미기재 + SDR', '1 SDR needing review · not on label + SDR')], ['potential_candidate', t('2 잠재적 위해성 후보 · 인과 미확립 단서', '2 Potential risk candidate · causality-not-established note')],
          ['identified_candidate', t('3 규명된 위해성 후보 · 라벨 기재 + SDR', '3 Identified risk candidate · on label + SDR')], ['known_no_sdr', t('4 알려진 위험 · SDR 없음', '4 Known risk · no SDR')], ['none', t('5 해당 없음', '5 Not applicable')]].map(([k, label]) => (
          <span key={k} className="chip" style={{ fontSize: 10, color: PV_COLOR[k], borderColor: PV_COLOR[k] + '66' }}>{label}</span>
        ))}
      </div>
      <div className="dim" style={{ fontSize: 10.5 }}>
        {t(<>숫자는 <Term k="pvclass">PV 분류</Term>의 검토 우선순위입니다. <Term k="SDR" ko />은 통계 기준을 넘은 상태이며, 검증을 거쳐야 검증된 <Term k="signal">신호</Term>가 됩니다(EU <Term k="GVP">GVP Module IX</Term>).
        분류는 모두 '후보'이고 실제 분류는 허가권자와 규제기관이 정합니다.</>,
        <>The number is the review priority of the <Term k="pvclass">PV (pharmacovigilance) class</Term>. An <Term k="SDR" ko /> means a statistical threshold was crossed; it becomes a validated <Term k="signal">signal</Term> only after validation (EU <Term k="GVP">GVP Module IX</Term>).
        Every class is a 'candidate'; the actual classification is decided by the marketing authorization holder and regulators.</>)}
      </div>
    </div>
  )
}

function Articles({ arts }: { arts: LitArticle[] }) {
  if (!arts.length) return null
  return (
    <table className="tbl" style={{ fontSize: 11 }}>
      <thead><tr><th><Term k="PubMed">PMID</Term></th><th><Term k="design">{t('설계', 'Design')}</Term></th><th>{t('다루는가', 'Addresses it?')}</th><th className="r">{t('연관 보고 p', 'Association p')}</th></tr></thead>
      <tbody>{arts.map((a) => (
        <tr key={a.pmid} title={a.title} style={{ opacity: a.addresses === 'passing' || a.addresses === 'unrelated' ? 0.5 : 1 }}>
          <td><a href={`https://pubmed.ncbi.nlm.nih.gov/${a.pmid}/`} target="_blank" rel="noreferrer">{a.pmid}</a> <span className="dim">{a.year}</span></td>
          <td>{t(DESIGN_KO, DESIGN_EN)[a.design] ?? a.design} <span className={`chip ${a.design_source === 'jev' ? 'jev' : ''}`} style={{ fontSize: 9 }}>{a.design_source === 'jev' ? t('모델', 'Model') : a.design_source === 'none' ? '-' : t('PubMed 유형', 'PubMed type')}</span></td>
          <td className="dim">{a.addresses ? t(ADDR_KO, ADDR_EN)[a.addresses] ?? a.addresses : '-'}</td>
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
          color: '#081020', background: c, boxShadow: `0 0 26px -6px ${c}`, flex: 'none' }} title={t('PV 검토 우선순위', 'PV review priority')}>{g.review_priority}</div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 600 }}>{t(g.pv_class_name, PV_CLASS_EN[g.pv_class]?.[0] ?? g.pv_class_name)}</div>
          <div className="dim" style={{ fontSize: 11.5, marginTop: 2 }}>{t(g.pv_hint, PV_CLASS_EN[g.pv_class]?.[1] ?? g.pv_hint)}</div>
          <div className="mono dim" style={{ fontSize: 10.5, marginTop: 4 }}>{g.drug} × {g.pt} · {t('시제품 호환 등급', 'legacy prototype grade')} <b style={{ color: GRADE_COLOR[g.grade] }}>{g.grade}</b> · <span className="chip ev" style={{ fontSize: 9.5 }}>{g.id}</span></div>
        </div>
      </div>
      <div className="row wrap" style={{ gap: 6 }}>
        {g.flags?.severity_boxed && <span className="chip bad" style={{ fontSize: 10 }}>{t('심각성', 'Severity')} · <Term k="boxed">{t('박스 경고', 'Boxed warning')}</Term></span>}
        {g.flags?.dme && <span className="chip bad" style={{ fontSize: 10 }}>EMA <Term k="DME" /> · {t('1건만으로도 검토', 'reviewed even from a single report')}</span>}
        {bias && (bias.flag_lawyer || bias.flag_consumer) && <span className="chip warn" style={{ fontSize: 10 }}>{t(<><Term k="bias">보고 편향</Term> 의심</>, <>Suspected <Term k="bias">reporting bias</Term></>)} · {bias.flag_lawyer ? `${t('변호사', 'lawyers')} ${fmt.pct(bias.lawyer_share, 0)}` : `${t('소비자', 'consumers')} ${fmt.pct(bias.consumer_share, 0)}`}</span>}
        {g.flags?.indication_term && <span className="chip warn" style={{ fontSize: 10 }}>{t(<><Term k="indication">적응증</Term> 용어와 겹침</>, <>Overlaps an <Term k="indication">indication</Term> term</>)}</span>}
      </div>
      <div className="grid g3" style={{ gap: 8 }}>
        <div style={{ padding: 8, borderRadius: 10, border: '1px solid var(--line)' }}>
          <div className="dim mono" style={{ fontSize: 9.5 }}>{t('라벨 상태 · FDA 허가 라벨', 'Label status · FDA label')}</div>
          <div className="row" style={{ gap: 3, marginTop: 6 }}>{LABEL_STEPS.map((_, i) => <span key={i} style={{ flex: 1, height: 6, borderRadius: 3, background: step >= 0 && i <= step ? c : 'rgba(120,170,255,0.12)' }} />)}</div>
          <div style={{ fontSize: 11.5, marginTop: 4 }}>{t(g.axes.label_status_name, LABEL_STATUS_EN[g.axes.label_status] ?? g.axes.label_status_name)}</div>
        </div>
        <div style={{ padding: 8, borderRadius: 10, border: '1px solid var(--line)' }}>
          <div className="dim mono" style={{ fontSize: 9.5 }}>{t('보고 통계 · FAERS', 'Report statistics · FAERS')}</div>
          <div style={{ fontSize: 12, marginTop: 6, color: g.axes.signal === 'strong' ? '#ff9ce8' : undefined }}>{t(g.axes.signal_name, SIG_EN[g.axes.signal] ?? g.axes.signal_name)}</div>
          {g.stats && <div className="num dim" style={{ fontSize: 10.5 }}>PRR {fmt.f(g.stats.prr)} · IC₀₂₅ {fmt.f(g.stats.ic025)} · a {fmt.int(g.stats.a)}</div>}
          {bias && (bias.flag_lawyer || bias.flag_consumer) && <div className="num dim" style={{ fontSize: 10.5 }}>{t('변호사 보고 제외 PRR', 'PRR without lawyer reports')} {bias.no_lawyer.prr == null ? '-' : fmt.f(bias.no_lawyer.prr)} · {bias.no_lawyer.sdr ? t('SDR 유지', 'SDR holds') : t('SDR 사라짐', 'SDR disappears')}</div>}
        </div>
        <div style={{ padding: 8, borderRadius: 10, border: '1px solid var(--line)' }}>
          <div className="dim mono" style={{ fontSize: 9.5 }}>{t('문헌 · 참고 축', 'Literature · reference axis')}</div>
          <div style={{ fontSize: 12, marginTop: 6 }}>{t(LIT_KO, LIT_EN)[lit.analytic_status] ?? lit.analytic_status}</div>
          <div className="num dim" style={{ fontSize: 10.5 }}>{t('분석', 'analytic')} {lit.analytic_supportive}/{lit.analytic_read} · {t('증례', 'case reports')} {lit.anecdotal_supportive} · {t('읽음', 'read')} {lit.read}</div>
        </div>
      </div>
      {kn?.p != null && (
        <div className="row" style={{ gap: 10, alignItems: 'center', padding: 8, borderRadius: 10, border: '1px solid var(--line)' }}>
          <span className="dim mono" style={{ fontSize: 9.5, whiteSpace: 'nowrap' }}><Term k="kbmode">{t('지식 기반 판별', 'Knowledge-based check')}</Term> · {t('참고', 'reference')}</span>
          <div className="bar" style={{ flex: 1, height: 6 }}><i style={{ width: `${kn.p * 100}%`, background: 'var(--jev)' }} /></div>
          <span className="num" style={{ fontSize: 12 }}>{kn.p.toFixed(2)}</span>
          <span className="dim" style={{ fontSize: 10.5 }}>{t('공인된 연관일 확률', 'probability of an established association')}{kn.latency_ms ? ` · ${Math.round(kn.latency_ms)} ms` : ''}</span>
        </div>
      )}
      {g.disclaimer && <div style={{ fontSize: 11.5, padding: 8, borderRadius: 8, border: '1px solid rgba(255,224,102,0.4)' }}><b style={{ color: '#ffe066' }}>{t('그 반응에 붙은 인과 미확립 단서 · ', 'Label note that causality is not established for this reaction · ')}</b><span className="dim">"{g.disclaimer.quote}"</span></div>}
      {!compact && g.literature?.articles?.length ? <Articles arts={g.literature.articles} /> : null}
      <div className="row wrap" style={{ gap: 4 }}>{g.basis.map((b) => <span key={b} className="chip ev">{b}</span>)}</div>
      {g.gaps.length > 0 && <ul style={{ margin: 0, paddingLeft: 16, fontSize: 11, color: 'var(--text-3)' }}>{g.gaps.map((x) => <li key={x}>{gapEn(x)}</li>)}</ul>}
      <div className="note">{t(g.caution, CAUTION_EN)}</div>
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
  if (!g) return <div className="row dim mono" style={{ fontSize: 11.5 }}><span className="spin" />{t('FDA 허가 라벨 조회 · 문헌 읽기 · 규칙 분류 중', 'Looking up the FDA label · reading literature · classifying by rules')}</div>
  return <GradeView g={g} />
}
