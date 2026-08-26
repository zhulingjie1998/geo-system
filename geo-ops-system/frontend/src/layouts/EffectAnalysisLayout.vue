<template>
  <div class="effect-analysis-layout" :class="{ 'is-mobile': isMobile, 'drawer-open': drawerOpen }">
    <div v-if="isMobile && drawerOpen" class="drawer-backdrop" @click="drawerOpen = false"></div>

    <aside class="ea-sidebar" :class="{ 'is-open': drawerOpen }">
      <div class="sidebar-brand">
        <p class="brand-mini">MEDIA OPS</p>
        <h1>GEO 效果分析</h1>
      </div>

      <nav class="sidebar-nav" @click="onNavClick">
        <!-- 单客户深度 -->
        <div class="nav-section-title">单客户深度</div>
        <RouterLink to="/effect-analysis/customer-effect" class="nav-item">
          <el-icon><DataAnalysis /></el-icon>
          <span>客户效果分析</span>
        </RouterLink>

        <!-- 异动监控 -->
        <div class="nav-section-title">异动监控</div>
        <RouterLink to="/effect-analysis/on-list-keywords" class="nav-item">
          <el-icon><Top /></el-icon>
          <span>上榜词</span>
        </RouterLink>
        <RouterLink to="/effect-analysis/offline-keywords" class="nav-item">
          <el-icon><CircleClose /></el-icon>
          <span>不在线词</span>
        </RouterLink>
        <RouterLink to="/effect-analysis/offline-warning" class="nav-item">
          <el-icon><WarningFilled /></el-icon>
          <span>掉线预警</span>
        </RouterLink>
        <RouterLink to="/effect-analysis/ranking-fluctuation" class="nav-item">
          <el-icon><TrendCharts /></el-icon>
          <span>排名波动</span>
        </RouterLink>

        <!-- 维度 -->
        <div class="nav-section-title">维度</div>
        <RouterLink to="/effect-analysis/platform-comparison" class="nav-item">
          <el-icon><Histogram /></el-icon>
          <span>平台对比</span>
        </RouterLink>
        <RouterLink to="/effect-analysis/competitor-analysis" class="nav-item">
          <el-icon><Aim /></el-icon>
          <span>竞品分析</span>
        </RouterLink>
        <RouterLink to="/effect-analysis/citation-source" class="nav-item">
          <el-icon><Link /></el-icon>
          <span>引用源分析</span>
        </RouterLink>
      </nav>
    </aside>

    <main class="ea-main">
      <div class="ea-header">
        <button v-if="isMobile" class="burger" @click="drawerOpen = !drawerOpen" aria-label="切换侧边栏">
          <el-icon><Menu /></el-icon>
        </button>
        <div class="header-title">
          <h2>{{ pageTitle }}</h2>
          <p>{{ pageDesc }}</p>
        </div>
        <RouterLink to="/dashboard/home" class="header-back-link">
          <el-icon><Back /></el-icon>
          <span>返回运营系统</span>
        </RouterLink>
      </div>

      <div class="ea-body">
        <router-view />
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  DataAnalysis, Top, CircleClose, WarningFilled, TrendCharts,
  Histogram, Aim, Link, Menu, Back
} from '@element-plus/icons-vue'

const route = useRoute()

const MOBILE_BREAKPOINT = 900
const isMobile = ref(typeof window !== 'undefined' && window.innerWidth < MOBILE_BREAKPOINT)
const drawerOpen = ref(false)

function onResize() {
  const wasMobile = isMobile.value
  isMobile.value = window.innerWidth < MOBILE_BREAKPOINT
  if (!isMobile.value && wasMobile) drawerOpen.value = false
}
function onNavClick(e) {
  if (isMobile.value && e.target.closest('a')) drawerOpen.value = false
}
onMounted(() => window.addEventListener('resize', onResize))
onBeforeUnmount(() => window.removeEventListener('resize', onResize))
watch(() => route.fullPath, () => { drawerOpen.value = false })

const TITLE_MAP = {
  '/effect-analysis/customer-effect': ['客户效果分析', '选择一个客户，深入看它的上榜率趋势、平台表现、上榜/掉线词与排名波动。'],
  '/effect-analysis/on-list-keywords': ['上榜词', '监控客户上榜关键词的变化，及时发现新增上榜词。'],
  '/effect-analysis/offline-keywords': ['不在线词', '追踪已掉线/不在线的关键词，掌握客户内容覆盖缺口。'],
  '/effect-analysis/offline-warning': ['掉线预警', '对即将掉线的关键词进行预警，提前介入维护。'],
  '/effect-analysis/ranking-fluctuation': ['排名波动', '监控关键词排名波动情况，识别异常变化。'],
  '/effect-analysis/platform-comparison': ['平台对比', '跨 AI 平台效果对比分析，了解各平台品牌露出差异。'],
  '/effect-analysis/competitor-analysis': ['竞品分析', '分析竞品在各 AI 平台的品牌露出与引用情况。'],
  '/effect-analysis/citation-source': ['引用源分析', '分析 AI 回答中引用的网页来源、发布日期与内容类型。'],
}

const pageMeta = computed(() => TITLE_MAP[route.path] || ['GEO 效果分析', ''])
const pageTitle = computed(() => pageMeta.value[0])
const pageDesc = computed(() => pageMeta.value[1])
</script>

<style scoped>
.effect-analysis-layout {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  background: #f3f6fb;
  width: 100%;
  overflow-x: hidden;
}

.ea-sidebar {
  width: 220px;
  min-width: 220px;
  flex-shrink: 0;
  background: radial-gradient(circle at top, rgba(20, 135, 180, 0.22), transparent 45%), linear-gradient(180deg, #0c1e2e 0%, #0f2a3f 55%, #103a4a 100%);
  color: #fff;
  padding: 28px 16px 18px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  position: fixed;
  left: 0;
  top: 0;
  height: 100vh;
  height: 100dvh;
  overflow-y: auto;
  z-index: 100;
}
.ea-sidebar::-webkit-scrollbar { width: 4px; }
.ea-sidebar::-webkit-scrollbar-thumb { background: rgba(255,255,255,.1); border-radius: 2px; }

.sidebar-brand {
  padding: 4px 8px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.brand-mini {
  font-size: 10.5px; font-weight: 700; letter-spacing: 2.5px;
  color: #2dd4bf; margin: 0 0 4px; text-transform: uppercase;
}
.sidebar-brand h1 {
  font-size: 16px; font-weight: 700; margin: 0; color: #fff;
  letter-spacing: 0.5px;
}

.sidebar-nav {
  display: flex; flex-direction: column; gap: 4px; padding-top: 16px; flex: 1;
}
.nav-item {
  display: flex; align-items: center; gap: 10px;
  height: 46px; padding: 0 14px;
  color: #dbe6f5; text-decoration: none;
  border-radius: 12px; border: 1px solid transparent;
  transition: background .18s ease, color .18s ease, border-color .18s ease,
              padding .25s cubic-bezier(.22,1,.36,1), gap .25s cubic-bezier(.22,1,.36,1),
              transform .15s;
  overflow: hidden; position: relative;
}
.nav-item:hover {
  background: rgba(45, 212, 191, 0.18); color: #fff;
  transform: translateX(2px);
}
.nav-item .el-icon {
  flex-shrink: 0; font-size: 17px;
  transition: transform .2s cubic-bezier(.34, 1.56, .64, 1);
}
.nav-item:hover .el-icon { transform: scale(1.12); }
.nav-item.router-link-active,
.nav-item.active {
  background: linear-gradient(90deg, rgba(20, 184, 166, 0.55), rgba(45, 212, 191, 0.3));
  border-color: rgba(45, 212, 191, 0.5); color: #fff;
  box-shadow: inset 0 0 0 1px rgba(45, 212, 191, 0.15);
}
.nav-item span { white-space: nowrap; }

.nav-section-title {
  padding: 14px 14px 6px;
  font-size: 11px; font-weight: 600;
  color: rgba(255, 255, 255, 0.35);
  letter-spacing: 1px; text-transform: uppercase;
  user-select: none;
}

.ea-main {
  display: flex; flex-direction: column;
  min-width: 0;
  min-height: 100vh;
  min-height: 100dvh;
  flex: 1;
  margin-left: 220px;
  width: calc(100% - 220px);
  overflow-x: hidden;
}

.ea-header {
  display: flex; align-items: center; gap: 16px;
  padding: 16px 28px;
  background: #ffffff;
  border-bottom: 1px solid #e5eaf3;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
  flex-shrink: 0;
}
.header-title h2 {
  font-size: 20px; font-weight: 700; color: #0f172a; margin: 0 0 3px;
}
.header-title p {
  font-size: 13px; color: #64748b; margin: 0; line-height: 1.4;
}
.header-back-link {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid #dbe3f1;
  background: #f8fbff;
  color: #334155;
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  transition: all .18s ease;
}
.header-back-link:hover {
  background: #eff6ff;
  border-color: #c8d6ee;
  color: #0f172a;
}
.header-back-link .el-icon {
  font-size: 14px;
}
.burger {
  display: none; background: none; border: none;
  cursor: pointer; padding: 6px; border-radius: 8px;
  color: #475569; font-size: 22px;
}
.burger:hover { background: #f1f5f9; }

.ea-body {
  flex: 1;
  padding: 18px 28px 32px;
  width: 100%;
  max-width: 100%;
  overflow-x: hidden;
  box-sizing: border-box;
}

.drawer-backdrop {
  position: fixed; inset: 0; background: rgba(0,0,0,.45); z-index: 98;
}

@media (max-width: 900px) {
  .effect-analysis-layout { flex-direction: column; }
  .ea-sidebar {
    position: fixed; left: -240px; top: 0; bottom: 0; width: 220px;
    z-index: 99; transition: left .25s ease;
    height: 100vh; height: 100dvh;
  }
  .ea-sidebar.is-open { left: 0; }
  .burger { display: block; }
  .ea-main {
    margin-left: 0;
    width: 100%;
  }
  .ea-body {
    padding: 14px 14px 24px;
    width: 100%;
  }
  .ea-header { padding: 14px; }
  .header-back-link { padding: 7px 10px; font-size: 12px; }
}

@media (max-width: 480px) {
  .ea-body { padding: 12px 10px 20px; }
  .ea-header { padding: 12px 10px; }
  .header-title h2 { font-size: 17px; }
  .header-back-link span { display: none; }
}

/* ═══ 统一 el-table 表头样式（与运营管理系统一致） ═══ */
.ea-body :deep(.el-table) {
  --el-table-border-color: transparent;
  --el-table-header-bg-color: transparent;
  --el-table-row-hover-bg-color: #f8fafc;
}
.ea-body :deep(.el-table__header-wrapper) {
  border-bottom: 1px solid #f1f5f9;
}
.ea-body :deep(.el-table__header th) {
  background: transparent !important;
  padding: 10px 0 !important;
  text-transform: none;
}
</style>
