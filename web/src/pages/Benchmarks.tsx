import { useEffect, useState } from 'react'
import { Card, Kpi, Loading, PageHead } from '../components/ui'
import { fmt, getJSON } from '../lib/data'
import type { Bench, Escalation, LatStats, Overview } from '../lib/types'

const ARMS: { key: 'flyvigilance' | 'flyvigilance_ungrounded' | 'raw_jev'; name: string; sub: string; color: string }[] = [
  { key: 'flyvigilance', name: 'FlyVigilance', sub: '규칙 게이트 + 라벨 근거 주입 + 7문항 타입 판단 + 결정 정책', color: 'var(--c-sense)' },
  { key: 'flyvigilance_ungrounded', name: 'FlyVigilance · 근거 주입 없음', sub: '이전 설정 (라벨 여부를 Jev 기억에 물음)', color: '#7aa7ff' },
  { key: 'raw_jev', name: 'raw Jev', sub: '같은 엔진에 질문 하나: "먼저 봐야 하나?"', color: 'var(--jev)' },
]
const ROUTE_KO: Record<string, string> = { expedite: '사람 우선', signal_review: 'System-2 검토', follow_up: '추가정보 요청', monitor: '모니터링', close: '종결' }
const ROUTE_COL: Record<string, string> = { expedite: '#ff5d6c', signal_review: '#76b900', follow_up: '#a58bff', monitor: '#37e6ff', close: '#6c7aa8' }

function LatBox({ s, color, label, max }: { s: LatStats; color: string; label: string; max: number }) {
  const x = (v: number) => `${(Math.log10(Math.max(v, 10)) - 1) / (Math.log10(max) - 1) * 100}%`
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '210px 1fr 120px', gap: 12, alignItems: 'center', margin: '10px 0' }}>
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

function ArmRow({ name, sub, color, e }: { name: string; sub: string; color: string; e: Escalation }) {
  return (
    <tr>
      <td><div style={{ fontWeight: 600, color }}>{name}</div><div className="dim" style={{ fontSize: 11 }}>{sub}</div></td>
      <td className="r num" style={{ fontSize: 15, color: e.serious_without_review ? 'var(--bad)' : 'var(--ok)' }}>{e.serious_without_review}</td>
      <td className="r num" style={{ fontSize: 15 }}>{e.escalated}</td>
      <td className="r num" style={{ fontSize: 15, color: e.over_escalated > 10 ? 'var(--warn)' : undefined }}>{e.over_escalated}</td>
      <td className="r num">{fmt.pct(e.sens, 1)}</td>
      <td className="r num">{fmt.pct(e.spec, 1)}</td>
    </tr>
  )
}

export default function Benchmarks() {
  const [b, setB] = useState<Bench | null>(null)
  const [ov, setOv] = useState<Overview | null>(null)
  useEffect(() => { getJSON<Bench>('/data/bench.json').then(setB); getJSON<Overview>('/data/faers/overview.json').then(setOv) }, [])
  if (!b || !ov) return <div className="page"><Loading /></div>
  const jt = b.jev_triage, nt = b.nemotron, ab = b.ablation
  const bl = b.blind_serious
  const maxLat = Math.max(jt.latency_ms.max, nt?.triage.latency_ms.max ?? 0, nt?.blind.latency_ms.max ?? 0, bl.jev.latency_ms.max) * 1.2
  const Q = ov.latest.cases
  const serious = ab ? Math.round(ab.n * b.dataset.serious_rate) : 0
  const g = ab?.grounding

  return (
    <div className="page">
      <PageHead eyebrow={`Measured performance · ${b.generated} · FAERS ${b.dataset.source.split(' ')[1]} 실제 케이스 ${b.dataset.cases}건`}
        title={<>같은 엔진, 다른 설계: <span style={{ color: 'var(--jev)' }}>그대로 쓴 Jev</span> vs <span style={{ color: 'var(--c-sense)' }}>FlyVigilance</span></>}
        lede={<>Jev는 TypeSafe AI가 만든 판단 엔진이고, FlyVigilance는 그 엔진을 약물감시에 맞게 감싼 에이전트입니다. 같은 케이스를 같은 엔진으로 돌리되,
          질문 하나만 던진 경우(raw)와 FlyVigilance의 설계(규칙 게이트, 라벨 근거 주입, 규제 용어로 쪼갠 7문항, 결정 정책)를 거친 경우를 비교했습니다.
          정답은 FAERS 결과 코드(중대 여부)이고, 모든 숫자는 <span className="mono">pipeline/bench/bench.py</span> 실행 결과입니다.</>} />

      {ab && <>
        <div className="grid g4" style={{ marginBottom: 16 }}>
          <Kpi label="검토 없이 흘러간 중대 사례" value={ab.flyvigilance.serious_without_review} color="var(--ok)" format={(n) => `${Math.round(n)} / ${serious}`}
            sub={`raw Jev ${ab.raw_jev.serious_without_review}건 · 사람 또는 System-2 가 반드시 봄`} />
          <Kpi label="사람 검토 업무량" value={ab.flyvigilance.escalated} color="var(--c-sense)" format={(n) => `${Math.round(n)}건`}
            sub={`raw Jev ${ab.raw_jev.escalated}건 · ${fmt.pct(1 - ab.flyvigilance.escalated / ab.raw_jev.escalated, 0)} 적음`} />
          <Kpi label="사람에게 넘긴 비중대 사례" value={ab.flyvigilance.over_escalated} color="var(--c-memory)" format={(n) => `${Math.round(n)}건`}
            sub={`raw Jev ${ab.raw_jev.over_escalated}건 (비중대의 ${fmt.pct(ab.raw_jev.over_escalated / (ab.n - serious), 0)})`} />
          <Kpi label="라벨 근거로 구해 낸 중대 사례" value={ab.flyvigilance_ungrounded.missed_serious - ab.flyvigilance.missed_serious} color="var(--jev)" format={(n) => `+${Math.round(n)}건`}
            sub={`사람 우선 검토 민감도 ${fmt.pct(ab.flyvigilance_ungrounded.sens, 1)} → ${fmt.pct(ab.flyvigilance.sens, 1)}`} />
        </div>

        <div className="grid" style={{ gridTemplateColumns: 'minmax(0,1.3fr) minmax(0,1fr)', marginBottom: 16 }}>
          <Card title="비교 실험 · 같은 440건, 같은 엔진" sub={ab.definition}>
            <table className="tbl">
              <thead><tr><th>조건</th><th className="r">검토 없이 간 중대</th><th className="r">사람 검토</th><th className="r">비중대→사람</th><th className="r">민감도</th><th className="r">특이도</th></tr></thead>
              <tbody>{ARMS.map((a) => <ArmRow key={a.key} name={a.name} sub={a.sub} color={a.color} e={ab[a.key]} />)}</tbody>
            </table>
            <div className="divider" />
            <div className="dim mono" style={{ fontSize: 10.5, marginBottom: 8 }}>FLYVIGILANCE 경로 분포 (근거 주입 전 → 후)</div>
            {(['flyvigilance_ungrounded', 'flyvigilance'] as const).map((k) => (
              <div key={k} style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 10, alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontSize: 11.5 }}>{k === 'flyvigilance' ? '근거 주입 후' : '근거 주입 전'}</span>
                <div style={{ display: 'flex', height: 18, borderRadius: 6, overflow: 'hidden' }}>
                  {Object.entries(ab.routes[k]).filter(([, n]) => n).map(([r, n]) => (
                    <div key={r} title={`${ROUTE_KO[r]} ${n}`} style={{ width: `${n / ab.n * 100}%`, background: ROUTE_COL[r], opacity: .85, fontSize: 10, color: '#051022', paddingLeft: 4, overflow: 'hidden', whiteSpace: 'nowrap' }}>{n / ab.n > 0.08 ? `${ROUTE_KO[r]} ${n}` : ''}</div>
                  ))}
                </div>
              </div>
            ))}
            <div className="note" style={{ marginTop: 8 }}>raw Jev의 "no"는 자동 큐로 가서 아무도 보지 않습니다. FlyVigilance는 중대 사례를 종결·모니터링으로 보내지 않고, 사람 우선이 아니면 System-2(Nemotron) 검토로 올립니다.
              raw의 순위 성능(AUROC {ab.raw_auroc.toFixed(3)})은 나쁘지 않지만, 규정 기한·사유·경로가 없는 한 줄 판단이라 그대로 운영에 쓸 수 없습니다.</div>
          </Card>
          {g && <Card title="라벨 근거 주입 · 기억 대신 조회" sub={`라벨을 찾은 ${g.label_found}/${g.cases}건에서 Jev 기억 속 '라벨에 있음'과 openFDA 라벨 원문을 대조`}>
            <table className="tbl" style={{ textAlign: 'center' }}>
              <thead><tr><th></th><th className="r">라벨에 있음</th><th className="r">라벨에 없음</th></tr></thead>
              <tbody>
                <tr><td>기억: 있음</td><td className="r num">{g.memory_vs_label.both_expected}</td><td className="r num" style={{ color: 'var(--warn)', fontSize: 15 }}>{g.memory_vs_label.memory_expected_label_not}</td></tr>
                <tr><td>기억: 없음</td><td className="r num">{g.memory_vs_label.memory_unexpected_label_listed}</td><td className="r num">{g.memory_vs_label.both_unexpected}</td></tr>
              </tbody>
            </table>
            <div className="grid g3" style={{ gap: 10, marginTop: 12 }}>
              <div><div className="dim mono" style={{ fontSize: 10 }}>경로가 바뀐 케이스</div><div className="num" style={{ fontSize: 20 }}>{g.actions_changed}</div></div>
              <div><div className="dim mono" style={{ fontSize: 10 }}>중대 → 사람 우선으로</div><div className="num" style={{ fontSize: 20, color: 'var(--bad)' }}>{g.changed_serious_to_expedite}</div></div>
              <div><div className="dim mono" style={{ fontSize: 10 }}>조회 지연 p50</div><div className="num" style={{ fontSize: 20 }}>{fmt.ms(g.label_latency_ms.p50)}</div></div>
            </div>
            <div className="note" style={{ marginTop: 10 }}>라벨 검색은 MedDRA PT와 라벨 문구의 문자열 일치(영국·미국 철자, 뒤집힌 어순 포함) 기준이라 동의어는 놓칠 수 있습니다.
              놓치면 '예상하지 못한 반응'으로 처리되어 사람 검토 쪽으로 기울므로, 오류가 나도 안전한 방향입니다. 라벨 문서는 캐시해 두 번째부터 거의 비용이 없습니다.</div>
          </Card>}
        </div>
      </>}

      <div className="grid g4" style={{ marginBottom: 16 }}>
        <Kpi label="FlyVigilance 반사 판단 p50" value={jt.latency_ms.p50} color="var(--jev)" format={(n) => `${Math.round(n)} ms`} sub={`판단 7개 · 라벨 조회 포함 · n=${jt.ok}`} />
        <Kpi label="같은 스키마 · Nemotron 3.5 Lightning" value={nt?.triage.latency_ms.p50 ?? 0} color="var(--nvidia)" format={(n) => fmt.ms(n)} sub={nt ? `같은 7문항을 JSON 으로 · n=${nt.triage.n}` : '실행 안 함'} />
        <Kpi label="1,000건 반사 판단 비용" value={(jt.usd_per_1k ?? 0) * 1000} color="var(--c-memory)" format={(n) => `$${(n / 1000).toFixed(3)}`} sub={`입력 ${jt.tokens_in_mean} tok · 출력 무료 · $0.042/M`} />
        <Kpi label="중대성 맹검 AUROC" value={bl.jev.auroc * 1000} color="var(--c-feedback)" format={(n) => (n / 1000).toFixed(3)} sub={`결과 코드를 가린 상태 · n=${bl.jev.n}`} />
      </div>

      <div className="grid g2" style={{ marginBottom: 16 }}>
        <Card title="엔진 선택 · 반사 층에 무엇을 둘 것인가" sub="같은 7문항 스키마를 두 엔진에 올려 잰 지연 (로그 축)">
          <LatBox s={jt.latency_ms} color="var(--jev)" label="FlyVigilance 반사 · Jev 엔진" max={maxLat} />
          <LatBox s={bl.jev.latency_ms} color="#ffd38a" label="중대성 맹검 · Jev 엔진" max={maxLat} />
          {nt && <LatBox s={nt.triage.latency_ms} color="var(--nvidia)" label="같은 스키마 · Nemotron Lightning" max={maxLat} />}
          {nt && <LatBox s={nt.blind.latency_ms} color="#b6e86b" label="중대성 맹검 · Nemotron Lightning" max={maxLat} />}
          <div className="note" style={{ marginTop: 8 }}>반사 층은 건수가 많고 판단만 필요해서 출력 토큰을 만들지 않는 엔진이 맞습니다. Nemotron은 FlyVigilance 안에서
            근거를 읽고 글을 써야 하는 System-2 평가(Super·Ultra)와 안전 가드(Safety Guard)를 맡습니다. build.nvidia.com 호스팅 NIM은 공유 체험 엔드포인트라 대기열 지연이 섞입니다.</div>
        </Card>
        <Card title="중대성 맹검과 보정" sub="결과 코드를 지운 케이스 문자열로 중대성 확률을 받아 실제 결과 코드로 채점">
          <table className="tbl">
            <thead><tr><th></th><th className="r">n</th><th className="r">AUROC</th><th className="r">정확도@0.5</th></tr></thead>
            <tbody>
              <tr><td>FlyVigilance 반사 · Jev · 전체</td><td className="r num">{bl.jev.n}</td><td className="r num">{fmt.f(bl.jev.auroc, 3)}</td><td className="r num">{fmt.pct(bl.jev.acc, 1)}</td></tr>
              {nt && <tr><td>Jev · 같은 표본</td><td className="r num">{nt.blind.n}</td><td className="r num">{fmt.f(nt.blind.jev_same_subset_auroc, 3)}</td><td className="r num">{fmt.pct(nt.blind.jev_same_subset_acc, 1)}</td></tr>}
              {nt && <tr><td>Nemotron Lightning · 같은 표본</td><td className="r num">{nt.blind.n}</td><td className="r num">{fmt.f(nt.blind.auroc, 3)}</td><td className="r num">{fmt.pct(nt.blind.acc, 1)}</td></tr>}
              <tr><td className="dim">다수 클래스 기준선</td><td className="r num dim">{bl.jev.n}</td><td className="r num dim">0.500</td><td className="r num dim">{fmt.pct(bl.majority_baseline_acc, 1)}</td></tr>
            </tbody>
          </table>
          <div className="note" style={{ marginTop: 10 }}>같은 표본의 엔진 간 차이는 표본이 작아 확정할 수 없습니다. 중대 비율 {fmt.pct(b.dataset.serious_rate, 0)}의 층화 표본이며 실제 분기 구성비와 다릅니다.
            ECE {fmt.f(bl.jev.ece, 3)}. 확률은 집단 수준의 보정값이지 한 건의 확신이 아닙니다(R10).</div>
        </Card>
      </div>

      <div className="grid g2">
        <Card title="분기 1회분 투영" sub="실측 건당 값에 최신 분기 케이스 수를 곱한 단순 투영 (병렬화·배치 미반영)">
          <div className="grid g2" style={{ gap: 12 }}>
            <div><div className="dim mono" style={{ fontSize: 10.5 }}>FLYVIGILANCE 반사 · {fmt.int(Q)}건</div>
              <div className="num" style={{ fontSize: 20 }}>{(Q / jt.throughput_cases_per_s / 3600).toFixed(1)} h · {fmt.usd((jt.usd_per_case ?? 0) * Q)}</div></div>
            {nt && <div><div className="dim mono" style={{ fontSize: 10.5 }}>프런티어 LLM 로 전건 · 순차</div>
              <div className="num" style={{ fontSize: 20 }}>{(Q * nt.triage.latency_ms.p50 / 1000 / 3600).toFixed(0)} h · {fmt.compact(Q * (nt.triage.tokens_in_mean + nt.triage.tokens_out_mean))} tok</div></div>}
          </div>
        </Card>
        <Card title="외부 기준점" sub="우리가 잰 값이 아닙니다. 맥락으로만 씁니다">
          <table className="tbl">
            <tbody>
              <tr><td>사람 · ICSR 내러티브 검토</td><td className="r num">5.56 min / case</td><td className="dim" style={{ fontSize: 11 }}>Warner 2026 CPT, 예비 수치</td></tr>
              <tr><td>고정 규칙 크리틱 · 과잉해석 적발</td><td className="r num">1 / 16</td><td className="dim" style={{ fontSize: 11 }}>팀 선행 실측 (FlyGate)</td></tr>
              <tr><td>TypeSafe AI 공개 속도 주장</td><td className="r num">40–200×</td><td className="dim" style={{ fontSize: 11 }}>공급사 자체 측정, 독립 재현 없음</td></tr>
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  )
}
