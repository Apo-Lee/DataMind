import api from './index'

export const dashboardApi = {
  getPanels: () => api.get('/dashboard/panels'),
  refreshPanel: (datasourceId: string, isPrimary?: boolean) => api.post(`/dashboard/panels/${datasourceId}/refresh${isPrimary ? '?is_primary=true' : ''}`),
  getPanelDetail: (datasourceId: string) => api.get(`/dashboard/panels/${datasourceId}/detail`),
  getConfig: (datasourceId: string) => api.get(`/dashboard/panels/${datasourceId}/config`),
  saveConfig: (datasourceId: string, enabledKpiIds: string[]) =>
    api.put(`/dashboard/panels/${datasourceId}/config`, { enabled_kpi_ids: enabledKpiIds }),
}
