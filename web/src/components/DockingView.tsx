import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { TARGET_PALETTE, ballStick, chainGradient, disposeAll, dust, glowSprite, makeRenderer, ribbon, setOpacity, type Atom, type Ligand } from '../lib/molScene'

// 재도킹 장면(DiffDock 페이지): 결정 구조 수용체(리본 + 포켓 원자) 위로 DiffDock NIM 포즈 5개가 스쳐 가고,
// 1순위 포즈가 궤적을 그리며 날아와 결정 구조 정답(흰 윤곽) 자리에 앉습니다. 성공이면 초록, 실패면 빨강으로 번쩍입니다.
// 좌표는 pipeline/discovery/build_redock_scenes.py 가 RCSB 결정 구조와 NIM 응답에서 뽑은 값(결정 리간드 중심 = 원점)이고,
// 날아오는 경로와 카메라만 연출입니다.

export interface RedockScene {
  drug: string; target: string; gene: string; pdb: string; chain: string; note: string; membrane: boolean
  top1_rmsd: number | null; success: boolean | null; poses: { rank: number; confidence: number | null; rmsd: number | null }[]
  ca: [number, number, number, number][]; pocket: Atom[]
  xtal: Ligand; pose: Ligand; alt_poses?: Ligand[]
}

const FLY_START = 1500, FLY_MS = 2300
const clamp = (v: number) => Math.max(0, Math.min(1, v))
const ease = (k: number) => 1 - Math.pow(1 - clamp(k), 3)

export default function DockingView({ scene, height = 600, playKey = 0, onSettled }: {
  scene: RedockScene | null; height?: number; playKey?: number; onSettled?: () => void
}) {
  const host = useRef<HTMLDivElement>(null)
  const settledRef = useRef(onSettled)
  settledRef.current = onSettled

  useEffect(() => {
    const el = host.current
    if (!el || !scene) return
    let disposed = false, raf = 0, dragging = false
    const { renderer, scene: s3, camera, composer, bloom, film, resize } = makeRenderer(el)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true; controls.autoRotate = true; controls.autoRotateSpeed = 0.6
    controls.minDistance = 10; controls.maxDistance = 120
    controls.addEventListener('start', () => { dragging = true })
    controls.addEventListener('end', () => { dragging = false })
    s3.add(dust())

    // 수용체 튜브: 표적마다 정해진 세 색으로 N → C 말단을 물들입니다 (FDDD 쇼릴 팔레트)
    const pal = TARGET_PALETTE[scene.gene] ?? [0x37e6ff, 0x4d8dff, 0xa58bff]
    const cols = chainGradient(scene.ca.length, ...pal)
    const rb = ribbon(scene.ca.map((c, i) => ({ p: new THREE.Vector3(c[0], c[1], c[2]), resseq: c[3], color: cols[i] })), 0.3)
    s3.add(rb.core, rb.glow)
    // 포켓 원자: 결정 리간드 중심 9 Å 안
    const pocketMat = new THREE.PointsMaterial({ color: 0x6c9cfa, size: 0.62, transparent: true, opacity: 0.85, depthWrite: false })
    s3.add(new THREE.Points(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(scene.pocket.flatMap((p) => [p[0], p[1], p[2]]), 3)), pocketMat))
    // 정답 · 나머지 포즈 · 1순위 포즈
    const ghost = ballStick(scene.xtal, 'ghost'); s3.add(ghost)
    const alts = (scene.alt_poses ?? []).map((p) => { const g = ballStick(p, 'faint'); s3.add(g); return g })
    const pose = ballStick(scene.pose, 'solid'); const pivot = new THREE.Group(); pivot.add(pose); s3.add(pivot)
    const tone = scene.success === null ? 0xffb547 : scene.success ? 0x3ddc97 : 0xff5d6c
    const glow = glowSprite(tone); glow.scale.setScalar(6); s3.add(glow)
    const path = new THREE.CatmullRomCurve3([new THREE.Vector3(26, 18, -14), new THREE.Vector3(15, 3, 11), new THREE.Vector3(6, 7, 4), new THREE.Vector3(0, 0, 0)])
    const N = 50, trail = new THREE.Line(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(new Array(N * 3).fill(0), 3)),
      new THREE.LineBasicMaterial({ color: 0xffb547, transparent: true, opacity: 0.8, blending: THREE.AdditiveBlending }))
    s3.add(trail)

    const flash = new THREE.Color(tone), base = new THREE.Color(0x6c9cfa)
    camera.position.set(34, 20, 42); controls.target.set(0, 0, 0)
    const near = new THREE.Vector3(12, 7, 15)
    const ro = new ResizeObserver(resize); ro.observe(el); resize()
    const v = new THREE.Vector3()
    const t0 = performance.now()
    let settled = false
    const loop = (now: number) => {
      if (disposed) return
      const t = now - t0
      alts.forEach((g, i) => { const s = 150 + i * 330; setOpacity(g, t < s ? 0 : t < s + 900 ? Math.sin(((t - s) / 900) * Math.PI) : 0) })
      const k = ease((t - FLY_START) / FLY_MS)
      setOpacity(pivot, t < FLY_START ? 0 : 1)
      pivot.position.copy(path.getPointAt(1 - k))
      pivot.rotation.set(2.4 * (1 - k), -1.7 * (1 - k), 1.1 * (1 - k))
      const pos = trail.geometry.getAttribute('position') as THREE.BufferAttribute
      for (let i = 0; i < N; i++) { path.getPointAt(Math.max(0, 1 - k) + (i / N) * k * 0.999, v); pos.setXYZ(i, v.x, v.y, v.z) }
      pos.needsUpdate = true
      setOpacity(trail, t > FLY_START && t < FLY_START + FLY_MS + 900 ? clamp(1 - (t - FLY_START - FLY_MS) / 900) : 0)
      setOpacity(ghost, t < FLY_START + FLY_MS - 200 ? 0.35 : 1)
      if (k >= 1 && !settled) { settled = true; settledRef.current?.() }
      const f = settled ? Math.max(0, 1 - (t - FLY_START - FLY_MS) / 1600) : 0
      pocketMat.color.copy(base).lerp(flash, f); pocketMat.size = 0.62 + 0.5 * f
      glow.material.opacity = 0.45 * f
      bloom.strength = 0.3 + 0.2 * f
      if (!dragging) camera.position.lerp(near, 0.012)
      // 포켓 컷어웨이: 카메라와 결합 자리 사이 사슬을 잘라 리간드가 늘 보이게 합니다
      rb.uniforms.uEye.value.copy(camera.position); rb.uniforms.uCut.value = 6.5
      film.uniforms.uTime.value = (now % 1000) / 1000
      controls.update(); composer.render()
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => { disposed = true; cancelAnimationFrame(raf); ro.disconnect(); controls.dispose(); disposeAll(s3); composer.dispose(); renderer.dispose(); renderer.domElement.remove() }
  }, [scene, playKey])

  return <div ref={host} style={{ width: '100%', height, cursor: 'grab', borderRadius: 16, overflow: 'hidden' }}
    aria-label="결정 구조 수용체 리본과 포켓 원자, 결정 구조 리간드(흰 윤곽), DiffDock 포즈. 드래그로 회전합니다." />
}
