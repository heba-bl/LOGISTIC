import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchHealth } from '@/services/health.service'
import { toErrorMessage } from '@/services/apiClient'
import type { ApiStatus, HealthResponse } from '@/types'

interface UseApiHealthResult {
  status: ApiStatus
  service: string | null
  error: string | null
  lastCheckedAt: Date | null
  refresh: () => void
}

/**
 * Polls `GET /api/health` and exposes the connection state used by the
 * Mission Control status indicator.
 */
export function useApiHealth(intervalMs = 15000): UseApiHealthResult {
  const [status, setStatus] = useState<ApiStatus>('connecting')
  const [service, setService] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lastCheckedAt, setLastCheckedAt] = useState<Date | null>(null)
  const mounted = useRef(true)

  const check = useCallback(async () => {
    try {
      const payload: HealthResponse = await fetchHealth()
      if (!mounted.current) return
      setStatus(payload.status === 'ok' ? 'online' : 'offline')
      setService(payload.service)
      setError(null)
    } catch (err) {
      if (!mounted.current) return
      setStatus('offline')
      setError(toErrorMessage(err))
    } finally {
      if (mounted.current) setLastCheckedAt(new Date())
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    void check()
    const timer = window.setInterval(() => void check(), intervalMs)
    return () => {
      mounted.current = false
      window.clearInterval(timer)
    }
  }, [check, intervalMs])

  return { status, service, error, lastCheckedAt, refresh: () => void check() }
}
