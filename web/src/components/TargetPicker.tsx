// STEP 1 다섯 화면 맨 위의 표적·리간드 선택기입니다.
// UniProt 에서 단백질을, PubChem 에서 리간드를 찾아 그대로 라이브 NIM 파이프라인에 넣습니다.
// 목록에 있는 표적(측정 기록이 있는 PARP1·Factor Xa·COX-2)은 프리셋으로 남겨 '지난 측정' 비교를 그대로 씁니다.
import { useEffect, useMemo, useRef, useState } from 'react'
import { Card } from './ui'
import {
  bioText, getProtein, ligandName, searchLigand, targetDesc, searchProtein, selectLigand, selectTarget, useDiscovery,
  type Catalog, type CustomTarget, type LigandHit, type ProteinHit, type ProteinRecord, type RangeRef,
} from '../lib/discovery'
import { t } from '../lib/i18n'

// 프리셋: 목록 표적(kind: catalog)은 지난 측정 비교가 붙고, 나머지는 UniProt 번호로 바로 불러옵니다
// 설명 문구가 언어를 따르도록 렌더할 때 만듭니다.
const presets = (): { key: string; label: string; sub: string; accession?: string; catalog?: string }[] => [
  { key: 'parp1', label: 'PARP1', sub: t('4R6E · 측정 기록 있음', '4R6E · has measurement record'), catalog: 'parp1' },
  { key: 'egfr', label: 'EGFR', sub: t('P00533 · 키나아제 도메인', 'P00533 · kinase domain'), accession: 'P00533' },
  { key: 'braf', label: 'BRAF', sub: t('P15056 · 키나아제 도메인', 'P15056 · kinase domain'), accession: 'P15056' },
  { key: 'jak2', label: 'JAK2', sub: t('O60674 · JH1 도메인', 'O60674 · JH1 domain'), accession: 'O60674' },
  { key: 'sglt2', label: 'SGLT2', sub: t('P31639 · 막수송체', 'P31639 · membrane transporter'), accession: 'P31639' },
  { key: 'xa', label: 'Factor Xa', sub: t('2P16 · 측정 기록 있음', '2P16 · has measurement record'), catalog: 'xa' },
  { key: 'cox2', label: 'COX-2', sub: t('3LN1 · 측정 기록 있음(쥐)', '3LN1 · has measurement record (mouse)'), catalog: 'cox2' },
]
const ligandPresets = () => [
  { key: 'niraparib', label: t('니라파립', 'Niraparib'), sub: t('PARP1 데모 약물', 'PARP1 demo drug') },
  { key: 'rucaparib', label: t('루카파립', 'Rucaparib'), sub: t('PARP 억제제', 'PARP inhibitor') },
  { key: 'apixaban', label: t('아픽사반', 'Apixaban'), sub: 'Factor Xa' },
  { key: 'celecoxib', label: t('셀레콕시브', 'Celecoxib'), sub: 'COX-2' },
]

function fromRecord(rec: ProteinRecord, range: RangeRef): CustomTarget {
  const best = rec.best_structure
  const useStruct = range.kind === 'structure' && best
  return {
    id: rec.id, gene: rec.gene, name: rec.name, organism: rec.organism,
    sequence: rec.sequence, length: rec.length,
    pdb: useStruct ? best!.pdb : (best?.pdb ?? null), chain: useStruct ? best!.chain : (best?.chain ?? null),
    start: range.start, end: range.end, resolution: best?.resolution ?? null,
    label: rec.gene || rec.name || rec.id, range_label: range.label,
    openfold3_ok: range.end - range.start + 1 <= 1800,
  }
}

function useDebounced<T>(value: T, ms = 350) {
  const [v, setV] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setV(value), ms)
    return () => clearTimeout(id)
  }, [value, ms])
  return v
}

export default function TargetPicker({ cat }: { cat: Catalog | null }) {
  const { target, ligand, customTarget, customLigand } = useDiscovery()
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<ProteinHit[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [rec, setRec] = useState<ProteinRecord | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [lq, setLq] = useState('')
  const [lhits, setLhits] = useState<LigandHit[] | null>(null)
  const [lbusy, setLbusy] = useState(false)
  const dq = useDebounced(q)
  const dlq = useDebounced(lq)
  const seq = useRef(0)

  useEffect(() => {
    if (dq.trim().length < 2) { setHits(null); return }
    const my = ++seq.current
    setBusy(true); setErr(null)
    searchProtein(dq.trim())
      .then((r) => { if (my === seq.current) setHits(r.hits) })
      .catch((e) => { if (my === seq.current) setErr(e instanceof Error ? e.message : String(e)) })
      .finally(() => { if (my === seq.current) setBusy(false) })
  }, [dq])

  useEffect(() => {
    if (dlq.trim().length < 2) { setLhits(null); return }
    setLbusy(true)
    searchLigand(dlq.trim())
      .then((r) => setLhits(r.hits))
      .catch(() => setLhits([]))
      .finally(() => setLbusy(false))
  }, [dlq])

  async function loadProtein(id: string) {
    setBusy(true); setErr(null)
    try {
      const r = await getProtein(id)
      setRec(r)
      selectTarget(fromRecord(r, r.recommended_range))
      setHits(null)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally { setBusy(false) }
  }

  const PRESETS = presets()
  const LIGAND_PRESETS = ligandPresets()
  const preset = (p: typeof PRESETS[number]) => {
    if (p.catalog) { selectTarget(null, p.catalog); setRec(null); return }
    setOpen(true)
    loadProtein(p.accession!)
  }

  const current = customTarget
    ? `${customTarget.label} · ${customTarget.organism}${customTarget.range_label ? ` · ${bioText(customTarget.range_label)}` : ''}`
    : `${cat?.targets[target]?.label ?? target} · ${targetDesc(target, cat?.targets[target]?.desc)}`
  const currentLig = customLigand ? `${customLigand.name}${customLigand.cid ? ` · CID ${customLigand.cid}` : ''}`
    : ligandName(ligand, cat?.ligands[ligand]?.ko)
  const activeKey = customTarget ? '' : target

  const ranges = useMemo(() => rec?.ranges ?? [], [rec])

  return (
    <Card style={{ marginBottom: 14 }}>
      <div className="row between wrap" style={{ gap: 10 }}>
        <div style={{ minWidth: 0 }}>
          <div className="eyebrow" style={{ color: 'var(--text-3)' }}>{t('표적 · 리간드', 'Target · ligand')}</div>
          <div className="row wrap" style={{ gap: 8, marginTop: 4 }}>
            <b style={{ fontFamily: 'var(--font)', fontSize: 15 }}>{current}</b>
            <span className="chip" style={{ fontSize: 10.5 }}>{t('리간드', 'Ligand')} {currentLig}</span>
            {customTarget
              ? <span className="chip warn" style={{ fontSize: 10.5 }} title={t('측정 기록이 없는 표적이라 RMSD 대조를 하지 않습니다', 'No measurement record for this target, so no RMSD comparison is made')}>{t('기준 결정 구조 없음', 'No reference crystal structure')}</span>
              : <span className="chip ok" style={{ fontSize: 10.5 }}>{t('지난 측정 비교 있음', 'Compared with previous measurement')}</span>}
            {customTarget?.openfold3_ok === false
              && <span className="chip bad" style={{ fontSize: 10.5 }}>{t('구조 예측 한계 초과(1800잔기)', 'Exceeds structure-prediction limit (1,800 residues)')}</span>}
          </div>
        </div>
        <button className="btn ghost" onClick={() => setOpen((v) => !v)}>{open ? t('접기', 'Collapse') : t('단백질 · 리간드 찾기', 'Find a protein · ligand')}</button>
      </div>

      <div className="row wrap" style={{ gap: 6, marginTop: 10 }}>
        {PRESETS.map((p) => (
          <button key={p.key} className="chip" onClick={() => preset(p)} title={p.sub}
            style={{
              cursor: 'pointer', fontSize: 11,
              color: activeKey === p.key || customTarget?.id === p.accession ? '#c8f36b' : 'var(--text-2)',
              borderColor: activeKey === p.key || customTarget?.id === p.accession ? 'rgba(118,185,0,0.6)' : 'var(--line-2)',
              background: activeKey === p.key || customTarget?.id === p.accession ? 'rgba(118,185,0,0.12)' : undefined,
            }}>
            {p.label}<span className="dim" style={{ marginLeft: 6, fontSize: 9.5 }}>{p.catalog ? t('측정 기록', 'Measured') : 'UniProt'}</span>
          </button>
        ))}
      </div>

      {open && (
        <>
          <div className="divider" />
          <div className="grid g2" style={{ gap: 16 }}>
            <div className="stack" style={{ gap: 8 }}>
              <span className="mono dim" style={{ fontSize: 10.5, letterSpacing: 0.4, textTransform: 'uppercase' }}>
                {t('단백질 찾기 · UniProt (이름 · 유전자 · 번호 · PDB ID)', 'Find a protein · UniProt (name · gene · accession · PDB ID)')}
              </span>
              <input className="input" value={q} onChange={(e) => setQ(e.target.value)}
                placeholder={t('예: EGFR · kinase · P00533 · 1M17', 'e.g. EGFR · kinase · P00533 · 1M17')} />
              {busy && <div className="row dim mono" style={{ fontSize: 11 }}><span className="spin" />{t('찾는 중', 'Searching')}</div>}
              {err && <div className="note" style={{ color: 'var(--warn)' }}>{err}</div>}
              {hits && hits.length === 0 && <div className="note">{t('결과가 없습니다. 유전자 이름이나 UniProt 번호로 다시 찾아보시기 바랍니다.', 'No results. Try a gene name or a UniProt accession.')}</div>}
              {hits && hits.length > 0 && (
                <div className="stack" style={{ gap: 5, maxHeight: 240, overflowY: 'auto' }}>
                  {hits.map((h) => (
                    <button key={h.id} className="card" onClick={() => loadProtein(h.id)}
                      style={{ textAlign: 'left', cursor: 'pointer', padding: '8px 10px', border: '1px solid var(--line)' }}>
                      <div className="row between" style={{ gap: 8 }}>
                        <b style={{ fontFamily: 'var(--font)', fontSize: 13 }}>{h.gene || h.uniprot_id}</b>
                        <span className="row" style={{ gap: 5 }}>
                          {h.reviewed && <span className="chip ok" style={{ fontSize: 9.5 }}>{t('검토됨', 'Reviewed')}</span>}
                          {h.n_pdb > 0 && <span className="chip" style={{ fontSize: 9.5 }}>PDB {h.n_pdb}</span>}
                        </span>
                      </div>
                      <div className="dim" style={{ fontSize: 11.5 }}>{h.name}</div>
                      <div className="mono dim" style={{ fontSize: 10 }}>{h.organism} · {h.length ?? '–'}{t('잔기', ' residues')} · {h.id}</div>
                    </button>
                  ))}
                </div>
              )}
              {rec && (
                <div className="stack" style={{ gap: 6 }}>
                  <div className="note">
                    <b>{rec.gene} · {rec.name}</b> · {rec.organism} · {t(`전체 ${rec.length}잔기`, `${rec.length} residues in total`)}
                    {rec.best_structure && <> · {t('최적 실험 구조', 'best experimental structure')} {rec.best_structure.pdb} {rec.best_structure.resolution ?? '–'} Å {t('체인', 'chain')} {rec.best_structure.chain}</>}
                  </div>
                  <div className="row wrap" style={{ gap: 5 }}>
                    {ranges.map((r) => {
                      const on = customTarget?.start === r.start && customTarget?.end === r.end
                      const len = r.end - r.start + 1
                      return (
                        <button key={`${r.kind}-${r.start}-${r.end}`} className="chip"
                          onClick={() => selectTarget(fromRecord(rec, r))}
                          title={len > 1800 ? t('1800잔기를 넘으면 OpenFold3 가 호스팅 경로에서 실패할 수 있습니다', 'Above 1,800 residues OpenFold3 may fail on the hosted endpoint') : ''}
                          style={{
                            cursor: 'pointer', fontSize: 10.5,
                            color: on ? '#c8f36b' : len > 1800 ? 'var(--warn)' : 'var(--text-2)',
                            borderColor: on ? 'rgba(118,185,0,0.6)' : 'var(--line-2)',
                          }}>
                          {bioText(r.label)} · {r.start}–{r.end} ({len}{t('잔기', ' residues')})
                        </button>
                      )
                    })}
                  </div>
                  {!rec.check.ok && <div className="note" style={{ color: 'var(--bad)' }}>{bioText(rec.check.reason)}</div>}
                  {rec.check.ok && !rec.check.openfold3_ok && <div className="note" style={{ color: 'var(--warn)' }}>{bioText(rec.check.reason)}</div>}
                </div>
              )}
            </div>

            <div className="stack" style={{ gap: 8 }}>
              <span className="mono dim" style={{ fontSize: 10.5, letterSpacing: 0.4, textTransform: 'uppercase' }}>
                {t('리간드 찾기 · PubChem (이름) 또는 SMILES 붙여 넣기', 'Find a ligand · PubChem (name) or paste a SMILES string')}
              </span>
              <input className="input" value={lq} onChange={(e) => setLq(e.target.value)}
                placeholder={t('예: erlotinib · imatinib · CC(=O)OC1=CC=CC=C1C(=O)O', 'e.g. erlotinib · imatinib · CC(=O)OC1=CC=CC=C1C(=O)O')} />
              {lbusy && <div className="row dim mono" style={{ fontSize: 11 }}><span className="spin" />{t('찾는 중', 'Searching')}</div>}
              {lhits && lhits.length === 0 && <div className="note">{t('결과가 없습니다. 영문 이름이나 SMILES 로 다시 넣어 주시기 바랍니다.', 'No results. Try the English name or a SMILES string.')}</div>}
              {lhits && lhits.length > 0 && (
                <div className="stack" style={{ gap: 5, maxHeight: 240, overflowY: 'auto' }}>
                  {lhits.map((h, i) => (
                    <button key={`${h.cid ?? 'smiles'}-${i}`} className="card"
                      onClick={() => selectLigand({ name: h.name, smiles: h.smiles, cid: h.cid, mw: h.mw })}
                      style={{ textAlign: 'left', cursor: 'pointer', padding: '8px 10px', border: '1px solid var(--line)' }}>
                      <div className="row between" style={{ gap: 8 }}>
                        <b style={{ fontFamily: 'var(--font)', fontSize: 13 }}>{h.name}</b>
                        <span className="mono dim" style={{ fontSize: 10 }}>
                          {h.cid ? `CID ${h.cid}` : h.source}{h.mw ? ` · ${h.mw} g/mol` : ''}
                        </span>
                      </div>
                      <div className="mono dim" title={h.smiles}
                        style={{ fontSize: 10, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{h.smiles}</div>
                    </button>
                  ))}
                </div>
              )}
              <div className="row wrap" style={{ gap: 5 }}>
                {LIGAND_PRESETS.map((p) => (
                  <button key={p.key} className="chip" title={p.sub} onClick={() => selectLigand(null, p.key)}
                    style={{
                      cursor: 'pointer', fontSize: 10.5,
                      color: !customLigand && ligand === p.key ? '#c8f36b' : 'var(--text-2)',
                      borderColor: !customLigand && ligand === p.key ? 'rgba(118,185,0,0.6)' : 'var(--line-2)',
                    }}>{p.label}</button>
                ))}
              </div>
              <div className="note">
                {t(<>고른 단백질은 MSA-Search → OpenFold3 → DiffDock → Boltz-2 → 크리틱에 그대로 들어갑니다.
                실험 구조가 있으면 RCSB 에서 받아 도킹 수용체로 쓰고, 없으면 OpenFold3 예측 구조를 씁니다.
                측정 기록이 없는 표적에서는 RMSD 대신 <b>기준 결정 구조 없음</b>으로 표시합니다.</>,
                <>The chosen protein goes straight into MSA-Search → OpenFold3 → DiffDock → Boltz-2 → critic.
                If an experimental structure exists, it is fetched from RCSB and used as the docking receptor; otherwise the OpenFold3 predicted structure is used.
                For targets without a measurement record, RMSD is replaced by <b>No reference crystal structure</b>.</>)}
              </div>
            </div>
          </div>
        </>
      )}
    </Card>
  )
}
