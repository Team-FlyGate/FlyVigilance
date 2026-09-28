import type { Answer } from './data'

export interface Overview {
  asof: string; first: string; quarters: number; raw_reports: number; raw_drug_rows: number; raw_reac_rows: number
  versions: number; cases: number; deleted_cases: number; distinct_caseids: number; drug_names_raw: number
  drug_names_norm: number; drugname_map: number; pts: number; triplets: number; pairs: number; evans: number
  ror_sig: number; ic_sig: number; all3: number; serious_cases: number; death_cases: number
  per_quarter: { quarter: string; reports: number; cases: number; initial: number; followups: number; expedited: number; periodic: number; direct: number }[]
  etl: { quarter: string; seconds: number; demo: number; drug: number; reac: number }[]
  outcomes: Record<string, number>; reporters: Record<string, number>; countries: [string, number][]
  sex: Record<string, number>; age_bins: [number, number][]; top_drugs: [string, number][]; top_pts: [string, number][]
  top_signals: { drug: string; pt: string; a: number; prr: number; ror_lo: number; ic025: number }[]
  latest: { cases: number; serious: number; death: number; expedited: number }
}

export interface LatStats { n: number; p50: number; p90: number; p99: number; mean: number; min: number; max: number }

export interface BenchExample {
  primaryid: number; bucket: string; action: string; reasons: string[]; answers: Record<string, Answer>
  latency_ms: number; suspect: string; reactions: string[]
}

export interface Bench {
  generated: string
  ablation?: Ablation
  ablation_blind?: Ablation
  ablation_generated?: string
  dataset: { source: string; cases: number; buckets: Record<string, number>; serious_rate: number }
  jev_triage: {
    ok: number; errors: number; questions_per_call: number; latency_ms: LatStats; wall_s: number; concurrency: number
    throughput_cases_per_s: number; tokens_in_mean: number; tokens_out_mean: number; usd_per_case: number; usd_per_1k: number
    price: { in: number; out: number; source: string }; actions: Record<string, number>
    actions_by_bucket: Record<string, Record<string, number>>
    serious_rate_by_action: Record<string, { serious: number; n: number }>
    examples: BenchExample[]
  }
  blind_serious: {
    jev: { n: number; auroc: number; acc: number; ece: number; calibration: { bin: string; n: number; pred: number; obs: number }[]; latency_ms: LatStats; wall_s: number }
    majority_baseline_acc: number
  }
  nemotron?: {
    model: string; sample: number; errors: { blind: number; triage: number }; concurrency: number
    blind: { n: number; auroc: number; acc: number; latency_ms: LatStats; wall_s: number; jev_same_subset_auroc: number; jev_same_subset_acc: number }
    triage: { n: number; latency_ms: LatStats; wall_s: number; tokens_in_mean: number; tokens_out_mean: number; route_agreement: number; causality_agreement: number; compared: number }
  }
}

export interface ReporterMix { n: number; hcp: number; cn: number; lw: number }
export interface Backtest {
  quarters: string[]; criteria: string; reporter_note?: string
  items: {
    drug: string; pt: string; action: string | null; what: string; note?: string; first_signal_quarter: string | null
    first_signal_date: string | null; lead_days: number | null; left_censored: boolean
    series: { q: string; a: number; prr?: number; ror_lo?: number; ic025?: number; chi2?: number; signal?: boolean }[]
    reporters?: { all: ReporterMix | null; to_first_sdr: ReporterMix | null; pre_action: ReporterMix | null; peak_quarter: string | null; peak_share: number | null }
  }[]
}

export interface Schema {
  layers: Record<string, string>; db_bytes: number
  tables: { name: string; layer: string; rows: number; columns: { name: string; type: string }[] }[]
}

export interface RocMethod {
  key: string; label: string; family: 'metric' | 'raw' | 'flyvigilance' | 'knowledge'
  auc: number; ci: [number, number] | null; roc: [number, number][]
  'at_0.5'?: SensSpec
}
export interface SensSpec { sens: number | null; spec: number | null; ppv: number | null; tp: number; fp: number; tn: number; fn: number }
export interface RefsetResult {
  n: number; pos: number; neg: number; methods: RocMethod[]; points: { evans: SensSpec; triple: SensSpec }
  deltas: { a: string; b: string; delta: number; ci: [number, number]; best_metric?: boolean }[]
  excluded: { drug: string; event: string }[]; window?: string; N?: number; not_marketed_before_2013?: number
}
export interface RefPair {
  drug: string; drug_ref: string; event: string; truth: number; a: number; prr: number | null; ror_lo: number | null; ic025: number
  evans: boolean; triple: boolean; raw_named: number; raw_blind: number; fv: number; fv_alt: string | null
  dechal: [number, number]; indication: number
}
export interface Validation {
  generated: string; asof: string; N: number; jev: { calls: number; latency_ms_p50: number }
  refsets: Record<string, RefsetResult>; pairs: Record<string, RefPair[]>
  events: Record<string, { label: string; source: string; pts: string[]; note: string }>
  sources: { name: string; url: string }[]
}
export interface LiteratureEval {
  generated: string; n: number; accuracy: number; group_accuracy: number; pairs: number
  per_class: Record<string, { n: number; recall: number }>; confusion: Record<string, Record<string, number>>; labels: string[]
  calls: number; articles_per_call: number; latency_ms_p50: number; truth_source: string
}
export interface Escalation {
  sens: number; spec: number; missed_serious: number; over_escalated: number; escalated: number; n: number; serious_without_review: number
  routes?: Record<string, number>; routes_serious?: Record<string, number>
}
export interface McNemar { a_only: number; b_only: number; p: number }
export interface Ablation {
  n: number; definition: string; serious?: number; include_outcome?: boolean
  flyvigilance: Escalation; flyvigilance_ungrounded: Escalation; raw_jev: Escalation; flyvigilance_no_dme?: Escalation
  routes: Record<string, Record<string, number>>; raw_auroc: number; raw_latency_ms: LatStats
  tests?: Record<string, McNemar>
  dme?: { cases_with_dme: number; serious_among_dme: number; changed_by_dme: number; serious_changed_by_dme: number }
  grounding: {
    label_found: number; cases: number
    memory_vs_label: { both_expected: number; both_unexpected: number; memory_expected_label_not: number; memory_unexpected_label_listed: number }
    actions_changed: number; changed_to_expedite: number; changed_from_expedite: number; changed_serious_to_expedite: number
    label_latency_ms: LatStats
    examples: { primaryid: number; suspect: string; reactions: string[]; serious: boolean; memory_expected: number; label: Record<string, string[]>; before: string; after: string }[]
  }
}
export interface ReportingBias {
  lawyer_share: number; consumer_share: number; hcp_share: number; background: { lw: number; cn: number; hcp: number } | null
  flag_lawyer: boolean; flag_consumer: boolean
  no_lawyer: { a: number; prr: number | null; ic025: number | null; sdr: boolean }; hcp_only: { a: number; prr: number | null; ic025: number | null; sdr: boolean }
}
export interface EvidenceGrade {
  id: string; drug: string; pt: string; grade: 'A' | 'B' | 'C' | 'L' | 'D' | 'U'; grade_name: string
  pv_class: 'review_sdr' | 'potential_candidate' | 'undetermined' | 'identified_candidate' | 'known_no_sdr' | 'none'
  pv_class_name: string; pv_hint: string; review_priority: number
  axes: { regulatory: number; regulatory_name: string; label_status: string; label_status_name: string; signal: string; signal_name: string
    literature: { read: number; supportive: number; analytic_read: number; analytic_supportive: number; anecdotal_supportive: number; analytic_status: string } }
  flags: { severity_boxed: boolean; dme: boolean; reporting_bias: ReportingBias | null; contraindication: string | null; indication_term: boolean }
  label_sections: string[]; disclaimer: { section: string; quote: string } | null
  stats: { a: number; prr: number; prr_lo: number; prr_hi: number; ror_lo: number; ic025: number; chi2: number } | null
  basis: string[]; gaps: string[]; summary: string; caution: string
  literature?: { count: number | null; articles: LitArticle[]; summary: Record<string, unknown> }
}
export interface LitArticle { pmid: string; year: string | null; title: string; design: string; design_source: string; addresses?: string | null; supports: number | null; strength: number | null; dechallenge: string | number | null; id: string }

// ---------- Project-FlyGate: 에이전트 구성과 STEP 1 측정 ----------

/** /data/agent.json: OpenClaw 하네스, OpenShell 샌드박스, NemoClaw 구성입니다. 다른 스크립트가 만들므로 없을 수도 있습니다 */
export interface AgentEgressRule { host: string; port: number | string; methods: string[] | string; paths: string[] | string; binaries: string[] | string }
export interface AgentSmokeResult { check: string; expect: string; observed: string; pass: boolean }
export interface AgentInfo {
  generated: string
  stack: { layer: string; what: string; ours: string }[]
  workspace: { file: string; role: string; content: string }[]
  skills: { name: string; description: string; stage: string; path: string }[]
  policy: {
    yaml: string
    egress: AgentEgressRule[]
    filesystem: { read_only: string[]; read_write: string[] }
    process: { user: string; seccomp: string | boolean }
  }
  triggers: { name: string; session: string; directive: string; trigger: string }[]
  cli: { cmd: string; what: string }[]
  modules: { id: string; title: string; ours: string; where: string }[]
  smoke: { ran: boolean; when: string | null; gateway: string | null; sandbox: string | null; results: AgentSmokeResult[]; source: string }
  trifecta: { private_data: string; untrusted_input: string; external_comm: string; mediation: string }
}

/** fly_discovery/measurements/measurements.json 입니다. scripts/sync-discovery.mjs 가 /discovery/data/ 로 복사합니다 */
export interface DiscoveryMeasurements {
  openfold3_msa: { endpoint: string; target: string; msa_homologs: number; plddt: number; ptm: number; iptm: number; ca_rmsd_vs_4R6E: number; n_ca: number; ligand_rmsd: number; seconds: number }
  openfold2: { status: string; http: number; error: string; attempts: number }
  nemoguard_topic_control?: { status: string; http: number; error: string; attempts: number; alternative_ok?: string }
  /** [조합, Vina, DiffDock 신뢰도, Boltz-2 pIC50, Boltz-2 결합 확률, ChEMBL pChEMBL 중앙값 또는 null, ChEMBL 활성 건수] */
  diffdock_boltz2_chembl: [string, number, number, number, number, number | null, number][]
  parp1_affinity_benchmark: {
    n: number; spearman: number; pearson: number; mae: number; rmse: number; bias: number
    ef_top25: number; hit: number; k: number; sens: number; spec: number; pairs: [number, number][]
  }
  /** 모델별 크리틱 평가입니다. rows = [주장, 정답(PASS/REJECT), 모델 판정] */
  critic_eval: Record<string, { sec: number; caught: number; n_over: number; passed: number; n_valid: number; rows: [string, string, string][] }>
}
/** /discovery/data/dd_eval_all.json 의 값입니다. rmsd_xtal 은 공결정 리간드를 다시 넣은 재도킹 대조에만 있습니다 */
export interface DockEval { top_conf: number; pocket_dist: number; rmsd_xtal: number | null; vina: number }

/** /data/critic_probe.json: 실제 사례 메모에 틀린 주장을 넣어 크리틱이 잡는지 잰 결과입니다 */
export interface CriticProbe {
  generated: string; n_cases: number
  summary: Record<string, { expect: string; n: number; correct: number; by_source: Record<string, number> }>
  cases: {
    primaryid: number; suspect: string; reactions: string[]
    probes: { id: string; expect: string; text: string; evidence: string[]; flagged: boolean; correct: boolean; issues: { tier: number; rule: string; p: number | null; source: string }[] }[]
  }[]
}
