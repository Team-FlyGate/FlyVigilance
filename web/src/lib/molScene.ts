import * as THREE from 'three'
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js'
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js'
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js'

// STEP 1 도킹 장면의 공통 그리기 도구. 단백질 리본과 리간드 공-막대 모양은 FDDD(ProteinRibbon.ts)를 따랐고,
// 색은 FlyGate 대시보드 토큰(web/src/index.css)과 맞췄습니다. 좌표는 모두 Å 단위 실측값을 그대로 씁니다.

export type Atom = [number, number, number, string]
export interface Ligand { atoms: Atom[]; bonds: [number, number][] }

export const ELEMENT: Record<string, number> = {
  C: 0xffb547, N: 0x6c9cfa, O: 0xff5d6c, S: 0xffcc4d, F: 0x3ddc97, Cl: 0x3ddc97, P: 0xff9f43, Br: 0xc0845a, I: 0xa58bff,
}

// OpenFold3 pLDDT 색: 높을수록 차가운 색 (AlphaFold 관례를 대시보드 팔레트로)
export function plddtColor(p: number) {
  if (p >= 90) return new THREE.Color(0x37e6ff)
  if (p >= 70) return new THREE.Color(0x4d8dff)
  if (p >= 50) return new THREE.Color(0xffcc4d)
  return new THREE.Color(0xff8b35)
}

/** Cα 를 따라가는 매끈한 튜브. 끊긴 곳(번호 불연속, 4.5 Å 초과)에서 조각을 나눕니다. 색은 잔기별로 받습니다. */
export function ribbon(ca: { p: THREE.Vector3; resseq: number; color: THREE.Color }[], radius = 0.34) {
  const runs: typeof ca[] = []
  for (const a of ca) {
    const run = runs.at(-1), prev = run?.at(-1)
    if (!prev || a.resseq - prev.resseq !== 1 || a.p.distanceTo(prev.p) > 4.5) runs.push([a])
    else run!.push(a)
  }
  const core = new THREE.Group(), glow = new THREE.Group()
  const meshes: THREE.Mesh[] = []
  for (const run of runs) {
    if (run.length < 2) continue
    const curve = new THREE.CatmullRomCurve3(run.map((a) => a.p), false, 'centripetal')
    const seg = run.length * 6
    for (const [target, r, opacity, additive] of [[core, radius, 1, false], [glow, radius * 2.2, 0.06, true]] as const) {
      const geo = new THREE.TubeGeometry(curve, seg, r, 8, false)
      const colors: number[] = []
      const ring = 9
      for (let i = 0; i <= seg; i++) {
        const c = run[Math.min(run.length - 1, Math.round((i / seg) * (run.length - 1)))].color
        for (let j = 0; j < ring; j++) colors.push(c.r, c.g, c.b)
      }
      geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3))
      const mat = additive
        ? new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false })
        : new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.35, metalness: 0.15, emissive: 0x06101e, emissiveIntensity: 0.4 })
      const mesh = new THREE.Mesh(geo, mat)
      mesh.userData.total = geo.index ? geo.index.count : 0
      meshes.push(mesh)
      target.add(mesh)
    }
  }
  return { core, glow, meshes }
}

/** 리본을 N 말단부터 그리는 정도(0–1). 튜브 인덱스 범위를 잘라 그립니다. */
export function drawRibbon(meshes: THREE.Mesh[], k: number) {
  for (const m of meshes) m.geometry.setDrawRange(0, Math.floor((m.userData.total as number) * k / 6) * 6)
}

function cylinder(a: THREE.Vector3, b: THREE.Vector3, r: number, mat: THREE.Material) {
  const d = b.clone().sub(a)
  const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, d.length(), 10), mat)
  m.position.copy(a).add(b).multiplyScalar(0.5)
  m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize())
  return m
}

/** 리간드 공-막대. ghost 는 결정 구조 정답(흰 윤곽), faint 는 나머지 포즈(탐색 흔적). */
export function ballStick(lig: Ligand, style: 'solid' | 'ghost' | 'faint' = 'solid') {
  const g = new THREE.Group()
  const pts = lig.atoms.map((a) => new THREE.Vector3(a[0], a[1], a[2]))
  const mats = new Map<string, THREE.Material>()
  const mat = (el: string) => {
    if (!mats.has(el)) {
      const c = ELEMENT[el] ?? 0xd8dce8
      mats.set(el, style === 'solid'
        ? new THREE.MeshStandardMaterial({ color: c, emissive: c, emissiveIntensity: 0.55, roughness: 0.25, metalness: 0.15, transparent: true, opacity: 1 })
        : new THREE.MeshBasicMaterial({ color: style === 'ghost' ? 0xe8eefc : c, transparent: true, opacity: style === 'ghost' ? 0.28 : 0.22, depthWrite: false,
          blending: style === 'faint' ? THREE.AdditiveBlending : THREE.NormalBlending }))
    }
    return mats.get(el)!
  }
  const r = style === 'solid' ? 0.36 : 0.3
  lig.atoms.forEach((a, i) => { const m = new THREE.Mesh(new THREE.SphereGeometry(r, 18, 12), mat(a[3])); m.position.copy(pts[i]); g.add(m) })
  for (const [i, j] of lig.bonds) {
    const mid = pts[i].clone().add(pts[j]).multiplyScalar(0.5)
    g.add(cylinder(pts[i], mid, style === 'solid' ? 0.15 : 0.1, mat(lig.atoms[i][3])), cylinder(mid, pts[j], style === 'solid' ? 0.15 : 0.1, mat(lig.atoms[j][3])))
  }
  return g
}

export function setOpacity(o: THREE.Object3D, v: number) {
  o.traverse((c) => {
    if (c instanceof THREE.Mesh || c instanceof THREE.Line || c instanceof THREE.Points) {
      for (const m of Array.isArray(c.material) ? c.material : [c.material]) {
        if (m.userData.base === undefined) m.userData.base = m.opacity
        m.transparent = true; m.opacity = m.userData.base * v
      }
    }
  })
  o.visible = v > 0.002
}

/** 결합 자리의 부드러운 빛 (도착할 때 퍼집니다) */
export function glowSprite(color: number) {
  const cv = document.createElement('canvas'); cv.width = cv.height = 128
  const x = cv.getContext('2d')!
  const g = x.createRadialGradient(64, 64, 0, 64, 64, 64)
  g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(0.25, 'rgba(255,255,255,0.45)'); g.addColorStop(1, 'rgba(255,255,255,0)')
  x.fillStyle = g; x.fillRect(0, 0, 128, 128)
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(cv), color, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }))
  return s
}

/** 먼 배경의 은은한 입자 */
export function dust(n = 700, r = 120) {
  const p: number[] = []
  let s = 7
  const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647)
  for (let i = 0; i < n; i++) {
    const u = rnd() * 2 - 1, th = rnd() * Math.PI * 2, rr = r * (0.45 + 0.55 * rnd())
    p.push(rr * Math.sqrt(1 - u * u) * Math.cos(th), rr * u, rr * Math.sqrt(1 - u * u) * Math.sin(th))
  }
  return new THREE.Points(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(p, 3)),
    new THREE.PointsMaterial({ color: 0x4d8dff, size: 0.35, transparent: true, opacity: 0.35, depthWrite: false }))
}

export function makeRenderer(el: HTMLElement) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.05
  el.appendChild(renderer.domElement)
  const scene = new THREE.Scene()
  // 후처리(블룸)를 거치면 투명 배경이 사라지므로 카드 배경과 같은 색을 깝니다
  scene.background = new THREE.Color(0x070b16)
  scene.fog = new THREE.FogExp2(0x04060c, 0.012)
  scene.add(new THREE.HemisphereLight(0xcfe8ff, 0x10183a, 1.6))
  const key = new THREE.DirectionalLight(0xffffff, 2.2); key.position.set(30, 40, 30); scene.add(key)
  const rim = new THREE.DirectionalLight(0x37e6ff, 1.2); rim.position.set(-30, -10, -40); scene.add(rim)
  const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 600)
  const composer = new EffectComposer(renderer)
  composer.addPass(new RenderPass(scene, camera))
  const bloom = new UnrealBloomPass(new THREE.Vector2(512, 512), 0.6, 0.45, 0.42)
  composer.addPass(bloom)
  composer.addPass(new OutputPass())
  const resize = () => {
    const w = el.clientWidth, h = Math.max(1, el.clientHeight)
    renderer.setSize(w, h, false); composer.setSize(w, h); bloom.resolution.set(w, h)
    camera.aspect = w / h; camera.updateProjectionMatrix()
  }
  return { renderer, scene, camera, composer, bloom, resize }
}

export function disposeAll(root: THREE.Object3D) {
  root.traverse((o) => {
    if (o instanceof THREE.Mesh || o instanceof THREE.Line || o instanceof THREE.Points || o instanceof THREE.Sprite) {
      o.geometry.dispose()
      for (const m of Array.isArray(o.material) ? o.material : [o.material]) {
        if ('map' in m && m.map instanceof THREE.Texture) m.map.dispose()
        m.dispose()
      }
    }
  })
}
