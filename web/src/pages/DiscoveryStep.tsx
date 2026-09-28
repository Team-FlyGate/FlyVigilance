import type { ReactNode } from 'react'
import HeroDocking, { DRUG_LABEL, useHeroDrug, type StepId } from '../components/HeroDocking'
import DockPlayground from '../components/DockPlayground'
import SelectivityMap from '../components/SelectivityMap'
import ValidationGate from '../components/ValidationGate'
import EvidenceCard from '../components/EvidenceCard'
import Step2Handoff from '../components/Step2Handoff'
import { Card, Loading, PageHead } from '../components/ui'
import { CriticStream, MissingCard, RedockBench, STEP_PAGES, Tile, title, useDiscoveryData } from './Discovery'

// STEP 1 FlyDiscovery 의 다섯 단계 페이지. 가운데 3D 장면(HeroDocking)은 그 단계에 고정되고,
// 위 단계 표시를 누르면 다른 단계 페이지로 갑니다. 왼쪽 위 초파리 커넥텀은 단계마다 다른 층을 자극합니다.

const HEAD: Record<StepId, { no: string; name: string; title: ReactNode; lede: ReactNode }> = {
  msa: { no: '01', name: 'MSA-Search', title: <>표적 서열의 <span style={{ color: 'var(--c-sense)' }}>진화적 이웃</span>을 모읍니다</>,
    lede: <>PARP1 촉매 도메인 서열로 상동 서열을 찾아 정렬합니다. 이 정렬이 다음 단계 OpenFold3 의 입력이 되며, NVIDIA 공식 스킬 <span className="mono">bionemo-msa-structure-prediction-pipeline</span> 이 제시하는 MSA-Search → OpenFold3 규격을 그대로 따랐습니다.</> },
  of3: { no: '02', name: 'OpenFold3', title: <>서열에서 <span style={{ color: 'var(--c-sense)' }}>단백질 구조</span>를 예측합니다</>,
    lede: <>MSA-Search 정렬을 입력으로 OpenFold3 NIM 이 PARP1 구조를 예측했습니다(니라파립도 함께 넣어 예측했고, 약물 자리는 다음 단계에서 봅니다). 리본 색은 잔기별 예측 신뢰도(pLDDT)이고, 드래그로 돌리고 휠로 확대, 오른쪽 드래그로 이동할 수 있습니다. 공개 결정 구조 4R6E 와 Kabsch 로 겹쳐 Cα RMSD 를 쟀습니다. OpenFold2 엔드포인트는 측정 당시 서버 오류로 실패해 OpenFold3 로 갔습니다.</> },
  dd: { no: '03', name: 'DiffDock', title: <>약물이 <span style={{ color: 'var(--jev)' }}>어느 자세로</span> 붙는지 도킹합니다</>,
    lede: <>DiffDock NIM 은 포즈 5개와 신뢰도를 돌려줍니다. 결정 구조에 원래 리간드를 다시 넣는 재도킹으로 1순위 포즈가 정답 자리에서 몇 Å 떨어졌는지 잽니다(기준 ≤ 2 Å). 위는 고른 PARP1 억제제(니라파립 · 탈라조파립 · 루카파립), 아래는 STEP 2 가 감시하는 FAERS 데모 케이스 약물들입니다.</> },
  bz: { no: '04', name: 'Boltz-2', title: <>붙는 세기를 예측하고 <span style={{ color: 'var(--jev)' }}>실측과 대조</span>합니다</>,
    lede: <>Boltz-2 NIM 이 예측한 pIC50 를 ChEMBL 실측 중앙값과 비교합니다. 활성 범위가 고루 퍼지도록 고른 PARP1 억제제 39종으로 벤치마크했습니다. 예측값은 측정된 친화도가 아니며, 이 둘을 섞는 주장은 크리틱이 반려합니다.</> },
  critic: { no: '05', name: '크리틱', title: <>숫자가 다 맞아도 <span style={{ color: 'var(--bad)' }}>결론이 근거를 넘으면</span> 반려합니다</>,
    lede: <>에이전트가 쓴 주장은 사람에게 가기 전에 세 번 걸러집니다. 1단 근거 ID, 2단 원본 로그와 숫자 대조는 모델 없이 규칙으로, 3단 추론 검사만 Nemotron 이 합니다. 가운데 장면은 결정 구조(흰 선 · 흰 윤곽)를 겹쳐 주장을 검증하는 모습입니다.</> },
}

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
      <text x={W / 2} y={H - 4} fill="var(--text-2)" fontSize={11} textAnchor="middle">ChEMBL 실측 pChEMBL</text>
      <text x={12} y={H / 2} fill="var(--text-2)" fontSize={11} textAnchor="middle" transform={`rotate(-90 12 ${H / 2})`}>Boltz-2 예측 pIC50</text>
    </svg>
  )
}

export default function DiscoveryStep({ step }: { step: StepId }) {
  const { m, hero, missing, extras, redockList, scenes, critic } = useDiscoveryData()
  const h = HEAD[step]
  const [drug] = useHeroDrug()
  const of3 = m?.openfold3_msa, bm = m?.parp1_affinity_benchmark, hm = hero?.metrics
  const combos = m?.diffdock_boltz2_chembl ?? []
  const combo = (k: string) => { const [l, t] = k.split('@'); return `${title(l)} @ ${({ parp1: 'PARP1', cox2: 'COX-2', xa: 'Factor Xa' } as Record<string, string>)[t] ?? t}` }

  return (
    <div className="page">
      <PageHead eyebrow={`Project-FlyGate · STEP 1 FlyDiscovery · ${h.no} ${h.name}`} title={h.title} lede={h.lede}
        right={<div className="row wrap" style={{ justifyContent: 'flex-end', maxWidth: 360 }}>
          <span className="chip jev">데모 후보 · {DRUG_LABEL[drug]} × PARP1</span>
          <span className={`chip ${step === 'critic' ? 'bad' : 'nv'}`}>{step === 'critic' ? 'Nemotron 3 Super · 규칙' : `NVIDIA BioNeMo NIM · ${h.name}`}</span>
        </div>} />

      {missing ? <MissingCard /> : !m || !hero || !extras ? <Loading /> : (
        <>
          <Card className="" style={{ marginBottom: 16 }}>
            <HeroDocking key={step} hero={hero} extras={extras} only={step} nav={STEP_PAGES} height={600} />
          </Card>

          {step === 'msa' && (
            <div className="grid g3" style={{ marginBottom: 16 }}>
              <Tile tech="MSA-Search NIM" name="상동 서열" color="#76b900" value={<>{of3?.msa_homologs}개</>} sub="PARP1 촉매 도메인 · 데이터베이스 Uniref30_2302" />
              <Tile tech="입력 규격" name="OpenFold3 로 전달" color="#76b900" value="a3m" sub={<>정렬 파일 <span className="mono">nim/parp1.a3m</span> 을 그대로 OpenFold3 입력으로 씁니다</>} />
              <Tile tech="NVIDIA 공식 스킬" name="파이프라인" color="#8a97bd" value="MSA → OF3" sub={<span className="mono">bionemo-msa-structure-prediction-pipeline</span>} />
            </div>
          )}

          {step === 'of3' && hm && (
            <div className="grid" style={{ gridTemplateColumns: 'repeat(5, minmax(0, 1fr))', gap: 12, marginBottom: 16 }}>
              <Tile tech="OpenFold3 NIM" name="pLDDT" color="#37e6ff" value={hm.plddt.toFixed(2)} sub="잔기별 예측 신뢰도 평균 · 기준 ≥ 90" />
              <Tile tech="OpenFold3 NIM" name="pTM · ipTM" color="#37e6ff" value={`${hm.ptm} · ${hm.iptm}`} sub="전체 접힘 · 단백질-리간드 접촉면 신뢰도" />
              <Tile tech="4R6E 대조" name="Cα RMSD" color="#3ddc97" value={`${hm.ca_rmsd_kabsch.toFixed(2)} Å`} sub={`Kabsch 정렬 · Cα ${hm.matched_ca}개 · 기준 ≤ 2 Å`} />
              <Tile tech="4R6E 대조" name="리간드 RMSD" color="#ffb547" value={`${hm.of3_ligand_rmsd} Å`} sub="함께 예측한 니라파립 vs 결정 구조" />
              <Tile tech="OpenFold2 NIM" name="대체 경로" color="#ff5d6c" value={m.openfold2.status === 'FAILED' ? `HTTP ${m.openfold2.http}` : m.openfold2.status}
                sub={`${m.openfold2.attempts}회 시도 · 서버 오류라 OpenFold3 로 갔습니다`} />
            </div>
          )}

          {step === 'dd' && (
            <>
              <div className="row between" style={{ margin: '4px 0 10px' }}>
                <h2 style={{ margin: 0 }}>다른 약물로도 재도킹 · <span className="dim" style={{ fontWeight: 400 }}>FAERS 데모 케이스 약물 {Math.max(0, redockList.length - 1)}종 + 니라파립</span></h2>
                <span className="mono dim" style={{ fontSize: 11 }}>결정 구조: RCSB PDB · 포즈: DiffDock NIM</span>
              </div>
              {scenes && <DockPlayground scenes={scenes.scenes} />}
              <ValidationGate />
              {scenes && <SelectivityMap scenes={scenes.scenes} />}
              <RedockBench list={redockList} pocketR={scenes?.pocket_radius_A} />
              <Card title="니라파립 케이스 스터디 · 도킹 조합 8개" sub="같은 표적 안에서만 순위를 매길 수 있습니다. 다른 표적끼리 Vina 점수를 비교하는 주장은 크리틱이 반려합니다" style={{ marginBottom: 16 }}>
                <div className="mono dim" style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr 1fr 1fr', gap: 12, fontSize: 10.5, padding: '6px 4px', textTransform: 'uppercase' }}>
                  <span>조합</span><span>Vina kcal/mol</span><span>DiffDock 신뢰도</span><span>재도킹 RMSD</span>
                </div>
                {combos.map((c) => (
                  <div key={c[0]} style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr 1fr 1fr', gap: 12, fontSize: 12.5, padding: '8px 4px', borderTop: '1px solid var(--line)' }}>
                    <b style={{ fontFamily: 'var(--font)' }}>{combo(c[0])}</b><span className="num">{c[1].toFixed(3)}</span><span className="num">{c[2].toFixed(2)}</span>
                    <span className="num dim">{c[0] === 'niraparib@parp1' ? <span style={{ color: 'var(--ok)' }}>{hm?.diffdock_rmsd} Å ✓</span> : '—'}</span>
                  </div>
                ))}
              </Card>
            </>
          )}

          {step === 'bz' && bm && (
            <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.1fr)', gap: 16, marginBottom: 16 }}>
              <Card title="PARP1 39종 · 예측 vs 실측" sub="점 색은 오차: 초록 ≤ 0.5 · 노랑 ≤ 1.0 · 빨강 > 1.0 log">
                <Scatter pairs={bm.pairs} />
              </Card>
              <div className="stack" style={{ gap: 12 }}>
                <div className="grid g3" style={{ gap: 12 }}>
                  <Tile tech="순위 상관" name="Spearman" color="#3ddc97" value={bm.spearman.toFixed(3)} sub={`Pearson ${bm.pearson}`} />
                  <Tile tech="오차" name="MAE" color="#ffb547" value={`${bm.mae} log`} sub={`RMSE ${bm.rmse} · 편향 ${bm.bias}`} />
                  <Tile tech="선별" name="상위 25% EF" color="#37e6ff" value={bm.ef_top25.toFixed(2)} sub={`${bm.hit}/${bm.k} · 민감도 ${bm.sens} / 특이도 ${bm.spec}`} />
                </div>
                <Card title="케이스 스터디 조합 · Boltz-2 vs ChEMBL">
                  {combos.map((c) => (
                    <div key={c[0]} style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr 1fr 1fr', gap: 12, fontSize: 12.5, padding: '7px 0', borderTop: '1px solid var(--line)' }}>
                      <b style={{ fontFamily: 'var(--font)' }}>{combo(c[0])}</b><span className="num">pIC50 {c[3].toFixed(2)}</span>
                      <span className="num dim">결합 확률 {c[4].toFixed(2)}</span><span className="num">{c[5] === null ? <span className="dim">실측 없음</span> : `실측 ${c[5]} (n=${c[6]})`}</span>
                    </div>
                  ))}
                </Card>
              </div>
            </div>
          )}

          {step === 'critic' && <EvidenceCard />}
          {step === 'critic' && critic && (
            <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)', gap: 16, marginBottom: 16 }}>
              <Card title="Critic Stream" sub={extras.critic ? `${extras.critic.model} · 과잉해석 ${extras.critic.caught}/${extras.critic.n_over} 반려 · 정상 ${extras.critic.passed}/${extras.critic.n_valid} 통과 · ${extras.critic.sec}초` : ''}
                right={<span className="chip bad">크리틱 3단</span>}>
                {extras.critic && <CriticStream rows={extras.critic.rows} />}
                <div style={{ marginTop: 12 }}><Step2Handoff drug={drug} /></div>
              </Card>
              <Card title="모델별 평가 · 주장 8건" sub="정답(과잉해석 4 · 정상 4)과 모델 판정을 나란히 봅니다">
                {Object.entries(critic).map(([k, v]) => (
                  <div key={k} className="stack" style={{ gap: 4, marginBottom: 12 }}>
                    <div className="row between"><b style={{ fontFamily: 'var(--font)' }}>{k.replace('nvidia/', '')}</b>
                      <span className="mono dim" style={{ fontSize: 11 }}>반려 {v.caught}/{v.n_over} · 통과 {v.passed}/{v.n_valid} · {v.sec}초</span></div>
                    {v.rows.map((r, i) => {
                      const right = r[2] === r[1]
                      return <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 64px 70px', gap: 8, fontSize: 11.5, padding: '4px 0', borderTop: '1px solid var(--line)' }}>
                        <span className="dim">{r[0]}</span><span className="mono" style={{ color: r[1] === 'PASS' ? 'var(--ok)' : 'var(--bad)' }}>{r[1]}</span>
                        <span className="mono" style={{ color: r[2] === 'NONE' ? 'var(--text-3)' : right ? 'var(--ok)' : 'var(--bad)' }}>{r[2] === 'NONE' ? '응답 잘림' : `${r[2]} ${right ? '✓' : '✗'}`}</span>
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
