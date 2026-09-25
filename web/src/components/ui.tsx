import { useEffect, useRef, useState, type ReactNode } from 'react'
import * as d3 from 'd3'

export function PageHead({ eyebrow, title, lede, right }: { eyebrow: string; title: ReactNode; lede?: ReactNode; right?: ReactNode }) {
  return (
    <div className="page-head fade-in">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1 className="title">{title}</h1>
        {lede && <p className="lede">{lede}</p>}
      </div>
      {right}
    </div>
  )
}

export function Card({ title, sub, right, children, className = '', style }: {
  title?: ReactNode; sub?: ReactNode; right?: ReactNode; children: ReactNode; className?: string; style?: React.CSSProperties
}) {
  return (
    <section className={`card fade-in ${className}`} style={style}>
      {(title || right) && (
        <div className="card-head">
          <div>{title && <h2>{title}</h2>}{sub && <p>{sub}</p>}</div>
          {right}
        </div>
      )}
      {children}
    </section>
  )
}

export function useCountUp(target: number, ms = 1200) {
  const [v, setV] = useState(0)
  useEffect(() => {
    let raf = 0
    const t0 = performance.now()
    const run = (t: number) => {
      const k = Math.min(1, (t - t0) / ms)
      setV(target * (1 - Math.pow(1 - k, 3)))
      if (k < 1) raf = requestAnimationFrame(run)
    }
    raf = requestAnimationFrame(run)
    return () => cancelAnimationFrame(raf)
  }, [target, ms])
  return v
}

export function Kpi({ label, value, sub, color = 'var(--c-sense)', format = (n: number) => Math.round(n).toLocaleString('en-US') }: {
  label: string; value: number; sub?: ReactNode; color?: string; format?: (n: number) => string
}) {
  const v = useCountUp(value)
  return (
    <div className="card kpi fade-in">
      <div className="k-accent" style={{ background: color, boxShadow: `0 0 16px ${color}` }} />
      <div className="k-label">{label}</div>
      <div className="k-value">{format(v)}</div>
      {sub && <div className="k-sub">{sub}</div>}
    </div>
  )
}

export function ProbBar({ p, color = 'var(--c-sense)', label, right }: { p: number; color?: string; label?: ReactNode; right?: ReactNode }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: label ? '110px 1fr 52px' : '1fr 52px', gap: 10, alignItems: 'center' }}>
      {label && <span className="mono" style={{ fontSize: 11.5, color: 'var(--text-2)' }}>{label}</span>}
      <div className="pbar"><i style={{ width: `${Math.max(0, Math.min(1, p)) * 100}%`, background: color, boxShadow: `0 0 12px ${color}` }} /></div>
      <span className="num" style={{ fontSize: 12, textAlign: 'right' }}>{right ?? p.toFixed(2)}</span>
    </div>
  )
}

function useSize<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [w, setW] = useState(600)
  useEffect(() => {
    if (!ref.current) return
    const ro = new ResizeObserver((e) => setW(e[0].contentRect.width))
    ro.observe(ref.current)
    return () => ro.disconnect()
  }, [])
  return [ref, w] as const
}

export function HBars({ data, color = 'var(--c-sense)', height = 22, fmt = (n: number) => n.toLocaleString('en-US'), labelWidth = 150 }: {
  data: { label: string; value: number; color?: string; note?: string }[]; color?: string; height?: number; fmt?: (n: number) => string; labelWidth?: number
}) {
  const [ref, w] = useSize<HTMLDivElement>()
  const max = d3.max(data, (d) => d.value) || 1
  const bw = Math.max(40, w - labelWidth - 80)
  return (
    <div ref={ref}>
      <svg width={w} height={data.length * height}>
        {data.map((d, i) => (
          <g key={d.label} transform={`translate(0,${i * height})`}>
            <text x={labelWidth - 8} y={height / 2 + 4} textAnchor="end" fill="var(--text-2)" fontSize={11}>{d.label.length > 24 ? d.label.slice(0, 23) + '…' : d.label}</text>
            <rect x={labelWidth} y={4} width={bw} height={height - 8} rx={4} fill="rgba(120,170,255,0.06)" />
            <rect x={labelWidth} y={4} width={(d.value / max) * bw} height={height - 8} rx={4} fill={d.color ?? color} opacity={0.85}>
              <animate attributeName="width" from="0" to={(d.value / max) * bw} dur="0.9s" fill="freeze" />
            </rect>
            <text x={labelWidth + (d.value / max) * bw + 6} y={height / 2 + 4} fill="var(--text)" fontSize={11}>{fmt(d.value)}{d.note ? ` ${d.note}` : ''}</text>
          </g>
        ))}
      </svg>
    </div>
  )
}

export interface Series { key: string; color: string; values: { x: number; y: number | null }[]; dash?: string; area?: boolean }

export function LineChart({ series, height = 260, xTicks, yLabel, markers = [], hlines = [], xFormat, yLog = false, yDomain, markerLabels = true }: {
  series: Series[]; height?: number; xTicks?: { x: number; label: string }[]; yLabel?: string
  markers?: { x: number; label: string; color: string }[]; hlines?: { y: number; label: string; color: string }[]
  xFormat?: (x: number) => string; yLog?: boolean; yDomain?: [number, number]; markerLabels?: boolean
}) {
  const [ref, w] = useSize<HTMLDivElement>()
  const m = { l: 48, r: 16, t: 14, b: 28 }
  const all = series.flatMap((s) => s.values.filter((v) => v.y !== null && Number.isFinite(v.y as number)))
  const xs = d3.extent(all, (d) => d.x) as [number, number]
  const yExt = yDomain ?? ([Math.min(0, d3.min(all, (d) => d.y as number) ?? 0), (d3.max(all, (d) => d.y as number) ?? 1) * 1.08] as [number, number])
  const x = d3.scaleLinear().domain(xs[0] === undefined ? [0, 1] : xs).range([m.l, w - m.r])
  const y = yLog ? d3.scaleLog().domain([Math.max(0.1, yExt[0] || 0.1), Math.max(1, yExt[1])]).range([height - m.b, m.t]).clamp(true)
    : d3.scaleLinear().domain(yExt).nice().range([height - m.b, m.t])
  const line = d3.line<{ x: number; y: number | null }>().defined((d) => d.y !== null && Number.isFinite(d.y as number)).x((d) => x(d.x)).y((d) => y(d.y as number)).curve(d3.curveMonotoneX)
  const area = d3.area<{ x: number; y: number | null }>().defined((d) => d.y !== null).x((d) => x(d.x)).y0(height - m.b).y1((d) => y(d.y as number)).curve(d3.curveMonotoneX)
  const yt = (y as d3.ScaleLinear<number, number>).ticks(5)
  return (
    <div ref={ref}>
      <svg width={w} height={height}>
        <defs>
          {series.map((s) => (
            <linearGradient key={s.key} id={`ga-${s.key.replace(/\W/g, '')}`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0" stopColor={s.color} stopOpacity={0.35} /><stop offset="1" stopColor={s.color} stopOpacity={0} />
            </linearGradient>
          ))}
        </defs>
        <g className="axis">
          {yt.map((t) => (
            <g key={t} transform={`translate(0,${y(t)})`}>
              <line x1={m.l} x2={w - m.r} strokeDasharray="2 4" />
              <text x={m.l - 8} y={4} textAnchor="end">{t >= 1000 ? d3.format('.2s')(t) : t}</text>
            </g>
          ))}
          {(xTicks ?? x.ticks(6).map((t) => ({ x: t, label: xFormat ? xFormat(t) : String(t) }))).map((t) => (
            <text key={t.x} x={x(t.x)} y={height - 8} textAnchor="middle">{t.label}</text>
          ))}
          {yLabel && <text x={m.l} y={10} fill="var(--text-3)" fontSize={10}>{yLabel}</text>}
        </g>
        {hlines.map((h) => (
          <g key={h.label}>
            <line x1={m.l} x2={w - m.r} y1={y(h.y)} y2={y(h.y)} stroke={h.color} strokeDasharray="5 4" opacity={0.7} />
            <text x={w - m.r - 4} y={y(h.y) - 5} textAnchor="end" fill={h.color} fontSize={10}>{h.label}</text>
          </g>
        ))}
        {series.map((s) => (
          <g key={s.key}>
            {s.area && <path d={area(s.values) ?? ''} fill={`url(#ga-${s.key.replace(/\W/g, '')})`} />}
            <path d={line(s.values) ?? ''} fill="none" stroke={s.color} strokeWidth={2} strokeDasharray={s.dash} style={{ filter: `drop-shadow(0 0 6px ${s.color})` }} />
          </g>
        ))}
        {markers.map((mk) => (
          <g key={mk.label} transform={`translate(${x(mk.x)},0)`}>
            <line y1={m.t} y2={height - m.b} stroke={mk.color} strokeWidth={1.5} />
            <rect x={-2} y={m.t - 2} width={4} height={4} fill={mk.color} />
            {markerLabels && <text x={4} y={m.t + 10} fill={mk.color} fontSize={10}>{mk.label}</text>}
          </g>
        ))}
      </svg>
    </div>
  )
}

export function Spark({ values, color = 'var(--c-sense)', height = 36 }: { values: number[]; color?: string; height?: number }) {
  const [ref, w] = useSize<HTMLDivElement>()
  const x = d3.scaleLinear().domain([0, values.length - 1]).range([0, w])
  const y = d3.scaleLinear().domain([0, d3.max(values) || 1]).range([height - 2, 2])
  const p = d3.line<number>().x((_, i) => x(i)).y((d) => y(d)).curve(d3.curveMonotoneX)(values)
  const a = d3.area<number>().x((_, i) => x(i)).y0(height).y1((d) => y(d)).curve(d3.curveMonotoneX)(values)
  return (
    <div ref={ref}>
      <svg width={w} height={height}>
        <path d={a ?? ''} fill={color} opacity={0.12} />
        <path d={p ?? ''} fill="none" stroke={color} strokeWidth={1.6} />
      </svg>
    </div>
  )
}

export function Loading({ label = '불러오는 중' }: { label?: string }) {
  return <div className="row dim mono" style={{ fontSize: 12, padding: 20 }}><span className="spin" />{label}</div>
}
