import { useEffect, useRef } from 'react'
import { t } from '../lib/i18n'

// MSA-Search 단계의 가운데 장면: 상동 서열 100개가 한 줄씩 들어와 PARP1 서열 아래에 맞춰지는 모습.
// 위: 결합 포켓 근처 잔기를 글자로 확대한 정렬 창(같은 아미노산 = 시안, 다름 = 흐림, 빈칸 = -, 포켓 열 = 주황)
// 아래: 전체 정렬 지도(서열 × 352 잔기)와, 들어온 서열로 다시 계산되는 잔기별 보존도 막대
// 데이터는 nim/parp1.a3m (build_hero_scene.py) 그대로이고, 들어오는 순서와 속도만 연출입니다.

export interface MsaData { labels: [string, number | null][]; query_len: number; strip: string[]; pocket_residues: number[]; conservation: number[] }
const AA_QUERY_FALLBACK = ''

export default function MsaAnimation({ msa, query, duration = 9000, loop = false }: { msa: MsaData; query: string; duration?: number; loop?: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const cv = ref.current
    if (!cv) return
    const x = cv.getContext('2d')!
    let raf = 0, disposed = false
    const N = msa.strip.length, L = msa.query_len
    const pocket = new Set(msa.pocket_residues)
    // 확대 창: 포켓 잔기의 가운데를 중심으로 44개 열
    const pr = [...msa.pocket_residues].sort((a, b) => a - b), mid = pr[Math.floor(pr.length / 2)] ?? Math.floor(L / 2)
    const W0 = 44, s0 = Math.max(1, Math.min(L - W0 + 1, mid - Math.floor(W0 / 2)))
    const t0 = performance.now()
    const draw = (now: number) => {
      if (disposed) return
      const dpr = Math.min(devicePixelRatio, 2), w = cv.clientWidth, h = cv.clientHeight
      if (cv.width !== Math.round(w * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr) }
      x.setTransform(dpr, 0, 0, dpr, 0, 0)
      x.fillStyle = '#070b16'; x.fillRect(0, 0, w, h)
      const el = loop ? (now - t0) % (duration + 1500) : now - t0
      const k = Math.min(1, el / duration)
      const arrived = Math.floor(k * N), frac = k * N - arrived

      // ── 위: 확대 정렬 창 ──
      const padL = 150, top = 118, rowH = 17, cols = W0, cw = (w - padL - 20) / cols
      // 아래 설명 줄(mapTop - 48) 위에서 줄이 끝나게 합니다. 화면이 낮으면 줄 수를 줄여 겹치지 않게 합니다
      const captionY = h * 0.6 - 48
      const vis = Math.max(0, Math.min(13, Math.floor((captionY - 20 - top - 4) / rowH)))
      x.font = '600 11px "JetBrains Mono", monospace'; x.textBaseline = 'middle'; x.textAlign = 'center'
      for (let c = 0; c < cols; c++) {
        const r = s0 + c
        if (pocket.has(r)) { x.fillStyle = 'rgba(255,181,71,0.12)'; x.fillRect(padL + c * cw, top - 22, cw - 1, rowH * (vis + 2) + 4) }
        x.fillStyle = pocket.has(r) ? '#ffb547' : 'rgba(169,182,211,0.55)'
        // 번호는 5칸마다만 (포켓은 위 주황 띠로 표시하므로 번호를 겹쳐 쓰지 않음)
        if (c % 5 === 0) x.fillText(String(r), padL + c * cw + cw / 2, top - 14)
        x.fillStyle = '#f4f7ff'; x.fillText(query[r - 1] ?? AA_QUERY_FALLBACK, padL + c * cw + cw / 2, top + 2)
      }
      x.textAlign = 'left'; x.fillStyle = '#37e6ff'; x.fillText(t('PARP1 (쿼리)', 'PARP1 (query)'), 14, top + 2)
      // 최근에 들어온 서열이 위에 오도록. 오른쪽에서 미끄러져 들어오는 줄이 창 밖으로 넘치지 않게 잘라 그립니다
      x.save(); x.beginPath(); x.rect(0, top + 8, w - 14, rowH * (vis + 1)); x.clip()
      for (let j = 0; j < vis; j++) {
        const idx = arrived - 1 - j + (frac > 0 ? 1 : 0)
        if (idx < 0 || idx >= N) continue
        const y = top + rowH * (j + 1) + 4, row = msa.strip[idx], lab = msa.labels[idx]
        const slide = idx === arrived && frac > 0 ? (1 - frac) * (w * 0.5) : 0  // 막 들어오는 줄은 오른쪽에서 미끄러져 들어옴
        x.globalAlpha = idx === arrived ? Math.min(1, frac * 2) : 1 - j * 0.045
        x.fillStyle = 'rgba(169,182,211,0.75)'; x.textAlign = 'left'
        x.fillText(`${lab?.[0]?.replace('UniRef100_', '') ?? ''}`, 14 + slide, y)
        if (lab?.[1] != null) { x.fillStyle = 'rgba(111,125,158,0.9)'; x.fillText(`${Math.round(lab[1] * 100)}%`, 112 + slide, y) }
        x.textAlign = 'center'
        for (let c = 0; c < cols; c++) {
          const ch = row[s0 + c - 1], same = ch === '1', gap = ch === '-'
          const px = padL + c * cw + slide
          if (same) { x.fillStyle = pocket.has(s0 + c) ? 'rgba(255,181,71,0.45)' : 'rgba(55,230,255,0.28)'; x.fillRect(px + 1, y - 7, cw - 2, 14) }
          x.fillStyle = gap ? 'rgba(111,125,158,0.5)' : same ? '#e8eefc' : 'rgba(111,125,158,0.8)'
          x.fillText(gap ? '-' : same ? (query[s0 + c - 1] ?? '') : '·', px + cw / 2, y)
        }
        x.globalAlpha = 1
      }
      x.restore()

      // ── 아래: 전체 정렬 지도 + 보존도 막대 ──
      const mapTop = h * 0.6, mapH = h - mapTop - 44, mapL = 14, mapW = w - 28
      const cellW = mapW / L, cellH = mapH / N
      x.fillStyle = 'rgba(11,17,34,1)'; x.fillRect(mapL, mapTop, mapW, mapH)
      for (let j = 0; j < Math.min(arrived, N); j++) {
        const row = msa.strip[j]
        for (let i = 0; i < L; i++) {
          const ch = row[i]
          if (ch === '-') continue
          x.fillStyle = ch === '1' ? (pocket.has(i + 1) ? '#ffcf7a' : '#37e6ff') : '#3a3f7a'
          x.fillRect(mapL + i * cellW, mapTop + j * cellH, Math.max(1, cellW), Math.max(1, cellH))
        }
      }
      // 확대 창 위치 표시
      x.strokeStyle = 'rgba(255,255,255,0.6)'; x.lineWidth = 1
      x.strokeRect(mapL + (s0 - 1) * cellW, mapTop - 1, cols * cellW, mapH + 2)
      // 들어온 서열로 다시 계산한 보존도 막대
      const barTop = mapTop - 36, barH = 30
      if (arrived > 0) {
        for (let i = 0; i < L; i++) {
          let same = 0
          for (let j = 0; j < arrived; j++) if (msa.strip[j][i] === '1') same++
          const c = same / arrived
          x.fillStyle = pocket.has(i + 1) ? '#ffb547' : `rgba(55,230,255,${0.25 + 0.6 * c})`
          x.fillRect(mapL + i * cellW, barTop + barH * (1 - c), Math.max(1, cellW - 0.3), barH * c)
        }
      }
      x.textAlign = 'left'; x.font = '500 11px "JetBrains Mono", monospace'
      x.fillStyle = 'rgba(169,182,211,0.85)'
      x.fillText(t(`정렬 ${Math.min(arrived, N)} / ${N} 서열 · 잔기별 보존도(위 막대) · 전체 정렬 지도(아래)`, `Aligned ${Math.min(arrived, N)} / ${N} · conservation (bars) · alignment map (below)`), mapL, barTop - 12)
      x.fillStyle = '#ffb547'; x.textAlign = 'right'; x.fillText(t('주황 = 결합 포켓 잔기', 'Orange = pocket residues'), w - 14, barTop - 12)
      raf = requestAnimationFrame(draw)
    }
    raf = requestAnimationFrame(draw)
    return () => { disposed = true; cancelAnimationFrame(raf) }
  }, [msa, query, duration, loop])
  return <canvas ref={ref} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', display: 'block', borderRadius: 14 }}
    aria-label={t('상동 서열 100개가 PARP1 서열 아래에 한 줄씩 정렬되는 모습과, 들어온 서열로 계산되는 잔기별 보존도', '100 homologous sequences aligning one by one beneath the PARP1 sequence, with per-residue conservation recomputed from the arrived sequences')} />
}
