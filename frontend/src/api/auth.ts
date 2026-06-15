import api from './index'

export const authApi = {
  login: (username: string, password: string) => api.post('/auth/login', { username, password }),
  refresh: (refresh_token: string) => api.post('/auth/refresh', { refresh_token }),
  me: () => api.get('/auth/me'),
}
