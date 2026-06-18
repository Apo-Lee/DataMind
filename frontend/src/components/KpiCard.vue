<template>
  <div class="kpi-card" :class="{ 'has-trend': trend, 'kpi-warn': isWarn, 'kpi-good': isGood }" @click="handleClick" role="button" tabindex="0" :aria-label="`${props.label}: ${formattedValue} ${props.unit || ''}`">
    <div class="kpi-value" :style="{ color: valueColor }">
      <span class="kpi-number">{{ formattedValue }}</span>
      <span v-if="props.unit" class="kpi-unit">{{ props.unit }}</span>
    </div>
    <div class="kpi-label">{{ props.label }}</div>
    <div v-if="props.trend" class="kpi-trend" :style="{ color: trendColor, background: trendBg }">
      {{ trendIcon }}
    </div>
    <div v-if="isWarn" class="kpi-warn-icon">⚠</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ label: string; value: string; unit?: string; trend?: string | null; sql_template?: string }>()
const emit = defineEmits<{ drill: [question: string] }>()

// V2.3: 数值格式化（大数字简化 + 颜色编码）
const formattedValue = computed(() => {
  const v = props.value
  if (v === '--' || v === undefined) return '--'
  const num = parseFloat(v.replace(/,/g, ''))
  if (isNaN(num)) return v
  if (num >= 100000000) return (num / 100000000).toFixed(1) + '亿'
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 10000 && props.unit === '元') return (num / 10000).toFixed(0) + '万'
  return v.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
})

// 颜色编码
const isWarn = computed(() => {
  const label = props.label
  const v = props.value
  if (v === '--') return false
  const num = parseFloat(v)
  if (isNaN(num)) return false
  // 迟到率/请假率 > 10% 警告
  if ((label.includes('迟到') || label.includes('请假')) && num > 10) return true
  // 离职 > 5 人 警告
  if (label.includes('离职') && num > 5) return true
  // 待审批 > 50 警告
  if (label.includes('待审批') && num > 50) return true
  // 超支 > 0 警告
  if (label.includes('超支') && num > 0) return true
  return false
})

const isGood = computed(() => {
  const label = props.label
  const v = props.value
  if (v === '--') return false
  const num = parseFloat(v)
  if (isNaN(num)) return false
  // 出勤率 > 90 好
  if (label.includes('出勤') && num >= 90) return true
  // 绩效 > 85 好
  if (label.includes('绩效') && num >= 85) return true
  // 赢单率 > 60 好
  if (label.includes('赢单') && num >= 60) return true
  return false
})

const valueColor = computed(() => {
  if (isWarn.value) return 'var(--dm-rose)'
  if (isGood.value) return 'var(--dm-accent)'
  return 'var(--dm-text)'
})

// 趋势
const config: Record<string, { color: string; bg: string; icon: string }> = {
  up:    { color: 'var(--dm-accent)', bg: 'var(--dm-accent-soft)', icon: '↑ 上升' },
  down:  { color: 'var(--dm-rose)',   bg: 'var(--dm-rose-soft)',   icon: '↓ 下降' },
  stable:{ color: 'var(--dm-muted)',  bg: '#F1F5F9',              icon: '→ 平稳' },
}
const fallback = { color: 'var(--dm-text)', bg: '#F1F5F9', icon: '' }
const trendColor = computed(() => config[props.trend || '']?.color || fallback.color)
const trendBg = computed(() => config[props.trend || '']?.bg || fallback.bg)
const trendIcon = computed(() => config[props.trend || '']?.icon || '')

// P2#15: 点击下钻
function handleClick() {
  if (props.sql_template) {
    emit('drill', `请分析「${props.label}」的详细分布和变化趋势`)
  }
}
</script>

<style scoped>
.kpi-card {
  min-width: 0;
  padding: 12px 14px;
  border-radius: var(--radius);
  background: var(--dm-surface);
  text-align: center;
  transition: all 0.2s var(--ease-out);
  border: 1px solid transparent;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-card);
  cursor: pointer;
}
.kpi-warn { border-color: rgba(244,63,94,0.15); background: rgba(244,63,94,0.03); }
.kpi-good { border-color: rgba(0,201,167,0.15); background: rgba(0,201,167,0.03); }

.kpi-warn-icon { position: absolute; top: 6px; right: 8px; font-size: 10px; opacity: 0.6; }

.kpi-value {
  font-family: var(--font-display);
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.15;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}
.kpi-number { }
.kpi-unit {
  font-size: 12px;
  font-weight: 500;
  opacity: 0.45;
  margin-left: 2px;
}
.kpi-label {
  font-size: 11px;
  color: var(--dm-muted);
  margin-top: 3px;
  font-weight: 500;
}
.kpi-trend {
  display: inline-block;
  margin-top: 4px;
  padding: 1px 7px;
  border-radius: 12px;
  font-size: 10px;
  font-weight: 700;
}
</style>
