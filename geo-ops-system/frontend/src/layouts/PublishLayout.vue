<template>
  <div class="publish-layout" :class="{
    'is-mobile': isMobile,
    'drawer-open': drawerOpen,
  }">
    <div v-if="isMobile && drawerOpen" class="drawer-backdrop" @click="drawerOpen = false"></div>

    <aside class="publish-sidebar" :class="{ 'is-open': drawerOpen }">
      <div class="sidebar-brand">
        <p class="brand-mini">MEDIA OPS</p>
        <h1>GEO 内容发布系统</h1>
      </div>

      <nav class="sidebar-nav" @click="onNavClick">
        <div class="nav-section-title">客户内容</div>
        <RouterLink to="/publish/customers" class="nav-item">
          <el-icon><User /></el-icon>
          <span>客户管理</span>
        </RouterLink>
        <RouterLink to="/publish/customer-kb" class="nav-item">
          <el-icon><Notebook /></el-icon>
          <span>知识库</span>
        </RouterLink>
        <RouterLink to="/publish/content-library" class="nav-item">
          <el-icon><Document /></el-icon>
          <span>内容库</span>
        </RouterLink>

        <div class="nav-section-title">智能生文</div>
        <RouterLink to="/publish/ai-write" class="nav-item">
          <el-icon><MagicStick /></el-icon>
          <span>智能生文</span>
        </RouterLink>
        <RouterLink to="/publish/prompts" class="nav-item">
          <el-icon><Collection /></el-icon>
          <span>指令库</span>
        </RouterLink>

        <div class="nav-section-title">发布</div>
        <RouterLink to="/publish/releases" class="nav-item">
          <el-icon><Promotion /></el-icon>
          <span>发布管理</span>
        </RouterLink>

        <div class="nav-section-title">资源</div>
        <RouterLink to="/publish/resources" class="nav-item">
          <el-icon><Files /></el-icon>
          <span>资源管理</span>
        </RouterLink>
        <RouterLink to="/publish/official-config" class="nav-item">
          <el-icon><Connection /></el-icon>
          <span>官网配置</span>
        </RouterLink>
      </nav>
    </aside>

    <main class="publish-main">
      <div class="publish-header">
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

      <div class="publish-body">
        <router-view />
      </div>
    </main>

    <!-- 全局浮动任务窗口 -->
    <KbTaskFloat />
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import { User, Notebook, Document, Menu, Back, MagicStick, Collection, Promotion, Files, Connection } from '@element-plus/icons-vue'
import KbTaskFloat from '@/components/KbTaskFloat.vue'

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
  '/publish/home': ['首页', '内容发布系统总览与快捷操作入口'],
  '/publish/customers': ['客户管理', '管理内容发布所服务的客户档案；与 GEO 主系统客户管理共享同一份数据。'],
  '/publish/customer-kb': ['知识库', '为客户维护品牌知识库：上传素材、生成与管理知识库版本。'],
  '/publish/customer-kb-detail': ['知识库详情', '查看与编辑客户知识库内容。'],
  '/publish/content-library': ['内容库', '智能生文产物 点「保存到内容库」入库；支持编辑、去发布、删除。'],
  '/publish/content-publish': ['内容发布', '选择客户与文章，编辑标题正文并设置平台与发布时间。'],
  '/publish/releases': ['发布管理', '查看客户发布后的统计与记录，支持按客户进入明细。'],
  '/publish/releases-records': ['发布记录', '按客户查看文章发布记录，并按类型与状态筛选。'],
  '/publish/resources': ['资源管理', '维护资源站点资源（博客/论坛/B2B/问答）列表。'],
  '/publish/official-config': ['官网配置', '维护客户官网 HTTP 设置与 webhook 对接状态。'],
  '/publish/ai-write': ['智能生文', 'AI 智能生成高质量内容，支持多种写作模式。'],
  '/publish/prompts': ['指令库', '管理与维护 AI 写作提示词模板。'],
}

const pageMeta = computed(() => {
  if (route.path.startsWith('/publish/content-library')) {
    return TITLE_MAP['/publish/content-library']
  }
  if (route.path.startsWith('/publish/content-publish')) {
    return TITLE_MAP['/publish/content-publish']
  }
  if (route.path.match(/^\/publish\/customer-kb\/\d+/)) {
    return TITLE_MAP['/publish/customer-kb-detail']
  }
  if (route.path.startsWith('/publish/releases/')) {
    return TITLE_MAP['/publish/releases-records']
  }
  if (route.path.startsWith('/publish/releases')) {
    return TITLE_MAP['/publish/releases']
  }
  if (route.path.startsWith('/publish/resources')) {
    return TITLE_MAP['/publish/resources']
  }
  if (route.path.startsWith('/publish/official-config')) {
    return TITLE_MAP['/publish/official-config']
  }
  return TITLE_MAP[route.path] || ['GEO 内容发布系统', '']
})

const pageTitle = computed(() => pageMeta.value[0])
const pageDesc = computed(() => pageMeta.value[1])
</script>

<style scoped>
.publish-layout {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  background: #f3f6fb;
  width: 100%;
  overflow-x: hidden;
}

.publish-sidebar {
  width: 220px;
  min-width: 220px;
  flex-shrink: 0;
  background: radial-gradient(circle at top, rgba(20, 135, 219, 0.22), transparent 45%), linear-gradient(180deg, #111827 0%, #0f1f37 55%, #102a46 100%);
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
.publish-sidebar::-webkit-scrollbar { width: 4px; }
.publish-sidebar::-webkit-scrollbar-thumb { background: rgba(255,255,255,.1); border-radius: 2px; }

.sidebar-brand {
  padding: 4px 8px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.brand-mini {
  font-size: 10.5px; font-weight: 700; letter-spacing: 2.5px;
  color: #7c71ff; margin: 0 0 4px; text-transform: uppercase;
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
  background: rgba(33, 110, 255, 0.18); color: #fff;
  transform: translateX(2px);
}
.nav-item .el-icon {
  flex-shrink: 0; font-size: 17px;
  transition: transform .2s cubic-bezier(.34, 1.56, .64, 1);
}
.nav-item:hover .el-icon { transform: scale(1.12); }
.nav-item.router-link-active,
.nav-item.active {
  background: linear-gradient(90deg, rgba(22, 114, 196, 0.55), rgba(27, 122, 206, 0.3));
  border-color: rgba(75, 196, 255, 0.5); color: #fff;
  box-shadow: inset 0 0 0 1px rgba(62, 190, 255, 0.15);
}
.nav-item span { white-space: nowrap; }

.nav-section-title {
  padding: 14px 14px 6px;
  font-size: 11px; font-weight: 600;
  color: rgba(255, 255, 255, 0.35);
  letter-spacing: 1px; text-transform: uppercase;
  user-select: none;
}

.publish-main {
  display: flex; flex-direction: column;
  min-width: 0;
  min-height: 100vh;
  min-height: 100dvh;
  flex: 1;
  margin-left: 220px;
  width: calc(100% - 220px);
  overflow-x: hidden;
}

.publish-header {
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

.publish-body {
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
  .publish-layout { flex-direction: column; }
  .publish-sidebar {
    position: fixed; left: -240px; top: 0; bottom: 0; width: 220px;
    z-index: 99; transition: left .25s ease;
    height: 100vh; height: 100dvh;
  }
  .publish-sidebar.is-open { left: 0; }
  .burger { display: block; }
  .publish-main {
    margin-left: 0;
    width: 100%;
  }
  .publish-body {
    padding: 14px 14px 24px;
    width: 100%;
  }
  .publish-header { padding: 14px; }
  .header-back-link { padding: 7px 10px; font-size: 12px; }
}

@media (max-width: 480px) {
  .publish-body { padding: 12px 10px 20px; }
  .publish-header { padding: 12px 10px; }
  .header-title h2 { font-size: 17px; }
  .header-back-link span { display: none; }
}

/* ═══ 统一 el-table 表头样式（与运营管理系统一致） ═══ */
.publish-body :deep(.el-table) {
  --el-table-border-color: transparent;
  --el-table-header-bg-color: transparent;
  --el-table-row-hover-bg-color: #f8fafc;
}
.publish-body :deep(.el-table__header-wrapper) {
  border-bottom: 1px solid #f1f5f9;
}
.publish-body :deep(.el-table__header th) {
  background: transparent !important;
  padding: 10px 0 !important;
  text-transform: none;
}
</style>
