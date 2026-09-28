import { useEffect, useState } from 'react'

const MEDIA = '/media/cli/v2.0.0'
const scenes = [
  { name: '시작', command: 'flygate', title: '연구를 시작하는 한 화면', detail: '모델·키 설정 상태와 분석 명령을 확인합니다. NVIDIA ✓와 Jev ✓는 키가 설정되어 있다는 표시입니다.', image: '01-start.png' },
  { name: '입력', command: '/discover parp1', title: '하고 싶은 일을 한 줄로', detail: '채팅창에 슬래시 명령을 입력합니다. 자연어 요청도 가능하며, 모델이 제안한 분석은 확인 후 실행합니다.', image: '02-command.png' },
  { name: '승인', command: '실행할까요? [y/N] → y', title: '실행할 내용을 먼저 확인', detail: '실제 실행 명령을 보고 승인합니다. 이 데모는 저장된 PARP1 근거를 조회하며 새 도킹 요청을 보내지 않습니다.', image: '03-approve.png' },
  { name: '결과', command: '/last', title: '결과에서 근거까지', detail: '후보별 결과와 evidence_ids가 출력됩니다. 전체 결과를 다시 읽으려면 /last를 입력하세요.', image: '04-result.png' },
]

// 실제 캡처 4장을 자동으로 넘깁니다. 마우스를 올리거나 초점을 두면 멈추고, 움직임 줄이기 설정이면 넘기지 않습니다
const INTERVAL = 4200

export default function CliExperience() {
  const [scene, setScene] = useState(0)
  const [paused, setPaused] = useState(false)
  useEffect(() => {
    const reduce = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
    if (paused || reduce) return
    const id = setInterval(() => setScene((k) => (k + 1) % scenes.length), INTERVAL)
    return () => clearInterval(id)
  }, [paused])
  return <>
    <section className="cli-launch">
      <div className="cli-launch-copy">
        <span className="cli-kicker">YOUR RESEARCH. ONE TERMINAL.</span>
        <h2>한 줄로 묻고.<br /><em>근거로</em> 이어가세요.</h2>
        <p>FlyDiscovery의 후보 탐색부터 FlyVigilance의 약물 안전성 평가까지. 대화와 일곱 개의 분석 명령을 하나의 터미널에서 만납니다.</p>
        <div className="cli-launch-command"><span>❯</span><code>flygate</code><small>입력하면 대화 시작</small></div>
        <div className="cli-launch-actions"><a className="btn" href="#cli-demo" onClick={e => { e.preventDefault(); document.getElementById('cli-demo')?.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }) }}>실제 화면 보기 ↓</a><a className="btn ghost" href="#cli-install" onClick={e => { e.preventDefault(); document.getElementById('cli-install')?.scrollIntoView({ behavior: 'auto' }) }}>설치부터 시작</a></div>
        <div className="cli-launch-spec"><span><b>07</b> 분석 도구</span><span><b>/</b> 통일된 명령</span><span><b>✓</b> 확인 후 실행</span></div>
      </div>
      <figure className="cli-launch-shot"><div className="cli-shot-label"><span className="cli-live-dot" /> ACTUAL TERMINAL CAPTURE <span>macOS</span></div><a href={`${MEDIA}/01-start.png`} target="_blank" rel="noreferrer"><img src={`${MEDIA}/01-start.png`} width="2112" height="1680" alt="FlyGate CLI 실제 시작 화면. 청록색 로고, 연두색 초파리, 분석·채팅 명령과 한 줄 입력창." /></a><figcaption>실제 실행 화면 · 클릭하면 원본 크기로 보기</figcaption></figure>
    </section>
    <section id="cli-demo" className="cli-cinema" aria-label="FlyGate CLI 실제 화면 네 장면" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)} onFocus={() => setPaused(true)} onBlur={() => setPaused(false)}>
      <header><div><span className="cli-kicker">FROM COMMAND TO EVIDENCE</span><h2>입력. 확인. 실행. 근거.</h2></div><span className="cli-film-badge">실제 실행 캡처 4장 · 자동 전환</span></header>
      <div className="cli-cinema-grid">
        <div className="cli-film-screen">
          <a className="cli-slides" href={`${MEDIA}/${scenes[scene].image}`} target="_blank" rel="noreferrer" aria-label={`원본 크기로 보기: ${scenes[scene].title}`}>
            {scenes.map((sc, i) => <img key={sc.image} src={`${MEDIA}/${sc.image}`} alt={`FlyGate 실제 터미널: ${sc.title}`} className={i === scene ? 'on' : ''} loading={i === 0 ? 'eager' : 'lazy'} />)}
          </a>
          <div className="cli-slide-bar" aria-hidden="true"><i key={`${scene}-${paused}`} className={paused ? 'paused' : ''} style={{ animationDuration: `${INTERVAL}ms` }} /></div>
          <p>실제 터미널 화면입니다. 누르면 원본 크기로 열립니다. 마우스를 올리면 멈춥니다.</p>
        </div>
        <div className="cli-film-script" aria-live="polite"><span className="cli-kicker">0{scene + 1} / 04</span><h3>{scenes[scene].title}</h3><code>{scenes[scene].command}</code><p>{scenes[scene].detail}</p><div className="cli-film-steps">{scenes.map((sc, i) => <button key={sc.name} onClick={() => setScene(i)} aria-pressed={scene === i} className={scene === i ? 'active' : ''}><span>0{i + 1}</span>{sc.name}</button>)}</div></div>
      </div>
    </section>
    <section className="cli-chat-guide"><div><span className="cli-kicker">TWO WAYS. SAME TOOLS.</span><h2>대화 안에서는 /명령.<br />터미널에서는 flygate 명령.</h2><p>같은 분석 기능입니다. 채팅창에서는 실행 승인을 거치고, 일반 터미널 명령은 바로 실행합니다.</p></div><div className="cli-command-pair"><div><span>FlyGate 채팅창</span><code>/discover parp1</code></div><div><span>일반 터미널 · JSON 출력</span><code>flygate discover parp1</code></div></div></section>
    <div className="cli-shortcuts">{[['/help','명령·예제'],['/login','키 설정'],['/last','전체 결과'],['/clear','대화 초기화'],['/exit','종료']].map(([cmd,desc]) => <div key={cmd}><code>{cmd}</code><span>{desc}</span></div>)}</div>
  </>
}
