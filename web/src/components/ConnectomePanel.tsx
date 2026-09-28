import { useEffect, useRef } from 'react'
import BrainView from './BrainView'
import { useBrain } from '../lib/brain'
import { LAYER_COLOR, fmt } from '../lib/data'

// STEP 1 페이지 오른쪽의 실시간 커넥텀: STEP 2 관제 센터와 같은 MaleCNS 시뮬레이터(30 Hz)를 쓰고,
// 도킹 장면의 사건(포즈 탐색 · 도착 · 검증)이 해당 층을 자극합니다. 층 막대는 관제 센터 LayerMeter 와 같은 계산입니다.

export default function ConnectomePanel({ height = 240, focus }: { height?: number; focus?: string }) {
  // 작은 패널에서는 층 막대가 뇌를 가리므로 뺍니다
  const meter = height >= 220
  const { sim, conn, tick } = useBrain()
  // 스파이크 수 추이 (FDDD 쇼릴 학습 장면처럼 큰 숫자 + 작은 선 그래프)
  const hist = useRef<number[]>([])
  useEffect(() => { if (sim) { hist.current.push(sim.spikes); if (hist.current.length > 90) hist.current.shift() } }, [tick, sim])
  const h = hist.current, hi = Math.max(1, ...h), W = 150, Hs = 26
  const line = h.map((v, i) => `${i ? 'L' : 'M'}${(i / 89) * W},${Hs - (v / hi) * Hs}`).join('')
  return (
    <div style={{ position: 'relative', borderRadius: 14, overflow: 'hidden', border: '1px solid var(--line)', background: 'rgba(5,9,18,0.55)' }}>
      <div style={{ position: 'absolute', left: 12, top: 10, zIndex: 2, pointerEvents: 'none' }}>
        <div className="eyebrow" style={{ color: 'var(--text-3)', fontSize: 10 }}>Live connectome · 30 Hz · MaleCNS</div>
        <div className="mono dim" style={{ fontSize: 10, marginTop: 2 }}>
          {conn ? <>{fmt.int(conn.meta.neurons)} neurons · t = {tick} · active {sim ? fmt.int(sim.spikes) : 0}</> : '…'}
        </div>
        {focus && <div className="mono" style={{ fontSize: 10.5, marginTop: 4, color: 'var(--c-sense)' }}>{focus}</div>}
      </div>
      <div style={{ position: 'absolute', left: 12, bottom: 10, zIndex: 2, pointerEvents: 'none' }}>
        <div className="row" style={{ alignItems: 'baseline', gap: 6 }}>
          <span className="num" style={{ fontFamily: 'var(--font)', fontSize: height >= 220 ? 30 : 22, fontWeight: 700, letterSpacing: -0.5, textShadow: '0 0 18px rgba(55,230,255,0.35)' }}>{sim ? fmt.int(sim.spikes) : '–'}</span>
          <span className="mono dim" style={{ fontSize: 10 }}>spikes / step</span>
        </div>
        <svg width={W} height={Hs} style={{ display: 'block', marginTop: 2 }}><path d={line} fill="none" stroke="var(--c-sense)" strokeWidth={1.4} style={{ filter: 'drop-shadow(0 0 4px rgba(55,230,255,0.6))' }} /></svg>
      </div>
      <div style={{ filter: 'brightness(0.72) saturate(0.9)' }}><BrainView height={height} bloom={0.2} /></div>
      {meter && sim && conn && (
        <div style={{ position: 'absolute', right: 10, bottom: 10, zIndex: 2, width: 190, padding: '8px 10px', borderRadius: 10,
          background: 'rgba(5,9,18,0.72)', border: '1px solid var(--line)', backdropFilter: 'blur(8px)' }}>
          <div className="stack" style={{ gap: 4 }}>
            {conn.meta.layers.map((l, i) => {
              const v = Math.min(1, sim.layerMean[i] / sim.layerPeak[i])
              return (
                <div key={l.key} style={{ display: 'grid', gridTemplateColumns: '8px 86px 1fr', gap: 6, alignItems: 'center' }}>
                  <span className="legend-dot" style={{ width: 6, height: 6, background: LAYER_COLOR[l.key], boxShadow: `0 0 6px ${LAYER_COLOR[l.key]}` }} />
                  <span style={{ fontSize: 9.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{l.name}</span>
                  <div className="pbar" style={{ height: 4 }}><i style={{ width: `${v * 100}%`, background: LAYER_COLOR[l.key], transition: 'width .15s linear' }} /></div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
