<template>
  <div class="query-bar">
    <div class="query-input-wrap">
      <svg class="query-icon" viewBox="0 0 24 24" fill="none">
        <circle cx="11" cy="11" r="6" stroke="currentColor" stroke-width="1.5" />
        <path d="M19 19l-3.5-3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
      </svg>
      <input
        v-model="question"
        type="text"
        :placeholder="placeholder"
        class="query-input"
        :disabled="loading"
        @keyup.enter="handleSend"
      />
      <div class="query-shortcut" v-if="!loading">
        <kbd>&#8629;</kbd>
      </div>
    </div>

    <!-- 深度分析开关 -->
    <label class="deep-analyze-toggle" :class="{ active: deepAnalyze }" title="启用深度分析将执行完整的数据分析与可视化">
      <input type="checkbox" v-model="deepAnalyze" :disabled="loading" />
      <svg class="da-icon" viewBox="0 0 16 16" fill="none">
        <path d="M8 1v14M1 8h14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        <circle cx="8" cy="8" r="2.5" fill="currentColor"/>
      </svg>
      <span class="da-label">深度</span>
    </label>

    <!-- P0#5: 取消按钮 -->
    <button v-if="loading" class="cancel-btn" @click="handleCancel">
      取消
    </button>
    <button v-else class="send-btn" :class="{ active: question.trim() }" :disabled="!question.trim()" @click="handleSend">
      <span>分析</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ loading?: boolean; placeholder?: string }>()
const emit = defineEmits<{ send: [payload: { question: string; deepAnalyze: boolean }]; cancel: [] }>()
const question = ref('')
const deepAnalyze = ref(false)

function handleSend() {
  const q = question.value.trim()
  if (!q) return
  emit('send', { question: q, deepAnalyze: deepAnalyze.value })
  question.value = ''
}

function handleCancel() {
  emit('cancel')
}
</script>

<style scoped>
.query-bar {
  display: flex;
  gap: 10px;
  align-items: center;
}
.query-input-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  background: var(--dm-card);
  border: 1.5px solid var(--dm-border);
  border-radius: var(--radius);
  padding: 0 6px;
  transition: all 0.2s var(--ease-out);
}
.query-input-wrap:focus-within {
  border-color: var(--dm-primary);
  box-shadow: 0 0 0 3px var(--dm-primary-soft);
}
.query-icon {
  width: 18px;
  height: 18px;
  color: var(--dm-muted);
  margin-left: 10px;
  flex-shrink: 0;
}
.query-input {
  flex: 1;
  height: 46px;
  border: none;
  background: none;
  outline: none;
  font-size: 14px;
  font-family: var(--font-body);
  color: var(--dm-text);
  padding: 0 10px;
}
.query-input::placeholder {
  color: var(--dm-muted);
}
.query-input:disabled {
  opacity: 0.5;
}
.query-shortcut {
  padding: 0 6px;
}
.query-shortcut kbd {
  font-size: 11px;
  font-weight: 600;
  color: var(--dm-muted);
  background: var(--dm-surface);
  border: 1px solid var(--dm-border);
  border-radius: 4px;
  padding: 1px 6px;
}
/* 深度分析开关 */
.deep-analyze-toggle {
  display: flex;
  align-items: center;
  gap: 5px;
  height: 36px;
  padding: 0 12px;
  border: 1.5px solid var(--dm-border);
  border-radius: var(--radius);
  cursor: pointer;
  transition: all 0.2s var(--ease-out);
  user-select: none;
  background: var(--dm-card);
  flex-shrink: 0;
}
.deep-analyze-toggle:hover {
  border-color: var(--dm-primary);
}
.deep-analyze-toggle.active {
  border-color: var(--dm-primary);
  background: var(--dm-primary-soft);
}
.deep-analyze-toggle input {
  display: none;
}
.da-icon {
  width: 16px;
  height: 16px;
  color: var(--dm-muted);
  flex-shrink: 0;
}
.deep-analyze-toggle.active .da-icon {
  color: var(--dm-primary);
}
.da-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--dm-muted);
  white-space: nowrap;
}
.deep-analyze-toggle.active .da-label {
  color: var(--dm-primary);
}
.send-btn {
  height: 48px;
  padding: 0 24px;
  background: var(--dm-surface);
  color: var(--dm-muted);
  border: 1.5px solid var(--dm-border);
  border-radius: var(--radius);
  font-size: 14px;
  font-weight: 700;
  font-family: var(--font-body);
  cursor: pointer;
  transition: all 0.2s var(--ease-out);
  white-space: nowrap;
}
.send-btn.active {
  background: var(--dm-primary);
  color: #fff;
  border-color: var(--dm-primary);
}
.send-btn.active:hover {
  background: #4A4ED1;
  box-shadow: 0 4px 12px rgba(91,95,227,0.3);
}
.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
/* P0#5: 取消按钮 */
.cancel-btn {
  height: 48px;
  padding: 0 24px;
  background: var(--dm-rose-soft);
  color: var(--dm-rose);
  border: 1.5px solid var(--dm-rose);
  border-radius: var(--radius);
  font-size: 14px;
  font-weight: 700;
  font-family: var(--font-body);
  cursor: pointer;
  transition: all 0.2s var(--ease-out);
  white-space: nowrap;
}
.cancel-btn:hover {
  background: var(--dm-rose);
  color: #fff;
}
</style>