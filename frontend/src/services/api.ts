import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  withCredentials: true,
})

api.interceptors.request.use((config) => {
  // Dynamic import to avoid circular deps
  const token = (window as any).__accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && !error.config._retry) {
      error.config._retry = true
      try {
        const { data } = await axios.post(
          `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/auth/refresh`,
          {},
          { withCredentials: true }
        )
        ;(window as any).__accessToken = data.access_token
        error.config.headers.Authorization = `Bearer ${data.access_token}`
        return api(error.config)
      } catch {
        ;(window as any).__accessToken = null
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
