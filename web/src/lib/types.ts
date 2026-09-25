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
