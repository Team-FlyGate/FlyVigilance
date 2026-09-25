import { useEffect, useState } from 'react'
import { Card, LineChart, Loading, PageHead } from '../components/ui'
import { fmt, getJSON } from '../lib/data'
import type { Backtest } from '../lib/types'

const qIndex = (qs: string[], q: string) => qs.indexOf(q)
const dateToQ = (d: string) => { const [y, m] = d.split('-').map(Number); return `${y}Q${Math.ceil(m / 3)}` }

export default function TimeMachine() {
  const [bt, setBt] = useState<Backtest | null>(null)
  const [i, setI] = useState(0)
  useEffect(() => { getJSON<Backtest>('/data/faers/backtest.json').then(setBt) }, [])
  if (!bt) return <div className="page"><Loading /></div>
  const it = bt.items[i]
  const qs = bt.quarters
  const xt = qs.map((q, k) => ({ x: k, label: q.endsWith('Q1') ? q.slice(0, 4) : '' })).filter((t) => t.label)
  const firstX = it.first_signal_quarter ? qIndex(qs, it.first_signal_quarter) : null
  const actX = it.action ? qIndex(qs, dateToQ(it.action)) : null
  const markers = [
    ...(firstX !== null ? [{ x: firstX, label: `첫 신호 ${it.first_signal_quarter}`, color: '#ff4fd8' }] : []),
    ...(actX !== null && actX >= 0 ? [{ x: actX, label: `FDA 조치 ${it.action}`, color: '#ffcc4d' }] : []),
  ]
  const withLead = bt.items.filter((x) => x.lead_days !== null)
  const maxAbs = Math.max(...withLead.map((x) => Math.abs(x.lead_days as number)), 1)

  return (
    <div className="page">
      <PageHead eyebrow="Signal Time Machine · retrospective backtest"
        title={<>분기 누적 감시였다면 <span style={{ color: 'var(--c-memory)' }}>언제</span> 알 수 있었나</>}
        lede={<>FDA가 안전성 조치를 낸 약물-반응 쌍을 골라, 우리 웨어하우스로 {qs[0]}부터 분기마다 누적 불균형 지표를 다시 계산했다.
          기준은 <span className="mono" style={{ fontSize: 12.5 }}>{bt.criteria}</span>. 연속 감시 에이전트가 이 기준을 매 분기 자동으로 돌렸다면 첫 신호가 언제 섰는지를 본다.</>} />

      <div className="grid" style={{ gridTemplateColumns: '340px minmax(0,1fr)', alignItems: 'start' }}>
        <Card title="규제 조치 사례" sub="FDA Drug Safety Communication 기준일">
          <div className="stack" style={{ gap: 8 }}>
            {bt.items.map((x, k) => (
              <button key={x.drug + x.pt} onClick={() => setI(k)} style={{
                textAlign: 'left', cursor: 'pointer', padding: '10px 12px', borderRadius: 11, border: `1px solid ${k === i ? 'rgba(255,79,216,0.55)' : 'var(--line)'}`,
                background: k === i ? 'rgba(255,79,216,0.08)' : 'rgba(10,16,30,0.45)',
              }}>
                <div className="row between"><b style={{ fontFamily: 'var(--font)', fontSize: 12.5 }}>{x.drug}</b>
                  {x.lead_days !== null ? <span className={`chip ${x.lead_days > 0 ? 'ok' : 'warn'}`}>{x.lead_days > 0 ? `${fmt.int(x.lead_days)}일 먼저` : `${fmt.int(-x.lead_days)}일 늦음`}</span>
                    : <span className="chip">{x.first_signal_quarter ? 'control' : 'no signal'}</span>}</div>
                <div className="dim" style={{ fontSize: 11.5 }}>{x.pt}</div>
              </button>
            ))}
          </div>
        </Card>

        <div className="stack" style={{ gap: 16 }}>
          <Card title={<>{it.drug} × {it.pt}</>} sub={it.what}>
            <div className="grid g4" style={{ marginBottom: 12 }}>
              <div><div className="dim mono" style={{ fontSize: 10.5 }}>FIRST SIGNAL</div><div className="num" style={{ fontSize: 20, color: '#ff4fd8' }}>{it.first_signal_quarter ?? '—'}</div></div>
              <div><div className="dim mono" style={{ fontSize: 10.5 }}>FDA ACTION</div><div className="num" style={{ fontSize: 20, color: '#ffcc4d' }}>{it.action ?? '—'}</div></div>
              <div><div className="dim mono" style={{ fontSize: 10.5 }}>LEAD TIME</div><div className="num" style={{ fontSize: 20 }}>{it.lead_days !== null ? `${it.lead_days > 0 ? '+' : ''}${fmt.int(it.lead_days)} d` : '—'}</div></div>
              <div><div className="dim mono" style={{ fontSize: 10.5 }}>CASES AT ACTION</div><div className="num" style={{ fontSize: 20 }}>{actX !== null && actX >= 0 ? fmt.int(it.series[actX]?.a ?? 0) : fmt.int(it.series[it.series.length - 1].a)}</div></div>
            </div>
            <LineChart height={280} xTicks={xt} yLabel="IC₀₂₅ (cumulative)" markers={markers}
              hlines={[{ y: 0, label: 'IC₀₂₅ = 0', color: '#ff4fd8' }]}
              series={[{ key: 'ic', color: '#37e6ff', area: true, values: it.series.map((s, k) => ({ x: k, y: s.ic025 ?? null })) }]} />
            <div className="grid g2" style={{ marginTop: 12 }}>
              <div>
                <div className="dim mono" style={{ fontSize: 10.5, marginBottom: 4 }}>PRR (cumulative, Evans threshold 2)</div>
                <LineChart height={150} xTicks={xt} markers={markers} markerLabels={false} hlines={[{ y: 2, label: 'PRR 2', color: '#ffcc4d' }]}
                  series={[{ key: 'prr', color: '#ffb547', values: it.series.map((s, k) => ({ x: k, y: s.prr ?? null })) }]} />
              </div>
              <div>
                <div className="dim mono" style={{ fontSize: 10.5, marginBottom: 4 }}>co-reported cases a (cumulative)</div>
                <LineChart height={150} xTicks={xt} markers={markers} markerLabels={false}
                  series={[{ key: 'a', color: '#76b900', area: true, values: it.series.map((s, k) => ({ x: k, y: s.a })) }]} />
              </div>
            </div>
            {it.note && <div style={{ marginTop: 12, padding: 12, borderRadius: 12, border: '1px solid rgba(255,204,77,0.4)', background: 'rgba(255,204,77,0.06)', fontSize: 12.5 }}><b style={{ color: 'var(--warn)' }}>불균형 분석이 놓친 사례 · </b>{it.note}</div>}
            {it.left_censored && <div className="note" style={{ marginTop: 10 }}><b>왼쪽 절단:</b> 웨어하우스 첫 분기({qs[0]})에 이미 기준을 넘었다. 실제 첫 신호는 그 이전일 수 있어 선행 시간은 하한이다.</div>}
          </Card>
          <Card title="선행 시간 요약" sub="양수 = 규제 조치보다 먼저 통계 기준을 넘음. 음수 = 조치가 먼저였음 (기준이 늦게 서는 경우도 그대로 보여 준다)">
            <div className="stack" style={{ gap: 8 }}>
              {withLead.map((x) => {
                const v = x.lead_days as number
                return (
                  <div key={x.drug + x.pt} style={{ display: 'grid', gridTemplateColumns: '220px 1fr 1fr 90px', gap: 0, alignItems: 'center' }}>
                    <span style={{ fontSize: 12 }}>{x.drug} <span className="dim">· {x.pt}</span></span>
                    <div style={{ display: 'flex', justifyContent: 'flex-end', borderRight: '1px solid var(--line-2)' }}>
                      {v < 0 && <div style={{ height: 14, width: `${(-v / maxAbs) * 100}%`, background: 'var(--warn)', borderRadius: '6px 0 0 6px', opacity: .8 }} />}
                    </div>
                    <div>{v > 0 && <div style={{ height: 14, width: `${(v / maxAbs) * 100}%`, background: 'linear-gradient(90deg,#ff4fd8,#37e6ff)', borderRadius: '0 6px 6px 0' }} />}</div>
                    <span className="num" style={{ textAlign: 'right', fontSize: 12 }}>{v > 0 ? '+' : ''}{fmt.int(v)} d</span>
                  </div>
                )
              })}
            </div>
            <div className="note" style={{ marginTop: 12 }}>
              <b>해석 한계.</b> 사후 재계산이다. 분기 파일은 보고 접수 후 수개월 뒤 공개되고, 신호 기준 통과는 평가의 시작이지 인과 확인이 아니다.
              규제 조치는 FAERS 외 임상시험·문헌 근거로 내려지므로 이 선행 시간을 “FDA가 늦었다”로 읽으면 안 된다 (R1, R6).
              이 화면이 보여 주는 것은 연속 자동 감시가 사람의 평가를 <b>언제 시작시킬 수 있었는가</b>다.
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
