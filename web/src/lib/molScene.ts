import * as THREE from 'three'
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js'
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js'
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js'
import { ShaderPass } from 'three/examples/jsm/postprocessing/ShaderPass.js'

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

/** 단백질 튜브 셰이더. FDDD 모션 쇼릴 v1.1.0 의 튜브 셰이더를 옮겼습니다:
 *  잔기 색(정점 색) · 확산광 · 반사광 · 테두리광(프레넬), 그려 나가는 끝의 빛(uReveal),
 *  카메라와 결합 자리 사이의 사슬을 잘라 리간드를 보여 주는 포켓 컷어웨이(uCut, 잘린 테두리는 금색으로 빛남),
 *  MSA 정렬이 훑고 지나가는 띠(uScan). 좌표는 모두 Å 입니다. */
const TUBE_VS = `
attribute float aU; attribute vec3 color;
varying vec3 vN; varying vec3 vW; varying float vU; varying vec3 vC;
void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; vN = mat3(modelMatrix) * normal; vU = aU; vC = color;
  gl_Position = projectionMatrix * viewMatrix * w; }`
const TUBE_FS = `
uniform vec3 uEye; uniform vec3 uPocket; uniform float uReveal; uniform float uAlpha; uniform float uGlow; uniform float uCut; uniform float uScan;
varying vec3 vN; varying vec3 vW; varying float vU; varying vec3 vC;
void main(){
  if (vU > uReveal) discard;
  float rim = 0.0;
  if (uCut > 0.0) {
    vec3 ax = uPocket - uEye; float L = length(ax); ax /= L; vec3 d = vW - uEye; float tl = dot(d, ax);
    float r = length(d - ax * tl); float R = uCut * smoothstep(0.0, L * 0.6, tl);
    if (tl < L + 1.5 && r < R) discard;
    rim = exp(-(r - R) * 1.8) * step(tl, L + 1.5);
  }
  vec3 n = normalize(vN), v = normalize(uEye - vW); if (dot(n, v) < 0.0) n = -n;
  vec3 l = normalize(vec3(0.4, 0.8, 0.5));
  float df = max(dot(n, l), 0.0), sp = pow(max(dot(n, normalize(l + v)), 0.0), 40.0), fr = pow(1.0 - max(dot(n, v), 0.0), 2.0);
  vec3 c = vC * (0.07 + df * 0.5) + sp * 0.16 + vC * fr * 0.38 * uGlow + vec3(1.0, 0.8, 0.5) * rim * 0.6;
  float head = exp(-(uReveal - vU) * 160.0) * step(uReveal, 0.999); c += vec3(1.0, 0.95, 0.85) * head * 1.4;
  if (uScan >= 0.0) { float band = exp(-pow((vU - uScan) * 22.0, 2.0)); c = c * (0.6 + 0.4 * band) + vec3(0.55, 1.0, 1.0) * band * 0.45; }
  gl_FragColor = vec4(c, uAlpha);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`

export interface RibbonUniforms { uEye: { value: THREE.Vector3 }; uPocket: { value: THREE.Vector3 }; uReveal: { value: number }; uAlpha: { value: number }; uGlow: { value: number }; uCut: { value: number }; uScan: { value: number } }

/** Cα 를 따라가는 매끈한 튜브. 끊긴 곳(번호 불연속, 4.5 Å 초과)에서 조각을 나누고, 사슬 전체를 따라 0–1 의 진행값(aU)을 붙입니다. */
export function ribbon(ca: { p: THREE.Vector3; resseq: number; color: THREE.Color }[], radius = 0.34) {
  const runs: typeof ca[] = []
  for (const a of ca) {
    const run = runs.at(-1), prev = run?.at(-1)
    if (!prev || a.resseq - prev.resseq !== 1 || a.p.distanceTo(prev.p) > 4.5) runs.push([a])
    else run!.push(a)
  }
  const uniforms: RibbonUniforms = { uEye: { value: new THREE.Vector3() }, uPocket: { value: new THREE.Vector3() }, uReveal: { value: 1 }, uAlpha: { value: 1 },
    uGlow: { value: 1 }, uCut: { value: 0 }, uScan: { value: -1 } }
  const mat = new THREE.ShaderMaterial({ vertexShader: TUBE_VS, fragmentShader: TUBE_FS, uniforms: uniforms as unknown as Record<string, THREE.IUniform>, transparent: true })
  const core = new THREE.Group()
  const meshes: THREE.Mesh[] = []
  const total = ca.length
  let done = 0
  for (const run of runs) {
    if (run.length < 2) { done += run.length; continue }
    const curve = new THREE.CatmullRomCurve3(run.map((a) => a.p), false, 'centripetal')
    const seg = run.length * 6, ring = 9
    const geo = new THREE.TubeGeometry(curve, seg, radius, 8, false)
    const colors: number[] = [], us: number[] = []
    for (let i = 0; i <= seg; i++) {
      const k = i / seg, c = run[Math.min(run.length - 1, Math.round(k * (run.length - 1)))].color, u = (done + k * (run.length - 1)) / total
      for (let j = 0; j < ring; j++) { colors.push(c.r, c.g, c.b); us.push(u) }
    }
    geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3))
    geo.setAttribute('aU', new THREE.Float32BufferAttribute(us, 1))
    const mesh = new THREE.Mesh(geo, mat)
    meshes.push(mesh); core.add(mesh)
    done += run.length
  }
  return { core, glow: new THREE.Group(), meshes, uniforms }
}

/** MSA 보존도 색 (쿼리와 같은 아미노산 비율): 낮을수록 어둡고 높을수록 밝은 시안 */
export function conservationColor(c: number) {
  const lo = new THREE.Color(0x2a2f5e), mid = new THREE.Color(0x4d8dff), hi = new THREE.Color(0x37e6ff)
  return c < 0.6 ? lo.clone().lerp(mid, Math.max(0, c) / 0.6) : mid.clone().lerp(hi, (c - 0.6) / 0.4)
}

/** 사슬을 따라 세 색으로 물들입니다 (쇼릴의 표적별 팔레트) */
export function chainGradient(n: number, a: number, b: number, c: number) {
  const A = new THREE.Color(a), B = new THREE.Color(b), C = new THREE.Color(c)
  return Array.from({ length: n }, (_, i) => { const u = i / Math.max(1, n - 1); return u < 0.5 ? A.clone().lerp(B, u * 2) : B.clone().lerp(C, u * 2 - 1) })
}
// 표적(유전자)별 세 색. 같은 표적은 어느 화면에서나 같은 색입니다
export const TARGET_PALETTE: Record<string, [number, number, number]> = {
  PARP1: [0x2fd6c8, 0x5ea8ff, 0xb28cff], NR3C1: [0x7be495, 0x3ddc97, 0x2fd6c8], DRD2: [0xff9ad5, 0xff5d9e, 0xb28cff],
  JAK2: [0x5ea8ff, 0x4d6bff, 0x9b7bff], CRBN: [0xffd36e, 0xffb547, 0xff8b35], 'Mpro (nsp5)': [0xff8b8b, 0xff5d6c, 0xc94f9b],
  HTR2A: [0xc9a6ff, 0xa58bff, 0x6c7aff], SLC5A2: [0x6fe3ff, 0x37e6ff, 0x4d8dff], F10: [0xffb347, 0xff7a45, 0xff4f7b],
  OPRM1: [0xa0f0c8, 0x62d6a0, 0x2fb6a8], PDE5A: [0xffe08a, 0xf2b84b, 0xe08a3c], DHFR: [0x9fd3ff, 0x6ca8ff, 0x7b7bff],
}

function cylinder(a: THREE.Vector3, b: THREE.Vector3, r: number, mat: THREE.Material) {
  const d = b.clone().sub(a)
  const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, d.length(), 10), mat)
  m.position.copy(a).add(b).multiplyScalar(0.5)
  m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize())
  return m
}

/** 리간드 공-막대. ghost 는 결정 구조 정답(흰 윤곽), faint 는 나머지 포즈(탐색 흔적). */
export function ballStick(lig: Ligand, style: 'solid' | 'ghost' | 'faint' = 'solid', tint?: number) {
  const g = new THREE.Group()
  const pts = lig.atoms.map((a) => new THREE.Vector3(a[0], a[1], a[2]))
  const mats = new Map<string, THREE.Material>()
  const mat = (el0: string) => {
    const el = tint === undefined ? el0 : 'tint'
    if (!mats.has(el)) {
      // tint 가 있으면 원소와 관계없이 한 색으로 (여러 리간드를 구분할 때)
      const c = tint ?? ELEMENT[el] ?? 0xd8dce8
      mats.set(el, style === 'solid'
        ? new THREE.MeshStandardMaterial({ color: c, emissive: c, emissiveIntensity: 0.28, roughness: 0.25, metalness: 0.15, transparent: true, opacity: 1 })
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
    new THREE.PointsMaterial({ color: 0x4d8dff, size: 0.3, transparent: true, opacity: 0.16, depthWrite: false }))
}

export function makeRenderer(el: HTMLElement) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  // 블룸 후처리가 붙은 캔버스가 한 화면에 2~3개라 레티나(DPR 2)에서 픽셀 수가 4배가 되어 프레임이 끊깁니다. 1.5 로 묶습니다
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5))
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.05
  // setSize(..., false) 는 캔버스 CSS 크기를 건드리지 않으므로, 여기서 칸에 맞춥니다.
  // 이게 없으면 devicePixelRatio 2(맥 레티나 · 브라우저 확대) 화면에서 캔버스가 칸의 2배로 그려져
  // overflow:hidden 에 잘리고 왼쪽 위 1/4 만 보입니다(단백질이 오른쪽 아래로 치우쳐 잘림)
  renderer.domElement.style.cssText = 'display:block;width:100%;height:100%'
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
  const bloom = new UnrealBloomPass(new THREE.Vector2(512, 512), 0.3, 0.35, 0.8)
  composer.addPass(bloom)
  composer.addPass(new OutputPass())
  // 쇼릴처럼 아주 약한 필름 그레인과 비네팅
  const film = new ShaderPass({
    uniforms: { tDiffuse: { value: null }, uTime: { value: 0 }, uGrain: { value: 0.035 }, uVig: { value: 0.35 } },
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: `uniform sampler2D tDiffuse; uniform float uTime; uniform float uGrain; uniform float uVig; varying vec2 vUv;
      float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233)) + uTime) * 43758.5453); }
      void main(){ vec4 c = texture2D(tDiffuse, vUv); c.rgb += (h(vUv * 1000.0) - 0.5) * uGrain;
        float d = distance(vUv, vec2(0.5)); c.rgb *= 1.0 - uVig * smoothstep(0.35, 0.85, d); gl_FragColor = c; }`,
  })
  composer.addPass(film)
  const resize = () => {
    const w = el.clientWidth, h = Math.max(1, el.clientHeight)
    renderer.setSize(w, h, false); composer.setSize(w, h); bloom.resolution.set(w, h)
    camera.aspect = w / h; camera.updateProjectionMatrix()
  }
  // 화면 밖이거나 탭이 숨겨졌으면 그리지 않습니다(루프는 돌되 GPU 는 쉬게)
  let onScreen = true
  const io = new IntersectionObserver(([e]) => { onScreen = e.isIntersecting })
  io.observe(el)
  // 캔버스가 치워지면(컴포넌트 cleanup) 관찰도 끊습니다
  new MutationObserver((_, mo) => { if (!renderer.domElement.isConnected) { io.disconnect(); mo.disconnect() } }).observe(el, { childList: true })
  const shown = () => onScreen && !document.hidden
  return { renderer, scene, camera, composer, bloom, film, resize, shown }
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
