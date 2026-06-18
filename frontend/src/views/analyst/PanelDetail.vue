<template>
  <div class="detail-page">
    <!-- 顶栏 -->
    <header class="detail-top">
      <div class="detail-top-left">
        <button class="back-btn" @click="$router.push('/analyst')">
          <svg viewBox="0 0 16 16" fill="none"><path d="M10 4l-4 4 4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
          返回驾驶舱
        </button>
        <div class="detail-title-group">
          <h2 class="detail-name">{{ detail?.datasource_name || '加载中…' }}</h2>
          <span class="detail-tag" :class="`tag-${detail?.business_tag}`">{{ detail?.business_tag }}</span>
        </div>
      </div>
      <button class="refresh-btn" @click="loadDetail" :disabled="loading">
        <svg viewBox="0 0 16 16" fill="none" :class="{ spinning: loading }"><path d="M2 8a6 6 0 0111.3-3M14 8a6 6 0 01-11.3 3M14 2v4h-4M2 14v-4h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        刷新数据
      </button>
    </header>

    <!-- KPI 卡片行 -->
    <div class="detail-kpi-row" v-if="detail?.kpi_cards?.length">
      <div class="kpi-card" v-for="(kpi, i) in detail.kpi_cards" :key="i">
        <div class="kpi-value">{{ kpi.value }}<span class="kpi-unit" v-if="kpi.unit">{{ kpi.unit }}</span></div>
        <div class="kpi-label">{{ kpi.label }}</div>
      </div>
    </div>

    <!-- ECharts 图表网格 -->
    <div class="charts-grid" v-loading="loading">
      <div v-for="chart in detail?.charts || []" :key="chart.id" class="chart-card"
           :style="{ height: (chart.height || 320) + 'px' }">
        <div class="chart-header">
          <h3 class="chart-title">{{ chart.title }}</h3>
        </div>
        <div class="chart-body" :ref="el => setChartRef(chart.id, el)"></div>
      </div>

      <div v-if="!detail?.charts?.length && !loading" class="empty-charts">
        <svg viewBox="0 0 48 48" fill="none" style="width:56px;height:56px;opacity:0.15;margin-bottom:12px">
          <rect x="6" y="6" width="16" height="16" rx="3" stroke="var(--dm-muted)" stroke-width="2"/>
          <rect x="26" y="6" width="16" height="16" rx="3" stroke="var(--dm-muted)" stroke-width="2"/>
          <rect x="6" y="26" width="16" height="16" rx="3" stroke="var(--dm-muted)" stroke-width="2"/>
          <rect x="26" y="26" width="16" height="16" rx="3" stroke="var(--dm-muted)" stroke-width="2"/>
        </svg>
        <p>暂无图表数据</p>
        <span>请先对数据源执行「探测」以生成分析图表</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { dashboardApi } from '@/api/dashboard'

const route = useRoute()
const datasourceId = computed(() => route.params.id as string)

const detail = ref<any>(null)
const loading = ref(false)
const chartRefs: Record<string, HTMLElement | null> = {}
const chartInstances: Record<string, any> = {}

watch(datasourceId, () => {
  loadDetail()
})

async function loadDetail() {
  loading.value = true
  try {
    const resp = await dashboardApi.getPanelDetail(datasourceId.value)
    detail.value = resp.data
    await nextTick()
    renderAllCharts()
  } catch (e: any) {
    ElMessage.error('加载面板失败: ' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadDetail()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  Object.keys(chartInstances).forEach((k) => {
    chartInstances[k]?.dispose()
    delete chartInstances[k]
  })
})

function setChartRef(id: string, el: any) {
  if (el) chartRefs[id] = el
}

const COLOR_PALETTE = ['#5B5FE3', '#00C9A7', '#F59E0B', '#F43F5E', '#3B82F6', '#8B5CF6', '#06B6D4', '#84CC16']

function renderChart(chart: any) {
  const el = chartRefs[chart.id]
  if (!el) return
  // 销毁旧实例
  if (chartInstances[chart.id]) {
    chartInstances[chart.id].dispose()
  }

  const instance = echarts.init(el)
  chartInstances[chart.id] = instance

  const option: any = {
    color: COLOR_PALETTE,
    tooltip: { trigger: chart.type === 'pie' ? 'item' : 'axis', backgroundColor: '#fff', borderColor: '#E2E8F0', textStyle: { color: '#1E293B', fontSize: 13 } },
    grid: { left: 50, right: 30, top: 20, bottom: 40 },
    legend: { bottom: 0, textStyle: { color: '#94A3B8', fontSize: 12 } },
  }

  if (chart.type === 'pie') {
    option.series = [{
      type: 'pie', radius: ['45%', '72%'], center: ['50%', '48%'],
      data: chart.data, label: { color: '#64748B', fontSize: 12 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.1)' } },
    }]
    option.grid = undefined
  } else if (chart.type === 'bar' && chart.subtype === 'stack') {
    option.xAxis = { type: 'category', data: chart.xAxis, axisLine: { lineStyle: { color: '#E2E8F0' } }, axisLabel: { color: '#94A3B8' } }
    option.yAxis = { type: 'value', splitLine: { lineStyle: { color: '#F1F5F9' } }, axisLabel: { color: '#94A3B8' } }
    option.series = chart.series.map((s: any) => ({ ...s, type: 'bar', stack: 'total', barWidth: '50%' }))
  } else if (chart.type === 'bar') {
    option.xAxis = { type: 'category', data: chart.xAxis, axisLine: { lineStyle: { color: '#E2E8F0' } }, axisLabel: { color: '#94A3B8' } }
    option.yAxis = { type: 'value', splitLine: { lineStyle: { color: '#F1F5F9' } }, axisLabel: { color: '#94A3B8' } }
    option.series = chart.series.map((s: any) => ({ ...s, type: 'bar', barWidth: '50%', itemStyle: { borderRadius: [6, 6, 0, 0] } }))
    if (chart.markLine) {
      option.series[0].markLine = { silent: true, lineStyle: { color: '#F43F5E', type: 'dashed' }, data: [{ yAxis: chart.markLine, label: { formatter: '预警线 ' + chart.markLine + '%', color: '#F43F5E' } }] }
    }
  } else if (chart.type === 'line') {
    option.xAxis = { type: 'category', data: chart.xAxis, axisLine: { lineStyle: { color: '#E2E8F0' } }, axisLabel: { color: '#94A3B8' }, boundaryGap: false }
    option.yAxis = { type: 'value', splitLine: { lineStyle: { color: '#F1F5F9' } }, axisLabel: { color: '#94A3B8' } }
    if (chart.dualY) {
      option.yAxis = [
        { type: 'value', splitLine: { lineStyle: { color: '#F1F5F9' } }, axisLabel: { color: '#94A3B8' } },
        { type: 'value', axisLabel: { color: '#94A3B8' } },
      ]
    }
    option.series = chart.series.map((s: any, i: number) => ({
      ...s, type: 'line', smooth: true, symbol: 'circle', symbolSize: 6,
      yAxisIndex: chart.dualY ? i : 0,
      lineStyle: { width: 3 }, areaStyle: { opacity: 0.06 },
    }))
  }

  instance.setOption(option)
}

function renderAllCharts() {
  if (!detail.value?.charts) return
  nextTick(() => {
    detail.value.charts.forEach((chart: any) => renderChart(chart))
  })
}

// 窗口 resize 时重绘
function onResize() {
  Object.values(chartInstances).forEach((inst: any) => inst?.resize())
}

</script>

<style scoped>
.detail-page { height: 100vh; display: flex; flex-direction: column; background: var(--dm-surface); overflow: hidden; }

/* 顶栏 */
.detail-top {
  height: 56px; min-height: 56px; padding: 0 24px; display: flex; align-items: center;
  justify-content: space-between; background: var(--dm-card); border-bottom: 1px solid var(--dm-border);
}
.detail-top-left { display: flex; align-items: center; gap: 16px; }
.back-btn {
  display: flex; align-items: center; gap: 4px; padding: 6px 10px; border: none; background: none;
  border-radius: var(--radius-sm); font-size: 13px; font-weight: 600; font-family: var(--font-body);
  color: var(--dm-muted); cursor: pointer; transition: all 0.15s var(--ease-out);
}
.back-btn svg { width: 14px; height: 14px; }
.back-btn:hover { color: var(--dm-primary); background: var(--dm-primary-soft); }
.detail-title-group { display: flex; align-items: center; gap: 10px; }
.detail-name { font-family: var(--font-display); font-size: 17px; font-weight: 700; color: var(--dm-text); margin: 0; }
.detail-tag { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 20px; }
.tag-hr { background: var(--dm-primary-soft); color: var(--dm-primary); }
.tag-crm { background: var(--dm-amber-soft); color: var(--dm-amber); }
.tag-finance { background: var(--dm-accent-soft); color: var(--dm-accent); }
.refresh-btn {
  display: flex; align-items: center; gap: 5px; padding: 7px 14px; border: 1px solid var(--dm-border);
  border-radius: var(--radius-sm); background: var(--dm-card); font-size: 12px; font-weight: 600;
  font-family: var(--font-body); color: var(--dm-text2); cursor: pointer; transition: all 0.15s var(--ease-out);
}
.refresh-btn svg { width: 14px; height: 14px; }
.refresh-btn:hover { border-color: var(--dm-primary); color: var(--dm-primary); background: var(--dm-primary-soft); }
.refresh-btn:disabled { opacity: 0.5; }
.spinning { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* KPI 行 */
.detail-kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; padding: 18px 24px; flex-shrink: 0; }
.kpi-card {
  padding: 16px 18px; background: var(--dm-card);
  border-radius: var(--radius); border: 1px solid var(--dm-border); text-align: center;
  box-shadow: var(--shadow-card); transition: all 0.2s var(--ease-out);
  overflow: hidden;
}
.kpi-card:hover { box-shadow: var(--shadow-card-hover); transform: translateY(-1px); }
.kpi-value { font-family: var(--font-display); font-size: 30px; font-weight: 800; color: var(--dm-text); letter-spacing: -0.02em; line-height: 1.2; }
.kpi-unit { font-size: 14px; font-weight: 500; color: var(--dm-muted); margin-left: 3px; }
.kpi-label { font-size: 12px; color: var(--dm-muted); margin-top: 4px; font-weight: 500; }

/* 图表网格 */
.charts-grid { flex: 1; overflow: auto; padding: 0 24px 24px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.chart-card { background: var(--dm-card); border-radius: var(--radius-lg); border: 1px solid var(--dm-border); box-shadow: var(--shadow-card); display: flex; flex-direction: column; overflow: hidden; }
.chart-header { padding: 14px 18px 0; flex-shrink: 0; }
.chart-title { font-family: var(--font-display); font-size: 14px; font-weight: 700; color: var(--dm-text2); margin: 0; }
.chart-body { flex: 1; min-height: 0; }
.empty-charts { grid-column: 1/-1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 48px 0; color: var(--dm-muted); }
.empty-charts p { margin: 0; font-weight: 600; font-size: 14px; }
.empty-charts span { font-size: 12px; margin-top: 4px; }

@media (max-width: 1024px) {
  .charts-grid { grid-template-columns: 1fr; }
}
</style>
