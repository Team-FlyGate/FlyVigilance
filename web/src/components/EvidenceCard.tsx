import { useEffect, useState } from 'react'
import { Card } from './ui'
import { getJSON } from '../lib/data'
import { DRUG_LABEL, HERO_DRUGS, useHeroDrug } from './HeroDocking'
import Step2Handoff from './Step2Handoff'
import { isEn, t } from '../lib/i18n'

// 후보 근거 카드: STEP 1 이 STEP 2 로 넘기는 후보 한 장. 구조 · 계산 · 실험 · 선택성 근거와 발견 신뢰도,
// 그리고 이 근거로 말해도 되는 주장 / 안 되는 주장을 나란히 적습니다. 값은 evidence_cards.json(build_evidence_cards.py) 그대로입니다.

interface Ex { n: number; median: number; max: number; types: string[]; docs: number }
interface CardData {
  name: string; label: string; target: string; chembl: string; crystal_pdb: string; receptor_pdb: string
  structure: { method: string; resolution: number | null; organism: string | null; verdict: string; reasons: string[] }
  validation: { grade: string; crystal_hits: number; runs: number; pairwise_median: number | null; confidence_mean: number | null; confidence_sd: number | null }
  computational: { vina: number | null; dd_conf: number; dd_rmsd: number | null; boltz_pic50: number | null; xa_dd_conf: number; xa_vina: number | null }
  experimental: Record<string, Ex>
  selectivity: { gene: string; docking: number | null; chembl: Ex | null; status: 'supported' | 'exploratory' | 'measured-weak' | 'no-data' }[]
  confidence: { level: 'HIGH' | 'MEDIUM' | 'LOW'; score: number; checks: { name: string; ok: boolean; detail: string }[] }
  allowed: string[]; not_allowed: { rule: string; claim: string }[]
}

const GENE = (g: string) => (g === 'F10' ? 'Factor Xa' : g)
// 언어에 따라 이름이 바뀌므로 렌더할 때 부릅니다
const STATUS = (): Record<string, [string, string]> => ({
  supported: [t('실측 결합', 'Measured binding'), 'var(--ok)'], 'measured-weak': [t('측정됨 · 약함', 'Measured · weak'), 'var(--jev)'],
  exploratory: [t('탐색적 (도킹만)', 'Exploratory (docking only)'), 'var(--text-3)'], 'no-data': [t('기록 없음', 'No record'), 'var(--text-3)'],
})
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

// evidence_cards.json(build_evidence_cards.py)의 한국어 문장은 정해진 틀로 만들어지므로, 영어 화면에서는 틀별로 바꿔 씁니다.
// 틀에 맞지 않는 문장은 원문 그대로 둡니다. ko 는 카드의 한국어 약물 이름, en 은 영어 이름입니다.
const CHECK_EN: Record<string, string> = { '구조 품질': 'Structure quality', '도킹 검증': 'Docking validation', '실측 결합': 'Measured binding' }
function cardEn(x: string, ko: string, en: string): string {
  if (!isEn()) return x
  const s = x.split(ko).join(en).replace(new RegExp(`${en}(은|는|의)`, 'g'), (_, j) => (j === '의' ? `${en}'s` : en))
  const rules: [RegExp, (m: RegExpMatchArray) => string][] = [
    [/^(\S+)–(\S+) 상호작용은 계산 근거\(재도킹 (\d+)\/(\d+)회 정답\)와 실험 근거\(ChEMBL pChEMBL 중앙값 ([\d.]+), (\d+)건\)가 함께 뒷받침한다\.$/,
      (m) => `The ${m[1]}–${m[2]} interaction is supported by both computational evidence (redocking correct in ${m[3]}/${m[4]} runs) and experimental evidence (ChEMBL median pChEMBL ${m[5]}, ${m[6]} records).`],
    [/^Boltz-2 는 (\S+) pIC50 을 ([\d.]+) 로 예측했고, ChEMBL 실측 중앙값은 ([\d.]+) 이다\(예측값과 실측값을 나란히 적은 것\)\.$/,
      (m) => `Boltz-2 predicted a ${m[1]} pIC50 of ${m[2]}; the ChEMBL measured median is ${m[3]} (predicted and measured values shown side by side).`],
    [/^(\S+) 과 (\S+) 모두 실측 결합 근거가 있다\((\S+) 중앙값 ([\d.]+), (\d+)건\)\.$/,
      (m) => `Both ${m[1]} and ${m[2]} have measured binding evidence (${m[3]} median ${m[4]}, ${m[5]} records).`],
    [/^Factor Xa 결합은 도킹만 있고 실측 기록이 없어 탐색적 결과로만 적는다\.$/,
      () => 'Factor Xa binding has docking results only and no measured record, so it is reported as exploratory only.'],
    [/^(.+) DiffDock 신뢰도 (\S+) ([-\d.]+), Factor Xa ([-\d.]+) 이므로 (.+) 에 선택적이다\.$/,
      (m) => `${m[1]} is selective for ${m[5]} because its DiffDock confidence is ${m[3]} on ${m[2]} vs. ${m[4]} on Factor Xa.`],
    [/^(.+) (\S+) 에 Factor Xa 보다 ([\d.]+) kcal\/mol 더 선택적이다\.$/,
      (m) => `${m[1]} is ${m[3]} kcal/mol more selective for ${m[2]} than for Factor Xa.`],
    [/^(.+) (\S+) 친화도는 pIC50 ([\d.]+) 로 측정되었다\.$/,
      (m) => `${m[1]} ${m[2]} affinity was measured at pIC50 ${m[3]}.`],
    [/^(.+) (\S+) 선택적 억제제다\. \((\S+) 실측 결합도 있어 같은 조건의 비교 실험 없이는 말할 수 없다\)$/,
      (m) => `${m[1]} is a selective ${m[2]} inhibitor. (${m[3]} also has measured binding, so this cannot be claimed without a head-to-head experiment under the same conditions.)`],
    [/^DiffDock 신뢰도가 ([-\d.]+) 로 음수이므로 (.+) (\S+) 에 잘 붙지 않는다\. \(포즈는 결정 자리와 ([\d.]+) Å\)$/,
      (m) => `${m[2]} binds ${m[3]} poorly because its DiffDock confidence is negative (${m[1]}). (The pose is ${m[4]} Å from the crystal site.)`],
    [/^DiffDock (\d+)회 중 결정 자리 정답 (\d+)회 · 반복 간 ([\d.]+) Å · 등급 (\w+)$/,
      (m) => `DiffDock: ${m[2]} of ${m[1]} runs at the crystal site · ${m[3]} Å between runs · grade ${m[4]}`],
    [/^ChEMBL (\S+) pChEMBL 중앙값 ([\d.]+) · (\d+)건 · 문헌 (\d+)편$/,
      (m) => `ChEMBL ${m[1]} median pChEMBL ${m[2]} · ${m[3]} records · ${m[4]} papers`],
  ]
  for (const [re, f] of rules) { const m = s.match(re); if (m) return f(m) }
  return s
}
/** 구조 판정 · 주의 사유(validation.json · evidence_cards.json 공통)를 영어로 바꿉니다 */
export function structEn(x: string): string {
  if (!isEn()) return x
  if (x === '도킹 가능') return 'Dockable'
  if (x === '주의') return 'Caution'
  let m = x.match(/^해상도 (.+)$/); if (m) return `Resolution ${m[1]}`
  m = x.match(/^결합 자리 옆 잔기 (\d+)개가 구조에 없음$/); if (m) return `${m[1]} residues next to the binding site are missing from the structure`
  m = x.match(/^생물종 (.+)$/); if (m) return `Species: ${m[1]}`
  return x
}
const LEVEL_COLOR = { HIGH: 'var(--ok)', MEDIUM: 'var(--jev)', LOW: 'var(--bad)' }

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="stack" style={{ gap: 5 }}>
      <span className="mono" style={{ fontSize: 10, letterSpacing: 1.6, color: 'var(--text-3)' }}>{title}</span>
      {children}
    </div>
  )
}
function Row({ k, v, ok }: { k: string; v: React.ReactNode; ok?: boolean }) {
  return (
    <div className="row between" style={{ fontSize: 12.5, gap: 10 }}>
      <span className="dim">{k}</span>
      <span className="num" style={{ textAlign: 'right' }}>{v}{ok !== undefined && <span style={{ marginLeft: 6, color: ok ? 'var(--ok)' : 'var(--bad)' }}>{ok ? '✓' : '✕'}</span>}</span>
    </div>
  )
}

export default function EvidenceCard() {
  const [f, setF] = useState<{ strong_pchembl: number; cards: Record<string, CardData> } | null>(null)
  const [drug, setDrug] = useHeroDrug()
  useEffect(() => { getJSON<{ strong_pchembl: number; cards: Record<string, CardData> }>('/discovery/data/evidence_cards.json').then(setF).catch(() => null) }, [])
  const c = f?.cards[drug] ?? f?.cards.niraparib
  if (!f || !c) return null
  const s = c.structure, v = c.validation, x = c.computational, p1 = c.experimental.PARP1
  const en = cap(c.name), status = STATUS()
  const tx = (z: string) => cardEn(z, c.label, en)
  return (
    <Card title={t(`후보 근거 카드 · ${c.label} → ${c.target}`, `Candidate evidence card · ${en} → ${c.target}`)}
      sub={t('STEP 2 로 넘기기 전에 이 후보에 대해 무엇을 말해도 되는지 정합니다. 구조 · 계산 · 실험 · 선택성 근거를 한 장에 모았습니다',
        'Before handing off to STEP 2, this decides what may be claimed about the candidate. Structural, computational, experimental and selectivity evidence on one card')}
      right={<div className="row" style={{ gap: 6 }}>
        {HERO_DRUGS.filter((d) => f.cards[d]).map((d) => (
          <button key={d} className={`chip ${d === c.name ? 'jev' : ''}`} style={{ cursor: 'pointer', fontWeight: d === c.name ? 700 : 500 }} onClick={() => setDrug(d)}>{t(DRUG_LABEL[d], cap(d))}</button>
        ))}
      </div>}
      style={{ marginBottom: 16 }}>
      <div className="grid fade-in" key={c.name} style={{ gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.15fr)', gap: 22 }}>
        <div className="stack" style={{ gap: 16 }}>
          <Section title="STRUCTURE">
            <Row k={t('결정 구조', 'Crystal structure')} v={`PDB ${c.crystal_pdb} · ${s.method} ${s.resolution ?? '–'} Å`} ok={s.verdict === '도킹 가능'} />
            <Row k={t('생물종', 'Species')} v={s.organism ?? '–'} />
            <Row k={t('공결정 리간드', 'Co-crystal ligand')} v={t('있음', 'Present')} ok />
            {s.reasons.length > 0 && <span style={{ fontSize: 11.5, color: 'var(--jev)' }}>{t('주의', 'Caution')}: {s.reasons.map(structEn).join(', ')}</span>}
          </Section>
          <Section title="COMPUTATIONAL">
            {x.vina !== null && <Row k="Vina" v={`${x.vina} kcal/mol`} />}
            <Row k={`DiffDock (${c.receptor_pdb})`} v={t(`신뢰도 ${x.dd_conf} · 결정 자리 ${x.dd_rmsd ?? '–'} Å`, `confidence ${x.dd_conf} · ${x.dd_rmsd ?? '–'} Å from crystal site`)} />
            <Row k={t('반복 재도킹', 'Repeated redocking')} v={t(`${v.crystal_hits}/${v.runs}회 정답 · 등급 ${v.grade}`, `${v.crystal_hits}/${v.runs} correct · grade ${v.grade}`)} ok={v.grade === 'HIGH'} />
            <Row k={t('포즈 수렴', 'Pose convergence')} v={t(`반복 간 ${v.pairwise_median ?? '–'} Å`, `${v.pairwise_median ?? '–'} Å between runs`)} />
            <Row k={t('신뢰도 편차', 'Confidence spread')} v={t(`표준편차 ${v.confidence_sd ?? '–'}`, `SD ${v.confidence_sd ?? '–'}`)} />
            {x.boltz_pic50 !== null && <Row k={t('Boltz-2 예측', 'Boltz-2 prediction')} v={t(`pIC50 ${x.boltz_pic50.toFixed(2)} (예측)`, `pIC50 ${x.boltz_pic50.toFixed(2)} (predicted)`)} />}
          </Section>
        </div>
        <div className="stack" style={{ gap: 16 }}>
          <Section title="EXPERIMENTAL · ChEMBL">
            <Row k={t('PARP1 기록', 'PARP1 records')} v={p1 ? t(`${p1.n}건 · 문헌 ${p1.docs}편`, `${p1.n} records · ${p1.docs} papers`) : t('없음', 'None')} ok={!!p1 && p1.median >= f.strong_pchembl} />
            {p1 && <Row k="pChEMBL" v={t(`중앙값 ${p1.median} · 최대 ${p1.max}`, `median ${p1.median} · max ${p1.max}`)} />}
            {p1 && <Row k={t('측정 종류', 'Assay types')} v={p1.types.join(' · ')} />}
            <span className="mono dim" style={{ fontSize: 10 }}>{c.chembl} · {t(`pChEMBL = -log(몰 농도) · ${f.strong_pchembl} 이상 = 1 µM 보다 강함`, `pChEMBL = -log(molar concentration) · ${f.strong_pchembl} or higher = stronger than 1 µM`)}</span>
          </Section>
          <Section title="SELECTIVITY">
            {c.selectivity.map((r) => (
              <div key={r.gene} style={{ display: 'grid', gridTemplateColumns: '78px 1fr auto', gap: 8, fontSize: 12.5, alignItems: 'baseline' }}>
                <b>{GENE(r.gene)}</b>
                <span className="num dim" style={{ fontSize: 11 }}>{r.docking !== null ? `${t('도킹', 'docking')} ${r.docking}` : t('도킹 안 함', 'not docked')}{r.chembl ? ` · ${t('실측', 'measured')} ${r.chembl.median} (${r.chembl.n})` : ''}</span>
                <span style={{ fontSize: 11.5, color: status[r.status][1] }}>{status[r.status][0]}</span>
              </div>
            ))}
          </Section>
          <Section title="DISCOVERY CONFIDENCE">
            <div className="row" style={{ gap: 10, alignItems: 'center' }}>
              <div style={{ flex: 1, height: 10, borderRadius: 5, background: 'rgba(120,170,255,0.12)', overflow: 'hidden' }}>
                <div style={{ width: `${(c.confidence.score / 3) * 100}%`, height: '100%', background: LEVEL_COLOR[c.confidence.level], opacity: 0.85 }} />
              </div>
              <b className="mono" style={{ color: LEVEL_COLOR[c.confidence.level] }}>{c.confidence.level}</b>
            </div>
            {c.confidence.checks.map((k) => (
              <div key={k.name} style={{ fontSize: 11.5 }}><span style={{ color: k.ok ? 'var(--ok)' : 'var(--bad)', marginRight: 6 }}>{k.ok ? '✓' : '✕'}</span><b>{t(k.name, CHECK_EN[k.name] ?? k.name)}</b> <span className="dim">{tx(k.detail)}</span></div>
            ))}
          </Section>
        </div>
        <div className="stack" style={{ gap: 10 }}>
          <Section title="ALLOWED CLAIM">
            {c.allowed.map((a, i) => (
              <div key={i} style={{ padding: '8px 10px', borderRadius: 9, background: 'rgba(61,220,151,0.06)', border: '1px solid rgba(61,220,151,0.3)', fontSize: 12.5, lineHeight: 1.55 }}>“{tx(a)}”</div>
            ))}
          </Section>
          <Section title="NOT ALLOWED">
            {c.not_allowed.map((a, i) => (
              <div key={i} style={{ padding: '8px 10px', borderRadius: 9, background: 'rgba(255,93,108,0.05)', border: '1px solid rgba(255,93,108,0.3)', fontSize: 12.5, lineHeight: 1.55 }}>
                <span className="mono" style={{ fontSize: 10, color: 'var(--bad)', marginRight: 6 }}>{a.rule}</span>“{tx(a.claim)}”
              </div>
            ))}
          </Section>
          <Step2Handoff drug={c.name} />
        </div>
      </div>
    </Card>
  )
}
