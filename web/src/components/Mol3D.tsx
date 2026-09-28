// FlyDiscovery 3D 표시기: CA 골격(선), 리간드(구·막대), 주머니 원자(점)를 하나의 three.js 장면에 그립니다.
// 좌표는 모두 API 응답(라이브 NIM)에서 옵니다. 원자 수는 상한을 두어 프레임을 지킵니다.
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { plddtColor } from '../lib/discovery'

export type Atom = [string, number, number, number]
export interface Trace { key: string; points: number[][]; color: string; values?: number[]; width?: number; opacity?: number }
export interface Mol { key: string; atoms: Atom[]; bonds: number[][]; color: string; opacity?: number; active?: boolean; scale?: number }
export interface Props {
  traces?: Trace[]
  mols?: Mol[]
  cloud?: Atom[]
  focus?: number[] | null
  radius?: number
  height?: number | string
  spin?: boolean
  dockIn?: string | null   // 이 열쇠의 분자가 바뀌면 주머니 밖에서 들어오는 애니메이션을 한 번 재생합니다
  legend?: never
}

const EL_COLOR: Record<string, number> = {
  C: 0x9fb4d8, N: 0x4d8dff, O: 0xff5d6c, S: 0xffcc4d, F: 0x9dff6b, CL: 0x76b900, BR: 0xe2a74e,
  I: 0xa58bff, P: 0xffb547, H: 0xdfe8ff,
}
const MAX_CLOUD = 1400
const MAX_ATOMS = 90

function colorOf(el: string) {
  return EL_COLOR[el.toUpperCase()] ?? 0x8fa2ff
}

export default function Mol3D({ traces = [], mols = [], cloud = [], focus = null, radius = 26, height = 420,
  spin = true, dockIn = null }: Props) {
  const host = useRef<HTMLDivElement>(null)
  const state = useRef<{ scene?: THREE.Scene; group?: THREE.Group; dispose: (() => void)[] }>({ dispose: [] })
  const sig = useMemo(() => JSON.stringify([traces.map((t) => [t.key, t.points.length, t.color, t.opacity, t.values?.length]),
    mols.map((m) => [m.key, m.atoms.length, m.color, m.opacity, m.active, m.scale]), cloud.length, focus, radius]), [traces, mols, cloud, focus, radius])

  useEffect(() => {
    const el = host.current
    if (!el) return
    const W = () => el.clientWidth || 600
    const H = () => el.clientHeight || 420
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(W(), H())
    renderer.setClearColor(0x050912, 0)
    el.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(40, W() / H(), 0.5, 5000)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.autoRotate = spin
    controls.autoRotateSpeed = 0.55
    scene.add(new THREE.AmbientLight(0xffffff, 0.75))
    const key = new THREE.DirectionalLight(0xbfe6ff, 1.25)
    key.position.set(24, 30, 26)
    scene.add(key)
    const group = new THREE.Group()
    scene.add(group)
    state.current.scene = scene
    state.current.group = group
    const onResize = () => { renderer.setSize(W(), H()); camera.aspect = W() / H(); camera.updateProjectionMatrix() }
    const ro = new ResizeObserver(onResize)
    ro.observe(el)
    let raf = 0
    let alive = true
    const anim = { t: 1, dir: new THREE.Vector3(1, 0.4, 0.6).normalize(), targets: [] as THREE.Object3D[] }
    ;(group as THREE.Group & { __anim?: typeof anim }).__anim = anim
    const loop = () => {
      if (!alive) return
      if (anim.t < 1) {
        anim.t = Math.min(1, anim.t + 0.02)
        const k = 1 - Math.pow(anim.t, 3)
        for (const o of anim.targets) o.position.copy(anim.dir).multiplyScalar(k * 16)
      }
      controls.update()
      renderer.render(scene, camera)
      raf = requestAnimationFrame(loop)
    }
    loop()
    const cam = { camera, controls }
    ;(group as THREE.Group & { __cam?: typeof cam }).__cam = cam
    return () => {
      alive = false
      cancelAnimationFrame(raf)
      ro.disconnect()
      controls.dispose()
      renderer.dispose()
      if (renderer.domElement.parentElement === el) el.removeChild(renderer.domElement)
    }
  }, [spin])

  // 내용 갱신: 장면을 비우고 다시 채웁니다(입력은 한 단계 실행마다 한 번 바뀝니다)
  useEffect(() => {
    const group = state.current.group
    if (!group) return
    for (const d of state.current.dispose) d()
    state.current.dispose = []
    group.clear()
    const c = focus ?? [0, 0, 0]
    const pivot = new THREE.Group()
    pivot.position.set(-c[0], -c[1], -c[2])
    group.clear()
    group.add(pivot)

    for (const t of traces) {
      if (t.points.length < 2) continue
      const pts = t.points
      const pos = new Float32Array(pts.length * 3)
      const col = new Float32Array(pts.length * 3)
      const base = new THREE.Color(t.color)
      for (let i = 0; i < pts.length; i++) {
        pos[i * 3] = pts[i][0]; pos[i * 3 + 1] = pts[i][1]; pos[i * 3 + 2] = pts[i][2]
        const cc = t.values ? new THREE.Color(plddtColor(t.values[i] ?? 0)) : base
        col[i * 3] = cc.r; col[i * 3 + 1] = cc.g; col[i * 3 + 2] = cc.b
      }
      const g = new THREE.BufferGeometry()
      g.setAttribute('position', new THREE.BufferAttribute(pos, 3))
      g.setAttribute('color', new THREE.BufferAttribute(col, 3))
      const m = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: t.opacity ?? 0.9 })
      pivot.add(new THREE.Line(g, m))
      state.current.dispose.push(() => { g.dispose(); m.dispose() })
    }

    if (cloud.length) {
      const pts = cloud.slice(0, MAX_CLOUD)
      const pos = new Float32Array(pts.length * 3)
      const col = new Float32Array(pts.length * 3)
      for (let i = 0; i < pts.length; i++) {
        pos[i * 3] = pts[i][1]; pos[i * 3 + 1] = pts[i][2]; pos[i * 3 + 2] = pts[i][3]
        const cc = new THREE.Color(colorOf(pts[i][0]))
        col[i * 3] = cc.r * 0.6; col[i * 3 + 1] = cc.g * 0.6; col[i * 3 + 2] = cc.b * 0.6
      }
      const g = new THREE.BufferGeometry()
      g.setAttribute('position', new THREE.BufferAttribute(pos, 3))
      g.setAttribute('color', new THREE.BufferAttribute(col, 3))
      const m = new THREE.PointsMaterial({ size: 0.9, vertexColors: true, transparent: true, opacity: 0.55,
        blending: THREE.AdditiveBlending, depthWrite: false })
      pivot.add(new THREE.Points(g, m))
      state.current.dispose.push(() => { g.dispose(); m.dispose() })
    }

    const sphere = new THREE.SphereGeometry(1, 12, 10)
    const cyl = new THREE.CylinderGeometry(1, 1, 1, 8, 1, true)
    state.current.dispose.push(() => { sphere.dispose(); cyl.dispose() })
    const animTargets: THREE.Object3D[] = []
    for (const mol of mols) {
      const holder = new THREE.Group()
      const atoms = mol.atoms.slice(0, MAX_ATOMS)
      const opacity = mol.opacity ?? (mol.active ? 1 : 0.45)
      const rAtom = (mol.scale ?? 1) * (mol.active ? 0.42 : 0.3)
      const mat = new THREE.MeshStandardMaterial({ color: new THREE.Color(mol.color), roughness: 0.35, metalness: 0.1,
        transparent: opacity < 1, opacity, emissive: new THREE.Color(mol.color), emissiveIntensity: mol.active ? 0.45 : 0.15 })
      state.current.dispose.push(() => mat.dispose())
      const inst = new THREE.InstancedMesh(sphere, mat, atoms.length)
      const mtx = new THREE.Matrix4()
      atoms.forEach((a, i) => {
        const s = a[0] === 'H' ? rAtom * 0.5 : rAtom
        mtx.compose(new THREE.Vector3(a[1], a[2], a[3]), new THREE.Quaternion(), new THREE.Vector3(s, s, s))
        inst.setMatrixAt(i, mtx)
      })
      inst.instanceMatrix.needsUpdate = true
      holder.add(inst)
      const bonds = mol.bonds.filter(([i, j]) => i < atoms.length && j < atoms.length)
      if (bonds.length) {
        const bi = new THREE.InstancedMesh(cyl, mat, bonds.length)
        const up = new THREE.Vector3(0, 1, 0)
        bonds.forEach(([i, j], k) => {
          const a = new THREE.Vector3(atoms[i][1], atoms[i][2], atoms[i][3])
          const b = new THREE.Vector3(atoms[j][1], atoms[j][2], atoms[j][3])
          const mid = a.clone().add(b).multiplyScalar(0.5)
          const dir = b.clone().sub(a)
          const q = new THREE.Quaternion().setFromUnitVectors(up, dir.clone().normalize())
          mtx.compose(mid, q, new THREE.Vector3(rAtom * 0.32, dir.length(), rAtom * 0.32))
          bi.setMatrixAt(k, mtx)
        })
        bi.instanceMatrix.needsUpdate = true
        holder.add(bi)
      }
      pivot.add(holder)
      if (mol.active) animTargets.push(holder)
    }

    // 카메라 맞춤
    const g = group as THREE.Group & { __cam?: { camera: THREE.PerspectiveCamera; controls: OrbitControls }; __anim?: { t: number; dir: THREE.Vector3; targets: THREE.Object3D[] } }
    if (g.__cam) {
      const r = radius
      g.__cam.camera.position.set(r * 0.9, r * 0.5, r * 1.5)
      g.__cam.camera.near = Math.max(0.5, r / 200)
      g.__cam.camera.far = r * 40
      g.__cam.camera.updateProjectionMatrix()
      g.__cam.controls.target.set(0, 0, 0)
      g.__cam.controls.minDistance = r * 0.35
      g.__cam.controls.maxDistance = r * 6
      g.__cam.controls.update()
    }
    if (g.__anim) {
      g.__anim.targets = animTargets
      g.__anim.t = dockIn ? 0 : 1
      if (!dockIn) for (const o of animTargets) o.position.set(0, 0, 0)
    }
  }, [sig, dockIn, traces, mols, cloud, focus, radius])

  return <div ref={host} style={{ width: '100%', height, position: 'relative' }} />
}
