import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

export type ThemeChoice = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

interface ThemeContextValue {
  /** What the user picked, including "system". */
  choice: ThemeChoice
  /** What is actually applied right now. */
  resolved: ResolvedTheme
  setChoice: (choice: ThemeChoice) => void
  /** Light ↔ dark, keeping "system" out of the cycle. */
  toggle: () => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)
const STORAGE_KEY = 'slcc.theme'

function systemTheme(): ResolvedTheme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(resolved: ResolvedTheme) {
  const root = document.documentElement
  root.classList.toggle('dark', resolved === 'dark')
  root.setAttribute('data-theme', resolved)
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setChoiceState] = useState<ThemeChoice>(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system'
  })
  const [resolved, setResolved] = useState<ResolvedTheme>(() =>
    (window.localStorage.getItem(STORAGE_KEY) as ThemeChoice) === 'dark'
      ? 'dark'
      : (window.localStorage.getItem(STORAGE_KEY) as ThemeChoice) === 'light'
        ? 'light'
        : systemTheme(),
  )

  useEffect(() => {
    const next = choice === 'system' ? systemTheme() : choice
    setResolved(next)
    applyTheme(next)
    window.localStorage.setItem(STORAGE_KEY, choice)
  }, [choice])

  // Follow the OS while the user stays on "system".
  useEffect(() => {
    if (choice !== 'system') return
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => {
      const next = systemTheme()
      setResolved(next)
      applyTheme(next)
    }
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [choice])

  const setChoice = useCallback((next: ThemeChoice) => setChoiceState(next), [])
  const toggle = useCallback(
    () => setChoiceState(resolved === 'dark' ? 'light' : 'dark'),
    [resolved],
  )

  const value = useMemo(
    () => ({ choice, resolved, setChoice, toggle }),
    [choice, resolved, setChoice, toggle],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used inside a ThemeProvider')
  }
  return context
}
