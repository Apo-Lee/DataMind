<template>
  <div class="report-page">
    <nav class="report-nav">
      <button class="back-link" @click="$router.push('/analyst')">
        <svg viewBox="0 0 16 16" fill="none"><path d="M10 4l-4 4 4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
        返回驾驶舱
      </button>
      <h2 class="report-question">{{ conv?.question || '分析报告' }}</h2>
      <!-- P1#13: 导出按钮 -->
      <button class="export-btn" @click="handlePrint" title="打印/导出报告">
        <svg viewBox="0 0 16 16" fill="none"><path d="M4 11H2a1 1 0 01-1-1V5a1 1 0 011-1h12a1 1 0 011 1v5a1 1 0 01-1 1h-2M4 7v5a1 1 0 001 1h6a1 1 0 001-1V7M5 2h6v3H5V2z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        打印 / 导出
      </button>
    </nav>

    <div class="report-layout">
      <!-- 左侧：Markdown 报告 + 图表 -->
      <div class="report-main">
        <!-- 图表区域 -->
        <div v-if="insights.length > 0" class="chart-grid">
          <div v-for="(chart, ci) in chartInsights" :key="'chart-'+ci" class="chart-card" :ref="el => setChartRef(el, ci)">
            <div class="chart-header">
              <h4 class="chart-title">{{ chart.content?.title || '图表 '+(ci+1) }}</h4>
              <span class="chart-type-tag">{{ chart.content?.type || '—' }}</span>
            </div>
            <div class="chart-canvas" :style="{ height: (chart.content?.height || 320)+'px' }"></div>
            <div v-if="chartErrors[ci]" class="chart-error">图表渲染失败 — {{ chartErrors[ci] }}</div>
          </div>
        </div>

        <!-- Markdown 报告 -->
        <div class="report-card" v-loading="loading">
          <MarkdownReport v-if="conv?.report_markdown" :content="conv.report_markdown" />
          <div v-else class="empty-report">
            <svg viewBox="0 0 48 48" fill="none" style="width:56px;height:56px;opacity:0.25;margin-bottom:12px">
              <rect x="8" y="6" width="32" height="36" rx="4" stroke="var(--dm-muted)" stroke-width="2" />
              <path d="M16 18h16M16 24h12M16 30h8" stroke="var(--dm-muted)" stroke-width="2" stroke-linecap="round" />
            </svg>
            <p>报告内容为空</p>
          </div>
        </div>
      </div>

      <aside class="report-sidebar" v-if="conv">
        <div class="meta-card">
          <h4 class="meta-title">查询详情</h4>
          <dl class="meta-list">
            <div><dt>意图</dt><dd>{{ conv.intent || '—' }}</dd></div>
            <div><dt>分析深度</dt><dd>{{ conv.analysis_depth || '—' }}</dd></div>
            <div><dt>创建时间</dt><dd>{{ formatTime(conv.created_at) }}</dd></div>
          </dl>
        </div>

        <!-- P2#17-#18: SQL 展开/折叠 + 复制 -->
        <div class="meta-card" v-if="conv.sql_generated">
          <div class="sql-header">
            <h4 class="meta-title">执行的 SQL</h4>
            <button class="copy-btn" @click="copySQL">
              <svg viewBox="0 0 16 16" fill="none"><rect x="5" y="5" width="9" height="9" rx="1.5" stroke="currentColor" stroke-width="1.5"/><path d="M11 5V3a1 1 0 00-1-1H3a1 1 0 00-1 1v6a1 1 0 001 1h2" stroke="currentColor" stroke-width="1.5"/></svg>
              {{ copied ? '已复制' : '复制' }}
            </button>
          </div>
          <pre class="sql-code" :class="{ collapsed: sqlCollapsed && sqlLines > 12 }">{{ conv.sql_generated }}</pre>
          <button v-if="sqlLines > 12" class="expand-btn" @click="sqlCollapsed = !sqlCollapsed">
            {{ sqlCollapsed ? `展开完整 SQL（${sqlLines} 行）` : '收起' }}
          </button>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch, computed, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { queryApi } from '@/api/query'
import MarkdownReport from '@/components/MarkdownReport.vue'
import * as echarts from 'echarts'

const route = useRoute()
const conv = ref<any>(null)
const loading = ref(false)
const insights = ref<any[]>([])
const chartRefs = ref<Map<number, HTMLElement>>(new Map())
const chartInstances: Record<number, echarts.ECharts> = {}
const resizeObservers: Record<number, ResizeObserver> = {}
const chartErrors = ref<Record<number, string>>({})
const sqlCollapsed = ref(true)
const copied = ref(false)

const chartInsights = computed(() => insights.value.filter((ins: any) => ins.type === 'chart'))
const sqlLines = computed(() => (conv.value?.sql_generated || '').split('\n').length)

function setChartRef(el: any, index: number) {
  if (el) chartRefs.value.set(index, el)
  else chartRefs.value.delete(index)
}

function formatTime(t?: string) {
  if (!t) return '—'
  return new Date(t).toLocaleString('zh-CN', { dateStyle: 'medium', timeStyle: 'short' })
}

async function copySQL() {
  try {
    await navigator.clipboard.writeText(conv.value?.sql_generated || '')
    copied.value = true
    ElMessage.success('SQL 已复制到剪贴板')
    setTimeout(() => copied.value = false, 2000)
  } catch {
    ElMessage.error('复制失败，请手动选择复制')
  }
}

function handlePrint() {
  window.print()
}

function mountCharts() {
  nextTick(() => {
    // 清理旧的 ResizeObserver、chartInstances 和错误状态
    Object.values(resizeObservers).forEach((ro) => ro.disconnect())
    Object.keys(resizeObservers).forEach((k) => delete resizeObservers[+k])
    Object.values(chartInstances).forEach((inst) => inst.dispose())
    Object.keys(chartInstances).forEach((k) => delete chartInstances[+k])
    chartErrors.value = {}

    chartInsights.value.forEach((ins, i) => {
      try {
        const el = chartRefs.value.get(i)
        if (!el) return
        const c = ins.content || {}
        const canvasEl = (el as HTMLElement).querySelector('.chart-canvas') as HTMLElement
        if (!canvasEl) return

        if (chartInstances[i]) {
          chartInstances[i].dispose()
        }
        const chart = echarts.init(canvasEl)
        chartInstances[i] = chart
        chartErrors.value[i] = ''

        const option: any = {
          tooltip: { trigger: c.type === 'pie' ? 'item' : 'axis' },
          legend: { bottom: 0, textStyle: { fontSize: 11 } },
          grid: { left: '3%', right: '4%', bottom: '8%', containLabel: true },
        }

        if (c.type === 'pie' && c.data) {
          option.series = [{
            type: 'pie', radius: ['40%', '70%'], center: ['50%', '45%'],
            data: c.data, label: { formatter: '{b}: {c} ({d}%)' },
          }]
        } else if ((c.type === 'bar' || c.type === 'line') && c.xAxis && c.series) {
          option.xAxis = { type: 'category', data: c.xAxis }
          option.yAxis = { type: 'value' }
          option.series = c.series.map((s: any) => ({ ...s, type: c.type }))
        } else if (c.data && c.type === 'pie') {
          option.series = [{ type: 'pie', data: c.data }]
        } else if (c.xAxis && c.series) {
          option.xAxis = { type: 'category', data: c.xAxis }
          option.yAxis = { type: 'value' }
          option.series = c.series.map((s: any) => ({ ...s, type: c.type || 'bar' }))
        } else {
          // 不支持的图表格式
          chartErrors.value[i] = '不支持的图表数据格式'
          return
        }
        chart.setOption(option)
        const ro = new ResizeObserver(() => chart.resize())
        ro.observe(canvasEl)
        resizeObservers[i] = ro
      } catch (e: any) {
        chartErrors.value[i] = e?.message || '未知错误'
      }
    })
  })
}

function onResize() {
  Object.values(chartInstances).forEach((inst: any) => inst?.resize())
}

watch(insights, () => mountCharts())

onMounted(async () => {
  loading.value = true
  try {
    conv.value = (await queryApi.detail(route.params.id as string)).data
    if (conv.value?.result_data?.insights) {
      insights.value = conv.value.result_data.insights
    }
  } catch (e: any) {
    ElMessage.error('加载报告失败: ' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally {
    loading.value = false
    mountCharts()
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  Object.values(chartInstances).forEach((inst: any) => inst?.dispose())
  Object.values(resizeObservers).forEach((ro) => ro.disconnect())
})
</script>

<style scoped>
.report-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--dm-surface);
}

.report-nav {
  height: 56px;
  min-height: 56px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 28px;
  background: var(--dm-card);
  border-bottom: 1px solid var(--dm-border);
}
.back-link {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: var(--dm-muted);
  font-size: 13px;
  font-weight: 600;
  font-family: var(--font-body);
  cursor: pointer;
  white-space: nowrap;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  transition: all 0.15s var(--ease-out);
}
.back-link svg { width: 14px; height: 14px; }
.back-link:hover { color: var(--dm-primary); background: var(--dm-primary-soft); }
.report-question {
  font-family: var(--font-body);
  font-size: 15px;
  font-weight: 600;
  color: var(--dm-text);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.export-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 14px;
  border: 1px solid var(--dm-border);
  border-radius: var(--radius-sm);
  background: var(--dm-card);
  font-size: 12px;
  font-weight: 600;
  font-family: var(--font-body);
  color: var(--dm-text2);
  cursor: pointer;
  transition: all 0.15s var(--ease-out);
  white-space: nowrap;
}
.export-btn svg { width: 14px; height: 14px; }
.export-btn:hover { border-color: var(--dm-primary); color: var(--dm-primary); background: var(--dm-primary-soft); }

.report-layout {
  flex: 1;
  overflow: auto;
  display: flex;
  padding: 24px 28px;
  gap: 24px;
}
.report-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.report-card {
  background: var(--dm-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--dm-border);
  padding: 28px 32px;
  box-shadow: var(--shadow-card);
}
.empty-report {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 0;
  color: var(--dm-muted);
}

/* 图表区域 */
.chart-grid { display: flex; flex-direction: column; gap: 16px; }
.chart-card {
  background: var(--dm-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--dm-border);
  padding: 16px 20px;
  box-shadow: var(--shadow-card);
}
.chart-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.chart-title {
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
  color: var(--dm-text);
  margin: 0;
}
.chart-type-tag {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 12px;
  background: var(--dm-surface);
  color: var(--dm-muted);
  text-transform: uppercase;
}
.chart-canvas { width: 100%; }
.chart-error { color: var(--dm-rose); font-size: 12px; text-align: center; padding: 20px 0; }

/* Sidebar */
.report-sidebar { width: 260px; min-width: 260px; display: flex; flex-direction: column; gap: 16px; }
.meta-card {
  background: var(--dm-card);
  border: 1px solid var(--dm-border);
  border-radius: var(--radius);
  padding: 18px;
  box-shadow: var(--shadow-card);
}
.meta-title {
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 700;
  color: var(--dm-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 0 0 14px;
}
.sql-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.sql-header .meta-title { margin: 0; }
.copy-btn {
  display: flex; align-items: center; gap: 4px;
  padding: 3px 10px; border: 1px solid var(--dm-border); border-radius: 6px;
  background: var(--dm-surface); color: var(--dm-text2);
  font-size: 11px; font-weight: 600; font-family: var(--font-body); cursor: pointer;
  transition: all 0.15s var(--ease-out);
}
.copy-btn svg { width: 12px; height: 12px; }
.copy-btn:hover { border-color: var(--dm-primary); color: var(--dm-primary); background: var(--dm-primary-soft); }
.meta-list { display: flex; flex-direction: column; gap: 10px; margin: 0; }
.meta-list div { display: flex; justify-content: space-between; align-items: baseline; }
.meta-list dt { font-size: 12px; color: var(--dm-muted); }
.meta-list dd { font-size: 13px; font-weight: 600; color: var(--dm-text); margin: 0; }
.sql-code {
  background: var(--dm-deep);
  color: #E2E8F0;
  padding: 14px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  line-height: 1.6;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}
.sql-code.collapsed { max-height: 200px; overflow: hidden; }
.expand-btn {
  display: block; width: 100%; padding: 6px 0; border: none; background: var(--dm-surface);
  color: var(--dm-primary); font-size: 11px; font-weight: 600; font-family: var(--font-body);
  cursor: pointer; border-radius: 0 0 6px 6px; transition: all 0.15s var(--ease-out);
}
.expand-btn:hover { background: var(--dm-primary-soft); }

/* Print */
@media print {
  .report-nav { display: none; }
  .report-sidebar { display: none; }
  .report-layout { padding: 0; display: block; }
  .report-main { max-width: 100%; }
  .chart-grid { break-inside: avoid; }
}
</style>
