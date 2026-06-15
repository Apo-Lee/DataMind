<template>
  <div class="admin-page animate-in">
    <div class="page-top">
      <div>
        <h2 class="page-title">系统配置</h2>
        <p class="page-sub">管理 DataMind 平台的运行参数</p>
      </div>
    </div>

    <div class="config-grid">
      <div v-for="cfg in configs" :key="cfg.key" class="config-row">
        <div class="config-info">
          <div class="config-key">{{ cfg.key }}</div>
          <div class="config-desc" v-if="cfg.description">{{ cfg.description }}</div>
          <div class="config-type">{{ cfg.value_type }}</div>
        </div>
        <div class="config-value">
          <input class="form-input" :value="cfg.value" @change="handleUpdate(cfg.key, ($event.target as HTMLInputElement).value, cfg.value_type)" />
        </div>
        <div class="config-actions">
          <span class="config-updated" v-if="cfg.updated_at">更新于 {{ formatTime(cfg.updated_at) }}</span>
        </div>
      </div>
    </div>

    <div v-if="!configs.length" class="empty-state">
      <p>暂无配置项。系统启动或首次同步后会自动生成默认配置。</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { adminApi } from '@/api/admin'

const configs = ref<any[]>([])

async function fetchConfigs() {
  try { configs.value = (await adminApi.listConfigs()).data } catch {}
}

async function handleUpdate(key: string, value: string, valueType?: string) {
  try {
    await adminApi.updateConfig(key, value, valueType)
    ElMessage.success(`配置 "${key}" 已更新`)
    await fetchConfigs()
  } catch { ElMessage.error('更新失败') }
}

function formatTime(t?: string) { return t ? new Date(t).toLocaleString('zh-CN') : '-' }

onMounted(fetchConfigs)
</script>

<style scoped>
.admin-page { display: flex; flex-direction: column; gap: 20px; }
.page-top { display: flex; justify-content: space-between; align-items: flex-start; }
.page-title { font-family: var(--font-display); font-size: 22px; font-weight: 800; color: var(--dm-text); margin: 0 0 4px; letter-spacing: -0.01em; }
.page-sub { font-size: 13px; color: var(--dm-muted); margin: 0; }
.config-grid { display: flex; flex-direction: column; gap: 0; border: 1px solid var(--dm-border); border-radius: var(--radius-lg); overflow: hidden; background: var(--dm-card); }
.config-row { display: flex; align-items: center; gap: 16px; padding: 14px 20px; border-bottom: 1px solid var(--dm-border); transition: background 0.1s; }
.config-row:last-child { border-bottom: none; }
.config-row:hover { background: var(--dm-surface); }
.config-info { flex: 1; min-width: 0; }
.config-key { font-size: 13px; font-weight: 600; font-family: 'SF Mono', monospace; color: var(--dm-text); }
.config-desc { font-size: 12px; color: var(--dm-muted); margin-top: 2px; }
.config-type { font-size: 10px; font-weight: 700; color: var(--dm-muted); text-transform: uppercase; letter-spacing: 0.05em; }
.config-value { width: 300px; }
.form-input { width: 100%; padding: 8px 12px; font-size: 13px; font-family: var(--font-body); border: 1px solid var(--dm-border); border-radius: var(--radius-sm); background: var(--dm-surface); color: var(--dm-text); outline: none; }
.form-input:focus { border-color: var(--dm-primary); }
.config-actions { width: 160px; text-align: right; }
.config-updated { font-size: 11px; color: var(--dm-muted); }
.empty-state { padding: 48px; text-align: center; color: var(--dm-muted); font-size: 14px; }
</style>
