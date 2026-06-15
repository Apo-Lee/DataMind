<template>
  <div class="admin-page animate-in">
    <div class="page-top">
      <div>
        <h2 class="page-title">HR 数据同步</h2>
        <p class="page-sub">从 HR 系统同步组织架构和员工数据，自动创建/更新系统用户</p>
      </div>
      <button class="primary-btn" :disabled="syncing" @click="triggerSync">
        {{ syncing ? '同步中…' : '手动触发同步' }}
      </button>
    </div>

    <!-- 同步状态 -->
    <section>
      <h3 class="section-title">同步状态</h3>
      <div class="status-grid">
        <div class="stat-card">
          <div class="stat-value">{{ status?.hr_employee_count ?? '-' }}</div>
          <div class="stat-label">HR 系统员工数</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ status?.matched_users ?? '-' }}</div>
          <div class="stat-label">已同步用户</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ status?.unmatched_users ?? '-' }}</div>
          <div class="stat-label">手动创建用户</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" :class="status?.last_sync_status === 'success' ? 'good' : 'warn'">{{ status?.last_sync_status ?? '未同步' }}</div>
          <div class="stat-label">最近同步</div>
        </div>
      </div>
      <div class="sync-time" v-if="status?.last_sync_at">最近一次同步时间: {{ formatTime(status.last_sync_at) }}</div>
    </section>

    <!-- 同步日志 -->
    <section>
      <h3 class="section-title">同步历史</h3>
      <div class="table-card">
        <el-table :data="syncLogs" stripe v-loading="loading" :empty-text="'暂无记录'">
          <el-table-column prop="created_at" label="时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <span class="cell-tag" :class="row.status === 'success' ? 'ok' : 'fail'">{{ row.status === 'success' ? '成功' : row.status }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="total_hr_employees" label="HR员工" width="80" />
          <el-table-column prop="created_users" label="新建" width="60" />
          <el-table-column prop="updated_users" label="更新" width="60" />
          <el-table-column prop="deactivated_users" label="停用" width="60" />
          <el-table-column label="错误" min-width="200">
            <template #default="{ row }">
              <code class="cell-code">{{ row.errors && Object.keys(row.errors).length > 0 ? JSON.stringify(row.errors) : '无' }}</code>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { adminApi } from '@/api/admin'

const syncing = ref(false)
const loading = ref(false)
const status = ref<any>({})
const syncLogs = ref<any[]>([])

async function fetchData() {
  loading.value = true
  try { status.value = (await adminApi.getHrSyncStatus()).data } catch (e: any) { ElMessage.error('获取同步状态失败') }
  try { syncLogs.value = (await adminApi.listHrSyncLogs()).data } catch (e: any) { ElMessage.error('获取同步日志失败') }
  loading.value = false
}

async function triggerSync() {
  syncing.value = true
  try {
    const r = await adminApi.triggerHrSync()
    ElMessage.success(`同步完成: 新建 ${r.data.created_users} 人, 更新 ${r.data.updated_users} 人`)
    await fetchData()
  } catch { ElMessage.error('同步失败') }
  finally { syncing.value = false }
}

function formatTime(t?: string) { return t ? new Date(t).toLocaleString('zh-CN') : '-' }

onMounted(fetchData)
</script>

<style scoped>
.admin-page { display: flex; flex-direction: column; gap: 24px; }
.page-top { display: flex; justify-content: space-between; align-items: flex-start; }
.page-title { font-family: var(--font-display); font-size: 22px; font-weight: 800; color: var(--dm-text); margin: 0 0 4px; letter-spacing: -0.01em; }
.page-sub { font-size: 13px; color: var(--dm-muted); margin: 0; }
.primary-btn {
  display: inline-flex; align-items: center; gap: 6px; padding: 10px 22px;
  background: var(--dm-primary); color: #fff; border: none; border-radius: var(--radius-sm);
  font-size: 14px; font-weight: 600; font-family: var(--font-body); cursor: pointer;
}
.primary-btn:hover { background: #4A4ED1; }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.section-title { font-size: 15px; font-weight: 700; margin: 0 0 12px; color: var(--dm-text); }
.status-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.stat-card {
  background: var(--dm-card); border: 1px solid var(--dm-border);
  border-radius: var(--radius-lg); padding: 20px; text-align: center;
}
.stat-value { font-size: 32px; font-weight: 800; font-family: var(--font-display); color: var(--dm-primary); }
.stat-value.good { color: var(--dm-accent); }
.stat-value.warn { color: var(--dm-amber); }
.stat-label { font-size: 13px; color: var(--dm-muted); margin-top: 4px; }
.sync-time { font-size: 12px; color: var(--dm-muted); margin-top: 8px; }
.table-card { background: var(--dm-card); border-radius: var(--radius-lg); border: 1px solid var(--dm-border); box-shadow: var(--shadow-card); overflow: hidden; }
.cell-tag { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 20px; }
.cell-tag.ok { background: var(--dm-accent-soft); color: var(--dm-accent); }
.cell-tag.fail { background: var(--dm-rose-soft); color: var(--dm-rose); }
.cell-code { font-size: 11px; color: var(--dm-muted); font-family: 'SF Mono', monospace; word-break: break-all; }
</style>
