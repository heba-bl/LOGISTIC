import { useCallback, useEffect, useRef, useState } from 'react'

import { toErrorMessage } from '@/services/apiClient'

export interface ApiResource<T> {
  data: T | null
  loading: boolean
  /** True only for the first load, so refreshes do not blank the screen. */
  initialLoading: boolean
  error: string | null
  /** When the last successful read landed, or null if none ever did. */
  lastSuccessAt: Date | null
  /**
   * Figures on screen while the API is unreachable.
   *
   * A failed refresh keeps whatever the screen already had rather than blanking
   * it: in a control room an empty panel is a panel somebody turns off, while
   * frozen figures that say how old they are remain usable. The caller must
   * show that age - stale data presented as current is worse than none.
   */
  stale: boolean
  refresh: () => Promise<void>
  setData: (value: T) => void
}

/**
 * Fetch a backend resource with loading/error state and manual refresh.
 *
 * Deliberately tiny: the app needs request state and revalidation after a write,
 * not a full data layer.
 */
export function useApiResource<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
  options: { pollMs?: number; enabled?: boolean } = {},
): ApiResource<T> {
  const { pollMs, enabled = true } = options
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(enabled)
  const [initialLoading, setInitialLoading] = useState(enabled)
  const [error, setError] = useState<string | null>(null)
  //: When the last successful read happened. A failed refresh keeps the
  //: data it already had, so a screen can go on showing figures - as long
  //: as it says out loud how old they are.
  const [lastSuccessAt, setLastSuccessAt] = useState<Date | null>(null)
  const mounted = useRef(true)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const refresh = useCallback(async () => {
    if (!enabled) return
    setLoading(true)
    try {
      const payload = await fetcherRef.current()
      if (!mounted.current) return
      setData(payload)
      setError(null)
      setLastSuccessAt(new Date())
    } catch (err) {
      if (!mounted.current) return
      setError(toErrorMessage(err))
    } finally {
      if (mounted.current) {
        setLoading(false)
        setInitialLoading(false)
      }
    }
  }, [enabled])

  useEffect(() => {
    mounted.current = true
    void refresh()
    return () => {
      mounted.current = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refresh, ...deps])

  useEffect(() => {
    if (!pollMs || !enabled) return
    const timer = window.setInterval(() => void refresh(), pollMs)
    return () => window.clearInterval(timer)
  }, [pollMs, refresh, enabled])

  return { data, loading, initialLoading, error, refresh, setData,
    lastSuccessAt,
    //: Data on screen while the API is unreachable.
    stale: error !== null && data !== null,
  }
}
