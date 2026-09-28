import { useEffect, useState } from 'react'

// Boltz-2 단계의 친화도 예측 그래픽: 억제제가 포켓에 나타날 때마다 pIC50 눈금 위로 Boltz-2 예측값이 미끄러져 자리 잡고,
// 같은 눈금에 ChEMBL 실측 중앙값(흰 눈금)이 찍힙니다. 값은 measurements.json 의 Boltz-2 · ChEMBL 실측 그대로입니다.

export interface AffinityItem { name: string; boltz_pic50: number | null; boltz_p: number | null; chembl: number | null; chembl_n: number | null }
const COLOR: Record<string, string> = { '15r': '#2fd6c8', pamiparib: '#a58bff', niraparib: '#ffb547', rucaparib: '#ff7ab6' }
const NAME = (n: string) => (n === '15r' ? '15R' : n.charAt(0).toUpperCase() + n.slice(1))
const LO = 5, HI = 11

export default function AffinityMeter({ items, delayMs = 400, stepMs = 700 }: { items: AffinityItem[]; delayMs?: number; stepMs?: number }) {
  const [t, setT] = useState(0)
  useEffect(() => {
    // 프레임을 쉬는 창에서도 진행되도록 일반 타이머로 시간을 셉니다
    const t0 = performance.now(), end = delayMs + stepMs * items.length + 1200
    const id = setInterval(() => { const e = performance.now() - t0; setT(e); if (e > end) clearInterval(id) }, 40)
    return () => clearInterval(id)
  }, [items, delayMs, stepMs])
  const X = (v: number) => `${((v - LO) / (HI - LO)) * 100}%`
  // 니라파립을 마지막(주인공)으로
  const order = [...items].sort((a, b) => (a.name === 'niraparib' ? 1 : 0) - (b.name === 'niraparib' ? 1 : 0))
  return (
    <div style={{ position: 'absolute', left: 16, right: 16, bottom: 14, zIndex: 2, padding: '12px 16px 10px', borderRadius: 12,
      background: 'rgba(5,9,18,0.78)', border: '1px solid var(--line)', backdropFilter: 'blur(8px)', pointerEvents: 'none' }}>
      <div className="row between" style={{ marginBottom: 8 }}>
        <span className="mono" style={{ fontSize: 10.5, letterSpacing: 1.3, color: 'var(--jev)' }}>BOLTZ-2 · 친화도 예측 (pIC50)</span>
        <span className="mono dim" style={{ fontSize: 10 }}>● 예측 · │ ChEMBL 실측 중앙값</span>
      </div>
      {order.map((it, i) => {
        const k = Math.max(0, Math.min(1, (t - delayMs - i * stepMs) / 900)), e = 1 - Math.pow(1 - k, 3)
        const pred = it.boltz_pic50 ?? LO
        return (
          <div key={it.name} style={{ display: 'grid', gridTemplateColumns: '84px 1fr 110px', gap: 10, alignItems: 'center', height: 20, opacity: k > 0 ? 1 : 0.25 }}>
            <span style={{ fontSize: 12, fontWeight: it.name === 'niraparib' ? 700 : 500, color: COLOR[it.name] }}>{NAME(it.name)}</span>
            <div style={{ position: 'relative', height: 4, borderRadius: 2, background: 'rgba(120,170,255,0.12)' }}>
              <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `calc(${X(LO + (pred - LO) * e)})`, borderRadius: 2, background: `linear-gradient(90deg, transparent, ${COLOR[it.name]})`, opacity: 0.7 }} />
              <div style={{ position: 'absolute', top: -4, left: `calc(${X(LO + (pred - LO) * e)} - 6px)`, width: 12, height: 12, borderRadius: 6, background: COLOR[it.name], boxShadow: `0 0 10px ${COLOR[it.name]}` }} />
              {it.chembl !== null && k >= 1 && <div className="fade-in" style={{ position: 'absolute', top: -7, left: X(it.chembl), width: 2, height: 18, background: '#f4f7ff' }} />}
            </div>
            <span className="num" style={{ fontSize: 11.5, textAlign: 'right', color: k >= 1 ? 'var(--text)' : 'var(--text-3)' }}>
              {k > 0 ? (LO + (pred - LO) * e).toFixed(2) : '계산 중…'}{k >= 1 ? (it.chembl !== null ? ` · 실측 ${it.chembl}` : ' · 실측 없음') : ''}
            </span>
          </div>
        )
      })}
      <div style={{ display: 'grid', gridTemplateColumns: '84px 1fr 110px', gap: 10, marginTop: 4 }}>
        <span />
        <div className="row between mono dim" style={{ fontSize: 9.5 }}>{[5, 6, 7, 8, 9, 10, 11].map((v) => <span key={v}>{v}</span>)}</div>
        <span />
      </div>
    </div>
  )
}
