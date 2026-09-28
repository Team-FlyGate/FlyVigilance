import { useEffect, useState, type ReactNode } from 'react'
import { Card, Loading, PageHead } from '../components/ui'
import { getJSON } from '../lib/data'
import Term from '../components/Term'
import { t } from '../lib/i18n'

interface Skill {
  name: string; description: string; license: string; layer: string; model: string; path: string; body: string
  title?: string; version?: string; compatibility?: string; skill_card?: string; skill_card_url?: string; evals?: number
}

// 언어에 따라 문구가 바뀌므로 렌더할 때 만듭니다.
const rules = (): [string, ReactNode][] => [
  ['R1', t(<><Term k="disproportionality">Disproportionality</Term>(불균형 분석)는 보고 연관성이지 인과가 아닙니다</>, <><Term k="disproportionality">Disproportionality</Term> analysis shows a reporting association, not causation</>)], ['R2', t(<><Term k="FAERS" />에는 분모(전체 복용자 수)가 없습니다: 발생률·위험도를 추정하지 않습니다</>, <><Term k="FAERS" /> (FDA Adverse Event Reporting System) has no denominator (total number of patients exposed): never estimate incidence or risk</>)],
  ['R3', t('서로 다른 약물의 안전성을 불균형 크기로 순위 매기지 않습니다', 'Never rank the safety of different drugs by the size of their disproportionality')], ['R4', t(<><Term k="SDR" ko /> 부재는 안전성의 증거가 아닙니다</>, <>The absence of an <Term k="SDR" ko /> is not evidence of safety</>)],
  ['R5', t(<><Term k="label">라벨</Term> 기재가 이 케이스의 인과를 확인하지 않습니다</>, <>Being listed on the <Term k="label">label</Term> does not confirm causation in this case</>)], ['R6', t('단일 케이스로 신호를 확정하지 않습니다', 'Never confirm a signal from a single case')],
  ['R7', t(<><Term k="PubMed">PubMed</Term> 건수는 근거 강도가 아닙니다</>, <><Term k="PubMed">PubMed</Term> hit counts are not strength of evidence</>)], ['R8', t(<>중복·자극 보고(<Term k="bias">보고 편향</Term>) 때문에 건수는 정확하지 않습니다</>, <>Counts are imprecise because of duplicate and stimulated reports (<Term k="bias">reporting bias</Term>)</>)],
  ['R9', t(<><Term k="indication">적응증</Term> 교란과 병용약을 무시하지 않습니다</>, <>Never ignore <Term k="indication">indication</Term> confounding or co-medications</>)], ['R10', t('모델 확률은 집단 보정값이지 개별 확신이 아닙니다', 'Model probabilities are calibrated at the population level, not certainty about an individual')],
  ['R11', t(<>환자 개별 치료·용량 조언을 하지 않습니다 (NVIDIA Nemotron <Term k="guard">Safety Guard</Term>)</>, <>No individual treatment or dosing advice for patients (NVIDIA Nemotron <Term k="guard">Safety Guard</Term>)</>)], ['R12', t('인용한 라벨 문구는 실제 해당 절에 있어야 합니다', 'Quoted label text must actually appear in the cited section')],
  ['R13', t('근거 등급은 집단 근거입니다: 근거·공백 없이 등급만 인용하거나 이 사례의 인과로 쓰지 않습니다', 'Evidence grades describe population-level evidence: never quote a grade without its evidence and gaps, or use it as causation for this case')],
]

function Md({ text }: { text: string }) {
  const lines = text.split('\n')
  return (
    <div style={{ fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.7 }}>
      {lines.map((l, i) => {
        if (l.startsWith('# ')) return <div key={i} style={{ fontFamily: 'var(--font)', fontSize: 14, color: 'var(--text)', margin: '4px 0' }}>{l.slice(2)}</div>
        if (l.startsWith('## ')) return <div key={i} className="eyebrow" style={{ margin: '10px 0 4px' }}>{l.slice(3)}</div>
        if (l.startsWith('|')) return <div key={i} className="mono" style={{ fontSize: 10.5, whiteSpace: 'pre', overflowX: 'auto', color: l.includes('---') ? 'var(--text-3)' : 'var(--text-2)' }}>{l}</div>
        if (!l.trim()) return <div key={i} style={{ height: 6 }} />
        return <div key={i}>{l.replace(/`/g, '')}</div>
      })}
    </div>
  )
}

export default function Skills() {
  const [sk, setSk] = useState<Skill[] | null>(null)
  const [open, setOpen] = useState('pv-reflex-triage')
  useEffect(() => { getJSON<Skill[]>('/data/skills.json').then(setSk) }, [])
  if (!sk) return <div className="page"><Loading /></div>
  const cur = sk.find((s) => s.name === open) ?? sk[0]
  return (
    <div className="page">
      <PageHead eyebrow="NVIDIA Agent Skills · Guardrails · Governance"
        title={t(<>에이전트의 능력은 <span style={{ color: 'var(--nvidia)' }}><Term k="AgentSkills">SKILL.md</Term></span>로, 경계는 규칙으로</>, <>Agent abilities as <span style={{ color: 'var(--nvidia)' }}><Term k="AgentSkills">SKILL.md</Term></span>, boundaries as rules</>)}
        lede={t(<>FlyVigilance는 NVIDIA 스킬 위에 짠 워크플로입니다. build.nvidia.com의 <Term k="AgentSkills" /> 규격(에이전트 능력을 패키지로 적는 규격, <span className="mono">npx skills add NVIDIA/skills</span>)을 따라 능력 {sk.length}개를 스킬 패키지로 나눴습니다. 각 스킬은 입력·출력 계약, 허용 호스트, 쓰는 모델을 명시하고 저장소의 실제 코드를 가리킵니다. 글을 써야 하는 스킬은 NVIDIA <Term k="Nemotron" />을, 타입 있는 확률 판단만 필요한 스킬은 <Term k="NAR">비자기회귀 판단 모델</Term>(<Term k="Jev" />)을 씁니다. 가드레일 스킬은 NVIDIA 공식 <span className="mono">nemotron-policy-generator</span>의 BYO(Bring Your Own, 직접 쓴 정책을 넣는) 정책 방식을 따릅니다.</>, <>FlyVigilance is an agentic workflow built on NVIDIA Skills, pairing NVIDIA <Term k="Nemotron" /> with a non-autoregressive judgment model. Following the <Term k="AgentSkills" /> specification on build.nvidia.com (a format for packaging agent abilities, <span className="mono">npx skills add NVIDIA/skills</span>), its {sk.length} abilities are split into skill packages. Each skill declares its input/output contract, allowed hosts and model, and points to real code in the repository. Skills that must write text use NVIDIA <Term k="Nemotron" />; skills that only need typed probability judgments use the <Term k="NAR">non-autoregressive judgment model</Term> (<Term k="Jev" />). The guardrail skill follows the BYO (Bring Your Own policy) approach of NVIDIA's official <span className="mono">nemotron-policy-generator</span>.</>)} />
      <div className="grid" style={{ gridTemplateColumns: '360px minmax(0,1fr)', alignItems: 'start', marginBottom: 16 }}>
        <div className="stack" style={{ gap: 8 }}>
          {sk.map((s) => (
            <button key={s.name} onClick={() => setOpen(s.name)} className="card" style={{ textAlign: 'left', cursor: 'pointer', padding: '12px 14px',
              border: open === s.name ? '1px solid rgba(118,185,0,0.6)' : undefined, boxShadow: open === s.name ? '0 0 24px -8px var(--nvidia)' : undefined }}>
              <div className="row between"><b className="mono" style={{ fontSize: 12.5, color: open === s.name ? '#c8f36b' : 'var(--text)' }}>{s.name}</b>{s.layer && <span className="chip" style={{ fontSize: 9.5 }}>{s.layer}</span>}</div>
              <div className="dim" style={{ fontSize: 11.5, marginTop: 4, lineHeight: 1.45 }}>{s.description.slice(0, 130)}{s.description.length > 130 ? '…' : ''}</div>
            </button>
          ))}
        </div>
        <Card title={<span className="mono">{cur.path}</span>} sub={cur.description}
          right={<div className="row" style={{ gap: 6 }}>{cur.model && <span className="chip nv">{cur.model.split(' ')[0]}</span>}{cur.version && <span className="chip">v{cur.version}</span>}<span className="chip">{cur.license.split(' ')[0]}</span>{cur.skill_card_url && <a className="chip" href={cur.skill_card_url} target="_blank" rel="noreferrer" title={cur.skill_card}>skill card ↗</a>}</div>}>
          <Md text={cur.body} />
        </Card>
      </div>
      <div className="grid g2">
        <Card title={t(<><Term k="overclaim">과잉해석</Term> 규칙 13종</>, <>13 <Term k="overclaim">overclaim</Term> rules</>)} sub={t(<><Term k="critic">크리틱</Term> 3단(비자기회귀 판단 모델의 판정)과 Nemotron 시스템 프롬프트가 같은 목록을 씁니다</>, <><Term k="critic">Critic</Term> tier 3 (the non-autoregressive judgment model's verdict) and the Nemotron system prompt share the same list</>)}>
          <div className="grid g2" style={{ gap: 8 }}>
            {rules().map(([k, v]) => <div key={k} className="row" style={{ alignItems: 'flex-start', gap: 8, fontSize: 12 }}><span className="chip bad" style={{ fontSize: 10 }}>{k}</span><span className="muted">{v}</span></div>)}
          </div>
        </Card>
        <Card title={t('거버넌스와 감사', 'Governance and audit')} sub={t('에이전트가 지키는 경계입니다', 'The boundaries the agent keeps')}>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, lineHeight: 1.9, color: 'var(--text-2)' }}>
            {t(<>
            <li>외부 호출은 <Term k="egress">허용 호스트</Term> 4곳으로만 나갑니다: integrate.api.nvidia.com · api.typesafe.ai · api.fda.gov · eutils.ncbi.nlm.nih.gov</li>
            <li>숫자는 <Term k="SQL">SQL</Term>이 만들고, 모델 문장 속 모든 숫자는 근거와 대조됩니다 (<Term k="oracle">T2</Term>)</li>
            <li><Term k="evidenceId">근거 ID</Term>가 없는 주장은 사람에게 가지 않습니다 (T1)</li>
            <li>규제 보고와 인과성 최종 판정은 사람만 합니다. 에이전트는 초안과 우선순위를 냅니다</li>
            <li>공개 배포 <Term k="API" />는 IP별로 속도를 제한합니다 (트리아지 30회/분, 평가 6회/분)</li>
            <li>모든 라우팅 결정은 사유 문자열과 함께 반환되어 감사 로그로 남길 수 있습니다</li>
            <li>NVIDIA 호출은 <span className="mono">FV_CALL_LOG</span> 를 켜면 한 건마다 모델 · 상태 · 지연 · <Term k="NVCF" /> 만 기록합니다. 키와 프롬프트는 남기지 않습니다 → <a href="#/calls">NVIDIA 호출 로그</a></li>
            </>, <>
            <li>External calls go only to 4 <Term k="egress">allowed hosts</Term>: integrate.api.nvidia.com · api.typesafe.ai · api.fda.gov · eutils.ncbi.nlm.nih.gov</li>
            <li><Term k="SQL">SQL</Term> produces the numbers, and every number in a model sentence is checked against the evidence (<Term k="oracle">T2</Term>)</li>
            <li>Claims without an <Term k="evidenceId">evidence ID</Term> never reach a person (T1)</li>
            <li>Only people make regulatory reports and final causality judgments. The agent drafts and prioritizes</li>
            <li>The public <Term k="API" /> is rate-limited per IP (triage 30/min, grading 6/min)</li>
            <li>Every routing decision is returned with a reason string, so it can be kept as an audit log</li>
            <li>With <span className="mono">FV_CALL_LOG</span> on, each NVIDIA call records only model · status · latency · <Term k="NVCF" />. Keys and prompts are never stored → <a href="#/calls">NVIDIA call log</a></li>
            </>)}
          </ul>
        </Card>
      </div>
    </div>
  )
}
