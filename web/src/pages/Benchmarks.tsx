import { useEffect, useState } from 'react'
import { Card, Kpi, Loading, PageHead } from '../components/ui'
import { fmt, getJSON } from '../lib/data'
import type { Ablation, Bench, Escalation, LatStats, McNemar, Overview } from '../lib/types'
import Term from '../components/Term'

// 주 측정은 모든 조건의 입력에서 결과 코드를 가린 비교(bench.json 의 ablation_blind)입니다.
// 결과 코드를 보여 준 비교(ablation)는 참고 조건으로 함께 보여 드립니다.
type View = 'blind' | 'visible'
type ArmKey = 'flyvigilance' | 'flyvigilance_ungrounded' | 'flyvigilance_no_dme' | 'raw_jev'

const ARMS: { key: ArmKey; name: string; sub: string; color: string }[] = [
  { key: 'flyvigilance', name: 'FlyVigilance 워크플로', sub: '규칙 게이트 + 라벨 근거 주입 + 7문항 타입 판단 + 결정 정책 + DME 안전망', color: 'var(--c-sense)' },
  { key: 'flyvigilance_ungrounded', name: 'FlyVigilance · 라벨 근거 주입 없음', sub: '라벨 기재 여부를 모델 추정으로 채우는 설정', color: '#7aa7ff' },
  { key: 'flyvigilance_no_dme', name: 'FlyVigilance · DME 안전망 없음', sub: '같은 판단 결과에 안전망만 뺀 정책을 다시 적용', color: '#a58bff' },
  { key: 'raw_jev', name: '질문 하나 (모델 단독)', sub: '같은 판단 모델에 "먼저 봐야 하나?" 한 문항 · p ≥ 0.5면 사람 우선', color: 'var(--jev)' },
]
const ROUTES = ['expedite', 'signal_review', 'follow_up', 'monitor', 'close'] as const
const ROUTE_KO: Record<string, string> = { expedite: '사람 우선', signal_review: 'System-2 검토', follow_up: '추가정보 요청', monitor: '모니터링', close: '종결', auto: '자동 큐' }
const ROUTE_COL: Record<string, string> = { expedite: '#ff5d6c', signal_review: '#76b900', follow_up: '#a58bff', monitor: '#37e6ff', close: '#6c7aa8', auto: '#6c7aa8' }

// 짝지은 McNemar 정확 검정입니다. a_only 는 앞 조건만 해당한 사례 수, b_only 는 뒤 조건만 해당한 사례 수입니다
const TESTS: { key: string; label: string; a: string; b: string; good: 'less' | 'more' }[] = [
  { key: 'serious_unreviewed_fv_vs_raw', label: '자동 큐에 남은 중대 사례', a: 'FlyVigilance만', b: '질문 하나만', good: 'less' },
  { key: 'over_escalation_fv_vs_raw', label: '사람에게 넘긴 비중대 사례', a: 'FlyVigilance만', b: '질문 하나만', good: 'less' },
  { key: 'workload_fv_vs_raw', label: '사람 우선으로 올린 사례', a: 'FlyVigilance만', b: '질문 하나만', good: 'less' },
  { key: 'serious_escalation_grounded_vs_ungrounded', label: '중대 사례를 사람 우선으로 · 라벨 근거 주입', a: '주입 후만', b: '주입 전만', good: 'more' },
  { key: 'serious_escalation_dme_vs_no_dme', label: '중대 사례를 사람 우선으로 · DME 안전망', a: '안전망 있을 때만', b: '없을 때만', good: 'more' },
]

const SUP: Record<string, string> = { '-': '⁻', '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹' }
// 아주 작은 p 값은 과학 표기로 보여 드립니다 (예: 3.4×10⁻²¹)
export function fmtP(p: number): string {
  if (!(p > 0)) return '0'
  if (p >= 0.01) return p.toFixed(2)
  if (p >= 0.001) return p.toFixed(4)
  const e = Math.floor(Math.log10(p))
  return `${(p / 10 ** e).toFixed(1)}×10${String(e).split('').map((c) => SUP[c] ?? c).join('')}`
}

function PChip({ t, good }: { t?: McNemar; good: 'less' | 'more' }) {
  if (!t) return <span className="dim">–</span>
  const sig = t.p < 0.05
  const better = good === 'less' ? t.a_only < t.b_only : t.a_only > t.b_only
  return <span className={`chip ${sig ? (better ? 'ok' : 'bad') : ''}`} style={{ fontSize: 10.5 }}>p = {fmtP(t.p)}{sig ? '' : ' · 차이 없음'}</span>
}

function LatBox({ s, color, label, max }: { s: LatStats; color: string; label: string; max: number }) {
  const x = (v: number) => `${(Math.log10(Math.max(v, 10)) - 1) / (Math.log10(max) - 1) * 100}%`
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr 110px', gap: 12, alignItems: 'center', margin: '10px 0' }}>
      <span style={{ fontSize: 12.5 }}>{label}</span>
      <div style={{ position: 'relative', height: 26 }}>
        <div style={{ position: 'absolute', top: 12, left: x(s.min), width: `calc(${x(s.max)} - ${x(s.min)})`, height: 2, background: color, opacity: .5 }} />
        <div style={{ position: 'absolute', top: 4, left: x(s.p50), width: `calc(${x(s.p90)} - ${x(s.p50)})`, height: 18, background: color, opacity: .35, borderRadius: 4 }} />
        <div style={{ position: 'absolute', top: 1, left: x(s.p50), width: 3, height: 24, background: color, boxShadow: `0 0 10px ${color}` }} />
      </div>
      <span className="num" style={{ fontSize: 12, textAlign: 'right' }}>p50 {fmt.ms(s.p50)}<br /><span className="dim">p90 {fmt.ms(s.p90)}</span></span>
    </div>
  )
}

function StackBar({ parts, total }: { parts: [string, number][]; total: number }) {
  return (
    <div style={{ display: 'flex', height: 20, borderRadius: 6, overflow: 'hidden', background: 'rgba(120,170,255,0.06)' }}>
      {parts.filter(([, n]) => n > 0).map(([r, n]) => (
        <div key={r} title={`${ROUTE_KO[r]} ${n}`} style={{ width: `${(n / total) * 100}%`, background: ROUTE_COL[r], opacity: 0.85, fontSize: 10.5, lineHeight: '20px',
          color: '#051022', paddingLeft: 5, overflow: 'hidden', whiteSpace: 'nowrap' }}>{n / total > 0.12 ? `${ROUTE_KO[r]} ${n}` : n / total > 0.03 ? n : ''}</div>
      ))}
    </div>
  )
}

function ArmRow({ name, sub, color, e, dim }: { name: string; sub: string; color: string; e: Escalation; dim?: boolean }) {
  return (
    <tr style={{ opacity: dim ? 0.7 : 1 }}>
      <td><div style={{ fontWeight: 600, color }}>{name}</div><div className="dim" style={{ fontSize: 11 }}>{sub}</div></td>
      <td className="r num" style={{ fontSize: 15, color: e.serious_without_review ? 'var(--bad)' : 'var(--ok)' }}>{e.serious_without_review}</td>
      <td className="r num" style={{ fontSize: 15 }}>{e.escalated}</td>
      <td className="r num" style={{ fontSize: 15, color: e.over_escalated > 10 ? 'var(--warn)' : undefined }}>{e.over_escalated}</td>
      <td className="r num">{fmt.pct(e.sens, 1)}</td>
      <td className="r num">{fmt.pct(e.spec, 1)}</td>
    </tr>
  )
}

function AblationView({ ab, other, view }: { ab: Ablation; other?: Ablation; view: View }) {
  const n = ab.n
  const serious = ab.serious ?? 0
  const fv = ab.flyvigilance, raw = ab.raw_jev
  const t = (k: string): McNemar | undefined => ab.tests?.[k]
  const pTxt = (k: string) => { const r = t(k); return r ? <> · <Term k="McNemar">McNemar</Term> <Term k="pvalue">p</Term> = {fmtP(r.p)}</> : '' }
  const rs = fv.routes_serious
  const g = ab.grounding
  const gt = t('serious_escalation_grounded_vs_ungrounded')
  const gtOther = other?.tests?.serious_escalation_grounded_vs_ungrounded
  const diff = g.memory_vs_label.memory_expected_label_not + g.memory_vs_label.memory_unexpected_label_listed
  const routeRows = ([['flyvigilance', 'FlyVigilance'], ['flyvigilance_ungrounded', '근거 주입 없음']] as const)
    .filter(([k]) => ab[k].routes_serious)
    .map(([k, name]) => ({ key: k, name, color: ARMS.find((a) => a.key === k)!.color, rs: ab[k].routes_serious! }))
  const allRoutes = fv.routes ?? ab.routes.flyvigilance
  const s2 = allRoutes?.signal_review ?? 0

  return (
    <>
      <div className="grid g4" style={{ marginBottom: 16 }}>
        <Kpi label={<><Term k="autoqueue">자동 큐</Term>에 남은 중대 사례</>} value={fv.serious_without_review} color="var(--ok)" format={(x) => `${Math.round(x)} / ${serious}`}
          sub={<>질문 하나 {raw.serious_without_review}건{pTxt('serious_unreviewed_fv_vs_raw')}<br />자동 큐 = 종결·모니터링, 사람도 <Term k="System2" />(숙고 단계)도 보지 않습니다</>} />
        <Kpi label="사람에게 넘긴 비중대 사례" value={fv.over_escalated} color="var(--c-memory)" format={(x) => `${Math.round(x)}건`}
          sub={<>질문 하나 {raw.over_escalated}건 (비중대의 {fmt.pct(raw.over_escalated / Math.max(1, n - serious), 0)}){pTxt('over_escalation_fv_vs_raw')}</>} />
        <Kpi label="사람 우선 업무량" value={fv.escalated} color="var(--c-sense)" format={(x) => `${Math.round(x)}건`}
          sub={<>질문 하나 {raw.escalated}건 · {fmt.pct(1 - fv.escalated / Math.max(1, raw.escalated), 0)} 적음{pTxt('workload_fv_vs_raw')}</>} />
        <Kpi label={<>사람 우선 <Term k="sens">민감도</Term></>} value={fv.sens} color="var(--warn)" format={(x) => fmt.pct(x, 1)}
          sub={<>질문 하나 {fmt.pct(raw.sens, 1)} · 특이도 {fmt.pct(fv.spec, 1)} vs {fmt.pct(raw.spec, 1)}
            {rs ? <><br />사람 우선이 아닌 중대 사례 중 {rs.signal_review}건은 System-2 검토로 갑니다</> : null}</>} />
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'minmax(0,1.25fr) minmax(0,1fr)', marginBottom: 16 }}>
        <Card title={<><Term k="ablation">비교 실험</Term> · 같은 {n}건, 같은 판단 모델</>}
          sub="사람 우선 = FlyVigilance 행동 '사람 우선(expedite)' / 질문 하나 p ≥ 0.5. 자동 큐 = 종결·모니터링(질문 하나는 사람 우선이 아닌 전부). 정답 = FAERS 결과 코드 있음(중대)">
          <table className="tbl">
            <thead><tr><th>조건</th><th className="r">자동 큐에 남은 중대</th><th className="r">사람 우선</th><th className="r">비중대→사람</th><th className="r">민감도</th><th className="r">특이도</th></tr></thead>
            <tbody>{ARMS.map((a) => {
              const e = ab[a.key]
              return e ? <ArmRow key={a.key} name={a.name} sub={a.sub} color={a.color} e={e} dim={a.key === 'flyvigilance_no_dme'} /> : null
            })}</tbody>
          </table>
          {ab.tests && <>
            <div className="divider" />
            <div className="dim mono" style={{ fontSize: 10.5, marginBottom: 6 }}>짝지은 <Term k="McNemar">McNemar 정확 검정</Term> · 같은 사례에서 한쪽 조건만 해당한 수</div>
            <table className="tbl" style={{ fontSize: 12 }}>
              <tbody>{TESTS.map((x) => {
                const r = t(x.key)
                return (
                  <tr key={x.key}>
                    <td>{x.label}</td>
                    <td className="r"><span className="dim" style={{ fontSize: 11 }}>{x.a}</span> <b className="num">{r ? r.a_only : '–'}</b></td>
                    <td className="r"><span className="dim" style={{ fontSize: 11 }}>{x.b}</span> <b className="num">{r ? r.b_only : '–'}</b></td>
                    <td className="r"><PChip t={r} good={x.good} /></td>
                  </tr>
                )
              })}</tbody>
            </table>
          </>}
          <div className="note" style={{ marginTop: 10 }}>질문 하나의 '아니오'는 자동 큐로 가서 아무도 보지 않습니다. FlyVigilance는 사람 우선이 아니어도 판단이 불확실하거나 신호 검토가 필요하면
            System-2(NVIDIA Nemotron 숙고 + 3단 크리틱)로 올리고, 판단이 분명히 낮은 것만 자동 큐로 보냅니다. 질문 하나의 순위 성능(<Term k="AUC">AUROC</Term> {fmt.f(ab.raw_auroc, 3)})은 나쁘지 않지만,
            규정 기한·사유·경로가 없는 한 줄 판단이라 그대로 운영에 쓰기 어렵습니다.</div>
        </Card>

        <Card title={`중대 ${serious}건이 간 경로`} sub="자동 큐 = 종결·모니터링입니다. 질문 하나에는 System-2 같은 중간 경로가 없습니다">
          {routeRows.map((r) => (
            <div key={r.key} style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 10, alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: 12, color: r.color }}>{r.name}</span>
              <StackBar parts={ROUTES.map((k) => [k, r.rs[k] ?? 0])} total={serious} />
            </div>
          ))}
          <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 10, alignItems: 'center', marginBottom: 8 }}>
            <span style={{ fontSize: 12, color: 'var(--jev)' }}>질문 하나</span>
            <StackBar parts={[['expedite', serious - raw.missed_serious], ['auto', raw.serious_without_review]]} total={serious} />
          </div>
          <table className="tbl" style={{ marginTop: 8, fontSize: 12 }}>
            <thead><tr><th>중대 사례 수</th>{ROUTES.map((k) => <th key={k} className="r">{ROUTE_KO[k]}</th>)}</tr></thead>
            <tbody>
              {routeRows.map((r) => (
                <tr key={r.key}><td style={{ color: r.color }}>{r.name}</td>
                  {ROUTES.map((k) => <td key={k} className="r num" style={{ color: (k === 'monitor' || k === 'close') && r.rs[k] ? 'var(--bad)' : undefined }}>{r.rs[k] ?? 0}</td>)}</tr>
              ))}
              <tr><td style={{ color: 'var(--jev)' }}>질문 하나</td><td className="r num">{serious - raw.missed_serious}</td><td className="r dim">–</td><td className="r dim">–</td>
                <td className="r num" colSpan={2} style={{ color: raw.serious_without_review ? 'var(--bad)' : undefined }}>자동 큐 {raw.serious_without_review}</td></tr>
            </tbody>
          </table>
          {!routeRows.length && <div className="note" style={{ marginTop: 8 }}>중대 사례별 경로는 이 데이터 파일에 없습니다. 재측정 뒤 표시됩니다.</div>}
          {allRoutes && <>
            <div className="divider" />
            <div className="dim mono" style={{ fontSize: 10.5, marginBottom: 6 }}>전체 {n}건 · FLYVIGILANCE 경로</div>
            <StackBar parts={ROUTES.map((k) => [k, allRoutes[k] ?? 0])} total={n} />
          </>}
          <div className="note" style={{ marginTop: 10 }}>FlyVigilance는 사람 우선이 아닌 중대 사례를 대부분 System-2 검토로 보냅니다. 그래서 사람 우선 민감도는 {fmt.pct(fv.sens, 1)}로 낮지만,
            자동 큐에 남는 중대 사례는 {fv.serious_without_review}건입니다. 대가로 System-2 검토가 전체의 {fmt.pct(s2 / n, 0)}({s2}건)를 차지합니다.</div>
        </Card>
      </div>

      <div className="grid" style={{ gridTemplateColumns: ab.dme ? 'minmax(0,1.25fr) minmax(0,1fr)' : 'minmax(0,1fr)', marginBottom: 16 }}>
        <Card title={<><Term k="grounding">라벨 근거 주입</Term> · 추정 대신 원문 조회</>} sub={`라벨을 찾은 ${g.label_found}/${g.cases}건에서 모델이 추정한 '라벨에 있음'과 openFDA 라벨 원문을 대조했습니다`}>
          <div className="grid" style={{ gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)', gap: 16, alignItems: 'start' }}>
            <table className="tbl" style={{ textAlign: 'center' }}>
              <thead><tr><th></th><th className="r">라벨에 있음</th><th className="r">라벨에 없음</th></tr></thead>
              <tbody>
                <tr><td>모델 추정: 있음</td><td className="r num">{g.memory_vs_label.both_expected}</td><td className="r num" style={{ color: 'var(--warn)', fontSize: 15 }}>{g.memory_vs_label.memory_expected_label_not}</td></tr>
                <tr><td>모델 추정: 없음</td><td className="r num" style={{ color: 'var(--warn)', fontSize: 15 }}>{g.memory_vs_label.memory_unexpected_label_listed}</td><td className="r num">{g.memory_vs_label.both_unexpected}</td></tr>
              </tbody>
            </table>
            <div className="grid g3" style={{ gap: 10 }}>
              <div><div className="dim mono" style={{ fontSize: 10 }}>추정 ≠ 라벨</div><div className="num" style={{ fontSize: 20, color: 'var(--warn)' }}>{diff}</div><div className="dim" style={{ fontSize: 10.5 }}>{fmt.pct(diff / Math.max(1, g.label_found), 0)}</div></div>
              <div><div className="dim mono" style={{ fontSize: 10 }}>경로가 바뀐 사례</div><div className="num" style={{ fontSize: 20 }}>{g.actions_changed}</div><div className="dim" style={{ fontSize: 10.5 }}>중대 → 사람 우선 {g.changed_serious_to_expedite}</div></div>
              <div><div className="dim mono" style={{ fontSize: 10 }}>조회 지연 p50</div><div className="num" style={{ fontSize: 20 }}>{fmt.ms(g.label_latency_ms.p50)}</div><div className="dim" style={{ fontSize: 10.5 }}>캐시 포함</div></div>
            </div>
          </div>
          <div className="note" style={{ marginTop: 12 }}>
            라벨 원문 조회로 {fmt.pct(diff / Math.max(1, g.label_found), 0)}의 사례에서 라벨 기재 여부를 바로잡았습니다. FlyVigilance는 이 값을 조회로 정하고, 근거로 라벨 절을 남깁니다.
            {gt && <> 중대 사례를 사람 우선으로 올린 경우는 주입 후에만 {gt.a_only}건, 주입 전에만 {gt.b_only}건이었습니다(p = {fmtP(gt.p)}{gt.p < 0.05 ? '' : ', 차이 없음'}).</>}
            {gtOther && <> {view === 'blind' ? '결과 코드를 보여 준 조건' : '결과 코드를 가린 조건'}에서는 {gtOther.a_only} 대 {gtOther.b_only}(p = {fmtP(gtOther.p)})였습니다.</>}
            {' '}라벨 검색은 <Term k="MedDRA" />와 라벨 문구의 일치(영국·미국 철자, 어순, 동의어 사전 포함)로 정하고, 찾지 못한 반응은 '예상하지 못한 반응'으로 두어 사람 검토 쪽으로 보냅니다.
          </div>
        </Card>
        {ab.dme && <Card title={<><Term k="DME" /> 안전망 · <Term k="EMA" /> 지정 의학적 사건</>} sub="보고된 반응이 EMA DME 목록(62개 PT)에 있으면 점수와 관계없이 사람 검토로 보냅니다 (약사 검토 반영)">
          <div className="grid g3" style={{ gap: 10 }}>
            <div><div className="dim mono" style={{ fontSize: 10 }}>DME 반응이 있는 사례</div><div className="num" style={{ fontSize: 20 }}>{ab.dme.cases_with_dme}</div><div className="dim" style={{ fontSize: 10.5 }}>그중 중대 {ab.dme.serious_among_dme}</div></div>
            <div><div className="dim mono" style={{ fontSize: 10 }}>안전망이 바꾼 경로</div><div className="num" style={{ fontSize: 20 }}>{ab.dme.changed_by_dme}</div><div className="dim" style={{ fontSize: 10.5 }}>그중 중대 {ab.dme.serious_changed_by_dme}</div></div>
            <div><div className="dim mono" style={{ fontSize: 10 }}>McNemar</div><div style={{ marginTop: 6 }}><PChip t={t('serious_escalation_dme_vs_no_dme')} good="more" /></div></div>
          </div>
          <div className="note" style={{ marginTop: 12 }}>{ab.dme.changed_by_dme === 0
            ? <>이 표본에서는 DME 반응이 있는 {ab.dme.cases_with_dme}건이 안전망 없이도 이미 사람 우선 또는 추가정보 요청으로 가서, 안전망이 바꾼 경로가 0건입니다. 효과가 있다고 주장하지 않습니다. 모델이 드문 중대 사건을 낮게 볼 때를 대비한 보험입니다.</>
            : <>안전망이 {ab.dme.changed_by_dme}건의 경로를 사람 검토로 바꿨고, 그중 중대 사례가 {ab.dme.serious_changed_by_dme}건입니다.</>}</div>
        </Card>}
      </div>
    </>
  )
}

export default function Benchmarks() {
  const [b, setB] = useState<Bench | null>(null)
  const [ov, setOv] = useState<Overview | null>(null)
  const [want, setWant] = useState<View>('blind')
  useEffect(() => { getJSON<Bench>('/data/bench.json').then(setB); getJSON<Overview>('/data/faers/overview.json').then(setOv) }, [])
  if (!b || !ov) return <div className="page"><Loading /></div>
  const jt = b.jev_triage, nt = b.nemotron
  const bl = b.blind_serious
  const maxLat = Math.max(jt.latency_ms.max, nt?.triage.latency_ms.max ?? 0, nt?.blind.latency_ms.max ?? 0, bl.jev.latency_ms.max) * 1.2
  const Q = ov.latest.cases
  // ablation_blind 가 아직 없으면(재측정 전) 결과 코드 공개 조건을 경고와 함께 보여 드립니다
  const view: View = want === 'blind' && b.ablation_blind ? 'blind' : b.ablation ? 'visible' : 'blind'
  const pick = view === 'blind' ? b.ablation_blind : b.ablation
  const other = view === 'blind' ? b.ablation : b.ablation_blind
  const ab = pick ? { ...pick, serious: pick.serious ?? Math.round(pick.n * b.dataset.serious_rate) } : undefined

  return (
    <div className="page">
      <PageHead eyebrow={`Measured performance · ${b.ablation_generated ?? b.generated} · ${b.dataset.source} 실제 케이스 ${b.dataset.cases}건`}
        title={<>같은 모델, 다른 설계: <span style={{ color: 'var(--jev)' }}>질문 하나</span> vs <span style={{ color: 'var(--c-sense)' }}>FlyVigilance 워크플로</span></>}
        lede={<>FlyVigilance는 NVIDIA 스킬(build.nvidia.com <Term k="NIM" /> · <Term k="AgentSkills" /> · <Term k="NemoClaw" />/<Term k="OpenShell" />) 위에 짠 <Term k="PV">약물감시</Term> 워크플로입니다. 글을 써야 하는 일은 NVIDIA <Term k="Nemotron" />이 맡고,
          확률만 필요한 판단에는 <Term k="NAR">비자기회귀 판단 모델</Term>(<Term k="Jev" />, TypeSafe AI)을 함께 씁니다. 여기서는 같은 판단 모델에 질문 하나만 던진 경우와 FlyVigilance 워크플로(<Term k="gate">규칙 게이트</Term>, <Term k="grounding">라벨 근거 주입</Term>,
          규제 용어로 쪼갠 <Term k="q7">7문항</Term>, <Term k="policy">결정 정책</Term>, <Term k="DME" ko /> 안전망)를 거친 경우를 같은 사례로 비교합니다. 정답은 <Term k="FAERS" /> <Term k="outcome">결과 코드</Term>(중대 여부)이고, 주 측정에서는 모든 조건의 입력에서 결과 코드를 <Term k="blind">가렸습니다</Term>.
          숫자는 <span className="mono">pipeline/bench/ablation.py</span> 실행 결과입니다.</>} />

      <Card style={{ marginBottom: 16 }}>
        <div className="row wrap between" style={{ gap: 12 }}>
          <div className="seg">
            <button className={view === 'blind' ? 'on' : ''} disabled={!b.ablation_blind} onClick={() => setWant('blind')}
              style={{ opacity: b.ablation_blind ? 1 : 0.45 }}>결과 코드 가림 · 주 측정</button>
            <button className={view === 'visible' ? 'on' : ''} disabled={!b.ablation} onClick={() => setWant('visible')}
              style={{ opacity: b.ablation ? 1 : 0.45 }}>결과 코드 공개 · 참고</button>
          </div>
          {ab && <span className="mono dim" style={{ fontSize: 11 }}>n = {ab.n} · 중대 {ab.serious} · 비중대 {ab.n - ab.serious} · 측정 {b.ablation_generated ?? b.generated}</span>}
        </div>
        {!b.ablation_blind && <div className="note" style={{ marginTop: 10 }}>결과 코드를 가린 비교가 아직 이 데이터 파일에 없습니다. 재측정 뒤에는 이 화면이 그 결과를 주 측정으로 보여 드립니다.</div>}
        {view === 'visible' && ab && (
          <div style={{ marginTop: 12, padding: '10px 12px', borderRadius: 10, border: '1px solid rgba(255,204,77,0.45)', background: 'rgba(255,204,77,0.07)', fontSize: 12.5, lineHeight: 1.65, color: 'var(--text-2)' }}>
            <b style={{ color: 'var(--warn)' }}>참고 조건입니다.</b> 트리아지 입력에 결과 코드(사망·입원 등)가 들어가는 운영과 같은 조건이며, 정답도 같은 결과 코드입니다.
            서술만으로 중대성을 알아보는 능력은 결과 코드를 가린 주 측정에서 봅니다.
          </div>
        )}
      </Card>

      {ab ? <AblationView ab={ab} other={other} view={view} />
        : <Card style={{ marginBottom: 16 }}><div className="note">비교 실험 결과가 이 데이터 파일에 없습니다.</div></Card>}

      <div className="grid g4" style={{ marginBottom: 16 }}>
        <Kpi label={<><Term k="reflex">반사 판단</Term> <Term k="pct">p50</Term> · 7문항 한 번 호출</>} value={jt.latency_ms.p50} color="var(--jev)" format={(n) => `${Math.round(n)} ms`} sub={`비자기회귀 판단 모델 · 라벨 조회 포함 · n=${jt.ok}`} />
        <Kpi label={<>같은 7문항을 <Term k="AR">생성 방식</Term>으로</>} value={nt?.triage.latency_ms.p50 ?? 0} color="var(--nvidia)" format={(n) => fmt.ms(n)} sub={nt ? `NVIDIA Nemotron 3.5 Lightning · JSON 생성 · n=${nt.triage.n}` : '실행하지 않았습니다'} />
        <Kpi label="1,000건 반사 판단 비용" value={(jt.usd_per_1k ?? 0) * 1000} color="var(--c-memory)" format={(n) => `$${(n / 1000).toFixed(3)}`} sub={`입력 ${jt.tokens_in_mean} tok · 출력 과금 없음 · $0.042/M`} />
        <Kpi label={<>중대성 <Term k="blind">맹검</Term> <Term k="AUC">AUROC</Term></>} hint="판별 정확도: 0.5 무작위, 1 완벽" value={bl.jev.auroc * 1000} color="var(--c-feedback)" format={(n) => (n / 1000).toFixed(3)} sub={`결과 코드를 가린 중대성 확률 · n=${bl.jev.n}`} />
      </div>

      <div className="grid g2" style={{ marginBottom: 16 }}>
        <Card title={<>역할 분담 · 생성은 <Term k="AR">자기회귀</Term>, 타입 판단은 <Term k="NAR">비자기회귀</Term></>} sub={<>같은 7문항 스키마를 두 방식으로 받아 잰 지연입니다 (로그 축, 막대 = <Term k="pct">p50–p90</Term>)</>}>
          <LatBox s={jt.latency_ms} color="var(--jev)" label="7문항 · 비자기회귀 판단" max={maxLat} />
          <LatBox s={bl.jev.latency_ms} color="#ffd38a" label="중대성 맹검 · 비자기회귀 판단" max={maxLat} />
          {nt && <LatBox s={nt.triage.latency_ms} color="var(--nvidia)" label="7문항 · 생성 (Nemotron 3.5 Lightning)" max={maxLat} />}
          {nt && <LatBox s={nt.blind.latency_ms} color="#b6e86b" label="중대성 맹검 · 생성 (Nemotron Lightning)" max={maxLat} />}
          <table className="tbl" style={{ marginTop: 10, fontSize: 12 }}>
            <thead><tr><th>일</th><th>맡는 모델</th><th>이유</th></tr></thead>
            <tbody>
              <tr><td>System-2 평가 메모 · 국내 서식 구조화</td><td><span className="chip nv">NVIDIA Nemotron 3 Super · Ultra · 3.5 Lightning</span></td><td className="dim">근거를 읽고 글을 써야 합니다</td></tr>
              <tr><td>주장별 안전 판정</td><td><span className="chip nv">NVIDIA Nemotron Safety Guard</span></td><td className="dim">개별 치료 조언을 막습니다</td></tr>
              <tr><td>반사 트리아지 7문항 · 크리틱 과잉해석 판정 · 문헌 설계 분류</td><td><span className="chip jev">비자기회귀 판단 모델 · Jev (TypeSafe AI)</span></td><td className="dim">답이 타입 있는 확률뿐이라 출력 문장을 생성하지 않습니다</td></tr>
            </tbody>
          </table>
          <div className="note" style={{ marginTop: 10 }}>같은 7문항을 한 번 호출로 받으면 p50 {fmt.ms(jt.latency_ms.p50)}{nt ? <>, 생성 방식으로 받으면 p50 {fmt.ms(nt.triage.latency_ms.p50)}(n={nt.triage.n})</> : null}였습니다.
            이 비교는 어느 일에 어느 방식이 맞는지 정하려는 것이지 모델의 우열을 가리려는 것이 아닙니다. build.nvidia.com 호스팅 NIM은 공유 체험 엔드포인트라 대기열 지연이 섞입니다{nt ? `(p90 ${fmt.ms(nt.triage.latency_ms.p90)})` : ''}.</div>
        </Card>
        <Card title={<>중대성 맹검과 <Term k="ECE">보정</Term></>} sub="결과 코드를 지운 케이스 문자열로 중대성 확률을 받아 실제 결과 코드로 채점했습니다">
          <table className="tbl">
            <thead><tr><th></th><th className="r">n</th><th className="r">AUROC</th><th className="r">정확도@0.5</th></tr></thead>
            <tbody>
              <tr><td>비자기회귀 판단 모델 · 전체</td><td className="r num">{bl.jev.n}</td><td className="r num">{fmt.f(bl.jev.auroc, 3)}</td><td className="r num">{fmt.pct(bl.jev.acc, 1)}</td></tr>
              {nt && <tr><td>비자기회귀 판단 모델 · 같은 표본</td><td className="r num">{nt.blind.n}</td><td className="r num">{fmt.f(nt.blind.jev_same_subset_auroc, 3)}</td><td className="r num">{fmt.pct(nt.blind.jev_same_subset_acc, 1)}</td></tr>}
              {nt && <tr><td>NVIDIA Nemotron 3.5 Lightning · 같은 표본</td><td className="r num">{nt.blind.n}</td><td className="r num">{fmt.f(nt.blind.auroc, 3)}</td><td className="r num">{fmt.pct(nt.blind.acc, 1)}</td></tr>}
              <tr><td className="dim"><Term k="baseline">다수 클래스 기준선</Term></td><td className="r num dim">{bl.jev.n}</td><td className="r num dim">0.500</td><td className="r num dim">{fmt.pct(bl.majority_baseline_acc, 1)}</td></tr>
            </tbody>
          </table>
          <div className="note" style={{ marginTop: 10 }}>같은 표본에서 두 방식의 차이는 표본이 작아 확정할 수 없습니다. 중대 비율 {fmt.pct(b.dataset.serious_rate, 0)}의 층화 표본이며 실제 분기 구성비와 다릅니다.
            <Term k="ECE" /> {fmt.f(bl.jev.ece, 3)}. 확률은 집단 수준의 보정값이지 한 건에 대한 확신이 아닙니다(R10).</div>
        </Card>
      </div>

      <div className="grid g2">
        <Card title="분기 1회분 투영" sub="실측 건당 값에 최신 분기 케이스 수를 곱한 단순 투영입니다 (병렬화·배치 미반영)">
          <div className="grid g2" style={{ gap: 12 }}>
            <div><div className="dim mono" style={{ fontSize: 10.5 }}>FLYVIGILANCE 반사 · {fmt.int(Q)}건</div>
              <div className="num" style={{ fontSize: 20 }}>{(Q / jt.throughput_cases_per_s / 3600).toFixed(1)} h · {fmt.usd((jt.usd_per_case ?? 0) * Q)}</div></div>
            {nt && <div><div className="dim mono" style={{ fontSize: 10.5 }}>같은 7문항을 생성 방식으로 전건 · 순차</div>
              <div className="num" style={{ fontSize: 20 }}>{(Q * nt.triage.latency_ms.p50 / 1000 / 3600).toFixed(0)} h · {fmt.compact(Q * (nt.triage.tokens_in_mean + nt.triage.tokens_out_mean))} tok</div></div>}
          </div>
        </Card>
        <Card title="외부 기준점" sub="우리가 잰 값이 아닙니다. 맥락으로만 씁니다">
          <table className="tbl">
            <tbody>
              <tr><td>사람 · <Term k="ICSR" /> 서술(내러티브) 검토</td><td className="r num">5.56 min / case</td><td className="dim" style={{ fontSize: 11 }}>Warner 2026 CPT, 예비 수치</td></tr>
              <tr><td>고정 규칙 크리틱 · 과잉해석 적발</td><td className="r num">1 / 16</td><td className="dim" style={{ fontSize: 11 }}>팀 선행 실측 (FlyGate)</td></tr>
              <tr><td>TypeSafe AI 공개 속도 주장</td><td className="r num">40–200×</td><td className="dim" style={{ fontSize: 11 }}>공급사 자체 측정, 독립 재현 없음</td></tr>
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  )
}
