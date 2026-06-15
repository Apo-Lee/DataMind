<template>
  <div class="admin-page animate-in">
    <div class="page-top">
      <div>
        <h2 class="page-title">用户管理</h2>
        <p class="page-sub">系统用户由 HR 同步自动创建，管理员仅可修改权限和状态</p>
      </div>
    </div>

    <div class="table-card">
      <!-- 搜索/筛选栏 -->
      <div class="table-filter-bar">
        <input class="filter-input" v-model="userSearch" placeholder="搜索用户名或显示名…" />
        <select class="filter-select" v-model="roleFilter">
          <option value="">全部角色</option>
          <option v-for="r in allRoles" :key="r" :value="r">{{ roleLabel(r) }}</option>
        </select>
      </div>
      <el-table :data="filteredUsers" stripe v-loading="loading" :empty-text="'暂无匹配用户'">
        <el-table-column label="用户" min-width="160">
          <template #default="{ row }">
            <div class="user-cell">
              <div class="user-avatar-sm" :class="`avatar-${row.role}`">{{ row.display_name?.[0] }}</div>
              <div>
                <div class="user-name">{{ row.display_name }}</div>
                <div class="user-username">@{{ row.username }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="role" label="角色" width="130">
          <template #default="{ row }">
            <span class="role-badge" :class="`role-${row.role}`">{{ roleLabel(row.role) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="dept_id" label="部门ID" width="80">
          <template #default="{ row }">
            <code>{{ row.dept_id ?? '-' }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="data_scope" label="数据范围" width="120">
          <template #default="{ row }">
            <span class="cell-tag">{{ scopeLabel(row.data_scope) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="80">
          <template #default="{ row }">
            <span :class="row.source === 'hr_sync' ? 'cell-tag tag-hr' : 'cell-tag'">{{ row.source === 'hr_sync' ? 'HR同步' : '手动' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <span class="status-dot-text" :class="row.is_active ? 'on' : 'off'">
              {{ row.is_active ? '启用' : '停用' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <button class="action-btn danger" @click="handleToggleActive(row)">{{ row.is_active ? '停用' : '启用' }}</button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { usersApi } from '@/api/users'

const users = ref([])
const loading = ref(false)
const userSearch = ref('')
const roleFilter = ref('')

const roleLabels: Record<string, string> = {
  admin: '管理员', hr_director: 'HR总监', finance_bp: '财务BP',
  finance_director: '财务总监', dept_ceo: '部门CEO', dept_manager: '部门经理',
  sales_manager: '销售经理', employee: '员工', viewer: '只读',
}
const scopeLabels: Record<string, string> = {
  self_only: '仅自己', team: '直属下级', dept: '本部门',
  dept_and_sub: '本部门+子部门', cross_dept: '跨部门', all: '全部',
}
function roleLabel(r: string) { return roleLabels[r] || r }
function scopeLabel(s?: string) { return s ? scopeLabels[s] || s : '-' }

const filteredUsers = computed(() => {
  let list = users.value as any[]
  const q = userSearch.value.toLowerCase()
  const f = roleFilter.value
  if (q) list = list.filter((u: any) => u.username?.toLowerCase().includes(q) || u.display_name?.includes(userSearch.value))
  if (f) list = list.filter((u: any) => u.role === f)
  return list
})

const allRoles = computed(() => {
  const roles = new Set<string>()
  users.value.forEach((u: any) => { if (u.role) roles.add(u.role) })
  return Array.from(roles).sort()
})

async function fetchUsers() { loading.value = true; try { const r = await usersApi.list(); users.value = r.data } catch (e: any) { ElMessage.error('加载用户失败') } finally { loading.value = false } }

async function handleToggleActive(row: any) {
  const original = row.is_active
  try {
    await usersApi.update(row.id, { is_active: !original })
    row.is_active = !original
    ElMessage.success(row.is_active ? '已启用' : '已停用')
  } catch (e: any) {
    row.is_active = original
    ElMessage.error('操作失败: ' + (e?.response?.data?.detail || e?.message || '未知错误'))
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
.user-cell { display: flex; align-items: center; gap: 10px; }
.user-avatar-sm { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 13px; font-weight: 700; }
.user-avatar-sm.avatar-admin { background: linear-gradient(135deg, #5B5FE3, #818CF8); }
.user-avatar-sm.avatar-hr_director { background: linear-gradient(135deg, #00C9A7, #34D399); }
.user-avatar-sm.avatar-finance_bp { background: linear-gradient(135deg, #F59E0B, #FBBF24); }
.user-avatar-sm.avatar-finance_director { background: linear-gradient(135deg, #F59E0B, #FBBF24); }
.user-avatar-sm.avatar-dept_ceo { background: linear-gradient(135deg, #6366F1, #8B5CF6); }
.user-avatar-sm.avatar-dept_manager { background: linear-gradient(135deg, #6366F1, #8B5CF6); }
.user-avatar-sm.avatar-sales_manager { background: linear-gradient(135deg, #F43F5E, #FB7185); }
.user-avatar-sm.avatar-employee { background: linear-gradient(135deg, #94A3B8, #CBD5E1); }
.user-avatar-sm.avatar-viewer { background: linear-gradient(135deg, #94A3B8, #CBD5E1); }
.user-name { font-size: 13px; font-weight: 600; color: var(--dm-text); }
.user-username { font-size: 11px; color: var(--dm-muted); }
.role-badge { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 20px; letter-spacing: 0.02em; }
.role-badge.role-admin { background: var(--dm-primary-soft); color: var(--dm-primary); }
.role-badge.role-hr_director { background: var(--dm-accent-soft); color: var(--dm-accent); }
.role-badge.role-finance_bp { background: var(--dm-amber-soft); color: var(--dm-amber); }
.role-badge.role-finance_director { background: var(--dm-amber-soft); color: var(--dm-amber); }
.role-badge.role-dept_ceo { background: var(--dm-primary-soft); color: var(--dm-primary); }
.role-badge.role-dept_manager { background: var(--dm-primary-soft); color: var(--dm-primary); }
.role-badge.role-employee { background: var(--dm-surface); color: var(--dm-text2); }
.cell-tag { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 20px; background: var(--dm-surface); color: var(--dm-text2); }
.cell-tag.tag-hr { background: var(--dm-primary-soft); color: var(--dm-primary); }
.status-dot-text { font-size: 12px; font-weight: 600; }
.status-dot-text.on { color: var(--dm-accent); }
.status-dot-text.off { color: var(--dm-rose); }
.action-btn {
  padding: 4px 10px; border: 1px solid var(--dm-border); border-radius: 6px;
  background: var(--dm-card); color: var(--dm-text2); font-size: 12px;
  font-weight: 500; font-family: var(--font-body); cursor: pointer; transition: all 0.15s;
}
.action-btn.danger:hover { border-color: var(--dm-rose); color: var(--dm-rose); background: var(--dm-rose-soft); }
/* 筛选栏 */
.table-filter-bar { display: flex; gap: 8px; padding: 12px 16px; border-bottom: 1px solid var(--dm-border2); }
.filter-input { flex: 1; max-width: 260px; padding: 6px 12px; font-size: 12px; font-family: var(--font-body); border: 1px solid var(--dm-border); border-radius: 6px; background: var(--dm-surface); color: var(--dm-text); outline: none; }
.filter-input:focus { border-color: var(--dm-primary); }
.filter-select { padding: 6px 10px; font-size: 12px; font-family: var(--font-body); border: 1px solid var(--dm-border); border-radius: 6px; background: var(--dm-surface); color: var(--dm-text); cursor: pointer; outline: none; }
</style>
