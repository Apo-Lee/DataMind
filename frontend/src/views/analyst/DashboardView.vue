<template>
  <div class="cockpit">
    <header class="cockpit-top">
      <div class="cockpit-brand">
        <svg class="cockpit-logo" viewBox="0 0 28 28" fill="none"><rect x="1" y="1" width="10" height="10" rx="2" fill="currentColor" opacity="0.9"/><rect x="15" y="1" width="12" height="6" rx="2" fill="currentColor" opacity="0.5"/><rect x="15" y="10" width="5" height="15" rx="2" fill="currentColor" opacity="0.7"/><rect x="23" y="10" width="4" height="10" rx="1.5" fill="currentColor" opacity="0.4"/><rect x="1" y="15" width="10" height="10" rx="2" fill="currentColor" opacity="0.6"/></svg>
        <span class="cockpit-title">DataMind</span>
      </div>

      <!-- A) 推荐提问胶囊 -->
      <div class="suggest-bar">
        <span class="suggest-greeting">{{ greeting }}</span>
        <button v-for="q in quickQuestions" :key="q" class="suggest-chip" @click="handleAsk(q, deepAnalyze)" :disabled="asking || !store.mainPanel">{{ q }}</button>
      </div>

      <div class="cockpit-meta">
        <span class="ds-badge" v-if="store.mainPanel">{{ store.mainPanel.datasource_name }} &middot; {{ store.panels.length }} 个数据源</span>
        <button class="toggle-sidebar-btn" :class="{ active: sidebarOpen }" @click="sidebarOpen = !sidebarOpen">
          <svg viewBox="0 0 16 16" fill="none"><rect x="2" y="3" width="12" height="2" rx="1" fill="currentColor"/><rect x="2" y="7" width="12" height="2" rx="1" fill="currentColor"/><rect x="2" y="11" width="8" height="2" rx="1" fill="currentColor"/></svg>
        </button>
        <div class="user-chip" @click="handleLogout">
          <span class="user-initial">{{ authStore.user?.display_name?.[0] || '?' }}</span>
          <span>{{ authStore.user?.display_name }}</span>
        </div>
      </div>
    </header>

    <div class="cockpit-grid">
      <main class="main-col">
        <div class="main-col-body">
          <section class="main-panel-section">
            <div v-if="store.mainPanel" class="main-panel-wrapper">
              <div class="main-panel-header">
                <span class="main-panel-name">{{ store.mainPanel.datasource_name }}</span>
                <span class="main-panel-tag" :class="'tag-'+store.mainPanel.business_tag">{{ store.mainPanel.business_tag.toUpperCase() }}</span>
                <span v-if="store.mainPanel.is_primary" class="primary-star">★ 主看板</span>
              </div>
              <div class="main-panel-kpis">
                <KpiCard v-for="(kpi, ki) in store.mainPanel.kpi_cards" :key="'m-'+ki" v-bind="kpi" @drill="(q: string) => handleAsk(q, deepAnalyze)" />
              </div>
              <div class="main-panel-charts" v-if="store.mainPanel.charts && store.mainPanel.charts.length > 0">
                <div v-for="(ch, ci) in store.mainPanel.charts" :key="store.mainPanel.datasource_id + '-' + ch.id" class="chart-card">
                  <div class="chart-title-bar">{{ ch.title }}</div>
                  <div :ref="el => setMainChartRef(ch.id, el)" :style="{height: (ch.height||280)+'px', width:'100%'}" class="chart-container"></div>
                </div>
              </div>
              <div class="panel-detail-link" v-if="store.mainPanel">
                <button class="detail-btn" @click="router.push('/analyst/panel/'+store.mainPanel.datasource_id)">
                  查看详细数据报告 →
                </button>
              </div>
            </div>
            <div v-else class="empty-state">
              <svg viewBox="0 0 48 48" fill="none" style="width:64px;height:64px;opacity:0.15"><rect x="4" y="4" width="16" height="16" rx="3" stroke="var(--dm-muted)" stroke-width="2"/><rect x="24" y="4" width="20" height="10" rx="3" stroke="var(--dm-muted)" stroke-width="2"/><rect x="4" y="24" width="16" height="16" rx="3" stroke="var(--dm-muted)" stroke-width="2"/><rect x="24" y="18" width="8" height="22" rx="3" stroke="var(--dm-muted)" stroke-width="2"/><rect x="36" y="18" width="8" height="16" rx="3" stroke="var(--dm-muted)" stroke-width="2"/></svg>
              <p v-if="authStore.user?.role && authStore.user.role !== 'admin'">
                您的角色（{{ roleLabel(authStore.user.role) }}）暂未分配数据源权限，请联系管理员。
              </p>
              <p v-else>暂无可用的数据源，请联系管理员。</p>
              <button class="primary-btn-sm" @click="store.fetchPanels">刷新</button>
            </div>
          </section>
          <section v-if="store.subPanels.length > 0" class="sub-panel-section">
            <div class="sub-grid" :style="{ gridTemplateColumns: `repeat(${Math.min(store.subPanels.length, 3)}, 1fr)` }">
              <div v-for="panel in store.subPanels" :key="'sub-'+panel.datasource_id" class="sub-panel-card" @click="store.setMainPanel(store.panels.indexOf(panel))">
                <div class="sub-panel-header">
                  <span class="sub-panel-name">{{ panel.datasource_name }}</span>
                  <span class="sub-panel-tag" :class="'tag-'+panel.business_tag">{{ panel.business_tag }}</span>
                </div>
                <div class="sub-panel-kpis">
                  <KpiCard v-for="(kpi, ki) in panel.kpi_cards" :key="'s-'+ki" v-bind="kpi" @drill="(q: string) => handleAsk(q, deepAnalyze)" />
                </div>
                <div v-if="panel.kpi_cards.length === 0" class="sub-panel-empty">
                  当前角色暂无该数据源的 KPI 视图权限
                </div>
                <!-- 子看板迷你图：默认 1 张 -->
                <div v-if="panel.charts && panel.charts.length > 0" class="sub-panel-mini-chart">
                  <div :ref="el => setSubChartRef(panel.datasource_id, el)" :style="{height: '120px', width:'100%'}" class="chart-container"></div>
                </div>
              </div>
            </div>
          </section>
        </div>
        <footer class="query-area">
          <!-- P0#4: 数据源选择器 -->
          <div v-if="store.panels.length > 1" class="ds-selector">
            <label class="ds-selector-label">提问对象：</label>
            <select v-model="selectedDsId" class="ds-select">
              <option v-for="p in store.panels" :key="p.datasource_id" :value="p.datasource_id">
                {{ p.datasource_name }}（{{ p.business_tag }}）
              </option>
            </select>
          </div>
          <QueryInput :loading="asking" :placeholder="inputPlaceholder" @send="handleAskPayload" @cancel="handleCancelAsk" />
        </footer>
      </main>

      <aside class="side-panel" :class="{ 'side-open': sidebarOpen }">
        <div class="side-tabs">
          <button class="side-tab" :class="{ active: sideTab === 'terminal' }" @click="sideTab = 'terminal'">
            <svg viewBox="0 0 14 14" fill="none"><path d="M3 4l3 3-3 3M8 10h3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>AI 终端
          </button>
          <button class="side-tab" :class="{ active: sideTab === 'report' }" @click="sideTab = 'report'">
            <svg viewBox="0 0 14 14" fill="none"><rect x="2" y="1.5" width="10" height="11" rx="2" stroke="currentColor" stroke-width="1.5"/><path d="M5 5h4M5 8h3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>结果
          </button>
          <button class="side-tab" :class="{ active: sideTab === 'history' }" @click="sideTab = 'history'">
            <svg viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="5.5" stroke="currentColor" stroke-width="1.5"/><path d="M7 4v3l2 2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>历史
          </button>
          <button class="side-close" @click="sidebarOpen = false">
            <svg viewBox="0 0 14 14" fill="none"><path d="M10 4l-6 6M4 4l6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
          </button>
        </div>
        <div class="side-content">
          <div v-if="sideTab === 'terminal'" class="terminal-pane">
            <div class="terminal-output" ref="termRef">
              <div v-if="terminalLogs.length === 0 && !asking" class="terminal-empty"><span class="term-prompt">$</span> 等待 AI 分析任务…</div>
              <div v-for="(line, i) in terminalLogs" :key="i" class="term-line" :class="`term-${line.level}`"><span class="term-time">{{ line.time }}</span><span class="term-prompt">{{ line.level === 'error' ? '✗' : line.level === 'success' ? '✓' : line.level === 'warn' ? '⚠' : '▸' }}</span><span>{{ line.text }}</span><code v-if="line.code" class="term-code">{{ line.code }}</code></div>
              <div v-if="asking" class="term-line term-info"><span class="term-spinner"></span><span>{{ currentStep || 'AI 分析中…' }}</span><span class="term-elapsed">{{ elapsedTime }}</span></div>
            </div>
          </div>
          <div v-if="sideTab === 'report'" class="report-pane">
            <div v-if="lastReport" class="side-report"><div class="side-report-meta"><span class="side-report-q">{{ lastReport.question }}</span><span class="side-report-tag">{{ lastReport.intent }}</span><span v-if="lastReport.deepAnalyze" class="side-report-deep-badge">深度分析</span><span v-if="lastReport.insights?.length" class="side-report-insight-count">{{ lastReport.insights.length }} 项洞察</span></div><div class="side-report-body"><div v-for="(ins, ii) in chartItems" :key="'chart-'+ii" :ref="el => setChartRef(ii, el)" :style="{height:'280px', width:'100%'}" class="chart-container"></div><MarkdownReport :content="lastReport.markdown" /></div><button class="primary-btn-sm" @click="router.push(`/analyst/${lastReport.id}`)" style="margin-top:12px">查看完整报告</button></div>
            <div v-else class="terminal-empty">尚无分析结果</div>
          </div>
          <div v-if="sideTab === 'history'" class="history-pane">
            <div v-if="history.length === 0" class="terminal-empty">暂无查询历史</div>
            <!-- P1#12: 搜索/筛选 -->
            <div v-if="history.length > 0" class="history-search-bar">
              <input v-model="historySearch" placeholder="搜索历史…" class="history-search-input" />
              <select v-model="historyFilter" class="history-filter-select">
                <option value="">全部</option>
                <option v-for="intent in uniqueIntents" :key="intent" :value="intent">{{ intent }}</option>
              </select>
            </div>
            <div v-for="(h, i) in filteredHistory" :key="i" class="history-item" @click="router.push(`/analyst/${h.id}`)"><div class="history-q">{{ h.question }}</div><div class="history-meta"><span>{{ h.intent || '—' }}</span><span>{{ formatTime(h.created_at) }}</span></div></div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, nextTick, watch, onBeforeUnmount, onUpdated } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'  // P1-3: 取消提示
import { useDashboardStore } from '@/stores/dashboard'
import { useAuthStore } from '@/stores/auth'
import { queryApi } from '@/api/query'
import PanelCard from '@/components/PanelCard.vue'
import KpiCard from '@/components/KpiCard.vue'
import QueryInput from '@/components/QueryInput.vue'
import MarkdownReport from '@/components/MarkdownReport.vue'
import * as echarts from 'echarts'

const router = useRouter()
const store = useDashboardStore()
const authStore = useAuthStore()
const sidebarOpen = ref(true)
const sideTab = ref<'terminal' | 'report' | 'history'>('terminal')
interface LogLine { time: string; level: 'info' | 'success' | 'error' | 'warn'; text: string; code?: string }
const terminalLogs = ref<LogLine[]>([])
const termRef = ref<HTMLElement>()
const asking = ref(false)
const deepAnalyze = ref(false)
// Watch deepAnalyze toggle from QueryInput via the payload
// deepAnalyze is also used by suggest-chip clicks
const currentStep = ref('')
const elapsedTime = ref('')
let elapsedTimer: ReturnType<typeof setInterval> | null = null
function startElapsedTimer() {
  const start = Date.now()
  elapsedTimer = setInterval(() => {
    const secs = Math.floor((Date.now() - start) / 1000)
    const m = Math.floor(secs / 60)
    const s = secs % 60
    elapsedTime.value = m > 0 ? `${m}分${s}秒` : `${s}秒`
  }, 1000)
}
function stopElapsedTimer() {
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null }
  elapsedTime.value = ''
}
const lastReport = ref<{ id: string; question: string; intent: string; markdown: string; insights?: any[]; deepAnalyze?: boolean } | null>(null)
const chartInstances = ref<Record<number, any>>({})
const chartContainers = ref<Record<number, HTMLElement>>({})
const chartItems = computed(() => {
  if (!lastReport.value?.insights) return []
  return lastReport.value.insights.filter((ins: any) => ins.type === 'chart')
})
function setChartRef(idx: number, el: any) {
  if (el) chartContainers.value[idx] = el as HTMLElement
}
const history = ref<any[]>([])
// P0#4: 数据源选择器
const selectedDsId = ref<string>('')
const abortController = ref<AbortController | null>(null)
// P1#12: 历史搜索
const historySearch = ref('')
const historyFilter = ref('')

function roleLabel(role?: string) {
  const map: Record<string,string> = { admin:'管理员', hr_director:'HR总监', finance_bp:'财务BP', finance_director:'财务总监', dept_ceo:'部门CEO', dept_manager:'部门经理', sales_manager:'销售经理', employee:'员工', viewer:'只读' }
  return map[role || ''] || role || ''
}

// A) 问候语
const greeting = computed(() => {
  const h = new Date().getHours()
  const name = authStore.user?.display_name || ''
  if (h < 11) return `早上好，${name}`
  if (h < 14) return `中午好，${name}`
  if (h < 18) return `下午好，${name}`
  return `晚上好，${name}`
})

// A) 根据角色生成推荐提问
const quickQuestions = computed(() => {
  const role = authStore.user?.role
  if (!role || !store.mainPanel) return []
  const qs: Record<string, string[]> = {
    admin: ['各部门人力分布如何', '本月费用支出概览', '客户跟进状态统计'],
    hr_director: ['各部门在职人数统计', '近半年绩效趋势', '本月新入职员工'],
    finance_bp: ['各部门预算使用率', '今年费控趋势分析', '超支预警部门'],
    dept_ceo: ['我部门人效趋势', '部门预算使用情况', '客户与费用全景'],
  }
  return qs[role] || qs.dept_ceo
})

// P1#9: 动态 placeholder
const inputPlaceholder = computed(() => {
  if (!store.mainPanel) return '请先加载数据源…'
  const q = quickQuestions.value[0]
  return q ? `向「${store.mainPanel.datasource_name}」提问，如"${q}"` : `向「${store.mainPanel.datasource_name}」提问…`
})

// P1#12: 过滤后的历史
const uniqueIntents = computed(() => {
  const intents = new Set<string>()
  history.value.forEach((h: any) => { if (h.intent) intents.add(h.intent) })
  return Array.from(intents).sort()
})
const filteredHistory = computed(() => {
  let list = history.value
  const q = historySearch.value.toLowerCase()
  const f = historyFilter.value
  if (q) list = list.filter((h: any) => h.question?.toLowerCase().includes(q))
  if (f) list = list.filter((h: any) => h.intent === f)
  return list
})

// 进度步骤友好文案
const STEP_LABELS: Record<string, string> = {
  intent: '正在理解您的问题…',
  sql: '正在检索相关数据…',
  execute: '正在获取数据…',
  analysis: '正在进行深度分析…',
  report: '正在生成分析报告…',
}

function now() { return new Date().toLocaleTimeString('zh-CN', { hour12: false }) }
function addLog(level: LogLine['level'], text: string, code?: string) {
  terminalLogs.value.push({ time: now(), level, text, code })
  // 限制日志最多 200 条
  if (terminalLogs.value.length > 200) terminalLogs.value.shift()
  nextTick(() => { if (termRef.value) termRef.value.scrollTop = termRef.value.scrollHeight })
}
function formatTime(t?: string) { if (!t) return '—'; return new Date(t).toLocaleString('zh-CN', { dateStyle: 'short', timeStyle: 'short' }) }
function handleLogout() { authStore.logout(); router.push('/login') }

// 图表渲染 - 分析报告中的 ECharts 图表
watch(() => lastReport.value?.insights, async (insights) => {
  // 先销毁旧图表
  Object.values(chartInstances.value).forEach((inst: any) => { try { inst.dispose() } catch {} })
  chartInstances.value = {}
  if (!insights || insights.length === 0) return
  await nextTick()
  insights.forEach((ins: any, idx: number) => {
    if (ins.type !== 'chart') return
    const container = chartContainers.value[idx]
    if (!container) return
    try {
      const chart = echarts.init(container)
      chart.setOption(ins.content || {})
      chartInstances.value[idx] = chart
      const handler = () => chart.resize()
      window.addEventListener('resize', handler)
      ;(chart as any)._dmResizeHandler = handler
    } catch (e) {
      console.warn('Chart render failed:', e)
    }
  })
}, { deep: true })

// V2.4: 图表挂载
const mainChartInstances = new Map<string, echarts.ECharts>()
const resizeObservers = new Map<string, ResizeObserver>()
const mainChartRefs: Record<string, HTMLElement | null> = {}
const subChartRefs: Record<string, HTMLElement | null> = {}

function setMainChartRef(id: string, el: any) {
  if (el) mainChartRefs[id] = el
}
function setSubChartRef(datasourceId: string, el: any) {
  if (el) subChartRefs[datasourceId] = el
}

// 实际挂载逻辑（不包裹 nextTick）
function doMountCharts() {
  // 清理旧的图表和 ResizeObserver
  resizeObservers.forEach((ro) => ro.disconnect())
  resizeObservers.clear()
  mainChartInstances.forEach((inst) => inst.dispose())
  mainChartInstances.clear()

  // 1) 主看板 — 完整渲染
  const panel = store.mainPanel
  if (panel && panel.charts && panel.charts.length > 0) {
    panel.charts.forEach((ch: any) => {
      const key = ch.id
      const el = mainChartRefs[key]
      if (!el) {
        console.warn(`[Dashboard] main chart element not found: ${key}`)
        return
      }
      el.innerHTML = ''
      const chart = echarts.init(el)
      const option: any = {
        tooltip: { trigger: ch.type === 'pie' ? 'item' : 'axis' },
        legend: { bottom: 0, textStyle: { fontSize: 10 } },
        grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
      }
      if (ch.type === 'pie' && ch.data && ch.data.length > 0) {
        option.series = [{
          type: 'pie', radius: ['40%', '70%'], center: ['50%', '45%'],
          data: ch.data, label: { formatter: '{b}: {d}%' },
        }]
        option.title = { text: ch.title, left: 'center', top: 0, textStyle: { fontSize: 12, fontWeight: 700 } }
      } else if (ch.xAxis && ch.series) {
        option.xAxis = { type: 'category', data: ch.xAxis }
        option.yAxis = { type: 'value' }
        option.series = ch.series.map((s: any) => ({ ...s, type: ch.type === 'stack' ? 'bar' : ch.type }))
        if (ch.type === 'stack' || ch.subtype === 'stack') {
          option.series.forEach((s: any) => s.stack = 'total')
        }
        option.title = { text: ch.title, left: 'center', top: 0, textStyle: { fontSize: 12, fontWeight: 700 } }
      }
      chart.setOption(option)
      mainChartInstances.set(key, chart)
      const ro = new ResizeObserver((entries) => {
        for (const entry of entries) {
          const cr = entry.contentRect
          if (cr.width > 0 && cr.height > 0) chart.resize()
        }
      })
      ro.observe(el)
      resizeObservers.set(key, ro)
    })
  }

  // 2) 子看板 — 迷你图（只取第1张）
  store.subPanels.forEach((sp: any) => {
    if (!sp.charts || sp.charts.length === 0) return
    const ch = sp.charts[0]
    const key = `sub-${sp.datasource_id}`
    const el = subChartRefs[sp.datasource_id]
    if (!el) {
      console.warn(`[Dashboard] sub chart element not found: ${key}`)
      return
    }
    el.innerHTML = ''
    const chart = echarts.init(el)
    const option: any = {
      tooltip: { show: false },
      legend: { show: false },
      grid: { left: '2%', right: '2%', top: '8%', bottom: '2%', containLabel: true },
      xAxis: { show: false, type: 'category', data: ch.xAxis || ch.data?.map((d: any) => d.name) },
      yAxis: { show: false, type: 'value' },
    }
    if (ch.type === 'pie' && ch.data && ch.data.length > 0) {
      option.series = [{
        type: 'pie', radius: ['50%', '80%'], center: ['50%', '50%'],
        data: ch.data, label: { show: false },
      }]
    } else if (ch.xAxis && ch.series) {
      option.series = ch.series.map((s: any) => ({ ...s, type: ch.type === 'stack' ? 'bar' : ch.type, label: { show: false } }))
      if (ch.type === 'stack' || ch.subtype === 'stack') {
        option.series.forEach((s: any) => s.stack = 'total')
      }
    }
    chart.setOption(option)
    mainChartInstances.set(key, chart)
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const cr = entry.contentRect
        if (cr.width > 0 && cr.height > 0) chart.resize()
      }
    })
    ro.observe(el)
    resizeObservers.set(key, ro)
  })
}

// 供 onMounted 等场景使用，确保 DOM 已就绪
function mountCharts() {
  nextTick(() => doMountCharts())
}

// P0#14: 窗口 resize 时统一触发所有图表 resize，防止 grid 列变化时 canvas 错位
function handleWindowResize() {
  mainChartInstances.forEach((chart) => chart.resize())
}
window.addEventListener('resize', handleWindowResize)

onBeforeUnmount(() => {
  stopElapsedTimer()
  Object.values(chartInstances.value).forEach((inst: any) => {
    try {
      if ((inst as any)._dmResizeHandler) window.removeEventListener('resize', (inst as any)._dmResizeHandler)
      inst.dispose()
    } catch {}
  })
  window.removeEventListener('resize', handleWindowResize)
  resizeObservers.forEach((ro) => ro.disconnect())
  resizeObservers.clear()
  mainChartInstances.forEach((inst) => inst.dispose())
  mainChartInstances.clear()
  if (abortController.value) {
    abortController.value.abort()
    abortController.value = null
  }
})

// flush: 'post' 确保 DOM 已更新后再 doMountCharts，避免旧 canvas 残留
watch(() => store.mainPanel, (newVal) => {
  if (newVal) selectedDsId.value = newVal.datasource_id
  doMountCharts()  // 直接调用，不再包 nextTick
}, { flush: 'post' })

onMounted(() => {
  store.fetchPanels().then(() => {
    if (store.mainPanel) selectedDsId.value = store.mainPanel.datasource_id
    mountCharts() // nextTick 确保 DOM 就绪
  })
  loadHistory()
})

const lastMountedDsId = ref('')

onUpdated(() => {
  const currentDsId = store.mainPanel?.datasource_id
  if (currentDsId && currentDsId !== lastMountedDsId.value) {
    lastMountedDsId.value = currentDsId
    doMountCharts()
  }
})

// P0#5: 取消分析
function handleCancel() {
  if (abortController.value) {
    abortController.value.abort()
    abortController.value = null
  }
  stopElapsedTimer()
  asking.value = false
  currentStep.value = ''
  addLog('warn', '分析已取消')
  // P1-3: 提示用户取消仅断开前端连接，后端可能仍在执行
  ElMessage.warning('已断开连接，后端任务可能仍在执行中')
}

async function handleAskPayload(payload: { question: string; deepAnalyze: boolean }) {
  handleAsk(payload.question, payload.deepAnalyze)
}
function handleCancelAsk() { deepAnalyze.value = false; stopElapsedTimer(); if (abortController.value) { abortController.value.abort(); asking.value = false } }

async function handleAsk(question: string, deepAnalyze: boolean = false) {
  const dsId = selectedDsId.value || store.mainPanel?.datasource_id
  if (!dsId) return
  asking.value = true
  startElapsedTimer()
  // P0#5: 不在这里清空日志，保留最近的 3 次分析历史
  abortController.value = new AbortController()
  addLog('info', `收到问题: ${question}`)
  try {
    currentStep.value = STEP_LABELS.intent
    addLog('info', 'STEP 1: 意图识别 — 分析问题复杂度与数据范围')
    const resp = dsId ? await queryApi.ask(dsId, question, deepAnalyze, abortController.value.signal) : await queryApi.askAuto(question, deepAnalyze, abortController.value.signal); const d = resp.data
    addLog('success', `意图识别完成 → ${d.intent}（${d.analysis_depth === 'complex' ? '深度分析' : '快速查询'}）`)
    currentStep.value = STEP_LABELS.sql
    addLog('info', 'STEP 2: SQL 生成 — 根据表结构生成查询')
    addLog('success', 'SQL 已生成', d.sql_generated.substring(0, 200) + (d.sql_generated.length > 200 ? '...' : ''))
    currentStep.value = STEP_LABELS.execute
    addLog('info', 'STEP 3: 数据获取 — 执行 SQL 查询')

    // V2.1: 展示 Python 分析/图表
    if (d.analysis_depth === 'complex') {
      addLog('info', 'STEP 4: 深度分析 — 启动 Python 沙箱执行统计建模')
      currentStep.value = STEP_LABELS.analysis
      if (d.insights && d.insights.length > 0) {
        for (const ins of d.insights) {
          if (ins.type === 'text') addLog('success', `洞察: ${ins.content}`)
          else if (ins.type === 'chart') addLog('info', `图表生成: ${ins.content?.title || ''}`)
        }
      }
      addLog('success', 'Python 分析完成')
    } else {
      addLog('info', `STEP 4: 数据摘要 — ${d.insights?.length || 0} 项结果`)
      // P0: 在终端日志中直接展示报告结论，用户不用切换 tab
      if (d.report_markdown) {
        let preview = d.report_markdown
          .replace(/[#*`\[\]]/g, "")
          .replace(/\n{3,}/g, "\n")
          .trim()
          .slice(0, 500)
        if (preview) addLog('success', preview)
      }
    }

    currentStep.value = STEP_LABELS.report
    addLog('info', 'STEP 5: 报告组装 — 生成 Markdown 分析报告')
    addLog('success', '分析完成')
    lastReport.value = { id: d.conversation_id, question, intent: d.intent, markdown: d.report_markdown, insights: d.insights, deepAnalyze }
    loadHistory()
    // 仅在用户未手动切换标签时自动跳到结果
    if (sideTab.value === 'terminal') sideTab.value = 'report'
  } catch (e: any) {
    // P0#5: 用户主动取消 — 不显示错误
    if (e?.name === 'CanceledError' || e?.code === 'ERR_CANCELED') {
      addLog('warn', '分析已取消')
      return
    }
        // 增强版分类错误指引
    const detail = e?.response?.data?.detail || e?.message || e?.toString() || '未知错误'
    const status = e?.response?.status
    const respData = e?.response?.data
    const reportMd = respData?.report_markdown || ''
    addLog('error', '分析失败')

    if (reportMd && respData?.intent === 'error') {
      addLog('warn', reportMd.replace(/[#*`[]]/g, '').replace(/\n{2,}/g, ' ').trim().slice(0, 300))
      return
    }

    const errorTips = {
      403: '💡 你没有该数据源的访问权限，请联系管理员分配。可以试试查询自己的数据。',
      404: '💡 数据源不存在或已被删除，请检查数据源配置。',
      422: '💡 请求参数有误，请换个说法重新提问。',
    }
    if (status in errorTips) {
      addLog('warn', errorTips[status as keyof typeof errorTips])
      return
    }

    const lowerDetail = detail.toLowerCase()
    if (lowerDetail.includes('权限') || lowerDetail.includes('permission') || lowerDetail.includes('无权')) {
      addLog('warn', '💡 权限不足，当前角色无法访问这些数据。试试查询个人数据或联系管理员。')
    } else if (lowerDetail.includes('找不到') || lowerDetail.includes('404') || lowerDetail.includes('not found')) {
      addLog('warn', '💡 请求的资源不存在，请检查名称是否正确。')
    } else if (lowerDetail.includes('超时') || lowerDetail.includes('timeout')) {
      addLog('warn', '💡 查询超时，数据量可能较大，试试缩小查询范围。')
    } else if (lowerDetail.includes('sql') && (status === 400 || status === 500)) {
      addLog('warn', '💡 查询生成失败，请尝试用更具体的条件重新提问。')
    } else if (lowerDetail.includes('数据源') || lowerDetail.includes('datasource')) {
      addLog('warn', '💡 数据源不可用，请联系管理员检查配置。')
    } else if (status === 500) {
      addLog('warn', '💡 服务内部错误，请稍后重试。如果持续出现，请联系管理员。')
    } else {
      addLog('warn', '💡 服务暂时不可用，请检查网络连接或稍后重试。')
    }
  } finally {
    asking.value = false; currentStep.value = ''; abortController.value = null
  }
}
async function loadHistory() { try { history.value = (await queryApi.history()).data } catch (e: any) { addLog('error', '加载历史失败: ' + (e?.message || '未知错误')) } }
</script>

<style scoped>
.cockpit { height: 100vh; display: flex; flex-direction: column; background: linear-gradient(180deg, var(--dm-surface) 0%, #F0F2F7 100%); }

/* ===== 顶栏 ===== */
.cockpit-top { height: 56px; min-height: 56px; padding: 0 24px; display: flex; align-items: center; justify-content: space-between; gap: 16px; background: var(--dm-card); border-bottom: 1px solid var(--dm-border); }
.cockpit-brand { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.cockpit-logo { width: 26px; height: 26px; color: var(--dm-primary); }
.cockpit-title { font-family: var(--font-display); font-size: 17px; font-weight: 800; color: var(--dm-text); letter-spacing: -0.02em; }

/* A) 推荐提问胶囊 */
.suggest-bar { flex: 1; display: flex; align-items: center; gap: 10px; overflow: hidden; }
.suggest-greeting { font-size: 13px; font-weight: 600; color: var(--dm-text2); white-space: nowrap; flex-shrink: 0; }
.suggest-chip { padding: 5px 14px; border-radius: 18px; border: 1px solid var(--dm-border); background: var(--dm-surface); font-size: 12px; font-family: var(--font-body); font-weight: 500; color: var(--dm-text2); cursor: pointer; transition: all 0.15s var(--ease-out); white-space: nowrap; }
.suggest-chip:hover { background: var(--dm-primary-soft); border-color: var(--dm-primary); color: var(--dm-primary); }
.suggest-chip:disabled { opacity: 0.4; cursor: not-allowed; }

.cockpit-meta { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.ds-badge { font-size: 11px; color: var(--dm-muted); font-weight: 500; }
.toggle-sidebar-btn { width: 32px; height: 32px; border-radius: var(--radius-sm); border: 1px solid var(--dm-border); background: var(--dm-card); color: var(--dm-muted); cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.15s var(--ease-out); }
.toggle-sidebar-btn svg { width: 14px; height: 14px; }
.toggle-sidebar-btn:hover { border-color: var(--dm-primary); color: var(--dm-primary); }
.toggle-sidebar-btn.active { background: var(--dm-primary-soft); border-color: var(--dm-primary); color: var(--dm-primary); }
.user-chip { display: flex; align-items: center; gap: 6px; padding: 4px 10px 4px 4px; border-radius: 20px; background: var(--dm-surface); border: 1px solid var(--dm-border); font-size: 12px; font-weight: 600; color: var(--dm-text2); cursor: pointer; transition: all 0.15s var(--ease-out); }
.user-chip:hover { border-color: var(--dm-rose); background: var(--dm-rose-soft); }
.user-initial { width: 24px; height: 24px; border-radius: 50%; background: linear-gradient(135deg, var(--dm-primary), #818CF8); color: #fff; font-size: 11px; font-weight: 700; display: flex; align-items: center; justify-content: center; }

/* ===== 三栏布局 ===== */
.cockpit-grid { flex: 1; display: flex; overflow: hidden; }
.main-col { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.main-col-body { flex: 1; overflow: auto; padding: 16px 20px; display: flex; flex-direction: column; gap: 14px; }
.main-panel-section { flex: 6; min-height: 0; }
.sub-panel-section { flex: 4; min-height: 0; }
.sub-grid { display: grid; gap: 12px; height: 100%; }
.empty-state { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; color: var(--dm-muted); font-size: 13px; }
.empty-state p { margin-bottom: 14px; }
.primary-btn-sm { padding: 7px 16px; background: var(--dm-primary); color: #fff; border: none; border-radius: var(--radius-sm); font-size: 12px; font-weight: 600; font-family: var(--font-body); cursor: pointer; transition: all 0.15s var(--ease-out); }
.primary-btn-sm:hover { background: #4A4ED1; }
.query-area { padding: 10px 20px 14px; background: var(--dm-card); border-top: 1px solid var(--dm-border); }

/* P0#4: 数据源选择器 */
.ds-selector { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.ds-selector-label { font-size: 12px; font-weight: 600; color: var(--dm-text2); white-space: nowrap; }
.ds-select { padding: 4px 10px; font-size: 12px; font-family: var(--font-body); border: 1px solid var(--dm-border); border-radius: 6px; background: var(--dm-surface); color: var(--dm-text); cursor: pointer; outline: none; }
.ds-select:focus { border-color: var(--dm-primary); }

/* Main panel native layout (no PanelCard wrapper) */
.main-panel-wrapper { background: var(--dm-card); border-radius: var(--radius-lg); border: 2px solid var(--dm-primary); padding: 18px 22px 14px; }
.main-panel-header { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
.main-panel-name { font-family: var(--font-display); font-size: 17px; font-weight: 700; color: var(--dm-text); }
.main-panel-tag { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 10px; letter-spacing: 0.03em; }
.tag-hr { background: var(--dm-primary-soft); color: var(--dm-primary); }
.tag-crm { background: var(--dm-amber-soft); color: var(--dm-amber); }
.tag-finance { background: var(--dm-accent-soft); color: var(--dm-accent); }
.tag-erp { background: rgba(139,92,246,0.1); color: #8B5CF6; }
.primary-star { font-size: 11px; font-weight: 600; color: var(--dm-primary); margin-left: auto; }
.main-panel-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 8px; }
.main-panel-charts { margin-top: 16px; display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 14px; min-width: 0; }
.chart-card { background: var(--dm-surface); border-radius: var(--radius); padding: 12px 16px 4px; border: 1px solid var(--dm-border2); overflow: hidden; position: relative; }
.chart-container { position: relative; width: 100%; }
.chart-title-bar { font-size: 12px; font-weight: 700; color: var(--dm-text2); margin-bottom: 4px; }
.mini-chart { width: 100%; }
.panel-detail-link { margin-top: 10px; text-align: right; }
.detail-btn { padding: 6px 16px; background: var(--dm-primary); color: #fff; border: none; border-radius: var(--radius-sm); font-size: 12px; font-weight: 600; font-family: var(--font-body); cursor: pointer; transition: all 0.15s; }
.detail-btn:hover { background: #4A4ED1; box-shadow: 0 4px 12px rgba(91,95,227,0.25); }

/* Sub panels as cards */
.sub-panel-card { overflow: hidden;  background: var(--dm-card); border-radius: var(--radius-lg); border: 1px solid var(--dm-border); padding: 14px 16px; cursor: pointer; transition: all 0.2s; }
.sub-panel-card:hover { box-shadow: var(--shadow-card-hover); border-color: var(--dm-primary); }
.sub-panel-header { display: flex; align-items: center; gap: 6px; margin-bottom: 10px; }
.sub-panel-name { font-size: 14px; font-weight: 700; color: var(--dm-text); }
.sub-panel-tag { font-size: 10px; font-weight: 700; padding: 1px 7px; border-radius: 8px; background: var(--dm-surface); color: var(--dm-muted); letter-spacing: 0.03em; }
.sub-panel-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(90px, 1fr)); gap: 6px; }
.sub-panel-mini-chart { margin-top: 12px; padding-top: 8px; border-top: 1px solid var(--dm-border2); }

/* ===== 右侧侧边栏 ===== */
.side-panel { width: 440px; min-width: 440px; background: var(--dm-card); border-left: 1px solid var(--dm-border); display: flex; flex-direction: column; transition: all 0.25s var(--ease-out); }
.side-panel:not(.side-open) { width: 0; min-width: 0; overflow: hidden; opacity: 0; }
.side-tabs { display: flex; align-items: center; gap: 2px; padding: 6px 8px; border-bottom: 1px solid var(--dm-border); background: var(--dm-surface); }
.side-tab { display: flex; align-items: center; gap: 5px; padding: 7px 12px; border: none; background: none; border-radius: 8px; font-size: 12px; font-weight: 600; font-family: var(--font-body); color: var(--dm-muted); cursor: pointer; transition: all 0.15s var(--ease-out); }
.side-tab svg { width: 13px; height: 13px; }
.side-tab:hover { color: var(--dm-text2); background: var(--dm-border2); }
.side-tab.active { color: var(--dm-primary); background: var(--dm-primary-soft); }
.side-close { margin-left: auto; width: 28px; height: 28px; border-radius: 6px; border: none; background: none; color: var(--dm-muted); cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.15s var(--ease-out); }
.side-close svg { width: 13px; height: 13px; }
.side-close:hover { color: var(--dm-text); background: var(--dm-border2); }
.side-content { flex: 1; overflow: hidden; }

/* AI 终端 */
.terminal-pane { height: 100%; display: flex; flex-direction: column; }
.terminal-output { flex: 1; overflow-y: auto; padding: 16px 18px; background: var(--dm-card); font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace; font-size: 12.5px; line-height: 1.75; }
.terminal-empty { color: var(--dm-muted); padding: 20px; font-size: 12px; text-align: center; background: var(--dm-card); }
.term-line { margin-bottom: 4px; display: flex; gap: 6px; align-items: baseline; }
.term-time { color: var(--dm-muted); font-size: 10px; flex-shrink: 0; min-width: 52px; }
.term-prompt { flex-shrink: 0; }
.term-info { color: var(--dm-text2); } .term-info .term-prompt { color: var(--dm-primary); }
.term-success { color: #059669; } .term-success .term-prompt { color: #059669; }
.term-error { color: #DC2626; } .term-error .term-prompt { color: #DC2626; }
.term-warn { color: var(--dm-amber); } .term-warn .term-prompt { color: var(--dm-amber); }
.term-code { display: block; margin-top: 4px; padding: 6px 10px; background: var(--dm-surface); border-left: 2px solid var(--dm-border); color: var(--dm-text2); font-size: 11px; border-radius: 0 4px 4px 0; word-break: break-all; white-space: pre-wrap; }
.term-spinner { display: inline-block; width: 10px; height: 10px; border: 1.5px solid var(--dm-border); border-top-color: var(--dm-primary); border-radius: 50%; animation: spin 0.7s linear infinite; }
.term-elapsed { color: var(--dm-muted); font-size: 10px; margin-left: 8px; font-variant-numeric: tabular-nums; }
@keyframes spin { to { transform: rotate(360deg); } }

/* 报告 + 历史面板 */
.report-pane { height: 100%; overflow: auto; background: var(--dm-card); }
.side-report { padding: 16px; }
.side-report-meta { margin-bottom: 14px; }
.side-report-q { font-size: 13px; font-weight: 600; color: var(--dm-text); display: block; margin-bottom: 6px; }
.side-report-tag { display: inline-block; font-size: 10px; font-weight: 700; letter-spacing: 0.04em; padding: 2px 10px; border-radius: 12px; background: var(--dm-primary-soft); color: var(--dm-primary); }
.side-report-body { color: var(--dm-text2); font-size: 13px; }
.side-report-body :deep(h2) { color: var(--dm-text); font-size: 16px; border-bottom-color: var(--dm-border); }
.side-report-body :deep(h3) { color: var(--dm-text2); }
.side-report-body :deep(blockquote) { background: var(--dm-primary-soft); border-left-color: var(--dm-primary); }
.side-report-body :deep(table) { border-color: var(--dm-border2); }
.side-report-body :deep(th) { background: var(--dm-surface); color: var(--dm-muted); border-bottom-color: var(--dm-border); }
.side-report-body :deep(td) { color: var(--dm-text2); border-bottom-color: var(--dm-border2); }
.side-report-body :deep(code) { background: var(--dm-surface); color: var(--dm-primary); }
.side-report-body :deep(pre) { background: var(--dm-surface); }
/* P1#12: 历史搜索栏 */
.history-search-bar { display: flex; gap: 6px; padding: 4px 12px 8px; }
.history-search-input { flex: 1; padding: 6px 10px; font-size: 12px; font-family: var(--font-body); border: 1px solid var(--dm-border); border-radius: 6px; background: var(--dm-surface); color: var(--dm-text); outline: none; }
.history-search-input:focus { border-color: var(--dm-primary); }
.history-filter-select { width: 120px; padding: 6px 8px; font-size: 12px; font-family: var(--font-body); border: 1px solid var(--dm-border); border-radius: 6px; background: var(--dm-surface); color: var(--dm-text); cursor: pointer; outline: none; }
.history-pane { padding: 0; height: 100%; overflow: auto; background: var(--dm-card); }
.history-item { padding: 12px 14px; border-radius: var(--radius-sm); cursor: pointer; transition: all 0.15s var(--ease-out); margin: 0 4px 2px; }
.history-item:hover { background: var(--dm-surface); }
.history-q { font-size: 13px; color: var(--dm-text); font-weight: 500; margin-bottom: 6px; }
.history-meta { font-size: 11px; color: var(--dm-muted); display: flex; gap: 12px; }

/* P0#6: 移动端 */
@media (max-width: 900px) {
  .side-panel { width: 100vw; min-width: 100vw; position: fixed; right: 0; top: 0; z-index: 100; height: 100vh; border-radius: 0; }
  .side-panel:not(.side-open) { width: 0; min-width: 0; }
  .cockpit-grid { flex-direction: column; }
  .cockpit-top { padding: 0 12px; }
  .suggest-bar { display: none; }
  .main-col-body { padding: 8px; }
  .main-panel-kpis { grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); }
  .main-panel-charts { grid-template-columns: 1fr; }
  .sub-grid { grid-template-columns: 1fr !important; }
  .ds-selector { flex-direction: column; align-items: flex-start; }
}
.side-report-deep-badge { display: inline-block; font-size: 10px; font-weight: 700; letter-spacing: 0.04em; padding: 2px 8px; border-radius: 12px; background: #EEF2FF; color: #6366F1; margin-left: 6px; }
</style>
