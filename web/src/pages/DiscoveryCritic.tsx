// STEP 1-5 크리틱: 앞 단계의 라이브 결과로 쓴 주장을 3단(근거 ID · 숫자 오라클 · Nemotron 판정)에 통과시킵니다.
import { useEffect, useMemo, useState } from 'react'
import { Card } from '../components/ui'
import { KV, Progress, RunButton, SkillBox, StepPage, pulseReward } from '../components/DiscoveryShell'
import { useBrain } from '../lib/brain'
import { getCatalog, runCritic, setReward, useDiscovery, type Catalog, type Claim, type CriticResult } from '../lib/discovery'

const TIERS = [
  { n: 1, name: '근거 ID 검사', en: 'Evidence IDs', model: '모델 미사용', color: '#37e6ff',
    what: '주장마다 근거 ID 가 붙었는지, 그 ID 가 실제 실행 결과에 있는지 확인합니다.' },
  { n: 2, name: '숫자 오라클', en: 'Numeric oracle', model: '모델 미사용', color: '#ffb547',
    what: '주장 속 숫자가 NIM 원본 응답에서 나온 값과 맞는지 대조합니다. 이름 속 숫자는 제외합니다.' },
  { n: 3, name: '과잉해석 판정', en: 'Overclaim judgment', model: 'nvidia/nemotron-3-super-120b-a12b', color: '#ff5d6c',
    what: '숫자가 다 맞아도 추론이 근거를 넘으면 반려합니다(예: 다른 단백질의 도킹 점수 비교).' },
]

function TierCard({ t, active, done, issues }: { t: typeof TIERS[number]; active: boolean; done: boolean; issues: number }) {
  const state = active ? '검사 중' : done ? (issues ? `${issues}건 반려` : '통과') : '대기'
  const color = active ? t.color : done ? (issues ? 'var(--bad)' : 'var(--ok)') : 'var(--text-3)'
  return (
    <div className="card" style={{ padding: '12px 14px', boxShadow: `var(--shadow), inset 3px 0 0 ${color}`, opacity: done || active ? 1 : 0.65 }}>
      <div className="row between">
        <b style={{ fontFamily: 'var(--font)', fontSize: 13.5 }}>{t.n}단 · {t.name}</b>
        <span className={`chip ${active ? 'warn' : done ? (issues ? 'bad' : 'ok') : ''}`} style={{ fontSize: 10 }}>
          {active && <span className="spin" style={{ width: 9, height: 9, marginRight: 5 }} />}{state}
        </span>
      </div>
      <div className="mono dim" style={{ fontSize: 9.5, marginTop: 2 }}>{t.en} · {t.model}</div>
      <div className="note" style={{ marginTop: 5 }}>{t.what}</div>
    </div>
  )
}

export default function DiscoveryCritic() {
  const { sim } = useBrain()
  const { runs } = useDiscovery()
  const [cat, setCat] = useState<Catalog | null>(null)
  const [busy, setBusy] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [stage, setStage] = useState(0)
  const [out, setOut] = useState<CriticResult | null>(null)
  const [extra, setExtra] = useState('')
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => { getCatalog().then(setCat).catch(() => setErr('목록을 불러오지 못했습니다')) }, [])
  useEffect(() => {
    if (!busy) return
    const t0 = Date.now()
    const id = setInterval(() => setElapsed((Date.now() - t0) / 1000), 100)
    return () => clearInterval(id)
  }, [busy])

  const hasRuns = Object.keys(runs).length > 0

  async function run() {
    setBusy(true); setErr(null); setElapsed(0); setStage(1); setOut(null)
    sim?.stimulate('layer', 'critic', 1.3, 14)
    const beat = setInterval(() => sim?.stimulate('layer', 'critic', 0.9, 6), 900)
    const walk = setInterval(() => setStage((s) => Math.min(3, s + 1)), 900)
    try {
      const claims: Claim[] | undefined = extra.trim()
        ? [{ id: 'cx', text: extra.trim(), evidence: [], kind: 'overclaim' }]
        : undefined
      const body = claims
        ? { claims, runs: runs as unknown as Record<string, unknown> }
        : { runs: runs as unknown as Record<string, unknown> }
      const r = await runCritic(body)
      setOut(r)
      setStage(3)
      const rejected = r.issues.length
      sim?.stimulate('layer', 'critic', rejected ? 1.4 : 0.6, rejected ? 18 : 8)
      if (rejected) setReward(0.08, `${rejected}건 반려 · 근거를 넘는 주장을 막았습니다`, '크리틱')
      else pulseReward(sim, 0.5, '주장 전부 통과', '크리틱')
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally { clearInterval(beat); clearInterval(walk); setBusy(false) }
  }

  const issuesByTier = useMemo(() => {
    const m: Record<number, number> = { 1: 0, 2: 0, 3: 0 }
    for (const i of out?.issues ?? []) m[i.tier] = (m[i.tier] ?? 0) + 1
    return m
  }, [out])
  const m = cat?.measured.critic
  const ml = cat?.measured.critic_lightning

  return (
    <StepPage
      eyebrow="STEP 1 · 시판 전 탐색 · 5단계"
      title={<>결과가 <span style={{ color: 'var(--c-critic)' }}>말해도 되는 범위</span>를 정합니다</>}
      lede={<>앞 네 단계의 라이브 결과로 쓴 주장을 크리틱 3단에 통과시킵니다. 1단과 2단은 모델을 쓰지 않는 규칙 검사이고,
        3단은 NVIDIA <b>Nemotron 3 Super</b> 가 추론이 근거를 넘었는지 판정합니다. 숫자가 다 맞아도 3단에서 반려될 수 있습니다.</>}
      right={<span className="chip nv">integrate.api.nvidia.com · Nemotron</span>}
      current="critic"
      center={
        <>
          <Card title="크리틱 3단" sub={out ? `${out.claims.length}개 주장 · 반려 ${out.issues.length}건 · 판정 ${out.judge.model ?? '–'}` : '실행하면 단계가 차례로 돕니다'}>
            <div className="grid g3" style={{ gap: 12 }}>
              {TIERS.map((t) => (
                <TierCard key={t.n} t={t} active={busy && stage === t.n} done={Boolean(out) || (busy && stage > t.n)} issues={out ? issuesByTier[t.n] : 0} />
              ))}
            </div>
            <div className="divider" />
            <div className="stack" style={{ gap: 8 }}>
              {(out?.claims ?? []).map((c) => {
                const rejected = c.verdict === 'REJECT'
                const issue = out?.issues.find((i) => i.claim === c.id)
                return (
                  <div key={c.id} className="fade-in" style={{
                    padding: '10px 12px', borderRadius: 12, border: `1px solid ${rejected || issue ? 'rgba(255,93,108,0.45)' : 'rgba(61,220,151,0.35)'}`,
                    background: rejected || issue ? 'rgba(255,93,108,0.07)' : 'rgba(61,220,151,0.05)',
                  }}>
                    <div className="row between" style={{ gap: 10, alignItems: 'flex-start' }}>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: 13 }}>{c.text}</div>
                        <div className="row wrap" style={{ gap: 5, marginTop: 5 }}>
                          {c.evidence.map((e) => <span key={e} className="chip ev">{e}</span>)}
                          {c.kind === 'overclaim' && <span className="chip warn" style={{ fontSize: 9.5 }}>과잉해석 주입</span>}
                        </div>
                      </div>
                      <span className={`chip ${rejected || issue ? 'bad' : 'ok'}`} style={{ flex: 'none' }}>
                        {rejected || issue ? '반려' : '통과'}{c.rule ? ` · ${c.rule}` : ''}
                      </span>
                    </div>
                    {(c.why || issue) && (
                      <div className="note" style={{ marginTop: 6 }}>
                        {issue ? `${issue.tier}단 · ${issue.detail_ko ?? issue.detail}` : c.why}
                      </div>
                    )}
                  </div>
                )
              })}
              {!out && !busy && (
                <div className="note">앞 단계를 돌리면 그 실행값으로 주장이 채워집니다. 지금 실행하면 {hasRuns ? '이번 세션의 라이브 결과' : '지난 측정값'}로 주장을 만듭니다.</div>
              )}
            </div>
          </Card>
          <Card title="과잉해석을 직접 넣어 보기" sub="근거를 넘는 문장을 써서 3단이 잡는지 확인합니다">
            <div className="row" style={{ gap: 8 }}>
              <input className="input" style={{ flex: 1 }} value={extra} onChange={(e) => setExtra(e.target.value)}
                placeholder="예: 니라파립은 PARP1 -10.178, Factor Xa -7.967 이므로 PARP1 에 선택적입니다." />
              <button className="btn" disabled={busy || !extra.trim()} onClick={run}>이 주장만 검사</button>
            </div>
            <div className="row wrap" style={{ gap: 6, marginTop: 8 }}>
              {(out?.rules ?? []).map((r) => (
                <span key={r.id} className="chip" style={{ fontSize: 10 }} title={r.text}>{r.id} · {r.ko}</span>
              ))}
            </div>
          </Card>
        </>
      }
      side={
        <>
          <Card title="라이브 실행" sub="NVIDIA Nemotron 호출">
            <RunButton busy={busy} onClick={() => { setExtra(''); run() }} label="크리틱 3단 실행"
              sub={hasRuns ? <>이번 세션 실행 {Object.keys(runs).join(' · ')}</> : <>앞 단계 결과가 없으면 지난 측정값으로 주장을 만듭니다</>} />
            <div className="divider" />
            <Progress env={null} busy={busy} elapsed={elapsed} />
            {err && <div className="note" style={{ color: 'var(--warn)', marginTop: 8 }}>{err}</div>}
            {out?.judge.error && <div className="note" style={{ color: 'var(--warn)', marginTop: 8 }}>3단 판정 오류: {out.judge.error}</div>}
          </Card>
          <Card title="요청" sub={out?.endpoint ?? 'integrate.api.nvidia.com/v1/chat/completions'}>
            <KV rows={[
              ['model', <span key="m" className="mono" style={{ fontSize: 10 }}>{out?.judge.model ?? 'nvidia/nemotron-3-super-120b-a12b'}</span>],
              ['mode', 'json_object · temperature 0'],
              ['근거 ID', String(out?.bundle.ids.length ?? '–')],
              ['주장', String(out?.claims.length ?? '–')],
            ]} />
          </Card>
          <Card title="측정값" sub="이번 실행">
            <KV rows={[
              ['판정', out ? (out.verdict === 'pass' ? '전부 통과' : '되돌림') : '–'],
              ['과잉해석 적발', out ? `${out.score.caught}/${out.score.n_over}` : '–'],
              ['정상 주장 통과', out ? `${out.score.passed}/${out.score.n_valid}` : '–'],
              ['3단 지연', out?.judge.latency_ms ? `${(out.judge.latency_ms / 1000).toFixed(1)}초` : '–'],
              ['전체', busy ? `${elapsed.toFixed(1)}초` : out ? `${(out.total_ms / 1000).toFixed(1)}초` : '–'],
            ]} />
            <div className="divider" />
            <div className="stack" style={{ gap: 4 }}>
              <div className="row between">
                <span className="chip warn" style={{ fontSize: 10.5 }}>지난 측정 · Super</span>
                <span className="num dim" style={{ fontSize: 11.5 }}>{m ? `${m.caught}/${m.n_over} 적발 · ${m.passed}/${m.n_valid} 통과 · ${m.sec}초` : '–'}</span>
              </div>
              <div className="row between">
                <span className="chip" style={{ fontSize: 10.5 }}>지난 측정 · Lightning</span>
                <span className="num dim" style={{ fontSize: 11.5 }}>{ml ? `${ml.caught}/${ml.n_over} 적발 · ${ml.sec}초` : '–'}</span>
              </div>
            </div>
            <div className="note" style={{ marginTop: 6 }}>지난 측정은 과잉해석 4건과 정상 4건으로 잰 기록입니다. Lightning 은 주어진 출력 토큰 안에서 판정 줄을 내지 못했습니다.</div>
          </Card>
          <Card title="따라간 스킬">
            <SkillBox skills={out?.skills ?? cat?.skills.critic ?? []} />
            <div className="note" style={{ marginTop: 8 }}>
              같은 3단 구조를 STEP 2 FlyVigilance 의 <a href="#/triage">사례 분류</a>에서도 씁니다(근거 ID · 숫자 오라클 · 판정 + 안전 가드).
            </div>
          </Card>
        </>
      }
    />
  )
}
