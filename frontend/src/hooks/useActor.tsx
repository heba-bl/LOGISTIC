import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { catalogApi } from '@/services/slcc.service'
import type { User } from '@/types/domain'

/**
 * Simulated identity.
 *
 * The project has no authentication: roles are simulated, and the operator picks
 * who they are acting as. Every write carries that actor id so the audit trail
 * records a real name rather than "system".
 */
interface ActorContextValue {
  users: User[]
  actor: User | null
  actorId: number | null
  setActor: (user: User) => void
  loading: boolean
  /** Users owning a given role, used to preselect the right operator per screen. */
  byRole: (roleName: string) => User | undefined
}

const ActorContext = createContext<ActorContextValue | null>(null)

const STORAGE_KEY = 'slcc.actor'

export function ActorProvider({ children }: { children: ReactNode }) {
  const [users, setUsers] = useState<User[]>([])
  const [actor, setActorState] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    catalogApi
      .users()
      .then((list) => {
        if (cancelled) return
        setUsers(list)
        const stored = window.localStorage.getItem(STORAGE_KEY)
        const restored = stored ? list.find((user) => user.username === stored) : undefined
        const manager = list.find((user) => user.role?.name === 'LOGISTICS_MANAGER')
        setActorState(restored ?? manager ?? list[0] ?? null)
      })
      .catch(() => {
        if (!cancelled) setUsers([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const setActor = useCallback((user: User) => {
    setActorState(user)
    window.localStorage.setItem(STORAGE_KEY, user.username)
  }, [])

  const byRole = useCallback(
    (roleName: string) => users.find((user) => user.role?.name === roleName),
    [users],
  )

  const value = useMemo(
    () => ({ users, actor, actorId: actor?.id ?? null, setActor, loading, byRole }),
    [users, actor, setActor, loading, byRole],
  )

  return <ActorContext.Provider value={value}>{children}</ActorContext.Provider>
}

export function useActor(): ActorContextValue {
  const context = useContext(ActorContext)
  if (!context) {
    throw new Error('useActor must be used inside an ActorProvider')
  }
  return context
}
