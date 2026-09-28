import { useMemo, type CSSProperties } from 'react'

// Project-FlyGate 에이전트 구성도입니다. docs/images/flygate_agent_diagram_v1.0.0.png 와 같은 배치로
// NemoClaw 과정의 네 층을 위에서 아래로 쌓습니다.
// ① LLM 엔드포인트(NVIDIA NIM과 허용된 외부 API) ② OpenClaw 하네스(워크스페이스, 두 워크플로, 사람 승인)
// ③ OpenShell 샌드박스(egress 허용 목록, Landlock, seccomp, non-root) ④ NemoClaw 블루프린트(하네스와 샌드박스 구성)
// 하네스의 모든 호출은 샌드박스 윗변의 egress 관문을 지나 엔드포인트로 갑니다.

const W = 1360, H = 826
const C = { green: '#76b900', tan: '#e2a74e', cyan: '#37e6ff', jev: '#ffb547', rule: '#8a97bd', critic: '#ff5d6c', human: '#f4f7ff', magenta: '#ff4fd8' }
type Kind = 'data' | 'nim' | 'jev' | 'rule' | 'critic'
const KC: Record<Kind, string> = { data: C.cyan, nim: C.green, jev: C.jev, rule: C.rule, critic: C.critic }
const LEGEND: [string, string][] = [[C.cyan, '데이터 · 조회'], [C.green, 'NVIDIA NIM'], [C.jev, '비자기회귀 판단 모델'], [C.rule, '규칙'], [C.critic, '크리틱'], [C.human, '사람']]
const KR: CSSProperties = { fontFamily: 'var(--font-kr)' }
const EN: CSSProperties = { fontFamily: 'var(--font)' }

// 아이콘은 24칸 격자의 선 그림입니다
const ICON = {
  chat: 'M4 5h16v10h-9l-5 4v-4H4z M8 9h8 M8 12h5',
  molecule: 'M12 3l7.5 4.3v8.6L12 20.2l-7.5-4.3V7.3z M12 9.2l2.6 1.5v3L12 15.2l-2.6-1.5v-3z',
  shield: 'M12 3l7 3v5.5c0 4.6-3 7.6-7 8.8-4-1.2-7-4.2-7-8.8V6z M8.8 11.8l2.3 2.3 4.3-4.6',
  bars: 'M5 19V12 M10 19V6 M15 19V10 M20 19V15 M3 19h19',
  doc: 'M6 3h8l4 4v14H6z M14 3v4h4 M9 12h6 M9 16h6',
  ban: 'M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0 M5.6 5.6l12.8 12.8',
  folder: 'M3 7h6l2 2h10v10H3z',
  gear: 'M8.5 12a3.5 3.5 0 1 0 7 0a3.5 3.5 0 1 0 -7 0 M12 2.5v3 M12 18.5v3 M2.5 12h3 M18.5 12h3 M5.3 5.3l2.1 2.1 M16.6 16.6l2.1 2.1 M5.3 18.7l2.1-2.1 M16.6 7.4l2.1-2.1',
  user: 'M8 8a4 4 0 1 0 8 0a4 4 0 1 0 -8 0 M4.5 20c0.8-4 3.8-6 7.5-6s6.7 2 7.5 6',
}
function Icon({ d, x, y, s = 1, c, w = 1.6 }: { d: string; x: number; y: number; s?: number; c: string; w?: number }) {
  return <path d={d} transform={`translate(${x},${y}) scale(${s})`} fill="none" stroke={c} strokeWidth={w / s} strokeLinecap="round" strokeLinejoin="round" />
}

const NIM = [
  { title: 'Nemotron 3 Super', lines: ['숙고 메모', '국내 보고 서식 구조화'], host: 'integrate.api', icon: ICON.chat },
  { title: 'BioNeMo NIM', lines: ['MSA-Search · OpenFold3', 'DiffDock · Boltz-2'], host: 'health.api', icon: ICON.molecule },
  { title: 'Nemotron Safety Guard', lines: ['주장별 안전 검사', '개별 치료 조언 차단'], host: 'integrate.api', icon: ICON.shield },
]
const OTHER = [
  { title: '비자기회귀 판단 모델', lines: ['Jev · TypeSafe AI', '타입 있는 확률 판단'], icon: ICON.bars, c: C.jev },
  { title: 'openFDA · PubMed', lines: ['라벨 절 조회', '문헌 초록'], icon: ICON.doc, c: C.rule },
]

type Step = [name: string, tech: string, kind: Kind]
const STEP1: Step[] = [
  ['PARP1 표적', 'PDB 4R6E', 'data'], ['MSA-Search', 'BioNeMo NIM', 'nim'], ['OpenFold3', 'BioNeMo NIM', 'nim'],
  ['DiffDock', 'BioNeMo NIM', 'nim'], ['Boltz-2', 'BioNeMo NIM', 'nim'], ['크리틱', 'Nemotron 3 Super', 'critic'],
]
const STEP2: Step[] = [
  ['FAERS 접수', 'DuckDB SQL', 'data'], ['규칙 게이트', 'ICH 최소 4요소', 'rule'], ['라벨 조회', 'openFDA', 'data'],
  ['비자기회귀 판단', '7문항 · 한 번 호출', 'jev'], ['Nemotron 숙고', 'Nemotron 3 Super', 'nim'], ['크리틱 3단', '+ Safety Guard', 'critic'],
]
const EVIDENCE = ['faers:NIRAPARIB:thrombocytopenia', 'label:setid#warnings', 'pubmed:PMID#rct', 'nim:diffdock']
const MECH: [string, string][] = [
  [ICON.ban, '기본 차단 egress · 허용 목록만 통과'], [ICON.folder, 'Landlock · 쓰기 경로를 작업 폴더로 제한'],
  [ICON.gear, 'seccomp · 위험한 시스템 호출 차단'], [ICON.user, 'non-root · 권한 낮은 사용자로 실행'],
]
const DEFAULT_FILES = ['SOUL.md', 'AGENTS.md', 'TOOLS.md', 'HEARTBEAT.md', 'MEMORY.md']

// 레인 상자가 왼쪽부터 차례로 밝아지며 흐름을 보여 줍니다 (한 칸 0.55초)
function Wave({ x, y, w, h, i, n, c }: { x: number; y: number; w: number; h: number; i: number; n: number; c: string }) {
  const slot = 0.55, T = n * slot + 1.6
  const k = (s: number) => Math.min(1, Math.max(0, s / T)).toFixed(4)
  return (
    <rect x={x} y={y} width={w} height={h} rx={10} fill="none" stroke={c} strokeWidth={2} opacity={0}>
      <animate attributeName="opacity" dur={`${T}s`} repeatCount="indefinite"
        values="0;0;0.95;0;0" keyTimes={`0;${k(i * slot)};${k(i * slot + 0.3)};${k(i * slot + 0.9)};1`} />
    </rect>
  )
}

// 레인 하나: 상자 여섯 개를 화살표로 잇습니다
const LANE_X0 = 312, LANE_X1 = 1136, BOX_GAP = 16, BOX_H = 62
const BOX_W = (LANE_X1 - LANE_X0 - BOX_GAP * 5) / 6
function Lane({ steps, y, still }: { steps: Step[]; y: number; still: boolean }) {
  return (
    <g>
      {steps.map(([name, tech, kind], i) => {
        const x = LANE_X0 + i * (BOX_W + BOX_GAP), c = KC[kind]
        return (
          <g key={name}>
            {i > 0 && <path d={`M${x - BOX_GAP + 3},${y + BOX_H / 2} h9`} stroke="rgba(169,182,211,0.75)" strokeWidth={1.5} markerEnd="url(#ad-arrow)" />}
            <rect x={x} y={y} width={BOX_W} height={BOX_H} rx={10} fill="rgba(8,13,26,0.94)"
              stroke={kind === 'jev' ? 'rgba(255,181,71,0.6)' : 'rgba(120,170,255,0.24)'} strokeDasharray={kind === 'jev' ? '5 4' : undefined} />
            <rect x={x} y={y + 9} width={3} height={BOX_H - 18} rx={1.5} fill={c} />
            <text x={x + 13} y={y + 26} fill="var(--text)" fontSize={14.5} fontWeight={600} style={KR}>{name}</text>
            <text x={x + 13} y={y + 46} fill={c} fontSize={12} style={KR}>{tech}</text>
            {!still && <Wave x={x} y={y} w={BOX_W} h={BOX_H} i={i} n={steps.length} c={c} />}
          </g>
        )
      })}
    </g>
  )
}

export default function AgentDiagram({ files, skills }: { files?: string[]; skills?: number }) {
  const still = useMemo(() => typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches, [])
  const ws = files && files.length ? files : DEFAULT_FILES
  const shown = ws.length > 8 ? [...ws.slice(0, 7), `+${ws.length - 7}`] : ws
  const nimX = NIM.map((_, i) => 36 + i * 282)
  const othX = OTHER.map((_, i) => 910 + i * 214)
  const ends = [...nimX.map((x) => x + 136), ...othX.map((x) => x + 102)]
  const endC = [C.green, C.green, C.green, C.jev, C.rule]
  const GATE = 595, BUS = 180, SAND = 214, HARN = 258
  const y1 = 332, y2 = 470 // 두 레인 상자의 윗변
  const lastX = LANE_X0 + 5 * (BOX_W + BOX_GAP) + BOX_W
  const firstCx = LANE_X0 + BOX_W / 2
  let evX = 414

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', display: 'block' }} role="img"
        aria-label="Project-FlyGate 에이전트 구성도: ① LLM 엔드포인트 ② OpenClaw 하네스 ③ OpenShell 샌드박스 ④ NemoClaw 블루프린트. 하네스 안에서 STEP 1 FlyDiscovery와 STEP 2 FlyVigilance가 같은 분자를 다룹니다">
        <defs>
          <filter id="ad-glow"><feGaussianBlur stdDeviation="2.5" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
          <marker id="ad-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="rgba(169,182,211,0.85)" /></marker>
          <marker id="ad-arrow-g" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill={C.green} /></marker>
        </defs>

        {/* ① LLM 엔드포인트: NVIDIA NIM */}
        <rect x={20} y={14} width={864} height={132} rx={14} fill="rgba(118,185,0,0.05)" stroke={C.green} strokeOpacity={0.6} />
        <text x={38} y={40} fill={C.green} fontSize={15} fontWeight={700} style={KR}>① LLM 엔드포인트 · NVIDIA NIM</text>
        <text x={866} y={40} textAnchor="end" fill="var(--text-3)" fontSize={11}>*.api.nvidia.com</text>
        {NIM.map((e, i) => {
          const x = nimX[i]
          return (
            <g key={e.title}>
              <rect x={x} y={52} width={272} height={82} rx={11} fill="rgba(8,13,26,0.92)" stroke={C.green} strokeOpacity={0.45} />
              <Icon d={e.icon} x={x + 12} y={62} s={1.05} c={C.green} />
              <text x={x + 46} y={75} fill="var(--text)" fontSize={15} fontWeight={700} style={EN}>{e.title}</text>
              {e.lines.map((l, k) => <text key={l} x={x + 46} y={95 + k * 18} fill="var(--text-2)" fontSize={12.5} style={KR}>{l}</text>)}
              <text x={x + 262} y={125} textAnchor="end" fill="var(--text-3)" fontSize={10.5}>{e.host}</text>
            </g>
          )
        })}

        {/* 그 밖에 허용된 외부 API (NVIDIA 밖) */}
        <rect x={896} y={14} width={444} height={132} rx={14} fill="rgba(138,151,189,0.04)" stroke={C.rule} strokeOpacity={0.6} strokeDasharray="7 5" />
        <text x={914} y={40} fill="var(--text-2)" fontSize={15} fontWeight={700} style={KR}>허용된 외부 API</text>
        {OTHER.map((e, i) => {
          const x = othX[i]
          return (
            <g key={e.title}>
              <rect x={x} y={52} width={204} height={82} rx={11} fill="rgba(8,13,26,0.92)" stroke={e.c} strokeOpacity={0.45} />
              <Icon d={e.icon} x={x + 11} y={62} s={1} c={e.c} />
              <text x={x + 42} y={75} fill="var(--text)" fontSize={14} fontWeight={700} style={KR}>{e.title}</text>
              {e.lines.map((l, k) => <text key={l} x={x + 42} y={95 + k * 18} fill="var(--text-2)" fontSize={12.5} style={KR}>{l}</text>)}
            </g>
          )
        })}

        {/* egress 관문: 하네스 → 관문 → 버스 → 각 엔드포인트 */}
        <path d={`M${ends[0]},${BUS} H${ends[4]}`} stroke="rgba(226,167,78,0.6)" strokeWidth={1.5} />
        {ends.map((x, i) => {
          const d = `M${x},${BUS} V137`
          return (
            <g key={x}>
              <path d={d} stroke={endC[i]} strokeOpacity={0.75} strokeWidth={1.6} markerEnd="url(#ad-arrow)" />
              {!still && (
                <circle r={3} fill={endC[i]} filter="url(#ad-glow)">
                  <animateMotion dur="2.6s" begin={`${i * 0.4}s`} repeatCount="indefinite" path={d} keyPoints="0;1;0" keyTimes="0;0.5;1" calcMode="linear" />
                </circle>
              )}
            </g>
          )
        })}
        {/* ③ OpenShell 샌드박스 */}
        <rect x={20} y={SAND} width={1320} height={522} rx={20} fill="rgba(226,167,78,0.03)" stroke={C.tan} strokeWidth={1.8} strokeDasharray="10 6" className={still ? '' : 'ants'} />
        <Icon d={ICON.shield} x={36} y={229} s={0.9} c={C.tan} />
        <text x={62} y={246} fill={C.tan} fontSize={15} fontWeight={700} style={KR}>③ OpenShell 샌드박스</text>
        <text x={234} y={246} fill="var(--text-3)" fontSize={12.5} style={KR}>정책이 허용한 네트워크 · 파일 · 시스템 호출만 통과합니다</text>

        {/* egress 관문 알약: 샌드박스 윗변 위에 얹습니다 */}
        <path d={`M${GATE},${HARN} V${SAND + 15}`} stroke={C.tan} strokeWidth={1.6} strokeDasharray="3 4" />
        <path d={`M${GATE},${SAND - 15} V${BUS}`} stroke={C.tan} strokeWidth={1.6} />
        {!still && <rect x={GATE - 96} y={SAND - 20} width={192} height={40} rx={20} fill={C.tan} opacity={0.14} className="breathe" />}
        <rect x={GATE - 86} y={SAND - 15} width={172} height={30} rx={15} fill="#140f06" stroke={C.tan} strokeWidth={1.6} />
        <rect x={GATE - 71} y={SAND - 4} width={13} height={10} rx={2} fill="none" stroke={C.tan} strokeWidth={1.6} />
        <path d={`M${GATE - 68.5},${SAND - 4} v-3 a4,4 0 0 1 8,0 v3`} fill="none" stroke={C.tan} strokeWidth={1.6} />
        <text x={GATE - 50} y={SAND + 5} fill={C.tan} fontSize={13} fontWeight={700} style={KR}>egress 허용 목록</text>

        {/* ② OpenClaw 하네스 */}
        <rect x={40} y={HARN} width={1280} height={408} rx={14} fill="rgba(118,185,0,0.035)" stroke={C.green} strokeOpacity={0.7} strokeWidth={1.4} />
        <text x={58} y={284} fill={C.green} fontSize={15} fontWeight={700} style={KR}>② OpenClaw 하네스</text>
        <text x={218} y={284} fill="var(--text-3)" fontSize={12.5} style={KR}>세션 · 워크스페이스 파일 · 도구를 가진 에이전트 런타임</text>

        {/* 워크스페이스 */}
        <rect x={58} y={298} width={222} height={352} rx={12} fill="rgba(8,13,26,0.6)" stroke="rgba(118,185,0,0.35)" />
        <text x={74} y={323} fill="var(--text)" fontSize={14} fontWeight={600} style={KR}>워크스페이스</text>
        {shown.map((f, i) => {
          const cx = i % 2 === 0 ? 114 : 224, y = 338 + Math.floor(i / 2) * 50
          return (
            <g key={f}>
              <Icon d={ICON.doc} x={cx - 11} y={y} s={0.92} c="rgba(200,243,107,0.85)" w={1.4} />
              <text x={cx} y={y + 38} textAnchor="middle" fill="#c8f36b" fontSize={11.5}>{f}</text>
            </g>
          )
        })}
        {[skills ? `Agent Skills ${skills}개` : 'Agent Skills', '세션 · 메모리', '하트비트 · cron'].map((t, i) => (
          <g key={t}>
            <rect x={74} y={556 + i * 30} width={190} height={23} rx={11.5} fill="rgba(118,185,0,0.1)" stroke="rgba(118,185,0,0.5)" />
            <text x={169} y={572 + i * 30} textAnchor="middle" fill="#c8f36b" fontSize={12} style={KR}>{t}</text>
          </g>
        ))}

        {/* STEP 1 레인: 제목 위, 상자 아래 */}
        <rect x={296} y={298} width={852} height={114} rx={12} fill="rgba(55,230,255,0.035)" stroke="rgba(55,230,255,0.35)" />
        <text x={312} y={321} fill={C.cyan} fontSize={14} fontWeight={700} style={KR}>STEP 1 · FlyDiscovery</text>
        <text x={488} y={321} fill="var(--text-3)" fontSize={12.5} style={KR}>시판 전 · 구조 예측 → 도킹 → 친화도, 단계마다 전통 기준으로 채점</text>
        <Lane steps={STEP1} y={y1} still={still} />

        {/* 같은 분자: STEP 1 의 표적 상자에서 STEP 2 의 접수 상자로 이어집니다 */}
        <path d={`M${firstCx},${y1 + BOX_H} V${y2 - 3}`} stroke={C.human} strokeOpacity={0.65} strokeWidth={1.5} strokeDasharray="4 4" markerEnd="url(#ad-arrow)" />
        <rect x={firstCx + 12} y={429} width={176} height={24} rx={12} fill="#0b1122" stroke="rgba(244,247,255,0.45)" />
        <text x={firstCx + 100} y={445} textAnchor="middle" fill="var(--text)" fontSize={12.5} style={KR}>같은 분자 · 니라파립</text>

        {/* STEP 2 레인: 상자 위, 제목 아래 */}
        <rect x={296} y={458} width={852} height={122} rx={12} fill="rgba(118,185,0,0.035)" stroke="rgba(118,185,0,0.4)" />
        <Lane steps={STEP2} y={y2} still={still} />
        <text x={312} y={563} fill={C.green} fontSize={14} fontWeight={700} style={KR}>STEP 2 · FlyVigilance</text>
        <text x={486} y={563} fill="var(--text-3)" fontSize={12.5} style={KR}>시판 후 · 같은 약의 FAERS 보고를 분류하고 필요한 건만 숙고와 사람에게</text>

        {/* 사람 승인 */}
        <rect x={1164} y={298} width={138} height={282} rx={12} fill="rgba(8,13,26,0.92)" stroke="rgba(244,247,255,0.45)" />
        <Icon d={ICON.user} x={1209} y={372} s={2} c={C.human} w={1.8} />
        <circle cx={1252} cy={410} r={10} fill={C.green} />
        <path d="M1247,410 l3.5,3.5 l6,-7" fill="none" stroke="#0b1400" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" />
        <text x={1233} y={456} textAnchor="middle" fill="var(--text)" fontSize={15} fontWeight={700} style={KR}>사람 승인</text>
        <text x={1233} y={478} textAnchor="middle" fill="var(--text-2)" fontSize={12} style={KR}>보고 · 인과성</text>
        <text x={1233} y={495} textAnchor="middle" fill="var(--text-2)" fontSize={12} style={KR}>최종 판정</text>
        {[y1 + BOX_H / 2, y2 + BOX_H / 2].map((y) => (
          <path key={y} d={`M${lastX + 3},${y} H1160`} stroke="rgba(169,182,211,0.85)" strokeWidth={1.6} markerEnd="url(#ad-arrow)" />
        ))}

        {/* 공유 근거 ID: 두 워크플로의 모든 주장이 같은 방식으로 근거에 묶입니다 */}
        <rect x={296} y={594} width={1006} height={56} rx={12} fill="rgba(255,79,216,0.05)" stroke="rgba(255,79,216,0.4)" />
        <text x={312} y={627} fill={C.magenta} fontSize={13.5} fontWeight={700} style={KR}>공유 근거 ID</text>
        {EVIDENCE.map((t) => {
          const w = t.length * 6.9 + 20, x0 = evX
          evX += w + 8
          return (
            <g key={t}>
              <rect x={x0} y={610} width={w} height={24} rx={7} fill="rgba(20,12,30,0.9)" stroke="rgba(255,79,216,0.35)" />
              <text x={x0 + w / 2} y={626} textAnchor="middle" fill="#ffa6ec" fontSize={11.5}>{t}</text>
            </g>
          )
        })}
        <text x={1288} y={627} textAnchor="end" fill="var(--text-2)" fontSize={12.5} style={KR}>주장마다 근거 ID · 크리틱이 원본과 대조</text>

        {/* 샌드박스의 네 장치 */}
        {MECH.map(([d, t], i) => {
          const x = 40 + i * 322
          return (
            <g key={t}>
              <rect x={x} y={680} width={314} height={36} rx={10} fill="rgba(226,167,78,0.07)" stroke="rgba(226,167,78,0.45)" />
              <Icon d={d} x={x + 12} y={687} s={0.92} c={C.tan} />
              <text x={x + 44} y={703} fill="var(--text)" fontSize={12.5} style={KR}>{t}</text>
            </g>
          )
        })}

        {/* ④ NemoClaw 블루프린트 */}
        {[210, 1150].map((x) => <path key={x} d={`M${x},760 V741`} stroke={C.green} strokeWidth={1.6} markerEnd="url(#ad-arrow-g)" />)}
        <text x={222} y={754} fill={C.green} fontSize={11.5} style={KR}>구성</text>
        <rect x={20} y={762} width={1320} height={52} rx={14} fill="rgba(118,185,0,0.1)" stroke={C.green} strokeOpacity={0.75} />
        <Icon d={ICON.doc} x={38} y={776} s={1} c={C.green} />
        <text x={70} y={794} fill={C.green} fontSize={16} fontWeight={700} style={KR}>④ NemoClaw 블루프린트</text>
        <text x={262} y={794} fill="var(--text-2)" fontSize={13} style={KR}>하네스와 샌드박스를 한 벌로 구성합니다 · 정책 프리셋 · 수명주기 명령(onboard · status · logs)</text>
      </svg>
      <div className="row wrap" style={{ gap: 14, padding: '10px 4px 0' }}>
        {LEGEND.map(([c, t]) => <span key={t} className="row" style={{ gap: 6, fontSize: 11.5, color: 'var(--text-3)' }}><span className="legend-dot" style={{ background: c }} />{t}</span>)}
        <span className="row" style={{ gap: 6, fontSize: 11.5, color: 'var(--text-3)' }}><span className="legend-dot" style={{ background: 'transparent', border: `1.5px dashed ${C.tan}` }} />OpenShell 경계 · egress 관문</span>
      </div>
    </div>
  )
}
