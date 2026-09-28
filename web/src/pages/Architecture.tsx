import { useEffect, useState, type ReactNode } from 'react'
import BrainView from '../components/BrainView'
import { Card, PageHead } from '../components/ui'
import { useBrain } from '../lib/brain'
import { LAYER_COLOR, fmt, getJSON } from '../lib/data'
import type { Bench, CriticProbe, LiteratureEval, Validation } from '../lib/types'
import Term from '../components/Term'
import { t } from '../lib/i18n'

const SUP: Record<string, string> = { '-': '⁻', '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹' }
// 아주 작은 p 값은 과학 표기로 보여 드립니다 (예: 3.6×10⁻⁴⁸)
function fmtP(p: number): string {
  if (!(p > 0)) return '0'
  if (p >= 0.01) return p.toFixed(2)
  if (p >= 0.001) return p.toFixed(4)
  const e = Math.floor(Math.log10(p))
  return `${(p / 10 ** e).toFixed(1)}×10${String(e).split('').map((c) => SUP[c] ?? c).join('')}`
}
const REFSETS = ['OMOP', 'EU-ADR', 'Harpaz']

interface Node { key: string; x: number; y: number; title: string; short: string; brain: string; agent: string; tech: { t: string; k?: 'nv' | 'jev' | ''; g?: string }[]; detail: ReactNode[] }
// 노드별 초파리 뇌 영역의 용어 풀이 키입니다
const BRAIN_TERM: Record<string, string> = { sense: 'antennal', encode: 'antennal', reflex: 'lateralHorn', memory: 'mushroom', deliberate: 'centralComplex', critic: 'GABA', action: 'descending', feedback: 'mushroom' }

// 언어에 따라 문구가 바뀌므로 렌더할 때 만듭니다.
const nodes = (): Node[] => [
  { key: 'sense', short: t('데이터 수용', 'Data intake'), x: 40, y: 190, title: 'Sensory Intake', brain: 'ORN · GRN · JO · VPN', agent: t('데이터 스트림 수용 스킬', 'Data stream intake skill'),
    tech: [{ t: 'FAERS ASCII', g: 'FAERS' }, { t: 'openFDA', g: 'openFDA' }, { t: 'PubMed', g: 'PubMed' }],
    detail: [t('FAERS 분기 zip 증분 적재 (etl_quarter 감사 테이블)', 'Incremental loading of quarterly FAERS (FDA Adverse Event Reporting System) zips (etl_quarter audit table)'), t('채널 = 감각 모달리티: 후각 FAERS, 미각 문헌, 기계감각 임상시험, 온습도 라벨 변경, 시각 디지털', 'Channel = sensory modality: smell for FAERS, taste for literature, mechanosensation for clinical trials, thermo-hygrosensation for label changes, vision for digital'), t('deny-by-default 허용 호스트만 호출', 'Deny-by-default: calls only allowed hosts')] },
  { key: 'encode', short: t('정규화 · 중복제거', 'Clean · dedupe'), x: 225, y: 190, title: 'Feature Encoding', brain: 'Antennal lobe PN', agent: t('정규화 · 중복제거 · 임베딩', 'Normalization · deduplication · embedding'),
    tech: [{ t: 'DuckDB', g: 'SQL' }, { t: 'nemotron-3-embed (planned)', k: 'nv' }],
    detail: [t(<><Term k="caseid">caseid</Term>(사례 번호) 최신 버전 + FDA 삭제 목록 반영</>, <>Latest version per <Term k="caseid">caseid</Term> (case number) + FDA deletion list applied</>), t('유효성분 우선, 염/수화물 접미사 제거, 상품명→성분 학습 매핑', 'Active ingredient first, salt/hydrate suffixes stripped, learned brand-name → ingredient mapping'), t(<><Term k="ICH4" /> <Term k="gate">규칙 게이트</Term> (모델 미사용)</>, <><Term k="ICH4" /> <Term k="gate">rule gate</Term> (no model)</>)] },
  { key: 'reflex', short: t('반사 판단', 'Reflex judgment'), x: 410, y: 60, title: 'Reflex Judgment', brain: 'Lateral horn', agent: t('FlyVigilance 반사 판단 · 비자기회귀 판단 모델', 'FlyVigilance reflex judgment · non-autoregressive judgment model'),
    tech: [{ t: t('비자기회귀 판단 모델', 'Non-autoregressive judgment model'), k: 'jev', g: 'NAR' }, { t: t('결정 정책 (규칙)', 'Decision policy (rules)'), g: 'policy' }],
    detail: [t(<>상태 1개 + 타입 질문 7개를 한 번에: noul(예/아니오 확률) · choice(선택지) · score(점수)</>, <>One state + 7 typed questions at once: noul (yes/no probability) · choice (options) · score</>), t(<><Term k="grounding">라벨 근거 주입</Term>: <Term k="expectedness">예측성</Term>은 openFDA 라벨 원문 조회로 정합니다</>, <><Term k="grounding">Label grounding</Term>: <Term k="expectedness">expectedness</Term> is set by looking up the openFDA label text</>), t(<><Term k="seriousness">중대성</Term>, 예측성, <Term k="WHOUMC" /> <Term k="causality">인과성</Term>, 특수상황, 우선순위, 다음 행동, 숙고 필요</>, <><Term k="seriousness">Seriousness</Term>, expectedness, <Term k="WHOUMC" /> <Term k="causality">causality</Term>, special situations, priority, next action, need for deliberation</>), t(<>규정 모드(US/KR)별 <Term k="expedited">신속보고</Term> 기한은 결정 정책이 붙입니다</>, <>The decision policy attaches <Term k="expedited">expedited reporting</Term> deadlines per regulatory mode (US/KR)</>), t(<>EMA <Term k="DME" /> 62개 <Term k="MedDRA">PT</Term>가 보고되면 점수와 관계없이 사람 검토로 보냅니다 (안전망)</>, <>If any of the 62 EMA <Term k="DME" /> <Term k="MedDRA">PTs</Term> is reported, the case goes to human review regardless of scores (safety net)</>)] },
  { key: 'memory', short: t('신호 기억', 'Signal memory'), x: 410, y: 320, title: 'Signal Memory', brain: 'Mushroom body KC · MBON · DAN', agent: t('불균형 분석 · 라벨 · 문헌 기억', 'Disproportionality · label · literature memory'),
    tech: [{ t: 'PRR · ROR · IC025', g: 'disproportionality' }, { t: 'DailyMed', g: 'openFDA' }],
    detail: [t(<><Term k="PRR" />·<Term k="ROR" /> <Term k="CI">95% CI</Term>, Yates <Term k="chi2">χ²</Term>, BCPNN <Term k="IC025" /> (SQL 계산, 모델 미개입)</>, <><Term k="PRR" />·<Term k="ROR" /> <Term k="CI">95% CI</Term>, Yates <Term k="chi2">χ²</Term>, BCPNN <Term k="IC025" /> (computed in SQL, no model involved)</>), t(<><Term k="pvclass">PV 분류</Term>(라벨 상태 × <Term k="SDR" />)와 근거 등급 A/B/C/L/D/U: 라벨 절 + <Term k="triple">3중 기준</Term> SDR (규칙)</>, <><Term k="pvclass">PV class</Term> (label status × <Term k="SDR" />) and evidence grade A/B/C/L/D/U: label section + <Term k="triple">triple-criterion</Term> SDR (rules)</>), t('문헌 읽기: PubMed 출판 유형(규칙) + 초록 설계·결론 판정(비자기회귀 판단 모델)', 'Literature reading: PubMed publication type (rules) + abstract design and conclusion judgment (non-autoregressive judgment model)'), t('SDR 기준의 참조 세트 성능을 근거 ID로 인용 (metric:)', 'Reference-set performance of the SDR criteria cited by evidence ID (metric:)')] },
  { key: 'deliberate', short: t('Nemotron 숙고', 'Nemotron System-2'), x: 610, y: 190, title: 'Deliberation', brain: 'Central complex EPG · PFL · FB', agent: t('NVIDIA Nemotron System-2 평가', 'NVIDIA Nemotron System-2 assessment'),
    tech: [{ t: 'Nemotron 3 Super', k: 'nv' }, { t: 'Ultra · Lightning', k: 'nv' }],
    detail: [t('승격된 케이스만: 중대+예상외, 우선순위 ≥ 2.5, 저신뢰, 신호 검토', 'Escalated cases only: serious + unexpected, priority ≥ 2.5, low confidence, signal review'), t(<>근거 묶음만 보고 <Term k="evidenceId">근거 ID</Term>가 붙은 주장 <Term k="JSON" /> 작성</>, <>Reads only the evidence bundle and writes claim <Term k="JSON" /> with <Term k="evidenceId">evidence IDs</Term></>), t(<>503(서버 과부하 오류)이면 Super → Ultra → Lightning <Term k="fallback">폴백</Term></>, <>On 503 (server overload), <Term k="fallback">falls back</Term> Super → Ultra → Lightning</>)] },
  { key: 'critic', short: t('3단 크리틱', '3-tier critic'), x: 800, y: 190, title: 'Inhibitory Critic', brain: 'GABAergic · APL', agent: t('3단 크리틱', '3-tier critic'),
    tech: [{ t: 'rules' }, { t: 'numeric oracle', g: 'oracle' }, { t: t('비자기회귀 판정', 'Non-autoregressive verdict'), k: 'jev', g: 'NAR' }, { t: 'Nemotron Safety Guard', k: 'nv', g: 'guard' }, { t: t('Content Safety · PV 정책', 'Content Safety · PV policy'), k: 'nv', g: 'guard' }],
    detail: [t(<>T1 근거 ID 실재 · T2 문장 속 숫자를 근거 수치와 대조(<Term k="oracle">숫자 오라클</Term>)</>, <>T1 evidence IDs exist · T2 numbers in sentences checked against the evidence values (<Term k="oracle">numeric oracle</Term>)</>), t(<>T3 <Term k="overclaim">과잉해석</Term> 규칙 13종 위반 확률 (비자기회귀 판단 모델 · 주장별 noul(예/아니오 확률) + 규칙 choice)</>, <>T3 probability of violating the 13 <Term k="overclaim">overclaim</Term> rules (non-autoregressive judgment model · per-claim noul (yes/no probability) + rule choice)</>), t('NVIDIA Nemotron Safety Guard 로 개별 치료 조언 차단 · 반려 시 1회 재작성', 'NVIDIA Nemotron Safety Guard blocks individual treatment advice · one rewrite when returned')] },
  { key: 'action', short: t('행동 · 사람 큐', 'Act · human queue'), x: 985, y: 190, title: 'Action Output', brain: 'Descending neurons', agent: t('행동: 신속보고 · 검토 · 모니터 · 종결', 'Actions: expedite · review · monitor · close'),
    tech: [{ t: 'human queue' }, { t: 'E2B(R3) draft', g: 'E2B' }],
    detail: [t('신속보고 후보는 15일 시계와 함께 사람 큐', 'Expedited-report candidates go to the human queue with a 15-day clock'), t('통과한 메모만 사람에게, 모든 판단은 감사 로그', 'Only memos that pass reach people; every judgment is audit-logged'), t('환자 개별 치료 조언은 가드레일로 차단', 'Individual patient treatment advice is blocked by guardrails')] },
  { key: 'feedback', short: t('검토 되먹임', 'Review feedback'), x: 800, y: 400, title: 'Reviewer Feedback', brain: 'Ascending neurons · DAN', agent: t('사람 검토 되먹임', 'Human review feedback'),
    tech: [{ t: 'threshold tuning' }],
    detail: [t('검토자 결정 = 도파민 신호: 라우팅 임계값과 우선순위 보정', 'Reviewer decision = dopamine signal: tunes routing thresholds and priorities'), t(<>판단 모델 확률의 보정 곡선을 실측 라벨로 추적 (<Term k="ECE" />)</>, <>Tracks the calibration curve of judgment-model probabilities against real labels (<Term k="ECE" />)</>), t('규칙 추가는 사람 승인 후에만', 'New rules only after human approval')] },
]

const EDGES: [string, string][] = [
  ['sense', 'encode'], ['encode', 'reflex'], ['encode', 'memory'], ['reflex', 'deliberate'], ['memory', 'deliberate'],
  ['reflex', 'action'], ['deliberate', 'critic'], ['critic', 'action'], ['critic', 'deliberate'], ['action', 'feedback'], ['feedback', 'memory'], ['feedback', 'reflex'],
]
const W = 172, H = 104

// embedded: 개요 화면 맨 위에 넣을 때는 머리말과 아래 설명 카드 없이 층 애니메이션과 커넥텀만 보여 줍니다
export default function Architecture({ embedded = false }: { embedded?: boolean } = {}) {
  const [sel, setSel] = useState('reflex')
  const [bench, setBench] = useState<Bench | null>(null)
  const [val, setVal] = useState<Validation | null>(null)
  const [lit, setLit] = useState<LiteratureEval | null>(null)
  const [probe, setProbe] = useState<CriticProbe | null>(null)
  const { conn, sim } = useBrain()
  useEffect(() => {
    getJSON<Bench>('/data/bench.json').then(setBench).catch(() => null)
    getJSON<Validation>('/data/validation.json').then(setVal).catch(() => null)
    getJSON<LiteratureEval>('/data/literature_eval.json').then(setLit).catch(() => null)
    getJSON<CriticProbe>('/data/critic_probe.json').then(setProbe).catch(() => null)
  }, [])
  const NODES = nodes()
  const node = NODES.find((n) => n.key === sel)!
  const layer = conn?.meta.layers.find((l) => l.key === sel)

  // 실측 수치는 JSON 에서 읽습니다. 비교 실험은 모든 조건의 입력에서 결과 코드를 가린 측정(ablation_blind)을 먼저 씁니다
  const ab = bench?.ablation_blind ?? bench?.ablation
  const cond = bench?.ablation_blind ? t('결과 코드 가림', 'outcome codes hidden') : t('결과 코드 공개', 'outcome codes visible')
  const fv = ab?.flyvigilance, base = ab?.raw_jev, g = ab?.grounding
  const serious = ab ? ab.serious ?? Math.round(ab.n * (bench?.dataset.serious_rate ?? 0)) : 0
  const diff = g ? g.memory_vs_label.memory_expected_label_not + g.memory_vs_label.memory_unexpected_label_listed : 0
  const pOf = (k: string) => { const tt = ab?.tests?.[k]; return tt ? ` (p = ${fmtP(tt.p)})` : '' }
  const followUp = fv?.routes?.follow_up ?? ab?.routes.flyvigilance?.follow_up
  // 참조 세트: 지식 기반 판별(약·반응 이름 사용)의 AUC 와 가장 좋은 불균형 통계의 AUC
  const modes = val ? REFSETS.map((r) => {
    const ms = val.refsets[r]?.methods ?? []
    return { r, named: ms.find((m) => m.key === 'raw_named')?.auc, stat: Math.max(...ms.filter((m) => m.family === 'metric').map((m) => m.auc)) }
  }) : []
  const modesOk = modes.length > 0 && modes.every((m) => m.named !== undefined && Number.isFinite(m.stat))
  // 전향 검증: 2013년 라벨 변경 전 보고만으로 3중 기준 SDR 을 계산한 결과입니다
  const pro = val?.refsets['Harpaz-prospective']?.points.triple
  const planted = probe ? Object.entries(probe.summary).filter(([k]) => k !== 'ctrl') : []
  const ctrl = probe?.summary.ctrl
  const LAYERS: [string, string, ReactNode, ReactNode][] = [
    ['1', t('규칙이 먼저', 'Rules first'), t(<><Term k="ICH4" />, 중대성 <Term k="outcome">결과 코드</Term>, <Term k="role">역할 코드</Term>처럼 규칙으로 되는 일은 모델에 묻지 않습니다</>, <>Anything rules can decide, such as <Term k="ICH4" />, seriousness <Term k="outcome">outcome codes</Term> and <Term k="role">role codes</Term>, is never asked of a model</>),
      ab && followUp !== undefined ? t(`${ab.n}건 중 최소 요소가 빠진 ${followUp}건은 규칙으로 추가정보 요청에 보냈습니다`, `Of ${ab.n} cases, the ${followUp} missing minimum elements were sent to a follow-up request by rule`) : '…'],
    ['2', t('라벨 원문 조회', 'Label text lookup'), t(<><Term k="label">라벨</Term>(허가사항) 기재 여부를 openFDA 라벨 절 검색으로 정해 상태에 넣습니다</>, <>Whether a reaction is on the <Term k="label">label</Term> is set by an openFDA label-section search and put into the state</>),
      g ? t(`라벨을 찾은 ${g.label_found}건 중 ${diff}건(${fmt.pct(diff / Math.max(1, g.label_found), 0)})에서 모델 추정 대신 라벨 원문 값을 썼습니다`, `Of ${g.label_found} cases with a label found, ${diff} (${fmt.pct(diff / Math.max(1, g.label_found), 0)}) used the label text instead of the model's guess`) : '…'],
    ['3', t('규제 용어로 쪼갠 질문', 'Questions split into regulatory terms'), t(<>질문 하나 대신 <Term k="ICH">ICH E2A</Term>·<Term k="WHOUMC" />·<Term k="kralgo">한국형 알고리즘</Term> 항목을 타입 있는 7~9문항으로 한 번에 묻습니다</>, <>Instead of one question, the <Term k="ICH">ICH E2A</Term>, <Term k="WHOUMC" /> and <Term k="kralgo">Korean algorithm</Term> items are asked at once as 7–9 typed questions</>),
      fv && base ? t(<>FlyVigilance vs 모델 단독 · 질문 하나 ({cond}): 사람 우선 {fv.escalated} vs {base.escalated}건{pOf('workload_fv_vs_raw')}, 사람에게 바로 간 비중대 {fv.over_escalated} vs {base.over_escalated}건{pOf('over_escalation_fv_vs_raw')}</>, <>FlyVigilance vs model alone with one question ({cond}): human-first {fv.escalated} vs {base.escalated}{pOf('workload_fv_vs_raw')}; non-serious sent straight to people {fv.over_escalated} vs {base.over_escalated}{pOf('over_escalation_fv_vs_raw')}</>) : '…'],
    ['4', t('결정 정책과 규정 모드', 'Decision policy and regulatory modes'), t(<>확률을 행동으로 바꾸는 규칙표입니다. 미국·한국 <Term k="expedited">신속보고</Term> 기준과 기한, 저신뢰 상향, <Term k="DME" /> 안전망을 담습니다</>, <>A rule table that turns probabilities into actions. It holds US and Korean <Term k="expedited">expedited reporting</Term> criteria and deadlines, low-confidence escalation and the <Term k="DME" /> safety net</>),
      fv && base ? t(`자동 큐(종결·모니터링)에 남은 중대 사례 ${fv.serious_without_review}건 vs 모델 단독 ${base.serious_without_review}건 / ${serious}건${pOf('serious_unreviewed_fv_vs_raw')} · ${cond}`, `Serious cases left in the automatic queues (close, monitor): ${fv.serious_without_review} vs ${base.serious_without_review} for the model alone, of ${serious}${pOf('serious_unreviewed_fv_vs_raw')} · ${cond}`) : '…'],
    ['5', t('통계는 SQL', 'Statistics in SQL'), t(<>불균형 순위와 <Term k="SDR" /> 판정은 <Term k="PRR" />·<Term k="ROR" />·<Term k="IC025" /> <Term k="SQL">SQL</Term>이 정하고, 모델은 숫자를 바꾸지 않습니다</>, <>Disproportionality ranking and <Term k="SDR" /> calls are set by <Term k="PRR" />·<Term k="ROR" />·<Term k="IC025" /> <Term k="SQL">SQL</Term>; the model never changes the numbers</>),
      pro ? t(<><Term k="prospective">전향 검증</Term>(Harpaz): 2013년 이전 보고만으로 3중 기준 SDR이 2013년 라벨 변경 {pro.tp}/{pro.tp + pro.fn}건을 먼저 잡았고, 오경보는 {pro.fp}/{pro.fp + pro.tn}건입니다 (<Term k="PPV" /> {fmt.f(pro.ppv ?? 0)})</>, <><Term k="prospective">Prospective validation</Term> (Harpaz): using only reports before 2013, the triple-criterion SDR caught {pro.tp}/{pro.tp + pro.fn} of the 2013 label changes ahead of time, with {pro.fp}/{pro.fp + pro.tn} false alarms (<Term k="PPV" /> {fmt.f(pro.ppv ?? 0)})</>) : '…'],
    ['6', t('두 판별 모드', 'Two discrimination modes'), t(<>약·반응 이름을 쓰는 <Term k="kbmode">지식 기반 판별</Term>과, 이름을 가리고 보고 통계만 보는 통계 기반 판별을 따로 측정합니다</>, <><Term k="kbmode">Knowledge-based discrimination</Term>, which uses drug and reaction names, and statistics-based discrimination, which hides the names and sees only report statistics, are measured separately</>),
      modesOk ? t(<>지식 기반 판별 <Term k="AUC" /> {modes.map((m) => `${m.r} ${fmt.f(m.named ?? 0, 3)}`).join(' · ')} (가장 좋은 통계 {modes.map((m) => fmt.f(m.stat, 3)).join(' · ')})</>, <>Knowledge-based <Term k="AUC" /> {modes.map((m) => `${m.r} ${fmt.f(m.named ?? 0, 3)}`).join(' · ')} (best statistic {modes.map((m) => fmt.f(m.stat, 3)).join(' · ')})</>) : '…'],
    ['7', t('근거 ID와 3단 크리틱', 'Evidence IDs and the 3-tier critic'), t(<>모든 주장은 카탈로그의 <Term k="evidenceId">근거 ID</Term>만 인용하고, 숫자는 대조되며, <Term k="overclaim">과잉해석</Term> 13규칙과 NVIDIA Nemotron <Term k="guard">Safety Guard</Term>를 통과해야 합니다</>, <>Every claim cites only <Term k="evidenceId">evidence IDs</Term> from the catalog, its numbers are checked, and it must pass the 13 <Term k="overclaim">overclaim</Term> rules and NVIDIA Nemotron <Term k="guard">Safety Guard</Term></>),
      probe && ctrl ? t(`실제 사례 ${probe.n_cases}건에 넣은 틀린 주장 ${planted.reduce((a, [, s]) => a + s.correct, 0)}/${planted.reduce((a, [, s]) => a + s.n, 0)} 적발, 정상 대조군 ${ctrl.correct}/${ctrl.n} 통과`, `Wrong claims planted in ${probe.n_cases} real cases: ${planted.reduce((a, [, s]) => a + s.correct, 0)}/${planted.reduce((a, [, s]) => a + s.n, 0)} caught; valid controls ${ctrl.correct}/${ctrl.n} passed`) : '…'],
    ['8', t('PV 분류와 문헌 읽기', 'PV class and literature reading'), t(<>라벨 상태 × 3중 기준 SDR로 <Term k="pvclass">PV 분류</Term>와 등급을 매기고, 문헌은 출판 유형 규칙 + 비자기회귀 판단 모델의 <Term k="design">설계</Term> 판정으로 읽습니다</>, <>Label status × triple-criterion SDR sets the <Term k="pvclass">PV class</Term> and grade; literature is read with publication-type rules + the non-autoregressive judgment model's <Term k="design">study design</Term> judgment</>),
      lit ? t(<>설계 판정이 <Term k="PubMed">MEDLINE</Term> 색인과 {fmt.pct(lit.accuracy, 1)} 일치 ({fmt.int(lit.n)}편)</>, <>Design judgments agree with <Term k="PubMed">MEDLINE</Term> indexing {fmt.pct(lit.accuracy, 1)} of the time ({fmt.int(lit.n)} papers)</>) : '…'],
  ]
  useEffect(() => { sim?.stimulate('layer', sel, 1.1, 10) }, [sel, sim])

  const pos = (k: string) => { const n = NODES.find((x) => x.key === k)!; return { cx: n.x + W / 2, cy: n.y + H / 2 } }
  const isBack = (a: string, b: string) => pos(b).cx < pos(a).cx || (a === 'critic' && b === 'deliberate')
  const path = (a: string, b: string) => {
    const p = pos(a), q = pos(b)
    if (a === 'critic' && b === 'deliberate') return `M${p.cx},${p.cy - H / 2} C${p.cx},${p.cy - H / 2 - 60} ${q.cx},${q.cy - H / 2 - 60} ${q.cx},${q.cy - H / 2}`
    if (a === 'action' && b === 'feedback') return `M${p.cx},${p.cy + H / 2} C${p.cx},${q.cy} ${q.cx + W / 2 + 40},${q.cy} ${q.cx + W / 2},${q.cy}`
    if (isBack(a, b)) { const my = Math.max(p.cy, q.cy) + 70; return `M${p.cx - W / 2},${p.cy} C${p.cx - W},${my} ${q.cx + W / 2 + 20},${my} ${q.cx + W / 2},${q.cy + (q.cy > p.cy ? -20 : 20)}` }
    const x1 = p.cx + W / 2, x2 = q.cx - W / 2
    return `M${x1},${p.cy} C${(x1 + x2) / 2},${p.cy} ${(x1 + x2) / 2},${q.cy} ${x2},${q.cy}`
  }

  const live = (
      <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1.65fr) minmax(340px, 1fr)', alignItems: 'start' }}>
        <Card className="flush">
          <svg viewBox="0 0 1180 560" style={{ width: '100%', display: 'block' }}>
            <defs>
              <filter id="glow"><feGaussianBlur stdDeviation="3" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
              <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="rgba(120,170,255,0.05)" /></pattern>
            </defs>
            <rect width="1180" height="560" fill="url(#grid)" />
            <rect x="20" y="30" width="1150" height="500" rx="18" fill="none" stroke="rgba(120,170,255,0.18)" strokeDasharray="6 6" />
            <text x="36" y="22" fill="var(--text-3)" fontSize="10.5">OPENSHELL-STYLE POLICY BOUNDARY · deny-by-default egress: integrate.api.nvidia.com · api.typesafe.ai · api.fda.gov · eutils.ncbi.nlm.nih.gov</text>
            {EDGES.map(([a, b], i) => {
              const d = path(a, b)
              const c = LAYER_COLOR[a]
              return (
                <g key={i}>
                  <path d={d} fill="none" stroke={c} strokeOpacity={isBack(a, b) ? 0.22 : 0.4} strokeWidth={isBack(a, b) ? 1.1 : 1.8} strokeDasharray={isBack(a, b) ? '4 5' : undefined} />
                  {[0, 1, 2].map((k) => (
                    <circle key={k} r={3} fill={c} filter="url(#glow)">
                      <animateMotion dur={`${2.4 + (i % 3) * 0.4}s`} begin={`${k * 0.8 + i * 0.13}s`} repeatCount="indefinite" path={d} />
                    </circle>
                  ))}
                </g>
              )
            })}
            {NODES.map((n) => {
              const c = LAYER_COLOR[n.key]
              const on = n.key === sel
              return (
                <g key={n.key} transform={`translate(${n.x},${n.y})`} style={{ cursor: 'pointer' }} onClick={() => setSel(n.key)}>
                  <rect width={W} height={H} rx={14} fill={on ? 'rgba(14,22,42,0.98)' : 'rgba(10,16,30,0.92)'} stroke={c} strokeOpacity={on ? 1 : 0.5} strokeWidth={on ? 2 : 1}
                    style={{ filter: on ? `drop-shadow(0 0 14px ${c})` : undefined }} />
                  <rect x={0} y={0} width={4} height={H} rx={2} fill={c} />
                  <text x={16} y={24} fill={c} fontSize={10.5} letterSpacing={1.2}>{n.title.toUpperCase()}</text>
                  <text x={16} y={50} fill="var(--text)" fontSize={16} fontWeight={600} style={{ fontFamily: 'var(--font-kr)' }}>{n.short}</text>
                  <text x={16} y={71} fill="var(--text-3)" fontSize={10.5}>{n.brain.length > 24 ? n.brain.slice(0, 23) + '…' : n.brain}</text>
                  <text x={16} y={92} fill="var(--text-2)" fontSize={11}>{conn ? `${fmt.int(conn.meta.layers.find((l) => l.key === n.key)?.neurons ?? 0)} neurons` : ''}</text>
                </g>
              )
            })}
          </svg>
        </Card>

        <div className="stack" style={{ gap: 16 }}>
          <Card className="flush" style={{ height: 340 }}>
            <BrainView height={340} highlight={sel} view="front" bloom={1.2} autoRotate />
          </Card>
          <Card title={<><span style={{ color: LAYER_COLOR[sel] }}>{node.title}</span> · {node.agent}</>} sub={<><Term k={BRAIN_TERM[sel]}>{node.brain}</Term> — {layer ? fmt.int(layer.neurons) : '…'} neurons in MaleCNS subgraph</>}>
            <div className="row wrap" style={{ gap: 6, marginBottom: 12 }}>{node.tech.map((tc) => <span key={tc.t} className={`chip ${tc.k ?? ''}`}>{tc.g ? <Term k={tc.g}>{tc.t}</Term> : tc.t}</span>)}</div>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, lineHeight: 1.8, color: 'var(--text-2)' }}>{node.detail.map((d, i) => <li key={i}>{d}</li>)}</ul>
          </Card>
        </div>
      </div>
  )
  if (embedded) return live

  return (
    <div className="page">
      <PageHead eyebrow="Architecture · connectome-routed agent"
        title={t(<>뇌의 층이 곧 에이전트의 층: <span style={{ color: 'var(--c-sense)' }}>감각 → 반사 → 기억 → 숙고 → 억제 → 행동</span></>, <>The brain's layers are the agent's layers: <span style={{ color: 'var(--c-sense)' }}>sense → reflex → memory → deliberation → inhibition → action</span></>)}
        lede={t(<><Term k="MaleCNS" ko /> 중앙뇌 49,244개 뉴런을 해부학 분류로 9개 기능 층에 배정하고, 같은 9개 층으로 에이전트를 짰습니다. 각 층은 실제로 구현한 스킬, 모델, 계산으로 채웠습니다. 노드를 누르면 해당 뉴런 집단이 오른쪽 <Term k="connectome">커넥텀</Term>(뉴런 연결 배선도)에서 켜집니다.</>, <>The 49,244 central-brain neurons of <Term k="MaleCNS" ko /> are assigned to 9 functional layers by anatomical class, and the agent is built on the same 9 layers. Each layer is filled with skills, models and computations that are actually implemented. Click a node to light up its neuron population in the <Term k="connectome">connectome</Term> (the wiring diagram of neurons) on the right.</>)} />

      {live}

      <Card title={<>{t('NVIDIA 스킬 기반 워크플로의 여덟 층 · 비자기회귀 판단 모델 병용', 'Eight layers of the NVIDIA Skills workflow · paired with a non-autoregressive judgment model')} <span className="chip nv" style={{ marginLeft: 8 }}>build.nvidia.com NIM · Agent Skills · NemoClaw/OpenShell/OpenClaw</span></>}
        sub={t('FlyVigilance는 NVIDIA 스킬 위에 짠 약물감시 워크플로입니다. 글을 써야 하는 일은 NVIDIA Nemotron이, 타입 있는 확률 판단은 비자기회귀 판단 모델(Jev, TypeSafe AI)이 맡습니다. 무엇을, 어떤 근거로, 어떤 형식으로 묻고 답을 어디에 쓸지는 아래 여덟 층이 정합니다. 각 층의 효과는 실측했습니다', 'FlyVigilance is an agentic pharmacovigilance workflow built on NVIDIA Skills, pairing NVIDIA Nemotron with a non-autoregressive judgment model. Nemotron handles work that requires writing; the judgment model (Jev, TypeSafe AI) handles typed probability judgments. The eight layers below decide what to ask, on what evidence, in what format, and where the answers go. The effect of each layer was measured.')}
        style={{ marginTop: 16 }}>
        <div className="grid g4" style={{ gap: 12 }}>
          {LAYERS.map(([n, ttl, d, e]) => (
            <div key={n} style={{ padding: 14, borderRadius: 14, border: '1px solid var(--line-2)', background: 'rgba(10,16,30,0.5)' }}>
              <div className="row" style={{ gap: 8 }}><span style={{ fontFamily: 'var(--font)', fontSize: 20, fontWeight: 700, color: 'var(--c-sense)' }}>{n}</span><b>{ttl}</b></div>
              <div style={{ fontSize: 12, color: 'var(--text-2)', margin: '6px 0 8px', lineHeight: 1.55 }}>{d}</div>
              <div className="chip ok" style={{ whiteSpace: 'normal', lineHeight: 1.4, fontSize: 10.5 }}>{e}</div>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid g4" style={{ marginTop: 16 }}>
        {[
          { h: 'Data plane', c: 'var(--c-sense)', items: ['FAERS 2012Q4–2026Q2 ASCII', t('DuckDB 계층: raw → core → ref → sig → ops', 'DuckDB layers: raw → core → ref → sig → ops'), 'openFDA label · PubMed E-utilities', 'MaleCNS v1.0 flat connectome'] },
          { h: 'Model plane', c: 'var(--nvidia)', items: [t('NVIDIA Nemotron 3 Super / Ultra / 3.5 Lightning (NIM): 생성 · System-2 평가 메모 · 국내 서식 구조화', 'NVIDIA Nemotron 3 Super / Ultra / 3.5 Lightning (NIM, NVIDIA Inference Microservice): generation · System-2 assessment memos · structuring Korean forms'), t('NVIDIA Nemotron Safety Guard 8B v3: 주장별 안전 판정 (가드레일)', 'NVIDIA Nemotron Safety Guard 8B v3: per-claim safety verdicts (guardrail)'), t('비자기회귀 판단 모델 Jev (TypeSafe AI) 병용: 반사 판단 · 과잉해석 판정 · 문헌 설계 판정', 'Paired non-autoregressive judgment model Jev (TypeSafe AI): reflex judgment · overclaim verdicts · literature design judgments'), t('nemotron-3-embed (의미 검색, 계획)', 'nemotron-3-embed (semantic search, planned)')] },
          { h: 'Control plane', c: 'var(--c-encode)', items: [t('결정론적 라우팅 정책 · 규정 모드 US/KR · DME 안전망', 'Deterministic routing policy · regulatory modes US/KR · DME safety net'), t('3단 크리틱(13규칙) + 1회 재작성 루프', '3-tier critic (13 rules) + one-rewrite loop'), t('참조 세트 검증 (OMOP·EU-ADR·Harpaz, 전향 포함)', 'Reference-set validation (OMOP · EU-ADR · Harpaz, incl. prospective)'), t('NVIDIA Agent Skills (SKILL.md) 패키징 · 오프라인 테스트', 'NVIDIA Agent Skills (SKILL.md) packaging · offline tests')] },
          { h: 'Connectome plane', c: 'var(--c-memory)', items: ['49,244 neurons · 1.05M signed edges', t('NT(신경전달물질) 부호: ACh(아세틸콜린) +, GABA/Glu(글루탐산) −', 'NT (neurotransmitter) sign: ACh (acetylcholine) +, GABA/Glu (glutamate) −'), t('브라우저 실시간 발화율 모델 30 Hz', 'Real-time firing-rate model in the browser, 30 Hz'), t('ROI(뇌 영역) 90개 메시 · 스켈레톤 점구름 44만', '90 ROI (brain region) meshes · 440K-point skeleton cloud')] },
        ].map((p) => (
          <Card key={p.h} title={<span style={{ color: p.c }}>{p.h}</span>}>
            <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12.5, lineHeight: 1.8, color: 'var(--text-2)' }}>{p.items.map((i) => <li key={i}>{i}</li>)}</ul>
          </Card>
        ))}
      </div>
    </div>
  )
}
