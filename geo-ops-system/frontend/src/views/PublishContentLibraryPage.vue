<template>
  <div class="publish-content-page">
    <section class="kpi-strip">
      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-blue"><el-icon><User /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-val">{{ stats.customers }}</div>
          <div class="kpi-label">客户总数</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-green"><el-icon><Document /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-val">{{ stats.withContent }}</div>
          <div class="kpi-label">有内容客户</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-orange"><el-icon><Collection /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-val">{{ stats.articleTotal }}</div>
          <div class="kpi-label">文章总量</div>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input
            v-model="searchText"
            placeholder="搜索品牌名 / 公司名"
            clearable
            :prefix-icon="Search"
            class="search-input"
          />
          <span class="count-text">{{ filteredRows.length }} 个客户</span>
        </div>
        <div class="toolbar-right">
          <el-button :icon="Refresh" plain @click="loadData">刷新</el-button>
        </div>
      </div>

      <el-table
        :data="filteredRows"
        v-loading="loading"
        row-key="id"
        class="content-table"
        :header-cell-style="{ background: '#fafbfc', color: '#64748b', fontWeight: 600, fontSize: '13px' }"
      >
        <el-table-column label="客户" min-width="300">
          <template #default="{ row }">
            <div class="customer-cell">
              <div class="avatar" :style="{ background: avatarColor(row) }">{{ avatarLetter(row) }}</div>
              <div class="customer-info">
                <div class="brand-line">{{ displayBrand(row) || '—' }}</div>
                <div class="company-line">{{ row.companyName || row.name || '—' }}</div>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="文章数" width="130" align="center" sortable>
          <template #default="{ row }">
            <span class="article-count">{{ row.articleCount || 0 }} 篇</span>
          </template>
        </el-table-column>

        <el-table-column prop="updatedAt" label="更新时间" width="190" sortable>
          <template #default="{ row }">
            <span class="time-cell">{{ formatTime(row.updatedAt) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="100" align="right">
          <template #default="{ row }">
            <a class="view-link" @click="viewDetail(row)">查看 ›</a>
          </template>
        </el-table-column>

        <template #empty>
          <div class="table-empty">暂无客户内容数据</div>
        </template>
      </el-table>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Search, Refresh, User, Document, Collection } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import api from '@/api'
import publishApi from '@/api/publish'

const loading = ref(false)
const searchText = ref('')
const rows = ref([])
const router = useRouter()

const stats = computed(() => {
  const customers = rows.value.length
  const withContent = rows.value.filter(r => (r.articleCount || 0) > 0).length
  const articleTotal = rows.value.reduce((sum, r) => sum + (Number(r.articleCount || 0) || 0), 0)
  return { customers, withContent, articleTotal }
})

const filteredRows = computed(() => {
  const q = searchText.value.trim().toLowerCase()
  const filtered = q
    ? rows.value.filter((row) => {
        const company = String(row.companyName || row.name || '').toLowerCase()
        const brand = displayBrand(row).toLowerCase()
        return company.includes(q) || brand.includes(q)
      })
    : rows.value
  return [...filtered].sort((a, b) => {
    const ta = a.updatedAt || a.createdAt || ''
    const tb = b.updatedAt || b.createdAt || ''
    return tb.localeCompare(ta)
  })
})

function normalizeBrands(raw) {
  if (Array.isArray(raw)) return raw.map(x => String(x || '').trim()).filter(Boolean)
  if (typeof raw !== 'string') return []
  const s = raw.trim()
  if (!s) return []
  if (s.startsWith('[') && s.endsWith(']')) {
    try {
      const arr = JSON.parse(s)
      return Array.isArray(arr) ? arr.map(x => String(x || '').trim()).filter(Boolean) : []
    } catch {
      return [s]
    }
  }
  if (s.includes('/')) return s.split('/').map(x => x.trim()).filter(Boolean)
  if (s.includes('、')) return s.split('、').map(x => x.trim()).filter(Boolean)
  if (s.includes(',')) return s.split(',').map(x => x.trim()).filter(Boolean)
  return [s]
}

function displayBrand(row) {
  const brands = normalizeBrands(row.companyBrands || row.companyBrand || row.brand || '')
  return brands.join(' / ')
}

function avatarLetter(row) {
  const txt = displayBrand(row) || row.companyName || row.name || '?'
  return String(txt).charAt(0) || '?'
}

function avatarColor(row) {
  const colors = ['#6366f1', '#10b981', '#ec4899', '#f59e0b', '#14b8a6', '#8b5cf6']
  const seed = displayBrand(row) || row.companyName || row.name || ''
  let hash = 0
  for (let i = 0; i < seed.length; i++) hash = seed.charCodeAt(i) + ((hash << 5) - hash)
  return colors[Math.abs(hash) % colors.length]
}

function formatTime(val) {
  if (!val) return '—'
  return String(val).slice(0, 16).replace('T', ' ')
}

async function loadData() {
  loading.value = true
  try {
    const [accData, overviewResp] = await Promise.all([
      api.listAccounts(),
      publishApi.kbCustomerOverview().catch(() => ({ items: [] })),
    ])
    const list = Array.isArray(accData) ? accData : []
    const overviewItems = Array.isArray(overviewResp?.items) ? overviewResp.items : []
    const overviewMap = new Map(overviewItems.map(x => [Number(x.account_id || x.id), x]))

    rows.value = list.map((acc) => {
      const ov = overviewMap.get(Number(acc.id)) || {}
      // 优先从 localStorage 读取内容库文章数（文章存储在前端）
      let articleCount = 0
      try {
        const raw = localStorage.getItem(`content_library_articles_${acc.id}`)
        if (raw) {
          const arts = JSON.parse(raw)
          if (Array.isArray(arts)) articleCount = arts.length
        }
      } catch {}
      // 如果 localStorage 没有文章，回退到后端 KB 数量
      if (articleCount === 0) {
        articleCount = Number(ov.kb_count || ov.article_count || 0) || 0
      }
      const updatedAt = ov.latest_kb_at || ov.current_created_at || acc.updatedAt || acc.createdAt || ''
      return {
        ...acc,
        articleCount,
        updatedAt,
      }
    })
  } finally {
    loading.value = false
  }
}

function viewDetail(row) {
  router.push({
    path: `/publish/content-library/${row.id}`,
    query: {
      accountId: row.id,
      accountName: row.companyName || row.name || '',
      accountBrand: displayBrand(row),
    },
  })
}

onMounted(loadData)
</script>

<style scoped>
.publish-content-page { display: flex; flex-direction: column; gap: 18px; }

.kpi-strip { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.kpi-card {
  display: flex; align-items: center; gap: 14px;
  background: #fff; border: 1px solid #eef1f6; border-radius: 12px; padding: 18px 24px;
}
.kpi-icon {
  width: 44px; height: 44px; border-radius: 11px;
  display: flex; align-items: center; justify-content: center; font-size: 20px;
}
.kpi-icon-blue { background: #eef4ff; color: #3b82f6; }
.kpi-icon-green { background: #ecfdf5; color: #10b981; }
.kpi-icon-orange { background: #fff7ed; color: #f59e0b; }
.kpi-val { font-size: 28px; font-weight: 700; line-height: 1; color: #0f172a; }
.kpi-label { font-size: 13px; color: #94a3b8; margin-top: 4px; }

.panel {
  background: #fff; border: 1px solid #eef1f6; border-radius: 12px;
  padding: 16px 18px;
}

.toolbar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; margin-bottom: 10px; flex-wrap: wrap;
}
.toolbar-left { display: flex; align-items: center; gap: 12px; }
.search-input { width: 320px; max-width: 72vw; }
.count-text { font-size: 13px; color: #94a3b8; }

.content-table :deep(.el-table__row:hover > td) { background: #f8fafc !important; }
.customer-cell { display: flex; align-items: center; gap: 12px; }
.avatar {
  width: 40px; height: 40px; border-radius: 10px;
  color: #fff; font-weight: 700; font-size: 16px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.customer-info { min-width: 0; }
.brand-line {
  font-size: 14px; font-weight: 600; color: #0f172a;
  line-height: 1.25;
}
.company-line {
  margin-top: 4px; font-size: 13px; color: #94a3b8;
  line-height: 1.25;
}
.article-count { font-size: 14px; font-weight: 700; color: #1e293b; }
.time-cell { font-size: 13px; color: #475569; }
.view-link {
  font-size: 14px; color: #64748b; cursor: pointer; text-decoration: none;
}
.view-link:hover { color: #3b82f6; }
.table-empty { padding: 28px 0; text-align: center; color: #94a3b8; }

@media (max-width: 900px) {
  .kpi-strip { grid-template-columns: 1fr; }
  .kpi-val { font-size: 28px; }
  .brand-line, .article-count { font-size: 14px; }
}

@media (max-width: 640px) {
  .toolbar { align-items: stretch; }
  .toolbar-left { width: 100%; }
  .search-input { width: 100%; max-width: none; }
}
</style>
