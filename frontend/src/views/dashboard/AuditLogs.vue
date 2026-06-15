<template>
  <div class="admin-page animate-in">
    <div class="page-top">
      <div>
        <h2 class="page-title">操作审计日志</h2>
        <p class="page-sub">记录所有关键操作，支持按用户和操作类型检索</p>
      </div>
    </div>

    <!-- 筛选 -->
    <div class="filter-bar">
      <input class="form-input" v-model="filterUsername" placeholder="搜索用户名..." @keyup.enter="fetchLogs" />
      <select class="form-input" v-model="filterAction" @change="fetchLogs" style="width:180px">
        <option value="">全部操作</option>
        <option value="login">登录</option>
        <option value="logout">登出</option>
        <option value="query_executed">查询执行</option>
        <option value="sql_executed">SQL执行</option>
        <option value="permission_changed">权限变更</option>
        <option value="hr_sync">HR同步</option>
        <option value="config_changed">配置变更</option>
      </select>
      <button class="primary-btn-sm" @click="fetchLogs">搜索</button>
    </div>

    <div class="table-card">
      <el-table :data="logs" stripe v-loading="loading" :empty-text="'暂无日志'">
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">
            <code class="cell-time">{{ formatTime(row.created_at) }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户" width="120">
          <template #default="{ row }">
            <span class="cell-name">{{ row.username }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="action" label="操作" width="120">
          <template #default="{ row }">
            <span class="cell-tag">{{ actionLabel(row.action) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="resource_type" label="资源类型" width="100">
          <template #default="{ row }">
            <code class="cell-code">{{ row.resource_type || '-' }}</code>
          </template>
        </el-table-column>
        <el-table-column label="详情" min-width="200">
          <template #default="{ row }">
            <span v-if="!row.detail" class="cell-detail">-</span>
            <span v-else class="cell-detail" :title="formatDetail(row.detail)">{{ formatDetailShort(row.detail) }}</span>
            <button v-if="row.detail && hasLongDetail(row.detail)" class="expand-detail-btn" @click="toggleDetail(row)">
              {{ expandedRows.has(row.id) ? '收起' : '展开' }}
            </button>
            <pre v-if="expandedRows.has(row.id)" class="detail-expanded">{{ formatDetail(row.detail) }}</pre>
          </template>
        </el-table-column>
        <el-table-column prop="ip_address" label="IP" width="130">
          <template #default="{ row }">
            <code>{{ row.ip_address || '-' }}</code>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="pager">
      <button class="pager-btn" :disabled="page <= 1" @click="page--; fetchLogs()">上一页</button>
      <span class="pager-info">第 {{ page }} 页</span>
      <button class="pager-btn" :disabled="logs.length < pageSize" @click="page++; fetchLogs()">下一页</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { adminApi } from '@/api/admin'

const logs = ref<any[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(50)
const filterUsername = ref('')
const filterAction = ref('')

const actionLabels: Record<string, string> = {
  login: '登录', logout: '登出', query_executed: '查询', sql_executed: 'SQL执行',
  permission_changed: '权限变更', hr_sync: 'HR同步', config_changed: '配置变更',
  user_created: '创建用户', user_modified: '编辑用户', user_deactivated: '停用用户',
}
function actionLabel(a: string) { return actionLabels[a] || a }
function formatTime(t?: string) { return t ? new Date(t).toLocaleString('zh-CN') : '-' }
function formatDetail(d: any) {
  if (!d) return '-'
  try { return JSON.stringify(d, null, 2) } catch { return String(d) }
}
function formatDetailShort(d: any) {
  if (!d) return '-'
  try {
    const s = JSON.stringify(d)
    return s.length > 60 ? s.substring(0, 60) + '…' : s
  } catch { return String(d).substring(0, 60) }
}
function hasLongDetail(d: any) {
  try { return JSON.stringify(d).length > 60 } catch { return false }
}
const expandedRows = ref<Set<string>>(new Set())
function toggleDetail(row: any) {
  const s = expandedRows.value
  if (s.has(row.id)) s.delete(row.id)
  else s.add(row.id)
  expandedRows.value = new Set(s) // 触发响应式
}

async function fetchLogs() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize.value }
    if (filterUsername.value) params.username = filterUsername.value
    if (filterAction.value) params.action = filterAction.value
    const r = await adminApi.listAuditLogs(params)
    logs.value = r.data
  } catch (e: any) { ElMessage.error('加载日志失败') } finally { loading.value = false }
}

onMounted(fetchLogs)
</script>

<style scoped>
.admin-page { display: flex; flex-direction: column; gap: 20px; }
.page-top { display: flex; justify-content: space-between; align-items: flex-start; }
.page-title { font-family: var(--font-display); font-size: 22px; font-weight: 800; color: var(--dm-text); margin: 0 0 4px; letter-spacing: -0.01em; }
.page-sub { font-size: 13px; color: var(--dm-muted); margin: 0; }
.filter-bar { display: flex; gap: 10px; align-items: center; }
.form-input { padding: 8px 12px; font-size: 13px; font-family: var(--font-body); border: 1px solid var(--dm-border); border-radius: var(--radius-sm); background: var(--dm-surface); color: var(--dm-text); outline: none; }
.form-input:focus { border-color: var(--dm-primary); }
.primary-btn-sm { padding: 8px 16px; background: var(--dm-primary); color: #fff; border: none; border-radius: var(--radius-sm); font-size: 13px; font-weight: 600; font-family: var(--font-body); cursor: pointer; }
.primary-btn-sm:hover { background: #4A4ED1; }
.table-card { background: var(--dm-card); border-radius: var(--radius-lg); border: 1px solid var(--dm-border); box-shadow: var(--shadow-card); overflow: hidden; }
.cell-name { font-weight: 600; color: var(--dm-text); }
.cell-tag { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 20px; background: var(--dm-surface); color: var(--dm-text2); }
.cell-time { font-size: 11px; color: var(--dm-muted); }
.cell-code { font-size: 12px; color: var(--dm-text2); font-family: 'SF Mono', monospace; }
.cell-detail { font-size: 11px; color: var(--dm-muted); max-width: 250px; display: inline-block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.expand-detail-btn { margin-left: 4px; padding: 1px 8px; border: 1px solid var(--dm-border); border-radius: 4px; background: var(--dm-surface); color: var(--dm-primary); font-size: 10px; font-family: var(--font-body); cursor: pointer; vertical-align: middle; }
.expand-detail-btn:hover { background: var(--dm-primary-soft); }
.detail-expanded { margin-top: 6px; padding: 8px 10px; background: var(--dm-surface); border-radius: 4px; font-size: 10px; font-family: 'SF Mono', monospace; color: var(--dm-text2); white-space: pre-wrap; word-break: break-all; max-height: 200px; overflow: auto; }
.pager { display: flex; align-items: center; justify-content: center; gap: 12px; }
.pager-btn { padding: 6px 16px; border: 1px solid var(--dm-border); border-radius: var(--radius-sm); background: var(--dm-card); color: var(--dm-text2); font-size: 13px; font-family: var(--font-body); cursor: pointer; }
.pager-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.pager-btn:hover:not(:disabled) { border-color: var(--dm-primary); color: var(--dm-primary); }
.pager-info { font-size: 13px; color: var(--dm-muted); }
</style>
