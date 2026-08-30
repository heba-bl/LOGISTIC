import axios, { AxiosError } from 'axios'

/**
 * Shared Axios instance.
 *
 * The base URL comes from `VITE_API_BASE_URL` (see `.env.example`) and falls
 * back to the local FastAPI server.
 */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api'

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 8000,
  headers: { 'Content-Type': 'application/json' },
  // FastAPI reads repeated keys (`status=A&status=B`). Axios would otherwise
  // emit `status[]=A`, which the backend silently ignores - dropping the filter.
  paramsSerializer: { indexes: null },
})

/** Normalise Axios failures into a readable message for the UI. */
export function toErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ detail?: string }>
    if (axiosError.response) {
      return axiosError.response.data?.detail ?? `HTTP ${axiosError.response.status}`
    }
    if (axiosError.code === 'ECONNABORTED') return 'Request timed out'
    return 'API unreachable'
  }
  return error instanceof Error ? error.message : 'Unknown error'
}

apiClient.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(error),
)
