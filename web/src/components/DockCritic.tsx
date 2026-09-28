import { useEffect, useState } from 'react'
import { api } from '../lib/data'
import { t } from '../lib/i18n'

// 직접 도킹 + 실시간 크리틱: 도킹이 끝나면 에이전트가 그 결과로 주장 5개를 쓰고(맞는 주장 1, 크리틱 1·2·3단에 걸릴 주장),
// /api/dock/critic 이 1단(근거 ID) · 2단(숫자 대조) 규칙과 3단 도킹 해석 규칙(D1–D5, Jev)으로 판정합니다.
// 사람이 주장을 직접 써서 넣어 볼 수도 있습니다.
// 서버의 키워드 판정(Jev 를 쓸 수 없을 때)이 한국어 표현을 보므로, 서버에는 늘 한국어 주장을 보내고 영어 화면에서는 id 로 영어 문장을 찾아 보여 줍니다. 판정은 모두 서버 응답 그대로이고, 서버가 없으면 판정을 지어내지 않습니다.

export interface CriticInput {
  drug: string; gene: string; pdb: string; target: string
  confidence: (number | null)[]; pocketDist: number | null; source: 'redock' | 'matrix' | 'live'
  other: { gene: string; conf: number } | null
}
interface Issue { claim: string; tier: number; rule: string; p: number | null; detail: string }
interface Resp { claims: { id: string; text: string; overclaim_p?: number }[]; issues: Issue[]; mode: 'jev' | 'rules'; judge_latency_ms?: number; total_ms: number }

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)
const tier = (n: number) => t(['', '1단 근거 ID', '2단 숫자 대조', '3단 추론'], ['', 'Tier 1 evidence ID', 'Tier 2 number check', 'Tier 3 reasoning'])[n]

export default function DockCritic({ input, targetKey }: { input: CriticInput; targetKey: string }) {
  const [res, setRes] = useState<Resp | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [mine, setMine] = useState('')
  const [busy, setBusy] = useState(false)
  const ev = `diffdock:${input.source}:${targetKey}|${input.drug}:pose:1`
  const c1 = input.confidence[0]
  const f = (v: number) => v.toFixed(2)
  const state = `${cap(input.drug)} docked to ${input.target} (${input.gene}, PDB ${input.pdb}) with DiffDock NIM. ` +
    `Pose confidences ${input.confidence.map((c) => (c === null ? 'NA' : f(c))).join(', ')}. ` +
    (input.pocketDist !== null ? `Pose 1 centroid ${f(input.pocketDist)} A from the crystal ligand site. ` : '') +
    (input.other ? `Same drug on ${input.other.gene}: pose 1 confidence ${f(input.other.conf)}.` : '')

  const agentClaims = () => {
    const out: { id: string; text: string; en: string; evidence: string[] }[] = []
    if (input.pocketDist !== null) out.push({ id: 'c1', text: `${cap(input.drug)} 의 1순위 포즈는 ${input.gene} 결합 자리 중심에서 ${f(input.pocketDist)} Å 떨어져 있다.`, en: `${cap(input.drug)}'s top pose is ${f(input.pocketDist)} Å from the center of the ${input.gene} binding site.`, evidence: [ev] })
    if (c1 !== null) out.push({ id: 'c2', text: `DiffDock 신뢰도가 ${f(c1)} 이므로 ${cap(input.drug)} 은(는) ${input.gene} 에 강하게 결합한다.`, en: `Because its DiffDock confidence is ${f(c1)}, ${cap(input.drug)} binds strongly to ${input.gene}.`, evidence: [ev] })
    if (c1 !== null && input.other) out.push({ id: 'c3', text: `${cap(input.drug)} 은(는) ${input.gene} 에서 신뢰도 ${f(c1)}, ${input.other.gene} 에서 ${f(input.other.conf)} 이므로 ${c1 >= input.other.conf ? input.gene : input.other.gene} 에 선택적이다.`, en: `${cap(input.drug)} has confidence ${f(c1)} on ${input.gene} and ${f(input.other.conf)} on ${input.other.gene}, so it is selective for ${c1 >= input.other.conf ? input.gene : input.other.gene}.`, evidence: [ev] })
    if (c1 !== null) out.push({ id: 'c4', text: `1순위 포즈 신뢰도는 ${f(c1 + 0.37)} 이다.`, en: `The top pose confidence is ${f(c1 + 0.37)}.`, evidence: [ev] })
    out.push({ id: 'c5', text: `${cap(input.drug)} 은(는) ${input.gene} 결합 자리에 들어간다.`, en: `${cap(input.drug)} fits into the ${input.gene} binding site.`, evidence: [`pdb:${input.pdb}:cocrystal-${input.drug}`] })
    return out
  }

  const [enText, setEnText] = useState<Record<string, string>>({})
  const judge = async (extra?: string) => {
    setBusy(true); setErr(null)
    const drafted = agentClaims()
    setEnText(Object.fromEntries(drafted.map((c) => [c.id, c.en])))
    const claims = drafted.map(({ id, text, evidence }) => ({ id, text, evidence }))
    if (extra?.trim()) claims.push({ id: 'me', text: extra.trim(), evidence: [ev] })
    try { setRes(await api<Resp>('/api/dock/critic', { claims, state, ids: [ev] })) } catch (e) { setErr(String(e instanceof Error ? e.message : e)); setRes(null) }
    setBusy(false)
  }
  useEffect(() => { void judge() }, [input.drug, targetKey]) // eslint-disable-line react-hooks/exhaustive-deps

  const issuesOf = (id: string) => res?.issues.filter((i) => i.claim === id) ?? []
  return (
    <div className="stack" style={{ gap: 8, marginTop: 14 }}>
      <div className="row between">
        <span className="mono" style={{ fontSize: 10.5, letterSpacing: 1.3, color: 'var(--bad)' }}>LIVE CRITIC · {t('에이전트가 쓴 주장 → 크리틱 3단', 'agent-written claims → 3-tier critic')}</span>
        <span className="mono dim" style={{ fontSize: 10.5 }}>
          {busy ? t('판정 중…', 'Judging…') : res ? `${res.mode === 'jev' ? t(`3단 Jev ${res.judge_latency_ms ?? '–'} ms`, `Tier 3 Jev ${res.judge_latency_ms ?? '–'} ms`) : t('3단 규칙 판정(Jev 미사용)', 'Tier 3 rule-based (Jev not used)')} · ${t('전체', 'total')} ${res.total_ms} ms` : ''}
        </span>
      </div>
      {err && <div className="note">{t('크리틱 서버에 연결할 수 없어 판정을 보여 드리지 못합니다', 'Cannot reach the critic server, so no verdict can be shown')} ({err})</div>}
      {res && res.claims.map((c) => {
        const iss = issuesOf(c.id), ok = iss.length === 0
        return (
          <div key={c.id} className="fade-in" style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 10, alignItems: 'center', padding: '8px 12px', borderRadius: 10,
            background: c.id === 'me' ? 'rgba(255,181,71,0.07)' : 'rgba(10,16,30,0.5)', border: `1px solid ${ok ? 'rgba(61,220,151,0.3)' : 'rgba(255,93,108,0.3)'}` }}>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 12.5 }}>{c.id === 'me' && <span className="chip jev" style={{ fontSize: 9.5, marginRight: 6 }}>{t('직접 쓴 주장', 'Your claim')}</span>}{c.id === 'me' ? c.text : t(c.text, enText[c.id] ?? c.text)}</div>
              {iss.map((i, k) => <div key={k} className="mono" style={{ fontSize: 10.5, color: 'var(--bad)', marginTop: 2 }}>
                {tier(i.tier)} · {i.rule}{i.p !== null && i.p !== undefined ? ` · p ${i.p.toFixed(2)}` : ''}{i.detail ? ` — ${i.detail.slice(0, 90)}` : ''}</div>)}
            </div>
            <span className={`chip ${ok ? 'ok' : 'bad'}`}>{ok ? 'PASS' : 'REJECT'}</span>
          </div>
        )
      })}
      <div className="row" style={{ gap: 8 }}>
        <input className="input" placeholder={t('직접 주장을 써서 크리틱에 넣어 보세요 (예: 이 약은 PARP1 억제제로 효과가 있다)', 'Write your own claim and send it to the critic (e.g. this drug works as a PARP1 inhibitor)')} value={mine}
          onChange={(e) => setMine(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && mine.trim()) void judge(mine) }} />
        <button className="btn" disabled={busy || !mine.trim()} onClick={() => void judge(mine)}>{t('판정', 'Judge')}</button>
      </div>
    </div>
  )
}
