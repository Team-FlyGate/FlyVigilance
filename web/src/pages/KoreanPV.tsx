import { useState } from 'react'
import BrainView from '../components/BrainView'
import { Card, PageHead, ProbBar } from '../components/ui'
import { useBrain } from '../lib/brain'
import { api, fmt, type Case, type TriageResult } from '../lib/data'
import { KR_SAMPLES, type KrSample } from '../lib/krSamples'
import { ACTION_META } from './MissionControl'
import Term from '../components/Term'
import { isEn, t } from '../lib/i18n'

type Form = KrSample['form']
const FORMS: Form[] = ['professional', 'consumer', 'narrative']
const formLabel = (f: Form) => ({
  professional: t('의약전문가용 서식', 'Healthcare-professional form'), consumer: t('일반인 보고', 'Consumer report'),
  narrative: t('자유 서술 (병원·약사 사례)', 'Free narrative (hospital / pharmacist case)'),
})[f]

interface Intake {
  kr_form: Record<string, Record<string, unknown> | string | null>
  case: Partial<Case> & { drugs: Case['drugs']; reactions: string[]; outcomes: string[] }
  narrative_en?: string; missing?: string[]; model: string; latency_ms: number
}
interface KrItem {
  id: string; name: string; choice: string; label: string; score: number; confidence: number; source: string
  evidence: string[]; needs_review: boolean; options: { key: string; label: string; score: number }[]
  // 규칙 항목('약물에 대해 알려진 정보')에만 있습니다
  method?: 'rule' | 'jev'; scope?: string; reaction?: string | null; mfds_checked?: boolean; lookup_failed?: boolean
}
interface KrCausality {
  items: KrItem[]; total: number; max: number; min: number; grade: string; band: string; approx: string
  who_umc: { choice: string; confidence: number; probabilities: Record<string, number> }
  label: { found: boolean; setid?: string; brand?: string; listed?: Record<string, boolean> } | null
  literature?: { query?: string; count?: number | null; case_reports_rule?: string[] } | null
  mfds_label?: { checked: boolean; reason: string; search_url: string }
  assessed_reaction?: string | null
  note: string; latency_ms: number; model: string
}

const whoName = (c: string) => (({
  certain: t('확실함', 'Certain'), probable: t('상당히 확실함', 'Probable / likely'), possible: t('가능함', 'Possible'),
  unlikely: t('가능성 적음', 'Unlikely'), conditional: t('평가 곤란', 'Conditional / unclassified'), unassessable: t('평가 불가', 'Unassessable / unclassifiable'),
}) as Record<string, string>)[c] ?? c
const GRADE_COLOR: Record<string, string> = { '확실함': '#ff5d6c', '가능성 높음': '#ffb547', '가능성 있음': '#37e6ff', '가능성 낮음': '#6c7aa8' }

// API(api/_fv/kr.py · triage.py)가 돌려주는 한국어 고정 문구를 영어 화면에서 옮기는 표입니다.
// 서식 항목 이름, 알고리즘 항목·선택지, 등급, 신속보고 기한처럼 정해진 문구만 옮기고,
// Nemotron 이 원문에서 뽑은 값(증상, 약 이름 등)은 데이터이므로 그대로 둡니다.
const KR_EXACT: Record<string, string> = {
  // 식약처 서식 섹션과 필드
  가_환자정보: 'A. Patient', 나_이상사례정보: 'B. Adverse event', 다_의약품정보: 'C. Medicines', 라_보고자정보: 'D. Reporter',
  마_보고서정보: 'E. Report', 바_종합의견: 'F. Overall comment',
  이니셜: 'initials', 나이: 'age', 성별: 'sex', 체중: 'weight', 원질환_병력: 'underlying disease / history', 알레르기_과거력: 'allergy history',
  이상사례명: 'event names', 발현일: 'onset', 종료일: 'end date', 경과_결과: 'course / outcome', 중대성: 'seriousness',
  사망: 'death', 생명위협: 'life-threatening', 입원_연장: 'hospitalization (or prolonged)', 장애: 'disability', 선천기형: 'congenital anomaly', 기타_의학적중요: 'other medically important',
  의심약물: 'suspect drugs', 병용약물: 'concomitant drugs', 성분명: 'ingredient', 성분명_영문: 'ingredient (INN)', 제품명: 'product', 용량_용법: 'dose / regimen',
  투여경로: 'route', 투여기간: 'duration', 투여목적: 'indication', 조치: 'action taken', 재투여: 'rechallenge',
  보고자_유형: 'reporter type', 소속_기관: 'institution', 보고유형: 'report type', 최초_추가: 'initial / follow-up',
  남: 'male', 여: 'female', 의사: 'physician', 약사: 'pharmacist', 간호사: 'nurse', '기타 의료인': 'other healthcare professional', '환자·소비자': 'patient / consumer',
  자발보고: 'spontaneous report', 연구: 'study', 문헌: 'literature', 최초: 'initial', 추가: 'follow-up',
  // 한국형 알고리즘 ver 2.0 항목
  '시간적 선후관계': 'Temporal relationship', '감량 또는 중단': 'Dose reduction or withdrawal', '이상사례의 과거력': 'Previous history of the event',
  비약물요인: 'Non-drug factors', '약물에 대해 알려진 정보': 'Known information about the drug', 재투약: 'Rechallenge', '특이적인 검사': 'Specific test',
  '선후관계 합당': 'Temporal sequence plausible', '선후관계 모순': 'Temporal sequence contradictory', 정보없음: 'No information',
  '감량 또는 중단 후 임상적 호전이 관찰됨': 'Clinical improvement after reduction or withdrawal', '감량 또는 중단과 무관한 임상경과를 보임': 'Clinical course unrelated to reduction or withdrawal',
  '감량 또는 중단을 시행하지 않음': 'Not reduced or withdrawn', 예: 'Yes', 아니오: 'No',
  '병용약물 단독으로 유해사례를 설명할 수 없는 경우': 'Concomitant drugs alone cannot explain the event', '병용약물 단독으로 유해사례를 설명할 수 있는 경우': 'Concomitant drugs alone can explain the event',
  '의심약물과 상호작용으로 설명되는 경우': 'Explained by an interaction with the suspect drug', '병용약물에 대한 설명이 없는 경우': 'No description of concomitant drugs',
  '비약물요인으로 유해사례가 설명되지 않음': 'Not explained by non-drug factors', '비약물요인으로 유해사례가 설명됨': 'Explained by non-drug factors',
  '허가사항(label, insert 등)에 반영되어 있음': 'Listed in the approved label (label, insert, etc.)', '허가사항에 반영되어 있지 않으나 증례보고가 있었음': 'Not in the label, but case reports exist',
  '알려진 바 없음': 'Nothing known', '재투약으로 동일한 유해사례가 발생함': 'Same event recurred on rechallenge', '재투약으로 동일한 유해사례가 발생하지 않음': 'Same event did not recur on rechallenge',
  재투약하지않음: 'Not rechallenged', '재투약하지 않음': 'Not rechallenged', 양성: 'Positive', 음성: 'Negative', '결과를 알 수 없음': 'Result unknown',
  // 등급과 구간
  확실함: 'Certain', '가능성 높음': 'Probable', '가능성 있음': 'Possible', '가능성 낮음': 'Unlikely',
  '12점 이상': '12 points or more', '6~11점': '6–11 points', '2~5점': '2–5 points', '1점 이하': '1 point or less',
  // 출처
  '미국 FDA 허가사항(openFDA drug/label)': 'US FDA label (openFDA drug/label)', '미국 FDA 허가사항·PubMed 조회': 'US FDA label · PubMed lookup', '조회 실패': 'Lookup failed',
  '한국형 알고리즘 등급(확실함·가능성 높음·가능성 있음·가능성 낮음)과 WHO-UMC 등급은 체계가 달라 서로 바꿔 쓰지 않습니다.':
    'The Korean algorithm grades (certain · probable · possible · unlikely) and the WHO-UMC categories are different systems and are never used interchangeably.',
  // 신속보고 기한
  "15일 이내 (의약품 등의 안전에 관한 규칙 별표 4의3 제7호 나목: 중대한 약물이상반응, '예상하지 못한' 요건 없음)":
    "Within 15 days (Korean Regulation on the Safety of Medicinal Products, Annex 4-3, item 7(b): serious adverse drug reaction, no 'unexpected' requirement)",
  '즉시 사람 검토: 인과관계 배제 여부 확인 (보고자와 품목허가를 받은 자가 모두 관련 없다고 판단한 경우에만 신속보고 제외, 별표 4의3 제1호 차목 단서)':
    'Immediate human review: confirm whether causality can be excluded (excluded from expedited reporting only if both the reporter and the marketing authorization holder judge it unrelated; Annex 4-3, item 1(j), proviso)',
  '즉시 사람 검토 (규정상 15일 신속보고 요건에는 해당하지 않음)': 'Immediate human review (does not meet the regulatory 15-day expedited criteria)',
}
// 사유·조회 범위처럼 값이 끼어 있는 문장은 조각 단위로 옮깁니다
const KR_FRAG: [RegExp, string][] = [
  [/인과관계 배제 불가/g, 'causality cannot be excluded'],
  [/중대한 약물이상반응 -> 15일 신속보고 후보 \(expected=([\d.]+)와 무관\)/g, 'serious ADR -> 15-day expedited candidate (regardless of expected=$1)'],
  [/인과관계 배제 후보 -> 보고자·품목허가권자 판단 확인 전까지 15일 기한은 그대로 둡니다/g, 'causality exclusion candidate -> the 15-day deadline stays until the reporter and marketing authorization holder confirm'],
  [/미국 FDA 허가사항\(([^)]*)\)의 (.+?) 절에 '([^']+)' 기재/g, "listed as '$3' in the $2 section(s) of the US FDA label ($1)"],
  [/미국 FDA 허가사항\(([^)]*)\)에 '([^']+)' 기재 없음/g, "'$2' not listed in the US FDA label ($1)"],
  [/ \(금기 절에만 언급\)/g, ' (mentioned only in the contraindications section)'],
  [/미국 FDA 허가사항 조회 실패\(([^)]*)\)/g, 'US FDA label lookup failed ($1)'],
  [/미국 FDA 허가사항\(openFDA drug\/label\)에서 이 성분의 라벨을 찾지 못했습니다/g, 'No label for this ingredient was found in the US FDA label database (openFDA drug/label)'],
  [/의심약물이나 평가할 반응명이 없어 허가사항·문헌을 조회하지 못했습니다/g, 'No suspect drug or reaction to assess, so the label and literature were not queried'],
  [/PubMed 증례보고 (\d+)건이 있으나 평가 반응이 이 약의 적응증과 겹쳐 그 질환 자체를 다룬 글일 수 있습니다\. 평가자가 확인해 주십시오/g,
    'PubMed has $1 case report(s), but the reaction overlaps with this drug\'s indication, so they may be about the disease itself. Please have an assessor confirm'],
  [/PubMed 증례보고\(PMID ([^)]*)\)/g, 'PubMed case reports (PMID $1)'],
  [/PubMed (.+?) 에서 증례보고 (\d+)건/g, 'PubMed $1: $2 case report(s)'],
  [/PubMed 조회 실패\(([^)]*)\)/g, 'PubMed lookup failed ($1)'],
  [/PubMed 는 조회하지 않았습니다/g, 'PubMed was not queried'],
  [/PubMed (.+?) 검색 (\S+)건, 그중 증례보고 0건/g, 'PubMed $1: $2 results, 0 case reports'],
  [/식약처 허가사항은 자동 조회하지 않았습니다\(의약품안전나라 robots\.txt 가 자동 수집을 막습니다\)/g,
    'The MFDS (Korean Ministry of Food and Drug Safety) label was not queried automatically (the Drug Safety Korea site\'s robots.txt disallows automated access)'],
  [/응답 없음/g, 'no response'],
]
/** API 가 준 한국어 고정 문구를 영어 화면에서 옮깁니다. 한국어 화면에서는 그대로 돌려줍니다. */
const kr = (v: string): string => {
  if (!isEn()) return v
  if (KR_EXACT[v]) return KR_EXACT[v]
  return KR_FRAG.reduce((acc, [re, en]) => acc.replace(re, en), v)
}

function Section({ title, data }: { title: string; data: unknown }) {
  const render = (v: unknown): React.ReactNode => {
    if (v === null || v === undefined || v === '') return <span className="dim">—</span>
    if (typeof v === 'boolean') return v ? t('예', 'Yes') : <span className="dim">{t('아니오', 'No')}</span>
    if (Array.isArray(v)) {
      if (!v.length) return <span className="dim">—</span>
      if (typeof v[0] === 'object') return <div className="stack" style={{ gap: 6 }}>{v.map((x, i) => <div key={i} style={{ padding: '6px 8px', borderRadius: 8, background: 'rgba(10,16,30,0.6)' }}>{render(x)}</div>)}</div>
      return v.map((x) => kr(String(x))).join(', ')
    }
    if (typeof v === 'object') {
      return (
        <div style={{ display: 'grid', gridTemplateColumns: '110px 1fr', gap: '3px 10px' }}>
          {Object.entries(v as Record<string, unknown>).map(([k, x]) => (
            <div key={k} style={{ display: 'contents' }}><span className="dim mono" style={{ fontSize: 10.5 }}>{kr(k).replace(/_/g, ' ')}</span><span style={{ fontSize: 12 }}>{render(x)}</span></div>
          ))}
        </div>
      )
    }
    return kr(String(v))
  }
  return (
    <div style={{ padding: 12, borderRadius: 12, border: '1px solid var(--line)', background: 'rgba(10,16,30,0.45)' }}>
      <div className="eyebrow" style={{ color: 'var(--c-sense)', marginBottom: 8, fontSize: 10.5 }}>{kr(title).replace(/_/g, ' ')}</div>
      {render(data)}
    </div>
  )
}

export default function KoreanPV() {
  const { sim } = useBrain()
  const [sample, setSample] = useState<KrSample>(KR_SAMPLES[0])
  const [text, setText] = useState(KR_SAMPLES[0].text)
  const [form, setForm] = useState<Form>(KR_SAMPLES[0].form)
  const [intake, setIntake] = useState<Intake | null>(null)
  const [caus, setCaus] = useState<KrCausality | null>(null)
  const [tri, setTri] = useState<Record<string, TriageResult>>({})
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [hl, setHl] = useState<string | null>(null)

  const pick = (s: KrSample) => { setSample(s); setText(s.text); setForm(s.form); setIntake(null); setCaus(null); setTri({}); setErr(null) }

  const run = async (label: string, layer: string, f: () => Promise<void>) => {
    setBusy(label); setErr(null); setHl(layer); sim?.stimulate('layer', layer, 1.2, 10)
    try { await f() } catch (e) { setErr(String(e)) } finally { setBusy(null); setHl(null) }
  }
  const doIntake = () => run('intake', 'encode', async () => {
    sim?.stimulate('channel', form === 'consumer' ? 'digital' : 'faers', 1.2, 8)
    const r = await api<Intake>('/api/kr/intake', { text, form })
    setIntake(r); setCaus(null); setTri({})
  })
  const doCaus = () => intake && run('caus', 'reflex', async () => {
    setCaus(await api<KrCausality>('/api/kr/causality', { case: intake.case, narrative: intake.narrative_en }))
    sim?.stimulate('layer', 'critic', 1, 6)
  })
  const doTriage = () => intake && run('triage', 'reflex', async () => {
    const [us, kr] = await Promise.all(['US', 'KR'].map((r) => api<TriageResult>(`/api/triage?regime=${r}`, intake.case)))
    setTri({ US: us, KR: kr })
    const a = ACTION_META[kr.decision.action]
    a?.layers.forEach((l, i) => setTimeout(() => sim?.stimulate('layer', l, 1, 6), 250 + i * 250))
  })

  return (
    <div className="page">
      <PageHead eyebrow={t('Korean PV · 국내 보고서식 · 한국형 인과성 평가 · 국내 규정 모드', 'Korean PV · Korean report forms · Korean causality assessment · Korean regulatory mode')}
        title={t(<>국내 보고 한 장이 <span style={{ color: 'var(--c-sense)' }}>구조화</span>되고 <span style={{ color: 'var(--jev)' }}>평가</span>되기까지</>,
          <>How one Korean report gets <span style={{ color: 'var(--c-sense)' }}>structured</span> and <span style={{ color: 'var(--jev)' }}>assessed</span></>)}
        lede={t(<>의약전문가용·일반인 보고서나 병원·약사의 사례 기사를 넣으면 NVIDIA <Term k="Nemotron" />이 <Term k="MFDS">식약처</Term>(식품의약품안전처) 공고 제2023-057호 서식(가~바)과 <Term k="triage">트리아지</Term>(사례 분류)용 케이스로 구조화합니다.
          <Term k="regional">지역의약품안전센터</Term>가 쓰는 <Term k="kralgo">한국형 인과성 평가 알고리즘 ver 2.0</Term>의 8개 항목 중 7개는 FlyVigilance가 <Term k="NAR">비자기회귀 판단 모델</Term>로 판단하고, '약물에 대해 알려진 정보' 항목은 모델이 고르지 않고 허가 <Term k="label">라벨</Term>·문헌 조회 규칙으로만 정합니다. 점수는 규칙으로 합산하며,
          국내 <Term k="expedited">신속보고</Term> 기준(중대한 <Term k="ADR">약물이상반응</Term>, 즉 인과관계를 배제할 수 없는 반응 → 15일)으로 라우팅합니다.</>,
          <>Paste a Korean healthcare-professional or consumer report, or a hospital or pharmacist case article, and NVIDIA <Term k="Nemotron" /> structures it into the sections (A–F) of the <Term k="MFDS">Ministry of Food and Drug Safety (MFDS)</Term> Notice No. 2023-057 form and into a case for <Term k="triage" />.
          Of the 8 items in the <Term k="kralgo">Korean causality assessment algorithm ver 2.0</Term> used by <Term k="regional">regional pharmacovigilance centers</Term>, FlyVigilance judges 7 with the <Term k="NAR">non-autoregressive judgment model</Term>; the item "known information about the drug" is never picked by the model and is set only by approved-<Term k="label" /> and literature lookup rules. Scores are summed by rules,
          and the case is routed under the Korean <Term k="expedited">expedited reporting</Term> criterion (a serious <Term k="ADR">adverse drug reaction</Term>, i.e. one whose causality cannot be excluded → 15 days).</>)} />

      <div className="grid" style={{ gridTemplateColumns: 'minmax(0,1.35fr) minmax(340px,1fr)', alignItems: 'start' }}>
        <div className="stack" style={{ gap: 16 }}>
          <Card title={t('1. 보고 입력', '1. Report input')} sub={t('데모 사례를 고르거나 직접 붙여 넣으세요. 공개 사례는 요지만 다시 쓴 글입니다', 'Pick a demo case or paste your own. The input is a Korean-language report; public cases are rewritten summaries, not the original text')}
            right={<button className="btn nv" onClick={doIntake} disabled={!!busy || !text.trim()}>{busy === 'intake' ? <span className="spin" /> : '◆'} {t('구조화 · NVIDIA Nemotron', 'Structure · NVIDIA Nemotron')}</button>}>
            <div className="row wrap" style={{ gap: 6, marginBottom: 10 }}>
              {KR_SAMPLES.map((s) => (
                <button key={s.id} className="chip" onClick={() => pick(s)} style={{ cursor: 'pointer', color: s.id === sample.id ? 'var(--c-sense)' : undefined, borderColor: s.id === sample.id ? 'var(--c-sense)' : undefined }}>{t(s.label, s.labelEn)}</button>
              ))}
            </div>
            <div className="row" style={{ gap: 8, marginBottom: 8 }}>
              <div className="seg">{FORMS.map((f) => <button key={f} className={form === f ? 'on' : ''} onClick={() => setForm(f)}>{formLabel(f)}</button>)}</div>
              <span className="dim" style={{ fontSize: 11.5 }}>{t('출처', 'Source')}: {sample.sourceUrl ? <a href={sample.sourceUrl} target="_blank" rel="noreferrer">{t(sample.source, sample.sourceEn)}</a> : t(sample.source, sample.sourceEn)}</span>
            </div>
            <textarea className="input" value={text} onChange={(e) => setText(e.target.value)} rows={9} style={{ fontFamily: 'var(--font-kr)', fontSize: 13, lineHeight: 1.6, resize: 'vertical', color: 'var(--text)' }} />
            {isEn() && text === sample.text && (
              <div className="note" style={{ marginTop: 8, whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                <b>English translation (for reference only; the Korean text above is what the model reads):</b>{'\n'}{sample.textEn}
              </div>
            )}
          </Card>

          {err && <Card><div style={{ color: 'var(--bad)' }}>{err}</div></Card>}

          {intake && (
            <Card title={<>{t('2. 식약처 보고서식으로 구조화', '2. Structured into the MFDS report form')} <span className="chip nv" style={{ marginLeft: 8 }}>{intake.model.split('/')[1]} · {fmt.ms(intake.latency_ms)}</span></>}
              sub={t('의약품등 이상사례·약물이상반응 보고서식(의약전문가용)의 가~바 섹션입니다. 원문에 없는 값은 비워 두고 누락 목록으로 돌려 드립니다', 'Sections A–F of the MFDS adverse event / adverse drug reaction report form (healthcare-professional version). Values missing from the source stay empty and are returned as a list of missing items. Extracted values stay in the original Korean')}
              right={<div className="row" style={{ gap: 8 }}>
                <button className="btn jev" onClick={doCaus} disabled={!!busy}>{busy === 'caus' ? <span className="spin" /> : '⚡'} {t('한국형 알고리즘 · FlyVigilance', 'Korean algorithm · FlyVigilance')}</button>
                <button className="btn" onClick={doTriage} disabled={!!busy}>{busy === 'triage' ? <span className="spin" /> : '⇄'} {t('규정 모드 비교', 'Compare regulatory modes')}</button>
              </div>}>
              <div className="grid g2" style={{ gap: 10 }}>
                {Object.entries(intake.kr_form).map(([k, v]) => <Section key={k} title={k} data={v} />)}
              </div>
              {intake.missing?.length ? <div className="row wrap" style={{ gap: 6, marginTop: 12 }}><span className="dim mono" style={{ fontSize: 10.5 }}>{t('누락 · 추가정보 요청 대상', 'Missing · to request as follow-up')}</span>{intake.missing.map((m) => <span key={m} className="chip warn">{m}</span>)}</div> : null}
              <div className="divider" />
              <div className="dim mono" style={{ fontSize: 10.5, marginBottom: 6 }}>{t('트리아지용 정규화 케이스 (역할·보고자·결과 코드는 서식 값에서 규칙으로 만듭니다)', 'Normalized case for triage (drug role, reporter and outcome codes are derived from the form values by rules)')}</div>
              <div className="row wrap" style={{ gap: 6 }}>
                {intake.case.drugs.map((d) => <span key={d.drug} className={`chip ${d.role === 'PS' ? 'bad' : ''}`}>{d.role} · {d.drug}{d.dechal === 'Y' ? ' · dechal+' : ''}</span>)}
                {intake.case.reactions.map((r) => <span key={r} className="chip" style={{ color: 'var(--text)' }}>{r}</span>)}
                <span className="chip">{t(`${intake.case.age ?? '?'}세`, `age ${intake.case.age ?? '?'}`)} · {intake.case.sex ?? '?'} · {t('보고자', 'reporter')} {intake.case.occp_cod ?? '?'}</span>
                <span className={`chip ${intake.case.outcomes.length ? 'bad' : 'ok'}`}>{intake.case.outcomes.length ? t(`중대: ${intake.case.outcomes.join(', ')}`, `Serious: ${intake.case.outcomes.join(', ')}`) : t('중대성 해당 없음', 'Not serious')}</span>
              </div>
            </Card>
          )}

          {caus && (
            <Card title={<>{t('3. 한국형 인과성 평가 알고리즘 ver 2.0', '3. Korean causality assessment algorithm ver 2.0')} <span className="chip jev" style={{ marginLeft: 8 }}>{t('비자기회귀 판단', 'Non-autoregressive judgment')} {fmt.ms(caus.latency_ms)} · {t('7문항', '7 items')} + <Term k="WHOUMC" /> {t('1회 호출', 'in one call')}</span></>}
              sub={t("7개 항목 선택은 비자기회귀 판단 모델이, '약물에 대해 알려진 정보'는 조회 규칙이, 점수 합산과 등급 구간은 규칙이 정합니다. 신뢰도 0.55 미만 항목과 '알려진 정보' 항목은 평가자 검토 대상으로 표시합니다",
                "The non-autoregressive judgment model picks the answer for 7 items; 'known information about the drug' is set by lookup rules; the score sum and grade bands are set by rules. Items with confidence below 0.55 and the 'known information' item are flagged for assessor review")}>
              <table className="tbl">
                <thead><tr><th>{t('항목', 'Item')}</th><th>{t('판단', 'Judgment')}</th><th className="r">{t('점수', 'Score')}</th><th>{t('근거', 'Evidence')}</th><th className="r">{t('신뢰도', 'Confidence')}</th></tr></thead>
                <tbody>{caus.items.map((it) => (
                  <tr key={it.id}>
                    <td style={{ whiteSpace: 'nowrap' }}>{kr(it.name)}</td>
                    <td>
                      {kr(it.label)}{it.needs_review && <span className="chip warn" style={{ marginLeft: 6, fontSize: 9.5 }}>{t('검토 필요', 'Needs review')}</span>}
                      {it.method === 'rule' && it.mfds_checked === false && <span className="chip warn" style={{ marginLeft: 6, fontSize: 9.5 }}>{t('식약처 허가사항 미확인', 'MFDS label not checked')}</span>}
                      {it.scope && <div className="dim" style={{ fontSize: 10.5, marginTop: 3 }}>{t('평가 반응', 'Assessed reaction')} {it.reaction ?? '—'} · {kr(it.scope)}</div>}
                    </td>
                    <td className="r num" style={{ color: it.score > 0 ? 'var(--ok)' : it.score < 0 ? 'var(--bad)' : 'var(--text-3)' }}>{it.score > 0 ? `+${it.score}` : it.score}</td>
                    <td>{it.source === 'jev' ? <span className="chip jev" style={{ fontSize: 9.5 }}>{t('판단 모델', 'Judgment model')}</span> : <span className={`chip ${it.lookup_failed ? 'warn' : 'ev'}`} title={it.evidence.join('\n')}>{kr(it.source)}</span>}</td>
                    <td className="r" style={{ width: 120 }}>{it.method === 'rule'
                      ? <span className="dim mono" style={{ fontSize: 10.5 }}>{it.lookup_failed ? t('조회 실패', 'Lookup failed') : t('규칙', 'Rule')}</span>
                      : <ProbBar p={it.confidence} color={it.needs_review ? 'var(--warn)' : 'var(--jev)'} />}</td>
                  </tr>
                ))}</tbody>
              </table>
              <div className="grid g2" style={{ marginTop: 14, gap: 12 }}>
                <div style={{ padding: 16, borderRadius: 14, border: `1px solid ${GRADE_COLOR[caus.grade]}88`, background: `color-mix(in srgb, ${GRADE_COLOR[caus.grade]} 10%, transparent)` }}>
                  <div className="eyebrow" style={{ color: GRADE_COLOR[caus.grade] }}>{t('한국형 알고리즘 ver 2.0', 'Korean algorithm ver 2.0')}</div>
                  <div className="row" style={{ gap: 12, marginTop: 6 }}>
                    <span className="num" style={{ fontSize: 34 }}>{caus.total}</span>
                    <div><b style={{ fontSize: 18, fontFamily: 'var(--font-kr)' }}>{kr(caus.grade)}</b><div className="dim" style={{ fontSize: 11.5 }}>{kr(caus.band)} · {caus.approx} · {t(`범위 ${caus.min}~${caus.max}점`, `range ${caus.min} to ${caus.max} points`)}</div></div>
                  </div>
                  <div className="pbar" style={{ marginTop: 10 }}><i style={{ width: `${((caus.total - caus.min) / (caus.max - caus.min)) * 100}%`, background: GRADE_COLOR[caus.grade] }} /></div>
                </div>
                <div style={{ padding: 16, borderRadius: 14, border: '1px solid var(--line-2)' }}>
                  <div className="eyebrow" style={{ color: 'var(--text-2)' }}><Term k="WHOUMC" /> {t('(별도 체계)', '(separate system)')}</div>
                  <div className="row" style={{ gap: 10, marginTop: 6 }}><b style={{ fontSize: 18, fontFamily: 'var(--font-kr)' }}>{whoName(caus.who_umc.choice)}</b><span className="chip">conf {caus.who_umc.confidence.toFixed(2)}</span></div>
                  <div className="note" style={{ marginTop: 8 }}>{kr(caus.note)}</div>
                </div>
              </div>
              <div className="note" style={{ marginTop: 10 }}>
                {t(<><b>허가사항 확인:</b> {!caus.label?.found && <>FDA 허가 라벨(openFDA drug/label)에서 이 성분을 찾지 못했습니다(국내 개발 신약 등). </>}
                '약물에 대해 알려진 정보' 점수는 FDA 허가 라벨(openFDA drug/label)과 PubMed 증례보고 검색 결과로만 정했습니다(라벨 기재 +3, 라벨에 없고 증례보고 있음 +2, 둘 다 없음 0).
                국내 평가 기준인 식약처 허가사항(의약품안전나라 사용상의 주의사항)은 자동으로 확인하지 않았습니다. 평가자가 확인하신 뒤 점수를 확정해 주세요. 식약처 허가사항에 기재되어 있으면 +3입니다.</>,
                <><b>Label check:</b> {!caus.label?.found && <>This ingredient was not found in the FDA label database (openFDA drug/label), e.g. a drug developed in Korea. </>}
                The score for 'known information about the drug' was set only from the FDA label (openFDA drug/label) and a PubMed case-report search (listed in label +3, not in label but case reports exist +2, neither 0).
                The Korean reference, the MFDS label (precautions for use on Drug Safety Korea), was not checked automatically. Please have an assessor confirm it before finalizing the score; if the MFDS label lists the reaction, it scores +3.</>)}
                {caus.mfds_label?.search_url && <> <a href={caus.mfds_label.search_url} target="_blank" rel="noreferrer">{t('의약품안전나라에서 검색', 'Search on Drug Safety Korea')}</a></>}
                {caus.literature?.case_reports_rule?.length ? (
                  <div style={{ marginTop: 6 }}>{t('PubMed 증례보고', 'PubMed case reports')}: {caus.literature.case_reports_rule.map((id, i) => (
                    <span key={id}>{i ? ', ' : ''}<a href={`https://pubmed.ncbi.nlm.nih.gov/${id}/`} target="_blank" rel="noreferrer">PMID {id}</a></span>
                  ))}</div>
                ) : null}
              </div>
            </Card>
          )}

          {tri.KR && tri.US && (
            <Card title={t('4. 규정 모드 비교 · 같은 판단, 다른 신속보고 규칙', '4. Regulatory modes · same judgment, different expedited-reporting rules')} sub={t("미국은 '중대하고 예상하지 못한' 사례, 한국은 중대한 약물이상반응(인과관계를 배제할 수 없는 반응)이 15일 신속보고 대상입니다 (별표 4의3 제7호 나목)", "In the US, 'serious and unexpected' cases require 15-day expedited reporting; in Korea, any serious adverse drug reaction (one whose causality cannot be excluded) does (Annex 4-3, item 7(b))")}>
              <div className="grid g2" style={{ gap: 12 }}>
                {(['KR', 'US'] as const).map((r) => {
                  const d = tri[r].decision, m = ACTION_META[d.action] ?? ACTION_META.monitor
                  return (
                    <div key={r} style={{ padding: 14, borderRadius: 14, border: `1px solid ${m.color}66`, background: `color-mix(in srgb, ${m.color} 8%, transparent)` }}>
                      <div className="row between"><span className="eyebrow" style={{ color: m.color }}>{r === 'KR' ? t('한국 식약처', 'Korea MFDS') : t('미국 FDA', 'US FDA')}</span><span className="chip">{t('반사 판단', 'Reflex judgment')} {fmt.ms(tri[r].jev.latency_ms)}</span></div>
                      <b style={{ fontFamily: 'var(--font-kr)', fontSize: 17, display: 'block', marginTop: 6 }}>{m.label}</b>
                      {d.deadline && <div className={`chip ${d.report15 ? 'bad' : 'warn'}`} style={{ marginTop: 8, whiteSpace: 'normal' }}>{kr(d.deadline)}</div>}
                      <ul style={{ margin: '8px 0 0', paddingLeft: 16 }}>{d.reasons.map((x) => <li key={x} className="mono" style={{ fontSize: 11 }}>{kr(x)}</li>)}</ul>
                    </div>
                  )
                })}
              </div>
              <div className="note" style={{ marginTop: 10 }}>
                {t(<>중대한 약물이상반응은 품목허가를 받은 자, 의약품도매상, 약국개설자, 의료기관개설자가 알게 된 날부터 15일 이내에 보고해야 합니다(별표 4의3 제7호 나목).
                약국·의료기관 개설자의 보고 의무는 중대한 사례에 한정되고(약사법 제68조의8 제2항), 비중대 사례는 자율 보고입니다.
                판단 모델이 WHO-UMC '가능성 적음(unlikely)'으로 본 중대 사례도 15일 대상에서 자동으로 빼지 않고 사람 확인(즉시 검토)으로 보냅니다. 보고자와 품목허가권자가 모두 관련 없다고 판단한 경우에만 약물이상반응에서 제외되기 때문입니다(별표 4의3 제1호 차목).</>,
                <>Marketing authorization holders, drug wholesalers, pharmacy owners and healthcare institution owners must report a serious adverse drug reaction within 15 days of becoming aware of it (Annex 4-3, item 7(b)).
                For pharmacies and healthcare institutions the obligation covers serious cases only (Pharmaceutical Affairs Act, Article 68-8(2)); non-serious cases are reported voluntarily.
                Even a serious case the judgment model rates WHO-UMC 'unlikely' is not automatically dropped from the 15-day track; it goes to a human for immediate review, because a reaction is excluded as an adverse drug reaction only when both the reporter and the marketing authorization holder judge it unrelated (Annex 4-3, item 1(j)).</>)}
              </div>
            </Card>
          )}
        </div>

        <div className="stack" style={{ gap: 16, position: 'sticky', top: 0 }}>
          <Card className="flush" style={{ height: 380 }}>
            <div style={{ position: 'absolute', left: 16, top: 12, zIndex: 2 }}>
              <div className="eyebrow" style={{ color: 'var(--text-3)' }}>Connectome state</div>
              <div style={{ fontSize: 12.5, marginTop: 2 }}>{hl ? `${hl} layer engaged` : 'resting stream'}</div>
            </div>
            <BrainView height={380} highlight={hl} view="front" bloom={1.1} />
          </Card>
          <Card title={t('국내 약물감시 흐름', 'Pharmacovigilance in Korea')} sub={t('팀 문서 「국내 PV 흐름 설명」 요약', 'Summary of the team document "Korean PV workflow explained"')}>
            <ol style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, lineHeight: 1.8, color: 'var(--text-2)' }}>{t(<>
              <li><b>보고</b>: 품목허가를 받은 자(제약사) 의무, 중대한 약물이상반응은 의약품도매상·약국개설자·의료기관개설자도 15일 이내 보고 의무, 의사·약사·환자는 자율 (<Term k="KAERS" ko /> · 1644-6223)</li>
              <li><b>지역의약품안전센터 28곳</b>: 개별 사례 인과성 평가 (WHO-UMC, 한국형 알고리즘 ver 2.0)</li>
              <li><b><Term k="KIDS" /> · KAERS</b>: 통계적 탐지(<Term k="PRR" />·<Term k="ROR" />·<Term k="IC025">IC</Term>) + 사례 분석 + 허가정보·문헌 검토 → <Term k="kr_signal">실마리정보</Term></li>
              <li><b>식약처</b>: 성분 단위 허가사항 변경 명령(3개월 내 반영), 안전성 서한, 회수</li>
              <li><b>공개·국제</b>: 실마리정보 알리미, WHO <Term k="VigiBase" /></li>
            </>, <>
              <li><b>Reporting</b>: mandatory for marketing authorization holders (pharma companies); drug wholesalers, pharmacy owners and healthcare institution owners must also report serious adverse drug reactions within 15 days; physicians, pharmacists and patients report voluntarily (<Term k="KAERS">Korea Adverse Event Reporting System (KAERS)</Term> · 1644-6223)</li>
              <li><b>28 regional pharmacovigilance centers</b>: causality assessment of individual cases (WHO-UMC, Korean algorithm ver 2.0)</li>
              <li><b><Term k="KIDS" /> · KAERS</b>: statistical detection (<Term k="PRR">proportional reporting ratio (PRR)</Term> · <Term k="ROR" /> · <Term k="IC025">IC</Term>) + case analysis + label and literature review → <Term k="kr_signal">safety signal information</Term></li>
              <li><b>MFDS (Ministry of Food and Drug Safety)</b>: ingredient-level label change orders (applied within 3 months), safety letters, recalls</li>
              <li><b>Public and international</b>: signal information alerts, WHO <Term k="VigiBase" /></li>
            </>)}</ol>
            <div className="note" style={{ marginTop: 8 }}>{t('FlyVigilance는 2단계(개별 평가)의 준비 작업과 3단계(신호 탐지)를 돕고, 판정과 보고는 평가자와 담당자가 합니다.', 'FlyVigilance prepares step 2 (individual assessment) and supports step 3 (signal detection); assessors and safety officers make the final judgment and file the reports.')}</div>
          </Card>
        </div>
      </div>
    </div>
  )
}
