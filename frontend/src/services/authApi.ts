import api from './api'
import type { User } from '@/types'

export const authApi = {
  refresh: () => api.post<{ access_token: string }>('/api/auth/refresh'),
  logout: () => api.post('/api/auth/logout'),
  getMe: () => api.get<User>('/api/users/me'),
}
