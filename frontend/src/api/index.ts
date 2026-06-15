import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({ baseURL: '/api', timeout: 120000 })

let isRefreshing = false
let refreshSubscribers: { resolve: (token: string) => void; reject: (err: any) => void }[] = []

function onRefreshed(token: string) {
  refreshSubscribers.forEach((sub) => sub.resolve(token))
  refreshSubscribers = []
}

function onRefreshFailed(err: any) {
  refreshSubscribers.forEach((sub) => sub.reject(err))
  refreshSubscribers = []
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const originalRequest = error.config
    const status = error.response?.status

    if (status === 401 && originalRequest && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          refreshSubscribers.push({
            resolve: (token: string) => {
              originalRequest.headers.Authorization = `Bearer ${token}`
              resolve(api(originalRequest))
            },
            reject,
          })
        })
      }

      isRefreshing = true
      originalRequest._retry = true

      try {
        const rt = localStorage.getItem('refresh_token')
        if (!rt) throw new Error('no refresh token')
        // 使用独立 axios 实例避免拦截器循环
        const resp = await axios.post('/api/auth/refresh', { refresh_token: rt })
        const newToken = resp.data.access_token
        localStorage.setItem('access_token', newToken)
        api.defaults.headers.common['Authorization'] = `Bearer ${newToken}`
        onRefreshed(newToken)
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return api(originalRequest)
      } catch (refreshError) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        onRefreshFailed(refreshError)
        if (!window.location.pathname.startsWith('/login')) {
          window.location.href = '/login'
        }
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    const msg = error.response?.data?.detail || error.message || '请求失败'
    // 不在 401 时显示 ElMessage（登录页自己处理 error）
    if (status !== 401) {
      ElMessage.error(msg)
    }
    return Promise.reject(error)
  }
)

export default api
