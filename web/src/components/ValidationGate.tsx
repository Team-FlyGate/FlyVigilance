import { useEffect, useState } from 'react'
import { Card } from './ui'
import { getJSON } from '../lib/data'

// 도킹 검증 관문: 도킹 결과를 믿어도 되는지 구조 품질 · 반복 수렴 · 결정 포즈 대조로 판정합니다.
// 값은 validation.json(validate_docking.py) 그대로입니다. 같은 입력으로 DiffDock NIM 을 5번 불러 1순위 포즈가 매번 어디에 놓였는지 보여 주고,
// "반복해서 같은 자리에 모였다(수렴)"와 "그 자리가 결정 구조의 정답이다(결정 대조)"가 다른 질문이라는 점을 드러냅니다.

interface Row {
  key: string; drug: string; gene: string; pdb: string; error?: string
  structure: { method: string; resolution: number | null; organism: string | null; verdict: string; reasons: string[] }
  runs: number; top1_rmsd: (number | null)[]; top1_confidence: (number | null)[]
  confidence_mean: number | null; confidence_sd: number | null
  pairwise_median: number | null; converged: boolean; crystal_hits: number; grade: 'HIGH' | 'MEDIUM' | 'LOW'
}
interface File { results: Record<string, Row>; runs: number; success_A: number; converged_A: number; rules: [string, string][]; updated: string }

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)
const GRADE_COLOR = { HIGH: 'var(--ok)', MEDIUM: 'var(--jev)', LOW: 'var(--bad)' }
const ORDER = { HIGH: 0, MEDIUM: 1, LOW: 2 }
// RMSD 눈금: 0–16 Å 를 제곱근 눈금으로(2 Å 안쪽을 넓게)
const MAX = 16
const X = (v: number) => `${(Math.sqrt(Math.min(v, MAX)) / Math.sqrt(MAX)) * 100}%`

export default function ValidationGate() {
  const [f, setF] = useState<File | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  useEffect(() => { getJSON<File>('/discovery/data/validation.json').then(setF).catch(() => null) }, [])
  if (!f) return null
  const rows = Object.values(f.results).filter((r) => !r.error).sort((a, b) => ORDER[a.grade] - ORDER[b.grade] || b.crystal_hits - a.crystal_hits)
  const n = (g: Row['grade']) => rows.filter((r) => r.grade === g).length
  // 수렴했지만 틀린 자리: 결정 구조 없이 수렴만 보면 속는 경우
  const fooled = rows.filter((r) => r.converged && r.crystal_hits <= 1)
  const calls = rows.reduce((s, r) => s + r.runs, 0)
  return (
    <Card title="도킹 검증 관문 · 이 도킹 결과를 믿어도 되는가"
      sub={`같은 입력으로 DiffDock NIM 을 ${f.runs}번씩 불러(총 ${calls}회) 1순위 포즈가 매번 어디에 놓이는지 보고, 구조 품질과 결정 포즈 대조를 합쳐 등급을 매깁니다`}
      right={<div className="row" style={{ gap: 6 }}>
        <span className="chip ok">HIGH {n('HIGH')}</span><span className="chip jev">MEDIUM {n('MEDIUM')}</span><span className="chip bad">LOW {n('LOW')}</span>
      </div>}
      style={{ marginBottom: 16 }}>
      {fooled.length > 0 && (
        <div className="note" style={{ marginBottom: 12 }}>
          <b>수렴 ≠ 정답.</b> {fooled.map((r) => cap(r.drug)).join(', ')} 은(는) {f.runs}번 모두 거의 같은 자리에 모였지만(수렴) 그 자리가 결정 구조의 정답과 {f.success_A} Å 넘게 떨어져 있습니다.
          결정 구조가 없는 새 표적이라면 수렴만 보고 믿었을 사례라, 등급은 결정 대조를 우선합니다.
        </div>
      )}
      <div className="mono dim" style={{ display: 'grid', gridTemplateColumns: '150px 150px 1fr 92px 74px', gap: 12, fontSize: 10.5, padding: '0 4px 6px', textTransform: 'uppercase' }}>
        <span>약물 → 표적</span><span>구조 품질</span>
        <span style={{ position: 'relative' }}>반복 {f.runs}회 1순위 포즈 · 결정 리간드와 RMSD<span style={{ position: 'absolute', right: 0 }}>0 · 2 · 8 · 16 Å</span></span>
        <span>반복 간 수렴</span><span>등급</span>
      </div>
      {rows.map((r) => (
        <div key={r.key}>
          <button onClick={() => setOpen(open === r.key ? null : r.key)} style={{ all: 'unset', cursor: 'pointer', display: 'grid', gridTemplateColumns: '150px 150px 1fr 92px 74px', gap: 12, alignItems: 'center',
            width: '100%', boxSizing: 'border-box', padding: '8px 4px', borderTop: '1px solid var(--line)' }}>
            <span style={{ minWidth: 0 }}>
              <b style={{ fontFamily: 'var(--font)', fontSize: 13 }}>{cap(r.drug)}</b> <span className="dim" style={{ fontSize: 12 }}>→ {r.gene}</span>
              <div className="mono dim" style={{ fontSize: 10 }}>PDB {r.pdb}</div>
            </span>
            <span style={{ fontSize: 11.5 }}>
              <span className={`chip ${r.structure.verdict === '도킹 가능' ? 'ok' : 'jev'}`} style={{ fontSize: 10 }}>{r.structure.verdict}</span>
              <div className="mono dim" style={{ fontSize: 10, marginTop: 3 }}>{r.structure.method} {r.structure.resolution ?? '–'} Å</div>
            </span>
            <span style={{ position: 'relative', height: 22 }}>
              <span style={{ position: 'absolute', left: 0, right: 0, top: 10, height: 2, background: 'rgba(120,170,255,0.12)' }} />
              <span style={{ position: 'absolute', left: 0, width: X(f.success_A), top: 4, height: 14, background: 'rgba(61,220,151,0.12)', borderRight: '1px dashed rgba(61,220,151,0.6)' }} />
              {r.top1_rmsd.map((v, i) => v !== null && (
                <span key={i} title={`반복 ${i + 1}: ${v} Å · 신뢰도 ${r.top1_confidence[i] ?? '–'}`}
                  style={{ position: 'absolute', left: `calc(${X(v)} - 5px)`, top: 6, width: 10, height: 10, borderRadius: 5,
                    background: v <= f.success_A ? 'var(--ok)' : 'var(--bad)', opacity: 0.8, boxShadow: '0 0 0 1px rgba(5,9,18,0.9)' }} />
              ))}
            </span>
            <span className="num" style={{ fontSize: 12, color: r.converged ? 'var(--text)' : 'var(--text-3)' }}>
              {r.converged ? '수렴' : '흩어짐'} <span className="dim" style={{ fontSize: 10.5 }}>{r.pairwise_median ?? '–'} Å</span>
            </span>
            <span><span className="chip" style={{ color: GRADE_COLOR[r.grade], borderColor: GRADE_COLOR[r.grade], fontSize: 10.5 }}>{r.grade}</span>
              <div className="mono dim" style={{ fontSize: 10, marginTop: 3 }}>정답 {r.crystal_hits}/{r.runs}</div></span>
          </button>
          {open === r.key && (
            <div className="fade-in mono" style={{ fontSize: 11, color: 'var(--text-2)', padding: '2px 4px 10px', display: 'grid', gap: 3 }}>
              <span>구조: {r.structure.method} {r.structure.resolution ?? '–'} Å · {r.structure.organism ?? '생물종 미상'}{r.structure.reasons.length ? ` · 주의: ${r.structure.reasons.join(', ')}` : ''}</span>
              <span>반복별 1순위 RMSD: {r.top1_rmsd.map((v) => (v === null ? '–' : v.toFixed(2))).join(' · ')} Å</span>
              <span>반복별 1순위 신뢰도: {r.top1_confidence.map((v) => (v === null ? '–' : v.toFixed(2))).join(' · ')} (평균 {r.confidence_mean ?? '–'}, 표준편차 {r.confidence_sd ?? '–'}) — 같은 입력에서도 신뢰도가 흔들립니다</span>
            </div>
          )}
        </div>
      ))}
      <div className="stack" style={{ gap: 3, marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--line)' }}>
        <span className="eyebrow" style={{ color: 'var(--text-3)' }}>판정 규칙</span>
        {f.rules.map(([k, v]) => <div key={k} style={{ fontSize: 11.5 }}><b className="mono" style={{ display: 'inline-block', width: 70, color: GRADE_COLOR[k as Row['grade']] ?? 'var(--text-2)' }}>{k}</b><span className="dim">{v}</span></div>)}
        <span className="mono dim" style={{ fontSize: 10, marginTop: 4 }}>점 하나 = 반복 한 번의 1순위 포즈 · 초록 띠 = 결정 리간드와 {f.success_A} Å 이내 · 눈금은 제곱근 · 측정 {f.updated}</span>
      </div>
    </Card>
  )
}
