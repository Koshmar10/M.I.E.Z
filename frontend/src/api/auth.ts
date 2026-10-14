import { api } from './client'

export type Role = 'CEO' | 'HR' | 'IT' | 'SALES' | 'INVENTORY'

export type CurrentUser = {
  id: number
  username: string
  email: string
  role: Role
  first_name: string
  last_name: string
  phone: string
  address: string
  department_name: string | null
}

export const authApi = {
  me: () => api.get<CurrentUser>('/api/auth/me/'),
  login: (username: string, password: string) => api.post<CurrentUser>('/api/auth/login/', { username, password }),
  logout: () => api.post('/api/auth/logout/'),
}
