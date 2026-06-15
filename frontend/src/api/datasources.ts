import api from './index'

export const datasourcesApi = {
  list: () => api.get('/datasources'),
  create: (data: any) => api.post('/datasources', data),
  // V2: upload 已废弃 — 数据源管理改为只读系统预置
  update: (id: string, data: any) => api.put(`/datasources/${id}`, data),
  remove: (id: string) => api.delete(`/datasources/${id}`),
  test: (id: string) => api.post(`/datasources/${id}/test`),
  probe: (id: string) => api.post(`/datasources/${id}/probe`),
  getPermissions: (id: string) => api.get(`/datasources/${id}/permissions`),
  updatePermissions: (id: string, grants: any[]) => api.put(`/datasources/${id}/permissions`, { grants }),
}
