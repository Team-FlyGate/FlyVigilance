import { useEffect, useState } from 'react'
import { Card, PageHead } from '../components/ui'
import { LAYER_COLOR, fmt, getJSON, type ConnectomeMeta } from '../lib/data'
import type { Bench, Overview } from '../lib/types'

interface Pain { n: string; title: string; fact: React.ReactNode; src: React.ReactNode; principle: string; brain: string; layer: string; fix: string; metric: React.ReactNode }

export default function Problem() {
  const [ov, setOv] = useState<Overview | null>(null)
  const [b, setB] = useState<Bench | null>(null)
  const [meta, setMeta] = useState<ConnectomeMeta | null>(null)
  useEffect(() => {
    getJSON<Overview>('/data/faers/overview.json').then(setOv)
    getJSON<Bench>('/data/bench.json').then(setB).catch(() => null)
    getJSON<ConnectomeMeta>('/data/connectome/meta.json').then(setMeta)
  }, [])
  const L = (k: string) => meta?.layers.find((l) => l.key === k)?.neurons ?? 0

  const pains: Pain[] = [
    {
      n: '01', title: '처리량 폭증: 모든 케이스를 같은 무게로 읽는다',
      fact: <>FAERS 한 분기({ov?.asof})에만 보고 <b>{ov ? fmt.int(ov.per_quarter.at(-1)?.reports ?? 0) : '…'}</b>건. 누적 {ov ? fmt.compact(ov.raw_reports) : '…'}건이 {ov?.quarters ?? '…'}개 분기에 걸쳐 쌓였다. 한국 KAERS도 2025년 277,279건이다.</>,
      src: <>우리 웨어하우스 실측 · KAERS 수치는 식약처 보고동향 보도 인용</>,
      principle: '감각 채널의 병렬 수용', brain: `감각 뉴런 ${fmt.int(L('sense'))}개가 모달리티별로 나뉘어 동시에 받는다`, layer: 'sense',
      fix: 'FAERS, 문헌, 임상시험, 라벨 변경, 디지털 채널을 각각 수용 스킬로 분리하고 한 번에 정규화한다',
      metric: <>분기 적재 {ov ? `${(ov.etl.reduce((a, e) => a + e.seconds, 0) / ov.etl.length).toFixed(1)}초/분기` : '…'} (DuckDB, 노트북)</>,
    },
    {
      n: '02', title: '사람의 시간: 건당 읽기만 수 분',
      fact: <>신호 평가 중 ICSR 내러티브 검토에 건당 약 5.56분(69건 395분). 자동화 플랫폼으로 약 63% 줄었다는 보고가 있다. 접수·코딩·인과성 평가를 뺀 <b>읽기 시간만</b>이다.</>,
      src: <>Warner et al., Clin Pharmacol Ther 2026, PMID 42522449 (저자 스스로 예비적 수치라고 밝힘)</>,
      principle: '선천적 반사 회로', brain: `Lateral horn ${fmt.int(L('reflex'))}개 뉴런: 학습 없이 즉시 판단`, layer: 'reflex',
      fix: 'Jev System-1이 중대성·예측성·인과성·우선순위·다음 행동을 한 번의 호출로 확률과 함께 낸다',
      metric: <>{b ? <>p50 <b>{Math.round(b.jev_triage.latency_ms.p50)} ms</b> / 7판단, {b.jev_triage.throughput_cases_per_s}건/초</> : '벤치마크 대기'}</>,
    },
    {
      n: '03', title: 'LLM을 붙이면 비싸고 느리다',
      fact: <>예아니오 한 줄을 받는 선별에도 프런티어 모델은 건당 입력 322 + 출력 47 토큰, 지연 중앙값 1.67초를 썼다. 분기 40만 건이면 순차로 186시간이다.</>,
      src: <>팀 선행 실측: Nemotron 3 Super, niraparib 상위 10건 (korea-agentic-hackathon-2026 triage-scale)</>,
      principle: '희소 확장 코딩', brain: `Kenyon cell ${fmt.int(4064)}개 중 소수만 발화하고 소수의 MBON이 읽는다`, layer: 'memory',
      fix: '모든 건은 Jev가 싸게, 애매하거나 중대·예상외인 건만 Nemotron으로 올린다. 통계는 SQL이 계산한다',
      metric: <>{b ? <>Jev <b>{fmt.usd(b.jev_triage.usd_per_1k)}</b> / 1,000건 · 입력 {b.jev_triage.tokens_in_mean} tok, 출력 무료</> : '…'}</>,
    },
    {
      n: '04', title: '그럴듯한 과잉해석',
      fact: <>근거 ID도 붙고 숫자도 맞는데 결론만 틀린 요약이 나온다. 고정 규칙은 심어 둔 과잉해석 16건 중 1건만 잡았고, LLM 판정을 더하면 16건 모두 잡았다(거짓 양성 0/17).</>,
      src: <>팀 선행 실측: FlyGate 크리틱 평가 33건 (critic_verdict_output_*.json)</>,
      principle: '억제성 되먹임', brain: `GABA성 억제 뉴런 ${fmt.int(L('critic'))}개: APL이 버섯체 활동을 눌러 희소성을 지킨다`, layer: 'critic',
      fix: '3단 크리틱: 근거 ID 실재(규칙) → 숫자 오라클(SQL 대조) → Jev 과잉해석 판정(규칙 12종). 반려 시 사유와 함께 재작성',
      metric: <>주장마다 overclaim 확률과 위반 규칙 ID를 남긴다</>,
    },
    {
      n: '05', title: '분기 배치 감시는 늦다',
      fact: <>불균형 분석을 분기 보고서 주기로 돌리면 신호가 기준을 넘은 뒤에도 평가가 시작되지 않는다. 연속 감시였다면 언제 시작할 수 있었는지는 사후 재계산으로 잴 수 있다.</>,
      src: <>신호 타임머신: FDA 안전성 조치 8건 백테스트</>,
      principle: '연합 학습과 도파민', brain: `DAN·MBON 회로가 경험을 누적해 가치를 갱신한다 (피드백 ${fmt.int(L('feedback'))}개 상행 뉴런)`, layer: 'feedback',
      fix: '매 적재마다 누적 2×2를 다시 계산하고, 사람 검토 결과를 되먹여 임계값과 우선순위를 조정한다',
      metric: <>사례별 선행 일수와 실패 사례를 그대로 공개</>,
    },
    {
      n: '06', title: '데이터 품질: 버전, 삭제, 이름 난립',
      fact: <>{ov ? <>원천 보고 {fmt.int(ov.raw_reports)}건 → 고유 케이스 {fmt.int(ov.cases)}건. 약물명 원문 {fmt.int(ov.drug_names_raw)}종, FDA 삭제 케이스 {fmt.int(ov.deleted_cases)}건.</> : '…'}</>,
      src: <>우리 웨어하우스 실측 (FDA 권고 중복 제거 규칙)</>,
      principle: '투사 뉴런의 정규화', brain: `안테나엽 PN ${fmt.int(L('encode'))}개가 수천 개 수용체 입력을 사구체별로 정리한다`, layer: 'encode',
      fix: 'caseid 최신 버전, 삭제 목록 반영, 유효성분 우선·염 접미사 제거·상품명→성분 학습 매핑',
      metric: <>{ov ? `상품명→성분 매핑 ${fmt.int(ov.drugname_map)}건 학습` : '…'}</>,
    },
    {
      n: '07', title: '사람의 주의는 가장 희소한 자원',
      fact: <>최종 판단과 규제 보고는 사람이 해야 한다. 문제는 사람에게 무엇을, 어떤 근거와 함께 올리느냐다.</>,
      src: <>ICH E2D, GVP Module VI 원칙</>,
      principle: '하행 뉴런 병목', brain: `${fmt.int(meta?.neurons ?? 0)}개 중 하행 뉴런은 ${fmt.int(L('action'))}개(${meta ? fmt.pct(L('action') / meta.neurons, 1) : ''})뿐이다`, layer: 'action',
      fix: '근거 ID가 붙고 크리틱을 통과한 메모만 사람 큐로, 신속보고 후보는 15일 시계와 함께 올린다',
      metric: <>{b ? <>표본 기준 사람에게 올라간 비율 {fmt.pct((b.jev_triage.actions.expedite ?? 0) / b.jev_triage.ok, 1)}</> : '…'}</>,
    },
  ]

  return (
    <div className="page">
      <PageHead eyebrow="Problem framing · why FlyVigilante"
        title={<>약물감시의 병목은 <span style={{ color: 'var(--bad)' }}>양</span>이 아니라 <span style={{ color: 'var(--c-sense)' }}>배분</span>이다</>}
        lede="모든 이상사례를 같은 비용으로 읽는 구조가 문제다. 초파리 뇌는 16만 개 뉴런으로 이 문제를 이미 풀었다. 감각은 넓게 받고, 반사는 싸게, 기억은 희소하게, 숙고는 드물게, 행동은 좁은 병목으로 낸다. 우리는 그 배선 원리를 에이전트 라우팅에 옮겼다." />

      <div className="stack" style={{ gap: 14 }}>
        {pains.map((p) => (
          <Card key={p.n} className="fade-in">
            <div style={{ display: 'grid', gridTemplateColumns: '64px minmax(0,1.25fr) minmax(0,1fr) minmax(0,1fr)', gap: 22, alignItems: 'start' }}>
              <div style={{ fontFamily: 'var(--font)', fontSize: 34, fontWeight: 700, color: LAYER_COLOR[p.layer], textShadow: `0 0 24px ${LAYER_COLOR[p.layer]}` }}>{p.n}</div>
              <div>
                <div className="eyebrow" style={{ color: 'var(--bad)' }}>Pain</div>
                <h3 style={{ fontSize: 16, margin: '4px 0 8px' }}>{p.title}</h3>
                <div style={{ fontSize: 13, color: 'var(--text-2)' }}>{p.fact}</div>
                <div className="note" style={{ marginTop: 8 }}>출처 · {p.src}</div>
              </div>
              <div style={{ borderLeft: `2px solid ${LAYER_COLOR[p.layer]}`, paddingLeft: 16 }}>
                <div className="eyebrow" style={{ color: LAYER_COLOR[p.layer] }}>Fly brain principle</div>
                <h3 style={{ fontSize: 14.5, margin: '4px 0 6px' }}>{p.principle}</h3>
                <div style={{ fontSize: 12.5, color: 'var(--text-2)' }}>{p.brain}</div>
              </div>
              <div>
                <div className="eyebrow" style={{ color: 'var(--ok)' }}>FlyVigilante</div>
                <div style={{ fontSize: 12.5, margin: '4px 0 10px' }}>{p.fix}</div>
                <div className="chip" style={{ whiteSpace: 'normal', lineHeight: 1.4 }}>{p.metric}</div>
              </div>
            </div>
          </Card>
        ))}
      </div>
      <Card style={{ marginTop: 16 }}>
        <div className="note" style={{ fontSize: 12.5 }}>
          <b>경계를 분명히 한다.</b> 커넥텀은 설계 원리와 실시간 라우팅 시각화를 준다. 임상 판단의 근거는 FAERS, 라벨, 문헌이고 판단은 Jev와 Nemotron과 사람이 한다.
          초파리 뇌가 약물 안전성을 “이해”한다고 주장하지 않는다. 배선도는 어디로 보낼지를 말해 주지 무엇이 옳은지를 말해 주지 않는다.
        </div>
      </Card>
    </div>
  )
}
