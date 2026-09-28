import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Card, Loading, PageHead } from '../components/ui'
import { getJSON } from '../lib/data'
import type { DiscoveryMeasurements, DockEval } from '../lib/types'

// STEP 1 FlyDiscovery: 팀원이 만든 독립 화면(fly_discovery/web)을 /discovery/ 에서 그대로 띄우고,
// 위에 이 단계가 하는 일과 핵심 실측치를 짧게 붙입니다. 파일은 scripts/sync-discovery.mjs 가 복사합니다.

const PAGE = '/discovery/index.html'

function Tile({ tech, name, value, sub, color }: { tech: string; name: string; value: ReactNode; sub: ReactNode; color: string }) {
  return (
    <div className="card" style={{ padding: '12px 14px', boxShadow: `var(--shadow), inset 3px 0 0 ${color}` }}>
      <div className="row between" style={{ gap: 6 }}>
        <b style={{ fontFamily: 'var(--font)', fontSize: 14 }}>{name}</b>
        <span className="mono" style={{ fontSize: 9.5, letterSpacing: 0.6, color, textTransform: 'uppercase', whiteSpace: 'nowrap' }}>{tech}</span>
      </div>
      <div className="num" style={{ fontSize: 21, fontWeight: 600, margin: '6px 0 2px' }}>{value}</div>
      <div style={{ fontSize: 11.5, color: 'var(--text-2)', lineHeight: 1.45 }}>{sub}</div>
    </div>
  )
}

// 같은 출처의 iframe 이라 문서 높이를 읽어 iframe 높이를 맞춥니다. 대시보드 스크롤 하나로 끝까지 볼 수 있습니다
function AutoFrame({ src }: { src: string }) {
  const ref = useRef<HTMLIFrameElement>(null)
  const [h, setH] = useState(1900)
  useEffect(() => {
    const f = ref.current
    if (!f) return
    let ro: ResizeObserver | null = null
    const onLoad = () => {
      try {
        const doc = f.contentDocument
        if (!doc?.body) return
        const fit = () => setH((old) => {
          const next = Math.min(8000, Math.max(900, doc.documentElement.scrollHeight))
          return Math.abs(next - old) > 2 ? next : old
        })
        fit()
        ro?.disconnect()
        ro = new ResizeObserver(fit)
        ro.observe(doc.body)
      } catch { /* 다른 출처로 옮겨 가면 기본 높이를 씁니다 */ }
    }
    f.addEventListener('load', onLoad)
    return () => { f.removeEventListener('load', onLoad); ro?.disconnect() }
  }, [])
  return <iframe ref={ref} src={src} title="FlyDiscovery 워크벤치" style={{ width: '100%', height: h, border: 0, display: 'block', background: 'var(--bg)' }} />
}

export default function Discovery() {
  const [m, setM] = useState<DiscoveryMeasurements | null>(null)
  const [dock, setDock] = useState<Record<string, DockEval> | null>(null)
  const [missing, setMissing] = useState(false)
  useEffect(() => {
    getJSON<DiscoveryMeasurements>('/discovery/data/measurements.json').then(setM).catch(() => setMissing(true))
    getJSON<Record<string, DockEval>>('/discovery/data/dd_eval_all.json').then(setDock).catch(() => null)
  }, [])

  const of3 = m?.openfold3_msa, bm = m?.parp1_affinity_benchmark
  const redock = dock ? Object.entries(dock).filter(([, d]) => d.rmsd_xtal !== null) : []
  const nir = dock?.['parp1-4r6e-chain-a--niraparib']
  const critics = m ? Object.entries(m.critic_eval).sort((a, b) => b[1].caught - a[1].caught) : []
  const [bestName, best] = critics[0] ?? []
  const short = (k: string) => (k.includes('super') ? 'Nemotron 3 Super' : k.includes('lightning') ? 'Nemotron 3.5 Lightning' : k.includes('ultra') ? 'Nemotron 3 Ultra' : k.replace('nvidia/', ''))
  const TARGET: Record<string, string> = { parp1: 'PARP1', factor: 'Xa', cox2: 'COX-2' }
  const pairName = (k: string) => { const [t, l] = k.split('--'); return `${l}@${TARGET[t.split('-')[0]] ?? t}` }

  return (
    <div className="page">
      <PageHead eyebrow="STEP 1 · 시판 전 탐색 · FlyDiscovery"
        title={<>결과를 더 내기보다 <span style={{ color: 'var(--c-sense)' }}>결과가 말해도 되는 범위</span>를 정합니다</>}
        lede={<>후보 하나(니라파립)를 PARP1 결정 구조부터 친화도 벤치마크까지 따라가며, 단계마다 그 분야의 전통 기준으로 채점합니다.
          NVIDIA BioNeMo NIM 네 가지(MSA-Search, OpenFold3, DiffDock, Boltz-2)를 계정 키로 실제 호출했고, 원본 응답은 저장소의 <span className="mono">fly_discovery/measurements/</span>에 있습니다.
          주장은 크리틱 3단(근거 ID, 원본 로그와 숫자 대조, 추론이 근거를 넘는지)을 통과해야 합니다. 이 후보의 시판 후 이상사례는 <a href="#/triage">STEP 2 FlyVigilance</a>가 이어받습니다.</>}
        right={<a className="btn ghost" href={PAGE} target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>새 창에서 열기 ↗</a>} />

      {missing ? (
        <Card title="FlyDiscovery 화면을 찾지 못했습니다" sub="web/public/discovery/ 가 비어 있습니다">
          <div className="note">원본은 <span className="mono">fly_discovery/web</span>에 있고, <span className="mono">npm run dev</span> · <span className="mono">npm run build</span> 전에
            <span className="mono"> scripts/sync-discovery.mjs</span>가 복사합니다. 직접 실행하려면 <span className="mono">cd web && npm run sync-discovery</span>를 실행하세요.</div>
        </Card>
      ) : !m ? <Loading /> : (
        <>
          <div className="grid" style={{ gridTemplateColumns: 'repeat(6, minmax(0, 1fr))', gap: 12, marginBottom: 10 }}>
            <Tile tech="BioNeMo NIM" name="MSA-Search" color="#76b900" value={<>{of3?.msa_homologs}개</>} sub="PARP1 상동 서열 · OpenFold3 입력" />
            <Tile tech="BioNeMo NIM" name="OpenFold3" color="#76b900" value={<>{of3?.ca_rmsd_vs_4R6E.toFixed(1)} Å</>}
              sub={<>4R6E 결정 구조 대비 CA RMSD ({of3?.n_ca}개) · pLDDT {of3?.plddt} · 리간드 {of3?.ligand_rmsd} Å</>} />
            <Tile tech="BioNeMo NIM" name="DiffDock" color="#76b900" value={<>{nir?.rmsd_xtal ?? '–'} Å</>}
              sub={<>재도킹 RMSD · {redock.map(([k, d]) => `${pairName(k)} ${d.rmsd_xtal}`).join(' · ')}</>} />
            <Tile tech="BioNeMo NIM" name="Boltz-2" color="#76b900" value={<>ρ {bm?.spearman.toFixed(3)}</>}
              sub={<>PARP1 {bm?.n}종 ChEMBL 대조 · MAE {bm?.mae} log · 상위 25% EF {bm?.ef_top25} ({bm?.hit}/{bm?.k})</>} />
            <Tile tech="전통 기준" name="채점" color="#8a97bd" value={<>{redock.filter(([, d]) => (d.rmsd_xtal ?? 9) <= 2).length}/{redock.length}</>}
              sub={<>포즈 RMSD ≤ 2 Å (재도킹 대조) · pIC50 ≥ 7 민감도 {bm?.sens} / 특이도 {bm?.spec}</>} />
            <Tile tech={bestName ? short(bestName) : 'Nemotron'} name="크리틱" color="#ff5d6c" value={best ? <>{best.caught}/{best.n_over}</> : '–'}
              sub={best ? <>과잉해석 반려 · 정상 주장 {best.passed}/{best.n_valid} 통과 · {best.sec}초</> : '–'} />
          </div>
          <div className="note" style={{ marginBottom: 16 }}>
            <b>측정 범위</b> · 재도킹 RMSD는 공결정 구조에 원래 리간드를 다시 넣어 도킹 설정을 검증하는 대조 실험입니다. OpenFold3 예측은 공개 결정 구조 4R6E와 비교했습니다.
            친화도 벤치마크는 PARP1 {bm?.n}종을 ChEMBL 실측값과 대조했고, 크리틱은 과잉해석 {best?.n_over ?? '…'}건과 정상 주장 {best?.n_valid ?? '…'}건으로 평가했습니다.
            {m.openfold2.status === 'FAILED' && <> 구조 예측은 OpenFold3로 실행했습니다(OpenFold2 엔드포인트는 측정 당시 HTTP {m.openfold2.http}을 반환).</>}
          </div>
        </>
      )}

      {!missing && (
        <Card className="flush" style={{ overflow: 'hidden' }}>
          <AutoFrame src={PAGE} />
        </Card>
      )}
    </div>
  )
}
