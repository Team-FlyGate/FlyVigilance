import { useEffect, useState } from 'react'
import { Card, Kpi, Loading, PageHead } from '../components/ui'
import { fmt, getJSON } from '../lib/data'
import type { Bench, LatStats, Overview } from '../lib/types'

function LatBox({ s, color, label, max }: { s: LatStats; color: string; label: string; max: number }) {
  const x = (v: number) => `${(Math.log10(Math.max(v, 10)) - 1) / (Math.log10(max) - 1) * 100}%`
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '170px 1fr 120px', gap: 12, alignItems: 'center', margin: '10px 0' }}>
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

export default function Benchmarks() {
  const [b, setB] = useState<Bench | null>(null)
  const [ov, setOv] = useState<Overview | null>(null)
  useEffect(() => { getJSON<Bench>('/data/bench.json').then(setB); getJSON<Overview>('/data/faers/overview.json').then(setOv) }, [])
  if (!b || !ov) return <div className="page"><Loading /></div>
  const jt = b.jev_triage, nt = b.nemotron
  const bl = b.blind_serious
  const speed = nt ? nt.triage.latency_ms.p50 / jt.latency_ms.p50 : null
  const tokRatio = nt ? (nt.triage.tokens_in_mean + nt.triage.tokens_out_mean) / (jt.tokens_in_mean + jt.tokens_out_mean) : null
  const maxLat = Math.max(jt.latency_ms.max, nt?.triage.latency_ms.max ?? 0, nt?.blind.latency_ms.max ?? 0, bl.jev.latency_ms.max) * 1.2
  const Q = ov.latest.cases

  return (
    <div className="page">
      <PageHead eyebrow={`Measured performance · ${b.generated}`}
        title={<>같은 케이스, 같은 질문: <span style={{ color: 'var(--jev)' }}>Jev</span> vs <span style={{ color: 'var(--nvidia)' }}>Nemotron</span></>}
        lede={<>{b.dataset.source} 실제 케이스 {b.dataset.cases}건(사망·중대·비중대·소아 층화 표본)으로 이 저장소의 <span className="mono">pipeline/bench/bench.py</span>를 돌린 결과다. 아래 숫자는 전부 그 실행 출력이며, 투영치와 외부 인용은 따로 표시한다.</>} />

      <div className="grid g4" style={{ marginBottom: 16 }}>
        <Kpi label="Jev triage p50 (7 decisions)" value={jt.latency_ms.p50} color="var(--jev)" format={(n) => `${Math.round(n)} ms`} sub={`p90 ${fmt.ms(jt.latency_ms.p90)} · n=${jt.ok}`} />
        <Kpi label={`${nt ? nt.model.split('/')[1] : 'Nemotron'} p50`} value={nt?.triage.latency_ms.p50 ?? 0} color="var(--nvidia)" format={(n) => fmt.ms(n)} sub={nt ? `same 7 questions as JSON · n=${nt.triage.n}` : 'not run'} />
        <Kpi label="speed ratio (p50)" value={speed ?? 0} color="var(--c-sense)" format={(n) => `${n.toFixed(1)}×`} sub="Nemotron p50 ÷ Jev p50, same session" />
        <Kpi label="Jev cost per 1,000 cases" value={(jt.usd_per_1k ?? 0) * 1000} color="var(--c-memory)" format={(n) => `$${(n / 1000).toFixed(4)}`} sub={`${jt.tokens_in_mean} input tok · output free · $0.042/M`} />
      </div>

      <div className="grid g2" style={{ marginBottom: 16 }}>
        <Card title="지연 분포" sub="로그 축 · 막대 = p50–p90, 선 = min–max">
          <LatBox s={jt.latency_ms} color="var(--jev)" label="Jev · 7-question triage" max={maxLat} />
          <LatBox s={bl.jev.latency_ms} color="#ffd38a" label="Jev · blind seriousness" max={maxLat} />
          {nt && <LatBox s={nt.triage.latency_ms} color="var(--nvidia)" label="Nemotron · 7-question JSON" max={maxLat} />}
          {nt && <LatBox s={nt.blind.latency_ms} color="#b6e86b" label="Nemotron · blind seriousness" max={maxLat} />}
          <div className="note" style={{ marginTop: 10 }}>Jev 동시성 {jt.concurrency}, Nemotron 동시성 {nt?.concurrency}. build.nvidia.com 호스팅 NIM은 공유 체험 엔드포인트라 대기열 지연과 503이 섞인다. 자체 배포 NIM에서는 달라진다.</div>
        </Card>
        <Card title="토큰과 처리량" sub="케이스 1건당 평균">
          <table className="tbl">
            <thead><tr><th></th><th className="r">input tok</th><th className="r">output tok</th><th className="r">throughput</th><th className="r">errors</th></tr></thead>
            <tbody>
              <tr><td><span className="chip jev">Jev</span></td><td className="r num">{jt.tokens_in_mean}</td><td className="r num">{jt.tokens_out_mean}</td><td className="r num">{jt.throughput_cases_per_s} /s</td><td className="r num">{jt.errors}</td></tr>
              {nt && <tr><td><span className="chip nv">Nemotron</span></td><td className="r num">{nt.triage.tokens_in_mean}</td><td className="r num">{nt.triage.tokens_out_mean}</td><td className="r num">{(nt.triage.n / nt.triage.wall_s).toFixed(2)} /s</td><td className="r num">{nt.errors.triage}</td></tr>}
            </tbody>
          </table>
          {tokRatio && <div className="note" style={{ marginTop: 10 }}>총 토큰 비율 Nemotron ÷ Jev = <b>{tokRatio.toFixed(2)}×</b>. Jev는 출력 토큰이 과금되지 않고 사고 과정 생성이 없다.</div>}
          <div className="divider" />
          <h3>분기 1회분 투영 <span className="chip warn" style={{ marginLeft: 6 }}>projection</span></h3>
          <div className="grid g2" style={{ gap: 10 }}>
            <div><div className="dim mono" style={{ fontSize: 10.5 }}>JEV · {fmt.int(Q)} cases</div>
              <div className="num" style={{ fontSize: 18 }}>{(Q / jt.throughput_cases_per_s / 3600).toFixed(1)} h · {fmt.usd(jt.usd_per_case * Q)}</div></div>
            {nt && <div><div className="dim mono" style={{ fontSize: 10.5 }}>NEMOTRON ALL CASES · sequential</div>
              <div className="num" style={{ fontSize: 18 }}>{(Q * nt.triage.latency_ms.p50 / 1000 / 3600).toFixed(0)} h · {fmt.compact(Q * (nt.triage.tokens_in_mean + nt.triage.tokens_out_mean))} tok</div></div>}
          </div>
          <div className="note" style={{ marginTop: 8 }}>실측 건당 값에 {ov.asof} 케이스 수를 곱한 단순 투영. 병렬화·배치·캐시는 반영하지 않았다.</div>
        </Card>
      </div>

      <div className="grid g2" style={{ marginBottom: 16 }}>
        <Card title="중대성 맹검 과제" sub="결과 코드(OUTC)를 지운 케이스 문자열만 주고 중대성 확률을 받아, 실제 FAERS 결과 코드 유무로 채점">
          <table className="tbl">
            <thead><tr><th></th><th className="r">n</th><th className="r">AUROC</th><th className="r">accuracy@0.5</th></tr></thead>
            <tbody>
              <tr><td><span className="chip jev">Jev</span> all cases</td><td className="r num">{bl.jev.n}</td><td className="r num">{fmt.f(bl.jev.auroc, 3)}</td><td className="r num">{fmt.pct(bl.jev.acc, 1)}</td></tr>
              {nt && <tr><td><span className="chip jev">Jev</span> same subset</td><td className="r num">{nt.blind.n}</td><td className="r num">{fmt.f(nt.blind.jev_same_subset_auroc, 3)}</td><td className="r num">{fmt.pct(nt.blind.jev_same_subset_acc, 1)}</td></tr>}
              {nt && <tr><td><span className="chip nv">Nemotron</span> subset</td><td className="r num">{nt.blind.n}</td><td className="r num">{fmt.f(nt.blind.auroc, 3)}</td><td className="r num">{fmt.pct(nt.blind.acc, 1)}</td></tr>}
              <tr><td className="dim">majority-class baseline</td><td className="r num dim">{bl.jev.n}</td><td className="r num dim">0.500</td><td className="r num dim">{fmt.pct(bl.majority_baseline_acc, 1)}</td></tr>
            </tbody>
          </table>
          <div className="note" style={{ marginTop: 10 }}>표본은 사망·중대 케이스를 과대 추출한 층화 표본(중대 비율 {fmt.pct(b.dataset.serious_rate, 0)})이다. 실제 분기 구성비와 다르다. 운영에서는 결과 코드가 있으면 중대성을 규칙으로 정하고, 이 과제는 코드가 없는 입력(문헌, 자유기술)에 대한 능력을 잰다.</div>
        </Card>
        <Card title="Jev 확률 보정 (reliability)" sub={`예측 확률 구간별 실제 중대 비율 · ECE ${fmt.f(bl.jev.ece, 3)}`}>
          <svg viewBox="0 0 320 240" style={{ width: '100%', maxHeight: 280 }}>
            <line x1={40} y1={210} x2={310} y2={210} stroke="rgba(120,170,255,0.2)" />
            <line x1={40} y1={210} x2={40} y2={10} stroke="rgba(120,170,255,0.2)" />
            <line x1={40} y1={210} x2={310} y2={10} stroke="rgba(120,170,255,0.35)" strokeDasharray="4 4" />
            {bl.jev.calibration.map((c) => {
              const cx = 40 + c.pred * 270, cy = 210 - c.obs * 200
              return <g key={c.bin}><circle cx={cx} cy={cy} r={Math.max(4, Math.sqrt(c.n) * 1.4)} fill="var(--jev)" opacity={0.75} /><text x={cx + 8} y={cy - 6} fontSize={9} fill="var(--text-2)">n={c.n}</text></g>
            })}
            <polyline fill="none" stroke="var(--jev)" strokeWidth={2} points={bl.jev.calibration.map((c) => `${40 + c.pred * 270},${210 - c.obs * 200}`).join(' ')} />
            <text x={175} y={234} textAnchor="middle" fontSize={10} fill="var(--text-3)">predicted P(serious)</text>
            <text x={12} y={110} fontSize={10} fill="var(--text-3)" transform="rotate(-90 12 110)">observed rate</text>
          </svg>
          <div className="note">보정은 집단의 성질이다. 대각선에 가까워도 개별 케이스의 확신을 뜻하지 않는다 (R10).</div>
        </Card>
      </div>

      <div className="grid g2">
        <Card title="라우팅 일치와 행동 분포" sub="Jev 7문항 판단 → 결정 정책 → 행동">
          {nt && <div className="row wrap" style={{ gap: 8, marginBottom: 12 }}>
            <span className="chip">route agreement Jev vs Nemotron {fmt.pct(nt.triage.route_agreement, 0)} (n={nt.triage.compared})</span>
            <span className="chip">causality agreement {fmt.pct(nt.triage.causality_agreement, 0)}</span>
          </div>}
          <table className="tbl">
            <thead><tr><th>action</th><th className="r">cases</th><th className="r">share</th><th className="r">actually serious</th></tr></thead>
            <tbody>{Object.entries(jt.actions).sort((a, b) => b[1] - a[1]).map(([a, n]) => {
              const s = jt.serious_rate_by_action[a]
              return <tr key={a}><td className="mono">{a}</td><td className="r num">{n}</td><td className="r num">{fmt.pct(n / jt.ok, 1)}</td><td className="r num">{s ? `${fmt.pct(s.serious / s.n, 0)} (${s.serious}/${s.n})` : ''}</td></tr>
            })}</tbody>
          </table>
          <div className="note" style={{ marginTop: 10 }}>“actually serious” = 해당 행동으로 간 케이스 중 FAERS 결과 코드가 있는 비율. 신속보고 쪽에 중대 케이스가 몰리고 종결 쪽에는 드물어야 정책이 제대로 작동하는 것이다.</div>
        </Card>
        <Card title="외부 기준점" sub="우리가 잰 값이 아니다. 비교의 맥락으로만 쓴다">
          <table className="tbl">
            <tbody>
              <tr><td>사람 · ICSR 내러티브 검토</td><td className="r num">5.56 min / case</td><td className="dim" style={{ fontSize: 11 }}>Warner 2026 CPT, 69건 395분. 예비 수치</td></tr>
              <tr><td>Nemotron 3 Super · 예아니오 선별</td><td className="r num">1,672 ms · 369 tok</td><td className="dim" style={{ fontSize: 11 }}>팀 선행 실측 (triage-scale, 10건)</td></tr>
              <tr><td>고정 규칙 크리틱 · 과잉해석 적발</td><td className="r num">1 / 16</td><td className="dim" style={{ fontSize: 11 }}>팀 선행 실측 (FlyGate eval 33건)</td></tr>
              <tr><td>LLM 포함 크리틱 · 과잉해석 적발</td><td className="r num">16 / 16</td><td className="dim" style={{ fontSize: 11 }}>거짓 양성 0/17, 같은 출처</td></tr>
              <tr><td>Jev 공급사 주장 속도</td><td className="r num">40–200×</td><td className="dim" style={{ fontSize: 11 }}>TypeSafe AI 자체 측정·상단 추정치, 독립 재현 없음</td></tr>
            </tbody>
          </table>
          <div className="note" style={{ marginTop: 10 }}>공급사 주장은 인용만 하고, 이 페이지의 속도 비율은 같은 세션에서 우리가 직접 잰 값만 쓴다.</div>
        </Card>
      </div>
    </div>
  )
}
