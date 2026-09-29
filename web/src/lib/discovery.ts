// STEP 1 FlyDiscovery: 라이브 NIM 호출과 단계 사이에 결과를 넘기는 작은 공용 저장소입니다.
// 모든 실행은 /api/discovery/* 를 거쳐 NVIDIA BioNeMo NIM 을 실제로 부릅니다.
import { useEffect, useState, useSyncExternalStore } from 'react'
import { isEn, t } from './i18n'

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
  receptor_predicted?: boolean
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

/** 한 단계를 부를 때 보낼 입력. 앞 단계에서 이어받을 것(MSA 정렬 · OpenFold3 예측 구조)을 여기서 붙입니다.
 *  라이브 실행 카드와 '다섯 단계 이어 실행' 이 같은 규칙을 쓰도록 한 곳에 둡니다. */
export function paramsFor(kind: StepKind, opts: { fresh?: boolean; predictedReceptor?: boolean } = {}): Record<string, unknown> {
  const s = getStore()
  const custom = !!(s.customTarget || s.customLigand)
  const target = s.target || 'parp1'
  const p: Record<string, unknown> = custom ? runParams() : kind === 'msa' ? { target } : { target, ligand: s.ligand || 'niraparib' }
  if (opts.fresh) p.no_cache = true
  if (kind === 'openfold3' || kind === 'boltz2') {
    // 이번 세션 MSA 는 같은 표적일 때만 넘기고, 지난 측정 정렬은 PARP1 것이라 PARP1 일 때만 씁니다
    const msaSame = Boolean(s.runs.msa) && (custom || (s.envs.msa?.params?.target ?? 'parp1') === target)
    if (msaSame && s.runs.msa?.a3m) p.a3m = s.runs.msa.a3m
    else if (msaSame && s.runs.msa?.a3m_key) p.a3m_key = s.runs.msa.a3m_key
    else if (kind === 'openfold3' && !custom && target === 'parp1') p.a3m_measured = true
  }
  if (kind === 'diffdock' && opts.predictedReceptor) {
    const key = predictedStructureKey()
    if (key) p.receptor_structure_key = key
  }
  return p
}

/** 이번 세션 OpenFold3 예측 구조(같은 표적일 때만). DiffDock 수용체로 쓸 수 있습니다. */
export function predictedStructureKey(): string | undefined {
  const s = getStore()
  const same = s.customTarget || s.customLigand || (s.envs.openfold3?.params?.target ?? 'parp1') === (s.target || 'parp1')
  return same ? s.runs.openfold3?.structure_key : undefined
}

/** 고른 리간드의 화면 이름(목록 리간드는 카탈로그의 한국어 이름). 여러 화면이 같은 이름을 쓰도록 둡니다. */
export function useLigandLabel(): string {
  const [ko, setKo] = useState<Record<string, string>>({})
  useEffect(() => { getCatalog().then((c) => setKo(Object.fromEntries(Object.entries(c.ligands).map(([k, v]) => [k, v.ko])))).catch(() => {}) }, [])
  const s = useDiscovery()
  return s.customLigand ? s.customLigand.name : ligandName(s.ligand, ko[s.ligand])
}

export const PIPELINE: StepKind[] = ['msa', 'openfold3', 'diffdock', 'boltz2']

/** 다섯 단계를 차례로 부르고, 각 결과를 다음 단계 입력으로 넘깁니다.
 *  한 단계가 실패하면 사유를 남기고 다음 단계로 넘어갑니다(앞 단계 없이 되는 단계가 있습니다). */
export async function runPipeline(opts: {
  fresh?: boolean
  onStep?: (kind: StepKind | 'critic', state: 'run' | 'done' | 'fail', detail?: string) => void
} = {}): Promise<{ failed: { kind: string; error: string }[] }> {
  const failed: { kind: string; error: string }[] = []
  for (const kind of PIPELINE) {
    opts.onStep?.(kind, 'run')
    try {
      const env = await runStep(kind, paramsFor(kind, { fresh: opts.fresh, predictedReceptor: true }))
      saveRun(kind, env as Envelope)
      if (env.state !== 'done' || env.error) {
        const why = env.error ?? '계산이 끝나지 않았습니다'
        failed.push({ kind, error: why }); opts.onStep?.(kind, 'fail', why)
      } else opts.onStep?.(kind, 'done')
    } catch (e) {
      const why = e instanceof Error ? e.message : String(e)
      failed.push({ kind, error: why }); opts.onStep?.(kind, 'fail', why)
    }
  }
  opts.onStep?.('critic', 'run')
  try {
    const r = await runCritic({ runs: getStore().runs as Record<string, unknown> })
    opts.onStep?.('critic', 'done', `${r.score.caught}/${r.score.n_over}`)
    return { failed }
  } catch (e) {
    const why = e instanceof Error ? e.message : String(e)
    failed.push({ kind: 'critic', error: why }); opts.onStep?.('critic', 'fail', why)
    return { failed }
  }
}

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
/** 단계 페이지 id → NIM 종류. 크리틱은 NIM 이 아니라 없습니다. */
export const STEP_KIND: Record<string, StepKind | undefined> = { msa: 'msa', of3: 'openfold3', dd: 'diffdock', bz: 'boltz2', critic: undefined }
export const getStore = () => store
/** 이 단계의 이번 세션 실행이 지금 고른 표적 · 리간드와 같은 입력일 때만 그 봉투를 돌려줍니다(라이브 실행 카드와 위 3D 장면이 같이 씁니다).
 *  fallbackLigand 는 리간드를 아직 고르지 않았을 때 부를 기본값입니다. */
export function liveFor(kind: StepKind, s: Store, fallbackLigand = 'niraparib'): Envelope | undefined {
  const env = s.envs[kind]
  if (!env) return undefined
  const custom = !!(s.customTarget || s.customLigand)
  const target = s.target || 'parp1'
  const lig = kind === 'msa' ? undefined : s.ligand || fallbackLigand
  const same = custom ? !!(env.params?.custom_target || env.params?.custom_ligand)
    : (env.params?.target ?? 'parp1') === target && (kind === 'msa' || env.params?.ligand === lig)
  return same ? env : undefined
}
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

// 언어에 따라 바뀌므로 렌더할 때 부르는 함수로 둡니다.
export const rewardNote = () => t(
  '커넥텀 반응은 결합력 측정값을 초파리 보상 회로 자극으로 옮긴 시각화이며 생물학적 효능 주장이 아닙니다.',
  'The connectome response is a visualization that maps measured binding strength onto stimulation of the fruit-fly reward circuit; it is not a claim of biological efficacy.')

export const fmtS = (s: number | null | undefined) =>
  s === null || s === undefined ? '–' : s >= 60 ? t(`${Math.floor(s / 60)}분 ${Math.round(s % 60)}초`, `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`) : t(`${s.toFixed(1)}초`, `${s.toFixed(1)} s`)

// text 는 읽을 때마다 지금 언어로 계산되도록 getter 로 둡니다.
export const SOURCE_LABEL: Record<string, { text: string; cls: string }> = {
  live: { get text() { return t('라이브 호출', 'Live call') }, cls: 'ok' },
  cache: { get text() { return t('라이브 결과 캐시', 'Cached live result') }, cls: 'ok' },
  measured: { get text() { return t('지난 측정으로 대체', 'Fell back to a previous measurement') }, cls: 'warn' },
}

// ---------------------------------------------------------------- 데이터 문구 영어 대응표
// fly_discovery/measurements/*.json 에 한국어로 적힌 짧은 문구(재도킹 메모, 크리틱 평가 주장)를 영어 화면에서 바꿔 보여 줍니다.
// 데이터 파일은 고치지 않고, 표에 없는 문구는 원문 그대로 둡니다.
const DATA_EN: Record<string, string> = {
  '케이스 스터디 데모 약물': 'Case-study demo drug',
  '공유결합 억제제. DiffDock 은 비공유 결합만 모사하므로 참고용이다': 'Covalent inhibitor. DiffDock models only non-covalent binding, so this result is for reference only',
  '니라파립과 같은 PARP 억제제': 'A PARP inhibitor, like niraparib',
  'cryo-EM 구조': 'Cryo-EM structure',
  '케이스 스터디의 대조 약물과 같은 구조': 'Same structure as the case study’s comparator drug',
  '보조인자 NADPH 는 수용체에 넣지 않았다 (ATOM 만 사용)': 'The NADPH cofactor was not included in the receptor (ATOM records only)',
  'PARP1 Vina 순위는 15R > pamiparib > niraparib > rucaparib이다.': 'The PARP1 Vina ranking is 15R > pamiparib > niraparib > rucaparib.',
  'DiffDock이 니라파립을 4R6E 공결정 위치에 RMSD 0.71A로 재현했다.': 'DiffDock reproduced niraparib’s 4R6E co-crystal position with an RMSD of 0.71 Å.',
  'ChEMBL 실측 중앙값은 pamiparib 8.89 > rucaparib 8.70 > niraparib 7.79이다.': 'The ChEMBL measured medians are pamiparib 8.89 > rucaparib 8.70 > niraparib 7.79.',
  'Boltz-2는 니라파립@PARP1 pIC50 8.909를 예측했고 ChEMBL 실측 중앙값은 7.79이다.': 'Boltz-2 predicted pIC50 8.909 for niraparib@PARP1, and the ChEMBL measured median is 7.79.',
  '니라파립은 PARP1 -10.178, Xa -7.967이므로 PARP1에 선택적이다.': 'Niraparib scores PARP1 −10.178 and Xa −7.967, so it is selective for PARP1.',
  'DiffDock 신뢰도 1.10인 pamiparib이 rucaparib보다 친화도가 높다.': 'Pamiparib, with a DiffDock confidence of 1.10, has higher affinity than rucaparib.',
  'Boltz-2 예측 pIC50 8.909는 니라파립의 측정된 PARP1 친화도이다.': 'The Boltz-2 predicted pIC50 of 8.909 is niraparib’s measured PARP1 affinity.',
  'PARP1 3종의 Boltz-2와 실측 Spearman이 -1.0이므로 Boltz-2는 실측과 역상관한다.': 'Because the Spearman correlation between Boltz-2 and measurements across three PARP1 inhibitors is −1.0, Boltz-2 is inversely correlated with measurement.',
}
/** 데이터에 담긴 한국어 문구를 지금 언어에 맞춰 돌려줍니다. 표에 없으면 원문을 그대로 돌려줍니다. */
export const dataText = (s: string | null | undefined): string => (s ? t(s, DATA_EN[s.trim()] ?? s) : s ?? '')

// 라이브 크리틱 서버(api/_fv/discovery.py)가 실행 결과로 만드는 한국어 주장 문장을 영어 화면에서 바꿔 보여 줍니다.
// 숫자와 이름은 문장에서 그대로 떼어 옮기고, 틀에 맞지 않는 문장(직접 넣은 주장 등)은 원문을 그대로 둡니다.
const CLAIM_EN: [RegExp, (...m: string[]) => string][] = [
  [/^MSA-Search 가 (.+) 에서 상동 서열 (\S+)개를 찾아 OpenFold3 입력으로 썼습니다\.$/, (db, n) => `MSA-Search found ${n} homologous sequences in ${db} and passed them to OpenFold3 as input.`],
  [/^OpenFold3 예측 구조는 결정 구조 대비 CA RMSD (\S+) Å 로 맞았고 pLDDT 는 (\S+) 입니다\.$/, (r, p) => `The OpenFold3 predicted structure matched the crystal structure with a Cα RMSD of ${r} Å, and its pLDDT is ${p}.`],
  [/^pLDDT (\S+) 이므로 이 리간드는 강하게 결합합니다\.$/, (p) => `Because pLDDT is ${p}, this ligand binds strongly.`],
  [/^DiffDock 이 공결정 리간드를 RMSD (\S+) Å 로 재현해 도킹 설정이 작동함을 확인했습니다\.$/, (r) => `DiffDock reproduced the co-crystal ligand with an RMSD of ${r} Å, confirming that the docking setup works.`],
  [/^DiffDock 신뢰도 (\S+) 이므로 이 화합물의 친화도가 더 높습니다\.$/, (c) => `Because the DiffDock confidence is ${c}, this compound has higher affinity.`],
  [/^Boltz-2 는 pIC50 (\S+) 를 예측했고 ChEMBL 실측 중앙값은 (\S+) 입니다\.$/, (p, m) => `Boltz-2 predicted a pIC50 of ${p}, and the ChEMBL measured median is ${m}.`],
  [/^Boltz-2 예측 pIC50 (\S+) 는 이 화합물의 측정된 친화도입니다\.$/, (p) => `The Boltz-2 predicted pIC50 of ${p} is this compound's measured affinity.`],
  [/^니라파립은 PARP1 (\S+), Factor Xa (\S+) 이므로 PARP1 에 선택적입니다\.$/, (a, b) => `Niraparib scores PARP1 ${a} and Factor Xa ${b}, so it is selective for PARP1.`],
  [/^아직 실행 결과가 없습니다\.$/, () => 'No run results yet.'],
]
/** 크리틱 주장 문장을 지금 언어로 돌려줍니다. */
export function claimText(s: string): string {
  if (!isEn()) return s
  const x = s.trim()
  for (const [re, f] of CLAIM_EN) { const m = x.match(re); if (m) return f(...m.slice(1)) }
  return DATA_EN[x] ?? s
}

// 카탈로그(api/_data/discovery.json.gz)의 한국어 표적 설명 · 리간드 이름을 영어 화면에서 바꿉니다.
const TARGET_DESC_EN: Record<string, string> = {
  parp1: 'PARP1 catalytic domain · 4R6E chain A',
  xa: 'Coagulation factor Xa · 2P16',
  cox2: 'COX-2 · 3LN1 (mouse protein)',
}
export const targetDesc = (key: string, desc: string | undefined): string => t(desc ?? '', TARGET_DESC_EN[key] ?? desc ?? '')
/** 리간드 표시 이름: 한국어 화면은 카탈로그의 한국어 이름, 영어 화면은 키에서 만든 영문 이름입니다. */
export function ligandName(key: string, ko?: string | null): string {
  if (!isEn()) return ko ?? key
  if (key === '15r') return '15R (PARP1 co-crystal ligand)'
  return key.charAt(0).toUpperCase() + key.slice(1)
}
// 단백질 검색 서버(api/_fv/bio_search.py)가 돌려주는 구간 이름 · 점검 사유 문장을 옮깁니다.
const BIO_EN: [RegExp, (...m: string[]) => string][] = [
  [/^전체 서열$/, () => 'Full sequence'],
  [/^(\S+) 체인 (\S+) 구간$/, (pdb, ch) => `${pdb} chain ${ch} region`],
  [/^서열이 비어 있습니다\.$/, () => 'The sequence is empty.'],
  [/^아미노산이 아닌 문자가 있습니다\.$/, () => 'The sequence contains characters that are not amino acids.'],
  [/^(\d+)잔기입니다\. MSA-Search 와 Boltz-2 의 상한이 (\d+)잔기이므로 도메인 구간을 골라 주세요\.$/, (n, mx) => `${n} residues. MSA-Search and Boltz-2 accept up to ${mx} residues, so please pick a domain region.`],
  [/^(\d+)잔기입니다\. OpenFold3 는 약 (\d+)잔기를 넘으면 80 GB GPU 가 필요해 호스팅 경로에서 실패할 수 있습니다\.?$/, (n, mx) => `${n} residues. Beyond about ${mx} residues OpenFold3 needs an 80 GB GPU and may fail on the hosted endpoint.`],
]
export function bioText(s: string | null | undefined): string {
  if (!s) return ''
  if (!isEn()) return s
  for (const [re, f] of BIO_EN) { const m = s.trim().match(re); if (m) return f(...m.slice(1)) }
  return s
}
