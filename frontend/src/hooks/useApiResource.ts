import { useCallback, useEffect, useRef, useState } from 'react'

import { toErrorMessage } from '@/services/apiClient'

export interface ApiResource<T> {
  data: T | null
  loading: boolean
  /** True only for the first load, so refreshes do not blank the screen. */
  initialLoading: boolean
  error: string | null
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

  return { data, loading, initialLoading, error, refresh, setData }
}
