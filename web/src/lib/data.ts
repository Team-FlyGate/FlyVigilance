// 정적 데이터(빌드 시 생성)와 라이브 API 접근

const cache = new Map<string, Promise<unknown>>()

export function getJSON<T>(url: string): Promise<T> {
  if (!cache.has(url)) {
    cache.set(url, fetch(url).then((r) => {
      if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`)
      return r.json()
    }))
  }
  return cache.get(url) as Promise<T>
}

export async function getBin(url: string): Promise<ArrayBuffer> {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`)
  return r.arrayBuffer()
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(path, body === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!r.ok) {
    let msg = `HTTP ${r.status}`
    try { msg = (await r.json()).detail ?? msg } catch { /* ignore */ }
    throw new Error(msg)
  }
  return r.json()
}

// ---------- 타입 ----------
export interface LayerDef { key: string; name: string; brain: string; agent: string; neurons: number }
export interface ChannelDef { key: string; name: string; modality: string; neurons: number }
export interface ConnectomeMeta {
  source: string; neurons: number; edges: number; synapses: number; cloudPoints: number
  bbox: [number[], number[]]; layers: LayerDef[]; channels: ChannelDef[]; nt: Record<string, number>
}

export interface Drug { drug: string; role: string; route?: string; dechal?: string; rechal?: string; indication?: string }
export interface Case {
  primaryid: number; caseid: number; quarter: string; fda_dt: string; age: number | null; sex: string | null
  weight: number | null; occp_cod: string | null; country: string | null; rept_cod: string | null; bucket: string
  drugs: Drug[]; reactions: string[]; outcomes: string[]
}

export interface NoulA { type: 'noul'; noul: number }
export interface ChoiceA { type: 'choice'; choice: string; confidence: number; probabilities: Record<string, number> }
export interface ScoreA { type: 'score'; score: number; confidence: number; legend: Record<string, string>; probabilities: Record<string, number> }
export type Answer = NoulA | ChoiceA | ScoreA

export interface TriageResult {
  state: string; suspect: string
  validity?: { valid: boolean; checks: Record<string, boolean> }
  jev: { answers: Record<string, Answer>; usage: { input_tokens: number; output_tokens: number }; model: string; latency_ms: number }
  decision: { action: string; tier: string; system2?: boolean; reasons: string[]; regime?: string; deadline?: string }
}

export interface Claim { id: string; text: string; evidence: string[]; overclaim_p?: number }
export interface Issue { claim: string; tier: number; rule: string; detail: string; p?: number }
export interface AssessRound {
  round: number; model: string; latency_ms: number; usage: Record<string, number>; fallbacks: string[]
  memo: { claims: Claim[]; assessment: string; narrative: string; open_questions?: string[] }
  issues: Issue[]; judge_latency_ms?: number; judge_usage?: Record<string, number>
}
export interface AssessResult {
  verdict: 'pass' | 'returned'; rounds: AssessRound[]; memo: AssessRound['memo']; total_ms: number
  rules: { id: string; text: string }[]; evidence_ms: number
  evidence: {
    suspect: string; reactions: string[]; ids: string[]; catalog?: { id: string; what: string }[]
    faers: (SignalRow & { id: string; N: number; note?: string })[]
    label: { found: boolean; setid?: string; brand?: string; effective?: string; hits?: { id: string; pt: string; section: string; quote: string }[]; listed?: Record<string, boolean> }
    pubmed: Record<string, { count: number | null; pmids: string[]; ids: string[] }>
  }
}

export interface SignalRow {
  pt: string; a: number; expected: number; prr: number; prr_lo: number; prr_hi: number; ror: number; ror_lo: number
  ror_hi: number; chi2: number; ic: number; ic025: number; evans: boolean; ror_sig: boolean; ic_sig: boolean
}

export interface Health { ok: boolean; jev: boolean; nim: boolean; signals_asof: string; signal_drugs: number; cases: number }

export const LAYER_COLOR: Record<string, string> = {
  sense: '#37e6ff', encode: '#4d8dff', reflex: '#ffb547', memory: '#ff4fd8', deliberate: '#76b900',
  critic: '#ff5d6c', assoc: '#6c7aa8', action: '#f4f7ff', feedback: '#a58bff',
}
export const CHANNEL_COLOR: Record<string, string> = {
  faers: '#37e6ff', literature: '#ffd166', trials: '#ff7ab8', label: '#9dff6b', digital: '#8fa2ff', other: '#7d8aa8',
}

export const fmt = {
  int: (n: number) => (n ?? 0).toLocaleString('en-US'),
  compact: (n: number) => Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(n ?? 0),
  pct: (x: number, d = 0) => `${(x * 100).toFixed(d)}%`,
  ms: (x: number) => (x >= 1000 ? `${(x / 1000).toFixed(2)} s` : `${Math.round(x)} ms`),
  usd: (x: number) => (x < 0.01 ? `$${x.toFixed(5)}` : x < 1 ? `$${x.toFixed(3)}` : `$${x.toFixed(2)}`),
  f: (x: number, d = 2) => (x === null || x === undefined || Number.isNaN(x) ? '–' : x.toFixed(d)),
}

export const OUTCOME_LABEL: Record<string, string> = {
  DE: '사망', LT: '생명위협', HO: '입원', DS: '장애', CA: '선천이상', RI: '개입필요', OT: '기타 중요',
}
export const OCCP_LABEL: Record<string, string> = {
  MD: '의사', PH: '약사', OT: '기타 의료인', HP: '의료인', LW: '변호사', CN: '소비자', NA: '미상',
}
