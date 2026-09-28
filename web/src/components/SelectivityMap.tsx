import { useEffect, useMemo, useState } from 'react'
import type { RedockScene } from './DockingView'
import { Card } from './ui'
import Step2Handoff from './Step2Handoff'
import { getJSON } from '../lib/data'

// 선택성 착시 히트맵: 약물 20 × 표적 14 의 DiffDock NIM 1순위 포즈 신뢰도.
// 값은 미리 계산 결과(dock_matrix.json, 266건)와 재도킹(redock_scenes.json, 원래 리간드 14건)을 그대로 씁니다.
// 칸을 누르면 "신뢰도가 가장 높으니 이 표적에 선택적이다" 라는 주장을 크리틱 3단으로 검사하고, 위 직접 도킹 장면에 그 조합을 띄웁니다.
// 3단 판정은 크리틱의 교차 표적 규칙(rule:cross-target)과 같은 논리를 결정적으로 적용한 것입니다(모델 호출 없음).
// 칸마다 ChEMBL 실측 결합 기록(selectivity_evidence.json)을 겹쳐, 선택성은 도킹 점수 차이가 아니라 실험 근거로 말하게 합니다.

interface Library { targets: { key: string; gene: string; target: string; pdb: string; native: string }[]; ligands: { name: string; smiles: string; source: string; native_target: string | null }[] }
interface Matrix { results: Record<string, { confidence: (number | null)[] }> }
interface EvCell { n: number; median: number; max: number; types: string[]; docs: number; evidence: 'strong' | 'weak' }
interface Evidence { strong_pchembl: number; ligands: Record<string, { chembl: string | null }>; cells: Record<string, EvCell>; source: string }
const STARS = { strong: '★★★', weak: '★★', none: '★' }

const cap = (s: string) => s.split(' ').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
// 신뢰도(대략 -4.3 ~ 1.0)를 어두운 남색 → 파랑 → 시안으로
function color(v: number | null) {
  if (v === null) return 'rgba(120,170,255,0.05)'
  const k = Math.max(0, Math.min(1, (v + 3.5) / 4.6))
  const a = [12, 20, 44], b = [77, 141, 255], c = [55, 230, 255]
  const m = k < 0.6 ? a.map((x, i) => x + (b[i] - x) * (k / 0.6)) : b.map((x, i) => x + (c[i] - x) * ((k - 0.6) / 0.4))
  return `rgb(${m.map(Math.round).join(',')})`
}

export default function SelectivityMap({ scenes }: { scenes: Record<string, RedockScene> }) {
  const [lib, setLib] = useState<Library | null>(null)
  const [mat, setMat] = useState<Matrix | null>(null)
  const [sel, setSel] = useState<{ lig: string; tgt: string } | null>(null)
  const [evd, setEvd] = useState<Evidence | null>(null)
  useEffect(() => {
    getJSON<Evidence>('/discovery/data/selectivity_evidence.json').then(setEvd).catch(() => null)
    getJSON<Library>('/discovery/data/dock_library.json').then(setLib).catch(() => null)
    getJSON<Matrix>('/discovery/data/dock_matrix.json').then(setMat).catch(() => null)
  }, [])

  const grid = useMemo(() => {
    if (!lib || !mat) return null  // 미리 계산이 다 로드된 뒤에만 계산합니다(순위가 섞이지 않게)
    const conf = (lig: string, tgt: string): number | null => {
      const t = lib.targets.find((x) => x.key === tgt)
      if (t?.native === lig) return scenes[tgt]?.poses[0]?.confidence ?? null
      return mat?.results[`${tgt}|${lig}`]?.confidence[0] ?? null
    }
    // 원래 표적이 있는 약물을 위로, 그 안에서는 표적 순서대로
    const ligs = [...lib.ligands].sort((a, b) => {
      const ia = lib.targets.findIndex((t) => t.native === a.name), ib = lib.targets.findIndex((t) => t.native === b.name)
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.name.localeCompare(b.name)
    })
    const rank = (lig: string, tgt: string) => {
      const v = conf(lig, tgt)
      if (v === null) return null
      return 1 + lib.targets.filter((t) => t.key !== tgt && (conf(lig, t.key) ?? -99) > v).length
    }
    const natives = lib.targets.map((t) => ({ lig: t.native, tgt: t.key, rank: rank(t.native, t.key) }))
    // 단독 1위만 셉니다. 신뢰도가 소수점까지 같은 표적이 있으면 공동 1위로 따로 적습니다
    const tied = (lig: string, tgt: string) => { const v = conf(lig, tgt); return lib.targets.some((t) => t.key !== tgt && v !== null && conf(lig, t.key) === v) }
    const top1 = natives.filter((n) => n.rank === 1 && !tied(n.lig, n.tgt)).length
    const coTop = natives.filter((n) => n.rank === 1 && tied(n.lig, n.tgt)).map((n) => n.lig)
    return { conf, ligs, rank, natives, top1, coTop }
  }, [lib, mat, scenes])

  const pick = (lig: string, tgt: string) => {
    setSel({ lig, tgt })
    window.dispatchEvent(new CustomEvent('fd-dock', { detail: { target: tgt, ligand: lig } }))
  }
  useEffect(() => { if (grid && !sel) setSel({ lig: 'aripiprazole', tgt: grid.ligs.length ? (lib!.targets.map((t) => t.key).sort((a, b) => (grid.conf('aripiprazole', b) ?? -99) - (grid.conf('aripiprazole', a) ?? -99))[0]) : '' }) }, [grid, sel, lib])

  if (!lib || !grid) return <Card title="선택성 착시 히트맵"><div className="shimmer" style={{ height: 360 }} /></Card>
  const T = lib.targets
  const ev = (lig: string, tgt: string): EvCell | null => { const g = T.find((x) => x.key === tgt)?.gene; return (g && evd?.cells[`${g}|${lig}`]) || null }
  const nStrong = evd ? T.reduce((k, t) => k + grid.ligs.filter((l) => ev(l.name, t.key)?.evidence === 'strong').length, 0) : 0
  // 실측 결합이 있는 칸 가운데 그 약물의 도킹 신뢰도 1위였던 칸
  const strongTop = evd ? T.reduce((k, t) => k + grid.ligs.filter((l) => ev(l.name, t.key)?.evidence === 'strong' && grid.rank(l.name, t.key) === 1).length, 0) : 0
  const s = sel && { t: T.find((x) => x.key === sel.tgt)!, l: sel.lig, v: grid.conf(sel.lig, sel.tgt), r: grid.rank(sel.lig, sel.tgt) }
  const nativeT = s ? T.find((x) => x.native === s.l) : undefined
  const best = s ? T.map((t) => ({ t, v: grid.conf(s.l, t.key) ?? -99 })).sort((a, b) => b.v - a.v)[0] : undefined

  return (
    <Card title="선택성 착시 히트맵 · 약물 20 × 표적 14"
      sub={`DiffDock NIM 1순위 포즈 신뢰도. ★ 는 그 약물의 원래 표적입니다. 원래 표적이 14개 중 신뢰도 단독 1위인 약물은 ${grid.top1}/${grid.natives.length}개뿐입니다${grid.coTop.length ? ` (공동 1위 ${grid.coTop.map(cap).join(', ')})` : ''}.${evd ? ` 흰 점은 ChEMBL 실측 결합 기록입니다. 실측 결합이 있는 ${nStrong}칸 중 도킹 신뢰도도 그 약물 1위였던 칸은 ${strongTop}칸입니다` : ''}`}
      right={<span className="chip bad">rule:cross-target</span>} style={{ marginBottom: 16 }}>
      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.6fr) minmax(300px, 1fr)', gap: 18 }}>
        <div style={{ overflowX: 'auto' }}>
          <div style={{ display: 'grid', gridTemplateColumns: `128px repeat(${T.length}, minmax(26px, 1fr))`, gap: 2, fontSize: 11 }}>
            <span />
            {T.map((t) => <span key={t.key} className="mono dim" title={`${t.target} · PDB ${t.pdb}`}
              style={{ fontSize: 9.5, writingMode: 'vertical-rl', transform: 'rotate(180deg)', height: 64, textAlign: 'left', color: sel?.tgt === t.key ? 'var(--c-sense)' : undefined }}>{t.gene}</span>)}
            {grid.ligs.map((l) => (
              <div key={l.name} style={{ display: 'contents' }}>
                <span style={{ fontSize: 11, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', alignSelf: 'center', color: sel?.lig === l.name ? 'var(--c-sense)' : 'var(--text-2)' }}>{cap(l.name)}</span>
                {T.map((t) => {
                  const v = grid.conf(l.name, t.key), native = t.native === l.name, on = sel?.lig === l.name && sel?.tgt === t.key
                  return (
                    <button key={t.key} onClick={() => pick(l.name, t.key)} title={`${cap(l.name)} → ${t.gene} · 신뢰도 ${v === null ? '–' : v.toFixed(2)}${native ? ' · 원래 표적' : ''}`}
                      style={{ position: 'relative', height: 22, borderRadius: 4, cursor: 'pointer', padding: 0, background: color(v), fontSize: 10, color: '#fff',
                        border: on ? '2px solid var(--jev)' : native ? '1px solid rgba(255,181,71,0.85)' : '1px solid transparent' }}>
                      {native ? '★' : ''}
                      {(() => { const e = ev(l.name, t.key); return e && <i title={`ChEMBL pChEMBL 중앙값 ${e.median} · ${e.n}건`} style={{ position: 'absolute', right: 2, top: 2, width: 6, height: 6, borderRadius: 3,
                        background: e.evidence === 'strong' ? '#f4f7ff' : 'transparent', border: '1.5px solid #f4f7ff', boxShadow: '0 0 0 1px rgba(5,9,18,0.8)' }} /> })()}
                    </button>
                  )
                })}
              </div>
            ))}
          </div>
          <div className="row" style={{ gap: 8, marginTop: 10, fontSize: 10.5 }}>
            <span className="mono dim">신뢰도</span>
            {[-3.5, -2, -0.5, 1].map((v) => <span key={v} className="row" style={{ gap: 4 }}><i style={{ display: 'inline-block', width: 14, height: 10, borderRadius: 2, background: color(v) }} /><span className="mono dim">{v}</span></span>)}
            <span className="mono" style={{ color: 'var(--jev)', marginLeft: 8 }}>★ 원래 표적</span>
            {evd && <><span className="row mono" style={{ gap: 4, marginLeft: 8 }}><i style={{ display: 'inline-block', width: 7, height: 7, borderRadius: 4, background: '#f4f7ff' }} />ChEMBL 실측 결합 (pChEMBL ≥ {evd.strong_pchembl})</span>
              <span className="row mono dim" style={{ gap: 4 }}><i style={{ display: 'inline-block', width: 7, height: 7, borderRadius: 4, border: '1.5px solid #f4f7ff' }} />측정됨 · 약함</span></>}
          </div>
        </div>

        {s && (
          <div className="stack fade-in" key={`${s.l}-${s.t.key}`} style={{ gap: 10 }}>
            <div className="mono dim" style={{ fontSize: 10.5 }}>에이전트가 쓴 주장</div>
            <div style={{ fontSize: 14.5, fontWeight: 600, lineHeight: 1.5 }}>
              “{cap(s.l)} 은(는) 표적 14개 중 {best?.t.gene} 에서 가장 높은 DiffDock 신뢰도({best?.v.toFixed(2)})를 보였으므로 {best?.t.gene} 에 선택적이다.”
            </div>
            <div className="stack" style={{ gap: 6 }}>
              <div className="row between"><span style={{ fontSize: 12.5 }}>1단 · 근거 ID</span><span className="chip ok">PASS</span></div>
              <div className="mono dim" style={{ fontSize: 10.5, marginTop: -4 }}>{best?.t.native === s.l ? `diffdock:redock:${best?.t.key}:pose:1` : `diffdock:matrix:${best?.t.key}|${s.l}:pose:1`}</div>
              <div className="row between"><span style={{ fontSize: 12.5 }}>2단 · 숫자 대조</span><span className="chip ok">PASS</span></div>
              <div className="mono dim" style={{ fontSize: 10.5, marginTop: -4 }}>원본 {best?.v.toFixed(3)} = 주장 {best?.v.toFixed(2)}</div>
              <div className="row between"><span style={{ fontSize: 12.5 }}>3단 · 추론 검사</span><span className="chip bad">REJECT</span></div>
              <div style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.55 }}>
                DiffDock 신뢰도는 포즈가 맞을 가능성이지 결합 세기가 아니고, 서로 다른 표적의 점수는 비교할 수 없습니다.
                {nativeT && (grid.rank(s.l, nativeT.key) === 1
                  ? <> 이번에는 원래 표적 <b>{nativeT.gene}</b> 이 1위였지만, 원래 표적이 단독 1위인 약물은 {grid.top1}/{grid.natives.length}개뿐이라 맞았더라도 근거가 되지 않습니다.</>
                  : <> 실제로 {cap(s.l)} 의 원래 표적 <b>{nativeT.gene}</b> 은 14개 중 <b style={{ color: 'var(--jev)' }}>{grid.rank(s.l, nativeT.key)}위</b>입니다.</>)}
              </div>
            </div>
            {evd && (() => {
              // 선택성 근거 표: 같은 유전자 표적(PARP1 · HTR2A 구조 2개)은 도킹 신뢰도가 높은 쪽 한 줄로
              const rows = Object.values(T.reduce<Record<string, { gene: string; key: string; v: number | null }>>((acc, t) => {
                const v = grid.conf(s.l, t.key), cur = acc[t.gene]
                if (!cur || (v ?? -99) > (cur.v ?? -99)) acc[t.gene] = { gene: t.gene, key: t.key, v }
                return acc
              }, {})).map((r) => ({ ...r, e: ev(s.l, r.key), rank: grid.rank(s.l, r.key) }))
                .sort((a, b) => (b.e ? (b.e.evidence === 'strong' ? 2 : 1) : 0) - (a.e ? (a.e.evidence === 'strong' ? 2 : 1) : 0) || (b.v ?? -99) - (a.v ?? -99))
              const strong = rows.filter((r) => r.e?.evidence === 'strong')
              return (
                <div className="stack" style={{ gap: 4 }}>
                  <div className="divider" />
                  <div className="row between"><span className="mono" style={{ fontSize: 10.5, letterSpacing: 1.2, color: 'var(--ok)' }}>선택성 근거 표 · {cap(s.l)}</span>
                    <span className="mono dim" style={{ fontSize: 10 }}>ChEMBL {evd.ligands[s.l]?.chembl ?? '없음'}</span></div>
                  <div className="mono dim" style={{ display: 'grid', gridTemplateColumns: '1fr 80px 132px 34px', gap: 6, fontSize: 9.5 }}>
                    <span>표적</span><span>도킹 신뢰도</span><span>ChEMBL 실측</span><span>근거</span></div>
                  {rows.slice(0, 7).map((r) => (
                    <div key={r.gene} style={{ display: 'grid', gridTemplateColumns: '1fr 80px 132px 34px', gap: 6, fontSize: 11.5, alignItems: 'center' }}>
                      <span style={{ fontWeight: r.e?.evidence === 'strong' ? 700 : 500 }}>{r.gene}</span>
                      <span className="num dim">{r.v === null ? '–' : r.v.toFixed(2)} <span style={{ fontSize: 9.5 }}>({r.rank}위)</span></span>
                      <span className="num" style={{ color: r.e ? (r.e.evidence === 'strong' ? 'var(--text)' : 'var(--text-2)') : 'var(--text-3)' }}>
                        {r.e ? `pChEMBL ${r.e.median} · ${r.e.n}건` : '기록 없음'}</span>
                      <span style={{ color: r.e?.evidence === 'strong' ? 'var(--ok)' : r.e ? 'var(--jev)' : 'var(--text-3)', fontSize: 11 }}>{STARS[r.e?.evidence ?? 'none']}</span>
                    </div>
                  ))}
                  <div className="mono dim" style={{ fontSize: 9.5 }}>★★★ 실측 결합(중앙값 ≥ {evd.strong_pchembl}) · ★★ 측정됨·약함 · ★ 도킹만 있음(탐색적) · 도킹 신뢰도는 등급에 넣지 않습니다</div>
                  <div style={{ marginTop: 6, padding: '8px 10px', borderRadius: 9, background: 'rgba(61,220,151,0.06)', border: '1px solid rgba(61,220,151,0.3)', fontSize: 12, lineHeight: 1.55 }}>
                    <span className="chip ok" style={{ fontSize: 9.5, marginRight: 6 }}>허용</span>
                    {strong.length === 0 ? <>이 표적들에는 {cap(s.l)} 의 결합을 뒷받침하는 ChEMBL 실측이 없습니다. 도킹만으로는 결합을 말할 수 없습니다.</>
                      : strong.length === 1 ? <>ChEMBL 실측(pChEMBL 중앙값 {strong[0].e!.median}, {strong[0].e!.n}건)이 {cap(s.l)} 의 <b>{strong[0].gene}</b> 결합을 뒷받침합니다.</>
                      : <>ChEMBL 실측이 {strong.map((r) => `${r.gene}(${r.e!.median})`).join(', ')} 결합을 모두 뒷받침합니다. 어느 쪽에 선택적인지는 같은 조건의 비교 실험이 있어야 말할 수 있습니다.</>}
                  </div>
                  <div style={{ padding: '8px 10px', borderRadius: 9, background: 'rgba(255,93,108,0.05)', border: '1px solid rgba(255,93,108,0.3)', fontSize: 12, lineHeight: 1.55 }}>
                    <span className="chip bad" style={{ fontSize: 9.5, marginRight: 6 }}>불허</span>
                    “{best?.t.gene} 에서 도킹 신뢰도가 가장 높으므로 {best?.t.gene} 에 선택적이다” — 위 크리틱 3단 반려와 같은 이유입니다
                  </div>
                </div>
              )
            })()}
            <div className="divider" />
            <div className="mono dim" style={{ fontSize: 10.5 }}>누른 칸</div>
            <div style={{ fontSize: 13 }}>{cap(s.l)} → <b>{s.t.gene}</b> · PDB {s.t.pdb} · 신뢰도 <span className="num">{s.v === null ? '–' : s.v.toFixed(2)}</span> · 이 약물 안에서 {s.r}위</div>
            <a className="btn" href={`#/d-diffdock?dock=${encodeURIComponent(`${s.t.key}|${s.l}`)}`} style={{ textDecoration: 'none', fontSize: 12.5, padding: '6px 12px', alignSelf: 'flex-start' }}>DiffDock 페이지에서 이 조합 직접 도킹해 보기 →</a>
            <Step2Handoff drug={s.l} />
          </div>
        )}
      </div>
    </Card>
  )
}
