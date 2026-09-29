import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { ballStick, disposeAll, dust, makeRenderer, plddtColor, ribbon, type Atom, type Ligand } from '../lib/molScene'
import { SOURCE_LABEL, getCatalog, getSceneForSelection, getStore, ligandName, targetLabel, type BoltzResult, type DockResult, type Envelope, type MsaResult, type Of3Result, type Scene } from '../lib/discovery'
import { t } from '../lib/i18n'
import MsaAnimation, { type MsaData } from './MsaAnimation'
import AffinityMeter from './AffinityMeter'
import DockingView, { type RedockScene } from './DockingView'
import type { StepId } from './HeroDocking'

// STEP 1 단계 페이지 위 장면을 "라이브 실행" 결과로 바꿔 그립니다. 좌표 · 값은 이번 NIM 응답 그대로입니다.
// - MSA-Search: 이번 정렬(상위 서열)을 MsaAnimation 으로
// - OpenFold3: 이번 예측 구조를 pLDDT 색 리본으로 그려 나가고 결정 구조 Cα(흰 선)를 겹침. 약물 없이 단백질만
// - DiffDock: 결정 구조 수용체 + 이번 포즈 5개를 DockingView 로(결합 자리 중심 = 원점)
// - Boltz-2: 이번 예측 복합체(리본 + 리간드)와 예측 pIC50 · ChEMBL 실측 눈금

type XYZ = number[]
type RawAtom = [string, number, number, number]
const centroid = (ps: XYZ[]) => [0, 1, 2].map((k) => ps.reduce((s, p) => s + Number(p[k]), 0) / Math.max(1, ps.length))
// 라이브 원자 [원소, x, y, z] → 장면 원자 [x, y, z, 원소], c 만큼 옮김
const toLigand = (atoms: RawAtom[], bonds: number[][], c: XYZ = [0, 0, 0]): Ligand =>
  ({ atoms: atoms.map(([el, x, y, z]) => [x - c[0], y - c[1], z - c[2], el] as Atom), bonds: bonds.map((b) => [b[0], b[1]] as [number, number]) })
// OpenFold3 pLDDT 는 0–100, Boltz-2 구조 파일 값은 0–1 일 수 있어 맞춥니다
const pl100 = (v: number[]) => (v.length && Math.max(...v) <= 1.0001 ? v.map((x) => x * 100) : v)

function Structure({ ca, plddt, xtalCa, lig, height, reveal }: { ca: XYZ[]; plddt: number[]; xtalCa?: XYZ[]; lig?: Ligand; height: number; reveal: boolean }) {
  const host = useRef<HTMLDivElement>(null)
  const [epoch, setEpoch] = useState(0)
  useEffect(() => {
    const el = host.current
    if (!el || ca.length < 2) return
    let disposed = false, raf = 0, user = false
    const { renderer, scene, camera, composer, bloom, film, resize, shown } = makeRenderer(el, () => setEpoch((k) => k + 1))
    bloom.strength = 0.3
    scene.add(dust(300, 120))
    const pl = pl100(plddt)
    const rb = ribbon(ca.map((p, i) => ({ p: new THREE.Vector3(p[0], p[1], p[2]), resseq: i + 1, color: plddtColor(pl[i] ?? 0) })), 0.32)
    scene.add(rb.core, rb.glow)
    if (xtalCa && xtalCa.length > 1) {
      const xs: number[] = []
      for (let i = 1; i < xtalCa.length; i++) {
        const a = xtalCa[i - 1], b = xtalCa[i]
        if (Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]) < 4.3) xs.push(a[0], a[1], a[2], b[0], b[1], b[2])
      }
      scene.add(new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(xs, 3)),
        new THREE.LineBasicMaterial({ color: 0xe8eefc, transparent: true, opacity: 0.35 })))
    }
    if (lig && lig.atoms.length) scene.add(ballStick(lig, 'solid'))
    // 카메라: 리간드가 있으면(Boltz-2) 리간드 중심, 없으면 단백질 전체가 들어오게
    const center = new THREE.Vector3(...(lig && lig.atoms.length ? centroid(lig.atoms as unknown as XYZ[]) : centroid(ca)) as [number, number, number])
    const pc = new THREE.Vector3(...(centroid(ca) as [number, number, number]))
    const radius = Math.max(...ca.map((p) => pc.distanceTo(new THREE.Vector3(p[0], p[1], p[2]))))
    const dir = new THREE.Vector3(0.62, 0.34, 0.71).normalize()
    const ro = new ResizeObserver(resize); ro.observe(el); resize()
    // 단백질 전체가 칸에 들어오는 거리(HeroDocking 의 fitDist 와 같은 계산). Boltz-2 는 리간드 둘레를 가까이서 봅니다
    const vHalf = (camera.fov / 2) * Math.PI / 180, hHalf = Math.atan(Math.tan(vHalf) * camera.aspect)
    const dist = lig && lig.atoms.length ? 34 : (radius / Math.sin(Math.min(vHalf, hHalf))) * 1.12
    camera.position.copy(center).add(dir.multiplyScalar(dist))
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.target.copy(center); controls.enableDamping = true; controls.autoRotate = true; controls.autoRotateSpeed = 0.4
    controls.enablePan = true; controls.enableZoom = true; controls.minDistance = 8; controls.maxDistance = 260
    controls.addEventListener('start', () => { user = true; controls.autoRotate = false })
    rb.uniforms.uPocket.value.copy(center)
    const t0 = performance.now()
    const loop = (now: number) => {
      if (disposed) return
      const U = rb.uniforms
      // OpenFold3 는 N 말단부터 그려 나갑니다(구조가 예측되어 그려지는 모습)
      U.uReveal.value = reveal ? Math.min(1, (now - t0) / 3200) : 1; U.uAlpha.value = 1; U.uScan.value = -1; U.uCut.value = 0
      U.uEye.value.copy(camera.position)
      film.uniforms.uTime.value = (now % 1000) / 1000
      controls.update(); if (shown()) composer.render()
      raf = requestAnimationFrame(loop)
    }
    void user
    raf = requestAnimationFrame(loop)
    return () => { disposed = true; cancelAnimationFrame(raf); ro.disconnect(); controls.dispose(); disposeAll(scene); composer.dispose(); renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove() }
  }, [ca, plddt, xtalCa, lig, reveal, epoch])
  return <div ref={host} style={{ position: 'absolute', inset: 0, cursor: 'grab', borderRadius: 14, overflow: 'hidden', border: '1px solid var(--line)', height }}
    aria-label={t('이번 실행으로 받은 예측 구조. 드래그로 돌리고 휠로 확대, 오른쪽 드래그로 이동합니다.', 'Predicted structure from this run. Drag to rotate, scroll to zoom, right-drag to pan.')} />
}

function DockLive({ env, height, drugName }: { env: Envelope; height: number; drugName: string }) {
  const r = env.result as DockResult
  const [sc, setSc] = useState<Scene | null>(null)
  const [err, setErr] = useState(false)
  useEffect(() => { let live = true; getSceneForSelection().then((s) => live && setSc(s)).catch(() => live && setErr(true)); return () => { live = false } }, [env.req_id])
  const scene = useMemo<RedockScene | null>(() => {
    if (!sc || !r.poses?.length) return null
    // 결합 자리 중심(결정 리간드 중심, 없으면 1순위 포즈 중심)을 원점으로
    const c = sc.pocket_center ?? r.poses[0].centroid ?? centroid(r.poses[0].atoms.map((a) => a.slice(1) as XYZ))
    const xl = r.xtal_ligand ?? sc.xtal_ligand
    return {
      drug: drugName, target: sc.target, gene: env.target?.gene ?? sc.label, pdb: sc.pdb, chain: sc.chain, note: '', membrane: false,
      top1_rmsd: r.top1_rmsd, success: r.redock ? r.top1_success : null,
      poses: r.poses.map((p) => ({ rank: p.rank, confidence: p.confidence, rmsd: p.rmsd })),
      ca: sc.ca.map((p, i) => [p[0] - c[0], p[1] - c[1], p[2] - c[2], i + 1] as [number, number, number, number]),
      pocket: sc.pocket.map(([el, x, y, z]) => [x - c[0], y - c[1], z - c[2], el] as Atom),
      xtal: xl && xl.atoms.length ? toLigand(xl.atoms, xl.bonds, c) : { atoms: [], bonds: [] },
      pose: toLigand(r.poses[0].atoms, r.poses[0].bonds, c), alt_poses: r.poses.slice(1).map((p) => toLigand(p.atoms, p.bonds, c)),
    }
  }, [sc, r, env.target?.gene, drugName])
  if (err) return <div className="note" style={{ margin: 20 }}>{t('수용체 좌표를 받지 못해 도킹 장면을 그리지 못했습니다 · 아래 표의 수치는 이번 실행 값입니다', 'Could not load the receptor coordinates, so the docking scene is not drawn · the numbers in the table below are from this run')}</div>
  return scene ? <DockingView scene={scene} height={height} playKey={env.req_id ? env.req_id.length + env.req_id.charCodeAt(0) : 1} /> : <div className="shimmer" style={{ height }} />
}

// 고른 리간드의 화면 이름(한국어 이름은 카탈로그에서)
function useLigandName() {
  const [ko, setKo] = useState<Record<string, string>>({})
  useEffect(() => { getCatalog().then((c) => setKo(Object.fromEntries(Object.entries(c.ligands).map(([k, v]) => [k, v.ko])))).catch(() => {}) }, [])
  const s = getStore()
  return s.customLigand ? s.customLigand.name : ligandName(s.ligand, ko[s.ligand])
}

export default function LiveScene({ step, env, height = 600, pocket }: { step: StepId; env: Envelope; height?: number; pocket?: { query_len: number; residues: number[] } }) {
  const res = env.result
  const drugName = useLigandName()
  const src = env.source ? SOURCE_LABEL[env.source] : null
  const what = step === 'msa' ? targetLabel() : `${targetLabel()} + ${drugName}`
  const msa = useMemo<{ data: MsaData; query: string; pocketKnown: boolean } | null>(() => {
    if (step !== 'msa' || !res) return null
    const m = res as MsaResult
    const known = !!pocket && pocket.query_len === m.query_len && (env.params?.target ?? 'parp1') === 'parp1' && !env.params?.custom_target
    return {
      query: m.query, pocketKnown: known,
      data: {
        labels: m.rows.map((r) => [r.name, r.identity] as [string, number | null]), query_len: m.query_len, conservation: m.conservation,
        strip: m.rows.map((r) => [...r.seq].map((ch, i) => (ch === '-' || ch === '.' ? '-' : ch === m.query[i] ? '1' : '0')).join('')),
        pocket_residues: known ? pocket!.residues : [],
      },
    }
  }, [step, res, pocket, env.params])
  const of3 = step === 'of3' && res ? (res as Of3Result) : null
  const bz = step === 'bz' && res ? (res as BoltzResult) : null
  const bzLig = useMemo(() => (bz ? toLigand(bz.ligand_atoms, bz.ligand_bonds) : undefined), [bz])
  const n = (v: number | null | undefined, d = 2) => (v === null || v === undefined ? '–' : v.toFixed(d))
  const foot = of3 ? `pLDDT ${n(of3.scores.plddt ?? of3.mean_plddt, 1)} · pTM ${n(of3.scores.ptm, 3)}${of3.ca_rmsd !== null ? ` · ${t('결정 구조 대비', 'vs crystal')} Cα RMSD ${n(of3.ca_rmsd)} Å` : ''}`
    : step === 'dd' && res ? (() => { const d = res as DockResult; return `${t('1순위 신뢰도', 'Top-1 confidence')} ${n(d.top1_confidence, 3)}${d.redock ? ` · ${t('결정 자리', 'crystal site')} ${n(d.top1_rmsd)} Å` : ` · ${t('교차 도킹(정답 자리 없음)', 'cross-docking (no crystal pose)')}`}` })()
    : null

  return (
    <div style={{ position: 'relative', height }}>
      {step === 'msa' && msa && (
        <div className="fade-in" style={{ position: 'absolute', inset: 0 }}>
          <MsaAnimation key={env.req_id ?? 'msa'} msa={msa.data} query={msa.query} duration={9000} />
        </div>
      )}
      {of3 && <Structure key={env.req_id ?? 'of3'} ca={of3.ca} plddt={of3.plddt_per_residue} xtalCa={of3.xtal_ca?.length ? of3.xtal_ca : undefined} height={height} reveal />}
      {step === 'dd' && res && <div style={{ position: 'absolute', inset: 0, borderRadius: 14, overflow: 'hidden', border: '1px solid var(--line)' }}><DockLive env={env} height={height} drugName={drugName} /></div>}
      {bz && <Structure key={env.req_id ?? 'bz'} ca={bz.ca} plddt={bz.plddt_per_residue} lig={bzLig} height={height} reveal={false} />}
      {bz && <AffinityMeter key={`live-bz-${env.req_id ?? ''}`} hero={drugName} items={[{ name: drugName, boltz_pic50: bz.affinity.pic50, boltz_p: bz.affinity.probability_binary, chembl: bz.chembl?.median_pchembl ?? null, chembl_n: bz.chembl?.n ?? null }]} />}
      <div className="hud-corners" style={{ position: 'absolute', inset: 10, pointerEvents: 'none', zIndex: 1 }} />
      {step !== 'msa' && (
        <div style={{ position: 'absolute', left: 22, top: 18, zIndex: 2, pointerEvents: 'none' }}>
          <div className="mono" style={{ fontSize: 10.5, letterSpacing: 2, color: 'var(--nvidia)' }}>LIVE · {t('이번 실행', 'THIS RUN')}{src ? ` · ${src.text}` : ''}</div>
          <div style={{ fontFamily: 'var(--font)', fontSize: 24, fontWeight: 700, marginTop: 6 }}>{what}</div>
          {of3 && <div className="mono dim" style={{ fontSize: 11, marginTop: 4 }}>{t('약물 없이 단백질만 · 흰 선 = 결정 구조 Cα', 'Protein only, no drug · white line = crystal Cα')}</div>}
        </div>
      )}
      {step === 'msa' && msa && (
        <div className="mono" style={{ position: 'absolute', right: 18, top: 14, zIndex: 2, fontSize: 10.5, letterSpacing: 1.4, color: 'var(--nvidia)', pointerEvents: 'none' }}>
          LIVE · {what}{msa.pocketKnown ? '' : ` · ${t('결합 자리 정보 없음 → 가운데 구간', 'no binding-site info → middle window')}`}
        </div>
      )}
      {foot && <div className="mono" style={{ position: 'absolute', left: 22, bottom: 18, zIndex: 2, fontSize: 12.5, pointerEvents: 'none', color: 'var(--text)' }}>{foot}</div>}
    </div>
  )
}
