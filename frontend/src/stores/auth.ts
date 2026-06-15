import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<any>(null)
  const isLoggedIn = ref(false)

  async function login(username: string, password: string) {
    const resp = await authApi.login(username, password)
    const { access_token, refresh_token } = resp.data
    localStorage.setItem('access_token', access_token)
    localStorage.setItem('refresh_token', refresh_token)
    await fetchUser()
    return resp.data
  }

  async function refreshToken() {
    const rt = localStorage.getItem('refresh_token')
    if (!rt) throw new Error('no refresh token')
    const resp = await authApi.refresh(rt)
    localStorage.setItem('access_token', resp.data.access_token)
    return resp.data.access_token
  }

  async function fetchUser() {
    try {
      const resp = await authApi.me()
      user.value = resp.data
      isLoggedIn.value = true
      localStorage.setItem('user_role', resp.data.role)
    } catch (e: any) {
      if (e?.response?.status === 401) {
        try {
          await refreshToken()
          const resp = await authApi.me()
          user.value = resp.data
          isLoggedIn.value = true
          localStorage.setItem('user_role', resp.data.role)
          return
        } catch {
          // refresh 也失败，强制登出
        }
      }
      logout()
      const router = useRouter()
      router.push('/login')
    }
  }

  function logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user_role')
    user.value = null
    isLoggedIn.value = false
  }

  return { user, isLoggedIn, login, fetchUser, logout, refreshToken }
})
