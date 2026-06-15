import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  { path: '/login', name: 'Login', component: () => import('@/views/Login.vue'), meta: { guest: true } },
  {
    path: '/dashboard', component: () => import('@/components/AppLayout.vue'), meta: { requiresAuth: true, adminOnly: true },
    children: [
      { path: '', redirect: '/dashboard/overview' },
      { path: 'overview', name: 'Overview', component: () => import('@/views/dashboard/Overview.vue') },
      { path: 'datasources', name: 'DataSources', component: () => import('@/views/dashboard/DataSources.vue') },
      { path: 'users', name: 'Users', component: () => import('@/views/dashboard/Users.vue') },
      // V2: 新增运维管理子页面
      { path: 'permissions', name: 'Permissions', component: () => import('@/views/dashboard/Permissions.vue') },
      { path: 'monitor', name: 'Monitor', component: () => import('@/views/dashboard/Monitor.vue') },
      { path: 'audit-logs', name: 'AuditLogs', component: () => import('@/views/dashboard/AuditLogs.vue') },
      { path: 'hr-sync', name: 'HrSync', component: () => import('@/views/dashboard/HrSync.vue') },
      { path: 'system-config', name: 'SystemConfig', component: () => import('@/views/dashboard/SystemConfig.vue') },
    ],
  },
  {
    path: '/analyst', component: () => import('@/components/AppLayout.vue'), meta: { requiresAuth: true },
    children: [
      { path: '', name: 'DashboardView', component: () => import('@/views/analyst/DashboardView.vue') },
      { path: ':id', name: 'ReportView', component: () => import('@/views/analyst/ReportView.vue') },
      { path: 'panel/:id', name: 'PanelDetail', component: () => import('@/views/analyst/PanelDetail.vue') },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/analyst' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()
  const token = localStorage.getItem('access_token')

  // 有 token 但未加载用户信息时，先向后端验证
  if (token && !authStore.user) {
    await authStore.fetchUser()
  }

  const isLoggedIn = !!authStore.user && !!token

  if (to.meta.requiresAuth && !isLoggedIn) {
    return next('/login')
  }
  if (to.meta.guest && isLoggedIn) {
    return next(authStore.user?.role === 'admin' ? '/dashboard/overview' : '/analyst')
  }
  if (to.meta.adminOnly && authStore.user?.role !== 'admin') {
    return next('/analyst')
  }
  next()
})

export default router
