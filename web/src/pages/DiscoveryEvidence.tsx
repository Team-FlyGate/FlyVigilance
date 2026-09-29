import ValidationGate from '../components/ValidationGate'
import PoseRanking from '../components/PoseRanking'
import SelectivityMap from '../components/SelectivityMap'
import EvidenceCard from '../components/EvidenceCard'
import { Loading, PageHead } from '../components/ui'
import { MissingCard, useDiscoveryData } from './Discovery'
import { t } from '../lib/i18n'

// STEP 1 FlyDiscovery 06 근거 검증: 다섯 단계가 낸 결과를 STEP 2 로 넘기기 전에 순서대로 따집니다.
// 붙을 수 있나(도킹 검증 관문) → 실측 근거가 있나 · 선택적인가(선택성 근거 표) → 후보로 넘길까(후보 근거 카드)

// 언어에 따라 문구가 바뀌므로 렌더할 때 만듭니다.
const flow = () => [t('① 같은 자리로 다시 나오나', '① Does it land in the same place again?'), t('② 1순위 포즈를 믿어도 되나', '② Can the top-ranked pose be trusted?'), t('③ 실측 결합 근거가 있나 · 선택적인가', '③ Is there measured binding evidence? Is it selective?'), t('④ 무엇을 말해도 되나 → STEP 2', '④ What may be claimed → STEP 2')]

export default function DiscoveryEvidence() {
  const { scenes, missing } = useDiscoveryData()
  const FLOW = flow()
  return (
    <div className="page">
      <PageHead eyebrow={t('Project-FlyGate · STEP 1 FlyDiscovery · 06 근거 검증', 'Project-FlyGate · STEP 1 FlyDiscovery · 06 Evidence check')}
        title={t(<>계산 결과를 <span style={{ color: 'var(--ok)' }}>근거로 걸러</span> 후보를 넘깁니다</>, <>Candidates move on only after results are <span style={{ color: 'var(--ok)' }}>filtered by evidence</span></>)}
        lede={t(<>다섯 단계(MSA-Search → OpenFold3 → DiffDock → Boltz-2 → 크리틱)가 낸 결과를 그대로 믿지 않고, 도킹 결과의 재현성, ChEMBL 실측 결합 기록, 선택성 근거를 차례로 확인합니다.
          마지막 카드는 이 근거로 <b>말해도 되는 주장과 안 되는 주장</b>을 정해 STEP 2 FlyVigilance 로 넘깁니다.</>,
          <>Rather than trusting the output of the five steps (MSA-Search → OpenFold3 → DiffDock → Boltz-2 → critic) as is, we check in turn the reproducibility of the docking result, measured binding records in ChEMBL, and the evidence for selectivity.
          The final card uses this evidence to decide <b>which claims may and may not be made</b>, then hands the candidate to STEP 2 FlyVigilance.</>)}
        right={<div className="row wrap" style={{ justifyContent: 'flex-end', maxWidth: 360 }}>
          <span className="chip nv">{t('DiffDock NIM · 반복 검증', 'DiffDock NIM · repeated validation')}</span><span className="chip ok">{t('ChEMBL 실측', 'ChEMBL measured')}</span>
        </div>} />
      {missing ? <MissingCard /> : (
        <>
          <div className="row wrap" style={{ gap: 8, marginBottom: 14 }}>
            {FLOW.map((f, i) => <span key={f} className="row" style={{ gap: 8 }}><span className="chip">{f}</span>{i < FLOW.length - 1 && <span className="dim">→</span>}</span>)}
          </div>
          <ValidationGate />
          <PoseRanking />
          {scenes ? <SelectivityMap scenes={scenes.scenes} /> : <Loading />}
          <EvidenceCard />
        </>
      )}
    </div>
  )
}
