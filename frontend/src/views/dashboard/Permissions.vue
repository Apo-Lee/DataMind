<template>
  <div class="admin-page animate-in">
    <div class="page-top">
      <div>
        <h2 class="page-title">数据权限分配</h2>
        <p class="page-sub">管理用户的数据访问范围和跨部门授权</p>
      </div>
    </div>

    <div class="table-card">
      <el-table :data="users" stripe v-loading="loading" :empty-text="'暂无用户'">
        <el-table-column prop="display_name" label="用户" min-width="120">
          <template #default="{ row }">
            <span class="cell-name">{{ row.display_name }}</span>
            <span class="cell-sub">{{ row.username }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="role" label="角色" width="110">
          <template #default="{ row }">
            <span class="cell-tag">{{ roleLabel(row.role) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="所属部门" width="100">
          <template #default="{ row }">
            <code>{{ row.dept_id ?? '-' }}</code>
          </template>
        </el-table-column>
        <el-table-column label="数据范围" width="160">
          <template #default="{ row }">
            <select class="form-input-sm" :value="row.data_scope" @change="handleScopeChange(row, ($event.target as HTMLSelectElement).value)">
              <option value="self_only">仅自己</option>
              <option value="team">直属下级</option>
              <option value="dept">本部门</option>
              <option value="dept_and_sub">本部门及子部门</option>
              <option value="cross_dept">跨部门</option>
              <option value="all">全部</option>
            </select>
          </template>
        </el-table-column>
        <el-table-column label="额外授权部门" min-width="140">
          <template #default="{ row }">
            <span v-if="row.extra_dept_ids?.length">{{ row.extra_dept_ids.join(', ') }}</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="80">
          <template #default="{ row }">
            <span :class="row.source === 'hr_sync' ? 'cell-tag tag-hr' : 'cell-tag'">{{ row.source === 'hr_sync' ? '同步' : '手动' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="70">
          <template #default="{ row }">
            <span class="status-dot" :class="row.is_active ? 'ok' : 'off'" />
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { adminApi } from '@/api/admin'

const users = ref<any[]>([])
const loading = ref(false)

const roleLabels: Record<string, string> = {
  admin: '管理员', hr_director: 'HR总监', finance_bp: '财务BP',
  finance_director: '财务总监', dept_ceo: '部门CEO', dept_manager: '部门经理',
  sales_manager: '销售经理', employee: '员工', viewer: '只读',
}
function roleLabel(role: string) { return roleLabels[role] || role }

async function fetchUsers() {
  loading.value = true
  try { const r = await adminApi.listUserPermissions(); users.value = r.data } catch (e: any) { ElMessage.error('加载用户失败') }
  finally { loading.value = false }
}

async function handleScopeChange(row: any, scope: string) {
  try {
    await adminApi.updateUserPermission(row.id, { data_scope: scope })
    row.data_scope = scope
    ElMessage.success(`已更新 ${row.display_name} 的数据范围为 "${scope}"`)
  } catch {
    ElMessage.error('更新失败')
    await fetchUsers()
  }
}

onMounted(fetchUsers)
</script>

<style scoped>
.admin-page { display: flex; flex-direction: column; gap: 20px; }
.page-top { display: flex; justify-content: space-between; align-items: flex-start; }
.page-title { font-family: var(--font-display); font-size: 22px; font-weight: 800; color: var(--dm-text); margin: 0 0 4px; letter-spacing: -0.01em; }
.page-sub { font-size: 13px; color: var(--dm-muted); margin: 0; }
.table-card { background: var(--dm-card); border-radius: var(--radius-lg); border: 1px solid var(--dm-border); box-shadow: var(--shadow-card); overflow: hidden; }
.cell-name { font-weight: 600; color: var(--dm-text); display: block; }
.cell-sub { font-size: 11px; color: var(--dm-muted); }
.cell-tag { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 20px; background: var(--dm-surface); color: var(--dm-text2); letter-spacing: 0.02em; }
.cell-tag.tag-hr { background: var(--dm-primary-soft); color: var(--dm-primary); }
.muted { color: var(--dm-muted); font-size: 12px; }
.status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; }
.status-dot.ok { background: var(--dm-accent); box-shadow: 0 0 6px rgba(0,201,167,0.5); }
.status-dot.off { background: var(--dm-border); }
.form-input-sm { padding: 4px 8px; font-size: 12px; font-family: var(--font-body); border: 1px solid var(--dm-border); border-radius: 6px; background: var(--dm-surface); color: var(--dm-text); cursor: pointer; }
</style>
