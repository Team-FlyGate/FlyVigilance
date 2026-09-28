import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { Card } from './ui'
import Term from './Term'
import { t } from '../lib/i18n'

// FlyGate Agent CLI 쇼케이스: 한 줄 설치(복사 버튼), 실제 터미널 캡처 갤러리(누르면 크게 보기), 사람·에이전트 같은 명령 띠.
// 대시보드의 기존 디자인 체계(Card, index.css 토큰)를 그대로 씁니다.
// 캡처 이미지는 web/public/cli/captures/*.png 이고, 명령·시각·종료 코드는 web/public/cli/captures.json 에서 읽습니다.

interface Capture { name: string; cmd: string; cmds: string[]; file: string; w: number; h: number; captured_at_utc: string; exit_code: number; note: string }

const INSTALL = 'git clone https://github.com/Team-FlyGate/Project-FlyGate && cd Project-FlyGate && ./scripts/install_flygate.sh'

// 화면에 보이는 짧은 이름과 설명입니다. 순서는 매니페스트와 같습니다. 언어에 따라 바뀌므로 렌더할 때 만듭니다.
const getShots = (): { name: string; word: string; title: string; gist: ReactNode }[] => [
  { name: 'install', word: 'install', title: t('설치', 'Install'), gist: t(<>새로 클론한 저장소에서 설치 스크립트를 돌리고 <code>flygate --help</code>로 하위 명령 9개를 확인합니다.</>, <>Runs the install script in a freshly cloned repository and lists the 9 subcommands with <code>flygate --help</code>.</>) },
  { name: 'triage', word: 'triage', title: t('사례 분류', 'Case triage'), gist: t(<>이상사례 보고(<Term k="ICSR">ICSR</Term>) 한 건의 검토 경로와 기한을 정하고 라벨 근거를 붙입니다.</>, <>Sets the review route and deadline for one adverse-event report (<Term k="ICSR">ICSR</Term>, individual case safety report) and attaches label evidence.</>) },
  { name: 'grade', word: 'grade', title: t('근거 등급', 'Evidence grade'), gist: t(<>허가 라벨, 불균형 보고 신호(<Term k="SDR">SDR</Term>), 문헌을 모아 등급 B와 근거 ID 9개를 냅니다.</>, <>Combines the approved label, the signal of disproportionate reporting (<Term k="SDR">SDR</Term>) and literature into grade B with 9 evidence IDs.</>) },
  { name: 'critic', word: 'critic', title: t('크리틱', 'Critic'), gist: t(<>근거를 넘는 주장을 3단 검사와 안전 가드 모델로 걸러 반려합니다.</>, <>Rejects claims that go beyond the evidence, using a three-stage check and a safety guard model.</>) },
  { name: 'discover_live', word: 'discover', title: t('실시간 도킹', 'Live docking'), gist: t(<>PARP1 구조와 니라파립을 <Term k="DiffDock" /> <Term k="NIM">NIM</Term>에 새로 보내 포즈 5개를 받습니다.</>, <>Sends the PARP1 structure and niraparib to the <Term k="DiffDock" /> <Term k="NIM">NIM</Term> (NVIDIA Inference Microservice) and receives 5 new poses.</>) },
  { name: 'kr_causality', word: 'kr-causality', title: t('국내 인과성', 'Korean causality'), gist: t(<>한국어 서술 보고를 구조화하고 한국형 인과성 알고리즘으로 11점, ‘가능성 높음’을 매깁니다.</>, <>Structures a Korean-language narrative report and scores it 11 points, “probable”, with the Korean causality assessment algorithm.</>) },
  { name: 'watch', word: 'watch', title: t('하트비트', 'Heartbeat'), gist: t(<>감시 목록 10쌍을 다시 계산하고 메모를 남깁니다. 아무것도 제출하지 않습니다.</>, <>Recomputes the 10 drug–event pairs on the watchlist and leaves a note. Nothing is submitted.</>) },
]

// captures.json 의 설명(note)은 한국어라 영어 화면에서는 이 표로 바꿔 보여 드립니다.
const NOTE_EN: Record<string, string> = {
  install: 'Cloned fresh into an empty home directory, ran the install script, then ran flygate --help.',
  triage: 'Reflex triage of a single case. Key fields selected from the full JSON with jq.',
  grade: 'Evidence grade for a drug–adverse event pair. Key fields selected with jq.',
  critic: 'Result of passing 6 claims through the three-stage critique and the safety guard.',
  discover_live: 'A real run that submitted a new job to the DiffDock NIM (PARP1 OpenFold3 structure + niraparib).',
  kr_causality: 'A Korean-language narrative report structured and scored with the Korean causality assessment algorithm v2.0.',
  watch: 'Heartbeat job. Recomputes the watchlist and writes a dated note. Nothing is submitted.',
}

function CopyLine({ text, label }: { text: string; label: string }) {
  const [status, setStatus] = useState('')
  async function copy() {
    try { await navigator.clipboard.writeText(text); setStatus(t('복사했습니다', 'Copied')) }
    catch {
      const ta = document.createElement('textarea'); ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0'
      document.body.appendChild(ta); ta.select()
      let ok = false
      try { ok = document.execCommand('copy') } catch { /* 직접 선택할 수 있습니다 */ }
      ta.remove(); setStatus(ok ? t('복사했습니다', 'Copied') : t('복사하지 못했습니다. 명령을 직접 선택해 주세요.', 'Could not copy. Please select the command manually.'))
    }
    window.setTimeout(() => setStatus(''), 2400)
  }
  return (
    <div className="cls-install">
      <div className="cls-install-head"><span>{label}</span><span className="cls-install-status" role="status">{status}</span></div>
      <div className="cls-install-row">
        <pre tabIndex={0} aria-label={`${label}: ${text}`}><code><span className="cls-prompt" aria-hidden="true">$ </span>{text}</code></pre>
        <button className="btn cls-copy" onClick={copy} aria-label={t(`${label} 명령 복사`, `Copy command: ${label}`)}>{t('복사', 'Copy')}</button>
      </div>
    </div>
  )
}

function Lightbox({ caps, index, onClose, onMove }: { caps: Capture[]; index: number; onClose: () => void; onMove: (d: number) => void }) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const boxRef = useRef<HTMLDivElement>(null)
  const c = caps[index], s = getShots().find((x) => x.name === c.name)
  useEffect(() => { closeRef.current?.focus() }, [])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); onClose() }
      else if (e.key === 'ArrowRight') { e.preventDefault(); onMove(1) }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); onMove(-1) }
      else if (e.key === 'Tab') {
        const f = boxRef.current?.querySelectorAll<HTMLElement>('button, a[href], [tabindex="0"]')
        if (!f || !f.length) return
        const first = f[0], last = f[f.length - 1]
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
      }
    }
    window.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { window.removeEventListener('keydown', onKey); document.body.style.overflow = prev }
  }, [onClose, onMove])
  return (
    <div className="cls-lb" onClick={onClose}>
      <div ref={boxRef} className="cls-lb-box" role="dialog" aria-modal="true" aria-label={t(`${s?.title ?? c.name} 터미널 캡처 크게 보기`, `Enlarged terminal capture: ${s?.title ?? c.name}`)} onClick={(e) => e.stopPropagation()}>
        <div className="cls-lb-head">
          <div>
            <span className="cls-lb-count">{String(index + 1).padStart(2, '0')} / {String(caps.length).padStart(2, '0')}</span>
            <b>{s?.title}</b> <code>flygate {s?.word === 'install' ? '--help' : s?.word}</code>
          </div>
          <div className="cls-lb-nav">
            <button className="btn ghost" onClick={() => onMove(-1)} aria-label={t('이전 캡처', 'Previous capture')}>←</button>
            <button className="btn ghost" onClick={() => onMove(1)} aria-label={t('다음 캡처', 'Next capture')}>→</button>
            <button ref={closeRef} className="btn ghost" onClick={onClose} aria-label={t('닫기 (Esc)', 'Close (Esc)')}>{t('닫기', 'Close')}</button>
          </div>
        </div>
        <div className="cls-lb-img" tabIndex={0} aria-label={t('캡처 이미지. 길면 스크롤할 수 있습니다.', 'Capture image. Scroll if it is long.')}>
          <img src={`/${c.file}`} width={c.w / 2} height={c.h / 2} alt={t(`실제 실행 화면: ${c.cmds.join(' 다음 ')}`, `Actual run screen: ${c.cmds.join(', then ')}`)} />
        </div>
        <dl className="cls-lb-meta">
          <div><dt>{t('입력한 명령', 'Commands entered')}</dt><dd>{c.cmds.map((x) => <code key={x}>{x}</code>)}</dd></div>
          <div><dt>{t('실행 시각 (UTC)', 'Run time (UTC)')}</dt><dd>{c.captured_at_utc.replace('T', ' ').replace('Z', '')}</dd></div>
          <div><dt>{t('종료 코드', 'Exit code')}</dt><dd>{c.exit_code} {c.exit_code === 0 ? t('· 정상 종료', '· exited normally') : ''}</dd></div>
          <div><dt>{t('설명', 'Description')}</dt><dd>{t(c.note, NOTE_EN[c.name] ?? c.note)}</dd></div>
        </dl>
      </div>
    </div>
  )
}

export default function CliShowcase() {
  const [caps, setCaps] = useState<Capture[]>([])
  const [open, setOpen] = useState<number | null>(null)
  const opener = useRef<HTMLElement | null>(null)

  useEffect(() => {
    fetch('/cli/captures.json').then((r) => r.json()).then((d: { captures: Capture[] }) => {
      const order = getShots().map((s) => s.name)
      setCaps(d.captures.filter((c) => order.includes(c.name)).sort((a, b) => order.indexOf(a.name) - order.indexOf(b.name)))
    }).catch(() => setCaps([]))
  }, [])

  const n = caps.length
  const move = useCallback((d: number) => setOpen((o) => (o === null ? o : (o + d + n) % n)), [n])
  const close = useCallback(() => {
    // 크게 보기에서 넘긴 캡처가 있으면 지금 보던 캡처의 칸으로 초점을 돌려줍니다
    setOpen((o) => {
      window.setTimeout(() => (document.getElementById(`cls-shot-${o}`) ?? opener.current)?.focus(), 0)
      return null
    })
  }, [])
  const date = caps[0]?.captured_at_utc.slice(0, 10)
  const SHOTS = getShots()

  return (
    <div className="cls">
      <div className="grid g2 cls-top">
        <Card title={t('한 줄 설치', 'One-line install')} sub={t('Mac·Linux 터미널 또는 Windows WSL에서 붙여 넣으세요. 저장소를 받고 .venv 를 만든 뒤 ~/.local/bin/flygate 를 연결합니다.', 'Paste into a Mac or Linux terminal, or Windows WSL. It clones the repository, creates .venv and links ~/.local/bin/flygate.')} className="cls-install-card">
          <CopyLine text={INSTALL} label={t('설치 명령', 'Install command')} />
          <div className="row wrap cls-chips" aria-label={t('설치 조건', 'Requirements')}>
            <span className="chip">{t('Python 3.10 이상 · Git', 'Python 3.10+ · Git')}</span>
            <span className="chip nv">NVIDIA_API_KEY</span>
            <span className="chip jev">TYPESAFE_API_KEY ({t('선택', 'optional')})</span>
          </div>
          {t(<p className="cls-note">키는 저장소 루트의 <code>.env</code> 또는 OS 보안 저장소에서 읽고, 명령 인자로 받지 않습니다. 키가 없어도 도움말과 저장된 결과 조회는 됩니다. 판단 모델이 필요한 명령은 키가 없으면 ‘사람 확인’으로 돌립니다.</p>, <p className="cls-note">Keys are read from <code>.env</code> at the repository root or from the OS secure keychain, never from command arguments. Help and saved-result lookups work without keys. Commands that need the judgment model route to “human check” when keys are missing.</p>)}
        </Card>
        <Card title={t('사람도 에이전트도 같은 명령', 'Same commands for people and agents')} sub={t(<><Term k="OpenClaw" /> 에이전트는 exec 도구로 사람이 치는 것과 같은 flygate 명령을 실행합니다.</>, <>The <Term k="OpenClaw" /> agent runs, via its exec tool, the same flygate commands a person types.</>)} className="cls-same">
          <div className="cls-same-row">
            <div className="cls-same-cell">
              <span className="cls-same-who">{t('사람 · 터미널', 'Person · terminal')}</span>
              <code><i aria-hidden="true">$ </i>flygate grade NIRAPARIB thrombocytopenia</code>
            </div>
            <div className="cls-same-cell agent">
              <span className="cls-same-who">{t('OpenClaw 에이전트 · exec 도구 · ', 'OpenClaw agent · exec tool · ')}<Term k="OpenShell" /> {t('샌드박스', 'sandbox')}</span>
              <code><i aria-hidden="true">exec </i>/sandbox/flygate/agent/bin/flygate grade NIRAPARIB thrombocytopenia</code>
            </div>
            <div className="cls-same-cell out">
              <span className="cls-same-who">{t('둘 다 같은 JSON과 같은 근거 ID를 받습니다', 'Both receive the same JSON and the same evidence IDs')}</span>
              <code>"grade": "B", "evidence_ids": ["faers:2x2:NIRAPARIB:…", "label:…#warnings_and_cautions", "pubmed:…"]</code>
            </div>
          </div>
          {t(<p className="cls-note">그래서 에이전트가 쓴 요약의 <Term k="evidenceId">근거 ID</Term>를 사람이 터미널에서 같은 명령으로 다시 확인할 수 있습니다.</p>, <p className="cls-note">So a person can re-check every <Term k="evidenceId">evidence ID</Term> in an agent-written summary by running the same command in a terminal.</p>)}
        </Card>
      </div>

      <Card title={t(`실제 터미널 화면${n ? ` ${n}장` : ''}`, `Real terminal screens${n ? ` (${n})` : ''}`)}
        sub={t(<>빈 폴더에 저장소를 새로 클론하고 명령을 실제로 실행해 그 출력을 그대로 담았습니다{date ? ` (${date})` : ''}. 긴 <Term k="JSON" /> 출력은 명령줄에 보이는 jq 필터로 핵심 필드만 골랐습니다. 누르면 크게 봅니다.</>, <>We cloned the repository fresh into an empty folder, actually ran each command and captured the output unchanged{date ? ` (${date})` : ''}. For long <Term k="JSON" /> output, the jq filter shown on the command line selects the key fields. Click to enlarge.</>)}
        right={<span className="chip ev">evidence_ids</span>} className="cls-gallery-card">
        {!n && <p className="dim">{t('캡처를 불러오는 중입니다.', 'Loading captures…')}</p>}
        <ul className="cls-gallery">
          {caps.map((c, i) => {
            const s = SHOTS.find((x) => x.name === c.name)!
            return (
              <li key={c.name}>
                <button id={`cls-shot-${i}`} type="button" className="cls-shot" aria-label={t(`${s.title} 캡처 크게 보기: ${c.cmds[c.cmds.length - 1]}`, `Enlarge ${s.title} capture: ${c.cmds[c.cmds.length - 1]}`)}
                  onClick={(e) => { opener.current = e.currentTarget; setOpen(i) }}>
                  <span className="cls-thumb"><img src={`/${c.file}`} alt="" width={c.w / 2} height={c.h / 2} loading={i < 3 ? 'eager' : 'lazy'} decoding="async" /></span>
                  <span className="cls-shot-head"><span className="num">{String(i + 1).padStart(2, '0')}</span><b>{s.title}</b><code>{s.word === 'install' ? 'install · --help' : s.word}</code></span>
                </button>
                <p className="cls-gist">{s.gist}</p>
              </li>
            )
          })}
        </ul>
      </Card>
      {open !== null && caps[open] && <Lightbox caps={caps} index={open} onClose={close} onMove={move} />}
    </div>
  )
}
