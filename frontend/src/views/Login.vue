<template>
  <div class="login-page">
    <div class="login-bg">
      <div class="bg-gradient"></div>
      <div class="bg-particles">
        <span v-for="i in 12" :key="i" class="particle" :style="{
          left: `${(i * 31 + 17) % 100}%`, top: `${(i * 19 + 11) % 100}%`,
          animationDelay: `${i * 0.7}s`, animationDuration: `${10 + i * 1.3}s`,
          width: `${3 + (i % 3) * 2}px`, height: `${3 + (i % 3) * 2}px`,
          opacity: 0.10 + (i % 4) * 0.08,
        }" />
      </div>
    </div>
    <div class="login-card animate-in" role="main" aria-label="登录表单">
      <div class="login-brand">
        <div class="brand-icon">
          <svg viewBox="0 0 40 40" fill="none" aria-hidden="true">
            <rect x="3" y="3" width="14" height="14" rx="3.5" fill="currentColor" opacity="0.9" />
            <rect x="22" y="3" width="15" height="9" rx="3.5" fill="currentColor" opacity="0.45" />
            <rect x="22" y="16" width="7" height="21" rx="3.5" fill="currentColor" opacity="0.7" />
            <rect x="33" y="16" width="4" height="10" rx="2" fill="currentColor" opacity="0.35" />
            <rect x="3" y="22" width="14" height="15" rx="3.5" fill="currentColor" opacity="0.6" />
          </svg>
        </div>
        <h1 class="brand-name">DataMind</h1>
        <p class="brand-sub">AI 数据自助分析平台</p>
      </div>
      <form class="login-form" @submit.prevent="handleLogin" novalidate>
        <div class="field-group" :class="{ 'has-error': errors.username }">
          <label class="field-label" for="login-username">账户</label>
          <input id="login-username" v-model="form.username" type="text" placeholder="输入用户名" class="native-input"
            autocomplete="username" :aria-invalid="!!errors.username" :aria-describedby="errors.username ? 'err-username' : undefined" />
          <span v-if="errors.username" id="err-username" class="field-error" role="alert">{{ errors.username }}</span>
        </div>
        <div class="field-group" :class="{ 'has-error': errors.password }">
          <label class="field-label" for="login-password">密码</label>
          <input id="login-password" v-model="form.password" type="password" placeholder="输入密码" class="native-input"
            autocomplete="current-password" :aria-invalid="!!errors.password" :aria-describedby="errors.password ? 'err-password' : undefined" />
          <span v-if="errors.password" id="err-password" class="field-error" role="alert">{{ errors.password }}</span>
        </div>
        <button type="submit" class="login-btn" :disabled="loading" :aria-busy="loading">
          <span v-if="loading" class="btn-loading" aria-hidden="true"></span><span v-else>登录</span>
        </button>
      </form>
      <div class="login-demo">
        <span class="demo-label">Demo 账户</span>
        <div class="demo-accounts">
          <button class="demo-chip" @click="fillDemo('admin','admin123')">管理员</button>
          <button class="demo-chip" @click="fillDemo('emp1','emp1@0001')">技术总监(张伟)</button>
          <button class="demo-chip" @click="fillDemo('emp31','emp31@0001')">HR总监(王静)</button>
        </div>
        <p class="demo-hint">HR 同步用户密码规则：emp{工号}@{手机后4位}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const form = reactive({ username: 'admin', password: 'admin123' })
const errors = reactive({ username: '', password: '' })
function fillDemo(user: string, pass: string) { form.username = user; form.password = pass; errors.username = ''; errors.password = '' }
async function handleLogin() {
  errors.username = ''; errors.password = ''
  if (!form.username) { errors.username = '请输入用户名'; return }
  if (!form.password) { errors.password = '请输入密码'; return }
  loading.value = true
  try { await authStore.login(form.username, form.password); router.push(authStore.user?.role === 'admin' ? '/dashboard/overview' : '/analyst') }
  catch (e: any) {
    const detail = e?.response?.data?.detail
    if (e?.response?.status === 401) {
      errors.password = detail || '用户名或密码错误'
    } else if (e?.response?.status === 403) {
      errors.password = detail || '账户已被停用'
    } else {
      ElMessage.error(detail || '登录失败，请检查用户名和密码')
    }
  } finally { loading.value = false }
}
</script>

<style scoped>
.login-page { position: relative; width: 100vw; height: 100vh; display: flex; align-items: center; justify-content: center; overflow: hidden; background: var(--dm-surface); }
.login-bg { position: absolute; inset: 0; }
.bg-gradient {
  position: absolute; inset: 0;
  background:
    radial-gradient(ellipse 60% 40% at 20% 15%, rgba(91,95,227,0.04) 0%, transparent 50%),
    radial-gradient(ellipse 50% 35% at 80% 85%, rgba(0,201,167,0.03) 0%, transparent 50%),
    linear-gradient(180deg, var(--dm-surface) 0%, var(--dm-card) 50%, var(--dm-surface) 100%);
}
.particle { position: absolute; border-radius: 50%; background: var(--dm-primary); animation: particleRise linear infinite; }
@keyframes particleRise { 0% { transform: translateY(0) scale(1); opacity: 0; } 15% { opacity: 1; } 85% { opacity: 0.08; } 100% { transform: translateY(-160px) scale(0.2); opacity: 0; } }
.login-card { position: relative; z-index: 1; width: 420px; max-width: 94vw; background: var(--dm-card); border-radius: var(--radius-xl); box-shadow: var(--shadow-elevated), 0 0 0 1px rgba(0,0,0,0.04); padding: 44px 40px 36px; }
.login-brand { text-align: center; margin-bottom: 34px; }
.brand-icon { width: 48px; height: 48px; color: var(--dm-primary); margin: 0 auto 14px; }
.brand-name { font-family: var(--font-display); font-size: 26px; font-weight: 800; color: var(--dm-text); margin: 0 0 4px; letter-spacing: -0.025em; }
.brand-sub { font-size: 13px; color: var(--dm-muted); margin: 0; font-weight: 500; }
.login-form { display: flex; flex-direction: column; gap: 18px; }
.field-group { display: flex; flex-direction: column; gap: 6px; }
.field-label { font-size: 12px; font-weight: 600; color: var(--dm-text2); letter-spacing: 0.03em; }
.native-input { width: 100%; height: 46px; padding: 0 16px; background: var(--dm-surface); border: 1px solid var(--dm-border); border-radius: var(--radius-sm); font-size: 14px; font-family: var(--font-body); color: var(--dm-text); outline: none; transition: all 0.2s var(--ease-out); }
.native-input::placeholder { color: var(--dm-muted); }
.native-input:focus { border-color: var(--dm-primary); box-shadow: 0 0 0 3px var(--dm-primary-soft); background: var(--dm-card); }
/* P3#25: 内联错误 */
.field-group.has-error .field-label { color: var(--dm-rose); }
.field-group.has-error .native-input { border-color: var(--dm-rose); background: var(--dm-rose-soft); }
.field-error { font-size: 11px; font-weight: 600; color: var(--dm-rose); margin-top: 2px; }
.login-btn { width: 100%; height: 46px; margin-top: 4px; background: var(--dm-primary); color: #fff; border: none; border-radius: var(--radius-sm); font-size: 15px; font-weight: 600; font-family: var(--font-body); letter-spacing: 0.02em; cursor: pointer; transition: all 0.2s var(--ease-out); }
.login-btn:hover { background: #4A4ED1; box-shadow: 0 4px 12px rgba(91,95,227,0.35); transform: translateY(-1px); }
.login-btn:active { transform: translateY(0); }
.login-btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
.login-btn:focus-visible { outline: 2px solid var(--dm-primary); outline-offset: 2px; }
.btn-loading { display: inline-block; width: 18px; height: 18px; border: 2px solid rgba(255,255,255,0.25); border-top-color: #fff; border-radius: 50%; animation: spin 0.6s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.login-demo { margin-top: 24px; text-align: center; border-top: 1px solid var(--dm-border2); padding-top: 18px; }
.demo-label { font-size: 10px; font-weight: 700; color: var(--dm-muted); letter-spacing: 0.08em; text-transform: uppercase; display: block; margin-bottom: 10px; }
.demo-accounts { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; margin-bottom: 10px; }
.demo-chip { padding: 5px 14px; background: var(--dm-surface); border: 1px solid var(--dm-border); border-radius: 20px; font-size: 12px; font-family: var(--font-body); font-weight: 600; color: var(--dm-text2); cursor: pointer; transition: all 0.2s var(--ease-out); }
.demo-chip:hover { background: var(--dm-primary-soft); border-color: var(--dm-primary); color: var(--dm-primary); }
.demo-chip:focus-visible { outline: 2px solid var(--dm-primary); outline-offset: 2px; }
/* P0#1 补充: 密码规则提示 */
.demo-hint { font-size: 10px; color: var(--dm-muted); margin: 8px 0 0; font-weight: 400; }
</style>
