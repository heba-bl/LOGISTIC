import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { apiClient, toErrorMessage } from '@/services/apiClient'
import type { User } from '@/types/domain'

/**
 * Who is signed into the supervision site.
 *
 * Deliberately not a security boundary: the identity is kept in the browser and
 * the API does not require it. It is the access *rule* made visible - this site
 * belongs to the direction and the chef logistique, and everyone else works in
 * the workbook. A deployment would put a real session token behind this; the
 * shape of the check would not change.
 */
interface SessionValue {
  user: User | null
  /** Returns an error message, or null when the sign-in succeeded. */
  signIn: (matricule: string, code: string) => Promise<string | null>
  signOut: () => void
}

const SessionContext = createContext<SessionValue | null>(null)

const STORAGE_KEY = 'slcc.session'

function restore(): User | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    // A corrupted entry must not lock the site: fall back to signed out.
    return null
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(restore)

  const signIn = useCallback(async (matricule: string, code: string) => {
    try {
      const { data } = await apiClient.post<{ user: User }>('/auth/login', {
        matricule,
        code,
      })
      setUser(data.user)
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(data.user))
      return null
    } catch (error) {
      return toErrorMessage(error)
    }
  }, [])

  const signOut = useCallback(() => {
    setUser(null)
    window.localStorage.removeItem(STORAGE_KEY)
  }, [])

  const value = useMemo(() => ({ user, signIn, signOut }), [user, signIn, signOut])
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): SessionValue {
  const context = useContext(SessionContext)
  if (!context) throw new Error('useSession must be used inside SessionProvider')
  return context
}
