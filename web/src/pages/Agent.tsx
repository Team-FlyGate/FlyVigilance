import { useEffect, useState, type ReactNode } from 'react'
import AgentDiagram from '../components/AgentDiagram'
import { Card, Loading, PageHead } from '../components/ui'
import { getJSON } from '../lib/data'
import type { AgentInfo } from '../lib/types'

// 에이전트 구성: NemoClaw 과정의 네 층(LLM 엔드포인트, OpenClaw 하네스, OpenShell 샌드박스, NemoClaw 블루프린트)에
// FlyGate 를 대응시킨 구성도와, agent/export_agent_json.py 가 만든 /data/agent.json 의 내용을 보여 줍니다.
// (모듈 체크리스트, 워크스페이스 파일, OpenShell 정책, 트리거, CLI, 라이브 점검, 치명적 삼박자)
// 파일이 없거나 일부 항목이 비어 있으면 그 부분만 건너뛰고 구성도는 그대로 보여 줍니다.

const REPO = 'https://github.com/Team-FlyGate/Project-FlyGate'
const IMG = '/images/flygate_agent_diagram_v1.0.0.png'

const clip = (t: string, n: number) => (t.length > n ? `${t.slice(0, n - 1)}…` : t)
const arr = (v: unknown): string[] => (Array.isArray(v) ? v.map(String) : v === undefined || v === null || v === '' ? [] : [String(v)])

// modules[].ours 는 'implemented' / 'documented' 같은 상태어로 시작합니다. 뒤에 설명이 붙어 있으면 따로 보여 줍니다
const STATUS: Record<string, { t: string; c: string }> = {
  implemented: { t: '구현', c: 'var(--ok)' },
  documented: { t: '문서화', c: 'var(--c-encode)' },
  partial: { t: '일부 구현', c: 'var(--warn)' },
}
function splitStatus(ours: string) {
  const m = /^\s*(implemented|documented|partial)\b[\s:·—–-]*(.*)$/is.exec(ours ?? '')
  return m ? { key: m[1].toLowerCase(), rest: m[2].trim() } : { key: '', rest: (ours ?? '').trim() }
}
function StatusChip({ k }: { k: string }) {
  const s = STATUS[k]
  if (!s) return null
  return <span className="chip" style={{ color: s.c, borderColor: s.c, background: 'transparent', fontSize: 10.5, padding: '1px 8px' }}>{s.t}</span>
}

function Section({ id, title, sub, right, children }: { id?: string; title: ReactNode; sub?: ReactNode; right?: ReactNode; children: ReactNode }) {
  return (
    <div id={id}>
      <Card title={title} sub={sub} right={right} style={{ height: '100%' }}>{children}</Card>
    </div>
  )
}

function Modules({ rows }: { rows: AgentInfo['modules'] }) {
  const counts = rows.reduce<Record<string, number>>((a, r) => { const k = splitStatus(r.ours).key || 'other'; a[k] = (a[k] ?? 0) + 1; return a }, {})
  return (
    <Section title="NemoClaw 과정 모듈 체크리스트" sub="NVIDIA DLI 'Securing Agents with NemoClaw and OpenShell' 01a–04c를 FlyGate의 어디에 적용했는지"
      right={<div className="row" style={{ gap: 6 }}>{Object.entries(STATUS).filter(([k]) => counts[k]).map(([k, s]) => <span key={k} className="chip" style={{ color: s.c }}>{s.t} {counts[k]}</span>)}</div>}>
      <table className="tbl">
        <thead><tr><th style={{ width: 52 }}>모듈</th><th>주제 · FlyGate 적용</th><th style={{ width: 84 }}>상태</th><th>위치</th></tr></thead>
        <tbody>
          {rows.map((r) => {
            const s = splitStatus(r.ours)
            return (
              <tr key={r.id}>
                <td className="mono" style={{ color: 'var(--text)' }}>{r.id}</td>
                <td><div>{r.title}</div>{s.rest && <div className="dim" style={{ fontSize: 11.5, lineHeight: 1.45 }}>{s.rest}</div>}</td>
                <td>{s.key ? <StatusChip k={s.key} /> : null}</td>
                <td className="mono dim" style={{ fontSize: 11, wordBreak: 'break-word' }}>{r.where}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </Section>
  )
}

function Trifecta({ t }: { t: AgentInfo['trifecta'] }) {
  const parts: [string, string, string | undefined][] = [
    ['비공개 데이터 접근', '#ff4fd8', t.private_data], ['신뢰할 수 없는 입력', '#ffb547', t.untrusted_input], ['외부 통신', '#37e6ff', t.external_comm],
  ]
  return (
    <Section title="치명적 삼박자와 차단" sub="세 조건이 한 에이전트에 모이면 데이터가 새어 나갈 수 있습니다. FlyGate가 각 조건을 어떻게 다루는지">
      <div className="grid g3" style={{ gap: 10 }}>
        {parts.map(([k, c, v]) => (
          <div key={k} style={{ padding: '10px 12px', borderRadius: 11, border: '1px solid var(--line)', background: 'rgba(8,13,26,0.55)', boxShadow: `inset 3px 0 0 ${c}` }}>
            <div className="mono" style={{ fontSize: 10.5, color: c, letterSpacing: 0.6 }}>{k}</div>
            <div style={{ fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.5, marginTop: 4 }}>{v ?? '–'}</div>
          </div>
        ))}
      </div>
      {t.mediation && (
        <div style={{ marginTop: 10, padding: '10px 12px', borderRadius: 11, border: '1px solid rgba(226,167,78,0.45)', background: 'rgba(226,167,78,0.07)' }}>
          <div className="mono" style={{ fontSize: 10.5, color: '#e2a74e', letterSpacing: 0.6 }}>차단 · OpenShell 정책과 사람 승인</div>
          <div style={{ fontSize: 12.5, color: 'var(--text)', lineHeight: 1.55, marginTop: 4 }}>{t.mediation}</div>
        </div>
      )}
    </Section>
  )
}

function Smoke({ s }: { s: AgentInfo['smoke'] }) {
  const results = s.results ?? []
  const ok = results.filter((r) => r.pass).length
  return (
    <Section title="라이브 점검 · OpenShell 샌드박스" sub={<>허용한 호스트는 열리고, 나머지 호스트와 시스템 경로 쓰기는 막히는지 샌드박스 안에서 확인한 결과입니다</>}
      right={results.length ? <span className={`chip ${ok === results.length ? 'ok' : 'warn'}`}>{ok}/{results.length} 통과</span> : undefined}>
      <div className="row wrap" style={{ gap: 6, marginBottom: 10 }}>
        <span className="chip">{s.ran ? '이 배포에서 실행' : '기록 인용'}</span>
        {s.when && <span className="chip">{s.when}</span>}
        {s.gateway && <span className="chip">gateway · {s.gateway}</span>}
        {s.sandbox && <span className="chip">sandbox · {s.sandbox}</span>}
      </div>
      {results.length > 0 && (
        <table className="tbl">
          <thead><tr><th>점검</th><th>기대</th><th>관측</th><th className="r">결과</th></tr></thead>
          <tbody>
            {results.map((r, i) => (
              <tr key={`${r.check}-${i}`}>
                <td style={{ color: 'var(--text)' }}>{r.check}</td>
                <td className="dim">{r.expect}</td>
                <td className="mono" title={String(r.observed ?? '')} style={{ fontSize: 11, wordBreak: 'break-word' }}>{clip(String(r.observed ?? ''), 72)}</td>
                <td className="r"><span className={`chip ${r.pass ? 'ok' : 'bad'}`} style={{ fontSize: 10.5, padding: '1px 8px' }}>{r.pass ? '통과' : '확인 필요'}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {s.source && <div className="note" style={{ marginTop: 8 }}>출처 · <span className="mono">{s.source}</span></div>}
    </Section>
  )
}

function Policy({ p }: { p: AgentInfo['policy'] }) {
  const [view, setView] = useState<'table' | 'yaml'>('table')
  const egress = p.egress ?? []
  return (
    <Section id="policy" title="OpenShell 정책" sub={<>기본은 모두 차단하고, 필요한 호스트만 바이너리 · 메서드 · 경로 단위로 엽니다 · <span className="mono">agent/policy/flygate.yaml</span></>}
      right={<div className="seg"><button className={view === 'table' ? 'on' : ''} onClick={() => setView('table')}>표로 보기</button><button className={view === 'yaml' ? 'on' : ''} onClick={() => setView('yaml')} disabled={!p.yaml}>YAML 원문</button></div>}>
      {view === 'yaml' && p.yaml ? <pre className="codebox" style={{ maxHeight: 560 }}>{p.yaml}</pre> : (
        <>
          <div className="mono dim" style={{ fontSize: 10.5, letterSpacing: 0.8, marginBottom: 6 }}>EGRESS 허용 목록 · {egress.length}개 호스트</div>
          <table className="tbl">
            <thead><tr><th>호스트</th><th style={{ width: 60 }}>포트</th><th style={{ width: 110 }}>메서드</th><th>경로</th><th>바이너리</th></tr></thead>
            <tbody>
              {egress.map((e, i) => (
                <tr key={`${e.host}-${i}`}>
                  <td className="mono" style={{ color: 'var(--text)' }}>{e.host}</td>
                  <td className="mono">{String(e.port ?? '')}</td>
                  <td>{arr(e.methods).map((m) => <span key={m} className="chip" style={{ fontSize: 10.5, padding: '1px 7px', marginRight: 4 }}>{m}</span>)}</td>
                  <td className="mono" style={{ fontSize: 11, lineHeight: 1.55 }}>{arr(e.paths).map((x) => <div key={x}>{x}</div>)}</td>
                  <td className="mono dim" style={{ fontSize: 11, lineHeight: 1.55 }}>{arr(e.binaries).map((x) => <div key={x}>{x}</div>)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="grid g3" style={{ gap: 12, marginTop: 14 }}>
            {([['읽기 전용 경로', arr(p.filesystem?.read_only), 'var(--text-2)'], ['읽기 · 쓰기 경로', arr(p.filesystem?.read_write), '#e2a74e']] as [string, string[], string][]).map(([k, v, c]) => (
              <div key={k} style={{ padding: '10px 12px', borderRadius: 11, border: '1px solid var(--line)', background: 'rgba(8,13,26,0.5)' }}>
                <div className="mono dim" style={{ fontSize: 10.5, letterSpacing: 0.8 }}>LANDLOCK · {k}</div>
                <div className="mono" style={{ fontSize: 11.5, lineHeight: 1.65, marginTop: 4, color: c }}>{v.length ? v.map((x) => <div key={x}>{x}</div>) : '–'}</div>
              </div>
            ))}
            <div style={{ padding: '10px 12px', borderRadius: 11, border: '1px solid var(--line)', background: 'rgba(8,13,26,0.5)' }}>
              <div className="mono dim" style={{ fontSize: 10.5, letterSpacing: 0.8 }}>프로세스</div>
              <div style={{ fontSize: 12.5, lineHeight: 1.7, marginTop: 4 }}>
                <div>실행 사용자 <span className="mono" style={{ color: 'var(--text)' }}>{p.process?.user ?? '–'}</span></div>
                <div>seccomp <span className="mono" style={{ color: 'var(--text)' }}>{typeof p.process?.seccomp === 'boolean' ? (p.process.seccomp ? '적용' : '미적용') : (p.process?.seccomp ?? '–')}</span></div>
              </div>
            </div>
          </div>
        </>
      )}
    </Section>
  )
}

function Workspace({ files, skills }: { files: AgentInfo['workspace']; skills: AgentInfo['skills'] }) {
  const [sel, setSel] = useState(0)
  const f = files[Math.min(sel, files.length - 1)]
  const stages = skills.reduce<Record<string, AgentInfo['skills']>>((a, s) => { (a[s.stage || '공통'] ??= []).push(s); return a }, {})
  return (
    <Section title="OpenClaw 워크스페이스" sub="에이전트가 세션마다 읽는 파일입니다. 성격 · 작업 규칙 · 도구 · 하트비트 점검 목록 · 기억을 파일로 둡니다">
      {files.length > 0 && (
        <>
          <div className="tabs" style={{ marginBottom: 8 }}>
            {files.map((x, i) => <button key={x.file} className={i === sel ? 'on' : ''} onClick={() => setSel(i)}>{x.file}</button>)}
          </div>
          {f && <div style={{ fontSize: 12.5, color: 'var(--text-2)', marginBottom: 6 }}>{f.role}</div>}
          {f && <pre className="codebox" style={{ maxHeight: 380 }}>{f.content}</pre>}
        </>
      )}
      {skills.length > 0 && (
        <>
          <div className="divider" />
          <div className="row between" style={{ marginBottom: 6 }}>
            <span className="mono dim" style={{ fontSize: 10.5, letterSpacing: 0.8 }}>AGENT SKILLS · {skills.length}개</span>
            <a href="#/skills" style={{ fontSize: 12, textDecoration: 'none' }}>스킬 · 거버넌스 →</a>
          </div>
          <div className="stack" style={{ gap: 6 }}>
            {Object.entries(stages).map(([st, list]) => (
              <div key={st} className="row wrap" style={{ gap: 6 }}>
                <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-3)', minWidth: 86 }}>{st}</span>
                {list.map((s) => <span key={s.name} className="chip nv" title={s.description} style={{ fontSize: 10.5 }}>{s.name}</span>)}
              </div>
            ))}
          </div>
        </>
      )}
    </Section>
  )
}

function Triggers({ rows, cli }: { rows: AgentInfo['triggers']; cli: AgentInfo['cli'] }) {
  return (
    <div className="stack" style={{ gap: 16 }}>
      {rows.length > 0 && (
        <Section title="작업을 시작하는 방법" sub="사람의 메시지 말고도 하트비트, 예약 실행(cron), 하위 에이전트가 일을 시작합니다">
          <table className="tbl">
            <thead><tr><th>이름</th><th>트리거</th><th>세션</th><th>지시</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.name}>
                  <td style={{ color: 'var(--text)', whiteSpace: 'nowrap' }}>{r.name}</td>
                  <td className="mono" style={{ fontSize: 11 }}>{r.trigger}</td>
                  <td className="mono dim" style={{ fontSize: 11 }}>{r.session}</td>
                  <td style={{ fontSize: 12, color: 'var(--text-2)' }}>{r.directive}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}
      {cli.length > 0 && (
        <Section title="flygate CLI" sub="에이전트가 도구로 부르는 명령입니다. 모두 근거 ID가 붙은 JSON을 돌려줍니다">
          <table className="tbl">
            <thead><tr><th>명령</th><th>하는 일</th></tr></thead>
            <tbody>
              {cli.map((c) => (
                <tr key={c.cmd}>
                  <td className="mono" style={{ fontSize: 11.5, color: '#c8f36b', wordBreak: 'break-word' }}>{c.cmd}</td>
                  <td style={{ fontSize: 12, color: 'var(--text-2)' }}>{c.what}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}
    </div>
  )
}

export default function Agent() {
  const [data, setData] = useState<AgentInfo | null>(null)
  const [missing, setMissing] = useState(false)
  useEffect(() => {
    getJSON<AgentInfo>('/data/agent.json')
      .then((d) => (d && typeof d === 'object' ? setData(d) : setMissing(true)))
      .catch(() => setMissing(true))
  }, [])

  const stack = data?.stack ?? []
  const files = data?.workspace ?? []
  const skills = data?.skills ?? []

  return (
    <div className="page">
      <PageHead eyebrow="에이전트 · NemoClaw · OpenShell · OpenClaw"
        title={<>두 워크플로를 <span style={{ color: '#e2a74e' }}>샌드박스 안의 에이전트 하나</span>로 돌립니다</>}
        lede={<>NVIDIA NemoClaw 과정의 네 층 구조를 그대로 따릅니다. OpenClaw 하네스가 워크스페이스 파일과 Agent Skills로 STEP 1 FlyDiscovery와
          STEP 2 FlyVigilance를 실행하고, OpenShell 샌드박스는 정책이 허용한 호스트 · 경로 · 시스템 호출만 통과시키며, NemoClaw 블루프린트가 둘을 한 벌로 구성합니다.
          보고와 인과성의 최종 판정은 사람이 합니다.</>}
        right={<div className="stack" style={{ gap: 8, alignItems: 'flex-end' }}>
          <a className="btn ghost" href={IMG} target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>구성도 이미지 ↗</a>
          <div className="row" style={{ gap: 8 }}>
            <a className="btn ghost" href={`${REPO}/tree/main/agent`} target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>agent/</a>
            <a className="btn ghost" href={`${REPO}/blob/main/docs/AGENT.md`} target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>AGENT.md</a>
          </div>
        </div>} />

      <Card style={{ marginBottom: 16, padding: '16px 16px 12px' }}>
        <AgentDiagram files={files.map((f) => f.file)} skills={skills.length || undefined} />
      </Card>

      {stack.length > 0 && (
        <div className="grid g4" style={{ marginBottom: 16 }}>
          {stack.map((s, i) => (
            <div key={s.layer} className="card" style={{ padding: '12px 14px', boxShadow: `var(--shadow), inset 3px 0 0 ${['#76b900', '#76b900', '#e2a74e', '#76b900'][i] ?? '#4d8dff'}` }}>
              <div className="mono dim" style={{ fontSize: 10.5, letterSpacing: 0.8 }}>{['①', '②', '③', '④'][i] ?? ''} {s.layer}</div>
              <div style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.45, marginTop: 3 }}>{s.what}</div>
              <div style={{ fontSize: 12.5, color: 'var(--text)', lineHeight: 1.5, marginTop: 6 }}>{s.ours}</div>
            </div>
          ))}
        </div>
      )}

      {missing ? (
        <Card title="에이전트 구성 데이터" sub="/data/agent.json">
          <div className="note">
            <span className="mono">agent/export_agent_json.py</span>가 워크스페이스 파일, OpenShell 정책, 트리거, CLI, 라이브 점검 결과를 이 파일로 내보냅니다.
            파일이 준비되면 이 자리에 모듈 체크리스트와 정책 뷰어가 나타납니다. 구성도와 정책 원문은 저장소의 <a href={`${REPO}/tree/main/agent`} target="_blank" rel="noreferrer">agent/</a>에 있습니다.
          </div>
        </Card>
      ) : !data ? <Loading /> : (
        <div className="stack" style={{ gap: 16 }}>
          <div className="grid g2" style={{ alignItems: 'stretch' }}>
            {(data.modules ?? []).length > 0 ? <Modules rows={data.modules} /> : <div />}
            <div className="stack" style={{ gap: 16 }}>
              {data.trifecta && <Trifecta t={data.trifecta} />}
              {data.smoke && <Smoke s={data.smoke} />}
            </div>
          </div>
          {data.policy && <Policy p={data.policy} />}
          <div className="grid g2" style={{ alignItems: 'start' }}>
            {(files.length > 0 || skills.length > 0) ? <Workspace files={files} skills={skills} /> : <div />}
            <Triggers rows={data.triggers ?? []} cli={data.cli ?? []} />
          </div>
          {data.generated && <div className="note" style={{ textAlign: 'right' }}>생성 {data.generated} · <span className="mono">agent/export_agent_json.py</span></div>}
        </div>
      )}
    </div>
  )
}
