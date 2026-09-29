import { useEffect, useMemo, useState } from 'react'
import { Card } from './ui'
import { getJSON } from '../lib/data'
import { t } from '../lib/i18n'

// 포즈 순위 신뢰도: DiffDock 이 돌려준 포즈 5개를 1순위만 보지 않고 모두 결정 구조와 대조합니다.
// 값은 redock.json(재도킹, 공결정 리간드를 다시 넣은 대조 실험) 그대로입니다.
// 여기서 나오는 것은 "자리를 못 찾았다" 와 "자리는 찾았는데 순위를 잘못 매겼다" 가 다른 실패라는 점입니다.

interface Pose { rank: number; confidence: number | null; rmsd: number | null }
interface Row { drug: string; gene: string; pdb: string; poses: Pose[]; top1_rmsd: number | null; best_rmsd: number | null; top1_success: boolean }
interface File { results: Record<string, Row>; criterion: string; updated: string }

const OK = 2.0
const MAX = 16
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)
// 0–16 Å 를 제곱근 눈금으로(2 Å 안쪽을 넓게). 검증 관문 카드와 같은 눈금입니다
const X = (v: number) => `${(Math.sqrt(Math.min(v, MAX)) / Math.sqrt(MAX)) * 100}%`

export default function PoseRanking() {
  const [f, setF] = useState<File | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  useEffect(() => { getJSON<File>('/discovery/data/redock.json').then(setF).catch(() => null) }, [])
  const rows = useMemo(() => {
    if (!f) return []
    return Object.entries(f.results)
      .map(([key, r]) => {
        const rms = r.poses.filter((p) => p.rmsd !== null)
        const best = rms.length ? rms.reduce((a, b) => (b.rmsd! < a.rmsd! ? b : a)) : null
        return { key, ...r, best, betterBelow: !!best && best.rank !== 1 && best.rmsd! < (r.top1_rmsd ?? 99) - 0.01 }
      })
      .filter((r) => r.top1_rmsd !== null)
      // 순위를 잘못 매긴 사례(1순위 실패 · 하위 포즈 통과)를 위로
      .sort((a, b) => Number(!a.top1_success && !!a.best && a.best.rmsd! <= OK) * -2 + Number(!b.top1_success && !!b.best && b.best.rmsd! <= OK) * 2
        || Number(b.betterBelow) - Number(a.betterBelow))
  }, [f])
  if (!f || !rows.length) return null
  const better = rows.filter((r) => r.betterBelow).length
  const misranked = rows.filter((r) => !r.top1_success && r.best && r.best.rmsd! <= OK)

  return (
    <Card title={t('포즈 순위는 얼마나 믿을 수 있나', 'How much can the pose ranking be trusted?')}
      sub={t(`DiffDock 이 돌려준 포즈 5개를 1순위만 보지 않고 모두 결정 구조와 대조했습니다 · 기준 ${OK} Å · 재도킹 ${rows.length}건`,
        `We compared all five DiffDock poses against the crystal structure, not just the top-ranked one · criterion ${OK} Å · ${rows.length} redockings`)}
      right={<span className="chip bad">rule:D2</span>} style={{ marginBottom: 16 }}>
      <div className="note" style={{ marginBottom: 12 }}>
        <b>{t(`${rows.length}건 중 ${better}건`, `In ${better} of ${rows.length} cases`)}</b>
        {t(' 에서 하위 순위 포즈가 1순위보다 정답에 더 가까웠습니다. ', ' a lower-ranked pose landed closer to the truth than the top-ranked one. ')}
        {misranked.length > 0 && (
          <>
            {t(`그중 ${misranked.length}건(`, `In ${misranked.length} of those (`)}
            {misranked.map((r) => cap(r.drug)).join(', ')}
            {t(`)은 1순위만 보면 ${OK} Å 기준 실패지만, 하위 포즈는 기준 안에 들어왔습니다. `,
              `) the top-ranked pose fails the ${OK} Å criterion while a lower-ranked pose falls inside it. `)}
          </>
        )}
        {t('자리를 못 찾은 것과 자리는 찾았는데 순위를 잘못 매긴 것은 다른 실패입니다. 신뢰도는 포즈 순위 점수이지 결합 세기가 아닙니다(D2).',
          'Failing to find the site and finding it but ranking it wrong are different failures. Confidence is a pose-ranking score, not binding strength (D2).')}
      </div>
      <div className="mono dim" style={{ display: 'grid', gridTemplateColumns: '150px 1fr 92px 92px', gap: 12, fontSize: 10.5, padding: '0 4px 6px', textTransform: 'uppercase' }}>
        <span>{t('약물 → 표적', 'drug → target')}</span>
        <span style={{ position: 'relative' }}>{t('포즈 5개 · 결정 리간드와 RMSD', 'five poses · RMSD vs crystal ligand')}<span style={{ position: 'absolute', right: 0 }}>0 · 2 · 8 · 16 Å</span></span>
        <span>{t('1순위', 'top-1')}</span><span>{t('가장 가까운 포즈', 'closest pose')}</span>
      </div>
      {rows.map((r) => (
        <div key={r.key}>
          <button onClick={() => setOpen(open === r.key ? null : r.key)} style={{ all: 'unset', cursor: 'pointer', display: 'grid', gridTemplateColumns: '150px 1fr 92px 92px', gap: 12,
            alignItems: 'center', width: '100%', boxSizing: 'border-box', padding: '8px 4px', borderTop: '1px solid var(--line)' }}>
            <span style={{ minWidth: 0 }}>
              <b style={{ fontFamily: 'var(--font)', fontSize: 13 }}>{cap(r.drug)}</b> <span className="dim" style={{ fontSize: 12 }}>→ {r.gene}</span>
              <div className="mono dim" style={{ fontSize: 10 }}>PDB {r.pdb}</div>
            </span>
            <span style={{ position: 'relative', height: 22 }}>
              <span style={{ position: 'absolute', left: 0, right: 0, top: 10, height: 2, background: 'rgba(120,170,255,0.12)' }} />
              <span style={{ position: 'absolute', left: 0, width: X(OK), top: 4, height: 14, background: 'rgba(61,220,151,0.12)', borderRight: '1px dashed rgba(61,220,151,0.6)' }} />
              {r.poses.map((p) => p.rmsd !== null && (
                <span key={p.rank} title={`pose ${p.rank} · ${p.rmsd} Å · ${t('신뢰도', 'confidence')} ${p.confidence ?? '–'}`}
                  style={{ position: 'absolute', left: `calc(${X(p.rmsd)} - ${p.rank === 1 ? 6 : 4}px)`, top: p.rank === 1 ? 5 : 7,
                    width: p.rank === 1 ? 12 : 8, height: p.rank === 1 ? 12 : 8, borderRadius: 6,
                    background: p.rank === 1 ? (p.rmsd <= OK ? 'var(--ok)' : 'var(--bad)') : 'transparent',
                    border: p.rank === 1 ? 'none' : `1.5px solid ${p.rmsd <= OK ? 'var(--ok)' : 'var(--bad)'}`,
                    boxShadow: '0 0 0 1px rgba(5,9,18,0.9)', opacity: p.rank === 1 ? 1 : 0.85 }} />
              ))}
            </span>
            <span className="num" style={{ fontSize: 12, color: r.top1_success ? 'var(--ok)' : 'var(--bad)' }}>{r.top1_rmsd?.toFixed(2)} Å</span>
            <span className="num" style={{ fontSize: 12, color: r.best && r.best.rmsd! <= OK ? 'var(--ok)' : 'var(--text-2)' }}>
              {r.best?.rmsd?.toFixed(2)} Å <span className="dim" style={{ fontSize: 10 }}>({t('순위', 'rank')} {r.best?.rank})</span>
            </span>
          </button>
          {open === r.key && (
            <div className="fade-in mono" style={{ fontSize: 11, color: 'var(--text-2)', padding: '2px 4px 10px', display: 'grid', gap: 3 }}>
              <span>{t('포즈별 RMSD', 'RMSD per pose')}: {r.poses.map((p) => (p.rmsd === null ? '–' : p.rmsd.toFixed(2))).join(' · ')} Å</span>
              <span>{t('포즈별 신뢰도', 'confidence per pose')}: {r.poses.map((p) => (p.confidence === null ? '–' : p.confidence.toFixed(3))).join(' · ')}
                {' — '}{t('신뢰도 순서와 정답 거리 순서가 같지 않습니다', 'the confidence order does not match the order of closeness to the truth')}</span>
            </div>
          )}
        </div>
      ))}
      <div className="mono dim" style={{ fontSize: 10, marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--line)' }}>
        {t(`꽉 찬 점 = 1순위 포즈 · 빈 원 = 2~5순위 · 초록 = 결정 리간드와 ${OK} Å 이내 · 눈금은 제곱근 · ${f.criterion} · 측정 ${f.updated}`,
          `filled dot = top-ranked pose · hollow = ranks 2–5 · green = within ${OK} Å of the crystal ligand · square-root scale · ${f.criterion} · measured ${f.updated}`)}
      </div>
    </Card>
  )
}
