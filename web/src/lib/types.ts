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

export interface Backtest {
  quarters: string[]; criteria: string
  items: {
    drug: string; pt: string; action: string | null; what: string; note?: string; first_signal_quarter: string | null
    first_signal_date: string | null; lead_days: number | null; left_censored: boolean
    series: { q: string; a: number; prr?: number; ror_lo?: number; ic025?: number; chi2?: number; signal?: boolean }[]
  }[]
}

export interface Schema {
  layers: Record<string, string>; db_bytes: number
  tables: { name: string; layer: string; rows: number; columns: { name: string; type: string }[] }[]
}

export interface RocMethod {
  key: string; label: string; family: 'metric' | 'raw' | 'flyvigilance' | 'memory'
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
export interface Escalation { sens: number; spec: number; missed_serious: number; over_escalated: number; escalated: number; n: number; serious_without_review: number }
export interface Ablation {
  n: number; definition: string
  flyvigilance: Escalation; flyvigilance_ungrounded: Escalation; raw_jev: Escalation
  routes: Record<string, Record<string, number>>; raw_auroc: number; raw_latency_ms: LatStats
  grounding: {
    label_found: number; cases: number
    memory_vs_label: { both_expected: number; both_unexpected: number; memory_expected_label_not: number; memory_unexpected_label_listed: number }
    actions_changed: number; changed_to_expedite: number; changed_from_expedite: number; changed_serious_to_expedite: number
    label_latency_ms: LatStats
    examples: { primaryid: number; suspect: string; reactions: string[]; serious: boolean; memory_expected: number; label: Record<string, string[]>; before: string; after: string }[]
  }
}
export interface EvidenceGrade {
  id: string; drug: string; pt: string; grade: 'A' | 'B' | 'C' | 'L' | 'D' | 'U'; grade_name: string
  axes: { regulatory: number; regulatory_name: string; signal: string; literature: { read: number; supportive: number; analytic_read: number; analytic_supportive: number; anecdotal_supportive: number; analytic_status: string } }
  label_sections: string[]; disclaimer: { section: string; quote: string } | null
  stats: { a: number; prr: number; prr_lo: number; prr_hi: number; ror_lo: number; ic025: number; chi2: number } | null
  basis: string[]; gaps: string[]; summary: string; caution: string
  literature?: { count: number | null; articles: LitArticle[]; summary: Record<string, unknown> }
}
export interface LitArticle { pmid: string; year: string | null; title: string; design: string; design_source: string; supports: number; strength: number | null; dechallenge: number; id: string }
