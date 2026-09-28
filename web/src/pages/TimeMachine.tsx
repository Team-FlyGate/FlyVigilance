import { useEffect, useState } from 'react'
import { Card, LineChart, Loading, PageHead } from '../components/ui'
import { fmt, getJSON } from '../lib/data'
import type { Backtest, ReporterMix } from '../lib/types'

const qIndex = (qs: string[], q: string) => qs.indexOf(q)
const dateToQ = (d: string) => { const [y, m] = d.split('-').map(Number); return `${y}Q${Math.ceil(m / 3)}` }
// 첫 SDR 까지 사례가 대부분 소비자·변호사 보고이거나 한 분기에 몰렸다면 선행 일수를 조심해 읽습니다
type Item = Backtest['items'][number]
const shaky = (x: Item) => { const r = x.reporters; if (!r?.to_first_sdr) return null
  if (r.to_first_sdr.cn + r.to_first_sdr.lw >= 0.7) return `첫 SDR까지 사례의 ${fmt.pct(r.to_first_sdr.cn + r.to_first_sdr.lw, 0)}가 소비자·변호사 보고입니다.`
  if ((r.peak_share ?? 0) >= 0.4) return `전체 사례의 ${fmt.pct(r.peak_share ?? 0, 0)}가 ${r.peak_quarter} 한 분기에 접수되었습니다.`
  return null }
// 백테스트 메모의 화면 표시 문구입니다. 원문이 바뀌면 원문을 그대로 씁니다
const NOTE_KO: Record<string, string> = {
  '분기 누적 불균형 분석으로는 기준(PRR≥2)을 넘지 못했다. FDA 조치 근거는 무작위 임상시험(ORAL Surveillance) 중간 결과였다. 자발적 보고 통계만으로는 못 잡는 신호가 있다는 사례다.':
    '분기 누적 불균형 지표는 기준(PRR≥2)에 이르지 않았습니다. FDA 조치는 무작위 임상시험(ORAL Surveillance) 중간 결과에 근거했습니다. 임상시험 근거를 자발적 보고 통계와 함께 보는 이유를 보여 주는 사례입니다.',
}
function MixBar({ label, m }: { label: string; m: ReporterMix | null }) {
  if (!m) return <div className="dim" style={{ fontSize: 11.5 }}>{label}: 해당 사례 없음</div>
  return (
    <div>
      <div className="row between" style={{ fontSize: 11.5 }}><span>{label} <span className="dim">· {fmt.int(m.n)}건</span></span>
        <span className="num dim">의료인 {fmt.pct(m.hcp, 0)} · 소비자 {fmt.pct(m.cn, 0)} · 변호사 {fmt.pct(m.lw, 0)}</span></div>
      <div className="row" style={{ height: 8, borderRadius: 4, overflow: 'hidden', marginTop: 4, background: 'rgba(120,170,255,0.1)' }}>
        <span style={{ width: `${m.hcp * 100}%`, background: '#37e6ff' }} /><span style={{ width: `${m.cn * 100}%`, background: '#ffb547' }} /><span style={{ width: `${m.lw * 100}%`, background: '#ff5d6c' }} />
      </div>
    </div>
  )
}

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
    ...(firstX !== null ? [{ x: firstX, label: `첫 SDR ${it.first_signal_quarter}`, color: '#ff4fd8' }] : []),
    ...(actX !== null && actX >= 0 ? [{ x: actX, label: `FDA 조치 ${it.action}`, color: '#ffcc4d' }] : []),
  ]
  const withLead = bt.items.filter((x) => x.lead_days !== null)
  const maxAbs = Math.max(...withLead.map((x) => Math.abs(x.lead_days as number)), 1)

  return (
    <div className="page">
      <PageHead eyebrow="Signal Time Machine · retrospective backtest"
        title={<>분기 누적 감시였다면 <span style={{ color: 'var(--c-memory)' }}>언제</span> 알 수 있었을까요</>}
        lede={<>FDA가 안전성 조치를 낸 약물-반응 쌍을 골라, 우리 웨어하우스로 {qs[0]}부터 분기마다 누적 불균형 지표를 다시 계산했습니다.
          기준은 <span className="mono" style={{ fontSize: 12.5 }}>{bt.criteria}</span>입니다. 연속 감시 에이전트가 이 기준을 매 분기 자동으로 돌렸다면 첫 SDR(불균형 보고 신호)이 언제 섰는지를 봅니다.
          SDR은 검토를 시작하게 하는 통계 기준 통과이며, 검증된 신호가 아닙니다.</>} />

      <div className="grid" style={{ gridTemplateColumns: '340px minmax(0,1fr)', alignItems: 'start' }}>
        <Card title="규제 조치 사례" sub="FDA Drug Safety Communication 기준일">
          <div className="stack" style={{ gap: 8 }}>
            {bt.items.map((x, k) => (
              <button key={x.drug + x.pt} onClick={() => setI(k)} style={{
                textAlign: 'left', cursor: 'pointer', padding: '10px 12px', borderRadius: 11, border: `1px solid ${k === i ? 'rgba(255,79,216,0.55)' : 'var(--line)'}`,
                background: k === i ? 'rgba(255,79,216,0.08)' : 'rgba(10,16,30,0.45)',
              }}>
                <div className="row between"><b style={{ fontFamily: 'var(--font)', fontSize: 12.5 }}>{x.drug}</b>
                  {x.lead_days !== null ? <span className={`chip ${x.lead_days > 0 ? (shaky(x) ? 'warn' : 'ok') : 'warn'}`}>{x.lead_days > 0 ? `${fmt.int(x.lead_days)}일 먼저` : `${fmt.int(-x.lead_days)}일 늦음`}</span>
                    : <span className="chip">{x.first_signal_quarter ? 'control' : 'no SDR'}</span>}</div>
                <div className="dim" style={{ fontSize: 11.5 }}>{x.pt}{shaky(x) ? ' · 보고자 구성 주의' : ''}</div>
              </button>
            ))}
          </div>
        </Card>

        <div className="stack" style={{ gap: 16 }}>
          <Card title={<>{it.drug} × {it.pt}</>} sub={it.what}>
            <div className="grid g4" style={{ marginBottom: 12 }}>
              <div><div className="dim mono" style={{ fontSize: 10.5 }}>FIRST SDR</div><div className="num" style={{ fontSize: 20, color: '#ff4fd8' }}>{it.first_signal_quarter ?? '—'}</div></div>
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
            {it.reporters && (
              <div className="stack" style={{ gap: 8, marginTop: 12, padding: 12, borderRadius: 12, border: '1px solid var(--line)' }}>
                <div className="dim mono" style={{ fontSize: 10.5 }}>REPORTERS · 누가 보고했는지 (파랑 의료인 · 주황 소비자 · 빨강 변호사)</div>
                <MixBar label="첫 SDR 까지" m={it.reporters.to_first_sdr} />
                <MixBar label="FDA 조치 전" m={it.reporters.pre_action} />
                {shaky(it) && <div style={{ fontSize: 12, color: 'var(--warn)' }}>주의: {shaky(it)} 이 선행 일수는 의료인 보고로 선 SDR보다 조심해서 읽어야 합니다.</div>}
              </div>
            )}
            {it.note && <div style={{ marginTop: 12, padding: 12, borderRadius: 12, border: '1px solid rgba(255,204,77,0.4)', background: 'rgba(255,204,77,0.06)', fontSize: 12.5 }}><b style={{ color: 'var(--warn)' }}>{it.first_signal_quarter ? '참고 · ' : 'SDR 없이 다른 근거로 조치된 사례 · '}</b>{NOTE_KO[it.note] ?? it.note}</div>}
            {it.left_censored && <div className="note" style={{ marginTop: 10 }}><b>왼쪽 절단:</b> 웨어하우스 첫 분기({qs[0]})에 이미 기준을 넘었습니다. 실제 첫 SDR은 그 이전일 수 있어 선행 시간은 하한입니다.</div>}
          </Card>
          <Card title="선행 시간 요약" sub="양수는 규제 조치보다 먼저 통계 기준을 넘었다는 뜻이고, 음수는 조치가 먼저였다는 뜻입니다. 모든 사례를 같은 기준으로 보여 드립니다">
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
              <b>읽는 법.</b> 공개된 분기 파일로 다시 계산한 결과입니다. 분기 파일은 보고 접수 후 수개월 뒤 공개되고, SDR은 평가를 시작하는 계기이며 인과 확인은 그다음 단계입니다.
              FDA 내부 검토는 공개 조치보다 앞설 수 있습니다(Harpaz 등은 라벨 개정보다 최대 2년 앞설 수 있다고 적었습니다).
              그래서 선행 시간은 공개 조치(라벨 개정) 시점을 기준으로 잰 값입니다 (R1, R6). 레보플록사신처럼 소비자 보고가 한꺼번에 접수되어 선 SDR은 보고자 구성과 함께 봅니다.
              이 화면은 연속 자동 감시가 사람의 평가를 <b>언제 시작시킬 수 있었는지</b>를 보여 드립니다.
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
