import { useEffect, useMemo, useState } from 'react'
import { Card, Loading, PageHead } from '../components/ui'
import { fmt, getJSON } from '../lib/data'
import type { LiteratureEval, RocMethod, RefsetResult, Validation as V } from '../lib/types'
import Term from '../components/Term'

const FAMILY: Record<RocMethod['family'], { name: string; color: string; dash?: string; width: number }> = {
  metric: { name: '통계 지표 (SQL)', color: '#4d8dff', width: 1.6 },
  raw: { name: '모델 단독', color: '#ffb547', dash: '6 4', width: 2 },
  flyvigilance: { name: 'FlyVigilance · 통계 기반', color: '#37e6ff', width: 2.4 },
  knowledge: { name: 'FlyVigilance · 지식 기반', color: '#7cffb2', width: 3 },
}
const METRIC_SHADE: Record<string, string> = { a: '#2d4a7a', prr: '#3e63a8', ror_lo: '#4d8dff', chi2s: '#7aa7ff', ic025: '#a8c6ff' }
const SET_LABEL: Record<string, string> = {
  OMOP: 'OMOP · 결과 4종', 'EU-ADR': 'EU-ADR · 결과 10종', Harpaz: 'Harpaz · 전 기간', 'Harpaz-prospective': 'Harpaz · 2013년 이전만 (전향)',
}
const DESIGN_KO: Record<string, string> = {
  meta_analysis: '메타분석', rct: 'RCT', case_report: '증례보고', review: '리뷰', case_series: '증례군', cohort: '코호트',
  case_control: '환자대조군', pharmacovigilance: 'PV DB 연구', preclinical: '전임상', other: '기타',
}

function colorOf(m: RocMethod) { return m.family === 'metric' ? METRIC_SHADE[m.key] ?? FAMILY.metric.color : FAMILY[m.family].color }
function labelOf(m: RocMethod) { return m.label }

function RocChart({ res, hidden, size = 380 }: { res: RefsetResult; hidden: Set<string>; size?: number }) {
  const pad = 38, W = size, H = size
  const x = (v: number) => pad + v * (W - pad - 12)
  const y = (v: number) => H - pad - v * (H - pad - 12)
  const pts = [res.points.evans, res.points.triple]
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: size + 40 }}>
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={t} className="axis">
          <line x1={x(t)} x2={x(t)} y1={y(0)} y2={y(1)} strokeDasharray="2 4" />
          <line x1={x(0)} x2={x(1)} y1={y(t)} y2={y(t)} strokeDasharray="2 4" />
          <text x={x(t)} y={H - pad + 16} textAnchor="middle">{t}</text>
          <text x={pad - 6} y={y(t) + 3} textAnchor="end">{t}</text>
        </g>
      ))}
      <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} stroke="rgba(120,170,255,0.25)" />
      <text x={W - 14} y={H - 6} textAnchor="end" fontSize={10} fill="var(--text-3)">1 − 특이도 (FPR)</text>
      <text x={10} y={14} fontSize={10} fill="var(--text-3)">민감도 (TPR)</text>
      {res.methods.filter((m) => !hidden.has(m.key)).map((m) => {
        const f = FAMILY[m.family]
        const d = m.roc.map(([a, b], i) => `${i ? 'L' : 'M'}${x(a).toFixed(1)},${y(b).toFixed(1)}`).join(' ')
        return <path key={m.key} d={d} fill="none" stroke={colorOf(m)} strokeWidth={f.width} strokeDasharray={f.dash}
          style={m.family === 'knowledge' || m.family === 'flyvigilance' ? { filter: `drop-shadow(0 0 6px ${f.color})` } : undefined} />
      })}
      {pts.map((p, i) => p.sens !== null && p.spec !== null && (
        <g key={i} transform={`translate(${x(1 - p.spec)},${y(p.sens)})`}>
          {i === 0 ? <rect x={-5} y={-5} width={10} height={10} transform="rotate(45)" fill="#ff4fd8" /> : <circle r={5} fill="#fff" stroke="#ff4fd8" strokeWidth={2} />}
          <text x={9} y={i === 0 ? -6 : 14} fontSize={10} fill="#ff9ce8">{i === 0 ? 'Evans' : '3중 기준'}</text>
        </g>
      ))}
    </svg>
  )
}

function Finding({ n, title, body, color }: { n: string; title: string; body: React.ReactNode; color: string }) {
  return (
    <div className="card fade-in" style={{ borderLeft: `3px solid ${color}` }}>
      <div className="row" style={{ gap: 10, alignItems: 'flex-start' }}>
        <span style={{ fontFamily: 'var(--font)', fontSize: 26, fontWeight: 700, color }}>{n}</span>
        <div><h3 style={{ fontSize: 15, marginBottom: 6 }}>{title}</h3><div style={{ fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.6 }}>{body}</div></div>
      </div>
    </div>
  )
}

function LitEval({ le }: { le: LiteratureEval }) {
  const cls = ['meta_analysis', 'rct', 'case_report', 'review']
  const max = Math.max(...cls.flatMap((t) => le.labels.map((q) => le.confusion[t]?.[q] ?? 0)))
  return (
    <div className="grid g2" style={{ gap: 16 }}>
      <div className="stack" style={{ gap: 12 }}>
        <div className="row" style={{ gap: 26 }}>
          <div><div className="dim mono" style={{ fontSize: 10.5 }}>ACCURACY</div><div className="num" style={{ fontSize: 34, color: 'var(--c-sense)' }}>{fmt.pct(le.accuracy, 1)}</div></div>
          <div><div className="dim mono" style={{ fontSize: 10.5 }}>분석·증례·리뷰 3분류</div><div className="num" style={{ fontSize: 34 }}>{fmt.pct(le.group_accuracy, 1)}</div></div>
          <div><div className="dim mono" style={{ fontSize: 10.5 }}>ARTICLES</div><div className="num" style={{ fontSize: 34 }}>{le.n}</div></div>
        </div>
        {cls.map((c) => (
          <div key={c} style={{ display: 'grid', gridTemplateColumns: '90px 1fr 80px', gap: 10, alignItems: 'center' }}>
            <span style={{ fontSize: 12.5 }}>{DESIGN_KO[c]}</span>
            <div className="pbar"><i style={{ width: `${le.per_class[c].recall * 100}%`, background: 'var(--c-sense)' }} /></div>
            <span className="num" style={{ fontSize: 12, textAlign: 'right' }}>{fmt.pct(le.per_class[c].recall, 1)} · {le.per_class[c].n}</span>
          </div>
        ))}
        <div className="note">정답: {le.truth_source}. 출판 유형을 가린 채 제목·초록만 주고, FlyVigilance가 문헌 읽기 단계에서 쓰는 같은 질문으로 물었습니다.
          한 번 호출에 {le.articles_per_call}편, 중앙값 {fmt.ms(le.latency_ms_p50)}. 운영에서는 출판 유형이 있으면 규칙으로 정하고, 없을 때만 이 판단을 씁니다.</div>
      </div>
      <div>
        <div className="dim mono" style={{ fontSize: 10.5, marginBottom: 6 }}><Term k="confusion">혼동 행렬</Term> (행 = 정답, 열 = 판정)</div>
        <table className="tbl" style={{ fontSize: 11.5 }}>
          <thead><tr><th></th>{le.labels.map((q) => <th key={q} className="r">{DESIGN_KO[q] ?? q}</th>)}</tr></thead>
          <tbody>{cls.map((t) => (
            <tr key={t}><td>{DESIGN_KO[t]}</td>{le.labels.map((q) => {
              const v = le.confusion[t]?.[q] ?? 0
              return <td key={q} className="r num" style={{ background: v ? `rgba(55,230,255,${0.08 + 0.5 * v / max})` : undefined, color: t === q ? 'var(--text)' : 'var(--text-2)' }}>{v || ''}</td>
            })}</tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  )
}

export default function Validation() {
  const [v, setV] = useState<V | null>(null)
  const [le, setLe] = useState<LiteratureEval | null>(null)
  const [set, setSet] = useState('Harpaz-prospective')
  const [hidden, setHidden] = useState<Set<string>>(new Set(['a', 'prr', 'chi2s']))
  const [onlyPos, setOnlyPos] = useState(false)
  useEffect(() => { getJSON<V>('/data/validation.json').then(setV); getJSON<LiteratureEval>('/data/literature_eval.json').then(setLe).catch(() => null) }, [])
  const res = v?.refsets[set]
  const pairs = useMemo(() => (v?.pairs[set] ?? []).filter((p) => !onlyPos || p.truth === 1).sort((a, b) => b.truth - a.truth || b.fv - a.fv), [v, set, onlyPos])
  if (!v || !res) return <div className="page"><Loading /></div>

  const best = (r: RefsetResult) => r.methods.filter((m) => m.family === 'metric').sort((a, b) => b.auc - a.auc)[0]
  const m = (r: RefsetResult, k: string) => r.methods.find((x) => x.key === k)!
  const omop = v.refsets.OMOP, pro = v.refsets['Harpaz-prospective']
  const toggle = (k: string) => setHidden((h) => { const n = new Set(h); if (n.has(k)) n.delete(k); else n.add(k); return n })

  return (
    <div className="page">
      <PageHead eyebrow="Reference validation · 공개 참조 세트 · 전향적 검증"
        title={<>어느 부품이 어디서 이기는지 <span style={{ color: 'var(--c-sense)' }}>재고 나서</span> 배치했습니다</>}
        lede={<>공개 <Term k="refset">참조 세트</Term>(정답을 미리 정해 둔 평가용 목록) 세 개(OMOP, EU-ADR, Harpaz)의 약물–반응 {Object.values(v.refsets).slice(0, 3).reduce((a, r) => a + r.n, 0)}쌍에서
          통계 지표, 모델 단독 판단, FlyVigilance의 두 판별 모드(<Term k="kbmode">지식 기반·통계 기반</Term>)를 같은 조건으로 비교했습니다. Harpaz는 2013년 <Term k="label">라벨</Term>(허가사항) 변경을 정답으로 삼으므로,
          2013년 이전 보고(구형 <Term k="FAERS">AERS</Term> 2004–2012Q3, {fmt.compact(pro?.N ?? 0)}건)만으로 다시 재어 "미리 알 수 있었는가"를 봤습니다. 이 <Term k="prospective">전향</Term> 조건은 2013년 이전 정보만 쓰므로 통계 기반 판별로 비교합니다.</>} />

      <div className="grid g3" style={{ marginBottom: 16 }}>
        <Finding n="1" color="#7cffb2" title="공인된 연관은 지식 기반 판별이 가려냅니다"
          body={<>약·반응 이름으로 묻는 FlyVigilance 지식 기반 판별이 최고 통계 지표보다 <Term k="AUC" />(판별 정확도: 0.5 무작위, 1 완벽)가 높았습니다
            ({(['OMOP', 'EU-ADR', 'Harpaz'] as const).map((k) => { const r = v.refsets[k]; const d = r.deltas.find((x) => x.best_metric && x.a === 'raw_named')
              return d ? `${k} ${m(r, 'raw_named').auc.toFixed(3)} vs ${best(r).auc.toFixed(3)}${d.ci[0] > 0 ? ' 유의' : ''}` : '' }).filter(Boolean).join(', ')}).
            판단 한 번에 {fmt.ms(v.jev.latency_ms_p50)}(중앙값)이라 트리아지 흐름 안에서 바로 씁니다.</>} />
        <Finding n="2" color="#4d8dff" title="새 조합은 통계, 예측성은 라벨 조회"
          body={<>아직 알려지지 않은 조합의 순위는 SQL 불균형 통계(<Term k="PRR" />·<Term k="ROR" />·<Term k="IC025">IC</Term>, <Term k="SDR" /> <Term k="triple">3중 기준</Term>)가 맡고, 모델이 숫자를 바꾸지 못하게 했습니다.
            라벨 기재 여부(<Term k="expectedness">예측성</Term>)는 FDA 허가 라벨을 조회해서 정합니다. 이름을 가린 통계 기반 판별은 통계 지표와 같은 수준입니다
            (OMOP {m(omop, 'fv').auc.toFixed(2)} vs {best(omop).auc.toFixed(2)}, 차이 없음).</>} />
        <Finding n="3" color="#ff4fd8" title="라벨이 바뀌기 전에 선 SDR"
          body={<>2013년 이전 보고만으로 3중 기준은 그해 라벨이 바뀐 {pro.pos}건 중 <b style={{ color: 'var(--text)' }}>{pro.points.triple.tp}건</b>을 이미 SDR로 잡았고,
            음성 {pro.neg}건 중 오경보는 {pro.points.triple.fp}건이었습니다(양성 예측도 <Term k="PPV" /> {fmt.pct(pro.points.triple.ppv ?? 0, 0)}). 연속 자동 감시의 근거입니다.
            라벨 개정 시점보다 앞섰다는 뜻이며, 규제기관의 인지 시점과는 별개입니다.</>} />
      </div>

      <Card style={{ marginBottom: 16 }}>
        <div className="row wrap between" style={{ gap: 10 }}>
          <div className="seg" style={{ flexWrap: 'wrap' }}>{Object.keys(v.refsets).map((k) => <button key={k} className={set === k ? 'on' : ''} onClick={() => setSet(k)}>{SET_LABEL[k] ?? k}</button>)}</div>
          <span className="mono dim" style={{ fontSize: 11 }}>n={res.n} · 양성 {res.pos} · 음성 {res.neg}{res.window ? ` · ${res.window}` : ''}</span>
        </div>
      </Card>

      <div className="grid" style={{ gridTemplateColumns: 'minmax(320px, 440px) minmax(0,1fr)', alignItems: 'start', marginBottom: 16 }}>
        <Card title={<Term k="ROC" />} sub={<><Term k="sens">민감도</Term>(세로)와 오경보율(가로)을 그린 곡선입니다. 왼쪽 위로 붙을수록 좋습니다. 범례를 눌러 곡선을 켜고 끕니다</>}>
          <RocChart res={res} hidden={hidden} />
          <div className="row wrap" style={{ gap: 6, marginTop: 8 }}>
            {res.methods.map((mm) => (
              <button key={mm.key} className="chip" onClick={() => toggle(mm.key)} style={{ cursor: 'pointer', opacity: hidden.has(mm.key) ? 0.35 : 1, borderColor: colorOf(mm) + '99', color: colorOf(mm) }}>{labelOf(mm)}</button>
            ))}
          </div>
        </Card>
        <div className="stack" style={{ gap: 16 }}>
          <Card title={<><Term k="AUC" /> · 95% <Term k="bootstrap">부트스트랩</Term> 구간</>} sub="같은 쌍, 같은 정답. 모델 계열은 확률 0.5 기준 민감도·특이도도 함께">
            <table className="tbl">
              <thead><tr><th>방법</th><th>계열</th><th className="r">AUC</th><th className="r">95% CI</th><th className="r">민감도@0.5</th><th className="r">특이도@0.5</th></tr></thead>
              <tbody>{[...res.methods].sort((a, b) => b.auc - a.auc).map((mm) => (
                <tr key={mm.key}>
                  <td><span className="legend-dot" style={{ background: colorOf(mm), marginRight: 8 }} />{labelOf(mm)}</td>
                  <td><span className="chip" style={{ fontSize: 10, color: FAMILY[mm.family].color }}>{FAMILY[mm.family].name}</span></td>
                  <td className="r num" style={{ fontSize: 13, color: mm.family === 'knowledge' || mm.family === 'flyvigilance' ? FAMILY[mm.family].color : undefined }}>{mm.auc.toFixed(3)}</td>
                  <td className="r num dim">{mm.ci ? `${mm.ci[0].toFixed(3)}–${mm.ci[1].toFixed(3)}` : '–'}</td>
                  <td className="r num">{mm['at_0.5'] ? fmt.pct(mm['at_0.5'].sens ?? 0, 0) : ''}</td>
                  <td className="r num">{mm['at_0.5'] ? fmt.pct(mm['at_0.5'].spec ?? 0, 0) : ''}</td>
                </tr>
              ))}</tbody>
            </table>
            <div className="grid g2" style={{ gap: 10, marginTop: 12 }}>
              {(['evans', 'triple'] as const).map((k) => {
                const p = res.points[k]
                return (
                  <div key={k} style={{ padding: 10, borderRadius: 10, border: '1px solid rgba(255,79,216,0.35)' }}>
                    <div className="mono" style={{ fontSize: 11, color: '#ff9ce8' }}>{k === 'evans' ? 'Evans (PRR≥2, χ²≥4, a≥3)' : '3중 기준 (Evans ∧ ROR₀₂₅>1 ∧ IC₀₂₅>0)'}</div>
                    <div className="num" style={{ fontSize: 13, marginTop: 4 }}>민감도 {fmt.pct(p.sens ?? 0, 0)} · 특이도 {fmt.pct(p.spec ?? 0, 0)} · PPV {fmt.pct(p.ppv ?? 0, 0)}</div>
                    <div className="dim mono" style={{ fontSize: 10.5 }}><Term k="confusion">TP</Term> {p.tp} · FP {p.fp} · TN {p.tn} · FN {p.fn}</div>
                  </div>
                )
              })}
            </div>
          </Card>
          <Card title="차이 검정 (짝지은 부트스트랩)" sub="구간이 0을 포함하면 차이가 있다고 말할 수 없습니다">
            <div className="stack" style={{ gap: 8 }}>
              {[...res.deltas].sort((x, y) => Number(!!y.best_metric) - Number(!!x.best_metric)).map((d) => {
                const la = labelOf(res.methods.find((x) => x.key === d.a)!), lb = labelOf(res.methods.find((x) => x.key === d.b)!)
                const sig = d.ci[0] > 0 || d.ci[1] < 0
                return (
                  <div key={d.a + d.b} className="row between" style={{ fontSize: 12.5 }}>
                    <span>{la} <span className="dim">−</span> {lb}{d.best_metric && <span className="chip" style={{ fontSize: 9.5, marginLeft: 6 }}>최고 통계 지표</span>}</span>
                    <span className="num">{d.delta >= 0 ? '+' : ''}{d.delta.toFixed(3)} <span className="dim">[{d.ci[0].toFixed(3)}, {d.ci[1].toFixed(3)}]</span> <span className={`chip ${sig ? (d.delta > 0 ? 'ok' : 'bad') : ''}`} style={{ fontSize: 10, marginLeft: 6 }}>{sig ? '유의' : '차이 없음'}</span></span>
                  </div>
                )
              })}
            </div>
          </Card>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'minmax(0,1.4fr) minmax(0,1fr)', alignItems: 'start', marginBottom: 16 }}>
        <Card title="쌍 탐색" sub="정답과 각 방법의 점수입니다. 전향 세트(2013년 이전)의 비교는 통계 기반 판별로 합니다"
          right={<label className="row" style={{ gap: 6, fontSize: 12, cursor: 'pointer' }}><input type="checkbox" checked={onlyPos} onChange={(e) => setOnlyPos(e.target.checked)} />양성만</label>}>
          <div style={{ maxHeight: 460, overflow: 'auto' }}>
            <table className="tbl" style={{ fontSize: 11.5 }}>
              <thead><tr><th>약물</th><th>반응</th><th className="r">정답</th><th className="r">a</th><th className="r">PRR</th><th className="r">IC₀₂₅</th><th>3중</th><th className="r">지식 기반</th><th className="r">통계 기반</th><th className="r">모델 단독</th></tr></thead>
              <tbody>{pairs.map((p) => (
                <tr key={p.drug + p.event}>
                  <td title={p.drug_ref !== p.drug ? `참조 이름: ${p.drug_ref}` : undefined}>{p.drug}</td>
                  <td className="dim">{v.events[p.event]?.label ?? p.event}</td>
                  <td className="r">{p.truth ? <span className="chip ok" style={{ fontSize: 9.5 }}>양성</span> : <span className="chip" style={{ fontSize: 9.5 }}>음성</span>}</td>
                  <td className="r num">{fmt.int(p.a)}</td><td className="r num">{fmt.f(p.prr ?? NaN)}</td><td className="r num">{fmt.f(p.ic025)}</td>
                  <td>{p.triple ? <span className="legend-dot" style={{ background: '#ff4fd8' }} /> : null}</td>
                  <td className="r num" style={{ color: FAMILY.knowledge.color }}>{set === 'Harpaz-prospective' ? '–' : p.raw_named.toFixed(2)}</td>
                  <td className="r num" style={{ color: 'var(--c-sense)' }}>{p.fv.toFixed(2)}</td>
                  <td className="r num dim">{p.raw_blind.toFixed(2)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </Card>
        <Card title="반응 정의" sub={<>Harpaz 정의를 먼저 쓰고, 없는 것은 공개 정규식으로 <Term k="MedDRA" />(이상반응 표준 용어)를 묶었습니다</>}>
          <div className="stack" style={{ gap: 8, maxHeight: 460, overflow: 'auto' }}>
            {Object.entries(v.events).filter(([k]) => (v.pairs[set] ?? []).some((p) => p.event === k)).map(([k, e]) => (
              <details key={k} style={{ padding: '8px 10px', borderRadius: 10, border: '1px solid var(--line)' }}>
                <summary style={{ cursor: 'pointer', fontSize: 12.5 }}>{e.label} <span className="dim mono" style={{ fontSize: 10.5 }}>· PT {e.pts.length}개 · {e.source}</span></summary>
                <div className="row wrap" style={{ gap: 4, marginTop: 6 }}>{e.pts.map((pt) => <span key={pt} className="chip" style={{ fontSize: 10 }}>{pt}</span>)}</div>
                {e.note && <div className="mono dim" style={{ fontSize: 10, marginTop: 4, wordBreak: 'break-all' }}>{e.note}</div>}
              </details>
            ))}
          </div>
        </Card>
      </div>

      {le && <Card title={<>문헌 읽기 단계 검증 · <Term k="design">연구 설계</Term> 판정</>} sub={<>{le.pairs}개 약물–반응 쌍의 PubMed 상위 문헌 중 <Term k="PubMed">MEDLINE</Term>이 설계를 색인한 {le.n}편</>} style={{ marginBottom: 16 }}>
        <LitEval le={le} />
      </Card>}

      <Card title="읽는 법과 한계">
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, lineHeight: 1.8, color: 'var(--text-2)' }}>
          <li>참조 세트의 양성은 라벨·문헌·규제 조치에서 뽑았습니다. 이 측정은 "공인된 조합을 가려내는가"를 재며, 개별 사례의 인과성을 재지 않습니다.</li>
          <li>OMOP 음성 대조군 일부가 잘못 분류됐다는 반론이 있습니다(Hauben et al. 2016). 음성의 정의가 AUC를 좌우합니다.</li>
          <li>라벨·문헌을 쓰는 근거 등급은 이 세트로 평가하지 않았습니다. 정답이 같은 출처에서 나와 순환이기 때문입니다.</li>
          <li>판단 모델 호출 {fmt.int(v.jev.calls)}회, 중앙값 {fmt.ms(v.jev.latency_ms_p50)}. 같은 입력은 캐시해 재실행해도 같은 값이 나오게 했습니다.</li>
          <li>재현: <span className="mono">pipeline/refsets/build_refsets.py → legacy_aers.py → evaluate.py</span></li>
        </ul>
        <div className="row wrap" style={{ gap: 6, marginTop: 10 }}>{v.sources.map((s) => <a key={s.url} className="chip" href={s.url} target="_blank" rel="noreferrer">{s.name} ↗</a>)}</div>
      </Card>
    </div>
  )
}
