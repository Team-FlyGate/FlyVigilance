import BrainView from './BrainView'
import { useBrain } from '../lib/brain'
import { LAYER_COLOR, fmt } from '../lib/data'

// STEP 1 페이지 오른쪽의 실시간 커넥텀: STEP 2 관제 센터와 같은 MaleCNS 시뮬레이터(30 Hz)를 쓰고,
// 도킹 장면의 사건(포즈 탐색 · 도착 · 검증)이 해당 층을 자극합니다. 층 막대는 관제 센터 LayerMeter 와 같은 계산입니다.

export default function ConnectomePanel({ height = 240, focus }: { height?: number; focus?: string }) {
  // 작은 패널에서는 층 막대가 뇌를 가리므로 뺍니다
  const meter = height >= 220
  const { sim, conn, tick } = useBrain()
  return (
    <div style={{ position: 'relative', borderRadius: 14, overflow: 'hidden', border: '1px solid var(--line)', background: 'rgba(5,9,18,0.55)' }}>
      <div style={{ position: 'absolute', left: 12, top: 10, zIndex: 2, pointerEvents: 'none' }}>
        <div className="eyebrow" style={{ color: 'var(--text-3)', fontSize: 10 }}>Live connectome · 30 Hz · MaleCNS</div>
        <div className="mono dim" style={{ fontSize: 10, marginTop: 2 }}>
          {conn ? <>{fmt.int(conn.meta.neurons)} neurons · t = {tick} · active {sim ? fmt.int(sim.spikes) : 0}</> : '…'}
        </div>
        {focus && <div className="mono" style={{ fontSize: 10.5, marginTop: 4, color: 'var(--c-sense)' }}>{focus}</div>}
      </div>
      <BrainView height={height} bloom={1} />
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
