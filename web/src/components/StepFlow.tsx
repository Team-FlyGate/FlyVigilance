import { useState } from 'react'
import { STEP_KIND, liveFor, fmtS, runPipeline, useDiscovery, type BoltzResult, type DockResult, type MsaResult, type Of3Result } from '../lib/discovery'
import { useBrain } from '../lib/brain'
import { STEP_PAGES } from '../pages/Discovery'
import { t } from '../lib/i18n'
import type { StepId } from './HeroDocking'

// 단계 사이 흐름 띠: 이번 세션에서 각 단계가 무엇을 받아 무엇을 냈는지 한 줄로 보여 줍니다.
// 아직 돌리지 않은 단계는 흐리게 두고, 누르면 그 단계 페이지로 갑니다. 값은 모두 이번 실행 결과 그대로입니다.

const ORDER: StepId[] = ['msa', 'of3', 'dd', 'bz', 'critic']
const NAME: Record<StepId, string> = { msa: 'MSA-Search', of3: 'OpenFold3', dd: 'DiffDock', bz: 'Boltz-2', critic: t('크리틱', 'Critic') }
const n = (v: number | null | undefined, d = 2) => (v === null || v === undefined ? '–' : v.toFixed(d))

const KIND_NAME: Record<string, string> = { msa: 'MSA-Search', openfold3: 'OpenFold3', diffdock: 'DiffDock', boltz2: 'Boltz-2', critic: t('크리틱', 'Critic') }

export default function StepFlow({ step }: { step: StepId }) {
  const store = useDiscovery()
  const { sim } = useBrain()
  // 다섯 단계 이어 실행: 앞 단계 결과를 다음 단계 입력으로 넘기며 차례로 NIM 을 부릅니다
  const [busy, setBusy] = useState(false)
  const [at, setAt] = useState<string | null>(null)
  const [fails, setFails] = useState<{ kind: string; error: string }[]>([])
  const runAll = async () => {
    setBusy(true); setFails([]); setAt(null)
    sim?.stimulate('layer', 'sense', 1.1, 12)
    const { failed } = await runPipeline({
      onStep: (kind, state) => {
        if (state === 'run') setAt(KIND_NAME[kind] ?? String(kind))
        if (state === 'done') sim?.stimulate('layer', kind === 'critic' ? 'critic' : 'action', 0.9, 10)
      },
    })
    setFails(failed); setAt(null); setBusy(false)
  }
  const cell = (id: StepId): { out: string; gave?: string } | null => {
    const kind = STEP_KIND[id]
    if (!kind) {
      // 크리틱은 앞 네 단계 결과를 그대로 받습니다
      const got = ORDER.slice(0, 4).filter((x) => store.runs[STEP_KIND[x]!]).length
      return got ? { out: t(`앞 ${got}단계 결과로 주장 판정`, `judges claims from ${got} earlier steps`) } : null
    }
    const env = liveFor(kind, store)
    const r = env?.state === 'done' ? env.result : undefined
    if (!r) return null
    // 소요 시간이 결과에 없으면 서버가 잰 왕복 시간(elapsed_s)으로 채웁니다
    const secs = (r as { seconds?: number | null }).seconds ?? env?.elapsed_s
    if (kind === 'msa') { const m = r as MsaResult; return { out: t(`상동 서열 ${m.homologs}개 · ${fmtS(secs)}`, `${m.homologs} homologs · ${fmtS(secs)}`), gave: t('정렬(a3m)', 'alignment (a3m)') } }
    if (kind === 'openfold3') {
      const o = r as Of3Result
      return { out: `pLDDT ${n(o.scores.plddt ?? o.mean_plddt, 1)}${o.ca_rmsd !== null ? ` · Cα RMSD ${n(o.ca_rmsd)} Å` : ''}`,
        gave: o.structure_key ? t('예측 구조', 'predicted structure') : undefined }
    }
    if (kind === 'diffdock') {
      const d = r as DockResult
      return { out: `${t('신뢰도', 'confidence')} ${n(d.top1_confidence, 3)}${d.redock ? ` · RMSD ${n(d.top1_rmsd)} Å` : ''}`,
        gave: d.receptor_predicted ? t('예측 구조에 도킹함', 'docked into the prediction') : undefined }
    }
    const b = r as BoltzResult
    return { out: `pIC50 ${n(b.affinity.pic50)}${b.chembl ? ` · ${t('실측', 'measured')} ${b.chembl.median_pchembl}` : ''}` }
  }
  const cells = ORDER.map(cell)
  return (
    <div className="card" style={{ padding: '10px 14px', marginBottom: 14 }}>
      <div className="row between" style={{ marginBottom: 8, gap: 10 }}>
        <span className="mono" style={{ fontSize: 10.5, letterSpacing: 1.3, color: 'var(--nvidia)' }}>{t('이번 세션 흐름 · 앞 단계 결과가 다음 단계 입력이 됩니다', 'This session · each step feeds the next')}</span>
        <div className="row" style={{ gap: 8, alignItems: 'center' }}>
          <span className="mono dim" style={{ fontSize: 10 }}>{busy ? t(`${at} 실행 중…`, `Running ${at}…`) : t('빈 칸은 아직 실행하지 않은 단계입니다', 'Empty cells are steps not run yet')}</span>
          <button className="btn nv" style={{ fontSize: 11.5, padding: '4px 10px' }} disabled={busy} onClick={() => void runAll()}>
            {busy ? t('실행 중…', 'Running…') : t('다섯 단계 이어 실행', 'Run all five steps')}</button>
        </div>
      </div>
      {!busy && fails.length > 0 && (
        <div style={{ fontSize: 11.5, color: 'var(--bad)', marginBottom: 8 }}>
          {fails.map((f) => `${KIND_NAME[f.kind] ?? f.kind}: ${f.error}`).join(' · ')}
        </div>
      )}
      <div className="row wrap" style={{ gap: 6, alignItems: 'stretch' }}>
        {ORDER.map((id, i) => {
          const c = cells[i], on = id === step
          return (
            <div key={id} className="row" style={{ gap: 6, alignItems: 'center' }}>
              <a href={`#/${STEP_PAGES[id]}`} style={{ textDecoration: 'none', color: 'inherit', display: 'block', minWidth: 132, padding: '6px 10px', borderRadius: 9,
                background: on ? 'rgba(55,230,255,0.08)' : c ? 'rgba(10,16,30,0.5)' : 'transparent',
                border: `1px solid ${on ? 'rgba(55,230,255,0.5)' : c ? 'var(--line)' : 'var(--line2, rgba(120,170,255,0.12))'}`, opacity: c ? 1 : 0.45 }}>
                <div className="mono" style={{ fontSize: 9.5, letterSpacing: 1.1, color: on ? 'var(--c-sense)' : 'var(--text-3)' }}>{`0${i + 1} ${NAME[id]}`}</div>
                <div className="num" style={{ fontSize: 11.5, marginTop: 2, color: c ? 'var(--text)' : 'var(--text-3)' }}>{c ? c.out : t('대기', 'not run')}</div>
              </a>
              {i < ORDER.length - 1 && (
                <span className="mono dim" style={{ fontSize: 9.5, textAlign: 'center', minWidth: 54, lineHeight: 1.25 }}>
                  →{c?.gave ? <div style={{ color: 'var(--nvidia)' }}>{c.gave}</div> : null}
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
