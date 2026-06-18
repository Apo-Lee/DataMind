<template>
  <div class="admin-page animate-in">
    <div class="page-top">
      <div>
        <h2 class="page-title">系统监控</h2>
        <p class="page-sub">各组件的运行状态 &amp; 24h 运营统计</p>
      </div>
      <button class="primary-btn" @click="refreshAll">刷新</button>
    </div>

    <!-- 健康状态 -->
    <section>
      <h3 class="section-title">组件健康度</h3>
      <div class="health-grid">
        <div v-for="c in health?.components" :key="c.component" class="health-card" :class="c.status">
          <span class="health-dot" :class="c.status" />
          <div class="health-body">
            <div class="health-name">{{ c.component }}</div>
            <div class="health-detail">{{ c.detail }}</div>
          </div>
          <span class="health-badge" :class="c.status">{{ statusLabel(c.status) }}</span>
        </div>
      </div>
      <div class="overall-bar" :class="health?.overall">
        整体状态: {{ health?.overall === 'healthy' ? '正常' : health?.overall === 'degraded' ? '部分降级' : '异常' }}
      </div>
    </section>

    <!-- 运营统计 -->
    <section>
      <h3 class="section-title">运营统计</h3>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-value">{{ stats?.total_users ?? '-' }}</div>
          <div class="stat-label">平台用户</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats?.active_users ?? '-' }}</div>
          <div class="stat-label">活跃用户</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats?.total_datasources ?? '-' }}</div>
          <div class="stat-label">数据源</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats?.total_queries ?? '-' }}</div>
          <div class="stat-label">累计查询</div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { adminApi } from '@/api/admin'
import { ElMessage } from "element-plus"

const health = ref<any>(null)
const stats = ref<any>(null)

async function refreshAll() {
  try { const r = await adminApi.monitorHealth(); health.value = r.data } catch (e: any) { ElMessage.error('获取健康状态失败') }
  try { const r = await adminApi.monitorStats(); stats.value = r.data } catch (e: any) { ElMessage.error('获取运营统计失败') }
}

function statusLabel(s: string) {
  return { ok: '正常', warning: '警告', error: '异常' }[s] || s
}

onMounted(refreshAll)
</script>

<style scoped>
.admin-page { display: flex; flex-direction: column; gap: 24px; }
.page-top { display: flex; justify-content: space-between; align-items: flex-start; }
.page-title { font-family: var(--font-display); font-size: 22px; font-weight: 800; color: var(--dm-text); margin: 0 0 4px; letter-spacing: -0.01em; }
.page-sub { font-size: 13px; color: var(--dm-muted); margin: 0; }
.section-title { font-size: 15px; font-weight: 700; margin: 0 0 12px; color: var(--dm-text); }
.primary-btn {
  display: inline-flex; align-items: center; gap: 6px; padding: 10px 22px;
  background: var(--dm-primary); color: #fff; border: none; border-radius: var(--radius-sm);
  font-size: 14px; font-weight: 600; font-family: var(--font-body); cursor: pointer;
}
.primary-btn:hover { background: #4A4ED1; }

.health-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
.health-card {
  display: flex; align-items: center; gap: 12px; padding: 14px 16px;
  border-radius: var(--radius-sm); background: var(--dm-card);
  border: 1px solid var(--dm-border);
}
.health-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.health-dot.ok { background: var(--dm-accent); }
.health-dot.warning { background: var(--dm-amber); }
.health-dot.error { background: var(--dm-rose); }
.health-body { flex: 1; min-width: 0; }
.health-name { font-size: 13px; font-weight: 600; color: var(--dm-text); }
.health-detail { font-size: 11px; color: var(--dm-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.health-badge { font-size: 11px; font-weight: 700; padding: 2px 10px; border-radius: 20px; }
.health-badge.ok { background: var(--dm-accent-soft); color: var(--dm-accent); }
.health-badge.warning { background: var(--dm-amber-soft); color: var(--dm-amber); }
.health-badge.error { background: var(--dm-rose-soft); color: var(--dm-rose); }
.overall-bar { margin-top: 12px; padding: 10px 16px; border-radius: var(--radius-sm); font-size: 13px; font-weight: 600; }
.overall-bar.healthy { background: var(--dm-accent-soft); color: var(--dm-accent); }
.overall-bar.degraded { background: var(--dm-amber-soft); color: var(--dm-amber); }
.overall-bar.down { background: var(--dm-rose-soft); color: var(--dm-rose); }

.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.stat-card {
  background: var(--dm-card); border: 1px solid var(--dm-border);
  border-radius: var(--radius-lg); padding: 20px; text-align: center;
}
.stat-value { font-size: 36px; font-weight: 800; font-family: var(--font-display); color: var(--dm-primary); }
.stat-label { font-size: 13px; color: var(--dm-muted); margin-top: 4px; }
</style>
