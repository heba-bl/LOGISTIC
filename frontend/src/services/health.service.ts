import { apiClient } from './apiClient'
import type { DatabaseHealthResponse, HealthResponse, ServiceInfoResponse } from '@/types'

/** GET /api/health — liveness probe driving the system status indicator. */
export async function fetchHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get<HealthResponse>('/health')
  return data
}

/** GET /api/health/db — which database backend is actually serving the API. */
export async function fetchDatabaseHealth(): Promise<DatabaseHealthResponse> {
  const { data } = await apiClient.get<DatabaseHealthResponse>('/health/db')
  return data
}

/** GET /api/info — static service metadata. */
export async function fetchServiceInfo(): Promise<ServiceInfoResponse> {
  const { data } = await apiClient.get<ServiceInfoResponse>('/info')
  return data
}
