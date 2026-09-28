import { useEffect, useState } from 'react'
import { api, fmt, getJSON, type SignalRow } from '../lib/data'
import { t } from '../lib/i18n'

// STEP 1 → STEP 2 연결: 시판 전 화면에서 고른 약물의 시판 후 FAERS 신호를 미리 보여 주고,
// 누르면 신호 연구실(#/signals?drug=…)을 그 약물로 엽니다. 신호는 STEP 2 와 같은 /api/signals 를 씁니다.

let drugsCache: Promise<{ drug: string; n: number }[]> | null = null
/** 약물 이름(소문자 성분명)을 FAERS 약물 이름으로. 복합제는 앞 성분으로 찾습니다(예: nirmatrelvir → NIRMATRELVIR\RITONAVIR) */
export async function faersName(name: string) {
  drugsCache ??= getJSON<{ drug: string; n: number }[]>('/data/faers/drugs.json')
  const list = await drugsCache, up = name.toUpperCase()
  return list.find((d) => d.drug === up) ?? list.find((d) => d.drug.startsWith(`${up}\\`)) ?? null
}
export const signalsHref = (drug: string) => `#/signals?drug=${encodeURIComponent(drug)}`

export default function Step2Handoff({ drug, compact = false }: { drug: string; compact?: boolean }) {
  const [hit, setHit] = useState<{ drug: string; n: number } | null | undefined>(undefined)
  const [rows, setRows] = useState<SignalRow[] | null>(null)
  useEffect(() => {
    let alive = true
    setHit(undefined); setRows(null)
    faersName(drug).then((h) => {
      if (!alive) return
      setHit(h)
      if (h && !compact) api<{ rows: SignalRow[] }>(`/api/signals/${encodeURIComponent(h.drug)}?limit=40`)
        .then((r) => alive && setRows(r.rows.filter((x) => x.evans).slice(0, 3))).catch(() => alive && setRows([]))
    })
    return () => { alive = false }
  }, [drug, compact])
  if (hit === undefined) return null
  if (hit === null) return <span className="mono dim" style={{ fontSize: 10.5 }}>{t('FAERS 에 없는 약물', 'Not in FAERS (FDA Adverse Event Reporting System)')}</span>
  if (compact) return <a href={signalsHref(hit.drug)} className="mono" style={{ fontSize: 10.5, textDecoration: 'none', color: 'var(--nvidia)' }}>STEP 2 →</a>
  return (
    <div style={{ padding: '10px 12px', borderRadius: 11, border: '1px solid rgba(118,185,0,0.35)', background: 'rgba(118,185,0,0.06)' }}>
      <div className="row between" style={{ gap: 8 }}>
        <span className="mono" style={{ fontSize: 10.5, letterSpacing: 1.2, color: 'var(--nvidia)' }}>{t('STEP 2 · 시판 후 FAERS', 'STEP 2 · post-market FAERS')}</span>
        <span className="mono dim" style={{ fontSize: 10.5 }}>{t(`보고 ${fmt.int(hit.n)}건`, `${fmt.int(hit.n)} reports`)}</span>
      </div>
      <div className="stack" style={{ gap: 3, margin: '6px 0 8px' }}>
        {rows === null ? <span className="dim" style={{ fontSize: 11.5 }}>{t('신호 불러오는 중…', 'Loading signals…')}</span>
          : rows.length === 0 ? <span className="dim" style={{ fontSize: 11.5 }}>{t('Evans 기준을 넘는 신호가 없습니다', 'No signal exceeds the Evans criteria')}</span>
          : rows.map((r) => (
            <div key={r.pt} className="row between" style={{ fontSize: 12 }}>
              <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.pt}</span>
              <span className="num" style={{ color: 'var(--text-2)' }}>PRR {r.prr.toFixed(1)} · {t(`${fmt.int(r.a)}건`, `${fmt.int(r.a)} reports`)}</span>
            </div>
          ))}
      </div>
      <a className="btn nv" href={signalsHref(hit.drug)} style={{ textDecoration: 'none', fontSize: 12.5, padding: '6px 12px' }}>{t(`${hit.drug} 시판 후 신호 보기 →`, `View post-market signals for ${hit.drug} →`)}</a>
    </div>
  )
}
