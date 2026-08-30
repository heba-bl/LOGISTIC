/** Payloads exchanged with the FastAPI backend. */

export interface HealthResponse {
  status: string
  service: string
}

export interface DatabaseHealthResponse {
  status: string
  dialect: string
  url: string
  connected: boolean
  fallback: boolean
  detail: string | null
}

export interface ServiceInfoResponse {
  service: string
  project: string
  version: string
  environment: string
  api_prefix: string
}

/** Connection state of the API as seen by the UI. */
export type ApiStatus = 'connecting' | 'online' | 'offline'
