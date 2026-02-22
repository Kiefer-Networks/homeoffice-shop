import axios, { type AxiosError, type AxiosRequestConfig } from 'axios'
import { getAccessToken, setAccessToken } from '@/lib/token'
import { useAuthStore } from '@/stores/authStore'

const MAX_RETRIES = 2
const RETRY_DELAY_MS = 1000

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

function shouldRetry(error: AxiosError): boolean {
  if (!error.response) return true // Network error
  return error.response.status >= 500 && error.response.status < 600
}

const RETRYABLE_METHODS = new Set(['get', 'put', 'delete'])

let refreshPromise: Promise<any> | null = null

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  withCredentials: true,
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as AxiosRequestConfig & { _retry?: boolean; _retryCount?: number }
    if (!config) return Promise.reject(error)

    // Retry logic for network errors and 5xx responses (non-POST only)
    const method = (config.method || '').toLowerCase()
    if (
      shouldRetry(error) &&
      RETRYABLE_METHODS.has(method) &&
      (config._retryCount ?? 0) < MAX_RETRIES
    ) {
      config._retryCount = (config._retryCount ?? 0) + 1
      await sleep(RETRY_DELAY_MS * config._retryCount)
      return api(config)
    }

    // 401 token refresh with mutex to avoid concurrent refreshes
    const url = config.url || ''
    if (
      error.response?.status === 401 &&
      !config._retry &&
      !url.includes('/auth/refresh')
    ) {
      config._retry = true
      try {
        if (!refreshPromise) {
          refreshPromise = axios.post(
            `${import.meta.env.VITE_API_URL || ''}/api/auth/refresh`,
            {},
            { withCredentials: true }
          ).then(({ data }) => {
            setAccessToken(data.access_token)
            useAuthStore.getState().setAccessToken(data.access_token)
            return data.access_token
          }).catch((err) => {
            setAccessToken(null)
            useAuthStore.getState().logout()
            throw err
          }).finally(() => {
            refreshPromise = null
          })
        }
        const newToken = await refreshPromise
        config.headers = config.headers || {}
        ;(config.headers as Record<string, string>).Authorization = `Bearer ${newToken}`
        return api(config)
      } catch {
        // Refresh failed – already handled above (logout)
      }
    }
    return Promise.reject(error)
  }
)

export default api
