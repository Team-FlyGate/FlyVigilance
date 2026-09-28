import { useState } from 'react'
import { Card, PageHead } from '../components/ui'
import './CliTutorial.css'
import Term from '../components/Term'

const REPO = 'https://github.com/Team-FlyGate/Project-FlyGate'
const steps = ['준비하기', '첫 명령 실행', '결과 읽기', '새 도킹 실행']
const commands = [
  { name: 'discover', tag: '저장 결과 + 실시간 도킹', title: '후보물질 근거 살펴보기', cmd: 'flygate discover parp1', what: '저장된 근거를 조회하거나 --live로 단백질과 리간드를 NVIDIA DiffDock에 보내 새 포즈를 계산합니다.', need: '저장 결과 조회는 키가 필요 없습니다. --live는 NVIDIA_API_KEY, 네트워크, 단백질 PDB와 리간드 입력이 필요합니다. 위 4단계에 실행 예제가 있습니다.', read: '저장 결과는 candidates, 새 실행은 status와 poses를 봅니다. completed이면 run_dir 안에 포즈 SDF와 response.json이 저장됩니다. evidence_ids로 실행 결과를 식별합니다.' },
  { name: 'signals', tag: '저장 데이터', title: '이상사례 통계 조회', cmd: 'flygate signals NIRAPARIB --limit 5', what: '니라파립과 함께 보고된 이상반응의 불균형 지표를 조회합니다.', need: 'CLI 설치 필요. 저장소의 통계 추출본을 사용하며 API 키는 필요 없습니다.', read: 'rows의 prr, ror025, ic025와 sdr을 봅니다. 보고의 연관성이며 인과관계나 발생률을 뜻하지 않습니다.' },
  { name: 'triage', tag: '온라인 · Jev', title: '보고 한 건의 검토 경로 정하기', cmd: 'flygate triage agent/examples/case_niraparib.json --no-outcome', what: '예제 보고를 읽고 규칙·라벨·7문항 판단을 거쳐 검토 경로를 정합니다.', need: '네트워크와 TYPESAFE_API_KEY. 키가 없으면 규칙 기반 결과와 사람 검토 경로로 돌아갈 수 있습니다.', read: 'decision.action과 reasons를 확인하세요. --no-outcome은 평가용 결과 코드를 판단에서 숨깁니다. 보고서를 제출하지 않습니다.' },
  { name: 'grade', tag: '온라인 · 근거 조회', title: '약물–반응 쌍의 근거 모으기', cmd: 'flygate grade NIRAPARIB thrombocytopenia', what: '혈소판감소증(thrombocytopenia)에 대해 통계, 허가 라벨, 문헌을 모읍니다.', need: '외부 자료 조회에 네트워크가 필요합니다. Jev 판단·NVIDIA 재정렬을 사용하려면 해당 키를 설정합니다.', read: 'pv_class_name, review_priority, gaps와 evidence_ids를 함께 봅니다. --no-judge로 Jev 문헌 판단을 끌 수 있지만, 전체 오프라인 모드는 아닙니다.' },
  { name: 'critic', tag: '오프라인 연습 가능', title: '주장이 근거를 넘는지 확인', cmd: 'flygate critic agent/examples/claims_niraparib.json --offline', what: '예제 주장을 근거 ID와 숫자에 대조합니다.', need: '--offline은 규칙 검사만 합니다. 전체 모델·가드 검사에는 두 API 키와 네트워크가 필요합니다.', read: 'verdict와 issues를 확인합니다. human_check는 사람이 확인해야 한다는 뜻이며, 전체 검증 통과를 의미하지 않습니다.' },
  { name: 'kr-causality', tag: '온라인 · 두 모델', title: '국내 보고를 구조화하고 평가', cmd: 'flygate kr-causality agent/examples/kr_report.txt --route', what: '한국어 예제 보고를 구조화하고 한국형 인과성 평가 항목을 채웁니다.', need: 'NVIDIA_API_KEY, TYPESAFE_API_KEY와 네트워크. --route는 한국 규정 모드의 검토 경로도 계산합니다.', read: 'items, missing, needs_review와 평가 결과를 함께 확인하세요. 최종 인과성 판정과 보고 제출은 사람이 합니다.' },
  { name: 'watch', tag: '로컬 파일 저장', title: '감시 목록을 정기 점검', cmd: 'flygate watch --memory-dir ./tutorial-memory', what: '감시 목록을 다시 계산하고 날짜별 메모와 사람 검토 대기열을 만듭니다.', need: '지정한 폴더에 메모·상태 파일을 씁니다. 기본은 오프라인이며 --online은 외부 조회를 켭니다.', read: 'review_queue와 memory_note를 확인합니다. 한 번 실행하는 명령입니다. 반복 실행은 별도의 cron 설정이 필요합니다.' },
]

function Code({ text, label = '터미널에 붙여넣기' }: { text: string; label?: string }) {
  const [status, setStatus] = useState('')
  async function copy() {
    try { await navigator.clipboard.writeText(text); setStatus('복사했습니다') }
    catch {
      const input = document.createElement('textarea'); input.value = text
      input.style.position = 'fixed'; input.style.opacity = '0'; document.body.appendChild(input)
      const previous = document.activeElement as HTMLElement | null
      input.select()
      let copied = false
      try { copied = document.execCommand('copy') } catch { /* Manual selection remains available. */ }
      input.remove(); previous?.focus()
      setStatus(copied ? '복사했습니다' : '복사할 수 없습니다. 아래 명령을 직접 선택해 주세요.')
    }
  }
  return <div className="cli-code"><div className="cli-code-head"><span>{label}</span><button className="btn ghost" onClick={copy} aria-label={`${label} 복사`}>복사</button></div><pre tabIndex={0}><code>{text}</code></pre><span className="cli-copy-status" role="status">{status}</span></div>
}

export default function CliTutorial() {
  const [step, setStep] = useState(0)
  const [selected, setSelected] = useState('discover')
  const [target, setTarget] = useState('parp1')
  const [filter, setFilter] = useState('')
  const command = commands.find(c => c.name === selected)!
  const visible = commands.filter(c => `${c.name} ${c.title} ${c.what}`.toLowerCase().includes(filter.toLowerCase()))
  return <div className="page cli-tutorial">
    <PageHead eyebrow="AGENT TOOLKIT / FLYGATE CLI / GUIDE v1.0.0" title={<>한 줄로 시작하는 <span className="cli-accent">근거 탐색</span></>} lede="터미널이 처음이어도 괜찮습니다. 명령을 복사하고, 결과에서 무엇을 읽어야 하는지 차례로 살펴보세요. 저장된 결과 조회부터 NVIDIA API를 통한 새 도킹까지 안내합니다." right={<a className="btn ghost" href="#/agent">에이전트 구성 보기 ↗</a>} />
    <section className="cli-hero">
      <div><span className="cli-kicker">YOUR FIRST COMMAND</span><h2>질문은 짧게.<br />근거는 따라갈 수 있게.</h2><p>명령줄 인터페이스(Command-Line Interface, CLI)는 글로 누르는 버튼입니다. FlyGate CLI는 후보 탐색과 약물감시 기능을 한곳에 모은 리모컨처럼 작동합니다.</p><div className="cli-badges"><span>01 설치</span><span>02 실행</span><span>03 근거 읽기</span></div></div>
      <div className="cli-terminal"><div className="cli-terminal-top"><i /><i /><i /><span>LOCAL TERMINAL</span></div><code><span>$</span> flygate discover parp1</code><p>PARP1 후보 → 저장된 실측 → 근거 ID</p><div className="cli-terminal-note">이 페이지는 사용 안내입니다.<br />복사는 명령을 실행하지 않습니다.</div></div>
    </section>
    <div className="cli-concepts"><div><b>NVIDIA <Term k="NemoClaw" /></b><span>배포·관리 기반</span></div><span>→</span><div><b><Term k="OpenClaw" /> + <Term k="OpenShell" /></b><span>에이전트 실행 + 격리·정책</span></div><span>→</span><div><b>FlyGate CLI</b><span>팀이 개발한 분석 도구</span></div></div>
    <Card title="처음부터 따라 하기" sub="Mac·Linux 터미널 또는 Windows WSL의 bash/zsh 기준입니다. 명령은 한 블록씩 실행하세요." className="cli-guide">
      <div className="cli-steps" role="tablist" aria-label="튜토리얼 단계">{steps.map((s, i) => <button key={s} role="tab" id={`cli-tab-${i}`} aria-selected={step === i} aria-controls="cli-step-panel" tabIndex={step === i ? 0 : -1} onKeyDown={e => {
        const next = e.key === 'ArrowRight' ? (i + 1) % 4 : e.key === 'ArrowLeft' ? (i + 3) % 4 : e.key === 'Home' ? 0 : e.key === 'End' ? 3 : null
        if (next !== null) { e.preventDefault(); setStep(next); document.getElementById(`cli-tab-${next}`)?.focus() }
      }} className={step === i ? 'active' : ''} onClick={() => setStep(i)}><span>0{i + 1}</span>{s}</button>)}</div>
      <div id="cli-step-panel" role="tabpanel" aria-labelledby={`cli-tab-${step}`} className="cli-step-body">
        {step === 0 && <><h3>01 / 내 컴퓨터에 준비하기</h3><p>Mac은 ‘터미널’, Windows는 WSL의 Ubuntu 터미널을 여세요. Python 3.10 이상과 Git이 필요합니다. 아래 명령은 설치 여부와 버전을 보여 줍니다.</p><Code text={'python3 --version\ngit --version'} label="준비 상태 확인" /><p>코드 저장소를 내 컴퓨터로 내려받고 그 폴더로 이동합니다. 이미 받은 저장소가 있다면 해당 폴더를 열면 됩니다.</p><Code text={'git clone https://github.com/Team-FlyGate/Project-FlyGate.git\ncd Project-FlyGate'} label="저장소 받기" /><p>설치 스크립트는 프로젝트 전용 Python 환경(.venv)과 필요한 패키지를 만들고, 사용자 폴더에 flygate 명령을 연결합니다.</p><Code text={'./scripts/install_flygate.sh\nexport PATH="$HOME/.local/bin:$PATH"\nflygate --help'} label="CLI 설치 및 도움말 확인" /><div className="cli-tip">성공하면 triage, grade, signals 등 7개 명령 목록이 나옵니다. export 줄은 현재 터미널에 명령의 위치를 알려 줍니다. 첫 실습에는 API 키나 전체 FAERS 데이터 다운로드가 필요 없습니다.</div></>}
        {step === 1 && <><h3>02 / 저장된 후보 탐색 결과 읽기</h3><p>설치를 마쳤다면 표적을 고르고 명령을 복사하세요. 모든 예제는 저장소의 최상위 폴더에서 실행합니다.</p><label className="cli-select">살펴볼 표적<select value={target} onChange={e => setTarget(e.target.value)}><option value="parp1">PARP1 · 니라파립 예제</option><option value="xa">Factor Xa</option><option value="cox2">COX-2</option></select></label><Code text={`flygate discover ${target}`} /><p>여러 줄의 JSON이 나오면 정상입니다. JSON은 ‘항목 이름: 값’으로 구성된 결과표이며, 사람과 프로그램이 같은 결과를 읽을 수 있게 합니다.</p><div className="cli-tip"><strong>이 실습이 하는 일</strong><br />이미 계산해 둔 실측과 검증 결과를 불러옵니다. 새로운 구조 예측·도킹·모델 호출은 실행하지 않습니다.</div><h4>결과를 파일로 보관하려면</h4><Code text={`flygate discover ${target} > discovery-result.json`} label="JSON 파일 저장" /><p className="note">현재 폴더에 파일을 만듭니다. 같은 이름의 파일이 있으면 덮어쓰므로 다른 이름을 사용하세요.</p></>}
        {step === 2 && <><h3>03 / 숫자보다 먼저, 출처를 읽기</h3><p>긴 출력 전체를 한 번에 이해할 필요는 없습니다. 아래는 구조를 설명하기 위해 줄인 예시입니다.</p><Code label="출력 구조 예시 · 실행 명령이 아닙니다" text={'{\n  "cmd": "discover",\n  "candidates": [\n    { "ligand": "Niraparib",\n      "evidence_ids": ["vina:parp1/Niraparib"] }\n  ]\n}'} /><dl className="cli-fields"><div><dt>cmd</dt><dd>어떤 명령의 결과인지 확인합니다. 영수증의 거래 종류와 같습니다.</dd></div><div><dt>candidates</dt><dd>비교할 후보 목록입니다. 후보별 예측값과 실험 참조값을 구분해 읽습니다.</dd></div><div><dt>evidence_ids</dt><dd>근거를 다시 찾기 위한 식별자입니다. 참고문헌 번호처럼 출처를 가리키지만, ID가 있다는 사실만으로 결론이 옳아지는 것은 아닙니다.</dd></div><div><dt>decision / verdict</dt><dd>다른 명령에서 나오는 경로·검증 결과입니다. human_check와 human_review는 사람이 확인해야 한다는 뜻입니다.</dd></div></dl><div className="cli-tip">도킹 점수는 약효 입증이 아니고, 이상사례 통계는 인과관계 확정이 아닙니다. 숫자와 함께 원자료·비교 조건·검토 사유를 읽어 주세요.</div></>}
        {step === 3 && <><h3>04 / NVIDIA DiffDock으로 새 도킹 실행하기</h3><p>단백질 구조와 <Term k="ligand">리간드</Term>(단백질에 붙는 약물 분자)를 NVIDIA <Term k="DiffDock" /> <Term k="NIM" ko />에 보내 새로운 결합 <Term k="pose">포즈</Term>(붙는 위치와 자세)를 계산합니다. API 키는 서비스 이용 자격 증명이며, 연결된 계정의 사용량·비용이 발생할 수 있습니다.</p><p>코드 편집기에서 저장소 최상위 폴더의 <code>.env</code> 파일을 열어 NVIDIA_API_KEY를 설정하세요. TYPESAFE_API_KEY는 이후 Jev 기반 약물감시 명령을 사용할 때 필요하며, 도킹에는 필요 없습니다. 기존 파일이 있으면 다른 설정을 지우지 말고 해당 항목만 수정합니다.</p><Code label=".env 파일 형식 · 실제 값은 개인 편집기에서 입력" text={'TYPESAFE_API_KEY=<YOUR_TYPESAFE_API_KEY>\nNVIDIA_API_KEY=<YOUR_NVIDIA_API_KEY>'} /><p>키는 이 웹사이트에 입력하지 않습니다. .env는 GitHub에 올리지 마세요. 설정 후 새 CLI 명령을 실행하면 파일을 읽습니다.</p><p>저장소에 포함된 <Term k="PARP1" /> 예측 구조와 니라파립 <Term k="SMILES" />(분자를 한 줄로 표현한 문자열)로 첫 도킹을 실행해 보세요. 이 명령은 실제 API 요청을 보냅니다.</p><Code text="flygate discover --live --protein fly_discovery/measurements/nim/of3_parp1_niraparib.pdb --ligand-file agent/examples/niraparib.smi --num-poses 5 --timeout 300" label="새 도킹 실행 · NVIDIA API 사용" />
          <dl className="cli-fields"><div><dt>--protein</dt><dd>단백질 <Term k="PDB">PDB</Term>(단백질 3차원 구조) 파일 경로입니다. 자신의 구조 파일로 바꿀 수 있습니다.</dd></div><div><dt>--ligand-file</dt><dd>한 분자의 <Term k="SDF" /> 또는 <Term k="SMILES" /> 파일입니다. --smiles 옵션으로 문자열을 직접 지정할 수도 있습니다.</dd></div><div><dt>--num-poses</dt><dd>계산할 결합 포즈 수입니다. 1~20개 중 선택합니다.</dd></div><div><dt>status / run_dir</dt><dd>completed이면 완료입니다. 출력된 폴더에서 pose_01.sdf, response.json, manifest.json을 확인합니다. pending이면 같은 작업을 이어서 조회합니다.</dd></div></dl>
          <Code text={'flygate discover --resume data/discovery-runs/<출력된_run_id>'} label="대기 중인 요청 이어서 조회 · 경로를 바꿔 주세요" />
          <p>실행마다 새 폴더를 만들어 입력·출력·근거 ID를 보존합니다. 통신 중단 시 새 작업을 자동 제출하지 않습니다. 신뢰도는 포즈에 대한 모델 점수이며 친화도 측정값과는 다릅니다.</p>
          <h4>다음 실습: 약물감시</h4><Code text={'flygate triage agent/examples/case_niraparib.json --no-outcome'} label="예제 보고 분류" /><p><code>decision.action</code>은 다음 처리 경로, <code>decision.reasons</code>는 그 이유입니다. 예제 파일은 저장소에 포함되어 있습니다.</p><div className="cli-tip">키가 없거나 모델을 사용할 수 없으면 명령에 따라 오류·제한 모드·사람 확인 결과가 나올 수 있습니다. ‘모델 미실행’을 ‘검증 통과’로 해석하지 마세요.</div><p><a href="https://build.nvidia.com" target="_blank" rel="noreferrer">NVIDIA API 서비스 ↗</a> · <a href="https://www.typesafe.ai" target="_blank" rel="noreferrer">TypeSafe AI ↗</a></p></>}
      </div>
      <div className="cli-step-footer"><button className="btn ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>← 이전</button><span aria-live="polite">{step + 1} / {steps.length}</span><button className="btn" disabled={step === 3} onClick={() => setStep(step + 1)}>다음 단계 →</button></div>
    </Card>
    <Card title="내가 하려는 일로 명령 찾기" sub="각 명령의 준비물과 결과 읽는 방법을 함께 확인하세요." className="cli-catalog"><label className="cli-search">명령 검색<input value={filter} onChange={e => setFilter(e.target.value)} placeholder="예: 문헌, 보고, discover" /></label><div className="cli-catalog-grid"><div className="cli-command-list">{visible.map(c => <button key={c.name} aria-pressed={selected === c.name} className={selected === c.name ? 'active' : ''} onClick={() => setSelected(c.name)}><code>{c.name}</code><span>{c.title}</span></button>)}{!visible.length && <p role="status">일치하는 명령이 없습니다. 다른 단어로 검색해 주세요.</p>}</div><div className="cli-command-detail"><span className="chip">{command.tag}</span><h3>{command.title}</h3><p>{command.what}</p><Code text={command.cmd} label={`${command.name} 예제`} /><h4>실행 전에</h4><p>{command.need}</p><h4>결과에서 볼 것</h4><p>{command.read}</p><Code text={`flygate ${command.name} --help`} label="이 명령의 전체 옵션 확인" /></div></div></Card>
    <Card title="막혔을 때 확인할 것" className="cli-faq">{[
      ['command not found: flygate', '명령 위치를 못 찾은 상태입니다. 위 설치 단계의 export PATH 줄을 다시 실행하세요. 저장소 폴더에서는 ./agent/bin/flygate --help로도 확인할 수 있습니다.'],
      ['python3 또는 git을 찾을 수 없어요', '첫 단계의 준비 도구가 없습니다. python.org와 git-scm.com의 운영체제별 설치 안내를 따라 설치한 뒤 터미널을 새로 여세요. Windows PowerShell 대신 WSL 터미널을 사용합니다.'],
      ['No such file / 파일을 찾을 수 없어요', '현재 위치가 Project-FlyGate 최상위 폴더인지 확인하세요. 그 안에 agent와 scripts 폴더가 보여야 합니다. 예제 경로는 이 위치를 기준으로 합니다.'],
      ['ModuleNotFoundError', '필요한 Python 패키지가 없거나 다른 Python 환경으로 실행했을 수 있습니다. ./scripts/install_flygate.sh를 실행한 뒤 flygate 명령으로 다시 시도하세요.'],
      ['401·403, not configured, human_check', '키 누락·권한 문제·검사 미실행을 구분해야 합니다. 오류 메시지와 .env 항목 이름, 서비스 이용 가능 상태를 확인하세요. 사람 확인 표시는 검증 통과가 아닙니다.'],
      ['실행이 오래 걸리거나 429가 나와요', '라벨·문헌 조회와 모델 응답에는 시간이 걸립니다. 429는 요청량 제한일 수 있습니다. 연속 재시도 대신 서비스 상태와 할당량을 확인하세요.'],
      ['전체 데이터나 NemoClaw 설치도 필요한가요?', '첫 discover 실습에는 필요 없습니다. 전체 FAERS 재현은 별도 데이터 다운로드가 필요합니다. NemoClaw 배포는 CLI를 에이전트의 도구로 쓰는 다음 단계이며, 에이전트 문서에서 안내합니다.'],
    ].map(([q,a]) => <details key={q}><summary>{q}</summary><p>{a}</p></details>)}</Card>
    <footer className="cli-source"><span>이제 근거를 직접 살펴볼 준비가 됐습니다.</span><div><a href={`${REPO}/blob/main/agent/flygate.py`} target="_blank" rel="noreferrer">CLI 구현 ↗</a><a href={`${REPO}/blob/main/docs/AGENT.md`} target="_blank" rel="noreferrer">에이전트 배포 안내 ↗</a><a href="#/discovery">FlyDiscovery 화면 →</a></div></footer>
  </div>
}
