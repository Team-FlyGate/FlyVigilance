import { useState, type ReactNode } from 'react'
import HeroDocking, { DRUG_LABEL, useHeroDrug, type StepId } from '../components/HeroDocking'
import DockPlayground from '../components/DockPlayground'
import Step2Handoff from '../components/Step2Handoff'
import { Card, Loading, PageHead } from '../components/ui'
import { CriticStream, MissingCard, RedockBench, STEP_PAGES, Tile, title, useDiscoveryData } from './Discovery'
import Term from '../components/Term'
import LiveRun from '../components/LiveRun'
import LiveScene from '../components/LiveScene'
import StepFlow from '../components/StepFlow'
import { t } from '../lib/i18n'
import { STEP_KIND, dataText, ligandName, liveFor, useDiscovery } from '../lib/discovery'

// STEP 1 FlyDiscovery 의 다섯 단계 페이지. 가운데 3D 장면(HeroDocking)은 그 단계에 고정되고,
// 위 단계 표시를 누르면 다른 단계 페이지로 갑니다. 왼쪽 위 초파리 커넥텀은 단계마다 다른 층을 자극합니다.

// 언어에 따라 문구가 바뀌므로 렌더할 때 만듭니다.
const head = (): Record<StepId, { no: string; name: string; title: ReactNode; lede: ReactNode }> => ({
  msa: { no: '01', name: 'MSA-Search', title: t(<>표적 서열의 <span style={{ color: 'var(--c-sense)' }}>진화적 이웃</span>을 모읍니다</>, <>Gathering the <span style={{ color: 'var(--c-sense)' }}>evolutionary neighbors</span> of the target sequence</>),
    lede: t(<><Term k="PARP1" /> 촉매 도메인 서열로 <Term k="MSA">상동 서열</Term>(진화적으로 닮은 서열)을 찾아 정렬(MSA)합니다. 이 정렬이 다음 단계 <Term k="OpenFold3" /> 의 입력이 되며, NVIDIA 공식 스킬 <span className="mono">bionemo-msa-structure-prediction-pipeline</span> 이 제시하는 MSA-Search → OpenFold3 규격을 그대로 따랐습니다.</>,
      <>Starting from the <Term k="PARP1" /> catalytic-domain sequence, we find <Term k="MSA">homologous sequences</Term> (sequences that are evolutionarily similar) and align them (MSA, multiple sequence alignment). This alignment feeds the next step, <Term k="OpenFold3" />, and follows the MSA-Search → OpenFold3 specification set out in the official NVIDIA skill <span className="mono">bionemo-msa-structure-prediction-pipeline</span>.</>) },
  of3: { no: '02', name: 'OpenFold3', title: t(<>서열에서 <span style={{ color: 'var(--c-sense)' }}>단백질 구조</span>를 예측합니다</>, <>Predicting the <span style={{ color: 'var(--c-sense)' }}>protein structure</span> from its sequence</>),
    lede: t(<>MSA-Search 정렬을 입력으로 OpenFold3 <Term k="NIM" /> 이 PARP1 구조를 예측했습니다(니라파립도 함께 넣어 예측했고, 약물 자리는 다음 단계에서 봅니다). 리본 색은 잔기별 예측 신뢰도(<Term k="pLDDT" />)이고, 드래그로 돌리고 휠로 확대, 오른쪽 드래그로 이동할 수 있습니다. 공개 <Term k="cocrystal">결정 구조</Term> <Term k="PDB">4R6E</Term> 와 <Term k="Kabsch">Kabsch</Term> 로 겹쳐 <Term k="CA">Cα</Term> <Term k="RMSD" />(결정 구조와의 거리)를 쟀습니다. OpenFold2 엔드포인트는 측정 당시 서버 오류로 실패해 OpenFold3 로 갔습니다.</>,
      <>Using the MSA-Search alignment as input, the OpenFold3 <Term k="NIM" /> (NVIDIA Inference Microservice) predicted the PARP1 structure (niraparib was included in the prediction; its binding site is examined in the next step). Ribbon color shows per-residue prediction confidence (<Term k="pLDDT" />, predicted local distance difference test). Drag to rotate, scroll to zoom, right-drag to pan. We superimposed the prediction on the public <Term k="cocrystal">crystal structure</Term> <Term k="PDB">4R6E</Term> with <Term k="Kabsch">Kabsch</Term> alignment and measured the <Term k="CA">Cα</Term> <Term k="RMSD" /> (root-mean-square deviation, the distance from the crystal structure). The OpenFold2 endpoint returned a server error at measurement time, so we used OpenFold3.</>) },
  dd: { no: '03', name: 'DiffDock', title: t(<>약물이 <span style={{ color: 'var(--jev)' }}>어느 자세로</span> 붙는지 도킹합니다</>, <>Docking to find <span style={{ color: 'var(--jev)' }}>the pose</span> in which a drug binds</>),
    lede: t(<><Term k="DiffDock" /> NIM 은 <Term k="pose">포즈</Term>(약물이 붙는 위치와 자세) 5개와 신뢰도를 돌려줍니다. 결정 구조에 원래 <Term k="ligand">리간드</Term>를 다시 넣는 <Term k="docking">재도킹</Term>으로 1순위 포즈가 정답 자리에서 몇 <Term k="angstrom">Å</Term> 떨어졌는지 잽니다(기준 ≤ 2 Å). 위는 고른 PARP1 억제제(니라파립 · 탈라조파립 · 루카파립), 아래는 STEP 2 가 감시하는 FAERS 데모 케이스 약물들입니다.</>,
      <>The <Term k="DiffDock" /> NIM returns five <Term k="pose">poses</Term> (where and in what orientation the drug binds) with confidence scores. In <Term k="docking">redocking</Term>, we put a crystal structure’s original <Term k="ligand">ligand</Term> back in and measure how many <Term k="angstrom">Å</Term> the top-ranked pose lands from the true position (criterion ≤ 2 Å). Above: selected PARP1 inhibitors (niraparib · talazoparib · rucaparib). Below: drugs from the FAERS (FDA Adverse Event Reporting System) demo cases monitored in STEP 2.</>) },
  bz: { no: '04', name: 'Boltz-2', title: t(<>붙는 세기를 예측하고 <span style={{ color: 'var(--jev)' }}>실측과 대조</span>합니다</>, <>Predicting binding strength and <span style={{ color: 'var(--jev)' }}>checking it against measurements</span></>),
    lede: t(<><Term k="Boltz2" /> NIM 이 예측한 <Term k="pIC50" />(억제 효력) 를 <Term k="ChEMBL" /> 실측 중앙값과 비교합니다. 활성 범위가 고루 퍼지도록 고른 PARP1 억제제 39종으로 벤치마크했습니다. 예측값은 측정된 친화도가 아니며, 이 둘을 섞는 주장은 크리틱이 반려합니다.</>,
      <>We compare the <Term k="pIC50" /> (inhibitory potency) predicted by the <Term k="Boltz2" /> NIM against the measured median in <Term k="ChEMBL" />. The benchmark uses 39 PARP1 inhibitors chosen to span the activity range evenly. A prediction is not a measured affinity, and the critic rejects any claim that conflates the two.</>) },
  critic: { no: '05', name: t('크리틱', 'Critic'), title: t(<>숫자가 다 맞아도 <span style={{ color: 'var(--bad)' }}>결론이 근거를 넘으면</span> 반려합니다</>, <>Even when every number is right, <span style={{ color: 'var(--bad)' }}>a conclusion that outruns the evidence</span> is rejected</>),
    lede: t(<>에이전트가 쓴 주장은 사람에게 가기 전에 세 번 걸러집니다. 1단 <Term k="evidenceId">근거 ID</Term>, 2단 원본 로그와 숫자 대조는 모델 없이 규칙으로, 3단 추론 검사만 <Term k="Nemotron" /> 이 합니다. 가운데 장면은 결정 구조(흰 선 · 흰 윤곽)를 겹쳐 주장을 검증하는 모습입니다.</>,
      <>Every claim the agent writes is filtered three times before it reaches a person. Tier 1 checks <Term k="evidenceId">evidence IDs</Term> and tier 2 checks numbers against the raw logs, both by rules without a model; only tier 3, the reasoning check, uses <Term k="Nemotron" />. The scene in the center overlays the crystal structure (white lines · white outline) to verify the claims.</>) },
})

function Scatter({ pairs }: { pairs: [number, number][] }) {
  const W = 420, H = 300, pad = 36, lo = 4.5, hi = 10
  const X = (v: number) => pad + ((v - lo) / (hi - lo)) * (W - pad - 12), Y = (v: number) => H - pad - ((v - lo) / (hi - lo)) * (H - pad - 12)
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
      <line x1={X(lo)} y1={Y(lo)} x2={X(hi)} y2={Y(hi)} stroke="rgba(120,170,255,0.25)" strokeDasharray="4 4" />
      {[5, 6, 7, 8, 9].map((v) => <g key={v}>
        <text x={X(v)} y={H - pad + 16} fill="var(--text-3)" fontSize={10} textAnchor="middle">{v}</text>
        <text x={pad - 8} y={Y(v) + 3} fill="var(--text-3)" fontSize={10} textAnchor="end">{v}</text>
      </g>)}
      {pairs.map(([c, p], i) => {
        const e = Math.abs(p - c), col = e <= 0.5 ? 'var(--ok)' : e <= 1 ? 'var(--warn)' : 'var(--bad)'
        return <circle key={i} cx={X(c)} cy={Y(p)} r={4.5} fill={col} opacity={0.85}><animate attributeName="r" from="0" to="4.5" dur="0.6s" begin={`${i * 0.03}s`} fill="freeze" /></circle>
      })}
      <text x={W / 2} y={H - 4} fill="var(--text-2)" fontSize={11} textAnchor="middle">{t('ChEMBL 실측 pChEMBL', 'ChEMBL measured pChEMBL')}</text>
      <text x={12} y={H / 2} fill="var(--text-2)" fontSize={11} textAnchor="middle" transform={`rotate(-90 12 ${H / 2})`}>{t('Boltz-2 예측 pIC50', 'Boltz-2 predicted pIC50')}</text>
    </svg>
  )
}

export default function DiscoveryStep({ step }: { step: StepId }) {
  const { m, hero, missing, extras, redockList, scenes, critic } = useDiscoveryData()
  const h = head()[step]
  const [drug] = useHeroDrug()
  const of3 = m?.openfold3_msa, bm = m?.parp1_affinity_benchmark, hm = hero?.metrics
  const combos = m?.diffdock_boltz2_chembl ?? []
  // 아래 라이브 실행 카드에서 이 단계를 새로 부르면 위 장면을 그 결과로 바꾸고, 칩으로 대표 장면에 되돌아갈 수 있게 합니다
  const store = useDiscovery()
  const kind = STEP_KIND[step]
  const env = kind ? liveFor(kind, store) : undefined
  const live = env && env.state === 'done' && env.result ? env : undefined
  // 이번 실행을 가리키는 값. 고른 표적 · 리간드를 함께 넣어, 캐시에서 나온 같은 응답이라도 선택이 바뀌면 다른 실행으로 봅니다
  const stamp = live ? [store.customTarget?.id ?? store.target, store.customLigand?.smiles ?? store.ligand,
    live.req_id ?? '', live.source ?? '', live.elapsed_s ?? ''].join('|') : ''
  // 라이브 결과가 있으면 그 결과를 보여 주는 것이 기본입니다. 사용자가 '대표 장면' 을 고른 그 응답에 한해서만 대표 장면을 둡니다.
  // 응답 객체로 비교하므로 다시 실행하면(캐시에서 같은 값이 와도 새 응답 객체입니다) 이번 실행 결과로 돌아옵니다.
  // (예전에는 효과와 ref 로 전환했는데, 값이 같으면 전환이 일어나지 않았습니다)
  const [heroFor, setHeroFor] = useState<unknown>(null)
  const view: 'hero' | 'live' = live && heroFor !== live ? 'live' : 'hero'
  const combo = (k: string) => { const [l, t] = k.split('@'); return `${title(l)} @ ${({ parp1: 'PARP1', cox2: 'COX-2', xa: 'Factor Xa' } as Record<string, string>)[t] ?? t}` }

  return (
    <div className="page">
      <PageHead eyebrow={`Project-FlyGate · STEP 1 FlyDiscovery · ${h.no} ${h.name}`} title={h.title} lede={h.lede}
        right={<div className="row wrap" style={{ justifyContent: 'flex-end', maxWidth: 360 }}>
          <span className="chip jev">{t('데모 후보', 'Demo candidate')} · {ligandName(drug, DRUG_LABEL[drug])} × PARP1</span>
          <span className={`chip ${step === 'critic' ? 'bad' : 'nv'}`}>{step === 'critic' ? t('Nemotron 3 Super · 규칙', 'Nemotron 3 Super · rules') : `NVIDIA BioNeMo NIM · ${h.name}`}</span>
        </div>} />

      {missing ? <MissingCard /> : !m || !hero || !extras ? <Loading /> : (
        <>
          <StepFlow step={step} />
          <Card className="" style={{ marginBottom: 16 }}>
            {live && (
              <div className="row" style={{ gap: 8, marginBottom: 10, alignItems: 'center' }}>
                <span className="mono dim" style={{ fontSize: 10.5, letterSpacing: 1.2 }}>{t('장면', 'Scene')}</span>
                <button className={`chip ${view === 'live' ? 'nv' : ''}`} style={{ cursor: 'pointer' }} onClick={() => setHeroFor(null)}>{t('이번 실행 결과', 'This run')}</button>
                <button className={`chip ${view === 'hero' ? 'jev' : ''}`} style={{ cursor: 'pointer' }} onClick={() => setHeroFor(live)}>{t('대표 장면', 'Reference scene')} · {ligandName(drug, DRUG_LABEL[drug])} × PARP1</button>
              </div>
            )}
            {/* 두 장면을 동시에 띄우지 않고 바꿔 끼웁니다(WebGL 컨텍스트 수를 늘리지 않게) */}
            {live && view === 'live'
              ? <LiveScene key={`${step}-${stamp}`} step={step} env={live} height={600} pred={store.runs.openfold3}
                  pocket={hero.msa ? { query_len: hero.msa.query_len, residues: hero.msa.pocket_residues } : undefined} />
              : <HeroDocking key={step} hero={hero} extras={extras} only={step} nav={STEP_PAGES} height={600} />}
          </Card>

          {/* 3D 장면과 아래 분석은 그대로 두고, 이 단계의 NIM 을 지금 다시 부르는 카드만 더합니다 */}
          <LiveRun step={step} drug={drug} />

          {step === 'msa' && (
            <div className="grid g3" style={{ marginBottom: 16 }}>
              <Tile tech="MSA-Search NIM" name={t('상동 서열', 'Homologous sequences')} color="#76b900" value={<>{of3?.msa_homologs}{t('개', '')}</>} sub={t('PARP1 촉매 도메인 · 데이터베이스 Uniref30_2302', 'PARP1 catalytic domain · database Uniref30_2302')} />
              <Tile tech={t('입력 규격', 'Input format')} name={t('OpenFold3 로 전달', 'Passed to OpenFold3')} color="#76b900" value="a3m" sub={t(<>정렬 파일 <span className="mono">nim/parp1.a3m</span> 을 그대로 OpenFold3 입력으로 씁니다</>, <>The alignment file <span className="mono">nim/parp1.a3m</span> is used as OpenFold3 input as is</>)} />
              <Tile tech={t('NVIDIA 공식 스킬', 'Official NVIDIA skill')} name={t('파이프라인', 'Pipeline')} color="#8a97bd" value="MSA → OF3" sub={<span className="mono">bionemo-msa-structure-prediction-pipeline</span>} />
            </div>
          )}

          {step === 'of3' && hm && (
            <div className="grid" style={{ gridTemplateColumns: 'repeat(5, minmax(0, 1fr))', gap: 12, marginBottom: 16 }}>
              <Tile tech="OpenFold3 NIM" name="pLDDT" color="#37e6ff" value={hm.plddt.toFixed(2)} sub={t('잔기별 예측 신뢰도 평균 · 기준 ≥ 90', 'Mean per-residue prediction confidence · criterion ≥ 90')} />
              <Tile tech="OpenFold3 NIM" name="pTM · ipTM" color="#37e6ff" value={`${hm.ptm} · ${hm.iptm}`} sub={t('전체 접힘 · 단백질-리간드 접촉면 신뢰도', 'Confidence in overall fold · protein–ligand interface')} />
              <Tile tech={t('4R6E 대조', 'vs 4R6E')} name="Cα RMSD" color="#3ddc97" value={`${hm.ca_rmsd_kabsch.toFixed(2)} Å`} sub={t(`Kabsch 정렬 · Cα ${hm.matched_ca}개 · 기준 ≤ 2 Å`, `Kabsch alignment · ${hm.matched_ca} Cα atoms · criterion ≤ 2 Å`)} />
              <Tile tech={t('4R6E 대조', 'vs 4R6E')} name={t('리간드 RMSD', 'Ligand RMSD')} color="#ffb547" value={`${hm.of3_ligand_rmsd} Å`} sub={t('함께 예측한 니라파립 vs 결정 구조', 'Co-predicted niraparib vs crystal structure')} />
              <Tile tech="OpenFold2 NIM" name={t('대체 경로', 'Fallback path')} color="#ff5d6c" value={m.openfold2.status === 'FAILED' ? `HTTP ${m.openfold2.http}` : m.openfold2.status}
                sub={t(`${m.openfold2.attempts}회 시도 · 서버 오류라 OpenFold3 로 갔습니다`, `${m.openfold2.attempts} attempts · server error, so we used OpenFold3`)} />
            </div>
          )}

          {step === 'dd' && (
            <>
              <div className="row between" style={{ margin: '4px 0 10px' }}>
                <h2 style={{ margin: 0 }}>{t('다른 약물로도 재도킹', 'Redocking other drugs too')} · <span className="dim" style={{ fontWeight: 400 }}>{t(`FAERS 데모 케이스 약물 ${Math.max(0, redockList.length - 1)}종 + 니라파립`, `${Math.max(0, redockList.length - 1)} FAERS demo-case drugs + niraparib`)}</span></h2>
                <span className="mono dim" style={{ fontSize: 11 }}>{t('결정 구조: RCSB PDB · 포즈: DiffDock NIM', 'Crystal structures: RCSB PDB · poses: DiffDock NIM')}</span>
              </div>
              {scenes && <DockPlayground scenes={scenes.scenes} />}
              <RedockBench list={redockList} pocketR={scenes?.pocket_radius_A} />
            </>
          )}

          {step === 'bz' && bm && (
            <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.1fr)', gap: 16, marginBottom: 16 }}>
              <Card title={t('PARP1 39종 · 예측 vs 실측', '39 PARP1 inhibitors · predicted vs measured')} sub={t('점 색은 오차: 초록 ≤ 0.5 · 노랑 ≤ 1.0 · 빨강 > 1.0 log', 'Dot color shows error: green ≤ 0.5 · yellow ≤ 1.0 · red > 1.0 log')}>
                <Scatter pairs={bm.pairs} />
              </Card>
              <div className="stack" style={{ gap: 12 }}>
                <div className="grid g3" style={{ gap: 12 }}>
                  <Tile tech={t('순위 상관', 'Rank correlation')} name="Spearman" color="#3ddc97" value={bm.spearman.toFixed(3)} sub={`Pearson ${bm.pearson}`} />
                  <Tile tech={t('오차', 'Error')} name="MAE" color="#ffb547" value={`${bm.mae} log`} sub={t(`RMSE ${bm.rmse} · 편향 ${bm.bias}`, `RMSE ${bm.rmse} · bias ${bm.bias}`)} />
                  <Tile tech={t('선별', 'Screening')} name={t('상위 25% EF', 'Top-25% EF (enrichment factor)')} color="#37e6ff" value={bm.ef_top25.toFixed(2)} sub={t(`${bm.hit}/${bm.k} · 민감도 ${bm.sens} / 특이도 ${bm.spec}`, `${bm.hit}/${bm.k} · sensitivity ${bm.sens} / specificity ${bm.spec}`)} />
                </div>
                <Card title={t('케이스 스터디 조합 · Boltz-2 vs ChEMBL', 'Case-study pairs · Boltz-2 vs ChEMBL')}>
                  {combos.map((c) => (
                    <div key={c[0]} style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr 1fr 1fr', gap: 12, fontSize: 12.5, padding: '7px 0', borderTop: '1px solid var(--line)' }}>
                      <b style={{ fontFamily: 'var(--font)' }}>{combo(c[0])}</b><span className="num">pIC50 {c[3].toFixed(2)}</span>
                      <span className="num dim">{t('결합 확률', 'Binding probability')} {c[4].toFixed(2)}</span><span className="num">{c[5] === null ? <span className="dim">{t('실측 없음', 'No measurement')}</span> : t(`실측 ${c[5]} (n=${c[6]})`, `Measured ${c[5]} (n=${c[6]})`)}</span>
                    </div>
                  ))}
                </Card>
              </div>
            </div>
          )}

          {step === 'critic' && (
            <a href="#/d-evidence" className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', textDecoration: 'none', color: 'inherit', padding: '14px 18px', marginBottom: 16, border: '1px solid rgba(61,220,151,0.35)' }}>
              <span><b style={{ fontFamily: 'var(--font)' }}>{t('다음 · 근거 검증', 'Next · evidence check')}</b> <span className="dim" style={{ fontSize: 13 }}>{t('도킹 결과를 믿어도 되는지 → 실측 근거가 있는지 → 선택적인지 → 후보 근거 카드', 'Can the docking result be trusted → is there measured evidence → is it selective → candidate evidence card')}</span></span>
              <span style={{ color: 'var(--ok)' }}>→</span>
            </a>
          )}
          {step === 'critic' && critic && (
            <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)', gap: 16, marginBottom: 16 }}>
              <Card title="Critic Stream" sub={extras.critic ? t(`${extras.critic.model} · 과잉해석 ${extras.critic.caught}/${extras.critic.n_over} 반려 · 정상 ${extras.critic.passed}/${extras.critic.n_valid} 통과 · ${extras.critic.sec}초`, `${extras.critic.model} · overclaims rejected ${extras.critic.caught}/${extras.critic.n_over} · valid claims passed ${extras.critic.passed}/${extras.critic.n_valid} · ${extras.critic.sec} s`) : ''}
                right={<span className="chip bad">{t('크리틱 3단', 'Three-tier critic')}</span>}>
                {extras.critic && <CriticStream rows={extras.critic.rows} />}
                <div style={{ marginTop: 12 }}><Step2Handoff drug={drug} /></div>
              </Card>
              <Card title={t('모델별 평가 · 주장 8건', 'Per-model evaluation · 8 claims')} sub={t('정답(과잉해석 4 · 정상 4)과 모델 판정을 나란히 봅니다', 'Ground truth (4 overclaims · 4 valid) side by side with each model’s verdict')}>
                {Object.entries(critic).map(([k, v]) => (
                  <div key={k} className="stack" style={{ gap: 4, marginBottom: 12 }}>
                    <div className="row between"><b style={{ fontFamily: 'var(--font)' }}>{k.replace('nvidia/', '')}</b>
                      <span className="mono dim" style={{ fontSize: 11 }}>{t(`반려 ${v.caught}/${v.n_over} · 통과 ${v.passed}/${v.n_valid} · ${v.sec}초`, `Rejected ${v.caught}/${v.n_over} · passed ${v.passed}/${v.n_valid} · ${v.sec} s`)}</span></div>
                    {v.rows.map((r, i) => {
                      const right = r[2] === r[1]
                      return <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 64px 70px', gap: 8, fontSize: 11.5, padding: '4px 0', borderTop: '1px solid var(--line)' }}>
                        <span className="dim">{dataText(r[0])}</span><span className="mono" style={{ color: r[1] === 'PASS' ? 'var(--ok)' : 'var(--bad)' }}>{r[1]}</span>
                        <span className="mono" style={{ color: r[2] === 'NONE' ? 'var(--text-3)' : right ? 'var(--ok)' : 'var(--bad)' }}>{r[2] === 'NONE' ? t('응답 잘림', 'Truncated') : `${r[2]} ${right ? '✓' : '✗'}`}</span>
                      </div>
                    })}
                  </div>
                ))}
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  )
}
