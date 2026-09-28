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
  target_label?: string
}
export interface Of3Result {
  target: string; ligand: string | null; msa_source?: string
  scores: { confidence: number | null; plddt: number | null; ptm: number | null; iptm: number | null; pde: number | null }
  ca_rmsd: number | null; n_ca: number; ligand_rmsd: number | null; n_residues: number
  plddt_per_residue: number[]; mean_plddt: number; ca: number[][]; xtal_ca: number[][]
  ligand_atoms: [string, number, number, number][]; ligand_bonds: number[][]
  xtal_ligand: { atoms: [string, number, number, number][]; bonds: number[][] } | null; seconds?: number
  target_label?: string; reference?: 'crystal' | 'none'; reference_note?: string | null; structure_key?: string
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
  target_label?: string; reference?: 'crystal' | 'none'; reference_note?: string | null; receptor_source?: string | null
}
export interface BoltzResult {
  target: string; ligand: string
  affinity: { pic50: number | null; pred_value: number | null; probability_binary: number | null }
  scores: { confidence: number | null; plddt: number | null; iptm: number | null; ptm: number | null; pde: number | null }
  n_residues: number; ca: number[][]; plddt_per_residue: number[]
  ligand_atoms: [string, number, number, number][]; ligand_bonds: number[][]
  metrics: Record<string, number>; chembl: { median_pchembl: number; n: number; source: string } | null; seconds?: number
  target_label?: string
}
export type StepResult = MsaResult | Of3Result | DockResult | BoltzResult

export interface Envelope<T = StepResult> {
  kind: StepKind; endpoint: string; skills: Skill[]; params: Record<string, unknown>
  request: Record<string, unknown>; measured: T | null
  state: 'done' | 'pending'; source?: 'live' | 'cache' | 'measured'; elapsed_s?: number
  target?: { label?: string; gene?: string; pdb?: string; chain?: string; organism?: string; desc?: string
    kind?: string; reference?: string; length?: number | null; custom?: boolean }
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
  kind?: string; reference?: string; pocket_ligand_code?: string | null; receptor_source?: string | null
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

// ---------------------------------------------------------------- 단백질·리간드 찾기
export interface ProteinHit {
  id: string; uniprot_id: string; name: string; gene: string; organism: string
  reviewed: boolean; length: number | null; n_pdb: number; pdb: string | null
}
export interface StructureRef {
  pdb: string; method: string; resolution: number | null; chain: string | null
  start: number | null; end: number | null; chains_raw: string
}
export interface RangeRef { kind: 'structure' | 'domain' | 'full'; label: string; start: number; end: number }
export interface ProteinRecord {
  id: string; uniprot_id: string; name: string; gene: string; organism: string; reviewed: boolean
  length: number; sequence: string; structures: StructureRef[]; best_structure: StructureRef | null
  domains: { label: string; start: number; end: number }[]; ranges: RangeRef[]; recommended_range: RangeRef
  check: { ok: boolean; length: number; openfold3_ok: boolean; reason: string }
}
export interface LigandHit { cid: number | null; name: string; smiles: string; mw: number | null; source: string }

export const searchProtein = (q: string) =>
  fresh<{ query: string; hits: ProteinHit[]; ms?: number }>(`/api/discovery/search/protein?q=${encodeURIComponent(q)}`)
export const getProtein = (id: string) => fresh<ProteinRecord>(`/api/discovery/protein/${encodeURIComponent(id)}`)
export const searchLigand = (q: string) =>
  fresh<{ query: string; hits: LigandHit[]; ms?: number; smiles_note?: string }>(`/api/discovery/search/ligand?q=${encodeURIComponent(q)}`)

export const getCatalog = (() => {
  let p: Promise<Catalog> | null = null
  return () => (p ??= fresh<Catalog>('/api/discovery/catalog'))
})()

const scenes = new Map<string, Promise<Scene>>()
export function getScene(target: string): Promise<Scene> {
  if (!scenes.has(target)) scenes.set(target, fresh<Scene>(`/api/discovery/scene/${target}`))
  return scenes.get(target)!
}

/** 고른 표적의 3D 배경입니다. 화면에서 찾은 단백질은 RCSB 실험 구조를 받아 그립니다. */
export function getSceneForSelection(): Promise<Scene> {
  const s = getStore()
  if (!s.customTarget) return getScene(s.target)
  const key = `custom:${s.customTarget.id}:${s.customTarget.pdb}:${s.customTarget.chain}`
  if (!scenes.has(key)) scenes.set(key, fresh<Scene>('/api/discovery/scene', { custom_target: customTargetPayload(s.customTarget) }))
  return scenes.get(key)!
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

/** 지난 측정만 받습니다(NIM 을 부르지 않음). 실행 전 · 실패했을 때 비교 열을 채웁니다. */
export function getMeasured<T = StepResult>(kind: StepKind, target: string, ligand?: string): Promise<{ measured: T | null }> {
  const q = new URLSearchParams({ target, ...(ligand ? { ligand } : {}) })
  return fresh(`/api/discovery/measured/${kind}?${q}`)
}

export const runCritic = (body: { claims?: Claim[]; runs: Record<string, unknown> }) =>
  fresh<CriticResult>('/api/discovery/critic', body)

// ---------------------------------------------------------------- 공용 저장소 (단계 사이 전달)
export interface CustomTarget {
  id: string; gene: string; name: string; organism: string; sequence: string; length: number
  pdb: string | null; chain: string | null; start: number | null; end: number | null
  label: string; resolution?: number | null; range_label?: string
  openfold3_ok?: boolean; note?: string
}
export interface CustomLigand { name: string; smiles: string; cid: number | null; mw: number | null }

export const customTargetPayload = (t: CustomTarget) => ({
  id: t.id, gene: t.gene, name: t.name, organism: t.organism, sequence: t.sequence, label: t.label,
  pdb: t.pdb, chain: t.chain, start: t.start, end: t.end,
})

/** 실행에 보낼 입력입니다. 화면에서 고른 표적·리간드가 있으면 그것을, 없으면 목록의 것을 씁니다. */
export function runParams(extra: Record<string, unknown> = {}): Record<string, unknown> {
  const s = getStore()
  const p: Record<string, unknown> = { ...extra }
  if (s.customTarget) p.custom_target = customTargetPayload(s.customTarget)
  else p.target = s.target
  if (s.customLigand) p.custom_ligand = s.customLigand
  else p.ligand = s.ligand
  return p
}

export interface Store {
  target: string
  ligand: string
  customTarget: CustomTarget | null
  customLigand: CustomLigand | null
  runs: { msa?: MsaResult; openfold3?: Of3Result; diffdock?: DockResult; boltz2?: BoltzResult }
  envs: Partial<Record<StepKind, Envelope>>
  reward: { value: number; label: string; source: string; at: number }
}
let store: Store = { target: 'parp1', ligand: 'niraparib', customTarget: null, customLigand: null,
  runs: {}, envs: {}, reward: { value: 0, label: '대기', source: '', at: 0 } }

/** 표적이나 리간드를 바꾸면 앞 단계 결과는 더 이상 맞지 않으므로 비웁니다. */
export function selectTarget(t: CustomTarget | null, presetKey?: string) {
  store = { ...store, customTarget: t, target: presetKey ?? store.target, runs: {}, envs: {},
    reward: { value: 0, label: '대기', source: '', at: 0 } }
  emit()
}
export function selectLigand(l: CustomLigand | null, presetKey?: string) {
  store = { ...store, customLigand: l, ligand: presetKey ?? store.ligand,
    runs: { ...store.runs, openfold3: undefined, diffdock: undefined, boltz2: undefined },
    envs: { ...store.envs, openfold3: undefined, diffdock: undefined, boltz2: undefined } }
  emit()
}
export const targetLabel = () => (store.customTarget ? store.customTarget.label : store.target.toUpperCase())
export const ligandLabel = () => (store.customLigand ? store.customLigand.name : store.ligand)
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
