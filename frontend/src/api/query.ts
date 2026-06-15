import api from './index'

export const queryApi = {
  ask: (datasource_id: string, question: string, signal?: AbortSignal) =>
    api.post('/query/ask', { datasource_id, question }, { signal }),
  history: () => api.get('/query/history'),
  detail: (id: string) => api.get(`/query/history/${id}`),
}
