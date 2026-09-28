import { useEffect, useRef, useState, type ReactNode } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import ConnectomePanel from './ConnectomePanel'
import { useBrain } from '../lib/brain'
import { ballStick, disposeAll, drawRibbon, dust, glowSprite, makeRenderer, plddtColor, ribbon, setOpacity, type Ligand } from '../lib/molScene'

// STEP 1 대표 장면(쇼릴 03 장면의 3D 판): OpenFold3 NIM 이 예측한 PARP1 + 니라파립 복합체를 가운데 두고,
// 위 단계 표시(MSA-Search → OpenFold3 → DiffDock → Boltz-2 → 크리틱)를 따라 장면과 오른쪽 수치가 바뀝니다.
// 좌표: pipeline/discovery/build_hero_scene.py 가 만든 hero_scene.json (4R6E 는 Kabsch 로 예측 좌표계에 겹침, Cα RMSD 1.00 Å 재현).
// 연출(리본을 그려 나가는 순서, 포즈가 날아오는 경로, 카메라)만 만든 것이고 도착한 좌표와 수치는 NIM 응답·RCSB·ChEMBL 그대로입니다.

export interface HeroScene {
  metrics: { ca_rmsd_kabsch: number; matched_ca: number; plddt: number; ptm: number; iptm: number; of3_ligand_rmsd: number; msa_homologs: number; of3_seconds: number; diffdock_rmsd: number; diffdock_conf: number; vina: number }
  pose_eval: { rank: number; confidence: number; rmsd: number }[]
  ribbon: [number, number, number, number, number][]
  crystal_ca: [number, number, number, number][]
  of3_ligand: Ligand; xtal_ligand: Ligand; diffdock_poses: Ligand[]
}
export interface HeroExtras { boltz: { pic50: number; p: number; chembl: number | null; n: number } | null; bench: { n: number; spearman: number; mae: number } | null
  critic: { model: string; caught: number; n_over: number; passed: number; n_valid: number; sec: number; rows: [string, string, string][] } | null }

const STEPS = [
  { id: 'msa', label: 'MSA-Search', tech: 'NIM', t0: 0, t1: 3000 },
  { id: 'of3', label: 'OpenFold3', tech: 'NIM', t0: 3000, t1: 11000 },
  { id: 'dd', label: 'DiffDock', tech: 'NIM', t0: 11000, t1: 19000 },
  { id: 'bz', label: 'Boltz-2', tech: 'NIM', t0: 19000, t1: 24500 },
  { id: 'critic', label: '크리틱', tech: 'NEMOTRON', t0: 24500, t1: 31000 },
] as const
const LOOP = 31000
// 메뉴가 바뀔 때 커넥텀에서 반짝일 층 (STEP 2 관제 센터와 같은 시뮬레이터를 씁니다)
const STEP_LAYERS: Record<string, string[]> = { msa: ['sense'], of3: ['encode'], dd: ['reflex', 'memory'], bz: ['memory', 'deliberate'], critic: ['critic', 'action'] }
const FOCUS: Record<string, string> = { msa: '감각 입력 · 서열 정렬', of3: '특징 부호화 · 구조 예측', dd: '반사 · 기억 · 포즈 판단', bz: '기억 · 숙고 · 친화도', critic: '억제성 크리틱 · 행동' }
// 장면 속 사건이 일어나는 시각(ms)과 자극할 층. 반복 재생 때마다 다시 울립니다
const EVENTS: [number, string, number][] = [
  [300, 'sense', 0.8], [1100, 'sense', 0.8], [1900, 'sense', 0.8], [2700, 'sense', 0.8],
  [3600, 'encode', 0.9], [4800, 'encode', 0.9], [6000, 'encode', 0.9], [7600, 'encode', 1.1], [8200, 'assoc', 0.8],
  [11400, 'sense', 0.9], [12100, 'sense', 0.9], [12800, 'sense', 0.9], [13500, 'sense', 0.9], [14200, 'reflex', 1],
  [16200, 'reflex', 1.4], [16300, 'memory', 1.2], [16500, 'action', 1], [16800, 'critic', 1],
  [19500, 'memory', 1.1], [20500, 'deliberate', 1.2], [21700, 'deliberate', 1], [23000, 'memory', 0.9],
  [25000, 'critic', 1.3], [26500, 'critic', 1.1], [28000, 'action', 1.2], [29500, 'feedback', 1],
]
type StepId = typeof STEPS[number]['id']
const clamp = (v: number) => Math.max(0, Math.min(1, v))
const ease = (k: number) => 1 - Math.pow(1 - clamp(k), 3)

function Stepper({ step, done, onPick, m, x }: { step: StepId; done: (id: StepId) => boolean; onPick: (id: StepId) => void; m: HeroScene['metrics']; x: HeroExtras }) {
  const val: Record<StepId, string> = {
    msa: `상동 서열 ${m.msa_homologs}개`, of3: `pLDDT ${m.plddt.toFixed(2)}`, dd: `재도킹 ${m.diffdock_rmsd.toFixed(2)} Å`,
    bz: x.bench ? `Spearman ${x.bench.spearman.toFixed(3)}` : 'Boltz-2', critic: x.critic ? `과잉해석 ${x.critic.caught}/${x.critic.n_over} 반려` : '크리틱',
  }
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(0, 1fr))', gap: 10 }}>
      {STEPS.map((s) => {
        const on = s.id === step, ok = done(s.id)
        return (
          <button key={s.id} onClick={() => onPick(s.id)} style={{ textAlign: 'left', padding: '9px 12px', borderRadius: 11, cursor: 'pointer',
            background: on ? 'rgba(55,230,255,0.10)' : 'rgba(10,16,30,0.55)', border: `1px solid ${on ? 'rgba(55,230,255,0.55)' : 'var(--line)'}`,
            boxShadow: on ? '0 0 24px -6px rgba(55,230,255,0.6)' : 'none', transition: 'all .3s' }}>
            <div className="row between">
              <span className="mono" style={{ fontSize: 10, letterSpacing: 1.4, color: on ? 'var(--c-sense)' : 'var(--text-3)', textTransform: 'uppercase' }}>{s.label}</span>
              <span className={`chip ${s.tech === 'NIM' ? 'nv' : 'bad'}`} style={{ fontSize: 9, padding: '1px 6px' }}>{s.tech}</span>
            </div>
            <div className="row between" style={{ marginTop: 3 }}>
              <b style={{ fontFamily: 'var(--font)', fontSize: 13.5, color: on || ok ? 'var(--text)' : 'var(--text-3)' }}>{on || ok ? val[s.id] : '· · ·'}</b>
              {ok && !on && <span style={{ color: 'var(--ok)', fontSize: 13 }}>✓</span>}
            </div>
          </button>
        )
      })}
    </div>
  )
}

function Big({ eyebrow, value, unit, lines, foot }: { eyebrow: string; value: string; unit?: string; lines: ReactNode[]; foot?: ReactNode }) {
  return (
    <div className="fade-in stack" style={{ gap: 10 }} key={eyebrow}>
      <div className="mono" style={{ fontSize: 11, letterSpacing: 1.6, color: 'var(--c-sense)', textTransform: 'uppercase' }}>{eyebrow}</div>
      <div className="row" style={{ alignItems: 'baseline', gap: 10 }}>
        <span style={{ fontFamily: 'var(--font)', fontWeight: 700, fontSize: 76, lineHeight: 1, letterSpacing: -2, textShadow: '0 0 32px rgba(55,230,255,0.25)' }}>{value}</span>
        {unit && <span className="mono" style={{ fontSize: 16, color: 'var(--text-2)' }}>{unit}</span>}
      </div>
      {lines.map((l, i) => <div key={i} style={{ fontSize: 15.5, fontWeight: 500 }}>{l}</div>)}
      {foot && <div style={{ marginTop: 6 }}>{foot}</div>}
    </div>
  )
}

export type { StepId }
export default function HeroDocking({ hero, extras, height = 560, only, nav }: { hero: HeroScene; extras: HeroExtras; height?: number; only?: StepId; nav?: Record<StepId, string> }) {
  const host = useRef<HTMLDivElement>(null)
  const label = useRef<HTMLDivElement>(null)
  const clock = useRef({ t0: performance.now(), offset: only ? STEPS.find((s) => s.id === only)!.t0 : 0 })
  const [step, setStep] = useState<StepId>(only ?? 'msa')
  const [tick, setTick] = useState(0)
  const m = hero.metrics

  // 처음에는 다섯 메뉴를 자동으로 넘기고, 메뉴를 누르면 그 메뉴 구간을 반복합니다
  const hold = useRef<StepId | null>(only ?? null)
  const [held, setHeld] = useState<StepId | null>(only ?? null)
  const jump = (id: StepId) => {
    if (nav) { location.hash = `/${nav[id]}`; return }
    const s = STEPS.find((x) => x.id === id)!; clock.current = { t0: performance.now(), offset: s.t0 }; hold.current = id; setHeld(id) }
  const resume = () => { hold.current = null; setHeld(null) }
  const { sim } = useBrain()
  const simRef = useRef(sim)
  simRef.current = sim
  useEffect(() => { if (sim) (STEP_LAYERS[step] ?? []).forEach((l, i) => setTimeout(() => sim.stimulate('layer', l, 1, 10), i * 300)) }, [step, sim])

  useEffect(() => {
    const el = host.current
    if (!el) return
    let disposed = false, raf = 0
    const { renderer, scene, camera, composer, bloom, resize } = makeRenderer(el)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true; controls.autoRotate = true; controls.autoRotateSpeed = 0.45
    controls.minDistance = 14; controls.maxDistance = 140

    const root = new THREE.Group(); scene.add(root)
    scene.add(dust())
    // 예측 리본(pLDDT 색) — 리간드 중심이 원점이므로 단백질 중심을 따로 잡아 카메라 목표로 씁니다
    const ca = hero.ribbon.map((r) => ({ p: new THREE.Vector3(r[0], r[1], r[2]), resseq: r[3], color: plddtColor(r[4]) }))
    const protCenter = ca.reduce((v, a) => v.add(a.p), new THREE.Vector3()).multiplyScalar(1 / ca.length)
    const rb = ribbon(ca, 0.32); root.add(rb.core, rb.glow)
    // 결정 구조 4R6E Cα (검증 단계에서 흰 선으로 겹침)
    const xs: number[] = []
    for (let i = 1; i < hero.crystal_ca.length; i++) {
      const a = hero.crystal_ca[i - 1], b = hero.crystal_ca[i]
      if (b[3] - a[3] === 1) xs.push(a[0], a[1], a[2], b[0], b[1], b[2])
    }
    const xtalTrace = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(xs, 3)),
      new THREE.LineBasicMaterial({ color: 0xe8eefc, transparent: true, opacity: 0.55 }))
    root.add(xtalTrace)
    // 리간드: OpenFold3 가 함께 예측한 니라파립 / DiffDock 1순위 / 나머지 4개 / 결정 구조 정답
    const of3Lig = ballStick(hero.of3_ligand, 'solid'); root.add(of3Lig)
    const dd1 = ballStick(hero.diffdock_poses[0], 'solid')
    const ddPivot = new THREE.Group(); ddPivot.add(dd1); root.add(ddPivot)
    const alts = hero.diffdock_poses.slice(1).map((p) => { const g = ballStick(p, 'faint'); root.add(g); return g })
    const xtalLig = ballStick(hero.xtal_ligand, 'ghost'); root.add(xtalLig)
    const glow = glowSprite(0xffb547); glow.scale.setScalar(14); root.add(glow)
    // 날아오는 궤적
    const trailPts = 60, trail = new THREE.Line(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(new Array(trailPts * 3).fill(0), 3)),
      new THREE.LineBasicMaterial({ color: 0xffb547, transparent: true, opacity: 0.8, blending: THREE.AdditiveBlending }))
    root.add(trail)
    const path = new THREE.CatmullRomCurve3([new THREE.Vector3(34, 22, -18), new THREE.Vector3(20, 4, 14), new THREE.Vector3(8, 9, 6), new THREE.Vector3(0, 0, 0)])

    // 단백질 전체가 들어오도록 경계 구 반지름으로 거리를 잡습니다
    const radius = Math.max(...ca.map((a) => a.p.distanceTo(protCenter)))
    const farPos = protCenter.clone().add(new THREE.Vector3(0.62, 0.34, 0.71).normalize().multiplyScalar(radius / Math.sin((36 / 2) * Math.PI / 180) * 0.92)), nearPos = new THREE.Vector3(10, 6.5, 13)
    camera.position.copy(farPos); controls.target.copy(protCenter)
    const ro = new ResizeObserver(resize); ro.observe(el); resize()
    const v = new THREE.Vector3()
    let lastStep = '', dragging = false, lastT = -1

    const loop = (now: number) => {
      if (disposed) return
      const h = hold.current ? STEPS.find((s) => s.id === hold.current)! : null
      const raw = now - clock.current.t0 + clock.current.offset
      // 머무는 메뉴: 앞 단계의 결과(리본, 도킹)는 끝난 상태로 두고 그 구간만 반복합니다
      const t = h ? h.t0 + ((raw - h.t0) % (h.t1 - h.t0)) : raw % LOOP
      const st = STEPS.find((s) => t >= s.t0 && t < s.t1) ?? STEPS[0]
      // 한 단계에 머물 때는 구간이 다시 시작돼도 카메라가 튀지 않게, 그 단계의 카메라 자리에 둡니다
      // 사건 시각을 지나면 커넥텀 층을 자극합니다 (구간이 다시 시작되면 lastT 도 되감깁니다)
      if (t < lastT) lastT = t - 1
      for (const [et, layer, amp] of EVENTS) if (lastT < et && et <= t) simRef.current?.stimulate('layer', layer, amp, 8)
      lastT = t
      const camT = h ? (h.id === 'msa' || h.id === 'of3' ? 0 : 20000) : t
      if (st.id !== lastStep) { lastStep = st.id; setStep(st.id) }
      // OpenFold3: 리본을 N 말단부터 그리고, 끝에 함께 예측한 리간드가 나타납니다
      if (t < 3000) {
        // MSA-Search: 흐린 뼈대 위로 상동 서열 정렬이 N 말단부터 훑고 지나갑니다
        rb.meshes.forEach((mm, i) => { mm.geometry.setDrawRange(0, Infinity); setOpacity(mm, i % 2 ? 0.9 * Math.sin(clamp(t / 3000) * Math.PI) : 0.12) })
        const k = clamp(t / 2600), band = 0.08
        rb.meshes.forEach((mm, i) => { if (i % 2) { const tot = mm.userData.total as number; mm.geometry.setDrawRange(Math.floor(tot * Math.max(0, k - band) / 6) * 6, Math.floor(tot * band / 6) * 6 * 2) } })
      } else {
        const closeK = ease((camT - 12200) / 3200) * (1 - ease((camT - 26000) / 4000))
        rb.meshes.forEach((mm, i) => setOpacity(mm, (i % 2 ? 0.7 : 1) * (1 - 0.72 * closeK)))
        drawRibbon(rb.meshes, ease((t - 3000) / 4800))
      }
      setOpacity(of3Lig, t < 7600 ? 0 : t < 11000 ? clamp((t - 7600) / 700) : clamp(1 - (t - 11000) / 600))
      // DiffDock: 나머지 포즈가 스쳐 가고, 1순위가 궤적을 그리며 날아와 박힙니다
      alts.forEach((g, i) => { const a = 11400 + i * 700; setOpacity(g, t < a ? 0 : t < a + 1400 ? Math.sin(((t - a) / 1400) * Math.PI) : 0) })
      const fk = ease((t - 13600) / 2600)
      setOpacity(ddPivot, t < 13600 ? 0 : 1)
      ddPivot.position.copy(path.getPointAt(1 - fk).multiplyScalar(1)).sub(path.getPointAt(1))
      ddPivot.rotation.set(2.6 * (1 - fk), -1.8 * (1 - fk), 1.2 * (1 - fk))
      const pos = trail.geometry.getAttribute('position') as THREE.BufferAttribute
      for (let i = 0; i < trailPts; i++) { path.getPointAt(Math.max(0, 1 - fk) + (i / trailPts) * fk * 0.999, v); pos.setXYZ(i, v.x, v.y, v.z) }
      pos.needsUpdate = true
      setOpacity(trail, t > 13600 && t < 17200 ? clamp(1 - (t - 16200) / 1000) : 0)
      // 검증: 결정 구조(뼈대 + 리간드 정답)가 겹쳐집니다
      setOpacity(xtalLig, t < 16400 ? 0 : clamp((t - 16400) / 800))
      setOpacity(xtalTrace, t < 16400 || t > 19500 ? 0 : 0.9 * Math.sin(clamp((t - 16400) / 3100) * Math.PI))
      const flash = t > 16200 && t < 18400 ? Math.sin(((t - 16200) / 2200) * Math.PI) : 0
      glow.material.opacity = 0.18 + 0.7 * flash + (t > 19000 ? 0.12 * (1 + Math.sin(now / 500)) : 0)
      // 카메라: 전체 → 결합 자리로 다가갔다가 다시 물러납니다
      const inK = ease((camT - 12200) / 3200), outK = ease((camT - 26000) / 4000)
      const want = farPos.clone().lerp(nearPos, inK * (1 - outK)), tgt = protCenter.clone().lerp(new THREE.Vector3(), inK * (1 - outK))
      if (!dragging) { camera.position.lerp(want, 0.04); controls.target.lerp(tgt, 0.06) }
      bloom.strength = 0.55 + 0.45 * flash
      controls.update(); composer.render()
      // 리간드 말풍선: 원점을 화면 좌표로 옮깁니다
      if (label.current) {
        v.set(0, 0, 0).project(camera)
        const show = (t > 8000 && t < 11000) || (t > 16400 && t < 24500)
        label.current.style.opacity = show ? '1' : '0'
        label.current.style.transform = `translate(${((v.x + 1) / 2) * el.clientWidth + 26}px, ${((1 - v.y) / 2) * el.clientHeight - 74}px)`
      }
      raf = requestAnimationFrame(loop)
    }
    controls.addEventListener('start', () => { dragging = true })
    controls.addEventListener('end', () => { dragging = false })
    raf = requestAnimationFrame(loop)
    const tk = setInterval(() => setTick((k) => k + 1), 500)
    return () => { disposed = true; cancelAnimationFrame(raf); clearInterval(tk); ro.disconnect(); controls.dispose(); disposeAll(scene); composer.dispose(); renderer.dispose(); renderer.domElement.remove() }
  }, [hero])

  const done = (id: StepId) => STEPS.findIndex((s) => s.id === id) < STEPS.findIndex((s) => s.id === step)
  const tNow = (performance.now() - clock.current.t0 + clock.current.offset) % LOOP
  void tick
  const legend = (
    <div className="row wrap mono" style={{ gap: 14, fontSize: 11, color: 'var(--text-2)' }}>
      <span>pLDDT</span>
      {[['#37e6ff', '≥ 90'], ['#4d8dff', '70–90'], ['#ffcc4d', '50–70'], ['#ff8b35', '< 50']].map(([c, l]) => <span key={l}><i style={{ display: 'inline-block', width: 16, height: 3, background: c, marginRight: 6, verticalAlign: 'middle', boxShadow: `0 0 8px ${c}` }} />{l}</span>)}
    </div>
  )
  const stat: Record<StepId, ReactNode> = {
    msa: <Big eyebrow="MSA-Search NIM · 상동 서열 정렬" value={String(m.msa_homologs)} unit="서열" lines={['PARP1 촉매 도메인 · Uniref30_2302', <span className="dim">OpenFold3 입력으로 그대로 잇습니다 (NVIDIA 공식 스킬 규격)</span>]} />,
    of3: <Big eyebrow={`OpenFold3 NIM · 복합체 예측 · ${m.of3_seconds} s`} value={m.plddt.toFixed(2)} unit="pLDDT"
      lines={[`pTM ${m.ptm} · ipTM ${m.iptm}`, `4R6E 결정 구조 대비 Cα RMSD ${m.ca_rmsd_kabsch.toFixed(1)} Å · ${m.matched_ca} Cα`, <span style={{ color: 'var(--jev)' }}>리간드 RMSD {m.of3_ligand_rmsd} Å</span>]}
      foot={<div className="stack" style={{ gap: 12 }}>{legend}<div className="mono" style={{ fontSize: 11, color: 'var(--ok)' }}>고전 기준 · pLDDT ≥ 90 · 결정 구조 대비 Cα RMSD ≤ 2 Å</div></div>} />,
    dd: <Big eyebrow={`DiffDock NIM · 포즈 ${hero.pose_eval.length}개 중 1순위`} value={m.diffdock_rmsd.toFixed(2)} unit="Å RMSD"
      lines={[`결정 구조 4R6E 의 니라파립 자리 재현 · 신뢰도 ${m.diffdock_conf}`, <span className="dim">나머지 포즈 {hero.pose_eval.slice(1).map((p) => `${p.rmsd.toFixed(2)}`).join(' · ')} Å</span>, <span style={{ color: 'var(--ok)' }}>고전 기준 · 1순위 포즈 RMSD ≤ 2 Å 통과</span>]} />,
    bz: <Big eyebrow="Boltz-2 NIM · 친화도 예측" value={extras.boltz ? extras.boltz.pic50.toFixed(2) : '–'} unit="pIC50"
      lines={[extras.boltz ? `ChEMBL 실측 중앙값 ${extras.boltz.chembl} (n=${extras.boltz.n}) · 결합 확률 ${extras.boltz.p}` : '',
        extras.bench ? <span>PARP1 {extras.bench.n}종 벤치마크 Spearman <b style={{ color: 'var(--ok)' }}>{extras.bench.spearman.toFixed(3)}</b> · MAE {extras.bench.mae} log</span> : '',
        <span className="dim">예측값은 측정된 친화도가 아닙니다 (크리틱이 이 혼동을 반려합니다)</span>]} />,
    critic: <Big eyebrow={extras.critic ? `크리틱 3단 · ${extras.critic.model} · ${extras.critic.sec} s` : '크리틱 3단'} value={extras.critic ? `${extras.critic.caught}/${extras.critic.n_over}` : '–'} unit="과잉해석 반려"
      lines={extras.critic ? [`정상 주장 ${extras.critic.passed}/${extras.critic.n_valid} 통과`,
        ...extras.critic.rows.filter((r) => r[1] === 'REJECT').slice(0, 2).map((r) => <span className="dim" style={{ fontSize: 13 }}>✗ {r[0]}</span>)] : []} />,
  }

  return (
    <div className="stack" style={{ gap: 14 }}>
      {!only && <div className="row between" style={{ marginBottom: -4 }}>
        <span className="mono dim" style={{ fontSize: 10.5 }}>{held ? `${STEPS.find((s) => s.id === held)!.label} 단계를 반복 재생 중` : '다섯 단계를 차례로 재생 중 · 단계를 누르면 그 단계에 머뭅니다'}</span>
        {held && <button className="chip" style={{ cursor: 'pointer' }} onClick={resume}>▶ 전체 자동 재생</button>}
      </div>}
      <Stepper step={step} done={done} onPick={jump} m={m} x={extras} />
      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.35fr) minmax(320px, 1fr)', gap: 16, alignItems: 'start' }}>
        <div style={{ position: 'relative', height }}>
          <div ref={host} style={{ position: 'absolute', inset: 0, cursor: 'grab', borderRadius: 14, overflow: 'hidden', border: '1px solid var(--line)' }}
            aria-label="OpenFold3 가 예측한 PARP1 과 니라파립, DiffDock 포즈, 결정 구조 4R6E. 드래그로 회전합니다." />
          <div ref={label} style={{ position: 'absolute', left: 0, top: 0, pointerEvents: 'none', transition: 'opacity .4s', opacity: 0,
            padding: '7px 11px', borderRadius: 8, background: 'rgba(5,9,18,0.82)', border: '1px solid rgba(255,181,71,0.45)', whiteSpace: 'nowrap' }}>
            <div className="mono" style={{ fontSize: 10, letterSpacing: 1.3, color: 'var(--jev)' }}>LIGAND · 니라파립</div>
            <div style={{ fontSize: 13.5, fontWeight: 600 }}>{tNow < 11000 ? '단백질과 함께 예측 (OpenFold3)' : tNow < 16400 ? 'DiffDock 1순위 포즈' : `결정 구조와 ${m.diffdock_rmsd} Å`}</div>
          </div>
        </div>
        <div className="stack" style={{ gap: 14, alignSelf: 'stretch' }}>
          <ConnectomePanel height={Math.round(height * 0.42)} focus={FOCUS[step]} />
          <div style={{ minHeight: 280 }}>{stat[step]}</div>
        </div>
      </div>
    </div>
  )
}
