// STEP 1-1 MSA 탐색: NVIDIA BioNeMo MSA-Search NIM 을 실제로 부르고 정렬을 그립니다.
import { useEffect, useRef, useState } from 'react'
import { Card } from '../components/ui'
import { KV, pathOf, Progress, RunButton, SkillBox, SourceChip, StepPage, pulseReward } from '../components/DiscoveryShell'
import { useBrain } from '../lib/brain'
import { fmtS, getCatalog, runParams, rewardFromDepth, runStep, saveRun, useDiscovery, type Catalog, type Envelope, type MsaResult } from '../lib/discovery'

// 잔기를 성질별로 묶어 색을 줍니다(정렬 그림의 관례). 질의와 같은 잔기만 진하게 칠합니다.
const AA_GROUP: Record<string, string> = {
  A: 'hydro', V: 'hydro', L: 'hydro', I: 'hydro', M: 'hydro', F: 'arom', W: 'arom', Y: 'arom',
  K: 'pos', R: 'pos', H: 'pos', D: 'neg', E: 'neg', S: 'polar', T: 'polar', N: 'polar', Q: 'polar',
  C: 'special', G: 'special', P: 'special',
}
const GROUP_COLOR: Record<string, string> = {
  hydro: '#76b900', arom: '#a58bff', pos: '#37e6ff', neg: '#ff5d6c', polar: '#ffb547', special: '#ff4fd8',
}

function Alignment({ res, reveal }: { res: MsaResult; reveal: number }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const [w, setW] = useState(880)
  useEffect(() => {
    const el = ref.current?.parentElement
    if (!el) return
    const ro = new ResizeObserver((e) => setW(Math.max(320, e[0].contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  useEffect(() => {
    const cv = ref.current
    if (!cv) return
    const rows = res.rows
    const L = res.query_len
    const rowH = 7
    const consLabel = 12
    const consH = 26
    const histH = 46
    const h = consLabel + consH + 8 + rows.length * rowH + 14 + histH
    const dpr = Math.min(window.devicePixelRatio, 2)
    cv.width = w * dpr
    cv.height = h * dpr
    cv.style.width = `${w}px`
    cv.style.height = `${h}px`
    const g = cv.getContext('2d')!
    g.setTransform(dpr, 0, 0, dpr, 0, 0)
    g.clearRect(0, 0, w, h)
    const cw = w / L
    // 보존도 막대
    for (let i = 0; i < L; i++) {
      const c = res.conservation[i] ?? 0
      g.fillStyle = `rgba(55,230,255,${0.18 + 0.72 * c})`
      const bh = 3 + c * (consH - 3)
      g.fillRect(i * cw, consLabel + consH - bh, Math.max(cw, 0.7), bh)
    }
    g.fillStyle = 'rgba(232,238,252,0.55)'
    g.font = '9px ui-monospace, monospace'
    g.fillText('열별 보존도 (질의 잔기와 같은 서열의 비율)', 2, 9)
    const top = consLabel + consH + 8
    // 정렬 행
    const shown = Math.round(rows.length * reveal)
    for (let r = 0; r < shown; r++) {
      const s = rows[r].seq
      const y = top + r * rowH
      for (let i = 0; i < L; i++) {
        const ch = s[i]
        if (!ch || ch === '-' || ch === '.') continue
        const same = ch === res.query[i]
        const col = GROUP_COLOR[AA_GROUP[ch]] ?? '#6c7aa8'
        g.fillStyle = same ? col : 'rgba(120,170,255,0.18)'
        g.globalAlpha = same ? 0.45 + 0.5 * (res.conservation[i] ?? 0) : 0.35
        g.fillRect(i * cw, y, Math.max(cw, 0.7), rowH - 1)
      }
    }
    g.globalAlpha = 1
    // 질의 행 강조
    g.fillStyle = 'rgba(118,185,0,0.75)'
    g.fillRect(0, top - 4, w, 2)
    // 깊이 히스토그램
    const hy = top + rows.length * rowH + 14
    const maxD = Math.max(1, ...res.depth)
    g.fillStyle = 'rgba(232,238,252,0.55)'
    g.fillText(`열별 정렬 깊이 (최대 ${maxD}줄)`, 2, hy - 2)
    for (let i = 0; i < L; i++) {
      const d = (res.depth[i] ?? 0) / maxD
      g.fillStyle = `rgba(118,185,0,${0.25 + 0.6 * d})`
      g.fillRect(i * cw, hy + histH - d * histH, Math.max(cw, 0.7), d * histH)
    }
  }, [res, reveal, w])
  return <canvas ref={ref} style={{ display: 'block', width: '100%' }} />
}

export default function DiscoveryMsa() {
  const { sim } = useBrain()
  const { target, runs, envs } = useDiscovery()
  const [cat, setCat] = useState<Catalog | null>(null)
  const [busy, setBusy] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [reveal, setReveal] = useState(1)
  const [err, setErr] = useState<string | null>(null)
  const [fresh, setFresh] = useState(false)
  const env = (envs.msa ?? null) as Envelope<MsaResult> | null
  const res = (runs.msa ?? env?.measured ?? null) as MsaResult | null
  const isLive = Boolean(runs.msa)

  useEffect(() => { getCatalog().then(setCat).catch(() => setErr('목록을 불러오지 못했습니다')) }, [])
  useEffect(() => {
    if (!busy) return
    const t0 = Date.now()
    const id = setInterval(() => setElapsed((Date.now() - t0) / 1000), 100)
    return () => clearInterval(id)
  }, [busy])

  async function run() {
    setBusy(true); setErr(null); setElapsed(0); setReveal(0)
    sim?.stimulate('channel', 'literature', 1.2, 14)
    sim?.stimulate('layer', 'sense', 1.1, 12)
    const beat = setInterval(() => sim?.stimulate('layer', 'sense', 0.8, 6), 1100)
    try {
      const out = await runStep<MsaResult>('msa', runParams({ no_cache: fresh }), (e) => saveRun('msa', e as Envelope))
      saveRun('msa', out as Envelope)
      if (out.result) {
        pulseReward(sim, rewardFromDepth(out.result.mean_depth) * 0.5, `정렬 깊이 ${out.result.homologs}줄`, 'MSA-Search')
        sim?.stimulate('layer', 'encode', 1.1, 12)
        let k = 0
        const anim = setInterval(() => { k += 0.05; setReveal(Math.min(1, k)); if (k >= 1) clearInterval(anim) }, 40)
      }
      if (out.error) setErr(out.error)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      clearInterval(beat)
      setBusy(false)
    }
  }

  const m = cat?.measured.msa
  const t = cat?.targets[target]
  return (
    <StepPage
      eyebrow="STEP 1 · 시판 전 탐색 · 1단계"
      title={<>상동 서열을 찾아 <span style={{ color: 'var(--c-sense)' }}>진화 정보</span>를 모읍니다</>}
      lede={<>NVIDIA BioNeMo <b>MSA-Search</b>(ColabFold, GPU MMSeqs2) NIM 을 계정 키로 실제로 부릅니다. 공식 스킬
        <span className="mono"> bionemo-msa-structure-prediction-pipeline</span> 의 1단계로, 여기서 받은 A3M 정렬을 다음 단계 OpenFold3 에 그대로 넘깁니다.
        기본 데모는 니라파립·PARP1(4R6E 체인 A)이고, 위에서 UniProt·PubChem 으로 다른 단백질과 리간드를 찾아 그대로 돌릴 수 있습니다.</>}
      right={<span className="chip nv">health.api.nvidia.com · MSA-Search</span>}
      cat={cat}
      current="msa"
      center={
        <Card title="정렬 결과" sub={res ? `${res.database} · ${res.sequences}줄(질의 1 + 상동 ${res.homologs}) · 질의 ${res.query_len}잔기` : '실행하면 라이브 정렬이 그려집니다'}
          right={<div className="row" style={{ gap: 6 }}><SourceChip env={env} />{!isLive && res && <span className="chip warn" style={{ fontSize: 10.5 }}>지난 측정</span>}</div>}>
          {res ? <Alignment res={res} reveal={busy ? 0.15 : reveal} /> : <div className="shimmer" style={{ height: 320 }} />}
          <div className="row wrap" style={{ gap: 10, marginTop: 10 }}>
            {Object.entries(GROUP_COLOR).map(([k, c]) => (
              <span key={k} className="row" style={{ gap: 5, fontSize: 10.5, color: 'var(--text-3)' }}>
                <i className="legend-dot" style={{ background: c }} />{k === 'hydro' ? '소수성' : k === 'arom' ? '방향족' : k === 'pos' ? '양전하' : k === 'neg' ? '음전하' : k === 'polar' ? '극성' : '특수(C·G·P)'}
              </span>
            ))}
            <span className="note">질의와 같은 잔기는 진하게, 다른 잔기는 흐리게 그렸습니다. 아래 막대는 열별 정렬 깊이입니다.</span>
          </div>
        </Card>
      }
      side={
        <>
          <Card title="라이브 실행" sub="NVIDIA BioNeMo NIM 호출">
            <RunButton busy={busy} onClick={run} label="MSA-Search 실행" fresh={fresh} setFresh={setFresh}
              sub={<>표적 {t?.label ?? 'PARP1'} · {t?.sequence_len ?? 352}잔기 · Uniref30_2302</>} />
            <div className="divider" />
            <Progress env={env} busy={busy} elapsed={elapsed} />
            {err && <div className="note" style={{ color: 'var(--warn)', marginTop: 8 }}>{err}</div>}
            {env?.note && <div className="note" style={{ color: 'var(--warn)', marginTop: 8 }}>{env.note}</div>}
          </Card>
          <Card title="요청" sub={<span className="mono" style={{ fontSize: 10.5 }} title={env?.endpoint ?? undefined}>{pathOf(env?.endpoint) || '/v1/biology/colabfold/msa-search/predict'}</span>}>
            <KV rows={[
              ['databases', String((env?.request?.databases as string[]) ?? ['Uniref30_2302'])],
              ['e_value', String(env?.request?.e_value ?? 1e-4)],
              ['format', String((env?.request?.output_alignment_formats as string[]) ?? ['a3m'])],
              ['sequence', `${env?.request?.sequence_len ?? t?.sequence_len ?? 352} aa`],
            ]} />
          </Card>
          <Card title="측정값" sub="이번 실행">
            <KV rows={[
              ['정렬 줄 수', res ? `${res.sequences}줄` : '–'],
              ['상동 서열', res ? `${res.homologs}개` : '–'],
              ['평균 깊이', res ? `${res.mean_depth}줄` : '–'],
              ['열 커버리지', res ? `${(res.coverage * 100).toFixed(1)}%` : '–'],
              ['소요', busy ? `${elapsed.toFixed(1)}초` : env?.source === 'cache' ? '캐시(같은 입력)' : fmtS(env?.elapsed_s)],
            ]} />
            <div className="divider" />
            <div className="row between">
              <span className="chip warn" style={{ fontSize: 10.5 }}>지난 측정</span>
              <span className="num dim" style={{ fontSize: 11.5 }}>{m ? `상동 ${m.homologs}개 · ${m.seconds}초` : '–'}</span>
            </div>
            <div className="note" style={{ marginTop: 6 }}>지난 측정은 2026-09-28 에 같은 엔드포인트로 받은 응답입니다(fly_discovery/measurements/nim/parp1.a3m).</div>
          </Card>
          <Card title="따라간 NVIDIA 공식 스킬">
            <SkillBox skills={env?.skills ?? cat?.skills.msa ?? []} />
          </Card>
        </>
      }
    />
  )
}
