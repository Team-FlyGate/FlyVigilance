// MaleCNS 부분그래프 로더와 실시간 발화율 시뮬레이터 (브라우저에서 직접 계산)
//
// x_i <- d*x_i + (1-d) * relu(tanh(g * sum_j w_ij x_j + I_i - theta - k*a_i))
// a_i <- a_i + r*(x_i - a_i)          (적응: 자극이 끝나면 활동이 가라앉는다)
// w_ij 는 post 뉴런 입력 합으로 정규화, 신경전달물질로 부호(ACh +, GABA/Glu -)

import { getBin, getJSON, type ConnectomeMeta } from './data'

export interface Connectome {
  meta: ConnectomeMeta
  n: number
  pos: Float32Array
  layer: Uint8Array
  channel: Uint8Array
  cloud: Float32Array
  owner: Uint32Array
  indptr: Uint32Array
  pre: Uint32Array
  w: Float32Array
  center: [number, number, number]
  radius: number
}

let loading: Promise<Connectome> | null = null

export function loadConnectome(): Promise<Connectome> {
  if (loading) return loading
  loading = (async () => {
    const base = '/data/connectome/'
    const [meta, nb, cb, eb] = await Promise.all([
      getJSON<ConnectomeMeta>(base + 'meta.json'), getBin(base + 'neurons.bin'), getBin(base + 'cloud.bin'), getBin(base + 'edges.bin'),
    ])
    const n = meta.neurons
    const pos = new Float32Array(nb, 0, n * 3)
    const layer = new Uint8Array(nb, n * 12, n)
    const channel = new Uint8Array(nb, n * 13, n)
    const m = cb.byteLength / 16
    const cloud = new Float32Array(cb, 0, m * 3)
    const owner = new Uint32Array(cb, m * 12, m)
    const indptr = new Uint32Array(eb, 0, n + 1)
    const E = indptr[n]
    const pre = new Uint32Array(eb, (n + 1) * 4, E)
    const w = new Float32Array(eb, (n + 1) * 4 + E * 4, E)
    const [lo, hi] = meta.bbox
    const center: [number, number, number] = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2]
    const radius = Math.max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) / 2
    return { meta, n, pos, layer, channel, cloud, owner, indptr, pre, w, center, radius }
  })()
  return loading
}

export interface Stimulus { kind: 'channel' | 'layer'; index: number; amp: number; until: number }

export class Sim {
  c: Connectome
  x: Float32Array
  a: Float32Array
  inp: Float32Array
  g = 8; d = 0.6; theta = 0.05; k = 3; r = 0.1
  t = 0
  stimuli: Stimulus[] = []
  layerMean: Float32Array
  layerPeak: Float32Array
  layerCount: Uint32Array
  spikes = 0

  constructor(c: Connectome) {
    this.c = c
    this.x = new Float32Array(c.n)
    this.a = new Float32Array(c.n)
    this.inp = new Float32Array(c.n)
    const L = c.meta.layers.length
    this.layerMean = new Float32Array(L)
    this.layerPeak = new Float32Array(L).fill(0.05)
    this.layerCount = new Uint32Array(L)
    for (let i = 0; i < c.n; i++) this.layerCount[c.layer[i]]++
  }

  stimulate(kind: 'channel' | 'layer', key: string, amp = 1, steps = 10) {
    const list = kind === 'channel' ? this.c.meta.channels : this.c.meta.layers
    const index = list.findIndex((l) => l.key === key)
    if (index >= 0) this.stimuli.push({ kind, index, amp, until: this.t + steps })
  }

  step() {
    const { n, indptr, pre, w, layer, channel } = this.c
    const { x, a, inp } = this
    inp.fill(0)
    this.stimuli = this.stimuli.filter((s) => s.until > this.t)
    for (const s of this.stimuli) {
      const arr = s.kind === 'channel' ? channel : layer
      // 층 자극은 일부 뉴런만(희소 코딩) 켠다
      const frac = s.kind === 'layer' ? 0.35 : 1
      for (let i = 0; i < n; i++) if (arr[i] === s.index && ((i * 2654435761) >>> 0) % 100 < frac * 100) inp[i] += s.amp
    }
    const nx = new Float32Array(n)
    const L = this.layerMean.length
    const sum = new Float32Array(L)
    let spikes = 0
    for (let i = 0; i < n; i++) {
      let h = 0
      for (let e = indptr[i], end = indptr[i + 1]; e < end; e++) h += w[e] * x[pre[e]]
      let v = Math.tanh(this.g * h + inp[i] - this.theta - this.k * a[i])
      if (v < 0) v = 0
      const xi = this.d * x[i] + (1 - this.d) * v
      nx[i] = xi
      a[i] += this.r * (xi - a[i])
      sum[layer[i]] += xi
      if (xi > 0.5) spikes++
    }
    this.x = nx
    this.spikes = spikes
    for (let l = 0; l < L; l++) {
      const m = sum[l] / Math.max(1, this.layerCount[l])
      this.layerMean[l] = m
      this.layerPeak[l] = Math.max(this.layerPeak[l] * 0.995, m, 0.02)
    }
    this.t++
  }
}
