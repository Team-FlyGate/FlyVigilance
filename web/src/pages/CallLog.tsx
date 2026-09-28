import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Card, Kpi, Loading, PageHead } from '../components/ui'
import { getJSON } from '../lib/data'
import Term from '../components/Term'
import { t } from '../lib/i18n'

// NVIDIA 호출 로그: pipeline/bench/nvidia_call_audit.py 가 만든 /data/nvidia_calls.json 을 보여 줍니다.
// live = 이번 감사에서 모델·엔드포인트마다 한 번씩 실제로 부른 기록(api/_fv/calllog.py, FV_CALL_LOG)
// archived = 저장소에 이미 있던 실측 원본(응답 파일, 실행 manifest, 평가 JSON)을 출처 경로와 함께 모은 것
// 키 · Authorization 헤더 · 프롬프트 · 응답 본문은 기록하지 않습니다. 이 화면도 메타데이터만 읽습니다.

const REPO = 'https://github.com/Team-FlyGate/Project-FlyGate/blob/main/'

interface LiveRow {
  step: string; technology: string; group: string; ts: string; service: string; model: string; endpoint: string; purpose: string
  status: number | null; error: string | null; latency_ms: number | null; nvcf_reqid: string | null
  tokens: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number } | null
  bytes_out: number | null; bytes_in: number | null; cache_hit: boolean; polls?: number | null; json_mode?: boolean | null; template?: string | null
  logged_code_path: string | null; code_path: string; pages: string[]; outcome: Record<string, unknown>
}
interface ArchivedRow {
  ts: string | null; service: string | null; model: string | null; endpoint: string | null; purpose: string | null; status: string | null
  latency_ms: number | null; nvcf_reqid: string | null; tokens: LiveRow['tokens']; n_calls: number | null; source: string | null
  code_path?: string | null; note: string | null
}
interface CallLogData {
  generated_utc: string; run_started_utc: string; script: string; logger: string; reproduce: string; privacy: string
  steps: Record<string, { technology: string; group: string; code_path: string; pages: string[] }>
  live: LiveRow[]; archived: ArchivedRow[]
}

const SVC: Record<string, { label: string; short: string; color: string }> = {
  nim: { label: 'build.nvidia.com NIM', short: 'NIM', color: 'var(--nvidia)' },
  retrieval: { label: 'Retrieval NIM', short: 'Retrieval', color: '#37e6ff' },
  bionemo: { label: 'BioNeMo NIM', short: 'BioNeMo', color: '#3ddc97' },
}
const groupOf = (service: string | null) =>
  !service ? 'nim' : service.startsWith('BioNeMo') ? 'bionemo' : service.startsWith('NVIDIA Retrieval') ? 'retrieval' : 'nim'

// 표의 화면 열: 대시보드 경로 → 메뉴 이름(언어에 따라 바뀌므로 렌더할 때 만듭니다)
const pageNames = (): Record<string, string> => ({
  '#/triage': t('사례 분류', 'Case Triage'), '#/korea': t('국내 보고', 'Korean Reports'), '#/bench': t('벤치마크', 'Benchmarks'), '#/skills': t('스킬 · 거버넌스', 'Skills · Governance'), '#/signals': t('신호 연구실', 'Signal Lab'),
  '#/calls': t('이 화면', 'This page'), '#/d-msa': 'MSA-Search', '#/d-of3': 'OpenFold3', '#/d-diffdock': 'DiffDock', '#/d-boltz': 'Boltz-2', '#/cli': 'CLI',
})

// 증거 대응표: 기술 → 코드 → 실행 화면 → 아키텍처 그림 → 호출 기록 단계
const matrix = (): { tech: ReactNode; code: string; screen: string; diagram: string; steps: string[]; note?: string }[] => [
  { tech: <>Nemotron 3 Super · Ultra · 3.5 Lightning (<Term k="System2" />)</>, code: 'api/_fv/assess.py:assess · api/_fv/kr.py:intake → clients.nim_chat', screen: '#/triage · #/korea · CLI triage.png', diagram: 'docs/images/flygate-architecture_v2.1.0.png · #/architecture (Deliberation)', steps: ['super', 'ultra', 'lightning'] },
  { tech: t(<><Term k="guard">Safety Guard 8B v3</Term> + Content Safety PV 정책</>, <><Term k="guard">Safety Guard 8B v3</Term> + Content Safety PV (pharmacovigilance) policy</>), code: 'api/_fv/assess.py:guard · policy_guard · guard_claims', screen: t('#/triage (가드 칩) · #/skills · CLI critic.png', '#/triage (guard chips) · #/skills · CLI critic.png'), diagram: '#/architecture (Inhibitory Critic)', steps: ['guard', 'policy'] },
  { tech: t(<><Term k="reranker">Nemotron 리랭커</Term></>, <><Term k="reranker">Nemotron reranker</Term></>), code: 'api/_fv/literature.py:rerank → clients.nim_rerank', screen: t('#/signals · #/triage (문헌 축) · CLI grade.png', '#/signals · #/triage (literature axis) · CLI grade.png'), diagram: '#/architecture (Signal Memory)', steps: ['rerank'] },
  { tech: <>Nemotron 3 Embed (<Term k="embedding" />)</>, code: 'api/_fv/clients.py:nim_embed · nim_embed_many', screen: t('전용 화면 없음 · 문헌 재정렬 평가의 기준선 (literature_rerank_eval.json)', 'No dedicated page · baseline for the literature reranking evaluation (literature_rerank_eval.json)'), diagram: '#/architecture (Feature Encoding)', steps: ['embed'] },
  { tech: <><Term k="BioNeMo" /> <Term k="MSA" /> · <Term k="OpenFold3" /> · <Term k="Boltz2" /></>, code: t('pipeline/bench/nvidia_call_audit.py:nvcf_call (원본 응답: fly_discovery/measurements/nim)', 'pipeline/bench/nvidia_call_audit.py:nvcf_call (raw responses: fly_discovery/measurements/nim)'), screen: '#/d-msa · #/d-of3 · #/d-boltz', diagram: 'docs/images/flygate-architecture_v2.1.0.png (FlyDiscovery)', steps: ['msa', 'of3', 'boltz'] },
  { tech: <><Term k="BioNeMo" /> <Term k="DiffDock" /></>, code: 'api/_fv/dock.py:dock (POST /api/dock) · api/_fv/docking.py:execute (CLI)', screen: '#/d-diffdock · CLI discover_live.png', diagram: 'docs/images/flygate-architecture_v2.1.0.png (FlyDiscovery)', steps: ['diffdock'] },
  { tech: t(<><Term k="NemoClaw" /> · <Term k="OpenShell" /> (NIM 전용 <Term k="egress" />)</>, <><Term k="NemoClaw" /> · <Term k="OpenShell" /> (NIM-only <Term k="egress" />)</>), code: 'agent/policy/flygate.yaml · agent/openshell_smoke.sh', screen: '#/agent', diagram: 'docs/images/flygate_agent_diagram_v1.1.0.png', steps: [], note: 'archived · openshell_smoke_2026-09-28.txt (/v1/models 200)' },
]

function StatusChip({ status, error }: { status: number | string | null; error?: string | null }) {
  const s = status === null || status === undefined ? '' : String(status)
  const ok = /^(2\d\d|completed)/.test(s) && !error
  const cls = ok ? 'ok' : /^(5|4)\d\d/.test(s) || error ? 'bad' : 'warn'
  return <span className={`chip ${cls}`} style={{ fontSize: 10.5, padding: '1px 8px', whiteSpace: 'nowrap' }}>{[s, error].filter(Boolean).join(' · ') || '—'}</span>
}

const ms = (v: number | null | undefined) => (v === null || v === undefined ? '—' : v >= 10000 ? `${(v / 1000).toFixed(1)} s` : `${Math.round(v).toLocaleString('en-US')} ms`)
const hhmmss = (ts: string | null) => (ts ? ts.replace('T', ' ').replace(/\.\d+Z$/, 'Z').replace(/\+00:00$/, 'Z') : '—')
// 이전 기록의 시각은 형식이 섞여 있습니다: ISO(UTC 또는 +09:00 커밋 시각), 'YYYY-MM-DD HH:MM (KST)'
const when = (ts: string | null) => {
  if (!ts) return '—'
  if (ts.includes('(KST)')) return ts.replace(' (KST)', ' KST')
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.\d+)?(Z|[+-]\d{2}:\d{2})?$/.exec(ts)
  if (!m) return ts
  return `${m[1]} ${m[2]} ${!m[3] || m[3] === 'Z' || m[3] === '+00:00' ? 'UTC' : m[3] === '+09:00' ? 'KST' : m[3]}`
}
const tok = (t: LiveRow['tokens']) => (t ? [t.prompt_tokens, t.completion_tokens].filter((x) => x !== undefined).join(' → ') || String(t.total_tokens ?? '') : '—')
const src = (p: string | null | undefined) => (p ? <a className="mono" href={REPO + p} target="_blank" rel="noreferrer" style={{ fontSize: 10.5, color: 'var(--text-2)' }}>{p}</a> : '—')

export default function CallLog() {
  const [d, setD] = useState<CallLogData | null>(null)
  const [err, setErr] = useState(false)
  const [svc, setSvc] = useState<'all' | 'nim' | 'retrieval' | 'bionemo'>('all')
  const [model, setModel] = useState('all')
  const [arch, setArch] = useState<'all' | 'nim' | 'retrieval' | 'bionemo'>('all')
  useEffect(() => { getJSON<CallLogData>('/data/nvidia_calls.json').then(setD).catch(() => setErr(true)) }, [])

  const models = useMemo(() => [...new Set((d?.live ?? []).map((r) => r.model))], [d])
  const live = useMemo(() => (d?.live ?? []).filter((r) => (svc === 'all' || r.group === svc) && (model === 'all' || r.model === model)), [d, svc, model])
  const archived = useMemo(() => (d?.archived ?? []).filter((r) => arch === 'all' || groupOf(r.service) === arch), [d, arch])

  if (err) return <div className="page"><Card title={t('호출 기록을 읽지 못했습니다', 'Could not load the call log')}><p className="muted">{t('/data/nvidia_calls.json 이 없습니다. pipeline/bench/nvidia_call_audit.py 를 실행하세요.', '/data/nvidia_calls.json is missing. Run pipeline/bench/nvidia_call_audit.py.')}</p></Card></div>
  if (!d) return <div className="page"><Loading /></div>

  const ok = d.live.filter((r) => r.status === 200 && !r.error).length
  const fail = d.live.length - ok
  const withId = d.live.filter((r) => r.nvcf_reqid).length
  const stepRows = (s: string) => d.live.filter((r) => r.step === s)
  const PAGE = pageNames()

  return (
    <div className="page">
      <PageHead eyebrow="Evidence · NVIDIA API call log"
        title={t(<>NVIDIA <span style={{ color: 'var(--nvidia)' }}>호출 로그</span>: 어떤 모델을, 어느 코드에서, 어떻게 불렀는지</>, <>NVIDIA <span style={{ color: 'var(--nvidia)' }}>call log</span>: which model, from which code, and how</>)}
        lede={t(<>프로젝트가 쓰는 NVIDIA 모델과 엔드포인트를 하나씩 한 번 실제로 부르고, 호출마다 시각 · 모델 · 용도 · HTTP 상태 · 지연 · <Term k="NVCF" /> · <Term k="token">토큰</Term> 수를 남겼습니다. 호출은 저장소의 실제 코드 경로(<span className="mono">api/_fv/*</span>)를 지나가며, 기록기는 <span className="mono">{d.logger}</span> 입니다. 입력은 데모 값(<Term k="PARP1" /> + <Term k="niraparib">니라파립</Term>, 가상의 약물감시 주장)만 씁니다. 아래쪽에는 저장소에 이미 있던 이전 실측 원본을 출처 파일과 함께 모았습니다.</>, <>We called each NVIDIA model and endpoint the project uses once for real, and recorded for every call the time · model · purpose · HTTP status · latency · <Term k="NVCF" /> request ID · <Term k="token">token</Term> counts. Calls pass through the repository's actual code paths (<span className="mono">api/_fv/*</span>); the logger is <span className="mono">{d.logger}</span>. Inputs are demo values only (<Term k="PARP1" /> + <Term k="niraparib">niraparib</Term>, a hypothetical pharmacovigilance claim). Further down, earlier measured originals already in the repository are collected with their source files.</>)} />

      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', marginBottom: 16 }}>
        <Kpi label={t('이번 감사 호출', 'Calls in this audit')} value={d.live.length} sub={t(`${Object.keys(d.steps).length}개 기술 · ${hhmmss(d.run_started_utc).slice(0, 10)}`, `${Object.keys(d.steps).length} technologies · ${hhmmss(d.run_started_utc).slice(0, 10)}`)} color="var(--nvidia)" />
        <Kpi label="HTTP 200" value={ok} sub={fail ? t(`실패 ${fail}건도 그대로 기록`, `${fail} failed calls recorded as-is`) : t('실패 없음', 'No failures')} color="var(--ok)" />
        <Kpi label={t('요청 ID 확보', 'Request IDs captured')} value={withId} hint={t('NVIDIA 서버가 붙인 접수 번호', 'Receipt number assigned by the NVIDIA server')} sub={t('응답 헤더 NVCF-REQID', 'Response header NVCF-REQID')} color="#37e6ff" />
        <Kpi label={t('이전 실측 기록', 'Earlier measured records')} value={d.archived.length} sub={t('응답 원본 · 실행 manifest · 평가 JSON', 'Raw responses · run manifests · evaluation JSON')} color="#e2a74e" />
      </div>

      <Card title={t('기록 원칙', 'Logging principles')} sub={t('심사용 증거이면서 운영 감사 로그입니다', 'Evidence for reviewers and an operational audit log')} style={{ marginBottom: 16 }}>
        <div className="grid g2" style={{ gap: 12, fontSize: 12.5, lineHeight: 1.8, color: 'var(--text-2)' }}>
          {t(<>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            <li><b style={{ color: 'var(--text)' }}>API 키는 기록하지 않습니다.</b> Authorization 헤더, 프롬프트, 응답 본문도 남기지 않습니다. 메타데이터만 남깁니다.</li>
            <li>환경변수 <span className="mono">FV_CALL_LOG=&lt;파일&gt;</span> 을 줄 때만 켜집니다. 없으면 기록기는 아무 일도 하지 않습니다.</li>
            <li>기록 중 오류가 나도 본 호출은 깨지지 않습니다. 테스트: <span className="mono">tests/test_call_log.py</span></li>
          </ul>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            <li>실패한 호출(예: 시간 초과, 5xx)도 다시 시도해 덮지 않고 그대로 적습니다.</li>
            <li>202(접수) 후 폴링하는 <Term k="BioNeMo" /> 작업은 한 줄로 적고, 폴링 횟수와 요청 ID 를 함께 남깁니다.</li>
            <li>재현: <span className="mono" style={{ fontSize: 11 }}>{d.reproduce}</span></li>
          </ul>
          </>, <>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            <li><b style={{ color: 'var(--text)' }}>API keys are never logged.</b> Neither are Authorization headers, prompts or response bodies. Only metadata is kept.</li>
            <li>Logging is on only when the environment variable <span className="mono">FV_CALL_LOG=&lt;file&gt;</span> is set. Otherwise the logger does nothing.</li>
            <li>A logging error never breaks the actual call. Test: <span className="mono">tests/test_call_log.py</span></li>
          </ul>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            <li>Failed calls (e.g. timeouts, 5xx) are recorded as they are, not retried and overwritten.</li>
            <li><Term k="BioNeMo" /> jobs that are accepted (202) and then polled are logged as one row, with the poll count and request ID.</li>
            <li>Reproduce: <span className="mono" style={{ fontSize: 11 }}>{d.reproduce}</span></li>
          </ul>
          </>)}
        </div>
      </Card>

      <Card title={t('이번 감사 호출', 'Calls in this audit')} sub={t(<>생성 {hhmmss(d.generated_utc)} · 스크립트 {src(d.script)}</>, <>Generated {hhmmss(d.generated_utc)} · script {src(d.script)}</>)}
        right={<div className="row" style={{ gap: 8, flexWrap: 'nowrap', alignItems: 'center' }}>
          <div className="seg">{(['all', 'nim', 'retrieval', 'bionemo'] as const).map((k) => <button key={k} className={svc === k ? 'on' : ''} onClick={() => setSvc(k)}>{k === 'all' ? t('전체', 'All') : SVC[k].short}</button>)}</div>
          <select className="input" aria-label={t('모델로 거르기', 'Filter by model')} value={model} onChange={(e) => setModel(e.target.value)} style={{ fontSize: 12, padding: '5px 8px', width: 'auto', maxWidth: 300 }}>
            <option value="all">{t('모든 모델', 'All models')}</option>
            {models.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>}
        style={{ marginBottom: 16 }}>
        <div style={{ overflowX: 'auto' }}>
          <table className="tbl" style={{ minWidth: 1280 }}>
            <thead>{t(<tr><th>시각 (UTC)</th><th>서비스 · 모델</th><th>용도</th><th>상태</th><th className="r">지연</th><th className="r">토큰 in → out</th><th>요청 ID (NVCF-REQID)</th><th>코드 경로</th><th>화면</th></tr>, <tr><th>Time (UTC)</th><th>Service · model</th><th>Purpose</th><th>Status</th><th className="r">Latency</th><th className="r">Tokens in → out</th><th>Request ID (NVCF-REQID)</th><th>Code path</th><th>Page</th></tr>)}</thead>
            <tbody>
              {live.map((r, i) => (
                <tr key={i}>
                  <td className="mono" style={{ fontSize: 10.5, whiteSpace: 'nowrap' }}>{hhmmss(r.ts).slice(11)}</td>
                  <td><span className="chip" style={{ fontSize: 9.5, padding: '0 6px', color: SVC[r.group]?.color, borderColor: SVC[r.group]?.color }}>{SVC[r.group]?.short}</span> <span className="mono" style={{ fontSize: 11 }}>{r.model}</span>
                    <div className="dim mono" style={{ fontSize: 10 }}>{r.endpoint}{r.json_mode ? ' · json_mode' : ''}{r.template ? ` · ${r.template}` : ''}{r.polls ? ` · polls ${r.polls}` : ''}</div></td>
                  <td style={{ fontSize: 11.5, maxWidth: 240 }}>{r.purpose}</td>
                  <td><StatusChip status={r.status} error={r.error} /></td>
                  <td className="r num" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>{ms(r.latency_ms)}</td>
                  <td className="r mono" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>{tok(r.tokens)}</td>
                  <td className="mono" style={{ fontSize: 10.5, color: '#9fe9ff', whiteSpace: 'nowrap' }}>{r.nvcf_reqid ?? '—'}</td>
                  <td style={{ minWidth: 300, maxWidth: 340, overflowWrap: 'anywhere' }}><div className="mono" style={{ fontSize: 10.5 }}>{r.logged_code_path}</div><div className="dim mono" style={{ fontSize: 9.5 }}>{r.code_path}</div></td>
                  <td><div className="stack" style={{ gap: 3, alignItems: 'flex-start' }}>{r.pages.map((p) => <a key={p} className="chip" href={p} style={{ fontSize: 10, padding: '0 6px', whiteSpace: 'nowrap' }}>{PAGE[p] ?? p}</a>)}</div></td>
                </tr>
              ))}
              {!live.length && <tr><td colSpan={9} className="dim">{t('조건에 맞는 호출이 없습니다', 'No calls match the filter')}</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title={t('증거 대응표', 'Evidence map')} sub={t('기술마다 코드 · 실행 화면 · 아키텍처 그림 · 호출 기록을 한 줄로 잇습니다', 'One row per technology links code · running page · architecture diagram · call records')} style={{ marginBottom: 16 }}>
        <div style={{ overflowX: 'auto' }}>
          <table className="tbl" style={{ minWidth: 980 }}>
            <thead>{t(<tr><th>NVIDIA 기술</th><th>코드 경로</th><th>실행 화면</th><th>아키텍처 그림</th><th>호출 기록</th></tr>, <tr><th>NVIDIA technology</th><th>Code path</th><th>Running page</th><th>Architecture diagram</th><th>Call records</th></tr>)}</thead>
            <tbody>
              {matrix().map((m, i) => (
                <tr key={i}>
                  <td style={{ fontSize: 12 }}>{m.tech}</td>
                  <td className="mono" style={{ fontSize: 10.5 }}>{m.code}</td>
                  <td className="mono" style={{ fontSize: 10.5 }}>{m.screen}</td>
                  <td className="mono" style={{ fontSize: 10.5 }}>{m.diagram}</td>
                  <td>{m.note && <span className="dim mono" style={{ fontSize: 10 }}>{m.note}</span>}{m.steps.flatMap(stepRows).map((r, j) => <div key={j} style={{ whiteSpace: 'nowrap' }}><StatusChip status={r.status} error={r.error} /> <span className="mono" style={{ fontSize: 10, color: '#9fe9ff' }}>{r.nvcf_reqid ? r.nvcf_reqid.slice(0, 8) + '…' : '—'}</span></div>)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title={t('이전 실측 기록 (archived)', 'Earlier measured records (archived)')} sub={t('저장소에 이미 있던 NVIDIA 응답 원본과 실행 기록입니다. 시각은 원본 파일의 기록 시각 또는 커밋 시각입니다', 'Raw NVIDIA responses and run records already in the repository. Times are those recorded in the source file or the commit time')}
        right={<div className="seg">{(['all', 'nim', 'retrieval', 'bionemo'] as const).map((k) => <button key={k} className={arch === k ? 'on' : ''} onClick={() => setArch(k)}>{k === 'all' ? t('전체', 'All') : SVC[k].short}</button>)}</div>}>
        <div style={{ overflowX: 'auto', maxHeight: 520 }}>
          <table className="tbl" style={{ minWidth: 1080 }}>
            <thead>{t(<tr><th>시각</th><th>모델</th><th>용도</th><th>상태</th><th className="r">지연</th><th className="r">호출 수</th><th>요청 ID</th><th>출처 파일</th></tr>, <tr><th>Time</th><th>Model</th><th>Purpose</th><th>Status</th><th className="r">Latency</th><th className="r">Calls</th><th>Request ID</th><th>Source file</th></tr>)}</thead>
            <tbody>
              {archived.map((r, i) => (
                <tr key={i}>
                  <td className="mono" style={{ fontSize: 10.5, whiteSpace: 'nowrap' }}>{when(r.ts)}</td>
                  <td className="mono" style={{ fontSize: 11 }}>{r.model}</td>
                  <td style={{ fontSize: 11.5, maxWidth: 280 }}>{r.purpose}{r.note && <div className="dim" style={{ fontSize: 10.5 }}>{r.note}</div>}</td>
                  <td><StatusChip status={r.status} /></td>
                  <td className="r num" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>{ms(r.latency_ms)}</td>
                  <td className="r num" style={{ fontSize: 12 }}>{r.n_calls ?? '—'}</td>
                  <td className="mono" style={{ fontSize: 10.5, color: '#9fe9ff', whiteSpace: 'nowrap' }}>{r.nvcf_reqid ?? '—'}</td>
                  <td style={{ maxWidth: 300 }}>{r.source?.startsWith('data/') ? <span className="mono dim" style={{ fontSize: 10.5 }}>{r.source} {t('(로컬)', '(local)')}</span> : src(r.source)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
