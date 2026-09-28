import { useEffect, useState } from 'react'
import { Card, Loading, PageHead } from '../components/ui'
import { getJSON } from '../lib/data'

interface Skill { name: string; description: string; license: string; layer: string; model: string; path: string; body: string }

const RULES = [
  ['R1', 'Disproportionality는 보고 연관성이지 인과가 아니다'], ['R2', 'FAERS에는 분모가 없다: 발생률·위험도 추정 금지'],
  ['R3', '서로 다른 약물의 안전성을 불균형 크기로 순위 매기지 않는다'], ['R4', '신호 부재는 안전성의 증거가 아니다'],
  ['R5', '라벨 기재가 이 케이스의 인과를 확인하지 않는다'], ['R6', '단일 케이스로 신호를 확정하지 않는다'],
  ['R7', 'PubMed 건수는 근거 강도가 아니다'], ['R8', '중복·자극 보고로 건수는 정확하지 않다'],
  ['R9', '적응증 교란과 병용약을 무시하지 않는다'], ['R10', '모델 확률은 집단 보정값이지 개별 확신이 아니다'],
  ['R11', '환자 개별 치료·용량 조언 금지 (NVIDIA safety guard)'], ['R12', '인용한 라벨 문구는 실제 해당 절에 있어야 한다'],
  ['R13', '근거 등급은 집단 근거다: 근거·공백 없이 등급만 인용하거나 이 사례의 인과로 쓰지 않는다'],
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
        title={<>에이전트의 능력은 <span style={{ color: 'var(--nvidia)' }}>SKILL.md</span>로, 경계는 규칙으로</>}
        lede={<>build.nvidia.com의 Agent Skills 규격(<span className="mono">npx skills add NVIDIA/skills</span>)을 따라 FlyVigilance의 능력 7개를 스킬 패키지로 나눴다. 각 스킬은 입력·출력 계약, 허용 호스트, 쓰는 모델을 명시하고 저장소의 실제 코드를 가리킨다. 가드레일 스킬은 NVIDIA 공식 <span className="mono">nemotron-policy-generator</span>의 BYO 정책 방식을 따른다.</>} />
      <div className="grid" style={{ gridTemplateColumns: '360px minmax(0,1fr)', alignItems: 'start', marginBottom: 16 }}>
        <div className="stack" style={{ gap: 8 }}>
          {sk.map((s) => (
            <button key={s.name} onClick={() => setOpen(s.name)} className="card" style={{ textAlign: 'left', cursor: 'pointer', padding: '12px 14px',
              border: open === s.name ? '1px solid rgba(118,185,0,0.6)' : undefined, boxShadow: open === s.name ? '0 0 24px -8px var(--nvidia)' : undefined }}>
              <div className="row between"><b className="mono" style={{ fontSize: 12.5, color: open === s.name ? '#c8f36b' : 'var(--text)' }}>{s.name}</b><span className="chip" style={{ fontSize: 9.5 }}>{s.layer}</span></div>
              <div className="dim" style={{ fontSize: 11.5, marginTop: 4, lineHeight: 1.45 }}>{s.description.slice(0, 130)}{s.description.length > 130 ? '…' : ''}</div>
            </button>
          ))}
        </div>
        <Card title={<span className="mono">{cur.path}</span>} sub={cur.description}
          right={<div className="row" style={{ gap: 6 }}>{cur.model && <span className="chip nv">{cur.model.split(' ')[0]}</span>}<span className="chip">{cur.license.split(' ')[0]}</span></div>}>
          <Md text={cur.body} />
        </Card>
      </div>
      <div className="grid g2">
        <Card title="과잉해석 규칙 13종" sub="크리틱 3단(Jev 판정)과 Nemotron 시스템 프롬프트가 같은 목록을 쓴다">
          <div className="grid g2" style={{ gap: 8 }}>
            {RULES.map(([k, v]) => <div key={k} className="row" style={{ alignItems: 'flex-start', gap: 8, fontSize: 12 }}><span className="chip bad" style={{ fontSize: 10 }}>{k}</span><span className="muted">{v}</span></div>)}
          </div>
        </Card>
        <Card title="거버넌스와 감사" sub="에이전트가 하지 못하는 것">
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, lineHeight: 1.9, color: 'var(--text-2)' }}>
            <li>외부 호출은 허용 호스트 4곳뿐: api.fda.gov · eutils.ncbi.nlm.nih.gov · api.typesafe.ai · integrate.api.nvidia.com</li>
            <li>숫자는 SQL이 만들고, 모델 문장 속 모든 숫자는 근거와 대조된다 (T2)</li>
            <li>근거 ID가 없는 주장은 사람에게 가지 않는다 (T1)</li>
            <li>규제 보고와 인과성 최종 판정은 사람만 한다. 에이전트는 초안과 우선순위를 낸다</li>
            <li>공개 배포 API는 IP별 속도 제한 (트리아지 30회/분, 평가 6회/분)</li>
            <li>모든 라우팅 결정은 사유 문자열과 함께 반환되어 감사 로그로 남길 수 있다</li>
          </ul>
        </Card>
      </div>
    </div>
  )
}
