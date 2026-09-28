import { useState } from 'react'
import BrainView from '../components/BrainView'
import { Card, PageHead, ProbBar } from '../components/ui'
import { useBrain } from '../lib/brain'
import { api, fmt, type Case, type TriageResult } from '../lib/data'
import { KR_SAMPLES, type KrSample } from '../lib/krSamples'
import { ACTION_META } from './MissionControl'

type Form = KrSample['form']
const FORM_LABEL: Record<Form, string> = {
  professional: '의약전문가용 서식', consumer: '일반인 보고', narrative: '자유 서술 (병원·약사 사례)',
}

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

const WHO_KR: Record<string, string> = {
  certain: '확실함', probable: '상당히 확실함', possible: '가능함', unlikely: '가능성 적음', conditional: '평가 곤란', unassessable: '평가 불가',
}
const GRADE_COLOR: Record<string, string> = { '확실함': '#ff5d6c', '가능성 높음': '#ffb547', '가능성 있음': '#37e6ff', '가능성 낮음': '#6c7aa8' }

function Section({ title, data }: { title: string; data: unknown }) {
  const render = (v: unknown): React.ReactNode => {
    if (v === null || v === undefined || v === '') return <span className="dim">—</span>
    if (typeof v === 'boolean') return v ? '예' : <span className="dim">아니오</span>
    if (Array.isArray(v)) {
      if (!v.length) return <span className="dim">—</span>
      if (typeof v[0] === 'object') return <div className="stack" style={{ gap: 6 }}>{v.map((x, i) => <div key={i} style={{ padding: '6px 8px', borderRadius: 8, background: 'rgba(10,16,30,0.6)' }}>{render(x)}</div>)}</div>
      return v.join(', ')
    }
    if (typeof v === 'object') {
      return (
        <div style={{ display: 'grid', gridTemplateColumns: '110px 1fr', gap: '3px 10px' }}>
          {Object.entries(v as Record<string, unknown>).map(([k, x]) => (
            <div key={k} style={{ display: 'contents' }}><span className="dim mono" style={{ fontSize: 10.5 }}>{k.replace(/_/g, ' ')}</span><span style={{ fontSize: 12 }}>{render(x)}</span></div>
          ))}
        </div>
      )
    }
    return String(v)
  }
  return (
    <div style={{ padding: 12, borderRadius: 12, border: '1px solid var(--line)', background: 'rgba(10,16,30,0.45)' }}>
      <div className="eyebrow" style={{ color: 'var(--c-sense)', marginBottom: 8, fontSize: 10.5 }}>{title.replace(/_/g, ' ')}</div>
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
      <PageHead eyebrow="Korean PV · 국내 보고서식 · 한국형 인과성 평가 · 국내 규정 모드"
        title={<>국내 보고 한 장이 <span style={{ color: 'var(--c-sense)' }}>구조화</span>되고 <span style={{ color: 'var(--jev)' }}>평가</span>되기까지</>}
        lede={<>의약전문가용·일반인 보고서나 병원·약사의 사례 기사를 넣으면 NVIDIA Nemotron이 식약처 공고 제2023-057호 서식(가~바)과 트리아지용 케이스로 구조화합니다.
          지역의약품안전센터가 쓰는 한국형 인과성 평가 알고리즘 ver 2.0의 8개 항목 중 7개는 FlyVigilance가 비자기회귀 판단 모델로 판단하고, '약물에 대해 알려진 정보' 항목은 모델이 고르지 않고 허가 라벨·문헌 조회 규칙으로만 정합니다. 점수는 규칙으로 합산하며,
          국내 신속보고 기준(중대한 약물이상반응, 즉 인과관계를 배제할 수 없는 반응 → 15일)으로 라우팅합니다.</>} />

      <div className="grid" style={{ gridTemplateColumns: 'minmax(0,1.35fr) minmax(340px,1fr)', alignItems: 'start' }}>
        <div className="stack" style={{ gap: 16 }}>
          <Card title="1. 보고 입력" sub="데모 사례를 고르거나 직접 붙여 넣으세요. 공개 사례는 요지만 다시 쓴 글입니다"
            right={<button className="btn nv" onClick={doIntake} disabled={!!busy || !text.trim()}>{busy === 'intake' ? <span className="spin" /> : '◆'} 구조화 · NVIDIA Nemotron</button>}>
            <div className="row wrap" style={{ gap: 6, marginBottom: 10 }}>
              {KR_SAMPLES.map((s) => (
                <button key={s.id} className="chip" onClick={() => pick(s)} style={{ cursor: 'pointer', color: s.id === sample.id ? 'var(--c-sense)' : undefined, borderColor: s.id === sample.id ? 'var(--c-sense)' : undefined }}>{s.label}</button>
              ))}
            </div>
            <div className="row" style={{ gap: 8, marginBottom: 8 }}>
              <div className="seg">{(Object.keys(FORM_LABEL) as Form[]).map((f) => <button key={f} className={form === f ? 'on' : ''} onClick={() => setForm(f)}>{FORM_LABEL[f]}</button>)}</div>
              <span className="dim" style={{ fontSize: 11.5 }}>출처: {sample.sourceUrl ? <a href={sample.sourceUrl} target="_blank" rel="noreferrer">{sample.source}</a> : sample.source}</span>
            </div>
            <textarea className="input" value={text} onChange={(e) => setText(e.target.value)} rows={9} style={{ fontFamily: 'var(--font-kr)', fontSize: 13, lineHeight: 1.6, resize: 'vertical' }} />
          </Card>

          {err && <Card><div style={{ color: 'var(--bad)' }}>{err}</div></Card>}

          {intake && (
            <Card title={<>2. 식약처 보고서식으로 구조화 <span className="chip nv" style={{ marginLeft: 8 }}>{intake.model.split('/')[1]} · {fmt.ms(intake.latency_ms)}</span></>}
              sub="의약품등 이상사례·약물이상반응 보고서식(의약전문가용)의 가~바 섹션입니다. 원문에 없는 값은 비워 두고 누락 목록으로 돌려 드립니다"
              right={<div className="row" style={{ gap: 8 }}>
                <button className="btn jev" onClick={doCaus} disabled={!!busy}>{busy === 'caus' ? <span className="spin" /> : '⚡'} 한국형 알고리즘 · FlyVigilance</button>
                <button className="btn" onClick={doTriage} disabled={!!busy}>{busy === 'triage' ? <span className="spin" /> : '⇄'} 규정 모드 비교</button>
              </div>}>
              <div className="grid g2" style={{ gap: 10 }}>
                {Object.entries(intake.kr_form).map(([k, v]) => <Section key={k} title={k} data={v} />)}
              </div>
              {intake.missing?.length ? <div className="row wrap" style={{ gap: 6, marginTop: 12 }}><span className="dim mono" style={{ fontSize: 10.5 }}>누락 · 추가정보 요청 대상</span>{intake.missing.map((m) => <span key={m} className="chip warn">{m}</span>)}</div> : null}
              <div className="divider" />
              <div className="dim mono" style={{ fontSize: 10.5, marginBottom: 6 }}>트리아지용 정규화 케이스 (역할·보고자·결과 코드는 서식 값에서 규칙으로 만듭니다)</div>
              <div className="row wrap" style={{ gap: 6 }}>
                {intake.case.drugs.map((d) => <span key={d.drug} className={`chip ${d.role === 'PS' ? 'bad' : ''}`}>{d.role} · {d.drug}{d.dechal === 'Y' ? ' · dechal+' : ''}</span>)}
                {intake.case.reactions.map((r) => <span key={r} className="chip" style={{ color: 'var(--text)' }}>{r}</span>)}
                <span className="chip">{intake.case.age ?? '?'}세 · {intake.case.sex ?? '?'} · 보고자 {intake.case.occp_cod ?? '?'}</span>
                <span className={`chip ${intake.case.outcomes.length ? 'bad' : 'ok'}`}>{intake.case.outcomes.length ? `중대: ${intake.case.outcomes.join(', ')}` : '중대성 해당 없음'}</span>
              </div>
            </Card>
          )}

          {caus && (
            <Card title={<>3. 한국형 인과성 평가 알고리즘 ver 2.0 <span className="chip jev" style={{ marginLeft: 8 }}>비자기회귀 판단 {fmt.ms(caus.latency_ms)} · 7문항 + WHO-UMC 1회 호출</span></>}
              sub="7개 항목 선택은 비자기회귀 판단 모델이, '약물에 대해 알려진 정보'는 조회 규칙이, 점수 합산과 등급 구간은 규칙이 정합니다. 신뢰도 0.55 미만 항목과 '알려진 정보' 항목은 평가자 검토 대상으로 표시합니다">
              <table className="tbl">
                <thead><tr><th>항목</th><th>판단</th><th className="r">점수</th><th>근거</th><th className="r">신뢰도</th></tr></thead>
                <tbody>{caus.items.map((it) => (
                  <tr key={it.id}>
                    <td style={{ whiteSpace: 'nowrap' }}>{it.name}</td>
                    <td>
                      {it.label}{it.needs_review && <span className="chip warn" style={{ marginLeft: 6, fontSize: 9.5 }}>검토 필요</span>}
                      {it.method === 'rule' && it.mfds_checked === false && <span className="chip warn" style={{ marginLeft: 6, fontSize: 9.5 }}>식약처 허가사항 미확인</span>}
                      {it.scope && <div className="dim" style={{ fontSize: 10.5, marginTop: 3 }}>평가 반응 {it.reaction ?? '—'} · {it.scope}</div>}
                    </td>
                    <td className="r num" style={{ color: it.score > 0 ? 'var(--ok)' : it.score < 0 ? 'var(--bad)' : 'var(--text-3)' }}>{it.score > 0 ? `+${it.score}` : it.score}</td>
                    <td>{it.source === 'jev' ? <span className="chip jev" style={{ fontSize: 9.5 }}>판단 모델</span> : <span className={`chip ${it.lookup_failed ? 'warn' : 'ev'}`} title={it.evidence.join('\n')}>{it.source}</span>}</td>
                    <td className="r" style={{ width: 120 }}>{it.method === 'rule'
                      ? <span className="dim mono" style={{ fontSize: 10.5 }}>{it.lookup_failed ? '조회 실패' : '규칙'}</span>
                      : <ProbBar p={it.confidence} color={it.needs_review ? 'var(--warn)' : 'var(--jev)'} />}</td>
                  </tr>
                ))}</tbody>
              </table>
              <div className="grid g2" style={{ marginTop: 14, gap: 12 }}>
                <div style={{ padding: 16, borderRadius: 14, border: `1px solid ${GRADE_COLOR[caus.grade]}88`, background: `color-mix(in srgb, ${GRADE_COLOR[caus.grade]} 10%, transparent)` }}>
                  <div className="eyebrow" style={{ color: GRADE_COLOR[caus.grade] }}>한국형 알고리즘 ver 2.0</div>
                  <div className="row" style={{ gap: 12, marginTop: 6 }}>
                    <span className="num" style={{ fontSize: 34 }}>{caus.total}</span>
                    <div><b style={{ fontSize: 18, fontFamily: 'var(--font-kr)' }}>{caus.grade}</b><div className="dim" style={{ fontSize: 11.5 }}>{caus.band} · {caus.approx} · 범위 {caus.min}~{caus.max}점</div></div>
                  </div>
                  <div className="pbar" style={{ marginTop: 10 }}><i style={{ width: `${((caus.total - caus.min) / (caus.max - caus.min)) * 100}%`, background: GRADE_COLOR[caus.grade] }} /></div>
                </div>
                <div style={{ padding: 16, borderRadius: 14, border: '1px solid var(--line-2)' }}>
                  <div className="eyebrow" style={{ color: 'var(--text-2)' }}>WHO-UMC (별도 체계)</div>
                  <div className="row" style={{ gap: 10, marginTop: 6 }}><b style={{ fontSize: 18, fontFamily: 'var(--font-kr)' }}>{WHO_KR[caus.who_umc.choice] ?? caus.who_umc.choice}</b><span className="chip">conf {caus.who_umc.confidence.toFixed(2)}</span></div>
                  <div className="note" style={{ marginTop: 8 }}>{caus.note}</div>
                </div>
              </div>
              <div className="note" style={{ marginTop: 10 }}>
                <b>허가사항 확인:</b> {!caus.label?.found && <>FDA 허가 라벨(openFDA drug/label)에서 이 성분을 찾지 못했습니다(국내 개발 신약 등). </>}
                '약물에 대해 알려진 정보' 점수는 FDA 허가 라벨(openFDA drug/label)과 PubMed 증례보고 검색 결과로만 정했습니다(라벨 기재 +3, 라벨에 없고 증례보고 있음 +2, 둘 다 없음 0).
                국내 평가 기준인 식약처 허가사항(의약품안전나라 사용상의 주의사항)은 자동으로 확인하지 않았습니다. 평가자가 확인하신 뒤 점수를 확정해 주세요. 식약처 허가사항에 기재되어 있으면 +3입니다.
                {caus.mfds_label?.search_url && <> <a href={caus.mfds_label.search_url} target="_blank" rel="noreferrer">의약품안전나라에서 검색</a></>}
                {caus.literature?.case_reports_rule?.length ? (
                  <div style={{ marginTop: 6 }}>PubMed 증례보고: {caus.literature.case_reports_rule.map((id, i) => (
                    <span key={id}>{i ? ', ' : ''}<a href={`https://pubmed.ncbi.nlm.nih.gov/${id}/`} target="_blank" rel="noreferrer">PMID {id}</a></span>
                  ))}</div>
                ) : null}
              </div>
            </Card>
          )}

          {tri.KR && tri.US && (
            <Card title="4. 규정 모드 비교 · 같은 판단, 다른 신속보고 규칙" sub="미국은 '중대하고 예상하지 못한' 사례, 한국은 중대한 약물이상반응(인과관계를 배제할 수 없는 반응)이 15일 신속보고 대상입니다 (별표 4의3 제7호 나목)">
              <div className="grid g2" style={{ gap: 12 }}>
                {(['KR', 'US'] as const).map((r) => {
                  const d = tri[r].decision, m = ACTION_META[d.action] ?? ACTION_META.monitor
                  return (
                    <div key={r} style={{ padding: 14, borderRadius: 14, border: `1px solid ${m.color}66`, background: `color-mix(in srgb, ${m.color} 8%, transparent)` }}>
                      <div className="row between"><span className="eyebrow" style={{ color: m.color }}>{r === 'KR' ? '한국 식약처' : '미국 FDA'}</span><span className="chip">반사 판단 {fmt.ms(tri[r].jev.latency_ms)}</span></div>
                      <b style={{ fontFamily: 'var(--font-kr)', fontSize: 17, display: 'block', marginTop: 6 }}>{m.label}</b>
                      {d.deadline && <div className={`chip ${d.report15 ? 'bad' : 'warn'}`} style={{ marginTop: 8, whiteSpace: 'normal' }}>{d.deadline}</div>}
                      <ul style={{ margin: '8px 0 0', paddingLeft: 16 }}>{d.reasons.map((x) => <li key={x} className="mono" style={{ fontSize: 11 }}>{x}</li>)}</ul>
                    </div>
                  )
                })}
              </div>
              <div className="note" style={{ marginTop: 10 }}>
                중대한 약물이상반응은 품목허가를 받은 자, 의약품도매상, 약국개설자, 의료기관개설자가 알게 된 날부터 15일 이내에 보고해야 합니다(별표 4의3 제7호 나목).
                약국·의료기관 개설자의 보고 의무는 중대한 사례에 한정되고(약사법 제68조의8 제2항), 비중대 사례는 자율 보고입니다.
                판단 모델이 WHO-UMC '가능성 적음(unlikely)'으로 본 중대 사례도 15일 대상에서 자동으로 빼지 않고 사람 확인(즉시 검토)으로 보냅니다. 보고자와 품목허가권자가 모두 관련 없다고 판단한 경우에만 약물이상반응에서 제외되기 때문입니다(별표 4의3 제1호 차목).
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
          <Card title="국내 약물감시 흐름" sub="팀 문서 「국내 PV 흐름 설명」 요약">
            <ol style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, lineHeight: 1.8, color: 'var(--text-2)' }}>
              <li><b>보고</b>: 품목허가를 받은 자(제약사) 의무, 중대한 약물이상반응은 의약품도매상·약국개설자·의료기관개설자도 15일 이내 보고 의무, 의사·약사·환자는 자율 (KAERS · 1644-6223)</li>
              <li><b>지역의약품안전센터 28곳</b>: 개별 사례 인과성 평가 (WHO-UMC, 한국형 알고리즘 ver 2.0)</li>
              <li><b>KIDS · KAERS</b>: 통계적 탐지(PRR·ROR·IC) + 사례 분석 + 허가정보·문헌 검토 → 실마리정보</li>
              <li><b>식약처</b>: 성분 단위 허가사항 변경 명령(3개월 내 반영), 안전성 서한, 회수</li>
              <li><b>공개·국제</b>: 실마리정보 알리미, WHO VigiBase</li>
            </ol>
            <div className="note" style={{ marginTop: 8 }}>FlyVigilance는 2단계(개별 평가)의 준비 작업과 3단계(신호 탐지)를 돕고, 판정과 보고는 평가자와 담당자가 합니다.</div>
          </Card>
        </div>
      </div>
    </div>
  )
}
