<template>
  <div class="login-page">
    <!-- 氛围层：极光光晕 + 经纬网格 + 颗粒噪点 -->
    <div class="aurora aurora-a"></div>
    <div class="aurora aurora-b"></div>
    <div class="globe" aria-hidden="true">
      <svg viewBox="0 0 600 600">
        <defs>
          <radialGradient id="gcore" cx="50%" cy="45%" r="60%">
            <stop offset="0%" stop-color="rgba(120,190,255,0.16)" />
            <stop offset="100%" stop-color="rgba(120,190,255,0)" />
          </radialGradient>
        </defs>
        <circle cx="300" cy="300" r="240" fill="url(#gcore)" />
        <g fill="none" stroke="rgba(150,200,255,0.14)" stroke-width="1">
          <circle cx="300" cy="300" r="240" />
          <ellipse cx="300" cy="300" rx="240" ry="90" />
          <ellipse cx="300" cy="300" rx="240" ry="160" />
          <ellipse cx="300" cy="300" rx="160" ry="240" />
          <ellipse cx="300" cy="300" rx="90" ry="240" />
          <line x1="60" y1="300" x2="540" y2="300" />
          <line x1="300" y1="60" x2="300" y2="540" />
        </g>
      </svg>
    </div>
    <div class="grain" aria-hidden="true"></div>

    <div class="login-shell">
      <!-- 左：品牌叙事 -->
      <section class="brand-side">
        <div class="mark">
          <span class="mark-glyph">迈</span>
          <span class="mark-orbit"></span>
        </div>
        <p class="kicker">GLOBAL · GEO OPERATIONS</p>
        <h1 class="brand-title"><em>GEO</em><br />运营系统</h1>
        <p class="brand-desc">面向全球市场的生成式引擎优化运营中枢<br />查词监测 · 排名洞察 · 内容生产与发布一体化</p>
        <ul class="brand-points">
          <li><i></i>多引擎品牌推荐排名追踪</li>
          <li><i></i>数据驱动的内容策略决策</li>
          <li><i></i>严谨的团队级权限与数据隔离</li>
        </ul>
      </section>

      <!-- 右：登录卡 -->
      <section class="login-card">
        <div class="card-head">
          <h2>欢迎登录</h2>
          <p>请使用您的运营账号进入工作台</p>
        </div>

        <el-form class="login-form" :model="form" @submit.prevent="handleLogin">
          <label class="field">
            <span class="field-label">账号</span>
            <el-input v-model="form.username" placeholder="请输入用户名" size="large" autocomplete="username">
              <template #prefix><span class="ic">◎</span></template>
            </el-input>
          </label>

          <label class="field">
            <span class="field-label">密码</span>
            <el-input v-model="form.password" placeholder="请输入密码" size="large" show-password
                      autocomplete="current-password" @keyup.enter="handleLogin">
              <template #prefix><span class="ic">✷</span></template>
            </el-input>
          </label>

          <button type="button" class="login-btn" :class="{ loading }" :disabled="loading" @click="handleLogin">
            <span v-if="!loading">进入系统</span>
            <span v-else class="btn-loading"><i></i>登录中…</span>
          </button>
        </el-form>

        <p class="card-foot">内部系统 · 请勿外传</p>
      </section>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import api from '../api'
import { resetAuthState } from '../utils/auth'

const router = useRouter()
const loading = ref(false)

const form = reactive({
  username: '',
  password: ''
})

async function handleLogin() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const data = await api.login(form.username, form.password)
    const role = data.role || 'operator'
    localStorage.setItem('geo_user', data.username || form.username)
    localStorage.setItem('geo_is_super', role === 'super_admin' ? '1' : '0')
    localStorage.setItem('geo_role', role)
    localStorage.setItem('geo_permissions', JSON.stringify(data.permissions || []))
    resetAuthState()
    ElMessage.success('登录成功')
    router.push('/dashboard/home')
  } catch (err) {
    ElMessage.error(err?.response?.data?.error || err.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  --ink: #070b16;
  --ink-2: #0c1326;
  --line: rgba(150, 190, 255, 0.14);
  --accent: #6fb4ff;
  --accent-2: #8f7bff;
  --gold: #e6c98a;
  --text: #eaf1ff;
  --text-dim: rgba(214, 226, 250, 0.62);

  min-height: 100vh;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 20px;
  background:
    radial-gradient(120% 90% at 82% 12%, #14224a 0%, transparent 55%),
    radial-gradient(120% 100% at 8% 92%, #101a38 0%, transparent 55%),
    linear-gradient(160deg, var(--ink) 0%, var(--ink-2) 100%);
  color: var(--text);
  font-feature-settings: "tnum" 1;
}

/* —— 氛围层 —— */
.aurora {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  opacity: 0.55;
  pointer-events: none;
  animation: drift 18s ease-in-out infinite alternate;
}
.aurora-a { width: 46vw; height: 46vw; top: -12vw; right: -8vw;
  background: radial-gradient(circle, rgba(111,180,255,0.55), transparent 65%); }
.aurora-b { width: 42vw; height: 42vw; bottom: -14vw; left: -10vw;
  background: radial-gradient(circle, rgba(143,123,255,0.45), transparent 65%);
  animation-delay: -6s; }

.globe {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  opacity: 0.9;
}
.globe svg { width: min(78vh, 720px); height: min(78vh, 720px); transform: translateX(6%); animation: spin 120s linear infinite; }

.grain {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.5;
  background-image: radial-gradient(rgba(255, 255, 255, 0.05) 0.5px, transparent 0.6px);
  background-size: 3px 3px;
  mix-blend-mode: overlay;
}

/* —— 布局 —— */
.login-shell {
  position: relative;
  z-index: 2;
  width: 100%;
  max-width: 1000px;
  display: grid;
  grid-template-columns: 1.05fr 0.95fr;
  align-items: stretch;
  gap: 0;
  border-radius: 22px;
  overflow: hidden;
  border: 1px solid rgba(150, 190, 255, 0.12);
  background: rgba(10, 16, 34, 0.5);
  backdrop-filter: blur(22px) saturate(120%);
  -webkit-backdrop-filter: blur(22px) saturate(120%);
  box-shadow: 0 40px 120px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

/* —— 品牌侧 —— */
.brand-side {
  padding: 54px 48px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 18px;
  position: relative;
  background:
    linear-gradient(180deg, rgba(111, 180, 255, 0.06), transparent 40%),
    linear-gradient(140deg, rgba(143, 123, 255, 0.08), transparent 60%);
  border-right: 1px solid rgba(150, 190, 255, 0.08);
}

.mark { position: relative; width: 58px; height: 58px; margin-bottom: 8px; }
.mark-glyph {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 26px; font-weight: 800; color: #0a1024;
  border-radius: 16px;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  box-shadow: 0 10px 26px rgba(111, 180, 255, 0.4);
}
.mark-orbit {
  position: absolute; inset: -8px;
  border: 1px solid rgba(230, 201, 138, 0.55);
  border-radius: 20px;
  transform: rotate(12deg);
  opacity: 0.7;
}

.kicker {
  font-size: 12px;
  letter-spacing: 4px;
  color: var(--gold);
  font-weight: 600;
}
.brand-title {
  font-size: clamp(30px, 3.2vw, 44px);
  line-height: 1.16;
  font-weight: 800;
  letter-spacing: 0.5px;
  color: var(--text);
}
.brand-title em {
  font-style: normal;
  background: linear-gradient(90deg, var(--accent), var(--gold));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.brand-desc {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-dim);
  margin-top: 2px;
}
.brand-points {
  list-style: none;
  margin-top: 14px;
  display: grid;
  gap: 11px;
}
.brand-points li {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13.5px;
  color: rgba(224, 233, 252, 0.82);
}
.brand-points i {
  width: 6px; height: 6px; border-radius: 50%;
  background: linear-gradient(135deg, var(--accent), var(--gold));
  box-shadow: 0 0 10px rgba(111, 180, 255, 0.7);
  flex: none;
}

/* —— 登录卡 —— */
.login-card {
  padding: 54px 46px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.01));
}
.card-head h2 { font-size: 24px; font-weight: 700; letter-spacing: 1px; }
.card-head p { margin-top: 6px; font-size: 13px; color: var(--text-dim); }

.login-form { margin-top: 26px; display: grid; gap: 16px; }
.field { display: block; }
.field-label {
  display: block;
  font-size: 12px;
  letter-spacing: 1px;
  color: rgba(203, 216, 244, 0.7);
  margin-bottom: 7px;
}
.ic { color: var(--accent); font-size: 13px; }

/* Element Plus 输入框：暗色玻璃化（走 EP CSS 变量，避免被默认白底覆盖） */
.login-card :deep(.el-input) {
  --el-input-bg-color: transparent;
  --el-fill-color-blank: transparent;
  --el-input-text-color: var(--text);
  --el-input-border-color: rgba(150, 190, 255, 0.16);
  --el-input-hover-border-color: rgba(150, 190, 255, 0.34);
  --el-input-focus-border-color: var(--accent);
  --el-input-placeholder-color: rgba(190, 205, 235, 0.42);
  --el-color-primary: var(--accent);
}
.login-card :deep(.el-input__wrapper) {
  background-color: rgba(255, 255, 255, 0.045) !important;
  background-image: none !important;
  border-radius: 12px;
  box-shadow: 0 0 0 1px rgba(150, 190, 255, 0.16) inset !important;
  padding: 8px 14px;
  transition: box-shadow 0.2s ease, background-color 0.2s ease;
}
.login-card :deep(.el-input__wrapper:hover) {
  background-color: rgba(255, 255, 255, 0.07) !important;
  box-shadow: 0 0 0 1px rgba(150, 190, 255, 0.34) inset !important;
}
.login-card :deep(.el-input__wrapper.is-focus) {
  background-color: rgba(111, 180, 255, 0.08) !important;
  box-shadow: 0 0 0 1px var(--accent) inset, 0 0 0 3px rgba(111, 180, 255, 0.18) !important;
}
.login-card :deep(.el-input__inner) {
  color: var(--text);
  height: 30px;
  font-size: 15px;
  letter-spacing: 0.5px;
  -webkit-text-fill-color: var(--text);
}
.login-card :deep(.el-input__inner:-webkit-autofill) {
  -webkit-text-fill-color: var(--text);
  transition: background-color 9999s ease-out;
}
.login-card :deep(.el-input__password),
.login-card :deep(.el-input__clear) { color: rgba(190, 205, 235, 0.6); }

/* CTA */
.login-btn {
  margin-top: 8px;
  width: 100%;
  height: 50px;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-size: 15.5px;
  font-weight: 700;
  letter-spacing: 4px;
  color: #0a1024;
  background: linear-gradient(100deg, var(--accent) 0%, #a9d0ff 40%, var(--gold) 120%);
  background-size: 180% 100%;
  background-position: 0% 50%;
  box-shadow: 0 14px 34px rgba(111, 180, 255, 0.32);
  transition: background-position 0.5s ease, transform 0.12s ease, box-shadow 0.2s ease;
}
.login-btn:hover:not(:disabled) {
  background-position: 100% 50%;
  box-shadow: 0 18px 44px rgba(230, 201, 138, 0.34);
}
.login-btn:active:not(:disabled) { transform: translateY(1px) scale(0.995); }
.login-btn:disabled { cursor: default; opacity: 0.85; }
.btn-loading { display: inline-flex; align-items: center; gap: 9px; letter-spacing: 2px; }
.btn-loading i {
  width: 15px; height: 15px; border-radius: 50%;
  border: 2px solid rgba(10, 16, 36, 0.35);
  border-top-color: #0a1024;
  animation: spin 0.7s linear infinite;
}

.card-foot {
  margin-top: 26px;
  text-align: center;
  font-size: 11.5px;
  letter-spacing: 0.5px;
  color: rgba(190, 205, 235, 0.4);
}

/* —— 动画 —— */
@keyframes drift {
  from { transform: translate3d(0, 0, 0) scale(1); }
  to   { transform: translate3d(2vw, 3vh, 0) scale(1.08); }
}
@keyframes spin { to { transform: rotate(360deg); } }
.globe svg { transform-origin: 50% 50%; }

@media (prefers-reduced-motion: reduce) {
  .aurora, .globe svg, .btn-loading i { animation: none; }
}

/* —— 响应式 —— */
@media (max-width: 860px) {
  .login-shell { grid-template-columns: 1fr; max-width: 460px; }
  .brand-side {
    padding: 40px 34px 30px;
    border-right: none;
    border-bottom: 1px solid rgba(150, 190, 255, 0.08);
  }
  .brand-points { display: none; }
  .login-card { padding: 34px 34px 40px; }
  .globe svg { transform: none; }
}
@media (max-width: 420px) {
  .brand-side { padding: 30px 24px 24px; }
  .login-card { padding: 28px 24px 34px; }
}
</style>
