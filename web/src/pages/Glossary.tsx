import { useEffect, useMemo, useState } from 'react'
import { Card, PageHead } from '../components/ui'
import Term from '../components/Term'
import { GLOSSARY, GLOSS_CAT, type GlossCat, type GlossEntry } from '../lib/glossary'

// 용어 풀이: 대시보드의 약어와 전문 용어를 한곳에서 찾아봅니다. 주소 #/glossary?k=SDR 로 들어오면 그 용어로 이동합니다.

const PAGE_LABEL: Record<string, string> = {
  overview: '개요', problem: '문제 정의', discovery: '후보 탐색 개요', 'd-msa': 'MSA-Search', 'd-of3': 'OpenFold3', 'd-diffdock': 'DiffDock',
  'd-boltz': 'Boltz-2', 'd-critic': '크리틱(STEP 1)', mission: '관제 센터', triage: '사례 분류', korea: '국내 보고 · 인과성', signals: '신호 연구실',
  timemachine: '신호 타임머신', validation: '검증', bench: '벤치마크', warehouse: '데이터 웨어하우스', agent: '에이전트 구성', cli: 'CLI 튜토리얼',
  skills: 'NVIDIA 스킬 · 거버넌스', architecture: '아키텍처',
}
const CORE = ['SDR', 'PRR', 'ROR', 'IC025', 'FAERS', 'triage', 'System2', 'NAR', 'NIM', 'AUC', 'pvalue', 'RMSD']

function readHash() {
  const q = location.hash.split('?')[1] ?? ''
  const p = new URLSearchParams(q)
  return { k: p.get('k') ?? '', q: p.get('q') ?? '' }
}

const norm = (s: string) => s.toLowerCase().replace(/[\s·₀₂₅()\-–]/g, '')
const hay = (e: GlossEntry) => norm([e.term, e.en ?? '', e.ko, e.short, e.long ?? '', ...(e.aliases ?? [])].join(' '))

export default function Glossary() {
  const [q, setQ] = useState(() => readHash().q)
  const [hit, setHit] = useState(() => readHash().k)
  const [cat, setCat] = useState<GlossCat | ''>('')

  useEffect(() => {
    const on = () => { const h = readHash(); if (h.k) { setHit(h.k); setQ(''); setCat('') } if (h.q) setQ(h.q) }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  useEffect(() => {
    if (!hit) return
    const t = window.setTimeout(() => document.getElementById(`gl-${hit}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 60)
    return () => window.clearTimeout(t)
  }, [hit])

  const all = useMemo(() => Object.entries(GLOSSARY), [])
  const list = useMemo(() => {
    const n = norm(q)
    return all.filter(([, e]) => (!cat || e.cat === cat) && (!n || hay(e).includes(n)))
  }, [all, q, cat])
  const groups = (Object.keys(GLOSS_CAT) as GlossCat[]).map((c) => ({ c, items: list.filter(([, e]) => e.cat === c) })).filter((g) => g.items.length)

  return (
    <div className="page">
      <PageHead eyebrow="Glossary · 약어와 전문 용어"
        title={<>처음 보는 용어를 <span style={{ color: 'var(--c-sense)' }}>쉬운 말</span>로 풀었습니다</>}
        lede={<>약물감시(PV), 신호 통계, 구조생물학, AI 에이전트 용어 {all.length}개를 모았습니다. 다른 화면에서 점선 밑줄이 그어진 용어(예: <Term k="SDR" />)에 마우스를 올리거나,
          손가락으로 누르거나, 키보드 Tab으로 초점을 옮기면 같은 풀이가 바로 뜹니다. 각 용어 아래에는 그 용어가 나오는 화면을 적어 두었습니다.</>} />

      <Card style={{ marginBottom: 16 }}>
        <div className="row wrap" style={{ gap: 10 }}>
          <div style={{ position: 'relative', width: 320, maxWidth: '100%' }}>
            <input className="input" type="search" placeholder="용어 검색 (예: SDR, 트리아지, 도킹, p값)" value={q} aria-label="용어 검색"
              onChange={(e) => { setQ(e.target.value); setHit('') }} />
          </div>
          <div className="seg" style={{ flexWrap: 'wrap' }}>
            <button className={cat === '' ? 'on' : ''} onClick={() => setCat('')}>전체</button>
            {(Object.keys(GLOSS_CAT) as GlossCat[]).map((c) => (
              <button key={c} className={cat === c ? 'on' : ''} onClick={() => setCat(c)}>{GLOSS_CAT[c].name}</button>
            ))}
          </div>
          <span className="mono dim" style={{ fontSize: 11, marginLeft: 'auto' }} role="status">{list.length} / {all.length}개</span>
        </div>
        <div className="row wrap" style={{ gap: 6, marginTop: 12 }}>
          <span className="dim" style={{ fontSize: 11.5 }}>자주 나오는 용어</span>
          {CORE.filter((k) => GLOSSARY[k]).map((k) => (
            <a key={k} className="chip" href={`#/glossary?k=${k}`} style={{ textDecoration: 'none' }}>{GLOSSARY[k].term}</a>
          ))}
        </div>
      </Card>

      {!groups.length && <Card><div className="note" style={{ fontSize: 12.5 }}>"{q}"와 맞는 용어가 없습니다. 다른 표기(영문 약어, 한국어 이름)로 검색해 보세요.</div></Card>}

      <div className="stack" style={{ gap: 18 }}>
        {groups.map(({ c, items }) => (
          <section key={c}>
            <div className="row" style={{ gap: 8, margin: '0 0 8px' }}>
              <span className="legend-dot" style={{ background: GLOSS_CAT[c].color }} />
              <h2 style={{ margin: 0 }}>{GLOSS_CAT[c].name}</h2>
              <span className="mono dim" style={{ fontSize: 11 }}>{items.length}</span>
            </div>
            <div className="gl-list">
              {items.map(([k, e]) => (
                <article key={k} id={`gl-${k}`} className={`gl-item ${hit === k ? 'hit' : ''}`} style={{ ['--cat' as string]: GLOSS_CAT[e.cat].color }}>
                  <h3>{e.term}{e.en && <small>{e.en}</small>}</h3>
                  <div className="gl-ko">{e.ko}</div>
                  <p>{e.short}</p>
                  {e.long && <p className="gl-long">{e.long}</p>}
                  <div className="gl-where">
                    <span className="mono dim" style={{ fontSize: 10.5 }}>나오는 곳</span>
                    {e.where?.length
                      ? e.where.map((w) => <a key={w} className="chip" href={`#/${w}`}>{PAGE_LABEL[w] ?? w}</a>)
                      : <span className="dim" style={{ fontSize: 11 }}>README · 문서의 참고 용어</span>}
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}
