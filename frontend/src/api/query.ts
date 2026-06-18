import api from "./index"

export const queryApi = {
  ask: (datasource_id: string, question: string, deepAnalyze: boolean = false, signal?: AbortSignal) =>
    api.post("/query/ask", { datasource_id: datasource_id || "", question, deep_analyze: deepAnalyze }, { signal }),
  askAuto: (question: string, deepAnalyze: boolean = false, signal?: AbortSignal) =>
    api.post("/query/ask", { datasource_id: "", question, deep_analyze: deepAnalyze }, { signal }),
  history: () => api.get("/query/history"),
  detail: (id: string) => api.get(`/query/history/${id}`),
}