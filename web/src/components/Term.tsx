import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { GLOSSARY, GLOSS_CAT } from '../lib/glossary'

// 약어와 전문 용어에 점선 밑줄을 긋고, 올리거나(마우스) 누르거나(터치) 키보드로 초점을 주면 쉬운 풀이를 띄웁니다.
// 풀이 상자는 document.body 에 포털로 그려 카드의 overflow 에 잘리지 않고, 본문 배치를 밀어내지 않습니다.
// ko 를 주면 용어 뒤에 한국어 이름을 괄호로 붙여 첫 등장 풀이를 겸합니다.

let closeOpen: (() => void) | null = null

export default function Term({ k, children, ko = false }: { k: string; children?: ReactNode; ko?: boolean }) {
  const e = GLOSSARY[k]
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState<{ left: number; top: number; below: boolean; arrow: number } | null>(null)
  const anchor = useRef<HTMLSpanElement>(null)
  const tip = useRef<HTMLDivElement>(null)
  const timer = useRef<number | undefined>(undefined)
  const pointer = useRef<string>('mouse')
  const id = useId()

  const hideNow = useCallback(() => { window.clearTimeout(timer.current); setOpen(false) }, [])
  const show = useCallback(() => {
    window.clearTimeout(timer.current)
    if (closeOpen && closeOpen !== hideNow) closeOpen()
    closeOpen = hideNow
    setOpen(true)
  }, [hideNow])
  const hideSoon = () => { window.clearTimeout(timer.current); timer.current = window.setTimeout(hideNow, 140) }

  const place = useCallback(() => {
    const a = anchor.current?.getBoundingClientRect(), t = tip.current
    if (!a || !t) return
    const w = t.offsetWidth, h = t.offsetHeight, vw = window.innerWidth, vh = window.innerHeight
    const below = a.top - h - 10 < 8 && a.bottom + h + 10 < vh
    const left = Math.max(8, Math.min(vw - w - 8, a.left + a.width / 2 - w / 2))
    const top = below ? a.bottom + 8 : a.top - h - 8
    setPos({ left, top, below, arrow: Math.max(12, Math.min(w - 12, a.left + a.width / 2 - left)) })
  }, [])

  useLayoutEffect(() => { if (open) place(); else setPos(null) }, [open, place])
  useEffect(() => {
    if (!open) return
    const onDown = (ev: PointerEvent) => {
      const n = ev.target as Node
      if (!anchor.current?.contains(n) && !tip.current?.contains(n)) hideNow()
    }
    const onKey = (ev: KeyboardEvent) => { if (ev.key === 'Escape') { hideNow(); anchor.current?.focus() } }
    window.addEventListener('pointerdown', onDown, true)
    window.addEventListener('keydown', onKey)
    window.addEventListener('scroll', place, true)
    window.addEventListener('resize', place)
    return () => {
      window.removeEventListener('pointerdown', onDown, true)
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('scroll', place, true)
      window.removeEventListener('resize', place)
    }
  }, [open, place, hideNow])
  useEffect(() => () => { window.clearTimeout(timer.current); if (closeOpen === hideNow) closeOpen = null }, [hideNow])

  if (!e) return <>{children ?? k}</>
  const cat = GLOSS_CAT[e.cat]
  const label = children ?? e.term

  return (
    <>
      <span ref={anchor} className="term" tabIndex={0} role="button" aria-expanded={open} aria-describedby={open ? id : undefined}
        aria-label={`${typeof label === 'string' ? label : e.term}: ${e.ko}. 풀이 보기`}
        onPointerDown={(ev) => { pointer.current = ev.pointerType }}
        onPointerEnter={(ev) => { if (ev.pointerType === 'mouse') show() }}
        onPointerLeave={(ev) => { if (ev.pointerType === 'mouse') hideSoon() }}
        onFocus={(ev) => { if (ev.currentTarget.matches(':focus-visible')) show() }}
        onBlur={(ev) => { if (!tip.current?.contains(ev.relatedTarget as Node)) hideSoon() }}
        onClick={(ev) => { ev.stopPropagation(); ev.preventDefault(); if (pointer.current === 'mouse') show(); else if (open) hideNow(); else show() }}
        onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); if (open) hideNow(); else show() } }}>
        {label}
      </span>
      {ko && <span className="term-ko">({e.ko})</span>}
      {open && createPortal(
        <div ref={tip} id={id} role="tooltip" className={`term-tip ${pos?.below ? 'below' : ''}`}
          style={{ left: pos?.left ?? -9999, top: pos?.top ?? -9999, visibility: pos ? 'visible' : 'hidden', ['--arrow' as string]: `${pos?.arrow ?? 20}px`, ['--cat' as string]: cat.color }}
          onPointerEnter={() => window.clearTimeout(timer.current)} onPointerLeave={(ev) => { if (ev.pointerType === 'mouse') hideSoon() }}>
          <div className="term-tip-head">
            <b>{e.term}</b>
            <span className="term-tip-cat">{cat.name}</span>
          </div>
          <div className="term-tip-ko">{e.ko}{e.en ? <span> · {e.en}</span> : null}</div>
          <p>{e.short}</p>
          {e.long && <p className="term-tip-long">{e.long}</p>}
          <a href={`#/glossary?k=${encodeURIComponent(k)}`} onClick={() => hideNow()}>용어 풀이 전체 보기 →</a>
        </div>,
        document.body,
      )}
    </>
  )
}
