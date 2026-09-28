// STEP 1 FlyDiscovery: 라이브 NIM 호출과 단계 사이에 결과를 넘기는 작은 공용 저장소입니다.
// 모든 실행은 /api/discovery/* 를 거쳐 NVIDIA BioNeMo NIM 을 실제로 부릅니다.
import { useSyncExternalStore } from 'react'

export type StepKind = 'msa' | 'openfold3' | 'diffdock' | 'boltz2'
export interface Skill { name: string; repo: string; url: string; step: string }

export interface MsaResult {
  database: string; homologs: number; sequences: number; query_len: number; query: string; query_name: string
  depth: number[]; conservation: number[]; mean_depth: number; coverage: number
  rows: { name: string; seq: string; identity: number }[]
  databases_returned: string[]; a3m_chars: number; a3m_key?: string; a3m?: string | null; seconds?: number
}
export interface Of3Result {
  target: string; ligand: string | null; msa_source?: string
  scores: { confidence: number | null; plddt: number | null; ptm: number | null; iptm: number | null; pde: number | null }
  ca_rmsd: number | null; n_ca: number; ligand_rmsd: number | null; n_residues: number
  plddt_per_residue: number[]; mean_plddt: number; ca: number[][]; xtal_ca: number[][]
  ligand_atoms: [string, number, number, number][]; ligand_bonds: number[][]
  xtal_ligand: { atoms: [string, number, number, number][]; bonds: number[][] } | null; seconds?: number
}
export interface Pose {
  rank: number; confidence: number | null; rmsd: number | null; pocket_dist: number | null
  atoms: [string, number, number, number][]; bonds: number[][]; centroid: number[]
}
export interface DockResult {
  target: string; ligand: string; redock: boolean; n_poses: number; poses: Pose[]
  top1_confidence: number | null; top1_rmsd: number | null; best_rmsd: number | null; top1_success: boolean
  criterion: string; status?: string; xtal_ligand: { atoms: [string, number, number, number][]; bonds: number[][] } | null
  seconds?: number | null
}
export interface BoltzResult {
  target: string; ligand: string
  affinity: { pic50: number | null; pred_value: number | null; probability_binary: number | null }
  scores: { confidence: number | null; plddt: number | null; iptm: number | null; ptm: number | null; pde: number | null }
  n_residues: number; ca: number[][]; plddt_per_residue: number[]
  ligand_atoms: [string, number, number, number][]; ligand_bonds: number[][]
  metrics: Record<string, number>; chembl: { median_pchembl: number; n: number; source: string } | null; seconds?: number
}
export type StepResult = MsaResult | Of3Result | DockResult | BoltzResult

export interface Envelope<T = StepResult> {
  kind: StepKind; endpoint: string; skills: Skill[]; params: Record<string, unknown>
  request: Record<string, unknown>; measured: T | null
  state: 'done' | 'pending'; source?: 'live' | 'cache' | 'measured'; elapsed_s?: number
  result?: T; error?: string; note?: string; req_id?: string; poll_url?: string; waited_s?: number | null
}

export interface Catalog {
  targets: Record<string, { label: string; gene: string; pdb: string; chain: string; organism: string; desc: string; kind: string; xtal_drug: string | null; sequence_len: number | null }>
  ligands: Record<string, { smiles: string; ko: string }>
  pairs: Record<string, { target: string; ligand: string; role: string; redock: boolean; vina: number | null; chembl_median: number | null; chembl_n: number | null }>
  benchmark: {
    n: number; spearman: number; pearson: number; mae: number; rmse: number; bias: number; ef_top25: number
    hit: number; k: number; sens: number; spec: number
    points: { id: string; smiles: string | null; exp: number; pred: number; p: number; n: number | null }[]
  }
  measured: {
    msa: { homologs: number; seconds: number; database: string }
    openfold3: Record<string, number | string>
    openfold2_failed: { status: string; http: number; error: string; attempts: number }
    critic: { model: string; sec: number; caught: number; n_over: number; passed: number; n_valid: number; rows: [string, string, string][] }
    critic_lightning: { sec: number; caught: number; n_over: number; passed: number; n_valid: number }
  }
  skills: Record<string, Skill[]>
  endpoints: Record<string, string>
  source: string
}

export interface Scene {
  target: string; label: string; pdb: string; chain: string; organism: string; desc: string
  xtal_drug: string | null; xtal_ligand: { atoms: [string, number, number, number][]; bonds: number[][] }
  ca: number[][]; pocket: [string, number, number, number][]; pocket_center: number[] | null; sequence_len: number | null
}

export interface Claim {
  id: string; text: string; evidence: string[]; kind?: 'valid' | 'overclaim'; expect?: string
  verdict?: string; rule?: string | null; why?: string | null
}
export interface CriticResult {
  verdict: 'pass' | 'returned'; claims: Claim[]
  issues: { claim: string; tier: number; rule: string; detail: string; detail_ko?: string }[]
  tiers: { tier1: unknown[]; tier2: unknown[]; tier3: unknown[] }
  judge: { model?: string; latency_ms?: number; error?: string }
  bundle: { catalog: { id: string; what: string }[]; ids: string[] }
  score: { caught: number; n_over: number; passed: number; n_valid: number }
  rules: { id: string; text: string; ko: string }[]
  measured: Catalog['measured']['critic']; measured_lightning: Catalog['measured']['critic_lightning']
  skills: Skill[]; endpoint: string; total_ms: number
}

// ---------------------------------------------------------------- API
async function fresh<T>(url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, body === undefined ? { cache: 'no-store' } : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!r.ok) {
    let msg = `HTTP ${r.status}`
    try { msg = (await r.json()).detail ?? msg } catch { /* 본문이 JSON 이 아닐 수 있습니다 */ }
    throw new Error(msg)
  }
  return r.json() as Promise<T>
}

export const getCatalog = (() => {
  let p: Promise<Catalog> | null = null
  return () => (p ??= fresh<Catalog>('/api/discovery/catalog'))
})()

const scenes = new Map<string, Promise<Scene>>()
export function getScene(target: string): Promise<Scene> {
  if (!scenes.has(target)) scenes.set(target, fresh<Scene>(`/api/discovery/scene/${target}`))
  return scenes.get(target)!
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/** NIM 을 부르고, 계산 중(202)이면 요청 ID 로 끝날 때까지 이어서 묻습니다. */
export async function runStep<T = StepResult>(kind: StepKind, params: Record<string, unknown>,
  onTick?: (e: Envelope<T>) => void, maxWaitS = 300): Promise<Envelope<T>> {
  let env = await fresh<Envelope<T>>(`/api/discovery/${kind}`, params)
  const t0 = Date.now()
  while (env.state === 'pending' && env.req_id && (Date.now() - t0) / 1000 < maxWaitS) {
    onTick?.(env)
    await sleep(2500)
    const q = new URLSearchParams({ kind, ...(params.target ? { target: String(params.target) } : {}), ...(params.ligand ? { ligand: String(params.ligand) } : {}) })
    env = await fresh<Envelope<T>>(`/api/discovery/status/${env.req_id}?${q}`)
  }
  return env
}

export const runCritic = (body: { claims?: Claim[]; runs: Record<string, unknown> }) =>
  fresh<CriticResult>('/api/discovery/critic', body)

// ---------------------------------------------------------------- 공용 저장소 (단계 사이 전달)
export interface Store {
  target: string
  ligand: string
  runs: { msa?: MsaResult; openfold3?: Of3Result; diffdock?: DockResult; boltz2?: BoltzResult }
  envs: Partial<Record<StepKind, Envelope>>
  reward: { value: number; label: string; source: string; at: number }
}
let store: Store = { target: 'parp1', ligand: 'niraparib', runs: {}, envs: {}, reward: { value: 0, label: '대기', source: '', at: 0 } }
const subs = new Set<() => void>()
const emit = () => subs.forEach((f) => f())

export function setStore(patch: Partial<Store>) {
  store = { ...store, ...patch }
  emit()
}
export function saveRun(kind: StepKind, env: Envelope) {
  store = { ...store, envs: { ...store.envs, [kind]: env },
    runs: { ...store.runs, [kind]: (env.result ?? store.runs[kind]) as never } }
  emit()
}
export function setReward(value: number, label: string, source: string) {
  store = { ...store, reward: { value: Math.max(0, Math.min(1, value)), label, source, at: Date.now() } }
  emit()
}
export const getStore = () => store
export function useDiscovery(): Store {
  return useSyncExternalStore((f) => { subs.add(f); return () => subs.delete(f) }, getStore, getStore)
}

// ---------------------------------------------------------------- 보상 회로 매핑
// 결합력 측정값을 초파리 보상 회로(버섯체 KC · MBON 과 도파민성 PAM/DAN, 커넥텀 'memory' 층) 자극으로 옮깁니다.
// 생물학적 효능 주장이 아니라, 측정값을 눈으로 비교하기 위한 시각화입니다.
export const rewardFromConfidence = (conf: number | null | undefined) =>
  conf === null || conf === undefined ? 0 : Math.max(0, Math.min(1, (conf + 1.5) / 3))
export const rewardFromRmsd = (rmsd: number | null | undefined) =>
  rmsd === null || rmsd === undefined ? 0 : Math.max(0, Math.min(1, 1 - rmsd / 4))
export const rewardFromPic50 = (p: number | null | undefined) =>
  p === null || p === undefined ? 0 : Math.max(0, Math.min(1, (p - 4) / 7))
export const rewardFromPlddt = (p: number | null | undefined) =>
  p === null || p === undefined ? 0 : Math.max(0, Math.min(1, (p > 1 ? p / 100 : p)))
export const rewardFromDepth = (n: number | null | undefined) =>
  n === null || n === undefined ? 0 : Math.max(0, Math.min(1, Math.log10(1 + n) / 3))

/** pLDDT 색: 90 이상 매우 높음 → 50 미만 낮음 (AlphaFold/OpenFold 관례와 같은 구간입니다). */
export function plddtColor(v: number): string {
  const x = v > 1 ? v / 100 : v
  if (x >= 0.9) return '#37e6ff'
  if (x >= 0.7) return '#76b900'
  if (x >= 0.5) return '#ffcc4d'
  return '#ff5d6c'
}

export const REWARD_NOTE =
  '커넥텀 반응은 결합력 측정값을 초파리 보상 회로 자극으로 옮긴 시각화이며 생물학적 효능 주장이 아닙니다.'

export const fmtS = (s: number | null | undefined) =>
  s === null || s === undefined ? '–' : s >= 60 ? `${Math.floor(s / 60)}분 ${Math.round(s % 60)}초` : `${s.toFixed(1)}초`

export const SOURCE_LABEL: Record<string, { text: string; cls: string }> = {
  live: { text: '라이브 호출', cls: 'ok' },
  cache: { text: '라이브 결과 캐시', cls: 'ok' },
  measured: { text: '지난 측정으로 대체', cls: 'warn' },
}
