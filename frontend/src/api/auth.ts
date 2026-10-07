import { api } from './client'

export type Role = 'CEO' | 'HR' | 'IT' | 'SALES' | 'INVENTORY'

export type CurrentUser = {
  id: number
  username: string
  email: string
  role: Role
}

export const authApi = {
  me: () => api.get<CurrentUser>('/api/auth/me/'),
  login: (username: string, password: string) => api.post<CurrentUser>('/api/auth/login/', { username, password }),
  logout: () => api.post('/api/auth/logout/'),
}
