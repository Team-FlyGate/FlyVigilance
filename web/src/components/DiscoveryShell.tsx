// STEP 1 FlyDiscovery 다섯 화면이 함께 쓰는 틀입니다.
// 왼쪽 위: 관제 센터와 같은 라이브 커넥텀(30 Hz 속도 모델) + 보상 신호 계기
// 가운데: 단계별 분자 시각화, 오른쪽: NIM 엔드포인트·따라간 NVIDIA 공식 스킬·요청 요약·진행·지표·지난 측정
import { useEffect, useRef, useState, type ReactNode } from 'react'
import BrainView from './BrainView'
import TargetPicker from './TargetPicker'
import { Card, PageHead } from './ui'
import { LayerMeter } from '../pages/MissionControl'
import { useBrain } from '../lib/brain'
import { CHANNEL_COLOR, fmt } from '../lib/data'
import type { Sim } from '../lib/connectome'
import { REWARD_NOTE, SOURCE_LABEL, fmtS, setReward, useDiscovery, type Catalog, type Envelope, type Skill } from '../lib/discovery'

export const STEP_ORDER: { id: string; label: string; en: string }[] = [
  { id: 'msa', label: 'MSA 탐색', en: 'MSA-Search' },
  { id: 'openfold3', label: '구조 예측', en: 'OpenFold3' },
  { id: 'diffdock', label: '결합 포즈', en: 'DiffDock' },
  { id: 'boltz2', label: '친화도', en: 'Boltz-2' },
  { id: 'critic', label: '크리틱', en: 'Nemotron critic' },
]

/** 결합력 측정값을 보상 회로 자극으로 옮깁니다(버섯체 KC·MBON 과 도파민성 PAM/DAN = 커넥텀 memory 층). */
export function pulseReward(sim: Sim | null, strength: number, label: string, source: string) {
  const s = Math.max(0, Math.min(1, strength))
  setReward(s, label, source)
  if (!sim) return
  // 세기는 보상 회로(memory 층: 버섯체 KC·MBON·도파민성 PAM/DAN)에 실리고, 조금 뒤 숙고 층으로 번집니다
  sim.stimulate('layer', 'memory', 0.35 + 0.95 * s, Math.round(6 + 20 * s))
  setTimeout(() => sim.stimulate('layer', 'deliberate', 0.3 + 0.5 * s, Math.round(4 + 8 * s)), 300)
}

export function stimulateLayer(sim: Sim | null, layer: string, amp: number, steps = 8) {
  sim?.stimulate('layer', layer, amp, steps)
}

function RewardGauge() {
  const { reward } = useDiscovery()
  const [shown, setShown] = useState(0)
  useEffect(() => {
    let raf = 0
    const run = () => {
      setShown((v) => {
        const target = reward.value * Math.max(0, 1 - (Date.now() - reward.at) / 14000)
        return v + (target - v) * 0.12
      })
      raf = requestAnimationFrame(run)
    }
    raf = requestAnimationFrame(run)
    return () => cancelAnimationFrame(raf)
  }, [reward])
  const pct = Math.round(shown * 100)
  const color = shown > 0.66 ? '#ff4fd8' : shown > 0.33 ? '#ffb547' : '#6c7aa8'
  return (
    <div style={{ padding: '10px 12px', borderRadius: 12, background: 'rgba(10,16,30,0.62)', border: '1px solid var(--line)' }}>
      <div className="row between" style={{ marginBottom: 6 }}>
        <span className="eyebrow" style={{ color: 'var(--text-2)', fontSize: 10 }}>보상 신호 · Reward signal</span>
        <span className="num" style={{ fontSize: 12, color }}>{pct}%</span>
      </div>
      <div className="pbar" style={{ height: 10 }}>
        <i style={{ width: `${pct}%`, background: color, boxShadow: `0 0 14px ${color}`, transition: 'none' }} />
      </div>
      <div className="note" style={{ marginTop: 6 }}>
        결합력 → 도파민성 보상 뉴런(PAM) 자극 강도 · {reward.label || '측정 대기'}
        {reward.source && <span className="mono dim"> · {reward.source}</span>}
      </div>
    </div>
  )
}

export function ConnectomePanel({ height = 300 }: { height?: number }) {
  const { sim, conn, tick } = useBrain()
  return (
    <Card className="flush" style={{ overflow: 'hidden' }}>
      <div style={{ position: 'relative' }}>
        <div className="disc-brain-head" style={{ position: 'absolute', left: 14, top: 12, zIndex: 2, pointerEvents: 'none' }}>
          <div className="eyebrow" style={{ color: 'var(--text-3)', fontSize: 9 }}>Live connectome · 30 Hz</div>
          <div className="mono" style={{ fontSize: 9.5, marginTop: 3, lineHeight: 1.5, color: 'var(--text-2)' }}>
            {conn ? <>{fmt.int(conn.meta.neurons)} neurons<br />{fmt.compact(conn.meta.edges)} connections · {fmt.compact(conn.meta.synapses)} synapses</> : '…'}
          </div>
          <div className="mono dim" style={{ fontSize: 9.5, marginTop: 2 }}>t = {tick} · active {sim ? fmt.int(sim.spikes) : 0}</div>
        </div>
        <BrainView height={height} view="front" bloom={0.45} />
      </div>
      <div style={{ padding: '10px 12px 12px', borderTop: '1px solid var(--line)' }}>
        <RewardGauge />
        <div className="row between" style={{ margin: '10px 0 6px' }}>
          <span className="eyebrow" style={{ color: 'var(--text-2)', fontSize: 10 }}>Layer activity</span>
          <span className="mono dim" style={{ fontSize: 9.5 }}>neurons</span>
        </div>
        <LayerMeter />
        <div className="row wrap" style={{ gap: 5, marginTop: 10 }}>
          <span className="eyebrow" style={{ color: 'var(--text-3)', fontSize: 9.5, width: '100%' }}>Inject data stream</span>
          {conn?.meta.channels.filter((c) => c.key !== 'none').map((c) => (
            <button key={c.key} className="chip" style={{ cursor: 'pointer', fontSize: 10, color: CHANNEL_COLOR[c.key], borderColor: CHANNEL_COLOR[c.key] + '55' }}
              onClick={() => sim?.stimulate('channel', c.key, 1.2, 12)} title={`${c.modality} sensory neurons (${c.neurons})`}>
              {c.name}
            </button>
          ))}
        </div>
        <div className="note" style={{ marginTop: 10 }}>{REWARD_NOTE}</div>
      </div>
    </Card>
  )
}

export function RunButton({ busy, onClick, label = '라이브 실행', sub, fresh, setFresh }: {
  busy: boolean; onClick: () => void; label?: string; sub?: ReactNode
  fresh?: boolean; setFresh?: (v: boolean) => void
}) {
  return (
    <div className="stack" style={{ gap: 6 }}>
      <button className="btn nv" style={{ width: '100%', padding: '12px 16px', fontSize: 14 }} disabled={busy} onClick={onClick}>
        {busy ? <span className="row" style={{ gap: 8, justifyContent: 'center' }}><span className="spin" />실행 중…</span> : label}
      </button>
      {sub && <div className="note" style={{ textAlign: 'center' }}>{sub}</div>}
      {setFresh && (
        <label className="row" style={{ gap: 7, cursor: 'pointer', justifyContent: 'center' }}>
          <input type="checkbox" checked={Boolean(fresh)} onChange={(e) => setFresh(e.target.checked)} />
          <span className="note">같은 입력이어도 NIM 을 다시 부릅니다(캐시 무시)</span>
        </label>
      )}
    </div>
  )
}

export function Progress({ env, busy, elapsed }: { env: Envelope | null; busy: boolean; elapsed: number }) {
  const state = busy ? (env?.state === 'pending' ? '계산 중(큐)' : '요청 보냄')
    : env ? (env.source === 'cache' ? '완료 · 같은 입력 캐시' : env.source === 'measured' ? '지난 측정으로 대체' : '완료') : '대기'
  const color = busy ? 'var(--warn)' : env ? (env.source === 'measured' ? 'var(--warn)' : 'var(--ok)') : 'var(--text-3)'
  return (
    <div className="stack" style={{ gap: 6 }}>
      <div className="row between">
        <span className="row" style={{ gap: 7 }}>
          <span className={`dot ${busy ? 'pulse' : ''}`} style={{ background: color, boxShadow: `0 0 10px ${color}` }} />
          <span style={{ fontSize: 12.5 }}>{state}</span>
        </span>
        <span className="num dim" style={{ fontSize: 11.5 }}>{busy ? `${elapsed.toFixed(1)}초` : env?.source === 'cache' ? '캐시' : fmtS(env?.elapsed_s)}</span>
      </div>
      <div className="pbar" style={{ height: 5 }}>
        <i className={busy ? 'shimmer' : ''} style={{ width: busy ? '100%' : env ? '100%' : '0%', background: busy ? 'transparent' : color, opacity: busy ? 1 : 0.8 }} />
      </div>
      {env?.req_id && <div className="mono dim" style={{ fontSize: 9.5 }}>NVCF 요청 {env.req_id.slice(0, 18)}… · /v1/status 로 이어 받는 중</div>}
    </div>
  )
}

export function SkillBox({ skills }: { skills: Skill[] }) {
  return (
    <div className="stack" style={{ gap: 7 }}>
      {skills.map((s) => (
        <a key={s.name + s.repo} className="chip nv" href={s.url} target="_blank" rel="noreferrer"
          style={{ textDecoration: 'none', display: 'block', padding: '7px 9px', lineHeight: 1.4 }}>
          <b style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{s.name}</b>
          <div className="dim" style={{ fontSize: 10, color: 'var(--text-3)' }}>{s.repo}</div>
          <div style={{ fontSize: 10.5, color: 'var(--text-2)', marginTop: 2 }}>{s.step}</div>
        </a>
      ))}
    </div>
  )
}

export function SourceChip({ env }: { env: Envelope | null }) {
  if (!env?.source) return null
  const s = SOURCE_LABEL[env.source] ?? { text: env.source, cls: '' }
  return <span className={`chip ${s.cls}`} style={{ fontSize: 10.5 }}>{s.text}</span>
}

export const pathOf = (url?: string) => (url ? url.replace(/^https?:\/\/[^/]+/, '') : '')

export function KV({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <div className="stack" style={{ gap: 5 }}>
      {rows.map(([k, v], i) => (
        <div key={i} className="row between" style={{ gap: 10, alignItems: 'baseline' }}>
          <span className="mono dim" style={{ fontSize: 10.5, letterSpacing: 0.4, textTransform: 'uppercase', flex: 'none' }}>{k}</span>
          <span className="num" style={{ fontSize: 12, textAlign: 'right', wordBreak: 'break-word' }}>{v}</span>
        </div>
      ))}
    </div>
  )
}

export function StepNav({ current }: { current: string }) {
  const i = STEP_ORDER.findIndex((s) => s.id === current)
  const next = STEP_ORDER[i + 1]
  return (
    <div className="row between wrap" style={{ gap: 10 }}>
      <div className="row wrap" style={{ gap: 5 }}>
        {STEP_ORDER.map((s, k) => (
          <a key={s.id} href={`#/${s.id}`} className="chip" style={{
            textDecoration: 'none', fontSize: 10.5, opacity: k <= i ? 1 : 0.55,
            color: k === i ? 'var(--text)' : 'var(--text-2)', borderColor: k === i ? 'rgba(118,185,0,0.6)' : 'var(--line-2)',
            background: k === i ? 'rgba(118,185,0,0.12)' : undefined,
          }}>{k + 1}. {s.label}</a>
        ))}
      </div>
      {next && <a className="btn ghost" href={`#/${next.id}`} style={{ textDecoration: 'none', fontSize: 12.5 }}>다음 단계로 · {next.label} →</a>}
    </div>
  )
}

export function StepPage({ eyebrow, title, lede, right, current, center, side, footer, cat }: {
  eyebrow: string; title: ReactNode; lede: ReactNode; right?: ReactNode; current: string
  center: ReactNode; side: ReactNode; footer?: ReactNode; cat?: Catalog | null
}) {
  const ref = useRef<HTMLDivElement>(null)
  return (
    <div className="page" ref={ref}>
      <PageHead eyebrow={eyebrow} title={title} lede={lede} right={right} />
      <div style={{ marginBottom: 14 }}><StepNav current={current} /></div>
      <TargetPicker cat={cat ?? null} />
      <div className="disc-grid">
        <div className="stack" style={{ gap: 14 }}>
          <ConnectomePanel />
        </div>
        <div className="stack" style={{ gap: 14, minWidth: 0 }}>{center}</div>
        <div className="stack" style={{ gap: 14 }}>{side}</div>
      </div>
      {footer}
    </div>
  )
}
