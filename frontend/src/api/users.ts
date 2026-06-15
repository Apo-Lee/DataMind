import api from './index'

export const usersApi = {
  list: () => api.get('/users'),
  create: (data: any) => api.post('/users', data),
  update: (id: string, data: any) => api.put(`/users/${id}`, data),
  remove: (id: string) => api.delete(`/users/${id}`),
}
