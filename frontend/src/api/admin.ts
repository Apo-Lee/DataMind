import api from './index'
import type { AxiosInstance } from 'axios'

export default api as AxiosInstance

// ---- V2: 管理后台 API ----
export const adminApi = {
  // 系统监控
  monitorHealth: () => api.get('/admin/monitor/health'),
  monitorStats: () => api.get('/admin/monitor/stats'),

  // 审计日志
  listAuditLogs: (params?: { page?: number; page_size?: number; action?: string; username?: string }) =>
    api.get('/admin/audit-logs', { params }),
  getAuditLog: (id: string) => api.get(`/admin/audit-logs/${id}`),

  // HR 同步
  triggerHrSync: () => api.post('/admin/hr-sync/trigger'),
  getHrSyncStatus: () => api.get('/admin/hr-sync/status'),
  listHrSyncLogs: () => api.get('/admin/hr-sync/logs'),

  // 系统配置
  listConfigs: () => api.get('/admin/configs'),
  getConfig: (key: string) => api.get(`/admin/configs/${key}`),
  updateConfig: (key: string, value: string, valueType?: string) =>
    api.put(`/admin/configs/${key}`, { value, value_type: valueType }),

  // 数据权限
  listUserPermissions: () => api.get('/admin/permissions/users'),
  updateUserPermission: (userId: string, data: { data_scope?: string; extra_dept_ids?: number[] }) =>
    api.put(`/admin/permissions/users/${userId}`, data),
  listDatasourcePermissions: () => api.get('/admin/permissions/datasources'),
  updateDatasourcePermissions: (dsId: string, grants: any[]) =>
    api.put(`/admin/permissions/datasources/${dsId}`, { grants }),
}
