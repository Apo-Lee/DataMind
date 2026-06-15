<template>
  <div class="admin-page animate-in">
    <div class="page-top">
      <div>
        <h2 class="page-title">数据源管理</h2>
        <p class="page-sub">系统预定义的业务数据源，与 HR 组织架构统一关联</p>
      </div>
    </div>

    <div class="table-card">
      <el-table :data="datasources" stripe v-loading="loading" :empty-text="'暂无数据源'">
        <el-table-column prop="name" label="名称" min-width="130">
          <template #default="{ row }">
            <span class="cell-name">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="db_type" label="类型" width="100">
          <template #default="{ row }">
            <span class="cell-tag">{{ row.db_type }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="business_tag" label="业务标签" width="100">
          <template #default="{ row }">
            <span class="cell-tag" :class="`tag-${row.business_tag}`">{{ row.business_tag }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="host" label="地址" min-width="200">
          <template #default="{ row }">
            <code class="cell-code">{{ row.host }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="is_system" label="系统预置" width="90" align="center">
          <template #default="{ row }">
            <span class="status-dot" :class="row.is_system ? 'ok' : 'none'" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <span :class="row.is_active ? 'cell-tag tag-ok' : 'cell-tag tag-off'">{{ row.is_active ? '启用' : '停用' }}</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { datasourcesApi } from '@/api/datasources'

const datasources = ref([])
const loading = ref(false)

async function fetchList() { loading.value = true; try { const r = await datasourcesApi.list(); datasources.value = r.data } catch (e: any) { ElMessage.error('加载数据源失败: ' + (e?.response?.data?.detail || e?.message || '未知错误')) } finally { loading.value = false } }
onMounted(fetchList)
</script>

<style scoped>
.admin-page { display: flex; flex-direction: column; gap: 20px; }
.page-top { display: flex; justify-content: space-between; align-items: flex-start; }
.page-title { font-family: var(--font-display); font-size: 22px; font-weight: 800; color: var(--dm-text); margin: 0 0 4px; letter-spacing: -0.01em; }
.page-sub { font-size: 13px; color: var(--dm-muted); margin: 0; }
.table-card { background: var(--dm-card); border-radius: var(--radius-lg); border: 1px solid var(--dm-border); box-shadow: var(--shadow-card); overflow: hidden; }
.cell-name { font-weight: 600; color: var(--dm-text); }
.cell-tag { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 20px; background: var(--dm-surface); color: var(--dm-text2); letter-spacing: 0.02em; }
.cell-tag.tag-hr { background: var(--dm-primary-soft); color: var(--dm-primary); }
.cell-tag.tag-crm { background: var(--dm-amber-soft); color: var(--dm-amber); }
.cell-tag.tag-finance { background: var(--dm-accent-soft); color: var(--dm-accent); }
.cell-tag.tag-ok { background: var(--dm-accent-soft); color: var(--dm-accent); }
.cell-tag.tag-off { background: var(--dm-rose-soft); color: var(--dm-rose); }
.cell-code { font-size: 12px; color: var(--dm-text2); font-family: 'SF Mono', monospace; background: var(--dm-surface); padding: 2px 6px; border-radius: 4px; }
.status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; }
.status-dot.ok { background: var(--dm-accent); box-shadow: 0 0 6px rgba(0,201,167,0.5); }
.status-dot.none { background: var(--dm-border); }
</style>
