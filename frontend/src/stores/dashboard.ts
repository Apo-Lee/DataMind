import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { dashboardApi } from '@/api/dashboard'

export const useDashboardStore = defineStore('dashboard', () => {
  const panels = ref<any[]>([])
  const mainPanelIndex = ref(0)
  const loading = ref(false)
  const lastFetchedAt = ref(0)  // P1#11: 数据新鲜度追踪

  async function fetchPanels() {
    loading.value = true
    try {
      const resp = await dashboardApi.getPanels()
      panels.value = resp.data.panels
      const primaryIdx = panels.value.findIndex((p: any) => p.is_primary)
      mainPanelIndex.value = primaryIdx >= 0 ? primaryIdx : 0
      lastFetchedAt.value = Date.now()
    } finally { loading.value = false }
  }

  function setMainPanel(index: number) { mainPanelIndex.value = index }

  async function refreshPanel(datasourceId: string) {
    try {
      // P0-6: 保存原有的 is_primary 值，刷新后恢复
      const idx = panels.value.findIndex((p: any) => p.datasource_id === datasourceId)
      const wasPrimary = idx >= 0 ? panels.value[idx].is_primary : false
      const resp = await dashboardApi.refreshPanel(datasourceId, wasPrimary)
      if (idx >= 0) panels.value[idx] = resp.data
    } catch {}
  }

  const mainPanel = computed(() => panels.value[mainPanelIndex.value] || null)
  const subPanels = computed(() => panels.value.filter((_: any, i: number) => i !== mainPanelIndex.value))

  return { panels, mainPanelIndex, loading, lastFetchedAt, fetchPanels, setMainPanel, refreshPanel, mainPanel, subPanels }
})
