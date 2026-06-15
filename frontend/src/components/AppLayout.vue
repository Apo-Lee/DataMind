<template>
  <div class="app-shell" :class="{ 'no-sidebar': !showSidebar }">
    <!-- 侧边导航 -->
    <aside v-if="showSidebar" class="sidebar">
      <div class="sidebar-brand" @click="$router.push(isAdmin ? '/dashboard' : '/analyst')">
        <svg class="brand-logo" viewBox="0 0 36 36" fill="none">
          <rect x="2" y="2" width="13" height="13" rx="3" fill="currentColor" opacity="0.9" />
          <rect x="19" y="2" width="15" height="8" rx="3" fill="currentColor" opacity="0.5" />
          <rect x="19" y="14" width="6" height="18" rx="3" fill="currentColor" opacity="0.7" />
          <rect x="29" y="14" width="5" height="12" rx="2" fill="currentColor" opacity="0.4" />
          <rect x="2" y="19" width="13" height="13" rx="3" fill="currentColor" opacity="0.6" />
        </svg>
        <span class="brand-text">DataMind</span>
      </div>

      <nav class="sidebar-nav">
        <div class="nav-section-label">分析工作台</div>
        <router-link to="/analyst" class="nav-item" :class="{ active: route.path === '/analyst' || route.path.startsWith('/analyst/') }">
          <svg viewBox="0 0 20 20" fill="none">
            <rect x="2" y="2" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.5" />
            <rect x="11" y="2" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.5" />
            <rect x="2" y="11" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.5" />
            <rect x="11" y="11" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.5" />
          </svg>
          <span>BI 驾驶舱</span>
        </router-link>

        <!-- P1-2: 非 admin 用户仅展现 BI 驾驶舱入口，admin 展现完整管理菜单 -->
        <template v-if="isAdmin">
          <div class="nav-section-label">系统管理</div>
          <router-link to="/dashboard/overview" class="nav-item"
                       :class="{ active: route.path.includes('/dashboard/overview') }">
            <svg viewBox="0 0 20 20" fill="none">
              <path d="M3 17V10l4 3 4-5 4 3 2-2v8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <span>系统概览</span>
          </router-link>
          <router-link to="/dashboard/datasources" class="nav-item"
                       :class="{ active: route.path.includes('/datasources') }">
            <svg viewBox="0 0 20 20" fill="none">
              <ellipse cx="6" cy="5" rx="2" ry="2" stroke="currentColor" stroke-width="1.5" />
              <ellipse cx="14" cy="5" rx="2" ry="2" stroke="currentColor" stroke-width="1.5" />
              <ellipse cx="6" cy="15" rx="2" ry="2" stroke="currentColor" stroke-width="1.5" />
              <ellipse cx="14" cy="15" rx="2" ry="2" stroke="currentColor" stroke-width="1.5" />
              <path d="M6 7v6M14 7v6M8 5h4M8 15h4" stroke="currentColor" stroke-width="1.5" />
            </svg>
            <span>数据源</span>
          </router-link>
          <router-link to="/dashboard/users" class="nav-item"
                       :class="{ active: route.path.includes('/dashboard/users') }">
            <svg viewBox="0 0 20 20" fill="none">
              <circle cx="10" cy="7" r="3" stroke="currentColor" stroke-width="1.5" />
              <path d="M4 17c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
            </svg>
            <span>用户</span>
          </router-link>
          <div class="nav-section-label">运维管理</div>
          <router-link to="/dashboard/permissions" class="nav-item"
                       :class="{ active: route.path.includes('/permissions') }">
            <svg viewBox="0 0 20 20" fill="none">
              <path d="M7 10h6M10 7v6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
              <rect x="3" y="3" width="14" height="14" rx="3" stroke="currentColor" stroke-width="1.5" />
            </svg>
            <span>数据权限</span>
          </router-link>
          <router-link to="/dashboard/monitor" class="nav-item"
                       :class="{ active: route.path.includes('/monitor') }">
            <svg viewBox="0 0 20 20" fill="none">
              <rect x="2" y="15" width="3" height="0" rx="1" stroke="currentColor" stroke-width="1.5" />
              <rect x="7" y="10" width="3" height="5" rx="1" stroke="currentColor" stroke-width="1.5" />
              <rect x="12" y="6" width="3" height="9" rx="1" stroke="currentColor" stroke-width="1.5" />
              <rect x="3" y="4" width="3" height="11" rx="1" stroke="currentColor" stroke-width="1.5" opacity="0.5" />
              <rect x="8" y="8" width="3" height="7" rx="1" stroke="currentColor" stroke-width="1.5" opacity="0.5" />
              <rect x="13" y="5" width="3" height="10" rx="1" stroke="currentColor" stroke-width="1.5" opacity="0.5" />
            </svg>
            <span>系统监控</span>
          </router-link>
          <router-link to="/dashboard/audit-logs" class="nav-item"
                       :class="{ active: route.path.includes('/audit-logs') }">
            <svg viewBox="0 0 20 20" fill="none">
              <rect x="3" y="3" width="14" height="14" rx="2" stroke="currentColor" stroke-width="1.5" />
              <path d="M7 8h6M7 12h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
            </svg>
            <span>审计日志</span>
          </router-link>
          <router-link to="/dashboard/hr-sync" class="nav-item"
                       :class="{ active: route.path.includes('/hr-sync') }">
            <svg viewBox="0 0 20 20" fill="none">
              <path d="M14 5l3 3-3 3M6 15l-3-3 3-3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
              <path d="M17 8H7M3 12h10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
            </svg>
            <span>HR 同步</span>
          </router-link>
          <router-link to="/dashboard/system-config" class="nav-item"
                       :class="{ active: route.path.includes('/system-config') }">
            <svg viewBox="0 0 20 20" fill="none">
              <circle cx="10" cy="10" r="3" stroke="currentColor" stroke-width="1.5" />
              <path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.9 4.9l1.4 1.4M13.7 13.7l1.4 1.4M4.9 15.1l1.4-1.4M13.7 6.3l1.4-1.4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
            </svg>
            <span>系统配置</span>
          </router-link>
        </template>
      </nav>

      <div class="sidebar-footer">
        <div class="user-badge">
          <div class="user-avatar">{{ user?.display_name?.[0] || '?' }}</div>
          <div class="user-info">
            <div class="user-name">{{ user?.display_name }}</div>
            <div class="user-role">{{ roleLabel(user?.role) }}</div>
          </div>
        </div>
        <button class="logout-btn" @click="handleLogout" title="退出">
          <svg viewBox="0 0 20 20" fill="none">
            <path d="M13 10H3M5 6l-4 4 4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M13 5h2a3 3 0 013 3v4a3 3 0 01-3 3h-2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
          </svg>
        </button>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="main-area">
      <!-- 纯工作区：BI驾驶舱无顶部头栏，管理页才有 -->
      <header v-if="showSidebar && !isAnalystOnly" class="top-bar">
        <div class="top-bar-left">
          <span class="top-bar-title">{{ pageTitle }}</span>
        </div>
        <div class="top-bar-right">
          <span class="top-bar-greeting">{{ user?.display_name }}</span>
        </div>
      </header>
      <div class="main-content" :class="{ 'flush': isAnalystOnly }">
        <router-view />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const user = computed(() => authStore.user)
const isAdmin = computed(() => user.value?.role === 'admin')

// P1-2: 非 admin 用户也展现最小侧边栏（仅"BI 驾驶舱"入口和用户信息）
// admin 用户展现完整侧边栏（含管理页面）
const showSidebar = computed(() => true)

// 纯 BI 工作区
const isAnalystOnly = computed(() => route.path.startsWith('/analyst'))

const pageTitle = computed(() => {
  if (route.path.includes('permissions')) return '数据权限分配'
  if (route.path.includes('monitor')) return '系统监控'
  if (route.path.includes('audit-logs')) return '操作审计日志'
  if (route.path.includes('hr-sync')) return 'HR 数据同步'
  if (route.path.includes('system-config')) return '系统配置'
  if (route.path.includes('datasources')) return '数据源管理'
  if (route.path.includes('users')) return '用户管理'
  if (route.path.includes('overview')) return '系统概览'
  return ''
})

function roleLabel(role?: string) {
  const map: Record<string,string> = { admin:'管理员', hr_director:'HR总监', finance_bp:'财务BP', finance_director:'财务总监', dept_ceo:'部门CEO', dept_manager:'部门经理', sales_manager:'销售经理', employee:'员工', viewer:'只读' }
  return map[role || ''] || role || ''
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}

// 如果不在登录页且未登录
if (route.path !== '/login' && localStorage.getItem('access_token')) {
  authStore.fetchUser().catch(() => {})
}
</script>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: var(--dm-surface);
}

/* ===== 侧边栏 ===== */
.sidebar {
  width: 240px;
  min-width: 240px;
  background: var(--dm-deep);
  display: flex;
  flex-direction: column;
  user-select: none;
}
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 20px 12px;
  cursor: pointer;
}
.brand-logo {
  width: 36px;
  height: 36px;
  color: var(--dm-primary);
  flex-shrink: 0;
}
.brand-text {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 800;
  color: #fff;
  letter-spacing: -0.02em;
}
.sidebar-nav {
  flex: 1;
  padding: 8px 12px;
  overflow-y: auto;
}
.nav-section-label {
  font-size: 10px;
  font-weight: 700;
  color: rgba(255,255,255,0.25);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 16px 10px 8px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  color: rgba(255,255,255,0.55);
  text-decoration: none;
  font-size: 13.5px;
  font-weight: 500;
  transition: all 0.15s var(--ease-out);
  margin-bottom: 2px;
}
.nav-item svg {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}
.nav-item:hover {
  color: #fff;
  background: rgba(255,255,255,0.06);
}
.nav-item.active {
  color: #fff;
  background: rgba(91, 95, 227, 0.25);
}
.nav-item.active svg {
  color: var(--dm-primary);
}

.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid rgba(255,255,255,0.06);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.user-badge {
  display: flex;
  align-items: center;
  gap: 10px;
}
.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--dm-primary), #818CF8);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  letter-spacing: 0.05em;
}
.user-info {
  line-height: 1.3;
}
.user-name {
  font-size: 13px;
  font-weight: 600;
  color: #fff;
}
.user-role {
  font-size: 11px;
  color: rgba(255,255,255,0.4);
}
.logout-btn {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  border: none;
  background: rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.4);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s var(--ease-out);
}
.logout-btn svg {
  width: 16px;
  height: 16px;
}
.logout-btn:hover {
  background: rgba(244,63,94,0.2);
  color: var(--dm-rose);
}

/* ===== 主区域 ===== */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.top-bar {
  height: 52px;
  min-height: 52px;
  background: var(--dm-card);
  border-bottom: 1px solid var(--dm-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}
.top-bar-title {
  font-weight: 700;
  font-size: 15px;
  color: var(--dm-text);
}
.top-bar-greeting {
  font-size: 13px;
  color: var(--dm-muted);
}
.main-content {
  flex: 1;
  overflow: auto;
  padding: 24px;
}
.main-content.flush {
  padding: 0;
  background: var(--dm-surface);
}

/* ===== BI 无侧栏 ===== */
.no-sidebar .main-content {
  padding: 0;
}

/* 响应式 */
@media (max-width: 768px) {
  .sidebar {
    width: 200px;
    min-width: 200px;
  }
  .main-content {
    padding: 16px;
  }
}
</style>
