import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { TARGET_PALETTE, ballStick, chainGradient, disposeAll, dust, makeRenderer, ribbon, type Ligand } from '../lib/molScene'
import { t as tr } from '../lib/i18n'

// 크리틱 단계의 오른쪽 절반: 니라파립을 Factor Xa(2P16)에 넣은 DiffDock NIM 포즈.
// 왼쪽 PARP1 장면과 나란히 놓아 "다른 표적의 점수는 비교할 수 없다"는 반려 이유를 보여 줍니다(FDDD 쇼릴의 분할 화면).
// 좌표는 build_hero_scene.py 가 2P16 결정 구조와 NIM 응답에서 뽑은 값(아픽사반 결정 자리 중심 = 원점)입니다.

export interface XaSplit { pdb: string; chain: string; ca: [number, number, number, number][]; niraparib: Ligand; dd_conf: number; vina: number }

export default function SplitTarget({ xa }: { xa: XaSplit }) {
  const host = useRef<HTMLDivElement>(null)
  // WebGL 컨텍스트가 강제로 죽으면 올려서 장면을 새로 만듭니다
  const [epoch, setEpoch] = useState(0)
  useEffect(() => {
    const el = host.current
    if (!el) return
    let disposed = false, raf = 0
    const { scene, camera, composer, film, renderer, resize, shown } = makeRenderer(el, () => setEpoch((k) => k + 1))
    scene.add(dust(300, 90))
    const cols = chainGradient(xa.ca.length, ...(TARGET_PALETTE.F10))
    const rb = ribbon(xa.ca.map((c, i) => ({ p: new THREE.Vector3(c[0], c[1], c[2]), resseq: c[3], color: cols[i] })), 0.3)
    scene.add(rb.core)
    const lig = ballStick(xa.niraparib, 'solid'); scene.add(lig)
    // 니라파립은 Factor Xa 에서 아픽사반 자리(원점)와 다른 곳에 놓일 수 있으므로 포즈 중심을 카메라 목표로 삼습니다
    const at = xa.niraparib.atoms, c = new THREE.Vector3(at.reduce((s, a) => s + a[0], 0) / at.length, at.reduce((s, a) => s + a[1], 0) / at.length, at.reduce((s, a) => s + a[2], 0) / at.length)
    rb.uniforms.uPocket.value.copy(c)
    const ro = new ResizeObserver(resize); ro.observe(el); resize()
    const t0 = performance.now()
    const loop = (now: number) => {
      if (disposed) return
      const a = (now - t0) / 1000 * 0.12
      camera.position.set(c.x + Math.cos(a) * 46, c.y + 16, c.z + Math.sin(a) * 46); camera.lookAt(c)
      rb.uniforms.uEye.value.copy(camera.position); rb.uniforms.uCut.value = 4
      film.uniforms.uTime.value = (now % 1000) / 1000
      if (shown()) composer.render()
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => { disposed = true; cancelAnimationFrame(raf); ro.disconnect(); disposeAll(scene); composer.dispose(); renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove() }
  }, [xa, epoch])
  return <div ref={host} style={{ position: 'absolute', inset: 0 }} aria-label={tr('니라파립을 Factor Xa(2P16)에 넣은 DiffDock 포즈', 'DiffDock pose of niraparib placed into Factor Xa (2P16)')} />
}
