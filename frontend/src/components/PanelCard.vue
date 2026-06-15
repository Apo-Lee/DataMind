<template>
  <div :class="['panel', { 'panel-primary': isMain }]" @click="handleClick">
    <div class="panel-top">
      <div class="panel-top-left">
        <span class="panel-name">{{ panel.datasource_name }}</span>
        <span class="panel-tag" :class="`tag-${panel.business_tag}`">{{ panel.business_tag }}</span>
      </div>
      <div class="panel-top-right">
        <span v-if="isMain" class="primary-badge">
          <svg viewBox="0 0 12 12" fill="none"><polygon points="6,1 7.5,4.5 11.5,5 8.5,7.5 9,11 6,9 3,11 3.5,7.5 0.5,5 4.5,4.5" fill="currentColor"/></svg>主看板
        </span>
        <span class="update-time" v-if="panelUpdatedAt">更新于 {{ panelUpdatedAt }}</span>
        <!-- 自定义按钮 -->
        <button class="icon-btn" @click.stop="showConfig = true" title="自定义 KPI">
          <svg viewBox="0 0 16 16" fill="none"><path d="M8 2c-.5 0-1 .5-1 1v1c-1 .3-2 .8-2.8 1.5l-.7-.7c-.4-.4-1-.4-1.4 0l-1.4 1.4c-.4.4-.4 1 0 1.4l.7.7C1 9 1 10 1 11H2c0 .5.5 1 1 1h1c.3 1 .8 2 1.5 2.8l-.7.7c-.4.4-.4 1 0 1.4l1.4 1.4c.4.4 1 .4 1.4 0l.7-.7C9 19 10 19 11 19v-1c.5 0 1-.5 1-1v-1c1-.3 2-.8 2.8-1.5l.7.7c.4.4 1 .4 1.4 0l1.4-1.4c.4-.4.4-1 0-1.4l-.7-.7c.5-.8.8-1.8 1-2.8H21c0-.5-.5-1-1-1h-1c-.3-1-.8-2-1.5-2.8l.7-.7c.4-.4.4-1 0-1.4l-1.4-1.4c-.4-.4-1-.4-1.4 0l-.7.7C13 3 12 3 11 3V2c0-.5-.5-1-1-1H8z" stroke="currentColor" stroke-width="1.2" transform="scale(0.6) translate(5 5)"/><circle cx="8" cy="8" r="2.5" stroke="currentColor" stroke-width="1.2"/></svg>
        </button>
        <button class="refresh-btn" @click.stop="handleRefresh" title="刷新数据">
          <svg viewBox="0 0 16 16" fill="none"><path d="M2 8a6 6 0 0111.3-3M14 8a6 6 0 01-11.3 3M14 2v4h-4M2 14v-4h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
      </div>
    </div>

    <div class="panel-kpis">
      <KpiCard v-for="(kpi, ki) in panel.kpi_cards" :key="ki" v-bind="kpi" />
    </div>

    <div v-if="panel.kpi_cards.length === 0" class="panel-empty">
      <svg viewBox="0 0 24 24" fill="none" style="width:32px;height:32px;color:var(--dm-muted);margin-bottom:8px"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.5"/><path d="M12 8v4M12 16h0" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
      <p>暂无可用的 KPI 数据</p><span>请先在数据源管理中执行「探测」</span>
    </div>

    <div v-if="!isMain" class="panel-hint">点击查看详情</div>

    <!-- KPI 自定义弹窗 -->
    <Teleport to="body">
      <div v-if="showConfig" class="overlay" @click.self="showConfig = false">
        <div class="config-dialog animate-in" @click.stop>
          <div class="config-header">
            <h3>自定义 {{ panel.datasource_name }} 看板</h3>
            <button class="close-btn" @click="showConfig = false">
              <svg viewBox="0 0 14 14" fill="none"><path d="M10 4l-6 6M4 4l6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
            </button>
          </div>
          <p class="config-desc">勾选要在看板上显示的 KPI 指标（最多4个）</p>
          <div class="config-list">
            <label v-for="m in metrics" :key="m.id" class="config-item"
                   :class="{ checked: isChecked(m.id) }">
              <input type="checkbox" :value="m.id" v-model="selected" :disabled="selected.length >= 4 && !isChecked(m.id)" />
              <span class="check-box"></span>
              <span class="metric-label">{{ m.label }}</span>
              <span class="metric-unit" v-if="m.unit">{{ m.unit }}</span>
            </label>
          </div>
          <div class="config-footer">
            <button class="secondary-btn" @click="showConfig = false">取消</button>
            <button class="primary-btn" @click="saveConfig">保存</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { dashboardApi } from '@/api/dashboard'
import KpiCard from './KpiCard.vue'

const props = defineProps<{ panel: any; isMain?: boolean }>()
const emit = defineEmits<{ click: []; refresh: [datasourceId: string] }>()
const router = useRouter()
const panelUpdatedAt = ref('')

const showConfig = ref(false)
const selected = ref<string[]>([])
const metrics = ref<any[]>([])

const availableMetrics = computed(() => props.panel?.available_metrics || [])

function isChecked(id: string) { return selected.value.includes(id) }

watch(showConfig, (val) => { if (val) loadConfig() })

async function loadConfig() {
  if (!props.panel?.datasource_id) return
  try {
    const r = await dashboardApi.getConfig(props.panel.datasource_id)
    const currentIds = props.panel.kpi_cards?.map((c: any) => c.id) || []
    selected.value = r.data.enabled_kpi_ids || currentIds
    metrics.value = r.data.available_metrics || availableMetrics.value
  } catch {
    // fallback to panel.available_metrics
    metrics.value = availableMetrics.value
    selected.value = props.panel.kpi_cards?.map((c: any) => c.id) || []
  }
}

async function saveConfig() {
  try {
    await dashboardApi.saveConfig(props.panel.datasource_id, selected.value)
    showConfig.value = false
    emit('refresh', props.panel.datasource_id)
  } catch { ElMessage.error('保存配置失败') }
}

function nowTime() {
  return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function handleClick() {
  router.push(`/analyst/panel/${props.panel.datasource_id}`)
}

function handleRefresh() {
  emit('refresh', props.panel.datasource_id)
  panelUpdatedAt.value = nowTime()
}
</script>

<style scoped>
.panel { background: var(--dm-card); border-radius: var(--radius-lg); border: 1px solid var(--dm-border); padding: 20px 22px; cursor: pointer; transition: all 0.25s var(--ease-out); height: 100%; display: flex; flex-direction: column; }
.panel:hover { box-shadow: var(--shadow-card-hover); }
.panel-primary { border: 2px solid var(--dm-primary); box-shadow: 0 0 0 1px rgba(91,95,227,0.1), 0 4px 20px rgba(91,95,227,0.06); }
.panel-primary:hover { box-shadow: 0 0 0 1px rgba(91,95,227,0.15), 0 8px 30px rgba(91,95,227,0.1); }
.panel-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 18px; }
.panel-top-left { display: flex; align-items: center; gap: 10px; }
.panel-name { font-family: var(--font-display); font-size: 16px; font-weight: 700; color: var(--dm-text); letter-spacing: -0.01em; }
.panel-tag { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 20px; letter-spacing: 0.02em; }
.tag-hr { background: var(--dm-primary-soft); color: var(--dm-primary); }
.tag-crm { background: var(--dm-amber-soft); color: var(--dm-amber); }
.tag-finance { background: var(--dm-accent-soft); color: var(--dm-accent); }
.panel-top-right { display: flex; align-items: center; gap: 6px; }
.primary-badge { display: flex; align-items: center; gap: 4px; font-size: 11px; font-weight: 700; color: var(--dm-primary); }
.primary-badge svg { width: 12px; height: 12px; }
.update-time { font-size: 10px; color: var(--dm-muted); font-weight: 500; }
.refresh-btn, .icon-btn { width: 30px; height: 30px; border: 1px solid var(--dm-border); border-radius: var(--radius-sm); background: var(--dm-card); color: var(--dm-muted); cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.15s var(--ease-out); }
.refresh-btn svg, .icon-btn svg { width: 14px; height: 14px; }
.refresh-btn:hover, .icon-btn:hover { border-color: var(--dm-primary); color: var(--dm-primary); background: var(--dm-primary-soft); }
.panel-kpis { display: flex; gap: 12px; flex-wrap: wrap; flex: 1; }
.panel-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: var(--dm-muted); font-size: 13px; padding: 24px 0; }
.panel-empty p { margin: 0; font-weight: 600; }
.panel-empty span { font-size: 12px; margin-top: 4px; }
.panel-hint { font-size: 11px; color: var(--dm-muted); text-align: center; margin-top: 14px; font-weight: 500; }

/* 配置弹窗 */
.overlay { position: fixed; inset: 0; z-index: 1000; background: rgba(11,17,32,0.3); backdrop-filter: blur(3px); display: flex; align-items: center; justify-content: center; }
.config-dialog { width: 420px; max-width: 94vw; background: var(--dm-card); border-radius: var(--radius-xl); box-shadow: var(--shadow-elevated); padding: 24px 28px 20px; }
.config-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.config-header h3 { font-family: var(--font-display); font-size: 17px; font-weight: 700; color: var(--dm-text); margin: 0; }
.close-btn { width: 32px; height: 32px; border: none; background: var(--dm-surface); border-radius: var(--radius-sm); color: var(--dm-muted); cursor: pointer; display: flex; align-items: center; justify-content: center; }
.close-btn svg { width: 12px; height: 12px; }
.close-btn:hover { color: var(--dm-text); }
.config-desc { font-size: 12px; color: var(--dm-muted); margin: 4px 0 16px; }
.config-list { display: flex; flex-direction: column; gap: 6px; margin-bottom: 20px; }
.config-item { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: var(--radius-sm); border: 1px solid var(--dm-border2); cursor: pointer; transition: all 0.15s var(--ease-out); }
.config-item:hover { border-color: var(--dm-primary); background: var(--dm-primary-soft); }
.config-item.checked { border-color: var(--dm-primary); background: var(--dm-primary-soft); }
.config-item input[type="checkbox"] { display: none; }
.check-box { width: 18px; height: 18px; border-radius: 4px; border: 1.5px solid var(--dm-border); flex-shrink: 0; transition: all 0.15s var(--ease-out); position: relative; }
.config-item.checked .check-box { background: var(--dm-primary); border-color: var(--dm-primary); }
.config-item.checked .check-box::after { content: ''; position: absolute; left: 5px; top: 2px; width: 5px; height: 9px; border: solid #fff; border-width: 0 2px 2px 0; transform: rotate(45deg); }
.metric-label { font-size: 13px; font-weight: 600; color: var(--dm-text); flex: 1; }
.metric-unit { font-size: 11px; color: var(--dm-muted); }
.config-footer { display: flex; gap: 8px; justify-content: flex-end; }
.primary-btn { padding: 8px 20px; background: var(--dm-primary); color: #fff; border: none; border-radius: var(--radius-sm); font-size: 13px; font-weight: 600; font-family: var(--font-body); cursor: pointer; transition: all 0.15s var(--ease-out); }
.primary-btn:hover { background: #4A4ED1; }
.secondary-btn { padding: 8px 20px; background: var(--dm-surface); color: var(--dm-text2); border: 1px solid var(--dm-border); border-radius: var(--radius-sm); font-size: 13px; font-weight: 600; font-family: var(--font-body); cursor: pointer; transition: all 0.15s var(--ease-out); }
.secondary-btn:hover { background: var(--dm-border2); }
</style>
