<template>
  <div class="admin-page animate-in">
    <div class="page-top">
      <div>
        <h2 class="page-title">系统概览</h2>
        <p class="page-sub">DataMind V2 平台运行概况</p>
      </div>
    </div>

    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-icon users">
          <svg viewBox="0 0 20 20" fill="none"><circle cx="10" cy="7" r="3" stroke="currentColor" stroke-width="1.5"/><path d="M4 17c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        </div>
        <div class="stat-body">
          <div class="stat-number">{{ stats.users }}</div>
          <div class="stat-label">平台用户</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon datasources">
          <svg viewBox="0 0 20 20" fill="none"><ellipse cx="6" cy="5" rx="2" ry="2" stroke="currentColor" stroke-width="1.5"/><ellipse cx="14" cy="5" rx="2" ry="2" stroke="currentColor" stroke-width="1.5"/><ellipse cx="6" cy="15" rx="2" ry="2" stroke="currentColor" stroke-width="1.5"/><ellipse cx="14" cy="15" rx="2" ry="2" stroke="currentColor" stroke-width="1.5"/><path d="M6 7v6M14 7v6M8 5h4M8 15h4" stroke="currentColor" stroke-width="1.5"/></svg>
        </div>
        <div class="stat-body">
          <div class="stat-number">{{ stats.datasources }}</div>
          <div class="stat-label">已接入数据源</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon queries">
          <svg viewBox="0 0 20 20" fill="none"><circle cx="9" cy="9" r="5" stroke="currentColor" stroke-width="1.5"/><path d="M16 16l-3-3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        </div>
        <div class="stat-body">
          <div class="stat-number">{{ stats.conversations }}</div>
          <div class="stat-label">累计查询</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon active">
          <svg viewBox="0 0 20 20" fill="none"><rect x="2" y="15" width="3" height="0" rx="1" stroke="currentColor" stroke-width="1.5"/><rect x="7" y="10" width="3" height="5" rx="1" stroke="currentColor" stroke-width="1.5"/><rect x="12" y="6" width="3" height="9" rx="1" stroke="currentColor" stroke-width="1.5"/></svg>
        </div>
        <div class="stat-body">
          <div class="stat-number">{{ stats.active_users }}</div>
          <div class="stat-label">活跃用户</div>
        </div>
      </div>
    </div>

    <div class="info-grid">
      <div class="info-card">
        <h3 class="info-title">V2 系统架构</h3>
        <div class="info-steps">
          <div class="step"><span class="step-num">1</span><div><strong>HR 数据锚点</strong><p>HR 系统作为组织架构唯一来源，统一管理</p></div></div>
          <div class="step"><span class="step-num">2</span><div><strong>HR 同步</strong><p>用户从 HR 自动同步，按职位映射角色</p></div></div>
          <div class="step"><span class="step-num">3</span><div><strong>行级权限</strong><p>上级看下级、部门隔离、跨部门授权</p></div></div>
          <div class="step"><span class="step-num">4</span><div><strong>运维管理</strong><p>系统监控、审计日志、HR同步、权限分配</p></div></div>
        </div>
      </div>
      <div class="info-card">
        <h3 class="info-title">预置数据源</h3>
        <div class="demo-list">
          <div class="demo-item"><span class="demo-dot hr" /><div><strong>HR 系统</strong><p>191 员工 · 17 部门 · 含层级汇报关系</p></div></div>
          <div class="demo-item"><span class="demo-dot crm" /><div><strong>CRM 系统</strong><p>800 客户 · 3000 交易 · 4000 跟进</p></div></div>
          <div class="demo-item"><span class="demo-dot fin" /><div><strong>费控系统</strong><p>181 预算 · 3000 费用 · 成本中心</p></div></div>
          <div class="demo-item"><span class="demo-dot erp" /><div><strong>ERP 系统</strong><p>20 项目 · 500 库存 · 300 采购订单</p></div></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { usersApi } from '@/api/users'
import { datasourcesApi } from '@/api/datasources'
import { adminApi } from '@/api/admin'

const stats = ref({ users: 0, datasources: 0, conversations: 0, active_users: 0 })
onMounted(async () => {
  try { stats.value.users = (await usersApi.list()).data.length } catch {}
  try { stats.value.datasources = (await datasourcesApi.list()).data.length } catch {}
  try {
    const monitorResp = await adminApi.monitorStats()
    stats.value.conversations = monitorResp.data.total_queries
    stats.value.active_users = monitorResp.data.active_users
  } catch {}
})
</script>

<style scoped>
.admin-page { display: flex; flex-direction: column; gap: 24px; }
.page-top { display: flex; justify-content: space-between; align-items: flex-start; }
.page-title { font-family: var(--font-display); font-size: 22px; font-weight: 800; color: var(--dm-text); margin: 0 0 4px; letter-spacing: -0.01em; }
.page-sub { font-size: 13px; color: var(--dm-muted); margin: 0; }

.stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.stat-card { background: var(--dm-card); border: 1px solid var(--dm-border); border-radius: var(--radius-lg); padding: 24px; display: flex; align-items: flex-start; gap: 16px; box-shadow: var(--shadow-card); transition: all 0.2s var(--ease-out); }
.stat-card:hover { box-shadow: var(--shadow-card-hover); transform: translateY(-2px); }
.stat-icon { width: 48px; height: 48px; border-radius: var(--radius); display: flex; align-items: center; justify-content: center; }
.stat-icon svg { width: 22px; height: 22px; }
.stat-icon.users { background: var(--dm-primary-soft); color: var(--dm-primary); }
.stat-icon.datasources { background: var(--dm-accent-soft); color: var(--dm-accent); }
.stat-icon.queries { background: var(--dm-amber-soft); color: var(--dm-amber); }
.stat-icon.active { background: var(--dm-rose-soft); color: var(--dm-rose); }
.stat-number { font-family: var(--font-display); font-size: 40px; font-weight: 800; color: var(--dm-text); letter-spacing: -0.02em; line-height: 1.1; }
.stat-label { font-size: 13px; color: var(--dm-muted); margin-top: 2px; }

.info-grid { display: grid; grid-template-columns: 1.2fr 1fr; gap: 16px; }
.info-card { background: var(--dm-card); border: 1px solid var(--dm-border); border-radius: var(--radius-lg); padding: 24px; box-shadow: var(--shadow-card); }
.info-title { font-family: var(--font-display); font-size: 15px; font-weight: 700; color: var(--dm-text); margin: 0 0 18px; }

.info-steps { display: flex; flex-direction: column; gap: 14px; }
.step { display: flex; gap: 14px; align-items: flex-start; }
.step-num { width: 24px; height: 24px; border-radius: 50%; background: var(--dm-primary-soft); color: var(--dm-primary); font-size: 12px; font-weight: 800; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.step strong { font-size: 13px; color: var(--dm-text); display: block; }
.step p { font-size: 12px; color: var(--dm-muted); margin: 2px 0 0; }

.demo-list { display: flex; flex-direction: column; gap: 14px; }
.demo-item { display: flex; gap: 12px; align-items: flex-start; }
.demo-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; margin-top: 4px; }
.demo-dot.hr { background: var(--dm-primary); }
.demo-dot.crm { background: var(--dm-amber); }
.demo-dot.fin { background: var(--dm-accent); }
.demo-dot.erp { background: var(--dm-rose); }
.demo-item strong { font-size: 13px; color: var(--dm-text); display: block; }
.demo-item p { font-size: 12px; color: var(--dm-muted); margin: 2px 0 0; }

@media (max-width: 768px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
  .info-grid { grid-template-columns: 1fr; }
}
</style>
