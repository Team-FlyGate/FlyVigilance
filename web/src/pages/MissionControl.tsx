import { useEffect, useMemo, useRef, useState } from 'react'
import BrainView from '../components/BrainView'
import { Card, Kpi, PageHead, Spark } from '../components/ui'
import { useBrain } from '../lib/brain'
import { CHANNEL_COLOR, LAYER_COLOR, fmt, getJSON } from '../lib/data'
import type { Overview, Bench, BenchExample } from '../lib/types'

const ACTION_META: Record<string, { label: string; color: string; layers: string[] }> = {
  close: { label: '종결', color: '#6c7aa8', layers: ['reflex'] },
  monitor: { label: '모니터링', color: '#37e6ff', layers: ['reflex', 'memory'] },
  signal_review: { label: '신호 검토 → System-2', color: '#76b900', layers: ['reflex', 'memory', 'deliberate', 'critic'] },
  expedite: { label: '신속보고 → 사람', color: '#ff5d6c', layers: ['reflex', 'memory', 'deliberate', 'critic', 'action'] },
  follow_up: { label: '추가정보 요청', color: '#a58bff', layers: ['encode'] },
}
export { ACTION_META }

function LayerMeter() {
  const { sim, conn } = useBrain()
  if (!sim || !conn) return null
  return (
    <div className="stack" style={{ gap: 7 }}>
      {conn.meta.layers.map((l, i) => {
        const v = Math.min(1, sim.layerMean[i] / sim.layerPeak[i])
        return (
          <div key={l.key} style={{ display: 'grid', gridTemplateColumns: '12px 118px 1fr 44px', gap: 8, alignItems: 'center' }}>
            <span className="legend-dot" style={{ background: LAYER_COLOR[l.key], boxShadow: `0 0 8px ${LAYER_COLOR[l.key]}` }} />
            <span style={{ fontSize: 11.5 }}>{l.name}</span>
            <div className="pbar" style={{ height: 6 }}><i style={{ width: `${v * 100}%`, background: LAYER_COLOR[l.key], transition: 'width .15s linear' }} /></div>
            <span className="num dim" style={{ fontSize: 10.5, textAlign: 'right' }}>{fmt.compact(l.neurons)}</span>
          </div>
        )
      })}
    </div>
  )
}

function Stream({ examples }: { examples: BenchExample[] }) {
  const { sim } = useBrain()
  const [i, setI] = useState(0)
  const [feed, setFeed] = useState<BenchExample[]>([])
  useEffect(() => {
    if (!examples.length) return
    const id = setInterval(() => setI((k) => k + 1), 1700)
    return () => clearInterval(id)
  }, [examples.length])
  const simRef = useRef(sim)
  simRef.current = sim
  useEffect(() => {
    if (!examples.length) return
    const e = examples[i % examples.length]
    setFeed((f) => (f[0] === e ? f : [e, ...f].slice(0, 7)))
    const sim = simRef.current
    if (!sim) return
    sim.stimulate('channel', 'faers', 1, 6)
    const meta = ACTION_META[e.action] ?? ACTION_META.monitor
    meta.layers.forEach((l, k) => setTimeout(() => sim.stimulate('layer', l, 0.9, 5), 250 + k * 260))
  }, [i, examples])
  return (
    <div className="stack" style={{ gap: 8 }}>
      {feed.map((e, k) => {
        const m = ACTION_META[e.action] ?? ACTION_META.monitor
        return (
          <div key={`${e.primaryid}-${k}-${i}`} className={k === 0 ? 'fade-in' : ''} style={{
            display: 'grid', gridTemplateColumns: '1fr auto', gap: 10, padding: '9px 12px', borderRadius: 11,
            background: k === 0 ? 'rgba(55,230,255,0.07)' : 'rgba(10,16,30,0.5)', border: `1px solid ${k === 0 ? 'rgba(55,230,255,0.3)' : 'var(--line)'}`,
            opacity: 1 - k * 0.1,
          }}>
            <div style={{ minWidth: 0 }}>
              <div className="row" style={{ gap: 8 }}>
                <span className="mono dim" style={{ fontSize: 10.5 }}>#{e.primaryid}</span>
                <b style={{ fontSize: 12.5, fontFamily: 'var(--font)' }}>{e.suspect}</b>
              </div>
              <div className="dim" style={{ fontSize: 11.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{e.reactions.join(' · ')}</div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <span className="chip" style={{ color: m.color, borderColor: m.color + '66' }}>{m.label}</span>
              <div className="mono dim" style={{ fontSize: 10, marginTop: 3 }}>Jev {Math.round(e.latency_ms)} ms · serious {(e.answers.serious as { noul: number }).noul.toFixed(2)}</div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function MissionControl() {
  const [ov, setOv] = useState<Overview | null>(null)
  const [bench, setBench] = useState<Bench | null>(null)
  const { sim, conn, tick } = useBrain()
  useEffect(() => {
    getJSON<Overview>('/data/faers/overview.json').then(setOv)
    getJSON<Bench>('/data/bench.json').then(setBench).catch(() => null)
  }, [])

  // 분기 부하 퍼널: 표본 버킷별 행동 비율을 최신 분기 실제 구성비로 재가중
  const funnel = useMemo(() => {
    if (!bench || !ov) return null
    const L = ov.latest
    const w = { death: L.death / L.cases, serious: (L.serious - L.death) / L.cases, nonserious: (L.cases - L.serious) / L.cases }
    const share: Record<string, number> = {}
    for (const [b, wt] of Object.entries(w)) {
      const acts = bench.jev_triage.actions_by_bucket[b] ?? {}
      const tot = Object.values(acts).reduce((a, c) => a + c, 0) || 1
      for (const [a, c] of Object.entries(acts)) share[a] = (share[a] ?? 0) + wt * (c / tot)
    }
    return { cases: L.cases, share }
  }, [bench, ov])

  const perQ = ov?.per_quarter.map((q) => q.reports) ?? []
  const jt = bench?.jev_triage

  return (
    <div className="page">
      <PageHead eyebrow="FlyVigilante · Mission Control"
        title={<>초파리 커넥텀으로 라우팅되는 <span style={{ color: 'var(--c-sense)' }}>약물감시 에이전트</span></>}
        lede={<>분기마다 40만 건이 넘는 FAERS 이상사례가 쏟아진다. 초파리 뇌가 감각 입력을 반사, 기억, 숙고, 행동으로 나누듯
          FlyVigilante는 모든 케이스를 <b style={{ color: 'var(--jev)' }}>Jev System-1</b>이 수백 밀리초 안에 판단하고,
          꼭 필요한 케이스만 <b style={{ color: 'var(--nvidia)' }}>NVIDIA Nemotron System-2</b>와 사람에게 올린다.</>}
        right={<div className="row wrap" style={{ justifyContent: 'flex-end', maxWidth: 380 }}>
          <span className="chip">MaleCNS v1.0 · Janelia FlyEM</span><span className="chip jev">Jev · TypeSafe AI</span>
          <span className="chip nv">NVIDIA NIM · Nemotron 3</span><span className="chip">openFDA · DailyMed · PubMed</span>
        </div>} />

      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.75fr) minmax(320px, 1fr)', marginBottom: 16 }}>
        <Card className="flush" style={{ minHeight: 600 }}>
          <div style={{ position: 'absolute', left: 20, top: 16, zIndex: 2 }}>
            <div className="eyebrow" style={{ color: 'var(--text-3)' }}>Live connectome · 30 Hz rate model</div>
            <div style={{ fontFamily: 'var(--font)', fontSize: 15, marginTop: 4 }}>
              {conn ? <>{fmt.int(conn.meta.neurons)} neurons · {fmt.compact(conn.meta.edges)} connections · {fmt.compact(conn.meta.synapses)} synapses</> : '…'}
            </div>
            <div className="mono dim" style={{ fontSize: 10.5, marginTop: 2 }}>t = {tick} · active {sim ? fmt.int(sim.spikes) : 0} neurons</div>
          </div>
          <div style={{ position: 'absolute', right: 16, bottom: 16, zIndex: 2, width: 330, padding: 14, borderRadius: 14,
            background: 'rgba(5,9,18,0.72)', border: '1px solid var(--line)', backdropFilter: 'blur(10px)' }}>
            <div className="row between" style={{ marginBottom: 8 }}>
              <span className="eyebrow" style={{ color: 'var(--text-2)' }}>Layer activity</span>
              <span className="mono dim" style={{ fontSize: 10 }}>neurons</span>
            </div>
            <LayerMeter />
          </div>
          <div style={{ position: 'absolute', left: 16, bottom: 16, zIndex: 2 }} className="stack">
            <span className="eyebrow" style={{ color: 'var(--text-3)' }}>Inject data stream</span>
            <div className="row wrap" style={{ gap: 6, maxWidth: 360 }}>
              {conn?.meta.channels.filter((c) => c.key !== 'none').map((c) => (
                <button key={c.key} className="chip" style={{ cursor: 'pointer', color: CHANNEL_COLOR[c.key], borderColor: CHANNEL_COLOR[c.key] + '55' }}
                  onClick={() => sim?.stimulate('channel', c.key, 1.2, 12)} title={`${c.modality} sensory neurons (${c.neurons})`}>
                  {c.name}
                </button>
              ))}
            </div>
          </div>
          <BrainView height={600} />
        </Card>

        <div className="stack" style={{ gap: 16 }}>
          <Card title="Reflex Stream" sub={`실제 ${bench?.dataset.source ?? 'FAERS'} 케이스에 대한 실측 Jev 판단 재생`}
            right={<span className="chip jev"><span className="dot on pulse" style={{ background: 'var(--jev)' }} />live replay</span>}>
            {bench ? <Stream examples={bench.jev_triage.examples} /> : <div className="shimmer" style={{ height: 300 }} />}
          </Card>
        </div>
      </div>

      <div className="grid g4" style={{ marginBottom: 16 }}>
        <Kpi label="FAERS reports ingested" value={ov?.raw_reports ?? 0} color="var(--c-sense)"
          sub={ov ? `${ov.first} – ${ov.asof} · ${ov.quarters} quarters` : '…'} />
        <Kpi label="Unique cases after dedupe" value={ov?.cases ?? 0} color="var(--c-encode)"
          sub={ov ? `${fmt.int(ov.raw_reports - ov.cases)} versions & deletions removed` : '…'} />
        <Kpi label="Signals · Evans ∧ ROR ∧ IC025" value={ov?.all3 ?? 0} color="var(--c-memory)"
          sub={ov ? `of ${fmt.int(ov.pairs)} drug–event pairs (a ≥ 3)` : '…'} />
        <Kpi label="Jev reflex latency p50" value={jt?.latency_ms?.p50 ?? 0} color="var(--jev)" format={(n) => `${Math.round(n)} ms`}
          sub={jt ? `7 typed decisions / call · ${jt.throughput_cases_per_s} cases/s` : '…'} />
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'minmax(0,1.2fr) minmax(0,1fr)', gap: 16 }}>
        <Card title="분기당 부하와 라우팅 퍼널" sub={funnel ? `${ov?.asof} 실제 케이스 ${fmt.int(funnel.cases)}건에 표본 실측 라우팅 비율을 적용한 투영치` : ''}>
          {funnel && jt ? (
            <div className="stack" style={{ gap: 12 }}>
              {Object.entries(ACTION_META).filter(([a]) => funnel.share[a]).sort((a, b) => (funnel.share[b[0]] ?? 0) - (funnel.share[a[0]] ?? 0)).map(([a, m]) => {
                const s = funnel.share[a] ?? 0
                return (
                  <div key={a} style={{ display: 'grid', gridTemplateColumns: '170px 1fr 150px', gap: 12, alignItems: 'center' }}>
                    <span style={{ fontSize: 12.5 }}><span className="legend-dot" style={{ background: m.color, marginRight: 8 }} />{m.label}</span>
                    <div className="pbar" style={{ height: 14 }}><i style={{ width: `${s * 100}%`, background: m.color, opacity: 0.85 }} /></div>
                    <span className="num" style={{ fontSize: 12, textAlign: 'right' }}>{fmt.pct(s, 1)} · {fmt.int(Math.round(s * funnel.cases))}</span>
                  </div>
                )
              })}
              <div className="divider" />
              <div className="grid g3">
                <div><div className="k-label mono dim" style={{ fontSize: 10.5 }}>REFLEX ONLY</div>
                  <div className="num" style={{ fontSize: 22 }}>{fmt.pct((funnel.share.close ?? 0) + (funnel.share.monitor ?? 0) + (funnel.share.follow_up ?? 0), 1)}</div>
                  <div className="dim" style={{ fontSize: 11 }}>System-2 호출 없이 처리</div></div>
                <div><div className="k-label mono dim" style={{ fontSize: 10.5 }}>JEV COST / QUARTER</div>
                  <div className="num" style={{ fontSize: 22 }}>{fmt.usd((jt.usd_per_case ?? 0) * funnel.cases)}</div>
                  <div className="dim" style={{ fontSize: 11 }}>입력 {jt.tokens_in_mean} tok/case × $0.042/M</div></div>
                <div><div className="k-label mono dim" style={{ fontSize: 10.5 }}>REFLEX WALL-CLOCK</div>
                  <div className="num" style={{ fontSize: 22 }}>{(funnel.cases / jt.throughput_cases_per_s / 3600).toFixed(1)} h</div>
                  <div className="dim" style={{ fontSize: 11 }}>동시성 {jt.concurrency}, 실측 처리량 기준</div></div>
              </div>
            </div>
          ) : <div className="shimmer" style={{ height: 200 }} />}
        </Card>
        <Card title="FAERS 분기별 보고량" sub="원천 계층 적재 행 수 (보고 버전 포함)">
          {ov && <>
            <Spark values={perQ} height={120} />
            <div className="row between mono dim" style={{ fontSize: 10.5, marginTop: 6 }}><span>{ov.first}</span><span>{ov.asof}</span></div>
            <div className="grid g3" style={{ marginTop: 14 }}>
              <div><div className="dim mono" style={{ fontSize: 10.5 }}>SERIOUS</div><div className="num" style={{ fontSize: 18 }}>{fmt.compact(ov.serious_cases)}</div></div>
              <div><div className="dim mono" style={{ fontSize: 10.5 }}>DEATH</div><div className="num" style={{ fontSize: 18, color: 'var(--bad)' }}>{fmt.compact(ov.death_cases)}</div></div>
              <div><div className="dim mono" style={{ fontSize: 10.5 }}>MEDDRA PTs</div><div className="num" style={{ fontSize: 18 }}>{fmt.int(ov.pts)}</div></div>
            </div>
          </>}
        </Card>
      </div>
    </div>
  )
}
