import { createRouter, createWebHistory } from 'vue-router'
import LoginPage from '../views/LoginPage.vue'
import DashboardLayout from '../layouts/DashboardLayout.vue'
import PublishLayout from '../layouts/PublishLayout.vue'
import HomePage from '../views/HomePage.vue'
import AccountManagementPage from '../views/AccountManagementPage.vue'
import KeywordSearchPage from '../views/KeywordSearchPage.vue'
import KeywordSearchDetailPage from '../views/KeywordSearchDetailPage.vue'
import SystemSettingsPage from '../views/SystemSettingsPage.vue'
import AdminUsersPage from '../views/AdminUsersPage.vue'
import KnowledgeBasePage from '../views/KnowledgeBasePage.vue'
import PublishCustomersPage from '../views/PublishCustomersPage.vue'
import PublishHome from '../views/PublishHome.vue'
import PublishKnowledgePage from '../views/PublishKnowledgePage.vue'
import PublishContentLibraryPage from '../views/PublishContentLibraryPage.vue'
import PublishContentLibraryDetailPage from '../views/PublishContentLibraryDetailPage.vue'
import PublishContentPublishPage from '../views/PublishContentPublishPage.vue'
import PublishReleaseManagementPage from '../views/PublishReleaseManagementPage.vue'
import PublishReleaseRecordsPage from '../views/PublishReleaseRecordsPage.vue'
import PublishResourceManagementPage from '../views/PublishResourceManagementPage.vue'
import PublishOfficialConfigPage from '../views/PublishOfficialConfigPage.vue'
import PublishKbDetailPage from '../views/PublishKbDetailPage.vue'
import PublishAiWritePage from '../views/PublishAiWritePage.vue'
import PublishInstructionPage from '../views/PublishInstructionPage.vue'
import GeoExpansionPage from '../views/GeoExpansionPage.vue'
import RankingAnalysisPage from '../views/RankingAnalysisPage.vue'
import api from '../api'
import { getAuthState, setAuthState, resetAuthState } from '../utils/auth'

const routes = [
  { path: '/login', name: 'Login', component: LoginPage },
  {
    path: '/dashboard',
    component: DashboardLayout,
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/dashboard/home' },
      { path: 'home', name: 'DashboardHome', component: HomePage },
      { path: 'accounts', name: 'DashboardAccounts', component: AccountManagementPage },
      { path: 'keyword-search', name: 'KeywordSearch', component: KeywordSearchPage },
      { path: 'keyword-search/:accountId', name: 'KeywordSearchDetail', component: KeywordSearchDetailPage },
      { path: 'ranking-analysis', name: 'RankingAnalysis', component: RankingAnalysisPage },
      { path: 'geo-expansion', name: 'GeoExpansion', component: GeoExpansionPage },
      { path: 'knowledge', name: 'DashboardKnowledge', component: KnowledgeBasePage },
      { path: 'admin-users', name: 'AdminUsers', component: AdminUsersPage },
      { path: 'roles', name: 'Roles', redirect: { path: '/dashboard/admin-users', query: { tab: 'roles' } } },
      { path: 'settings', name: 'SystemSettings', component: SystemSettingsPage },
    ]
  },
  // ========== 内容发布系统（独立布局）==========
  {
    path: '/publish',
    component: PublishLayout,
    meta: { requiresAuth: true, title: 'GEO 内容发布系统' },
    children: [
      { path: '', redirect: '/publish/home' },
      { path: 'home', name: 'PublishHome', component: PublishHome },
      { path: 'customers', name: 'PublishCustomers', component: PublishCustomersPage },
      { path: 'customer-kb', name: 'PublishCustomerKb', component: PublishKnowledgePage },
      { path: 'customer-kb/:id', name: 'PublishKbDetail', component: PublishKbDetailPage },
      { path: 'content-library', name: 'PublishContentLibrary', component: PublishContentLibraryPage },
      { path: 'content-library/:accountId', name: 'PublishContentLibraryDetail', component: PublishContentLibraryDetailPage },
      { path: 'content-publish/:accountId', name: 'PublishContentPublish', component: PublishContentPublishPage },
      { path: 'releases', name: 'PublishReleaseManagement', component: PublishReleaseManagementPage },
      { path: 'releases/:accountId', name: 'PublishReleaseRecords', component: PublishReleaseRecordsPage },
      { path: 'resources', name: 'PublishResourceManagement', component: PublishResourceManagementPage },
      { path: 'official-config', name: 'PublishOfficialConfig', component: PublishOfficialConfigPage },
      // 以下页面待开发，暂时占位
      { path: 'knowledge', name: 'PublishKnowledge', redirect: '/publish/customer-kb' },
      { path: 'ai-write', name: 'PublishAiWrite', component: PublishAiWritePage },
      { path: 'prompts', name: 'PublishPrompts', component: PublishInstructionPage },
      { path: 'media', name: 'PublishMedia', redirect: '/publish/home' },
      { path: 'articles', name: 'PublishArticles', redirect: '/publish/content-library' },
    ]
  },
  { path: '/', redirect: '/dashboard/home' },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export function getIsSuperAdmin() { return getAuthState().isSuperAdmin }

async function checkAuth() {
  try {
    const data = await api.authMe()
    const authOk = !!data?.authenticated
    const role = data?.role || 'operator'
    const isSuperAdmin = role === 'super_admin'
    setAuthState(true, authOk, isSuperAdmin)
    if (authOk && data?.username) {
      localStorage.setItem('geo_user', data.username)
      localStorage.setItem('geo_is_super', isSuperAdmin ? '1' : '0')
      localStorage.setItem('geo_role', role)
      localStorage.setItem('geo_role_name', data.roleName || '')
      localStorage.setItem('geo_data_scope', data.dataScope || 'self')
      localStorage.setItem('geo_pages', JSON.stringify(data.pages || []))
      // 兼容字段（旧代码可能还在读）
      localStorage.setItem('geo_permissions', JSON.stringify(data.pages || []))
    } else {
      localStorage.removeItem('geo_user')
      localStorage.removeItem('geo_is_super')
      localStorage.removeItem('geo_role')
      localStorage.removeItem('geo_role_name')
      localStorage.removeItem('geo_data_scope')
      localStorage.removeItem('geo_pages')
      localStorage.removeItem('geo_permissions')
    }
  } catch (_) {
    // 认证失败，保持未认证状态
  }
}

const PAGE_KEY_MAP = {
  'DashboardHome': 'home',
  'DashboardAccounts': 'accounts',
  'KeywordSearch': 'keyword-search',
  'KeywordSearchDetail': 'keyword-search',
  'RankingAnalysis': 'ranking-analysis',
  'DashboardKnowledge': 'knowledge',
  'AdminUsers': 'admin-users',
  'Roles': 'roles',
  'SystemSettings': 'settings',
}

function canAccessPage(pageKey) {
  const role = localStorage.getItem('geo_role') || 'operator'
  // super_admin 默认全部放行
  if (role === 'super_admin') return true
  // 其它角色：查 session 里 pages 数组（来自 role.pages）
  let pages = []
  try { pages = JSON.parse(localStorage.getItem('geo_pages') || '[]') } catch {}
  if (pages.includes(pageKey)) return true
  // 等价权限映射：新加的页面没在老 role.pages 里时，按业务等价权限放行
  const EQUIV = {
    // 内容库属于发布模块：任一发布相关权限即可访问
    'content-library': ['publish', 'publish-article', 'publish-batch', 'publish-orders'],
  }
  const alts = EQUIV[pageKey] || []
  return alts.some(k => pages.includes(k))
}

// 动态切换 document.title（外部页用独立标题）
const TITLE_MAP = {
  Login: '登录 · GEO 运营系统',
}
const DEFAULT_TITLE = 'GEO 运营系统'

router.beforeEach(async (to) => {
  // 外部页（无需鉴权）独立处理：跳过 authMe 调用 + 直接放行
  if (to.name === 'ExternalSearch' || to.path === '/external-search') {
    document.title = TITLE_MAP.ExternalSearch
    return true
  }
  if (to.name === 'ExternalKeywords' || to.path === '/external-keywords') {
    document.title = TITLE_MAP.ExternalKeywords
    return true
  }
  if (to.name === 'ExternalHub' || to.path === '/external') {
    document.title = TITLE_MAP.ExternalHub
    return true
  }
  const { authChecked } = getAuthState()
  if (!authChecked) await checkAuth()
  const { authOk } = getAuthState()
  if (to.meta.requiresAuth && !authOk) {
    return '/login'
  }
  if (to.path === '/login' && authOk) {
    return '/dashboard/home'
  }
  const pageKey = PAGE_KEY_MAP[to.name]
  if (pageKey && !canAccessPage(pageKey)) {
    return '/dashboard/home'
  }
  document.title = TITLE_MAP[to.name] || DEFAULT_TITLE
  return true
})

export default router
