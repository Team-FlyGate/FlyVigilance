import { useEffect, useState } from 'react'
import { Card, HBars, Kpi, LineChart, Loading, PageHead } from '../components/ui'
import { OCCP_LABEL, OUTCOME_LABEL, fmt, getJSON } from '../lib/data'
import type { Overview, Schema } from '../lib/types'
import Term from '../components/Term'
import { t } from '../lib/i18n'

const LAYER_COL: Record<string, string> = { raw: '#4d8dff', core: '#37e6ff', ref: '#a58bff', sig: '#ff4fd8', ops: '#76b900', etl: '#ffb547' }
const ORDER = ['raw', 'core', 'ref', 'sig', 'ops', 'etl']
// schema.json 의 계층 이름 중 통계 기준 결과를 '신호'라 부르던 것을 SDR 용어로 바꿔 보여 드립니다
// 영어 화면에서는 schema.json 의 한국어 계층 이름을 모두 이 표로 옮깁니다
const layerLabel = (): Record<string, string> => t<Record<string, string>>({ sig: '불균형 분석 (SDR 판정)' }, {
  raw: 'Raw (quarterly files as-is, VARCHAR)', core: 'Cleaned (deduplicated, normalized, typed)', ref: 'Reference (learned mappings)',
  sig: 'Disproportionality (SDR flags)', ops: 'Operational metrics', etl: 'Load audit',
})

export default function Warehouse() {
  const [ov, setOv] = useState<Overview | null>(null)
  const [sc, setSc] = useState<Schema | null>(null)
  const [open, setOpen] = useState<string | null>('sig_signal')
  useEffect(() => { getJSON<Overview>('/data/faers/overview.json').then(setOv); getJSON<Schema>('/data/faers/schema.json').then(setSc) }, [])
  if (!ov || !sc) return <div className="page"><Loading /></div>

  const funnel = [
    { label: t('원천 보고 (raw_demo)', 'Raw reports (raw_demo)'), value: ov.raw_reports, color: '#4d8dff' },
    { label: t('고유 caseid', 'Unique caseid'), value: ov.distinct_caseids, color: '#37e6ff' },
    { label: t('FDA 삭제 반영 후 케이스', 'Cases after FDA deletions'), value: ov.cases, color: '#3ddc97' },
    { label: t('의심약 × 반응 삼중항', 'Case × suspect drug × reaction triplets'), value: ov.triplets, color: '#ff4fd8' },
    { label: t('약물-반응 쌍 (a ≥ 3)', 'Drug–reaction pairs (a ≥ 3)'), value: ov.pairs, color: '#ffb547' },
    { label: t('3중 기준 SDR (Evans ∧ ROR ∧ IC)', 'Triple-criteria SDRs (Evans ∧ ROR ∧ IC)'), value: ov.all3, color: '#ff5d6c' },
  ]
  const qs = ov.per_quarter
  const xt = qs.map((q, k) => ({ x: k, label: q.quarter.endsWith('Q1') ? q.quarter.slice(0, 4) : '' })).filter((t) => t.label)

  return (
    <div className="page">
      <PageHead eyebrow="PV Data Warehouse · DuckDB"
        title={t(<>원천부터 <Term k="SDR" />까지, <span style={{ color: 'var(--c-sense)' }}>감사 가능한 5계층</span></>,
          <>From raw files to <Term k="SDR">SDRs</Term>: <span style={{ color: 'var(--c-sense)' }}>five auditable layers</span></>)}
        lede={t(<><Term k="warehouse">웨어하우스</Term>는 원천 데이터를 분석하기 좋게 층층이 정리한 데이터베이스입니다. <Term k="FAERS" ko /> 분기 파일 {ov.quarters}개({ov.first}–{ov.asof})를 증분 적재했습니다. 원문은 원천 계층에 VARCHAR 그대로 두고, 정제·참조·<Term k="disproportionality">불균형 분석</Term>·운영 계층을 <Term k="SQL">SQL</Term>로만 파생합니다. 모든 불균형 지표 수치는 이 SQL을 다시 돌리면 같은 값이 나옵니다. SDR은 불균형 보고 신호(세 통계 기준을 모두 넘은 약물–반응 쌍)입니다. DB 크기는 {(sc.db_bytes / 1e9).toFixed(2)} GB입니다.</>,
          <>A <Term k="warehouse">warehouse</Term> is a database that organizes raw data into layers that are easy to analyze. {ov.quarters} quarterly files ({ov.first}–{ov.asof}) of the <Term k="FAERS">FDA Adverse Event Reporting System (FAERS)</Term> were loaded incrementally. The original text stays as VARCHAR in the raw layer, and the cleaned, reference, <Term k="disproportionality">disproportionality</Term> and operational layers are derived only with <Term k="SQL">SQL</Term>. Rerunning this SQL reproduces every disproportionality number exactly. An SDR (signal of disproportionate reporting) is a drug–reaction pair that passes all three statistical criteria. The database is {(sc.db_bytes / 1e9).toFixed(2)} GB.</>)} />

      <div className="grid g4" style={{ marginBottom: 16 }}>
        <Kpi label="raw rows (demo+drug+reac)" hint={t('원천 파일의 보고 · 약물 · 반응 행을 모두 더한 수', 'Sum of report, drug and reaction rows in the raw files')} value={ov.raw_reports + ov.raw_drug_rows + ov.raw_reac_rows} color="#4d8dff" sub={`${fmt.compact(ov.raw_drug_rows)} drug rows · ${fmt.compact(ov.raw_reac_rows)} reaction rows`} />
        <Kpi label={<>unique <Term k="caseid">cases</Term></>} hint={t('같은 사례의 옛 버전과 FDA 삭제분을 뺀 고유 사례 수', 'Unique cases after removing older versions of the same case and FDA deletions')} value={ov.cases} color="#37e6ff" sub={`${fmt.int(ov.deleted_cases)} FDA-deleted caseids excluded`} />
        <Kpi label="drug names normalized" hint={t('제각각인 약 이름을 성분명으로 통일한 수', 'Inconsistent drug names unified to ingredient names')} value={ov.drug_names_norm} color="#a58bff" sub={`from ${fmt.int(ov.drug_names_raw)} raw spellings`} />
        <Kpi label={<Term k="MedDRA">MedDRA preferred terms</Term>} hint={t('보고에 나온 이상반응 표준 용어 수', 'Standard adverse-reaction terms that appear in the reports')} value={ov.pts} color="#ff4fd8" sub={`${fmt.compact(ov.triplets)} case-drug-event triplets`} />
      </div>

      <Card title={t('계층 스키마', 'Layer schema')} sub={t('클릭하면 컬럼이 펼쳐집니다. 행 수는 빌드 시점 실측값입니다', 'Click a table to show its columns. Row counts are measured at build time')} style={{ marginBottom: 16 }}>
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${ORDER.length}, minmax(0,1fr))`, gap: 12, position: 'relative' }}>
          {ORDER.map((L) => (
            <div key={L} className="stack" style={{ gap: 8 }}>
              <div style={{ padding: '8px 10px', borderRadius: 10, background: `color-mix(in srgb, ${LAYER_COL[L]} 14%, transparent)`, border: `1px solid ${LAYER_COL[L]}55` }}>
                <div className="mono" style={{ fontSize: 11, color: LAYER_COL[L], letterSpacing: 1.2 }}>{L.toUpperCase()}</div>
                <div style={{ fontSize: 11.5, color: 'var(--text-2)' }}>{layerLabel()[L] ?? sc.layers[L]}</div>
              </div>
              {sc.tables.filter((t) => t.layer === L).map((t) => (
                <div key={t.name} onClick={() => setOpen(open === t.name ? null : t.name)} style={{ cursor: 'pointer', padding: '8px 10px', borderRadius: 10, border: `1px solid ${open === t.name ? LAYER_COL[L] : 'var(--line)'}`, background: 'rgba(10,16,30,0.6)' }}>
                  <div className="row between"><span className="mono" style={{ fontSize: 11.5 }}>{t.name}</span></div>
                  <div className="num dim" style={{ fontSize: 10.5 }}>{fmt.int(t.rows)} rows · {t.columns.length} cols</div>
                  {open === t.name && <div className="fade-in" style={{ marginTop: 6, borderTop: '1px solid var(--line)', paddingTop: 6 }}>
                    {t.columns.map((c) => <div key={c.name} className="row between mono" style={{ fontSize: 10.5 }}><span>{c.name}</span><span className="dim">{c.type.toLowerCase()}</span></div>)}
                  </div>}
                </div>
              ))}
            </div>
          ))}
        </div>
      </Card>

      <div className="grid g2" style={{ marginBottom: 16 }}>
        <Card title={t('정제 퍼널', 'Cleaning funnel')} sub={t('보고 → 케이스 → SDR. 각 단계는 SQL 한 단계입니다', 'Reports → cases → SDRs. Each step is one SQL step')}>
          <HBars data={funnel} labelWidth={200} fmt={fmt.compact} height={34} />
        </Card>
        <Card title={t('분기별 보고와 적재 시간', 'Reports per quarter and load time')} sub={t(<>원천 보고 수(파랑), <Term k="expedited">신속보고</Term> EXP(분홍)입니다. 분기 zip 하나의 평균 적재 시간은 아래에 있습니다</>, <>Raw reports (blue) and <Term k="expedited">expedited</Term> EXP reports (pink). The average load time per quarterly zip is shown below</>)}>
          <LineChart height={220} xTicks={xt} series={[
            { key: 'rep', color: '#4d8dff', area: true, values: qs.map((q, k) => ({ x: k, y: q.reports })) },
            { key: 'exp', color: '#ff4fd8', values: qs.map((q, k) => ({ x: k, y: q.expedited })) },
          ]} />
          <div className="row" style={{ gap: 16, marginTop: 8 }}>
            <span className="chip">avg load {(ov.etl.reduce((a, e) => a + e.seconds, 0) / ov.etl.length).toFixed(1)} s / quarter</span>
            <span className="chip">total {ov.etl.reduce((a, e) => a + e.seconds, 0).toFixed(0)} s for {ov.quarters} quarters</span>
          </div>
        </Card>
      </div>

      <div className="grid g3">
        <Card title={<Term k="outcome">{t('결과 코드 분포', 'Outcome code distribution')}</Term>} sub={t('core_outc · 케이스당 중복 허용', 'core_outc · a case can have several')}>
          <HBars data={Object.entries(ov.outcomes).map(([k, v]) => ({ label: `${OUTCOME_LABEL[k] ?? k} (${k})`, value: v, color: k === 'DE' ? '#ff5d6c' : k === 'LT' ? '#ff8f3a' : '#37e6ff' }))} fmt={fmt.compact} labelWidth={120} />
        </Card>
        <Card title={t('보고자 유형', 'Reporter type')} sub="occp_cod">
          <HBars data={Object.entries(ov.reporters).map(([k, v]) => ({ label: OCCP_LABEL[k] ?? k, value: v, color: '#a58bff' }))} fmt={fmt.compact} labelWidth={100} />
        </Card>
        <Card title={t('보고 국가 상위', 'Top reporting countries')} sub="reporter_country">
          <HBars data={ov.countries.slice(0, 9).map(([k, v]) => ({ label: k, value: v, color: '#76b900' }))} fmt={fmt.compact} labelWidth={60} />
        </Card>
        <Card title={t('의심약 상위', 'Top suspect drugs')} sub={<><Term k="role">PS/SS</Term> {t('(주 · 부 의심약) 기준 케이스 수', '(primary / secondary suspect) case counts')}</>} className="span2">
          <HBars data={ov.top_drugs.slice(0, 14).map(([k, v]) => ({ label: k, value: v, color: '#ffb547' }))} fmt={fmt.compact} labelWidth={200} />
        </Card>
        <Card title={t('연령 분포', 'Age distribution')} sub={t('age_years (보고된 경우)', 'age_years (when reported)')}>
          <HBars data={ov.age_bins.map(([b, v]) => ({ label: `${b}–${b + 9}`, value: v, color: '#4d8dff' }))} fmt={fmt.compact} labelWidth={60} height={20} />
        </Card>
      </div>
    </div>
  )
}
