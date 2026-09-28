import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { useBrain } from '../lib/brain'
import { t } from '../lib/i18n'
import { LAYER_COLOR, getJSON } from '../lib/data'

interface Props {
  height?: number | string
  highlight?: string | null
  autoRotate?: boolean
  showRois?: boolean
  showSkeletons?: boolean
  bloom?: number
  view?: 'front' | 'oblique'
}

const ROI_TINT: Record<string, string> = {
  CA: '#ff4fd8', PED: '#ff4fd8', 'aL': '#ff4fd8', "a'L": '#ff4fd8', bL: '#ff4fd8', "b'L": '#ff4fd8', gL: '#ff4fd8',
  EB: '#76b900', FB: '#76b900', PB: '#76b900', NO: '#76b900',
  LH: '#ffb547', AL: '#4d8dff', GNG: '#f4f7ff',
}

function roiTint(name: string) {
  const base = name.replace(/\(.*\)/, '')
  return ROI_TINT[base] ?? '#5f7fc7'
}

const pointVS = /* glsl */ `
  attribute float activity;
  attribute vec3 color;
  uniform float uSize;
  uniform float uScale;
  uniform float uHighlight;
  attribute float layerId;
  varying vec3 vColor;
  varying float vAct;
  varying float vDim;
  void main() {
    vColor = color;
    vAct = activity;
    vDim = (uHighlight < 0.0 || abs(layerId - uHighlight) < 0.5) ? 1.0 : 0.12;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = uSize * (0.9 + 3.2 * activity) * (uScale / -mv.z);
    gl_Position = projectionMatrix * mv;
  }
`
const pointFS = /* glsl */ `
  uniform float uGlow;
  varying vec3 vColor;
  varying float vAct;
  varying float vDim;
  void main() {
    vec2 c = gl_PointCoord - 0.5;
    float d = length(c);
    if (d > 0.5) discard;
    float core = smoothstep(0.22, 0.0, d);
    float halo = exp(-d * d * 18.0) * uGlow;
    float base = 0.05 + 0.95 * vAct;
    vec3 col = mix(vColor, vec3(1.0), vAct * vAct * 0.45);
    float a = (core * 0.55 + halo * (0.12 + 0.6 * vAct)) * base * vDim;
    gl_FragColor = vec4(col * a, a);
  }
`
const roiVS = /* glsl */ `
  varying vec3 vN; varying vec3 vV;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }
`
const roiFS = /* glsl */ `
  uniform vec3 uColor; uniform float uGlow; uniform float uBase;
  varying vec3 vN; varying vec3 vV;
  void main() {
    float f = pow(1.0 - abs(dot(vN, vV)), 2.2);
    float a = uBase * f + uGlow * (0.25 + f);
    gl_FragColor = vec4(uColor * (f * 0.9 + uGlow * 1.4), a);
  }
`

export default function BrainView({ height = 520, highlight = null, autoRotate = true, showRois = true,
  showSkeletons = true, bloom = 0.9, view = 'oblique' }: Props) {
  const host = useRef<HTMLDivElement>(null)
  const hlRef = useRef<string | null>(highlight)
  const { conn, sim } = useBrain()
  const [ready, setReady] = useState(false)
  hlRef.current = highlight

  useEffect(() => {
    if (!conn || !sim || !host.current) return
    const el = host.current
    const W = () => el.clientWidth, H = () => el.clientHeight
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(W(), H())
    renderer.setClearColor(0x050912, 1)
    el.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(38, W() / H(), 1, 6000)
    const R = conn.radius
    if (view === 'front') camera.position.set(0, 0, R * 2.9)
    else camera.position.set(R * 1.05, R * 0.35, R * 2.7)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.autoRotate = autoRotate
    controls.autoRotateSpeed = 0.35
    controls.minDistance = R * 0.6
    controls.maxDistance = R * 4

    // EM 좌표: y 가 아래로 커지므로 뒤집어서 등쪽을 위로
    const root = new THREE.Group()
    root.scale.set(1, -1, -1)
    root.position.set(-conn.center[0], conn.center[1], conn.center[2])
    const pivot = new THREE.Group()
    pivot.add(root)
    scene.add(pivot)

    // 점구름
    const m = conn.owner.length
    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(conn.cloud, 3))
    const colors = new Float32Array(m * 3)
    const layerIds = new Float32Array(m)
    const layerCols = conn.meta.layers.map((l) => new THREE.Color(LAYER_COLOR[l.key] ?? '#8899bb'))
    for (let i = 0; i < m; i++) {
      const L = conn.layer[conn.owner[i]]
      const c = layerCols[L]
      colors[i * 3] = c.r; colors[i * 3 + 1] = c.g; colors[i * 3 + 2] = c.b
      layerIds[i] = L
    }
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    geo.setAttribute('layerId', new THREE.BufferAttribute(layerIds, 1))
    const act = new Float32Array(m)
    const actAttr = new THREE.BufferAttribute(act, 1)
    actAttr.setUsage(THREE.DynamicDrawUsage)
    geo.setAttribute('activity', actAttr)
    const pmat = new THREE.ShaderMaterial({
      vertexShader: pointVS, fragmentShader: pointFS, transparent: true, depthWrite: false,
      blending: THREE.AdditiveBlending, uniforms: { uSize: { value: 2.4 * Math.min(window.devicePixelRatio, 2) }, uScale: { value: conn.radius * 2.2 }, uHighlight: { value: -1 }, uGlow: { value: bloom } },
    })
    root.add(new THREE.Points(geo, pmat))

    // ROI 메시
    const roiMats: { mat: THREE.ShaderMaterial; name: string }[] = []
    if (showRois) {
      new GLTFLoader().load('/data/brain_rois.glb', (gltf) => {
        gltf.scene.traverse((o) => {
          const mesh = o as THREE.Mesh
          if (!mesh.isMesh) return
          const name = mesh.name || mesh.parent?.name || ''
          const mat = new THREE.ShaderMaterial({
            vertexShader: roiVS, fragmentShader: roiFS, transparent: true, depthWrite: false, side: THREE.DoubleSide,
            blending: THREE.AdditiveBlending,
            uniforms: { uColor: { value: new THREE.Color(roiTint(name)) }, uGlow: { value: 0 }, uBase: { value: 0.12 } },
          })
          mesh.material = mat
          roiMats.push({ mat, name })
        })
        root.add(gltf.scene)
      })
    }

    // 대표 뉴런 스켈레톤
    const skelMats: { mat: THREE.LineBasicMaterial; layer: number }[] = []
    if (showSkeletons) {
      getJSON<{ bodyId: number; type: string; layer: string; segments: number[] }[]>('/data/connectome/skeletons.json').then((sk) => {
        for (const s of sk) {
          const g = new THREE.BufferGeometry()
          g.setAttribute('position', new THREE.Float32BufferAttribute(s.segments, 3))
          const mat = new THREE.LineBasicMaterial({ color: LAYER_COLOR[s.layer] ?? '#fff', transparent: true, opacity: 0.25,
            blending: THREE.AdditiveBlending, depthWrite: false })
          root.add(new THREE.LineSegments(g, mat))
          skelMats.push({ mat, layer: conn.meta.layers.findIndex((l) => l.key === s.layer) })
        }
      })
    }

    const onResize = () => {
      renderer.setSize(W(), H())
      camera.aspect = W() / H(); camera.updateProjectionMatrix()
    }
    const ro = new ResizeObserver(onResize)
    ro.observe(el)

    const L = conn.meta.layers
    const roiLayer = (name: string) => {
      const b = name.replace(/\(.*\)/, '')
      if (['CA', 'PED', 'aL', "a'L", 'bL', "b'L", 'gL'].includes(b)) return L.findIndex((l) => l.key === 'memory')
      if (['EB', 'FB', 'PB', 'NO'].includes(b)) return L.findIndex((l) => l.key === 'deliberate')
      if (b === 'LH') return L.findIndex((l) => l.key === 'reflex')
      if (b === 'AL') return L.findIndex((l) => l.key === 'encode')
      if (b === 'GNG') return L.findIndex((l) => l.key === 'action')
      return -1
    }

    let raf = 0
    let alive = true
    const tick = () => {
      if (!alive) return
      const x = sim.x
      const owner = conn.owner
      for (let i = 0; i < m; i++) {
        const v = x[owner[i]]
        act[i] = v > 1 ? 1 : v
      }
      actAttr.needsUpdate = true
      const hl = hlRef.current ? L.findIndex((l) => l.key === hlRef.current) : -1
      pmat.uniforms.uHighlight.value = hl
      for (const r of roiMats) {
        const li = roiLayer(r.name)
        const lvl = li >= 0 ? Math.min(1, sim.layerMean[li] / sim.layerPeak[li]) : 0
        r.mat.uniforms.uGlow.value = li >= 0 ? lvl * 0.35 : 0
        r.mat.uniforms.uBase.value = hl >= 0 && li !== hl ? 0.03 : 0.07
      }
      for (const s of skelMats) {
        const lvl = s.layer >= 0 ? Math.min(1, sim.layerMean[s.layer] / sim.layerPeak[s.layer]) : 0
        s.mat.opacity = 0.18 + 0.8 * lvl
      }
      controls.update()
      renderer.render(scene, camera)
      raf = requestAnimationFrame(tick)
    }
    tick()
    setReady(true)

    return () => {
      alive = false
      cancelAnimationFrame(raf)
      ro.disconnect()
      controls.dispose()
      renderer.dispose()
      renderer.forceContextLoss()
      geo.dispose()
      el.removeChild(renderer.domElement)
    }
  }, [conn, sim, autoRotate, showRois, showSkeletons, bloom, view])

  return (
    <div ref={host} style={{ position: 'relative', width: '100%', height }}>
      {!ready && (
        <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }}>
          <div className="row dim mono" style={{ fontSize: 12 }}><span className="spin" /> {t('MaleCNS 커넥텀 로딩 중', 'Loading the MaleCNS connectome')} · 49,244 neurons · 1.05M connections</div>
        </div>
      )}
    </div>
  )
}
