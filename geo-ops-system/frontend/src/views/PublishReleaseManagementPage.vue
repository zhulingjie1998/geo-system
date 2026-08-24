<template>
  <div class="release-management-page">
    <section class="kpi-strip">
      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-blue">客</div>
        <div class="kpi-body">
          <div class="kpi-val">{{ overview.customerTotal }}</div>
          <div class="kpi-label">客户总数</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-green">发</div>
        <div class="kpi-body">
          <div class="kpi-val">{{ overview.publishTotal }}</div>
          <div class="kpi-label">发布数量</div>
        </div>
      </div>
    </section>

    <section class="panel">
      <el-table
        :data="rows"
        v-loading="loading"
        row-key="id"
        :header-cell-style="{ background: '#fafbfc', color: '#64748b', fontWeight: 600, fontSize: '13px' }"
      >
        <el-table-column label="客户" min-width="320">
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

        <el-table-column label="官网发布数" width="160" align="center">
          <template #default="{ row }">
            <span class="num official">{{ row.officialCount }}</span>
          </template>
        </el-table-column>

        <el-table-column label="资源站发布数" width="170" align="center">
          <template #default="{ row }">
            <span class="num resource">{{ row.resourceCount }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="120" align="right">
          <template #default="{ row }">
            <a class="view-link" @click="viewRecords(row)">查看 ›</a>
          </template>
        </el-table-column>

        <template #empty>
          <div class="table-empty">暂无发布记录</div>
        </template>
      </el-table>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api'

const router = useRouter()
const loading = ref(false)
const rows = ref([])

function storageKey(id) {
  return `content_library_articles_${id || 'unknown'}`
}

function parseArticles(accountId) {
  const raw = localStorage.getItem(storageKey(accountId))
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

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

function successfulCount(articles, platform) {
  return articles.filter((item) => item?.status === 'published' && item?.publishPlatform === platform).length
}

const overview = computed(() => {
  const customerTotal = rows.value.length
  const publishTotal = rows.value.reduce((sum, item) => sum + Number(item.officialCount || 0) + Number(item.resourceCount || 0), 0)
  return { customerTotal, publishTotal }
})

async function loadData() {
  loading.value = true
  try {
    const list = await api.listAccounts()
    const accounts = Array.isArray(list) ? list : []
    rows.value = accounts.map((account) => {
      const articles = parseArticles(account.id)
      const officialCount = successfulCount(articles, 'official')
      const resourceCount = successfulCount(articles, 'resource')
      return {
        ...account,
        officialCount,
        resourceCount,
      }
    }).sort((a, b) => {
      const ta = a.updatedAt || a.createdAt || ''
      const tb = b.updatedAt || b.createdAt || ''
      return tb.localeCompare(ta)
    })
  } finally {
    loading.value = false
  }
}

function viewRecords(row) {
  router.push({
    path: `/publish/releases/${row.id}`,
    query: {
      accountName: row.companyName || row.name || '',
      accountBrand: displayBrand(row),
    },
  })
}

onMounted(loadData)
</script>

<style scoped>
.release-management-page { display: flex; flex-direction: column; gap: 16px; }

.kpi-strip { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.kpi-card {
  display: flex; align-items: center; gap: 14px;
  background: #fff; border: 1px solid #eef1f6; border-radius: 12px; padding: 18px 24px;
}
.kpi-icon {
  width: 44px; height: 44px; border-radius: 11px;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; font-weight: 700;
}
.kpi-icon-blue { background: #eef4ff; color: #3b82f6; }
.kpi-icon-green { background: #ecfdf5; color: #10b981; }
.kpi-val { font-size: 28px; font-weight: 700; line-height: 1; color: #0f172a; }
.kpi-label { font-size: 13px; color: #94a3b8; margin-top: 4px; }

.panel {
  background: #fff;
  border: 1px solid #eef1f6;
  border-radius: 12px;
  padding: 14px 16px;
}

.customer-cell { display: flex; align-items: center; gap: 12px; }
.avatar {
  width: 40px; height: 40px; border-radius: 10px;
  color: #fff; font-weight: 700; font-size: 16px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.brand-line { font-size: 14px; font-weight: 600; color: #0f172a; line-height: 1.25; }
.company-line { margin-top: 4px; font-size: 13px; color: #94a3b8; line-height: 1.25; }

.num { font-size: 16px; font-weight: 700; }
.num.official { color: #2563eb; }
.num.resource { color: #0f766e; }

.view-link {
  font-size: 14px; color: #64748b; cursor: pointer; text-decoration: none;
}
.view-link:hover { color: #2563eb; }
.table-empty { padding: 28px 0; text-align: center; color: #94a3b8; }

@media (max-width: 900px) {
  .kpi-strip { grid-template-columns: 1fr; }
}
</style>
