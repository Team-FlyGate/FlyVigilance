import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

// 한국어(기본)와 영어를 오가는 아주 작은 i18n 도우미입니다.
// 문구는 t('한국어 원문', 'English') 처럼 원문 바로 옆에 영어를 나란히 적습니다.
// 언어를 바꾸면 LangProvider 가 하위 트리를 key 로 다시 그리므로, 렌더 중에 부르는 t() 는
// 컴포넌트 안이든 밖의 도우미 함수든(캔버스 라벨 포함) 모두 새 언어를 따릅니다.
// 모듈을 불러올 때 한 번만 계산되는 상수에는 t() 를 쓰지 말고 함수로 감싸 렌더 시점에 부릅니다.

export type Lang = 'ko' | 'en'

const STORE_KEY = 'flygate.lang'

function readInitial(): Lang {
  try {
    const q = new URLSearchParams(location.search).get('lang')
    if (q === 'en' || q === 'ko') return q
  } catch { /* 주소를 읽지 못하면 저장값으로 넘어갑니다 */ }
  try {
    const s = localStorage.getItem(STORE_KEY)
    if (s === 'en' || s === 'ko') return s
  } catch { /* 저장소를 쓸 수 없는 환경(사생활 보호 창 등)에서는 기본값을 씁니다 */ }
  return 'ko'
}

let current: Lang = readInitial()

/** 지금 언어를 돌려줍니다. 렌더 밖(이벤트 처리, 캔버스 그리기)에서도 쓸 수 있습니다. */
export const getLang = (): Lang => current
export const isEn = (): boolean => current === 'en'

/** 한국어 원문과 영어를 나란히 받아 지금 언어에 맞는 쪽을 돌려줍니다. 문자열·JSX 모두 됩니다. */
export function t<T>(ko: T, en: T): T {
  return current === 'en' ? en : ko
}

interface LangCtx { lang: Lang; setLang: (l: Lang) => void }
const Ctx = createContext<LangCtx>({ lang: current, setLang: () => {} })

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(current)
  // 렌더보다 먼저 전역 값을 맞춰 두어야 같은 렌더 안의 t() 가 새 언어를 봅니다.
  current = lang

  const setLang = useCallback((l: Lang) => {
    current = l
    setLangState(l)
    try { localStorage.setItem(STORE_KEY, l) } catch { /* 저장하지 못해도 화면 전환은 그대로 합니다 */ }
    try {
      const u = new URL(location.href)
      if (l === 'en') u.searchParams.set('lang', 'en'); else u.searchParams.delete('lang')
      history.replaceState(history.state, '', u.pathname + u.search + u.hash)
    } catch { /* 주소를 바꾸지 못해도 화면 전환은 그대로 합니다 */ }
  }, [])

  useEffect(() => { document.documentElement.lang = lang }, [lang])

  return <Ctx.Provider value={{ lang, setLang }}><LangRoot key={lang}>{children}</LangRoot></Ctx.Provider>
}

function LangRoot({ children }: { children: ReactNode }) { return <>{children}</> }

export const useLang = () => useContext(Ctx)
