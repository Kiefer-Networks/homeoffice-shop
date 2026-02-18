import api from './api'
import type { User, BudgetResponse } from '@/types'

export const authApi = {
  refresh: () => api.post<{ access_token: string }>('/api/auth/refresh'),
  logout: () => api.post('/api/auth/logout'),
  getMe: () => api.get<User>('/api/users/me'),
  getBudget: () => api.get<BudgetResponse>('/api/users/me/budget'),
}
