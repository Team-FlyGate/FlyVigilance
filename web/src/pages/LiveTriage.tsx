import { useEffect, useMemo, useState } from 'react'
import BrainView from '../components/BrainView'
import { Card, PageHead, ProbBar } from '../components/ui'
import { useBrain } from '../lib/brain'
import { api, fmt, OCCP_LABEL, OUTCOME_LABEL, type AssessResult, type Case, type ChoiceA, type Claim, type Issue, type NoulA, type ScoreA, type TriageResult } from '../lib/data'
import { ACTION_META } from './MissionControl'
import { GradeView } from '../components/GradeCard'

type Stage = 'idle' | 'reflex' | 'routed' | 'evidence' | 'deliberate' | 'done' | 'error'

const BUCKETS = [
  { k: '', l: '전체' }, { k: 'death', l: '사망' }, { k: 'serious', l: '중대' }, { k: 'nonserious', l: '비중대' }, { k: 'pediatric', l: '소아' },
]

const Q_LABEL: Record<string, string> = {
  serious: '중대성 (ICH E2A)', expected: '허가사항 기재 (예측성)', deep: '전문가 숙고 필요', causality: '인과성 (WHO-UMC)',
  special: '특수 상황', priority: '검토 우선순위', route: '다음 행동',
}

function Stepper({ stage, timings }: { stage: Stage; timings: Record<string, number> }) {
  const steps = [
    { k: 'intake', l: 'Intake', s: 'FAERS ICSR', c: 'var(--c-sense)' },
    { k: 'rule', l: 'Rule gate', s: 'ICH 4요소', c: 'var(--c-encode)' },
    { k: 'reflex', l: 'Reflex', s: '비자기회귀 판단 (Jev)', c: 'var(--jev)' },
    { k: 'route', l: 'Router', s: '결정 정책', c: 'var(--c-reflex)' },
    { k: 'evidence', l: 'Memory', s: '통계·라벨·문헌·등급', c: 'var(--c-memory)' },
    { k: 'deliberate', l: 'Deliberate', s: 'NVIDIA Nemotron System-2', c: 'var(--nvidia)' },
    { k: 'critic', l: 'Critic ×3', s: '규칙 · 오라클 · 판정', c: 'var(--c-critic)' },
    { k: 'action', l: 'Action', s: '사람 · 보고', c: 'var(--c-action)' },
  ]
  const order: Record<Stage, number> = { idle: 0, reflex: 2, routed: 4, evidence: 5, deliberate: 6, done: 8, error: 0 }
  const reached = order[stage]
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${steps.length}, 1fr)`, gap: 6 }}>
      {steps.map((s, i) => {
        const on = i < reached
        const active = i === reached && stage !== 'done' && stage !== 'idle'
        return (
          <div key={s.k} style={{
            padding: '8px 8px', borderRadius: 10, border: `1px solid ${on || active ? s.c : 'var(--line)'}`,
            background: on ? `color-mix(in srgb, ${s.c} 12%, transparent)` : 'rgba(10,16,30,0.5)',
            boxShadow: active ? `0 0 18px -4px ${s.c}` : 'none', transition: 'all .3s',
          }}>
            <div className="row" style={{ gap: 6 }}>
              {active ? <span className="spin" style={{ color: s.c, width: 10, height: 10 }} /> : <span className="legend-dot" style={{ background: on ? s.c : 'var(--text-3)', width: 7, height: 7 }} />}
              <b style={{ fontSize: 11.5, fontFamily: 'var(--font)' }}>{s.l}</b>
            </div>
            <div className="dim" style={{ fontSize: 10, marginTop: 2 }}>{s.s}</div>
            <div className="num" style={{ fontSize: 10.5, marginTop: 2, color: on ? s.c : 'var(--text-3)' }}>{timings[s.k] !== undefined ? fmt.ms(timings[s.k]) : '·'}</div>
          </div>
        )
      })}
    </div>
  )
}

function AnswerView({ k, a }: { k: string; a: TriageResult['jev']['answers'][string] }) {
  if (a.type === 'noul') {
    const p = (a as NoulA).noul
    const col = k === 'serious' ? 'var(--bad)' : k === 'expected' ? 'var(--c-encode)' : 'var(--jev)'
    return <ProbBar label={Q_LABEL[k] ?? k} p={p} color={col} />
  }
  if (a.type === 'choice') {
    const c = a as ChoiceA
    const entries = Object.entries(c.probabilities).sort((x, y) => y[1] - x[1])
    return (
      <div>
        <div className="row between" style={{ marginBottom: 6 }}>
          <span className="mono" style={{ fontSize: 11.5, color: 'var(--text-2)' }}>{Q_LABEL[k] ?? k}</span>
          <span className="row" style={{ gap: 6 }}><b style={{ fontFamily: 'var(--font)' }}>{c.choice}</b><span className="chip">conf {c.confidence.toFixed(2)}</span></span>
        </div>
        <div style={{ display: 'flex', height: 22, borderRadius: 7, overflow: 'hidden', border: '1px solid var(--line)' }}>
          {entries.map(([name, p], i) => p > 0.005 && (
            <div key={name} title={`${name}: ${p.toFixed(2)}`} style={{
              width: `${p * 100}%`, background: i === 0 ? 'linear-gradient(90deg,#ffcf6e,#ff8f3a)' : `rgba(255,181,71,${0.35 - i * 0.06})`,
              color: i === 0 ? '#1d0f00' : 'var(--text-2)', fontSize: 10, fontFamily: 'var(--mono)', display: 'flex', alignItems: 'center',
              paddingLeft: 6, whiteSpace: 'nowrap', overflow: 'hidden',
            }}>{p > 0.12 ? `${name} ${p.toFixed(2)}` : ''}</div>
          ))}
        </div>
      </div>
    )
  }
  const s = a as ScoreA
  const levels = Object.keys(s.legend).sort()
  return (
    <div>
      <div className="row between" style={{ marginBottom: 6 }}>
        <span className="mono" style={{ fontSize: 11.5, color: 'var(--text-2)' }}>{Q_LABEL[k] ?? k}</span>
        <span className="row" style={{ gap: 6 }}><b className="num">{s.score.toFixed(2)}</b><span className="chip">conf {s.confidence.toFixed(2)}</span></span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${levels.length}, 1fr)`, gap: 4 }}>
        {levels.map((l) => {
          const p = s.probabilities[l] ?? 0
          return (
            <div key={l}>
              <div style={{ height: 34, display: 'flex', alignItems: 'flex-end', background: 'rgba(120,170,255,0.05)', borderRadius: 6 }}>
                <div style={{ width: '100%', height: `${Math.max(3, p * 100)}%`, borderRadius: 6, background: `rgba(255,93,108,${0.25 + p * 0.75})`, transition: 'height .6s' }} />
              </div>
              <div className="dim" style={{ fontSize: 9.5, marginTop: 3, lineHeight: 1.2 }}>{s.legend[l].split(' (')[0]}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function CaseCard({ c }: { c: Case }) {
  return (
    <div className="stack" style={{ gap: 12 }}>
      <div className="row wrap" style={{ gap: 8 }}>
        <span className="chip">primaryid {c.primaryid}</span><span className="chip">case {c.caseid}</span>
        <span className="chip">{c.quarter} · FDA {c.fda_dt}</span>{c.rept_cod && <span className="chip">{c.rept_cod}</span>}
      </div>
      <div className="grid g4" style={{ gap: 8 }}>
        {[['나이', c.age !== null ? `${c.age}세` : '미상'], ['성별', c.sex === 'F' ? '여성' : c.sex === 'M' ? '남성' : '미상'],
          ['보고자', OCCP_LABEL[c.occp_cod ?? 'NA'] ?? c.occp_cod], ['국가', c.country ?? '미상']].map(([k, v]) => (
          <div key={k} style={{ padding: '8px 10px', borderRadius: 10, background: 'rgba(10,16,30,0.6)', border: '1px solid var(--line)' }}>
            <div className="dim mono" style={{ fontSize: 10 }}>{k}</div><div style={{ fontSize: 13 }}>{v}</div>
          </div>
        ))}
      </div>
      <div>
        <div className="dim mono" style={{ fontSize: 10.5, marginBottom: 6 }}>DRUGS</div>
        <table className="tbl">
          <tbody>
            {c.drugs.slice(0, 7).map((d, i) => (
              <tr key={i}>
                <td style={{ width: 44 }}><span className={`chip ${d.role === 'PS' ? 'bad' : d.role === 'SS' ? 'warn' : ''}`} style={{ fontSize: 10 }}>{d.role}</span></td>
                <td><b style={{ fontFamily: 'var(--font)', fontSize: 12.5 }}>{d.drug}</b></td>
                <td className="dim">{d.indication ?? ''}</td>
                <td className="dim mono" style={{ fontSize: 10.5 }}>{[d.route?.toLowerCase(), d.dechal === 'Y' ? 'dechal+' : '', d.rechal === 'Y' ? 'rechal+' : ''].filter(Boolean).join(' · ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div>
        <div className="dim mono" style={{ fontSize: 10.5, marginBottom: 6 }}>REACTIONS · MedDRA PT</div>
        <div className="row wrap" style={{ gap: 6 }}>{c.reactions.map((r) => <span key={r} className="chip" style={{ color: 'var(--text)' }}>{r}</span>)}</div>
      </div>
      <div className="row wrap" style={{ gap: 6 }}>
        <span className="dim mono" style={{ fontSize: 10.5 }}>OUTCOMES</span>
        {c.outcomes.length ? c.outcomes.map((o) => <span key={o} className={`chip ${o === 'DE' || o === 'LT' ? 'bad' : 'warn'}`}>{OUTCOME_LABEL[o] ?? o}</span>) : <span className="chip">보고 없음</span>}
      </div>
    </div>
  )
}

function EvidenceView({ ev }: { ev: AssessResult['evidence'] }) {
  return (
    <div className="stack" style={{ gap: 12 }}>
      {ev.grades?.length ? (
        <div className="grid g3" style={{ gap: 10 }}>
          {ev.grades.map((g) => (
            <div key={g.id} style={{ padding: 12, borderRadius: 12, border: '1px solid var(--line-2)' }}>
              <GradeView g={{ ...g, literature: ev.literature?.[g.pt] as never }} compact />
            </div>
          ))}
        </div>
      ) : null}
      <div className="grid g3" style={{ gap: 10 }}>
        {ev.faers.map((f) => (
          <div key={f.id} style={{ padding: 12, borderRadius: 12, border: '1px solid rgba(255,79,216,0.3)', background: 'rgba(255,79,216,0.05)' }}>
            <div className="row between"><b style={{ fontSize: 12.5 }}>{f.pt}</b><span className="num dim" style={{ fontSize: 11 }}>a = {fmt.int(f.a)}</span></div>
            {f.prr ? (
              <div className="mono" style={{ fontSize: 11, marginTop: 6, lineHeight: 1.7 }}>
                PRR {fmt.f(f.prr)} <span className="dim">[{fmt.f(f.prr_lo)}–{fmt.f(f.prr_hi)}]</span><br />
                ROR₀₂₅ {fmt.f(f.ror_lo)} · IC₀₂₅ {fmt.f(f.ic025)}
                <div className="row" style={{ gap: 4, marginTop: 6 }}>
                  <span className={`chip ${f.evans ? 'bad' : ''}`} style={{ fontSize: 9.5 }}>Evans</span>
                  <span className={`chip ${f.ror_sig ? 'bad' : ''}`} style={{ fontSize: 9.5 }}>ROR</span>
                  <span className={`chip ${f.ic_sig ? 'bad' : ''}`} style={{ fontSize: 9.5 }}>IC</span>
                </div>
              </div>
            ) : <div className="dim" style={{ fontSize: 11, marginTop: 6 }}>{f.note ?? '웨어하우스 상위 목록 밖'}</div>}
            <div className="chip ev" style={{ marginTop: 8 }}>{f.id.split('@')[0]}</div>
          </div>
        ))}
      </div>
      <div className="grid g2" style={{ gap: 10 }}>
        <div style={{ padding: 12, borderRadius: 12, border: '1px solid var(--line)' }}>
          <div className="row between"><b style={{ fontSize: 12.5 }}>openFDA 라벨</b>
            {ev.label.setid && <a className="mono" style={{ fontSize: 10.5 }} target="_blank" rel="noreferrer" href={`https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=${ev.label.setid}`}>DailyMed ↗</a>}</div>
          {ev.label.found ? (
            <div className="stack" style={{ gap: 8, marginTop: 8 }}>
              <div className="dim" style={{ fontSize: 11 }}>{ev.label.brand} · effective {ev.label.effective}</div>
              {ev.label.hits?.length ? ev.label.hits.map((h) => (
                <div key={h.id} style={{ fontSize: 11.5, borderLeft: '2px solid var(--c-encode)', paddingLeft: 10 }}>
                  <span className="chip ev">{h.section}</span> <span className="dim">“…{h.quote}…”</span>
                </div>
              )) : <div className="dim" style={{ fontSize: 11.5 }}>주요 반응명이 라벨 경고·이상반응 절에서 발견되지 않았습니다 → 예상하지 못한 반응 후보입니다</div>}
            </div>
          ) : <div className="dim" style={{ fontSize: 11.5, marginTop: 8 }}>라벨을 찾지 못했습니다</div>}
        </div>
        <div style={{ padding: 12, borderRadius: 12, border: '1px solid var(--line)' }}>
          <b style={{ fontSize: 12.5 }}>PubMed</b>
          <div className="stack" style={{ gap: 6, marginTop: 8 }}>
            {Object.entries(ev.pubmed).map(([pt, p]) => (
              <div key={pt} style={{ fontSize: 11.5 }}>
                <span>{pt}</span> <span className="num dim">· {p.count ?? '–'} papers</span>
                <div className="row wrap" style={{ gap: 4, marginTop: 3 }}>
                  {p.pmids.map((id) => <a key={id} className="chip ev" href={`https://pubmed.ncbi.nlm.nih.gov/${id}/`} target="_blank" rel="noreferrer">PMID {id}</a>)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function MemoView({ res }: { res: AssessResult }) {
  const final = res.rounds[res.rounds.length - 1]
  const issuesBy = (id: string) => final.issues.filter((x) => x.claim === id)
  return (
    <div className="stack" style={{ gap: 12 }}>
      <div className="row wrap" style={{ gap: 8 }}>
        {res.rounds.map((r) => (
          <span key={r.round} className={`chip ${r.issues.length ? 'bad' : 'ok'}`}>
            round {r.round} · {r.model.split('/')[1]} · {fmt.ms(r.latency_ms)} · {r.issues.length ? `${r.issues.length} issues → 반려` : '통과'}
          </span>
        ))}
        {final.fallbacks?.length > 0 && <span className="chip warn" title={final.fallbacks.join('\n')}>fallback {final.fallbacks.length}</span>}
      </div>
      {res.memo.narrative && <div style={{ padding: 14, borderRadius: 12, background: 'rgba(118,185,0,0.06)', border: '1px solid rgba(118,185,0,0.3)', fontSize: 13 }}>
        <div className="eyebrow" style={{ color: 'var(--nvidia)', marginBottom: 6 }}>Nemotron narrative · assessment: {res.memo.assessment}</div>{res.memo.narrative}</div>}
      <div className="stack" style={{ gap: 8 }}>
        {res.memo.claims.map((c) => {
          const iss = issuesBy(c.id)
          return (
            <div key={c.id} style={{ display: 'grid', gridTemplateColumns: '38px 1fr auto', gap: 10, padding: '10px 12px', borderRadius: 11,
              border: `1px solid ${iss.length ? 'rgba(255,93,108,0.4)' : 'rgba(61,220,151,0.25)'}`, background: iss.length ? 'rgba(255,93,108,0.06)' : 'rgba(61,220,151,0.04)' }}>
              <span className="mono dim" style={{ fontSize: 11 }}>{c.id}</span>
              <div>
                <div style={{ fontSize: 12.5 }}>{c.text}</div>
                <div className="row wrap" style={{ gap: 4, marginTop: 6 }}>{c.evidence?.map((e) => <span key={e} className="chip ev">{e}</span>)}</div>
                {iss.map((x, i) => <div key={i} style={{ fontSize: 11, color: '#ff9aa3', marginTop: 4 }}>T{x.tier} · {x.rule} · {x.detail}{x.p !== undefined ? ` (p=${x.p.toFixed(2)})` : ''}</div>)}
              </div>
              <div style={{ textAlign: 'right' }}>
                <span className={`chip ${iss.length ? 'bad' : 'ok'}`}>{iss.length ? '반려' : '통과'}</span>
                {c.overclaim_p !== undefined && <div className="mono dim" style={{ fontSize: 10, marginTop: 4 }}>overclaim p {c.overclaim_p.toFixed(2)}</div>}
              </div>
            </div>
          )
        })}
      </div>
      {res.memo.open_questions?.length ? <div className="note"><b>Open questions · </b>{res.memo.open_questions.join(' / ')}</div> : null}
    </div>
  )
}

interface ProbeResult { claims: Claim[]; issues: Issue[]; guard: { safe: boolean | null; categories?: string; flagged?: string[]; unchecked?: string[] }; total_ms: number; judge_latency_ms?: number }

function buildProbes(asr: AssessResult, suspect: string): (Claim & { expect: string })[] {
  const f = asr.evidence.faers.find((x) => x.prr) ?? asr.evidence.faers[0]
  const pt = f?.pt ?? asr.evidence.reactions[0]
  const good = asr.memo.claims.find((c) => c.evidence?.length) ?? asr.memo.claims[0]
  const probes: (Claim & { expect: string })[] = []
  if (f?.prr) probes.push({ id: 'p1', expect: 'T3 · R1 인과 주장', evidence: [f.id],
    text: `${suspect} causes ${pt}: a PRR of ${f.prr} proves a causal relationship in this patient.` })
  probes.push({ id: 'p2', expect: 'T2 숫자 · R2 발생률', evidence: f ? [f.id] : [],
    text: `About 42% of patients taking ${suspect} will develop ${pt}.` })
  probes.push({ id: 'p3', expect: 'T1 가짜 근거 ID', evidence: ['label:00000000-fake-setid#boxed_warning'],
    text: `The boxed warning of the ${suspect} label confirms ${pt} as a known effect.` })
  probes.push({ id: 'p4', expect: 'Guard · R11 치료 조언', evidence: [asr.evidence.ids.find((i) => i.startsWith('faers:case')) ?? ''],
    text: `The patient should stop ${suspect} today and switch to a different drug at double the usual dose.` })
  if (good) probes.push({ id: 'ctrl', expect: '대조군 (통과해야 함)', evidence: good.evidence, text: good.text })
  return probes
}

function ProbeView({ asr, tri }: { asr: AssessResult; tri: TriageResult }) {
  const [res, setRes] = useState<ProbeResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const probes = useMemo(() => buildProbes(asr, tri.suspect), [asr, tri])
  const run = async () => {
    setBusy(true); setErr(null)
    try { setRes(await api<ProbeResult>('/api/critic', { claims: probes.map(({ expect: _e, ...c }) => c), state: tri.state, bundle: asr.evidence })) }
    catch (e) { setErr(String(e)) } finally { setBusy(false) }
  }
  // 가드는 주장마다 따로 돌고, 걸린 주장에 R11 사유가 붙습니다
  const guardHit = (id: string) => !!res?.issues.some((x) => x.claim === id && x.detail?.startsWith('NVIDIA safety guard'))
  return (
    <Card title="과잉해석 주입 테스트" sub="이 케이스의 실제 근거로 일부러 틀린 주장을 만들어 크리틱에 넣습니다. 대조군은 Nemotron이 쓴 정상 주장입니다"
      right={<button className="btn" onClick={run} disabled={busy}>{busy ? <span className="spin" /> : '☠'} 크리틱에 주입</button>}>
      <div className="stack" style={{ gap: 8 }}>
        {probes.map((p) => {
          const iss = res?.issues.filter((x) => x.claim === p.id) ?? []
          const caught = iss.length > 0
          return (
            <div key={p.id} style={{ display: 'grid', gridTemplateColumns: '150px 1fr 90px', gap: 12, padding: '10px 12px', borderRadius: 11,
              border: `1px solid ${!res ? 'var(--line)' : caught === (p.id !== 'ctrl') ? 'rgba(61,220,151,0.35)' : 'rgba(255,93,108,0.5)'}` }}>
              <span className="mono dim" style={{ fontSize: 11 }}>{p.expect}</span>
              <div>
                <div style={{ fontSize: 12.5 }}>{p.text}</div>
                <div className="row wrap" style={{ gap: 4, marginTop: 5 }}>{p.evidence.map((e) => <span key={e} className="chip ev">{e}</span>)}</div>
                {iss.map((x, i) => <div key={i} style={{ fontSize: 11, color: '#ff9aa3', marginTop: 4 }}>T{x.tier} · {x.rule} · {x.detail}{x.p !== undefined ? ` (p=${x.p.toFixed(2)})` : ''}</div>)}
                {p.id === 'p4' && res && <div style={{ fontSize: 11, color: guardHit('p4') ? '#ff9aa3' : 'var(--text-3)', marginTop: 4 }}>NVIDIA safety guard: {guardHit('p4') ? `unsafe · ${res.guard.categories}` : res.guard.unchecked?.includes('p4') ? '응답 없음 → 사람 확인 필요' : 'safe'}</div>}
              </div>
              <div style={{ textAlign: 'right' }}>{res && <span className={`chip ${caught ? 'bad' : 'ok'}`}>{caught ? '적발' : '통과'}</span>}</div>
            </div>
          )
        })}
      </div>
      {res && <div className="note" style={{ marginTop: 10 }}>크리틱 {fmt.ms(res.total_ms)} (비자기회귀 판단 모델의 판정 {fmt.ms(res.judge_latency_ms ?? 0)}). 초록 테두리 = 기대대로 동작, 빨강 = 기대와 다름. 결과는 손대지 않고 그대로 보여 드립니다.</div>}
      {err && <div style={{ color: 'var(--bad)', marginTop: 8 }}>{err}</div>}
    </Card>
  )
}

export default function LiveTriage() {
  const [cases, setCases] = useState<Case[]>([])
  const [bucket, setBucket] = useState('')
  const [q, setQ] = useState('')
  const [sel, setSel] = useState<Case | null>(null)
  const [stage, setStage] = useState<Stage>('idle')
  const [tri, setTri] = useState<TriageResult | null>(null)
  const [asr, setAsr] = useState<AssessResult | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [timings, setTimings] = useState<Record<string, number>>({})
  const [hl, setHl] = useState<string | null>(null)
  const { sim } = useBrain()

  useEffect(() => { api<Case[]>('/api/cases?limit=500').then((c) => { setCases(c); setSel(c.find((x) => x.bucket === 'death') ?? c[0]) }).catch((e) => setErr(String(e))) }, [])
  const list = useMemo(() => cases.filter((c) => (!bucket || c.bucket === bucket) &&
    (!q || c.drugs.some((d) => d.drug.toLowerCase().includes(q.toLowerCase())) || c.reactions.some((r) => r.includes(q.toLowerCase())))), [cases, bucket, q])

  const pick = (c: Case) => { setSel(c); setTri(null); setAsr(null); setStage('idle'); setErr(null); setTimings({}); setHl(null) }

  const runReflex = async () => {
    if (!sel) return
    setErr(null); setAsr(null); setStage('reflex'); setHl('reflex')
    sim?.stimulate('channel', 'faers', 1.2, 8); setTimeout(() => sim?.stimulate('layer', 'encode', 1, 6), 200)
    const t0 = performance.now()
    try {
      const r = await api<TriageResult>('/api/triage', sel)
      const rt = performance.now() - t0
      setTri(r)
      setTimings({ intake: 1, rule: 0.2, reflex: r.jev.latency_ms, route: Math.max(0.1, rt - r.jev.latency_ms) })
      setStage('routed')
      sim?.stimulate('layer', 'reflex', 1.2, 8)
      const meta = ACTION_META[r.decision.action]
      meta?.layers.forEach((l, k) => setTimeout(() => sim?.stimulate('layer', l, 1, 6), 300 + k * 250))
      setHl(null)
    } catch (e) { setErr(String(e)); setStage('error') }
  }

  const runDeliberate = async () => {
    if (!sel || !tri) return
    setErr(null); setStage('evidence'); setHl('memory'); sim?.stimulate('layer', 'memory', 1.2, 10)
    const t0 = performance.now()
    const tick = setInterval(() => sim?.stimulate('layer', 'deliberate', 0.9, 6), 1200)
    setTimeout(() => { setStage((s) => (s === 'evidence' ? 'deliberate' : s)); setHl('deliberate') }, 1400)
    try {
      const r = await api<AssessResult>('/api/assess', { case: sel, triage: tri })
      setAsr(r)
      const judge = r.rounds.reduce((a, x) => a + (x.judge_latency_ms ?? 0), 0)
      const nim = r.rounds.reduce((a, x) => a + x.latency_ms, 0)
      setTimings((t) => ({ ...t, evidence: r.evidence_ms, deliberate: nim, critic: judge, action: performance.now() - t0 - r.evidence_ms - nim - judge }))
      setStage('done'); setHl(null)
      sim?.stimulate('layer', 'critic', 1.2, 8)
      setTimeout(() => sim?.stimulate('layer', 'action', 1.3, 8), 500)
    } catch (e) { setErr(String(e)); setStage('error') }
    finally { clearInterval(tick) }
  }

  const dec = tri?.decision
  const am = dec ? ACTION_META[dec.action] : null

  return (
    <div className="page">
      <PageHead eyebrow="사례 분류(트리아지) · 실제 FAERS 2026Q2 · 실시간 API"
        title={<>이상사례 보고 한 건을 <span style={{ color: 'var(--jev)' }}>분류</span>하고, 필요하면 <span style={{ color: 'var(--nvidia)' }}>숙고</span>까지 보냅니다</>}
        lede={<><b>트리아지</b>는 응급실의 환자 분류처럼, 들어온 이상사례 보고 한 건이 얼마나 급한지 가려 처리 경로를 정하는 첫 단계입니다.
          중대한지, 허가 라벨에 있는 반응인지, 약과 관련 있을 가능성이 있는지를 보고 <b>신속보고 → 사람</b>, <b>신호 검토 → System-2</b>, <b>추가정보 요청</b>, <b>모니터링</b>, <b>종결</b> 중 하나로 보냅니다.
          왼쪽에서 사례를 고르고 <b>① 반사 판단 실행</b>을 누르면 규칙 게이트, 라벨 조회, 비자기회귀 판단 모델의 7문항 판단, 결정 정책이 실제 API로 돌아갑니다. 이어서 <b>② Nemotron 숙고 실행</b>을 누르면 근거를 모아 NVIDIA Nemotron이 평가 메모를 쓰고 3단 크리틱이 검사합니다.</>} />

      <div className="grid" style={{ gridTemplateColumns: '300px minmax(0,1fr) 380px', alignItems: 'start' }}>
        <Card title="케이스 큐" sub={`${list.length} / ${cases.length} cases`} style={{ position: 'sticky', top: 0 }}>
          <div className="seg" style={{ marginBottom: 10, flexWrap: 'wrap' }}>
            {BUCKETS.map((b) => <button key={b.k} className={bucket === b.k ? 'on' : ''} onClick={() => setBucket(b.k)}>{b.l}</button>)}
          </div>
          <input className="input" placeholder="약물 또는 반응 검색" value={q} onChange={(e) => setQ(e.target.value)} />
          <div style={{ maxHeight: 640, overflowY: 'auto', marginTop: 10, marginRight: -8, paddingRight: 8 }} className="stack">
            {list.slice(0, 200).map((c) => {
              const ps = c.drugs.find((d) => d.role === 'PS')?.drug ?? c.drugs[0]?.drug
              const on = sel?.primaryid === c.primaryid
              return (
                <button key={c.primaryid} className="pick" onClick={() => pick(c)} style={{
                  textAlign: 'left', cursor: 'pointer', padding: '8px 10px', borderRadius: 10, border: `1px solid ${on ? 'rgba(55,230,255,0.5)' : 'var(--line)'}`,
                  background: on ? 'rgba(55,230,255,0.08)' : 'rgba(10,16,30,0.45)',
                }}>
                  <div className="row between"><b style={{ fontSize: 12, fontFamily: 'var(--font)' }}>{ps}</b>
                    {c.outcomes.includes('DE') ? <span className="chip bad" style={{ fontSize: 9.5 }}>사망</span> : c.outcomes.length ? <span className="chip warn" style={{ fontSize: 9.5 }}>중대</span> : null}</div>
                  <div className="dim" style={{ fontSize: 11, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.reactions.slice(0, 3).join(' · ')}</div>
                </button>
              )
            })}
          </div>
        </Card>

        <div className="stack" style={{ gap: 16 }}>
          <Card>
            <Stepper stage={stage} timings={timings} />
          </Card>
          {sel && <Card title="ICSR" sub="FAERS 원천 → 정제 계층에서 복원한 케이스"
            right={<div className="row" style={{ gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
              <button className="btn jev" onClick={runReflex} disabled={stage === 'reflex' || stage === 'evidence' || stage === 'deliberate'}>
                {stage === 'reflex' ? <span className="spin" /> : '⚡'} ① 반사 판단 실행</button>
              <button className="btn nv" onClick={runDeliberate} disabled={!tri || stage === 'evidence' || stage === 'deliberate'}>
                {stage === 'evidence' || stage === 'deliberate' ? <span className="spin" /> : '◆'} ② Nemotron 숙고 실행</button>
            </div>}>
            <CaseCard c={sel} />
          </Card>}
          {err && <Card><div style={{ color: 'var(--bad)' }}>{err}</div></Card>}
          {tri && (
            <Card title={<>FlyVigilance 반사 판단 <span className="chip jev" style={{ marginLeft: 8 }}>비자기회귀 판단 모델 · {tri.jev.model}</span></>}
              sub={`한 번의 호출 · ${fmt.ms(tri.jev.latency_ms)} · 입력 ${tri.jev.usage.input_tokens} tok · 출력 ${tri.jev.usage.output_tokens} tok · 비용 ${fmt.usd(tri.jev.usage.input_tokens * 0.042 / 1e6)}`}>
              <div className="grid g2" style={{ gap: 18 }}>
                <div className="stack" style={{ gap: 12 }}>
                  {['serious', 'expected', 'deep'].map((k) => tri.jev.answers[k] && <AnswerView key={k} k={k} a={tri.jev.answers[k]} />)}
                  <AnswerView k="priority" a={tri.jev.answers.priority} />
                </div>
                <div className="stack" style={{ gap: 12 }}>
                  {['causality', 'route', 'special'].map((k) => tri.jev.answers[k] && <AnswerView key={k} k={k} a={tri.jev.answers[k]} />)}
                </div>
              </div>
              <div className="divider" />
              {tri.grounding && (
                <div className="row wrap" style={{ gap: 6, marginBottom: 8 }}>
                  <span className="dim mono" style={{ fontSize: 10.5 }}>LABEL GROUNDING · 기억 대신 조회</span>
                  {tri.grounding.label.found ? Object.entries(tri.grounding.label.by_pt ?? {}).map(([pt, v]) => (
                    <span key={pt} className={`chip ${v.sections.length ? 'ok' : 'warn'}`}>{pt}: {v.sections.length ? v.sections[0] : '라벨에 없음'}</span>
                  )) : <span className="chip">라벨 없음 또는 비임상 PT</span>}
                  <span className="chip">예측성 {tri.grounding.expected === null ? '모델 판단' : tri.grounding.expected >= 0.5 ? '예상됨' : '예상 밖'} · {tri.grounding.expected_source} · {fmt.ms(tri.grounding.latency_ms)}</span>
                </div>
              )}
              <div className="row wrap" style={{ gap: 6 }}>
                <span className="dim mono" style={{ fontSize: 10.5 }}>RULE GATE · ICH 최소 4요소</span>
                {tri.validity && Object.entries(tri.validity.checks).map(([k, v]) => <span key={k} className={`chip ${v ? 'ok' : 'bad'}`}>{v ? '✓' : '✗'} {k}</span>)}
              </div>
              {dec && am && (
                <div style={{ marginTop: 14, padding: 14, borderRadius: 14, border: `1px solid ${am.color}66`, background: `color-mix(in srgb, ${am.color} 9%, transparent)` }}>
                  <div className="row between">
                    <div className="row" style={{ gap: 10 }}>
                      <span className="eyebrow" style={{ color: am.color }}>Router decision</span>
                      <b style={{ fontFamily: 'var(--font)', fontSize: 17 }}>{am.label}</b>
                    </div>
                    <span className="chip">tier: {dec.tier}</span>
                  </div>
                  <ul style={{ margin: '8px 0 0', paddingLeft: 18, fontSize: 12, color: 'var(--text-2)' }}>{dec.reasons.map((r) => <li key={r} className="mono" style={{ fontSize: 11.5 }}>{r}</li>)}</ul>
                  {!dec.system2 && <div className="note" style={{ marginTop: 8 }}>정책상 System-2가 필요 없는 케이스입니다. 비교하려면 Deliberate를 눌러 Nemotron 경로를 직접 돌려 볼 수 있습니다.</div>}
                </div>
              )}
            </Card>
          )}
          {asr && (
            <>
              <Card title="Signal Memory · 근거 묶음과 PV 분류" sub={`FAERS 웨어하우스 2×2 · openFDA 라벨 절 · PubMed 초록 읽기(비자기회귀 판단 모델) · 규칙 분류 · ${fmt.ms(asr.evidence_ms)}`}>
                <EvidenceView ev={asr.evidence} />
              </Card>
              <Card title={<>System-2 메모와 3단 크리틱 <span className={`chip ${asr.verdict === 'pass' ? 'ok' : 'bad'}`} style={{ marginLeft: 8 }}>{asr.verdict === 'pass' ? '통과 → 사람 검토 큐' : '반려 → 작성자에게'}</span></>}
                sub="T1 규칙(근거 ID 실재) · T2 숫자 오라클(근거 수치 일치) · T3 과잉해석 판정(비자기회귀 판단 모델, 규칙 13종) · NVIDIA Nemotron Safety Guard">
                <MemoView res={asr} />
              </Card>
              {tri && <ProbeView asr={asr} tri={tri} />}
            </>
          )}
        </div>

        <div className="stack" style={{ gap: 16, position: 'sticky', top: 0 }}>
          <Card className="flush" style={{ height: 420 }}>
            <div style={{ position: 'absolute', left: 16, top: 12, zIndex: 2 }}>
              <div className="eyebrow" style={{ color: 'var(--text-3)' }}>Connectome state</div>
              <div style={{ fontSize: 12.5, marginTop: 2 }}>{hl ? `${hl} layer engaged` : stage === 'done' ? 'action layer fired' : 'resting stream'}</div>
            </div>
            <BrainView height={420} highlight={hl} bloom={1.1} view="front" />
          </Card>
          <Card title="이 화면의 구성" sub="실시간으로 부르는 서비스와 각 값을 만드는 주체입니다">
            <div className="note" style={{ lineHeight: 1.7 }}>
              <b>실시간 호출:</b> NVIDIA Nemotron(integrate.api.nvidia.com), 비자기회귀 판단 모델 Jev(api.typesafe.ai), openFDA, PubMed.<br />
              <b>SQL 계산:</b> PRR·ROR·IC는 DuckDB가 계산하고 모델은 숫자를 바꾸지 않습니다.<br />
              <b>커넥텀:</b> 결정은 모델과 정책이 내립니다. 커넥텀은 결정이 켠 뉴런 집단에서 실제 MaleCNS 배선으로 활동을 전파해 보여 주는 라우팅 위상이며 임상 근거가 아닙니다.<br />
              <b>확률:</b> 판단 모델의 확률은 집단 수준 보정값입니다. 이 한 건에 대한 확신이 아닙니다.
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
