import axios from 'axios'
import { getAccessToken, setAccessToken } from '@/lib/token'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  withCredentials: true,
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
  async (error) => {
    const url = error.config?.url || ''
    if (
      error.response?.status === 401 &&
      !error.config._retry &&
      !url.includes('/auth/refresh')
    ) {
      error.config._retry = true
      try {
        const { data } = await axios.post(
          `${import.meta.env.VITE_API_URL || ''}/api/auth/refresh`,
          {},
          { withCredentials: true }
        )
        setAccessToken(data.access_token)
        error.config.headers.Authorization = `Bearer ${data.access_token}`
        return api(error.config)
      } catch {
        setAccessToken(null)
      }
    }
    return Promise.reject(error)
  }
)

export default api
