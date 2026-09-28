import { useEffect, useState } from 'react'
import { Card, PageHead } from '../components/ui'
import { LAYER_COLOR, fmt, getJSON, type ConnectomeMeta } from '../lib/data'
import type { Bench, CriticProbe, Overview, Validation } from '../lib/types'
import Term from '../components/Term'
import { t } from '../lib/i18n'

interface Pain { n: string; title: React.ReactNode; fact: React.ReactNode; src: React.ReactNode; principle: string; brain: React.ReactNode; layer: string; fix: React.ReactNode; metric: React.ReactNode }

const SUP: Record<string, string> = { '-': '⁻', '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹' }
// 아주 작은 p 값은 과학 표기로 보여 드립니다 (예: 3.6×10⁻⁴⁸)
function fmtP(p: number): string {
  if (!(p > 0)) return '0'
  if (p >= 0.01) return p.toFixed(2)
  if (p >= 0.001) return p.toFixed(4)
  const e = Math.floor(Math.log10(p))
  return `${(p / 10 ** e).toFixed(1)}×10${String(e).split('').map((c) => SUP[c] ?? c).join('')}`
}

export default function Problem() {
  const [ov, setOv] = useState<Overview | null>(null)
  const [b, setB] = useState<Bench | null>(null)
  const [meta, setMeta] = useState<ConnectomeMeta | null>(null)
  const [val, setVal] = useState<Validation | null>(null)
  const [probe, setProbe] = useState<CriticProbe | null>(null)
  useEffect(() => {
    getJSON<Overview>('/data/faers/overview.json').then(setOv)
    getJSON<Bench>('/data/bench.json').then(setB).catch(() => null)
    getJSON<ConnectomeMeta>('/data/connectome/meta.json').then(setMeta)
    getJSON<Validation>('/data/validation.json').then(setVal).catch(() => null)
    getJSON<CriticProbe>('/data/critic_probe.json').then(setProbe).catch(() => null)
  }, [])
  const L = (k: string) => meta?.layers.find((l) => l.key === k)?.neurons ?? 0
  // 비교 실험 수치는 모든 조건의 입력에서 결과 코드를 가린 측정(ablation_blind)을 먼저 씁니다
  const ab = b?.ablation_blind ?? b?.ablation
  const pOf = (k: string) => { const test = ab?.tests?.[k]; return test ? <>, <Term k="pvalue">p</Term> = {fmtP(test.p)}</> : '' }
  const arLat = b?.nemotron?.triage.latency_ms.p50
  const pro = val?.refsets['Harpaz-prospective']?.points.triple
  const planted = probe ? Object.entries(probe.summary).filter(([k]) => k !== 'ctrl') : []
  const ctrl = probe?.summary.ctrl

  const pains: Pain[] = [
    {
      n: '01', title: t('처리량 폭증: 모든 케이스를 같은 무게로 읽습니다', 'Volume overload: every case is read with the same weight'),
      fact: t(<><Term k="FAERS" ko /> 한 분기({ov?.asof})에만 보고가 <b>{ov ? fmt.int(ov.per_quarter.at(-1)?.reports ?? 0) : '…'}</b>건입니다. 누적 {ov ? fmt.compact(ov.raw_reports) : '…'}건이 {ov?.quarters ?? '…'}개 분기에 걸쳐 쌓였습니다. 한국 <Term k="KAERS" ko />도 2025년 277,279건입니다.</>,
        <><Term k="FAERS" ko /> received <b>{ov ? fmt.int(ov.per_quarter.at(-1)?.reports ?? 0) : '…'}</b> reports in a single quarter ({ov?.asof}). A cumulative {ov ? fmt.compact(ov.raw_reports) : '…'} reports have piled up over {ov?.quarters ?? '…'} quarters. Korea’s <Term k="KAERS" ko /> also received 277,279 reports in 2025.</>),
      src: t(<>우리 웨어하우스 실측 · KAERS 수치는 식약처 보고동향 보도 인용</>,
        <>Measured in our warehouse · KAERS figure cited from MFDS (Ministry of Food and Drug Safety) reporting-trend press releases</>),
      principle: t('감각 채널의 병렬 수용', 'Parallel intake through sensory channels'), brain: t(`감각 뉴런 ${fmt.int(L('sense'))}개가 모달리티별로 나뉘어 동시에 받습니다`, `${fmt.int(L('sense'))} sensory neurons, split by modality, receive input in parallel`), layer: 'sense',
      fix: t('FAERS, 문헌, 임상시험, 라벨 변경, 디지털 채널을 각각 수용 스킬로 분리하고 한 번에 정규화합니다', 'FAERS, literature, clinical trials, label changes, and digital channels each get their own intake skill and are normalized in one pass'),
      metric: t(<>분기 적재 {ov ? `${(ov.etl.reduce((a, e) => a + e.seconds, 0) / ov.etl.length).toFixed(1)}초/분기` : '…'} (<Term k="SQL">DuckDB</Term>, 노트북)</>,
        <>Load per quarter {ov ? `${(ov.etl.reduce((a, e) => a + e.seconds, 0) / ov.etl.length).toFixed(1)} s/quarter` : '…'} (<Term k="SQL">DuckDB</Term>, laptop)</>),
    },
    {
      n: '02', title: t('사람의 시간: 건당 읽기만 수 분이 걸립니다', 'Human time: reading alone takes minutes per case'),
      fact: t(<>신호 평가 중 <Term k="ICSR" ko /> 서술(내러티브) 검토에 건당 약 5.56분(69건 395분)이 들었고, 자동화 플랫폼으로 약 63% 줄었다는 보고가 있습니다. 접수·코딩·인과성 평가를 뺀 <b>읽기 시간만</b>입니다.</>,
        <>During signal assessment, reviewing each <Term k="ICSR" ko /> narrative took about 5.56 minutes (395 minutes for 69 cases), and an automation platform reportedly cut this by about 63%. That is <b>reading time only</b>, excluding intake, coding, and causality assessment.</>),
      src: t(<>Warner et al., Clin Pharmacol Ther 2026, PMID 42522449 (저자 스스로 예비적 수치라고 밝혔습니다)</>,
        <>Warner et al., Clin Pharmacol Ther 2026, PMID 42522449 (the authors describe the figure as preliminary)</>),
      principle: t('선천적 반사 회로', 'Innate reflex circuits'), brain: t(<><Term k="lateralHorn">Lateral horn</Term> {fmt.int(L('reflex'))}개 뉴런: 학습 없이 즉시 판단합니다</>, <><Term k="lateralHorn">Lateral horn</Term>, {fmt.int(L('reflex'))} neurons: instant judgments without learning</>), layer: 'reflex',
      fix: t(<>FlyVigilance <Term k="reflex">반사 층</Term>이 <Term k="gate">규칙 게이트</Term>와 라벨 조회를 먼저 하고, <Term k="seriousness">중대성</Term>·<Term k="expectedness">예측성</Term>·<Term k="causality">인과성</Term>·우선순위·다음 행동을 <Term k="NAR">비자기회귀 판단 모델</Term>(<Term k="Jev" />) 한 번 호출로 확률과 함께 받아 <Term k="policy">결정 정책</Term>으로 라우팅합니다</>,
        <>The FlyVigilance <Term k="reflex">reflex layer</Term> first runs the <Term k="gate">rule gate</Term> and a label lookup, then obtains <Term k="seriousness">seriousness</Term>, <Term k="expectedness">expectedness</Term>, <Term k="causality">causality</Term>, priority, and next action with probabilities from a single call to the <Term k="NAR">non-autoregressive judgment model</Term> (<Term k="Jev" />), and routes the case with a <Term k="policy">decision policy</Term></>),
      metric: t(<>{b ? <><Term k="pct">p50</Term>(응답 시간 중앙값) <b>{Math.round(b.jev_triage.latency_ms.p50)} ms</b> / 7판단, {b.jev_triage.throughput_cases_per_s}건/초</> : '벤치마크 대기'}</>,
        <>{b ? <><Term k="pct">p50</Term> (median response time) <b>{Math.round(b.jev_triage.latency_ms.p50)} ms</b> / 7 judgments, {b.jev_triage.throughput_cases_per_s} cases/s</> : 'Waiting for benchmark'}</>),
    },
    {
      n: '03', title: t(<>모든 건을 생성형 <Term k="LLM" />(대형 언어 모델)으로 읽으면 비싸고 느립니다</>, <>Reading every case with a generative <Term k="LLM" /> (large language model) is expensive and slow</>),
      fact: t(<>예/아니오 한 줄을 받는 선별에도 생성형 모델은 건당 입력 322 + 출력 47 <Term k="token">토큰</Term>, 지연 중앙값 1.67초를 썼습니다. 분기 40만 건이면 순차로 186시간입니다.</>,
        <>Even for yes/no screening, a generative model used 322 input + 47 output <Term k="token">tokens</Term> per case with a median latency of 1.67 s. At 400,000 reports per quarter, that is 186 hours run sequentially.</>),
      src: t(<>팀 선행 실측: Nemotron 3 Super, niraparib 상위 10건 (korea-agentic-hackathon-2026 triage-scale)</>,
        <>Team’s earlier measurement: Nemotron 3 Super, top 10 niraparib cases (korea-agentic-hackathon-2026 triage-scale)</>),
      principle: t('희소 확장 코딩', 'Sparse expansion coding'), brain: t(<><Term k="mushroom">Kenyon cell</Term> {fmt.int(4064)}개 중 소수만 발화하고 소수의 출력 뉴런(MBON)이 읽습니다</>, <>Only a few of {fmt.int(4064)} <Term k="mushroom">Kenyon cells</Term> fire, and a small set of output neurons (MBONs) reads them</>), layer: 'memory',
      fix: t(<>확률만 필요한 판단은 비자기회귀 판단 모델을 함께 써서 모든 건을 싸게 처리하고, 애매하거나 중대·예상외인 건만 NVIDIA <Term k="Nemotron" />의 숙고로 올립니다. 통계는 <Term k="SQL">SQL</Term>이 계산하고, 공개 <Term k="refset">참조 세트</Term>로 이 배치를 검증했습니다</>,
        <>Judgments that only need a probability also use the non-autoregressive judgment model, so every case is processed cheaply; only ambiguous, serious, or unexpected cases are escalated to NVIDIA <Term k="Nemotron" /> for deliberation. Statistics are computed in <Term k="SQL">SQL</Term>, and this split was validated against public <Term k="refset">reference sets</Term></>),
      metric: t(<>{b ? <>7문항 판단 p50 <b>{fmt.ms(b.jev_triage.latency_ms.p50)}</b>{arLat ? <> · 같은 7문항을 자기회귀로 생성하면 {fmt.ms(arLat)}</> : null} · 반사 판단 {fmt.usd(b.jev_triage.usd_per_1k)} / 1,000건</> : '…'}</>,
        <>{b ? <>7-question judgment p50 <b>{fmt.ms(b.jev_triage.latency_ms.p50)}</b>{arLat ? <> · generating the same 7 questions autoregressively: {fmt.ms(arLat)}</> : null} · reflex judgment {fmt.usd(b.jev_triage.usd_per_1k)} / 1,000 cases</> : '…'}</>),
    },
    {
      n: '04', title: t('그럴듯한 과잉해석', 'Plausible over-interpretation'),
      fact: t(<><Term k="evidenceId">근거 ID</Term>도 붙고 숫자도 맞는데 결론만 틀린 요약이 나옵니다. 고정 규칙은 심어 둔 <Term k="overclaim">과잉해석</Term> 16건 중 1건만 잡았고, LLM 판정을 더하면 16건 모두 잡았습니다(<Term k="confusion">거짓 양성</Term> 0/17).</>,
        <>Summaries come out with <Term k="evidenceId">evidence IDs</Term> attached and correct numbers, yet the wrong conclusion. Fixed rules caught only 1 of 16 planted <Term k="overclaim">over-interpretations</Term>; adding an LLM judgment caught all 16 (<Term k="confusion">false positives</Term> 0/17).</>),
      src: t(<>팀 선행 실측: FlyGate 크리틱 평가 33건 (critic_verdict_output_*.json)</>,
        <>Team’s earlier measurement: 33 FlyGate critic evaluations (critic_verdict_output_*.json)</>),
      principle: t('억제성 되먹임', 'Inhibitory feedback'), brain: t(<><Term k="GABA">GABA성 억제 뉴런</Term> {fmt.int(L('critic'))}개: APL 뉴런이 버섯체 활동을 눌러 희소성을 지킵니다</>, <><Term k="GABA">GABAergic inhibitory neurons</Term> {fmt.int(L('critic'))}: the APL neuron suppresses mushroom-body activity to keep it sparse</>), layer: 'critic',
      fix: t(<>3단 <Term k="critic">크리틱</Term>: 근거 ID 실재(규칙) → <Term k="oracle">숫자 오라클</Term>(SQL 대조) → 과잉해석 판정(비자기회귀 판단 모델, 규칙 13종) + NVIDIA Nemotron <Term k="guard">Safety Guard</Term>. 반려되면 사유와 함께 다시 씁니다</>,
        <>Three-stage <Term k="critic">critic</Term>: evidence IDs exist (rules) → <Term k="oracle">number oracle</Term> (SQL cross-check) → over-interpretation judgment (non-autoregressive judgment model, 13 rules) + NVIDIA Nemotron <Term k="guard">Safety Guard</Term>. Rejected text is rewritten with the reason attached</>),
      metric: t(<>주장마다 overclaim 확률과 위반 규칙 ID를 남깁니다{probe && ctrl ? <> · 틀린 주장 주입 {planted.reduce((a, [, s]) => a + s.correct, 0)}/{planted.reduce((a, [, s]) => a + s.n, 0)} 적발, 대조군 {ctrl.correct}/{ctrl.n} 통과</> : null}</>,
        <>Each claim records an overclaim probability and the violated rule IDs{probe && ctrl ? <> · planted wrong claims caught {planted.reduce((a, [, s]) => a + s.correct, 0)}/{planted.reduce((a, [, s]) => a + s.n, 0)}, controls passed {ctrl.correct}/{ctrl.n}</> : null}</>),
    },
    {
      n: '05', title: t('분기 배치 감시는 늦습니다', 'Quarterly batch surveillance is slow'),
      fact: t(<><Term k="disproportionality">불균형 분석</Term>(보고 비율을 다른 약과 비교하는 통계)을 분기 보고서 주기로 돌리면 불균형 지표가 기준을 넘어 <Term k="SDR" ko />이 선 뒤에도 평가가 시작되지 않습니다. 연속 감시였다면 언제 시작할 수 있었는지는 사후 재계산으로 잴 수 있습니다.</>,
        <>When <Term k="disproportionality">disproportionality analysis</Term> (statistics that compare a drug’s reporting ratio with other drugs) runs on a quarterly report cycle, assessment does not start even after the measure crosses its threshold and an <Term k="SDR" ko /> appears. How early continuous surveillance could have started can be measured by recalculating after the fact.</>),
      src: t(<>신호 타임머신: FDA 안전성 조치 8건 백테스트</>,
        <>Signal Time Machine: backtest of 8 FDA safety actions</>),
      principle: t('연합 학습과 도파민', 'Associative learning and dopamine'), brain: t(<>도파민 뉴런(<Term k="mushroom">DAN</Term>)·MBON 회로가 경험을 누적해 가치를 갱신합니다 (피드백 {fmt.int(L('feedback'))}개 상행 뉴런)</>, <>Dopamine neurons (<Term k="mushroom">DANs</Term>) and MBON circuits accumulate experience and update value (feedback: {fmt.int(L('feedback'))} ascending neurons)</>), layer: 'feedback',
      fix: t(<>매 적재마다 누적 <Term k="table22">2×2 표</Term>를 다시 계산하고, 사람 검토 결과를 되먹여 임계값과 우선순위를 조정합니다</>,
        <>Every load recomputes the cumulative <Term k="table22">2×2 table</Term>, and human review results feed back to adjust thresholds and priorities</>),
      metric: t(<>{pro ? <><Term k="prospective">전향 검증</Term>(Harpaz): 2013년 라벨 변경 전 보고만으로 {pro.tp}/{pro.tp + pro.fn}건에 <Term k="triple">3중 기준</Term> SDR, 오경보 {pro.fp}/{pro.fp + pro.tn}건 (<Term k="PPV" /> {fmt.f(pro.ppv ?? 0)}) · 사례별 선행 일수는 신호 타임머신에서 봅니다</> : '사례별 선행 일수는 신호 타임머신에서 봅니다'}</>,
        <>{pro ? <><Term k="prospective">Prospective test</Term> (Harpaz): using only reports from before the 2013 label changes, <Term k="triple">triple-criterion</Term> SDR in {pro.tp}/{pro.tp + pro.fn} cases, false alarms {pro.fp}/{pro.fp + pro.tn} (<Term k="PPV" /> {fmt.f(pro.ppv ?? 0)}) · per-case lead time is shown in the Signal Time Machine</> : 'Per-case lead time is shown in the Signal Time Machine'}</>),
    },
    {
      n: '06', title: t('데이터 품질: 버전, 삭제, 이름 난립', 'Data quality: versions, deletions, inconsistent names'),
      fact: t(<>{ov ? <>원천 보고 {fmt.int(ov.raw_reports)}건이 고유 케이스 {fmt.int(ov.cases)}건으로 줄어듭니다. 약물명 원문은 {fmt.int(ov.drug_names_raw)}종, FDA 삭제 케이스는 {fmt.int(ov.deleted_cases)}건입니다.</> : '…'}</>,
        <>{ov ? <>{fmt.int(ov.raw_reports)} raw reports reduce to {fmt.int(ov.cases)} unique cases. There are {fmt.int(ov.drug_names_raw)} distinct raw drug-name strings and {fmt.int(ov.deleted_cases)} cases deleted by FDA.</> : '…'}</>),
      src: t(<>우리 웨어하우스 실측 (FDA 권고 중복 제거 규칙)</>,
        <>Measured in our warehouse (FDA-recommended deduplication rules)</>),
      principle: t('투사 뉴런의 정규화', 'Normalization by projection neurons'), brain: t(<><Term k="antennal">안테나엽 PN</Term> {fmt.int(L('encode'))}개가 수천 개 수용체 입력을 사구체별로 정리합니다</>, <><Term k="antennal">Antennal-lobe PNs</Term> ({fmt.int(L('encode'))}) organize input from thousands of receptors by glomerulus</>), layer: 'encode',
      fix: t(<><Term k="caseid">caseid</Term>(사례 번호) 최신 버전, 삭제 목록 반영, 유효성분 우선·염 접미사 제거·상품명→성분 학습 매핑</>,
        <>Latest version per <Term k="caseid">caseid</Term> (case number), deletion list applied, active ingredient first, salt suffixes stripped, learned brand→ingredient mapping</>),
      metric: t(<>{ov ? `상품명→성분 매핑 ${fmt.int(ov.drugname_map)}건 학습` : '…'}</>,
        <>{ov ? `${fmt.int(ov.drugname_map)} brand→ingredient mappings learned` : '…'}</>),
    },
    {
      n: '07', title: t('사람의 주의는 가장 희소한 자원입니다', 'Human attention is the scarcest resource'),
      fact: t(<>최종 판단과 규제 보고는 사람이 해야 합니다. 문제는 사람에게 무엇을, 어떤 근거와 함께 올리느냐입니다.</>,
        <>Final decisions and regulatory reports must be made by humans. The question is what to send to them, and with what evidence.</>),
      src: t(<><Term k="ICH">ICH E2D</Term>, <Term k="GVP">GVP Module VI</Term> 원칙</>,
        <><Term k="ICH">ICH E2D</Term>, <Term k="GVP">GVP Module VI</Term> principles</>),
      principle: t('하행 뉴런 병목', 'The descending-neuron bottleneck'), brain: t(<>{fmt.int(meta?.neurons ?? 0)}개 중 <Term k="descending">하행 뉴런</Term>은 {fmt.int(L('action'))}개({meta ? fmt.pct(L('action') / meta.neurons, 1) : ''})뿐입니다</>, <>Of {fmt.int(meta?.neurons ?? 0)} neurons, only {fmt.int(L('action'))} ({meta ? fmt.pct(L('action') / meta.neurons, 1) : ''}) are <Term k="descending">descending neurons</Term></>), layer: 'action',
      fix: t(<>근거 ID가 붙고 크리틱을 통과한 메모만 사람 큐로 보내고, <Term k="expedited">신속보고</Term> 후보는 15일 시계와 함께 올립니다</>,
        <>Only memos with evidence IDs that pass the critic go to the human queue, and <Term k="expedited">expedited-report</Term> candidates arrive with the 15-day clock</>),
      metric: t(<>{ab ? <>{b?.ablation_blind ? <><Term k="blind">결과 코드를 가린</Term> </> : ''}{ab.n}건: 사람 우선 {ab.flyvigilance.escalated}건 vs 모델 단독 · 질문 하나 {ab.raw_jev.escalated}건{pOf('workload_fv_vs_raw')} · <Term k="autoqueue">자동 큐</Term>에 남은 중대 사례 {ab.flyvigilance.serious_without_review} vs {ab.raw_jev.serious_without_review}건{pOf('serious_unreviewed_fv_vs_raw')}</> : '…'}</>,
        <>{ab ? <>{b?.ablation_blind ? <><Term k="blind">Outcome-blinded</Term>, </> : ''}{ab.n} cases: human-first {ab.flyvigilance.escalated} vs model alone · single question {ab.raw_jev.escalated}{pOf('workload_fv_vs_raw')} · serious cases left in the <Term k="autoqueue">automatic queue</Term> {ab.flyvigilance.serious_without_review} vs {ab.raw_jev.serious_without_review}{pOf('serious_unreviewed_fv_vs_raw')}</> : '…'}</>),
    },
  ]

  return (
    <div className="page">
      <PageHead eyebrow="Problem framing · why FlyVigilance"
        title={t(<><Term k="PV">약물감시</Term>의 병목은 <span style={{ color: 'var(--bad)' }}>양</span>이 아니라 <span style={{ color: 'var(--c-sense)' }}>배분</span>입니다</>,
          <>The bottleneck in <Term k="PV">pharmacovigilance</Term> is not <span style={{ color: 'var(--bad)' }}>volume</span> but <span style={{ color: 'var(--c-sense)' }}>allocation</span></>)}
        lede={t(<>약물감시(PV)는 시판된 약의 <Term k="AE">이상사례</Term> 보고를 모아 위험을 찾아내는 일입니다. 모든 이상사례를 같은 비용으로 읽는 구조가 문제입니다. 초파리 뇌는 16만 개 뉴런으로 이 문제를 이미 풀었습니다. 감각은 넓게 받고, 반사는 싸게, 기억은 희소하게, 숙고는 드물게, 행동은 좁은 병목으로 냅니다. 우리는 그 배선 원리(<Term k="connectome">커넥텀</Term>)를 NVIDIA 스킬 위에 짠 에이전트 워크플로의 라우팅에 옮겼습니다. 처음 보는 용어는 점선 밑줄에 마우스를 올리거나 눌러 보시고, 전체 목록은 <a href="#/glossary">용어 풀이</a>에 있습니다.</>,
          <>Pharmacovigilance (PV) means collecting <Term k="AE">adverse event</Term> reports for marketed drugs to find risks. The problem is a structure that reads every adverse event at the same cost. The fruit fly brain already solved this with about 160,000 neurons: it senses broadly, reflexes cheaply, remembers sparsely, deliberates rarely, and acts through a narrow bottleneck. We carried that wiring principle (the <Term k="connectome">connectome</Term>) into the routing of an agentic workflow built on NVIDIA Skills. Hover over or tap any dotted-underlined term for an explanation; the full list is in the <a href="#/glossary">Glossary</a>.</>)} />

      <div className="stack" style={{ gap: 14 }}>
        {pains.map((p) => (
          <Card key={p.n} className="fade-in">
            <div style={{ display: 'grid', gridTemplateColumns: '64px minmax(0,1.25fr) minmax(0,1fr) minmax(0,1fr)', gap: 22, alignItems: 'start' }}>
              <div style={{ fontFamily: 'var(--font)', fontSize: 34, fontWeight: 700, color: LAYER_COLOR[p.layer], textShadow: `0 0 24px ${LAYER_COLOR[p.layer]}` }}>{p.n}</div>
              <div>
                <div className="eyebrow" style={{ color: 'var(--bad)' }}>Pain</div>
                <h3 style={{ fontSize: 16, margin: '4px 0 8px' }}>{p.title}</h3>
                <div style={{ fontSize: 13, color: 'var(--text-2)' }}>{p.fact}</div>
                <div className="note" style={{ marginTop: 8 }}>{t('출처', 'Source')} · {p.src}</div>
              </div>
              <div style={{ borderLeft: `2px solid ${LAYER_COLOR[p.layer]}`, paddingLeft: 16 }}>
                <div className="eyebrow" style={{ color: LAYER_COLOR[p.layer] }}>Fly brain principle</div>
                <h3 style={{ fontSize: 14.5, margin: '4px 0 6px' }}>{p.principle}</h3>
                <div style={{ fontSize: 12.5, color: 'var(--text-2)' }}>{p.brain}</div>
              </div>
              <div>
                <div className="eyebrow" style={{ color: 'var(--ok)' }}>FlyVigilance</div>
                <div style={{ fontSize: 12.5, margin: '4px 0 10px' }}>{p.fix}</div>
                <div className="chip" style={{ whiteSpace: 'normal', lineHeight: 1.4 }}><span>{p.metric}</span></div>
              </div>
            </div>
          </Card>
        ))}
      </div>
      <Card style={{ marginTop: 16 }}>
        <div className="note" style={{ fontSize: 12.5 }}>
          {t(<>
          <b>경계를 분명히 합니다.</b> 커넥텀은 설계 원리와 실시간 라우팅 시각화를 줍니다. 임상 판단의 근거는 FAERS, 라벨, 문헌이고, 판단은 FlyVigilance의 숙고 층(NVIDIA Nemotron)·반사 층(비자기회귀 판단 모델 병용)과 사람이 합니다.
          초파리 뇌가 약물 안전성을 “이해”한다고 주장하지 않습니다. 배선도는 어디로 보낼지를 말해 주지 무엇이 옳은지를 말해 주지 않습니다.
          </>, <>
          <b>Clear boundaries.</b> The connectome provides a design principle and a real-time routing visualization. The evidence for clinical judgment is FAERS, drug labels, and the literature, and judgments are made by FlyVigilance’s deliberative layer (NVIDIA Nemotron), its reflex layer (paired with the non-autoregressive judgment model), and humans.
          We do not claim that a fly brain “understands” drug safety. A wiring diagram tells you where to send something, not what is right.
          </>)}
        </div>
      </Card>
    </div>
  )
}
