<template>
  <div class="dashboard-layout" :class="{
    'is-mobile': isMobile,
    'drawer-open': drawerOpen,
    'is-collapsed': collapsed && !isMobile,
    'is-collapsed-hover': collapsed && !isMobile && sidebarHover,
  }">
    <!-- 移动端遮罩：点击关闭抽屉 -->
    <div v-if="isMobile && drawerOpen" class="drawer-backdrop" @click="drawerOpen = false"></div>
    <aside
      class="dashboard-sidebar"
      :class="{ 'is-open': drawerOpen, 'collapsed': collapsed && !isMobile, 'is-hovered': sidebarHover && collapsed && !isMobile }"
      @mouseenter="onSidebarEnter"
      @mouseleave="onSidebarLeave"
    >
      <!-- 折叠按钮固定在 sidebar 右上角(不再嵌入 brand) -->
      <button
        v-if="!isMobile"
        class="collapse-btn"
        :title="collapsed ? '展开侧栏' : '收起侧栏'"
        @click="toggleCollapse"
      >
        <el-icon :size="14"><component :is="collapsed ? Expand : Fold" /></el-icon>
      </button>

      <div class="sidebar-brand">
        <div v-if="!collapsed || isMobile" class="brand-text">
          <p class="brand-mini">MEDIA OPS</p>
          <h1>GEO 运营系统</h1>
        </div>
        <div v-else class="brand-mini-icon">GEO</div>
      </div>

      <nav class="sidebar-nav" @click="onNavClick">
        <el-tooltip content="首页" placement="right" :disabled="!collapsed || isMobile || sidebarHover" :show-after="200">
          <RouterLink v-if="canAccess('home')" to="/dashboard/home" class="nav-item">
            <el-icon><House /></el-icon>
            <span>首页</span>
          </RouterLink>
        </el-tooltip>
        <el-tooltip content="客户管理" placement="right" :disabled="!collapsed || isMobile || sidebarHover" :show-after="200">
          <RouterLink v-if="canAccess('accounts')" to="/dashboard/accounts" class="nav-item">
            <el-icon><User /></el-icon>
            <span>客户管理</span>
          </RouterLink>
        </el-tooltip>
        <el-tooltip content="查词管理" placement="right" :disabled="!collapsed || isMobile || sidebarHover" :show-after="200">
          <RouterLink v-if="canAccess('keyword-search')" to="/dashboard/keyword-search" class="nav-item">
            <el-icon><Search /></el-icon>
            <span>查词管理</span>
          </RouterLink>
        </el-tooltip>
        <el-tooltip content="排名分析" placement="right" :disabled="!collapsed || isMobile || sidebarHover" :show-after="200">
          <RouterLink v-if="canAccess('ranking-analysis')" to="/dashboard/ranking-analysis" class="nav-item">
            <el-icon><TrendCharts /></el-icon>
            <span>排名分析</span>
          </RouterLink>
        </el-tooltip>
        <el-tooltip content="GEO拓词" placement="right" :disabled="!collapsed || isMobile || sidebarHover" :show-after="200">
          <RouterLink v-if="canAccess('home')" to="/dashboard/geo-expansion" class="nav-item">
            <el-icon><MagicStick /></el-icon>
            <span>GEO拓词</span>
          </RouterLink>
        </el-tooltip>

        <!-- 效果分析模块（独立系统页，新窗口打开） -->
        <div class="nav-section-divider" v-if="canAccess('publish') || canAccess('home')"></div>
        <el-tooltip content="效果分析" placement="right" :disabled="!collapsed || isMobile || sidebarHover" :show-after="200">
          <a v-if="canAccess('publish') || canAccess('home')" href="/effect-analysis" target="_blank" rel="noopener" class="nav-item nav-item-highlight nav-item-teal">
            <el-icon><DataAnalysis /></el-icon>
            <span>效果分析</span>
          </a>
        </el-tooltip>

        <!-- 内容发布模块 -->
        <div class="nav-section-divider" v-if="canAccess('publish')"></div>
        <el-tooltip content="内容发布" placement="right" :disabled="!collapsed || isMobile || sidebarHover" :show-after="200">
          <RouterLink v-if="canAccess('publish')" to="/publish/customers" class="nav-item nav-item-highlight">
            <el-icon><Promotion /></el-icon>
            <span>内容发布</span>
          </RouterLink>
        </el-tooltip>

        <el-tooltip content="权限管理" placement="right" :disabled="!collapsed || isMobile || sidebarHover" :show-after="200">
          <RouterLink v-if="canAccess('admin-users') || canAccess('roles')" to="/dashboard/admin-users" class="nav-item">
            <el-icon><UserFilled /></el-icon>
            <span>权限管理</span>
          </RouterLink>
        </el-tooltip>
        <el-tooltip content="系统设置" placement="right" :disabled="!collapsed || isMobile || sidebarHover" :show-after="200">
          <RouterLink v-if="canAccess('settings')" to="/dashboard/settings" class="nav-item">
            <el-icon><Setting /></el-icon>
            <span>系统设置</span>
          </RouterLink>
        </el-tooltip>
      </nav>

      <div class="sidebar-footer">
        <el-popover
          placement="top-start"
          :width="200"
          trigger="click"
        >
          <template #reference>
            <div class="user-card" :title="collapsed && !isMobile ? username : ''">
              <div class="user-avatar">{{ avatarLetter }}</div>
              <span v-if="!collapsed || isMobile" class="user-name">{{ username }}</span>
            </div>
          </template>
          <div class="user-popover">
            <div class="pop-user-info">
              <div class="pop-avatar">{{ avatarLetter }}</div>
              <div class="pop-name">{{ username }}</div>
            </div>
            <div class="pop-actions">
              <div class="pop-action" @click="pwDialogVisible = true">修改密码</div>
              <div class="pop-action pop-action-danger" @click="handleLogout">退出登录</div>
            </div>
          </div>
        </el-popover>
      </div>

      <el-dialog v-model="pwDialogVisible" title="修改密码" width="min(380px, 90vw)" append-to-body>
        <el-form label-width="70px">
          <el-form-item label="原密码">
            <el-input v-model="pwForm.old" show-password />
          </el-form-item>
          <el-form-item label="新密码">
            <el-input v-model="pwForm.new1" show-password placeholder="至少 8 位" />
          </el-form-item>
          <el-form-item label="确认密码">
            <el-input v-model="pwForm.new2" show-password />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="pwDialogVisible=false">取消</el-button>
          <el-button type="primary" :loading="pwSaving" @click="submitPwChange">确定</el-button>
        </template>
      </el-dialog>
    </aside>

    <main class="dashboard-main">
      <div class="dashboard-main-header">
        <button v-if="isMobile" class="burger" @click="drawerOpen = !drawerOpen" aria-label="切换侧边栏">
          <el-icon><Menu /></el-icon>
        </button>
        <div class="header-title">
          <h2>{{ pageTitle }}</h2>
          <p>{{ pageDesc }}</p>
        </div>
      </div>

      <div class="dashboard-main-body">
        <router-view />
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, ref, reactive, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { House, User, UserFilled, MagicStick, Setting, Menu, Fold, Expand, Promotion, Search, TrendCharts, DataAnalysis } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import { resetAuthState } from '../utils/auth'

const router = useRouter()
const route = useRoute()

// ── 移动端抽屉侧边栏 ──
const MOBILE_BREAKPOINT = 900
const isMobile = ref(typeof window !== 'undefined' && window.innerWidth < MOBILE_BREAKPOINT)
const drawerOpen = ref(false)

// ── 桌面端折叠 ──
const collapsed = ref(localStorage.getItem('dash_sidebar_collapsed') === '1')
function toggleCollapse() {
  collapsed.value = !collapsed.value
  try { localStorage.setItem('dash_sidebar_collapsed', collapsed.value ? '1' : '0') } catch { /* ignore */ }
}

// 折叠状态下,鼠标悬浮 sidebar 自动浮出展开;移出后收回
const sidebarHover = ref(false)
let hoverLeaveTimer = null
function onSidebarEnter() {
  if (hoverLeaveTimer) { clearTimeout(hoverLeaveTimer); hoverLeaveTimer = null }
  if (collapsed.value && !isMobile.value) sidebarHover.value = true
}
function onSidebarLeave() {
  // 短暂延迟收回,避免鼠标从内容区误碰边缘时频繁抖动
  if (hoverLeaveTimer) clearTimeout(hoverLeaveTimer)
  hoverLeaveTimer = setTimeout(() => { sidebarHover.value = false }, 120)
}
function onResize() {
  const wasMobile = isMobile.value
  isMobile.value = window.innerWidth < MOBILE_BREAKPOINT
  if (!isMobile.value && wasMobile) drawerOpen.value = false  // 恢复桌面时关闭
}
function onNavClick(e) {
  // 点击 nav 内任意 a / RouterLink 都自动收起抽屉
  if (isMobile.value && e.target.closest('a')) drawerOpen.value = false
}
onMounted(() => window.addEventListener('resize', onResize))
onBeforeUnmount(() => window.removeEventListener('resize', onResize))
// 路由切换也关掉
watch(() => route.fullPath, () => { drawerOpen.value = false })

const username = computed(() => localStorage.getItem('geo_user') || '运营同学')
const userRole = computed(() => localStorage.getItem('geo_role') || 'operator')
const isSuper = computed(() => userRole.value === 'super_admin')
const userPages = computed(() => {
  try { return JSON.parse(localStorage.getItem('geo_pages') || '[]') } catch { return [] }
})
const avatarLetter = computed(() => (username.value || '?')[0].toUpperCase())

// 角色化权限：super_admin 默认全开；其余按 session.pages 数组（来自 role.pages）
function canAccess(pageKey) {
  if (isSuper.value) return true
  return userPages.value.includes(pageKey)
}

// 内容发布 Hub 入口：只要任一发布相关 page key 在 session.pages 里就显示
const PUBLISH_PAGE_KEYS = ['publish-home', 'customers', 'knowledge',
  'content-templates', 'content-history',
  'publish-article', 'publish-batch', 'publish-orders', 'publish-schedule']
const canAccessPublishHub = computed(() => {
  if (isSuper.value) return true
  return PUBLISH_PAGE_KEYS.some(k => userPages.value.includes(k))
})

const pwDialogVisible = ref(false)
const pwSaving = ref(false)
const pwForm = reactive({ old: '', new1: '', new2: '' })

async function submitPwChange() {
  if (!pwForm.old) { ElMessage.warning('请输入原密码'); return }
  if (pwForm.new1.length < 8) { ElMessage.warning('新密码至少 8 位'); return }
  if (pwForm.new1 !== pwForm.new2) { ElMessage.warning('两次密码不一致'); return }
  pwSaving.value = true
  try {
    await api.changePassword(pwForm.old, pwForm.new1)
    ElMessage.success('密码修改成功，请重新登录')
    pwDialogVisible.value = false
    await api.logout()
    resetAuthState()
    localStorage.removeItem('geo_user')
    localStorage.removeItem('geo_is_super')
    window.location.href = '/login'
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '修改失败')
  } finally { pwSaving.value = false }
}

const pageTitle = computed(() => {
  if (route.path.includes('/dashboard/accounts')) return '客户管理'
  if (route.path.match(/\/dashboard\/keyword-search\/\d/)) return '查词详情'
  if (route.path.includes('/dashboard/knowledge')) return '知识库管理'
  if (route.path.includes('/dashboard/keyword-search')) return '查词管理'
  if (route.path.includes('/dashboard/effect-analysis')) return '效果分析'
  if (route.path.includes('/dashboard/ranking-analysis')) return '排名分析'
  if (route.path.includes('/dashboard/citation-analysis')) return '引用源分析'
  if (route.path.includes('/dashboard/quote')) return '报价管理'
  if (route.path.includes('/dashboard/scheduled-tasks')) return '定时任务'
  if (route.path.includes('/dashboard/settings')) return '系统设置'
  if (route.path.includes('/dashboard/admin-users')) return '权限管理'
  if (route.path.includes('/dashboard/roles')) return '权限管理'
  if (route.path.includes('/dashboard/invites')) return '外部邀请码'
  if (route.path.includes('/dashboard/keyword-expand')) return 'GEO 拓词'
  return '首页'
})

const pageDesc = computed(() => {
  if (route.path.includes('/dashboard/accounts')) return '维护客户账号信息，后续将作为报告生成与分析的基础数据源。'
  if (route.path.match(/\/dashboard\/keyword-search\/\d/)) return '执行关键词查询，查看各 AI 平台的搜索结果与品牌露出情况。'
  if (route.path.includes('/dashboard/knowledge')) return '为付费客户维护品牌知识库：上传素材、生成与管理知识库版本。'
  if (route.path.includes('/dashboard/keyword-search')) return '查看客户查词概况，点击进入详细查词管理。'
  if (route.path.includes('/dashboard/effect-analysis')) return '跨客户的效果总览：上榜率、当天上榜词、掉线词预警、排名波动与客户健康度。'
  if (route.path.includes('/dashboard/ranking-analysis')) return '从查词结果提取品牌并计算排名；也可手动填写提示词与品牌新建分析，结果支持 Excel / CSV 导出。'
  if (route.path.includes('/dashboard/citation-analysis')) return '抓取引用源网页内容，分析发布日期、内容类型与网站类型。'
  if (route.path.includes('/dashboard/quote')) return '基于五维评分生成非标客户报价。'
  if (route.path.includes('/dashboard/scheduled-tasks')) return '统一管理所有客户的定时查词、定时排名任务。'
  if (route.path.includes('/dashboard/settings')) return '维护搜索 API、分析模型与系统配置。'
  if (route.path.includes('/dashboard/admin-users')) return '统一管理账号与团队、角色与页面权限。'
  if (route.path.includes('/dashboard/roles')) return '统一管理账号与团队、角色与页面权限。'
  if (route.path.includes('/dashboard/invites')) return '生成外部邀请码，让客户/合作方填关键词后自动得到一份带密钥分享的竞争分析报告。'
  if (route.path.includes('/dashboard/keyword-expand')) return '上传客户资料 → AI 生成提示词 → 导出 Excel 或导入到客户提示词。'
  return '系统总览与快捷操作入口'
})

async function handleLogout() {
  try { await api.logout() } catch (_) {}
  resetAuthState()
  localStorage.removeItem('geo_token')
  localStorage.removeItem('geo_user')
  localStorage.removeItem('geo_is_super')
  localStorage.removeItem('geo_role')
  localStorage.removeItem('geo_permissions')
  window.location.href = '/login'
}
</script>

<style scoped>
.dashboard-layout {
  min-height: 100vh;
  /* 侧边栏已 fixed，主内容区只需左边距 */
  margin-left: 220px;
  background: #f3f6fb;
  transition: margin-left .28s cubic-bezier(.22, 1, .36, 1);
}
.dashboard-layout.is-collapsed { margin-left: 64px; }
.dashboard-layout.is-collapsed-hover { margin-left: 220px; }

.dashboard-sidebar {
  background: radial-gradient(circle at top, rgba(20, 135, 219, 0.22), transparent 45%), linear-gradient(180deg, #111827 0%, #0f1f37 55%, #102a46 100%);
  color: #fff;
  padding: 28px 16px 18px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  /* 固定到视口左侧:右侧内容滚动时左侧导航不跟动 */
  position: fixed;
  top: 0;
  left: 0;
  width: 220px;
  height: 100vh;
  overflow-y: auto;
  z-index: 100;
}
/* sidebar 内部滚动条美化(避免长 nav 看起来 ugly) */
.dashboard-sidebar::-webkit-scrollbar { width: 4px; }
.dashboard-sidebar::-webkit-scrollbar-thumb { background: rgba(255,255,255,.1); border-radius: 2px; }
.dashboard-sidebar:hover::-webkit-scrollbar-thumb { background: rgba(255,255,255,.2); }

.sidebar-brand {
  padding: 4px 8px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  position: relative;
  /* 给折叠按钮留出右侧空间(展开模式) */
  padding-right: 38px;
}
.brand-text {
  flex: 1; min-width: 0;
  opacity: 1; max-height: 80px;
  overflow: hidden;
  transition: opacity .2s ease, max-height .25s cubic-bezier(.22,1,.36,1);
}
.brand-mini-icon {
  text-align: center;
  font-size: 14px; font-weight: 800; letter-spacing: 2px;
  color: #7c71ff;
  padding: 6px 0;
  opacity: 1;
  transition: opacity .2s ease;
}

/* 折叠按钮: 绝对定位在 sidebar 右上角,随 sidebar 宽度变化自然平移 */
.collapse-btn {
  position: absolute;
  top: 24px;
  right: 12px;
  z-index: 5;
  width: 26px; height: 26px;
  border: 1px solid rgba(255,255,255,.14); border-radius: 8px;
  background: rgba(255,255,255,.06); color: rgba(255,255,255,.7);
  cursor: pointer; display: inline-flex; align-items: center; justify-content: center;
  padding: 0;
  backdrop-filter: blur(4px);
  transition: right .25s cubic-bezier(.22,1,.36,1),
              background .18s, color .18s,
              border-color .18s, transform .35s cubic-bezier(.34,1.56,.64,1),
              box-shadow .2s;
}
.collapse-btn:hover {
  background: rgba(255,255,255,.18);
  color: #fff;
  border-color: rgba(255,255,255,.28);
  box-shadow: 0 4px 12px rgba(0,0,0,.18);
  transform: rotate(180deg);
}
.collapse-btn:active { transform: rotate(180deg) scale(.94); }
.collapse-btn .el-icon {
  transition: transform .35s cubic-bezier(.34,1.56,.64,1);
}

/* 折叠时按钮居中在 64px 宽度(brand 已隐藏,按钮独占顶部) */
.dashboard-sidebar.collapsed:not(.is-hovered) .collapse-btn {
  right: 19px; /* (64 - 8padding*2 - 26btn)/2 + 8 = 19 视觉居中 */
  top: 18px;
}
/* hover 浮出时按钮回到 220px 宽的右上 */
.dashboard-sidebar.collapsed.is-hovered .collapse-btn { right: 12px; top: 24px; }
.brand-mini {
  font-size: 12px; letter-spacing: 3px; color: #7c71ff;
  margin-bottom: 10px; font-weight: 700;
}
.sidebar-brand h1 { font-size: 15px; line-height: 1.5; font-weight: 800; }

.sidebar-nav {
  padding-top: 18px;
  display: flex; flex-direction: column; gap: 8px;
}
.nav-item {
  display: flex; align-items: center; gap: 10px;
  height: 46px; padding: 0 14px;
  color: #dbe6f5; text-decoration: none;
  border-radius: 12px; border: 1px solid transparent;
  transition: background .18s ease, color .18s ease, border-color .18s ease,
              padding .25s cubic-bezier(.22,1,.36,1), gap .25s cubic-bezier(.22,1,.36,1),
              transform .15s;
  overflow: hidden;
  position: relative;
}
.nav-item:hover {
  background: rgba(33, 110, 255, 0.18); color: #fff;
  transform: translateX(2px);
}
.nav-item .el-icon {
  flex-shrink: 0;
  transition: transform .2s cubic-bezier(.34, 1.56, .64, 1);
}
.nav-item:hover .el-icon { transform: scale(1.12); }
.nav-item.router-link-active {
  background: linear-gradient(90deg, rgba(22, 114, 196, 0.55), rgba(27, 122, 206, 0.3));
  border-color: rgba(75, 196, 255, 0.5); color: #fff;
  box-shadow: inset 0 0 0 1px rgba(62, 190, 255, 0.15);
}

/* 内容发布入口 - 高亮样式 */
.nav-item-highlight {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(139, 92, 246, 0.1));
  border-color: rgba(139, 92, 246, 0.25);
}
.nav-item-highlight:hover {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.28), rgba(139, 92, 246, 0.2));
  border-color: rgba(139, 92, 246, 0.45);
}
.nav-item-highlight .el-icon {
  color: #a78bfa;
}

/* 效果分析入口 - 青色高亮（与内容发布紫色区分） */
.nav-item-teal {
  background: linear-gradient(135deg, rgba(45, 212, 191, 0.15), rgba(20, 184, 166, 0.1));
  border-color: rgba(45, 212, 191, 0.25);
}
.nav-item-teal:hover {
  background: linear-gradient(135deg, rgba(45, 212, 191, 0.28), rgba(20, 184, 166, 0.2));
  border-color: rgba(45, 212, 191, 0.45);
}
.nav-item-teal .el-icon {
  color: #2dd4bf;
}

/* 导航分组分隔线 */
.nav-section-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
  margin: 8px 12px;
}
/* 标签文字: 平滑 fade + slide,而不是 display: none 一刀切 */
.nav-item span {
  max-width: 200px; opacity: 1;
  transform: translateX(0);
  white-space: nowrap;
  transition: max-width .25s cubic-bezier(.22,1,.36,1),
              opacity .15s ease,
              transform .25s cubic-bezier(.22,1,.36,1);
}
.nav-ext {
  margin-left: auto;
  font-size: 12px;
  opacity: 0.6;
  transition: opacity .18s ease;
}

/* Sidebar footer — user card */
.sidebar-footer {
  margin-top: auto;
  padding: 14px 4px 0;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}
.user-card {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 10px; border-radius: 10px;
  cursor: pointer; transition: background .15s;
}
.user-card:hover { background: rgba(255,255,255,0.08); }
.user-avatar {
  width: 34px; height: 34px; border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #818cf8);
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 700; color: #fff; flex-shrink: 0;
}
.user-name { font-size: 13px; color: #d7e5f7; font-weight: 500; }

/* ── 折叠状态(桌面端): 默认 64px,所有文字 fade+slide 出去 ── */
.dashboard-sidebar {
  transition: padding .25s cubic-bezier(.22,1,.36,1);
}
.dashboard-sidebar.collapsed:not(.is-hovered) { padding: 56px 8px 18px; }
.dashboard-sidebar.collapsed:not(.is-hovered) .sidebar-brand {
  padding: 4px 0 18px;
  flex-direction: column; align-items: center; gap: 6px;
}
.dashboard-sidebar.collapsed:not(.is-hovered) .nav-item {
  justify-content: center; padding: 0; gap: 0;
  width: 44px; height: 44px; margin: 0 auto;
}
/* 标签文字平滑收起(替代 display:none) */
.dashboard-sidebar.collapsed:not(.is-hovered) .nav-item span,
.dashboard-sidebar.collapsed:not(.is-hovered) .user-name {
  max-width: 0; opacity: 0;
  transform: translateX(-8px);
}
.dashboard-sidebar.collapsed:not(.is-hovered) .nav-ext {
  opacity: 0; max-width: 0;
  margin: 0; /* 关键:取消 margin-left:auto,否则会把主图标挤到左边(内容发布对不齐) */
}
.dashboard-sidebar.collapsed:not(.is-hovered) .brand-text { opacity: 0; max-height: 0; }
/* 折叠时整个 brand 区域(包括 GEO mini)都隐藏,只保留右上角折叠按钮 */
.dashboard-sidebar.collapsed:not(.is-hovered) .sidebar-brand {
  opacity: 0; max-height: 0; padding: 0; border-bottom: none;
  pointer-events: none;
  transition: opacity .15s ease, max-height .25s cubic-bezier(.22,1,.36,1), padding .25s;
}
/* 展开/hover 状态下 brand-mini-icon 不需要(brand-text 自动接管) */
.dashboard-sidebar:not(.collapsed) .brand-mini-icon,
.dashboard-sidebar.collapsed.is-hovered .brand-mini-icon {
  opacity: 0; max-width: 0; max-height: 0; padding: 0;
}
.dashboard-sidebar.collapsed:not(.is-hovered) .sidebar-nav { gap: 4px; align-items: center; }
.dashboard-sidebar.collapsed:not(.is-hovered) .sidebar-footer { padding: 14px 0 0; }
.dashboard-sidebar.collapsed:not(.is-hovered) .user-card {
  justify-content: center; padding: 8px 0; gap: 0;
}
.user-name {
  transition: max-width .25s cubic-bezier(.22,1,.36,1),
              opacity .15s ease,
              transform .25s cubic-bezier(.22,1,.36,1);
  white-space: nowrap; overflow: hidden;
  max-width: 200px; opacity: 1; transform: translateX(0);
}

/* ── 折叠+悬浮: 左栏从 64px 扩张到 220px,右侧内容自动让位(不再 fixed 覆盖) ── */
.dashboard-layout.is-collapsed-hover { grid-template-columns: 220px 1fr; }

/* sidebar 内部视觉恢复到"展开"外观;父 grid 列扩张 + 自身样式重置同步动画 */
.dashboard-sidebar.collapsed.is-hovered {
  padding: 28px 16px 18px;
  box-shadow: 6px 0 24px rgba(0,0,0,.18);
}
.dashboard-sidebar.collapsed.is-hovered .sidebar-brand {
  padding: 4px 8px 24px;
  flex-direction: row; align-items: flex-start; gap: 8px;
}
.dashboard-sidebar.collapsed.is-hovered .brand-text { opacity: 1; max-height: 80px; }
.dashboard-sidebar.collapsed.is-hovered .nav-item {
  justify-content: flex-start; padding: 0 14px; gap: 10px;
  width: auto; height: 46px; margin: 0;
}
.dashboard-sidebar.collapsed.is-hovered .nav-item span,
.dashboard-sidebar.collapsed.is-hovered .user-name {
  max-width: 200px; opacity: 1; transform: translateX(0);
}
.dashboard-sidebar.collapsed.is-hovered .nav-ext { opacity: 0.6; max-width: 200px; }
.dashboard-sidebar.collapsed.is-hovered .sidebar-nav { gap: 8px; align-items: stretch; }
.dashboard-sidebar.collapsed.is-hovered .sidebar-footer { padding: 14px 4px 0; }
.dashboard-sidebar.collapsed.is-hovered .user-card {
  justify-content: flex-start; padding: 10px; gap: 10px;
}

/* sidebar 通用 transition(box-shadow 也走) */
.dashboard-sidebar { transition: padding .25s cubic-bezier(.22,1,.36,1), box-shadow .25s ease; }
.sidebar-brand { transition: padding .25s cubic-bezier(.22,1,.36,1), gap .25s cubic-bezier(.22,1,.36,1); }
.user-card { transition: padding .25s cubic-bezier(.22,1,.36,1), gap .25s cubic-bezier(.22,1,.36,1), background .15s; }
.sidebar-footer { transition: padding .25s cubic-bezier(.22,1,.36,1); }

/* Popover content */
.user-popover { margin: -12px; }
.pop-user-info {
  display: flex; align-items: center; gap: 10px;
  padding: 16px 16px 12px;
  border-bottom: 1px solid #f0f0f0;
}
.pop-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #818cf8);
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 700; color: #fff; flex-shrink: 0;
}
.pop-name { font-size: 14px; font-weight: 600; color: #1e293b; }
.pop-actions { padding: 4px 0; }
.pop-action {
  padding: 10px 16px; font-size: 13px; color: #374151;
  cursor: pointer; transition: background .12s;
}
.pop-action:hover { background: #f5f7fa; }
.pop-action-danger { color: #ef4444; }
.pop-action-danger:hover { background: #fef2f2; }

.dashboard-main { min-width: 0; }
.dashboard-main-header {
  background: #fff; min-height: 82px;
  padding: 18px 24px; border-bottom: 1px solid #e7edf5;
  display: flex; justify-content: space-between; align-items: center; gap: 12px;
}
.dashboard-main-header .header-title { flex: 1; min-width: 0; }
.dashboard-main-header h2 { font-size: 22px; color: #0f172a; margin-bottom: 4px; }
.dashboard-main-header p { font-size: 13px; color: #64748b; }
.dashboard-main-body { padding: 20px 24px 32px; }

/* 汉堡按钮（仅 < 900px 显示） */
.burger {
  width: 38px; height: 38px; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  border: 1px solid #e2e8f0; border-radius: 8px; background: #fff;
  color: #475569; cursor: pointer; font-size: 18px;
  transition: background .15s, border-color .15s;
}
.burger:hover { background: #f1f5f9; border-color: #cbd5e1; }
.burger:active { background: #e2e8f0; }

/* 移动端遮罩 */
.drawer-backdrop {
  position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45);
  z-index: 1900; backdrop-filter: blur(2px);
  animation: backdrop-in .18s ease-out;
}
@keyframes backdrop-in { from { opacity: 0 } to { opacity: 1 } }

/* 移动端布局：侧边栏改 fixed 抽屉，main 占满宽 */
@media (max-width: 899.9px) {
  .dashboard-layout { margin-left: 0; }
  .dashboard-sidebar {
    position: fixed; top: 0; left: 0; bottom: 0;
    width: 260px; z-index: 2000;
    transform: translateX(-100%);
    transition: transform .25s cubic-bezier(.4, 0, .2, 1);
    box-shadow: 4px 0 24px rgba(0, 0, 0, 0.18);
    padding: 20px 14px 14px;
  }
  .dashboard-sidebar.is-open { transform: translateX(0); }
  .sidebar-nav { flex-direction: column; overflow-y: auto; }
  .sidebar-footer { margin-top: 12px; }
  .dashboard-main-header { padding: 14px 16px; min-height: 64px; }
  .dashboard-main-header h2 { font-size: 18px; }
  .dashboard-main-header p { font-size: 12px; }
  .dashboard-main-body { padding: 14px 14px 24px; }
}
.gs-trigger { flex-shrink: 0; display: inline-flex; align-items: center; gap: 8px; cursor: pointer;
  padding: 8px 13px; border-radius: 11px; color: #64748b; font-family: inherit; font-size: 13px;
  background: rgba(248,250,252,.65); backdrop-filter: blur(10px) saturate(160%); -webkit-backdrop-filter: blur(10px) saturate(160%);
  border: 1px solid rgba(226,232,240,.8); box-shadow: 0 4px 14px -8px rgba(37,99,235,.25), inset 0 1px 0 rgba(255,255,255,.7);
  transition: all .2s cubic-bezier(.16,1,.3,1); }
.gs-trigger .el-icon { color: #2563eb; }
.gs-trigger:hover { color: #2563eb; transform: translateY(-1px); background: rgba(239,246,255,.8);
  box-shadow: 0 8px 22px -8px rgba(37,99,235,.38), inset 0 1px 0 rgba(255,255,255,.85); }
.gs-trigger kbd { font-size: 11px; background: rgba(255,255,255,.6); border: 1px solid rgba(148,163,184,.3); border-radius: 5px; padding: 1px 6px; color: #64748b; }
@media (max-width: 640px) { .gs-trigger .gs-trigger-t, .gs-trigger kbd { display: none; } }
</style>
