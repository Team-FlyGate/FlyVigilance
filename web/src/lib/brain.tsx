import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { loadConnectome, Sim, type Connectome } from './connectome'

interface BrainCtx { conn: Connectome | null; sim: Sim | null; tick: number }
const Ctx = createContext<BrainCtx>({ conn: null, sim: null, tick: 0 })

// 앱 전체에서 커넥텀 하나, 시뮬레이터 하나를 공유한다. 약 30Hz 로 진행.
export function BrainProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<BrainCtx>({ conn: null, sim: null, tick: 0 })

  useEffect(() => {
    let alive = true
    let timer = 0
    let uiTick = 0
    loadConnectome().then((conn) => {
      if (!alive) return
      const sim = new Sim(conn)
      ;(window as unknown as { __fv: Sim }).__fv = sim
      // 기저 활동: 데이터 스트림이 조용히 흘러 들어오는 상태
      let last = performance.now()
      const loop = () => {
        if (!alive) return
        const now = performance.now()
        if (now - last > 30) {
          last = now
          if (sim.t % 45 === 0) sim.stimulate('channel', ['faers', 'literature', 'trials', 'label', 'digital'][Math.floor(Math.random() * 5)], 0.55, 5)
          sim.step()
          if (++uiTick % 6 === 0) setState((s) => ({ ...s, tick: sim.t }))
        }
        timer = requestAnimationFrame(loop)
      }
      setState({ conn, sim, tick: 0 })
      loop()
    })
    return () => { alive = false; cancelAnimationFrame(timer) }
  }, [])

  return <Ctx.Provider value={state}>{children}</Ctx.Provider>
}

export const useBrain = () => useContext(Ctx)
