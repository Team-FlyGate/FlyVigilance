import { useEffect, useRef, useState, type ReactNode } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import ConnectomePanel from './ConnectomePanel'
import SplitTarget, { type XaSplit } from './SplitTarget'
import MsaAnimation from './MsaAnimation'
import AffinityMeter from './AffinityMeter'
import { useBrain } from '../lib/brain'
import { t } from '../lib/i18n'
import { ballStick, conservationColor, disposeAll, dust, glowSprite, makeRenderer, plddtColor, ribbon, setOpacity, type Ligand } from '../lib/molScene'

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
  msa: { labels: [string, number | null][]; query: string; n_homologs: number; query_len: number; conservation: number[]; strip: string[]; pocket_residues: number[]; pocket_mean: number; overall_mean: number }
  parp_set: { name: string; pose: Ligand; vina: number | null; dd_conf: number | null; boltz_pic50: number | null; boltz_p: number | null; chembl: number | null; chembl_n: number | null }[]
  critic_split: { xa: XaSplit; parp1: { dd_conf: number; vina: number } }
  drugs?: Record<string, HeroDrug>
}
// 장면에서 고를 수 있는 약물 하나의 데이터 (build_hero_scene.py 의 drugs)
export interface HeroDrug {
  name: string; crystal_pdb: string; poses: Ligand[]; pose_eval: { rank: number; confidence: number; rmsd: number | null }[]; xtal: Ligand
  dd_rmsd: number | null; dd_conf: number; vina: number | null; boltz_pic50: number | null; chembl: number | null
  xa: { ligand: Ligand; dd_conf: number; vina: number | null }
}
export const HERO_DRUGS = ['niraparib', 'talazoparib', 'rucaparib'] as const
// 약물 표시 이름은 읽을 때마다 지금 언어로 돌려줍니다(getter). 부르는 쪽은 DRUG_LABEL[d] 그대로 씁니다.
const DRUG_KO: Record<string, string> = { niraparib: '니라파립', talazoparib: '탈라조파립', rucaparib: '루카파립' }
const DRUG_EN: Record<string, string> = { niraparib: 'Niraparib', talazoparib: 'Talazoparib', rucaparib: 'Rucaparib' }
export const DRUG_LABEL: Record<string, string> = Object.defineProperties({} as Record<string, string>,
  Object.fromEntries(Object.keys(DRUG_KO).map((k) => [k, { enumerable: true, get: () => t(DRUG_KO[k], DRUG_EN[k]) }])))
// Boltz-2 장면에서 고르지 않은 억제제의 색 (고른 약물은 늘 주황)
export const PARP_COLOR: Record<string, string> = { '15r': '#2fd6c8', pamiparib: '#a58bff', rucaparib: '#ff7ab6', talazoparib: '#7ce38b', niraparib: '#f2e36b' }
// 고른 약물은 단계 페이지를 옮겨 다녀도 유지합니다
let heroDrug = 'niraparib'
export function useHeroDrug(): [string, (d: string) => void] {
  const [d, setD] = useState(heroDrug)
  useEffect(() => { const f = () => setD(heroDrug); window.addEventListener('fd-hero-drug', f); return () => window.removeEventListener('fd-hero-drug', f) }, [])
  return [d, (x: string) => { heroDrug = x; window.dispatchEvent(new Event('fd-hero-drug')) }]
}
export interface HeroExtras { boltz: { pic50: number; p: number; chembl: number | null; n: number } | null; bench: { n: number; spearman: number; mae: number } | null
  critic: { model: string; caught: number; n_over: number; passed: number; n_valid: number; sec: number; rows: [string, string, string][] } | null }

const STEPS = [
  { id: 'msa', label: 'MSA-Search', tech: 'NIM', t0: 0, t1: 3000 },
  { id: 'of3', label: 'OpenFold3', tech: 'NIM', t0: 3000, t1: 11000 },
  { id: 'dd', label: 'DiffDock', tech: 'NIM', t0: 11000, t1: 19000 },
  { id: 'bz', label: 'Boltz-2', tech: 'NIM', t0: 19000, t1: 24500 },
  { id: 'critic', label: 'Critic', tech: 'NEMOTRON', t0: 24500, t1: 31000 },
] as const
const LOOP = 31000
// 3D 장면 HUD (FDDD 쇼릴처럼 한 줄 태그 + 타자처럼 찍히는 제목)
const HUD = (): Record<string, [string, string]> => ({
  msa: [t('MSA-SEARCH · 101 SEQUENCES · 보존도', 'MSA-SEARCH · 101 SEQUENCES · CONSERVATION'), t('약물이 붙는 자리는 더 잘 보존됩니다', 'Drug-binding sites are better conserved')],
  of3: [t('OPENFOLD3 · PARP1 촉매 도메인 · 352 잔기', 'OPENFOLD3 · PARP1 CATALYTIC DOMAIN · 352 RESIDUES'), t('서열에서 단백질 구조를 그립니다', 'Drawing protein structure from sequence')],
  dd: ['DIFFDOCK · POSE 1 / 5 · 4R6E', t('니라파립 → PARP1 결합 자리', 'Niraparib → PARP1 binding site')],
  bz: [t('BOLTZ-2 · PARP1 억제제 4종 · 같은 포켓', 'BOLTZ-2 · 4 PARP1 INHIBITORS · SAME POCKET'), t('같은 표적 안에서만 세기를 비교합니다', 'Strength is compared only within one target')],
  critic: ['CRITIC · PARP1 | FACTOR XA', t('다른 표적의 점수는 비교할 수 없습니다', 'Scores across targets are not comparable')],
})
// 메뉴가 바뀔 때 커넥텀에서 반짝일 층 (STEP 2 관제 센터와 같은 시뮬레이터를 씁니다)
const STEP_LAYERS: Record<string, string[]> = { msa: ['sense'], of3: ['encode'], dd: ['reflex', 'memory'], bz: ['memory', 'deliberate'], critic: ['critic', 'action'] }
const FOCUS = (): Record<string, string> => t(
  { msa: '감각 입력 · 서열 정렬', of3: '특징 부호화 · 구조 예측', dd: '반사 · 기억 · 포즈 판단', bz: '기억 · 숙고 · 친화도', critic: '억제성 크리틱 · 행동' },
  { msa: 'Sensory input · sequence alignment', of3: 'Feature encoding · structure prediction', dd: 'Reflex · memory · pose judgment', bz: 'Memory · deliberation · affinity', critic: 'Inhibitory critic · action' },
)
// 장면 속 사건이 일어나는 시각(ms)과 자극할 층. 반복 재생 때마다 다시 울립니다
const EVENTS: [number, string, number][] = [
  [600, 'sense', 0.45], [2200, 'sense', 0.45],
  [4200, 'encode', 0.45], [7600, 'encode', 0.5],
  [12000, 'sense', 0.4], [16200, 'reflex', 0.6], [16600, 'memory', 0.5],
  [20500, 'deliberate', 0.5], [25500, 'critic', 0.6], [28500, 'action', 0.5],
]
type StepId = typeof STEPS[number]['id']
const clamp = (v: number) => Math.max(0, Math.min(1, v))
const ease = (k: number) => 1 - Math.pow(1 - clamp(k), 3)

function Stepper({ step, done, onPick, m, x, ddRmsd }: { step: StepId; done: (id: StepId) => boolean; onPick: (id: StepId) => void; m: HeroScene['metrics']; x: HeroExtras; ddRmsd: number | null }) {
  const val: Record<StepId, string> = {
    msa: t(`상동 서열 ${m.msa_homologs}개`, `${m.msa_homologs} homologs`), of3: `pLDDT ${m.plddt.toFixed(2)}`, dd: t(`재도킹 ${ddRmsd?.toFixed(2) ?? '–'} Å`, `Redock ${ddRmsd?.toFixed(2) ?? '–'} Å`),
    bz: x.bench ? `Spearman ${x.bench.spearman.toFixed(3)}` : 'Boltz-2', critic: x.critic ? t(`과잉해석 ${x.critic.caught}/${x.critic.n_over} 반려`, `${x.critic.caught}/${x.critic.n_over} overclaims rejected`) : t('크리틱', 'Critic'),
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
  // WebGL 컨텍스트가 강제로 죽으면 올려서 장면을 새로 만듭니다
  const [epoch, setEpoch] = useState(0)
  // '전체 보기' 단추가 사용자가 돌리거나 확대한 시점을 자동 카메라로 되돌립니다
  const resetCam = useRef<() => void>(() => {})
  const label = useRef<HTMLDivElement>(null)
  const clock = useRef({ t0: performance.now(), offset: only ? STEPS.find((s) => s.id === only)!.t0 : 0 })
  const [step, setStep] = useState<StepId>(only ?? 'msa')
  const [tick, setTick] = useState(0)
  const m = hero.metrics
  const [drug, setDrugRaw] = useHeroDrug()
  const dname = DRUG_LABEL[drug] ?? drug
  // drugs 가 없는 옛 데이터에서는 니라파립 필드로 채웁니다
  const D: HeroDrug = hero.drugs?.[drug] ?? { name: 'niraparib', crystal_pdb: '4R6E', poses: hero.diffdock_poses, pose_eval: hero.pose_eval, xtal: hero.xtal_ligand,
    dd_rmsd: m.diffdock_rmsd, dd_conf: m.diffdock_conf, vina: m.vina, boltz_pic50: extras.boltz?.pic50 ?? null, chembl: extras.boltz?.chembl ?? null,
    xa: { ligand: hero.critic_split.xa.niraparib, dd_conf: hero.critic_split.xa.dd_conf, vina: hero.critic_split.xa.vina } }

  // 처음에는 다섯 메뉴를 자동으로 넘기고, 메뉴를 누르면 그 메뉴 구간을 반복합니다
  const hold = useRef<StepId | null>(only ?? null)
  const [held, setHeld] = useState<StepId | null>(only ?? null)
  const jump = (id: StepId) => {
    if (nav) { location.hash = `/${nav[id]}`; return }
    const s = STEPS.find((x) => x.id === id)!; clock.current = { t0: performance.now(), offset: s.t0 }; hold.current = id; setHeld(id) }
  const resume = () => { hold.current = null; setHeld(null) }
  // 약물을 바꾸면 머무는 단계를 처음부터 다시 재생합니다(새 약물이 날아와 박히도록)
  const setDrug = (d: string) => { if (hold.current) clock.current = { t0: performance.now(), offset: STEPS.find((s) => s.id === hold.current)!.t0 }; setDrugRaw(d) }
  const { sim } = useBrain()
  const simRef = useRef(sim)
  simRef.current = sim
  useEffect(() => { if (sim) (STEP_LAYERS[step] ?? []).forEach((l, i) => setTimeout(() => sim.stimulate('layer', l, 0.5, 8), i * 300)) }, [step, sim])

  useEffect(() => {
    const el = host.current
    if (!el) return
    let disposed = false, raf = 0
    const { renderer, scene, camera, composer, bloom, film, resize, shown } = makeRenderer(el, () => setEpoch((k) => k + 1))
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true; controls.autoRotate = true; controls.autoRotateSpeed = 0.45
    controls.minDistance = 8; controls.maxDistance = 220; controls.enablePan = true; controls.enableZoom = true

    const root = new THREE.Group(); scene.add(root)
    scene.add(dust())
    // 예측 리본(pLDDT 색) — 리간드 중심이 원점이므로 단백질 중심을 따로 잡아 카메라 목표로 씁니다
    const ca = hero.ribbon.map((r) => ({ p: new THREE.Vector3(r[0], r[1], r[2]), resseq: r[3], color: plddtColor(r[4]) }))
    const protCenter = ca.reduce((v, a) => v.add(a.p), new THREE.Vector3()).multiplyScalar(1 / ca.length)
    const rb = ribbon(ca, 0.32); root.add(rb.core, rb.glow)
    // MSA 단계: 같은 뼈대를 보존도로 칠하고, 포켓 잔기(니라파립 5 Å 안)는 주황으로 강조
    const pocketSet = new Set(hero.msa.pocket_residues)
    const rbCons = ribbon(hero.ribbon.map((r) => ({ p: new THREE.Vector3(r[0], r[1], r[2]), resseq: r[3],
      color: pocketSet.has(r[3]) ? new THREE.Color(0xffb547) : conservationColor(hero.msa.conservation[r[3] - 1] ?? 0) })), 0.32)
    root.add(rbCons.core)
    // Boltz-2 단계: 같은 4R6E 포켓에 PARP1 억제제 4종 (니라파립은 DiffDock 1순위 포즈 그대로)
    const parpOthers = hero.parp_set.filter((x) => x.name !== drug).map((x) => { const g = ballStick(x.pose, 'solid', new THREE.Color(PARP_COLOR[x.name] ?? '#9aa7c7').getHex()); root.add(g); return g })
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
    const dd1 = ballStick(D.poses[0], 'solid')
    const ddPivot = new THREE.Group(); ddPivot.add(dd1); root.add(ddPivot)
    const alts = D.poses.slice(1).map((p) => { const g = ballStick(p, 'faint'); root.add(g); return g })
    const xtalLig = ballStick(D.xtal, 'ghost'); root.add(xtalLig)
    const glow = glowSprite(0xffb547); glow.scale.setScalar(6); root.add(glow)
    // 날아오는 궤적
    const trailPts = 60, trail = new THREE.Line(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(new Array(trailPts * 3).fill(0), 3)),
      new THREE.LineBasicMaterial({ color: 0xffb547, transparent: true, opacity: 0.8, blending: THREE.AdditiveBlending }))
    root.add(trail)
    const path = new THREE.CatmullRomCurve3([new THREE.Vector3(34, 22, -18), new THREE.Vector3(20, 4, 14), new THREE.Vector3(8, 9, 6), new THREE.Vector3(0, 0, 0)])

    // 단백질 전체가 들어오도록 경계 구 반지름으로 거리를 잡습니다
    const radius = Math.max(...ca.map((a) => a.p.distanceTo(protCenter)))
    // 화면 비율과 관계없이 단백질 전체가 들어오도록, 가로 · 세로 시야각 중 좁은 쪽으로 거리를 잡습니다(여유 12%)
    const fitDist = (aspectScale = 1) => {
      const vHalf = (camera.fov / 2) * Math.PI / 180, hHalf = Math.atan(Math.tan(vHalf) * camera.aspect * aspectScale)
      return (radius / Math.sin(Math.min(vHalf, hHalf))) * 1.12
    }
    const farDir = new THREE.Vector3(0.62, 0.34, 0.71).normalize(), msaDir = new THREE.Vector3(18, 12, 24).normalize()
    const farAt = (k = 1) => protCenter.clone().add(farDir.clone().multiplyScalar(fitDist(k)))
    const nearPos = new THREE.Vector3(10, 6.5, 13)
    // Boltz-2 는 억제제 4종이 같은 포켓에 겹쳐 보이도록 DiffDock 보다 1.7배 뒤에서 봅니다(분자가 화면을 덮지 않게)
    const nearBz = nearPos.clone().multiplyScalar(1.7)
    camera.position.copy(farAt()); controls.target.copy(protCenter)
    const ro = new ResizeObserver(resize); ro.observe(el); resize()
    const v = new THREE.Vector3()
    let lastStep = '', dragging = false, lastT = -1, userCam = false
    resetCam.current = () => { userCam = false; controls.autoRotate = true }

    const loop = (now: number) => {
      if (disposed) return
      const h = hold.current ? STEPS.find((s) => s.id === hold.current)! : null
      const raw = now - clock.current.t0 + clock.current.offset
      // 머무는 메뉴: 앞 단계의 결과(리본, 도킹)는 끝난 상태로 두고 그 구간만 반복합니다
      // 머무는 단계는 한 번 재생하고 마지막 장면을 유지합니다(약물이 박힌 뒤 사라지지 않게). 약물이 없는 MSA 만 반복합니다
      const t = h ? (h.id === 'msa' ? h.t0 + ((raw - h.t0) % (h.t1 - h.t0)) : Math.min(raw, h.t1 - 1)) : raw % LOOP
      const st = STEPS.find((s) => t >= s.t0 && t < s.t1) ?? STEPS[0]
      // 한 단계에 머물 때는 구간이 다시 시작돼도 카메라가 튀지 않게, 그 단계의 카메라 자리에 둡니다
      // 사건 시각을 지나면 커넥텀 층을 자극합니다 (구간이 다시 시작되면 lastT 도 되감깁니다)
      if (t < lastT) lastT = t - 1
      for (const [et, layer, amp] of EVENTS) if (lastT < et && et <= t) simRef.current?.stimulate('layer', layer, amp, 8)
      lastT = t
      const camT = h ? (h.id === 'msa' || h.id === 'of3' ? 0 : h.id === 'dd' ? t : 20000) : t
      if (st.id !== lastStep) { lastStep = st.id; setStep(st.id); userCam = false; controls.autoRotate = true }
      // OpenFold3: 리본을 N 말단부터 그리고, 끝에 함께 예측한 리간드가 나타납니다
      const U = rb.uniforms
      U.uEye.value.copy(camera.position)
      const C = rbCons.uniforms
      C.uEye.value.copy(camera.position)
      rbCons.core.visible = t < 3000; rb.core.visible = t >= 3000
      if (t < 3000) {
        // MSA-Search: 보존도로 칠한 뼈대 위로 정렬 띠가 지나가고, 결합 포켓(주황)을 가까이서 봅니다
        C.uReveal.value = 1; C.uAlpha.value = 1; C.uScan.value = clamp(t / 2800); C.uCut.value = 5
      } else {
        // OpenFold3: 끝이 빛나며 N 말단부터 그려지고, 가까이 갈 때는 카메라와 결합 자리 사이 사슬을 잘라 냅니다(포켓 컷어웨이)
        const closeK = ease((camT - 12200) / 3200) * (t >= 24500 ? 1 : 1 - ease((camT - 26000) / 4000))
        U.uReveal.value = t < 7800 ? ease((t - 3000) / 4800) : 1; U.uAlpha.value = 1; U.uScan.value = -1; U.uCut.value = 7 * closeK
      }
      film.uniforms.uTime.value = (now % 1000) / 1000
      // OpenFold3 단계는 단백질만 보여 줍니다(함께 예측한 리간드는 수치로만). 약물은 DiffDock 단계에서 처음 들어옵니다
      setOpacity(of3Lig, 0)
      // DiffDock: 나머지 포즈가 스쳐 가고, 1순위가 궤적을 그리며 날아와 박힙니다
      alts.forEach((g, i) => { const a = 11400 + i * 700; setOpacity(g, t < a ? 0 : t < a + 1400 ? Math.sin(((t - a) / 1400) * Math.PI) : 0) })
      const fk = ease((t - 13600) / 2600)
      const endFade = h ? 1 : clamp((LOOP - t) / 1200)
      setOpacity(ddPivot, t < 13600 ? 0 : endFade)
      // 경로는 바깥(0)에서 결합 자리(1, 원점)로 갑니다. 진행도 fk 가 0 → 1 이면 약물이 바깥에서 포켓으로 들어옵니다
      ddPivot.position.copy(path.getPointAt(fk))
      ddPivot.rotation.set(2.6 * (1 - fk), -1.8 * (1 - fk), 1.2 * (1 - fk))
      const pos = trail.geometry.getAttribute('position') as THREE.BufferAttribute
      for (let i = 0; i < trailPts; i++) { path.getPointAt((i / (trailPts - 1)) * fk, v); pos.setXYZ(i, v.x, v.y, v.z) }
      pos.needsUpdate = true
      setOpacity(trail, t > 13600 && t < 17200 ? clamp(1 - (t - 16200) / 1000) : 0)
      // 검증: 결정 구조(뼈대 + 리간드 정답)가 겹쳐집니다
      setOpacity(xtalLig, t < 16400 ? 0 : clamp((t - 16400) / 800) * endFade * (t >= 19000 && t < 24500 ? 0.25 : 1))
      // OpenFold3 단계 끝에 결정 구조 4R6E 뼈대를 겹쳐 예측과 비교하고, DiffDock 검증 때 다시 한 번 겹칩니다
      setOpacity(xtalTrace, t < 16400 || t > 19500 ? 0 : 0.9 * Math.sin(clamp((t - 16400) / 3100) * Math.PI))
      // Boltz-2: 억제제 3종이 차례로 같은 포켓에 나타납니다(니라파립은 그대로)
      parpOthers.forEach((g, i) => setOpacity(g, t < 19400 + i * 700 ? 0 : t < 24500 ? clamp((t - 19400 - i * 700) / 500) : 0))
      const flash = t > 16200 && t < 18400 ? Math.sin(((t - 16200) / 2200) * Math.PI) : 0
      glow.material.opacity = 0.08 + 0.35 * flash + (t > 19000 ? 0.04 * (1 + Math.sin(now / 900)) : 0)
      // 카메라: 전체 → 결합 자리로 다가갔다가 다시 물러납니다
      const inK = ease((camT - 12200) / 3200), outK = ease((camT - 26000) / 4000)
      const closeK2 = t >= 24500 ? inK : inK * (1 - outK)
      const farPos = farAt(st.id === 'critic' ? 0.5 : 1)
      const want = t < 3000 ? protCenter.clone().add(msaDir.clone().multiplyScalar(fitDist())) : farPos.clone().lerp(st.id === 'bz' ? nearBz : nearPos, closeK2), tgt = t < 3000 ? protCenter.clone() : protCenter.clone().lerp(new THREE.Vector3(), closeK2)
      // 크리틱: 오른쪽 절반에 Factor Xa 를 띄우므로 PARP1 장면을 왼쪽 절반 가운데로 옮깁니다
      const W = el.clientWidth, H = el.clientHeight
      if (st.id === 'critic') camera.setViewOffset(W, H, W * 0.25, 0, W, H); else camera.clearViewOffset()
      if (!dragging && !userCam) { camera.position.lerp(want, 0.04); controls.target.lerp(tgt, 0.06) }
      bloom.strength = 0.3 + 0.2 * flash
      controls.update(); if (shown()) composer.render()
      // 리간드 말풍선: 원점을 화면 좌표로 옮깁니다
      if (label.current) {
        v.set(0, 0, 0).project(camera)
        const show = t > 16400 && t < 24500
        label.current.style.opacity = show ? '1' : '0'
        label.current.style.transform = `translate(${((v.x + 1) / 2) * el.clientWidth + 26}px, ${((1 - v.y) / 2) * el.clientHeight - 74}px)`
      }
      raf = requestAnimationFrame(loop)
    }
    controls.addEventListener('start', () => { dragging = true; userCam = true; controls.autoRotate = false })
    controls.addEventListener('end', () => { dragging = false })
    raf = requestAnimationFrame(loop)
    const tk = setInterval(() => setTick((k) => k + 1), 500)
    return () => { disposed = true; cancelAnimationFrame(raf); clearInterval(tk); ro.disconnect(); controls.dispose(); disposeAll(scene); composer.dispose(); renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove() }
  }, [hero, drug, epoch]) // eslint-disable-line react-hooks/exhaustive-deps

  const done = (id: StepId) => STEPS.findIndex((s) => s.id === id) < STEPS.findIndex((s) => s.id === step)
  const tNow = (performance.now() - clock.current.t0 + clock.current.offset) % LOOP
  void tick
  const legend = (
    <div className="row wrap mono" style={{ gap: 14, fontSize: 11, color: 'var(--text-2)' }}>
      <span>pLDDT</span>
      {[['#37e6ff', '≥ 90'], ['#4d8dff', '70–90'], ['#ffcc4d', '50–70'], ['#ff8b35', '< 50']].map(([c, l]) => <span key={l}><i style={{ display: 'inline-block', width: 16, height: 3, background: c, marginRight: 6, verticalAlign: 'middle', boxShadow: `0 0 8px ${c}` }} />{l}</span>)}
    </div>
  )
  const hudAll = HUD()
  const hud: [string, string] = step === 'dd' ? [`DIFFDOCK · POSE 1 / 5 · ${D.crystal_pdb}`, t(`${dname} → PARP1 결합 자리`, `${dname} → PARP1 binding site`)]
    : step === 'bz' ? [t(`BOLTZ-2 · PARP1 억제제 ${hero.parp_set.length}종 · 같은 포켓`, `BOLTZ-2 · ${hero.parp_set.length} PARP1 INHIBITORS · SAME POCKET`), hudAll.bz[1]] : hudAll[step]
  // 크리틱이 반려하는 주장: Vina 가 두 표적 모두 있으면 Vina, 아니면 DiffDock 신뢰도로 씁니다(어느 쪽이든 교차 표적 비교)
  const useVina = D.vina !== null && D.xa.vina !== null
  const pv = useVina ? D.vina! : D.dd_conf, xv = useVina ? D.xa.vina! : D.xa.dd_conf
  const hi = useVina ? (pv <= xv ? 'PARP1' : 'Factor Xa') : (pv >= xv ? 'PARP1' : 'Factor Xa')
  const critClaim = t(`“${dname}은(는) ${useVina ? 'Vina' : 'DiffDock 신뢰도'} PARP1 ${pv}, Factor Xa ${xv} 이므로 ${hi} 에 선택적이다”`,
    `“${dname} scores ${useVina ? 'Vina' : 'DiffDock confidence'} PARP1 ${pv} and Factor Xa ${xv}, so it is selective for ${hi}”`)
  const stat: Record<StepId, ReactNode> = {
    msa: <Big eyebrow={t('MSA-Search NIM · 상동 서열 정렬', 'MSA-Search NIM · homologous sequence alignment')} value={String(m.msa_homologs)} unit={t('서열', 'sequences')}
      lines={[t(<span>결합 포켓 잔기 {hero.msa.pocket_residues.length}개의 보존도 <b style={{ color: 'var(--jev)' }}>{hero.msa.pocket_mean.toFixed(2)}</b> · 단백질 전체 {hero.msa.overall_mean.toFixed(2)}</span>,
          <span>Conservation of the {hero.msa.pocket_residues.length} binding-pocket residues <b style={{ color: 'var(--jev)' }}>{hero.msa.pocket_mean.toFixed(2)}</b> · whole protein {hero.msa.overall_mean.toFixed(2)}</span>),
        <span className="dim">{t('보존도 = 상동 서열 중 PARP1 과 같은 아미노산의 비율 · 이 정렬이 OpenFold3 입력이 됩니다', 'Conservation = share of homologous sequences with the same amino acid as PARP1 · this alignment becomes the OpenFold3 input')}</span>]}
      foot={<span className="mono" style={{ fontSize: 11, color: 'var(--ok)' }}>{t('포켓 잔기가 더 잘 보존된다는 것은 여러 종에서 약물이 붙는 자리를 지켜 왔다는 뜻입니다', 'Better-conserved pocket residues mean the drug-binding site has been preserved across species')}</span>} />,
    of3: <Big eyebrow={t(`OpenFold3 NIM · 복합체 예측 · ${m.of3_seconds} s`, `OpenFold3 NIM · complex prediction · ${m.of3_seconds} s`)} value={m.plddt.toFixed(2)} unit="pLDDT"
      lines={[`pTM ${m.ptm} · ipTM ${m.iptm}`, t(`4R6E 결정 구조 대비 Cα RMSD ${m.ca_rmsd_kabsch.toFixed(1)} Å · ${m.matched_ca} Cα`, `Cα RMSD vs. the 4R6E crystal structure ${m.ca_rmsd_kabsch.toFixed(1)} Å · ${m.matched_ca} Cα`), <span style={{ color: 'var(--jev)' }}>{t('리간드 RMSD', 'Ligand RMSD')} {m.of3_ligand_rmsd} Å</span>]}
      foot={<div className="stack" style={{ gap: 12 }}>{legend}<div className="mono" style={{ fontSize: 11, color: 'var(--ok)' }}>{t('고전 기준 · pLDDT ≥ 90 · 결정 구조 대비 Cα RMSD ≤ 2 Å', 'Classic criteria · pLDDT ≥ 90 · Cα RMSD ≤ 2 Å vs. the crystal structure')}</div></div>} />,
    dd: <Big eyebrow={t(`DiffDock NIM · ${dname} · 포즈 ${D.pose_eval.length}개 중 1순위`, `DiffDock NIM · ${dname} · top pose of ${D.pose_eval.length}`)} value={D.dd_rmsd?.toFixed(2) ?? '–'} unit="Å RMSD"
      lines={[t(`결정 구조 ${D.crystal_pdb}${D.crystal_pdb !== '4R6E' ? '(4R6E 에 Cα 로 겹침)' : ''} 의 ${dname} 자리 재현 · 신뢰도 ${D.dd_conf}`,
          `Reproduces the ${dname} site in crystal structure ${D.crystal_pdb}${D.crystal_pdb !== '4R6E' ? ' (superposed on 4R6E by Cα)' : ''} · confidence ${D.dd_conf}`),
        <span className="dim">{t('나머지 포즈', 'Other poses')} {D.pose_eval.slice(1).map((p) => (p.rmsd === null ? '–' : p.rmsd.toFixed(2))).join(' · ')} Å</span>,
        D.dd_rmsd !== null && D.dd_rmsd <= 2 ? <span style={{ color: 'var(--ok)' }}>{t('고전 기준 · 1순위 포즈 RMSD ≤ 2 Å 통과', 'Classic criterion · top-pose RMSD ≤ 2 Å: pass')}</span> : <span style={{ color: 'var(--bad)' }}>{t('고전 기준 · 1순위 포즈 RMSD ≤ 2 Å 미달', 'Classic criterion · top-pose RMSD ≤ 2 Å: not met')}</span>,
        D.dd_conf < 0 && D.dd_rmsd !== null && D.dd_rmsd <= 2 ? <span className="dim" style={{ fontSize: 13 }}>{t('신뢰도는 음수인데 자리는 맞았습니다 · 신뢰도는 정답 여부의 확률 추정일 뿐입니다', 'Confidence is negative, yet the site is correct · confidence is only an estimated probability of being right')}</span> : '']} />,
    bz: <Big eyebrow={t('Boltz-2 NIM · 같은 PARP1 포켓 · 친화도 예측', 'Boltz-2 NIM · same PARP1 pocket · affinity prediction')} value={D.boltz_pic50?.toFixed(2) ?? '–'} unit={`pIC50 · ${dname}`}
      lines={[...hero.parp_set.map((x) => (
        <div className="row between" style={{ fontSize: 13.5, gap: 10, fontWeight: x.name === drug ? 700 : 500 }} key={x.name}>
          <span><i style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 5, marginRight: 8, background: x.name === drug ? '#ffb547' : PARP_COLOR[x.name] }} />{x.name === '15r' ? '15R' : x.name.charAt(0).toUpperCase() + x.name.slice(1)}</span>
          <span className="num">{t('예측', 'Predicted')} {x.boltz_pic50?.toFixed(2) ?? '–'} · {t('실측', 'measured')} {x.chembl ?? t('기록 없음', 'no record')}</span>
        </div>)),
        extras.bench ? <span className="dim" style={{ fontSize: 13 }}>{t(`PARP1 ${extras.bench.n}종 벤치마크`, `PARP1 benchmark of ${extras.bench.n} drugs ·`)} Spearman {extras.bench.spearman.toFixed(3)} · MAE {extras.bench.mae} log</span> : '']} />,
    critic: <Big eyebrow={extras.critic ? t(`크리틱 3단 · ${extras.critic.model} · ${extras.critic.sec} s`, `Three-stage critic · ${extras.critic.model} · ${extras.critic.sec} s`) : t('크리틱 3단', 'Three-stage critic')} value={extras.critic ? `${extras.critic.caught}/${extras.critic.n_over}` : '–'} unit={t('과잉해석 반려', 'overclaims rejected')}
      lines={[<span style={{ fontSize: 14 }}>{critClaim}</span>,
        <span><span className="chip bad">REJECT</span> <span className="dim" style={{ fontSize: 13 }}>{t('숫자는 모두 실측이지만 다른 표적의 도킹 점수는 비교할 수 없습니다', 'All numbers are real, but docking scores for different targets cannot be compared')}</span></span>,
        extras.critic ? <span className="dim" style={{ fontSize: 13 }}>{t(`정상 주장 ${extras.critic.passed}/${extras.critic.n_valid} 통과`, `Valid claims passed ${extras.critic.passed}/${extras.critic.n_valid}`)}</span> : '']} />,
  }

  return (
    <div className="stack" style={{ gap: 14 }}>
      {!only && <div className="row between" style={{ marginBottom: -4 }}>
        <span className="mono dim" style={{ fontSize: 10.5 }}>{held ? t(`${STEPS.find((s) => s.id === held)!.label} 단계를 반복 재생 중`, `Looping the ${STEPS.find((s) => s.id === held)!.label} step`) : t('다섯 단계를 차례로 재생 중 · 단계를 누르면 그 단계에 머뭅니다', 'Playing all five steps in order · click a step to stay on it')}</span>
        {held && <button className="chip" style={{ cursor: 'pointer' }} onClick={resume}>{t('▶ 전체 자동 재생', '▶ Play all steps')}</button>}
      </div>}
      <div className="row" style={{ gap: 8, alignItems: 'center' }}>
        <span className="mono dim" style={{ fontSize: 10.5, letterSpacing: 1.2 }}>{t('약물 선택 · PARP1 억제제', 'Choose a drug · PARP1 inhibitors')}</span>
        {HERO_DRUGS.filter((d) => d === 'niraparib' || hero.drugs?.[d]).map((d) => (
          <button key={d} className={`chip ${d === drug ? 'jev' : ''}`} style={{ cursor: 'pointer', fontSize: 12, padding: '4px 12px', fontWeight: d === drug ? 700 : 500 }}
            onClick={() => setDrug(d)}>{DRUG_LABEL[d]}{hero.drugs?.[d] && <span className="mono dim" style={{ marginLeft: 6, fontSize: 10 }}>{hero.drugs[d].crystal_pdb}</span>}</button>
        ))}
      </div>
      <Stepper step={step} done={done} onPick={jump} m={m} x={extras} ddRmsd={D.dd_rmsd} />
      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.35fr) minmax(320px, 1fr)', gap: 16, alignItems: 'start' }}>
        <div style={{ position: 'relative', height }}>
          <div ref={host} style={{ position: 'absolute', inset: 0, cursor: 'grab', borderRadius: 14, overflow: 'hidden', border: '1px solid var(--line)', visibility: step === 'msa' ? 'hidden' : 'visible' }}
            aria-label={t('OpenFold3 가 예측한 PARP1 과 니라파립, DiffDock 포즈, 결정 구조 4R6E. 드래그로 회전, 휠로 확대 · 축소, 오른쪽 드래그로 이동합니다.', 'PARP1 and niraparib as predicted by OpenFold3, DiffDock poses, and crystal structure 4R6E. Drag to rotate, scroll to zoom, right-drag to pan.')} />
          {(step === 'of3' || step === 'dd' || step === 'bz') && <div className="row" style={{ position: 'absolute', right: 40, top: 14, zIndex: 3, gap: 8, alignItems: 'center' }}>
            <button className="btn" style={{ padding: '6px 12px', fontSize: 12 }} onClick={() => resetCam.current()}
              title={t('드래그로 회전 · 휠로 확대/축소 · 오른쪽 드래그로 이동합니다. 누르면 단백질 전체가 보이는 시점으로 돌아갑니다.', 'Drag to rotate · scroll to zoom · right-drag to pan. Click to return to a view of the whole protein.')}>{t('⤢ 전체 보기', '⤢ Fit view')}</button>
          </div>}
          {step === 'critic' && (
            <div className="fade-in" style={{ position: 'absolute', top: 0, bottom: 0, right: 0, width: '50%', zIndex: 1, borderLeft: '1px solid var(--line2)', borderRadius: '0 14px 14px 0', overflow: 'hidden' }}>
              <SplitTarget key={drug} xa={{ ...hero.critic_split.xa, niraparib: D.xa.ligand, dd_conf: D.xa.dd_conf, vina: D.xa.vina ?? hero.critic_split.xa.vina }} />
              <div style={{ position: 'absolute', left: 16, bottom: 14, pointerEvents: 'none' }}>
                <div className="mono" style={{ fontSize: 10.5, letterSpacing: 1.4, color: '#ff7a45' }}>FACTOR XA · PDB 2P16</div>
                <div className="num" style={{ fontSize: 15 }}>{D.xa.vina !== null ? `Vina ${D.xa.vina} · ` : ''}DiffDock {D.xa.dd_conf}</div>
              </div>
            </div>
          )}
          {step === 'critic' && (
            <div className="fade-in" style={{ position: 'absolute', left: 16, bottom: 14, zIndex: 2, pointerEvents: 'none' }}>
              <div className="mono" style={{ fontSize: 10.5, letterSpacing: 1.4, color: 'var(--c-sense)' }}>PARP1 · PDB 4R6E</div>
              <div className="num" style={{ fontSize: 15 }}>{D.vina !== null ? `Vina ${D.vina} · ` : ''}DiffDock {D.dd_conf}</div>
            </div>
          )}
          {step === 'msa' && (
            // MSA 단계에서는 뒤의 3D 단백질을 숨기고 불투명한 바탕을 깔아, 페이드 동안 단백질 잔상이 비치지 않게 합니다
            <div key="ov-msa" style={{ position: 'absolute', inset: 0, zIndex: 1, background: '#070b16', borderRadius: 14 }}>
              <MsaAnimation msa={hero.msa} query={hero.msa.query} duration={only ? 9000 : 2800} />
            </div>
          )}
          {step === 'bz' && <AffinityMeter key={`ov-bz-${drug}`} items={hero.parp_set} hero={drug} />}
          <div className="hud-corners" style={{ position: 'absolute', inset: 10, pointerEvents: 'none', zIndex: 1 }} />
          <div key={`hud-${step}-${drug}`} style={{ position: 'absolute', left: 22, top: 18, zIndex: 2, pointerEvents: 'none' }}>
            <div className="mono" style={{ fontSize: 10.5, letterSpacing: 2, color: 'var(--c-sense)' }}>{hud[0]}<span className="hud-caret" /></div>
            <div className="hud-type" style={{ fontFamily: 'var(--font)', fontSize: 26, fontWeight: 700, marginTop: 6, letterSpacing: -0.3,
              textShadow: '1px 0 rgba(255,93,108,0.35), -1px 0 rgba(55,230,255,0.35)', ['--n' as string]: hud[1].length }}>{hud[1]}</div>
          </div>
          <div ref={label} style={{ position: 'absolute', left: 0, top: 0, pointerEvents: 'none', transition: 'opacity .4s', opacity: 0,
            padding: '7px 11px', borderRadius: 8, background: 'rgba(5,9,18,0.82)', border: '1px solid rgba(255,181,71,0.45)', whiteSpace: 'nowrap' }}>
            <div className="mono" style={{ fontSize: 10, letterSpacing: 1.3, color: 'var(--jev)' }}>LIGAND · {dname}</div>
            <div style={{ fontSize: 13.5, fontWeight: 600 }}>{tNow < 11000 ? t('단백질과 함께 예측 (OpenFold3)', 'Co-predicted with the protein (OpenFold3)') : tNow < 16400 ? t('DiffDock 1순위 포즈', 'DiffDock top pose') : t(`결정 구조와 ${D.dd_rmsd ?? '–'} Å`, `${D.dd_rmsd ?? '–'} Å from the crystal structure`)}</div>
          </div>
        </div>
        <div className="stack" style={{ gap: 14, alignSelf: 'stretch' }}>
          <ConnectomePanel height={Math.round(height * 0.42)} focus={FOCUS()[step]} />
          <div style={{ minHeight: 280 }}>{stat[step]}</div>
        </div>
      </div>
    </div>
  )
}
