<template>
  <div class="release-records-page">
    <section class="panel toolbar-panel">
      <div class="toolbar-left">
        <button class="back-btn" @click="goBack">← 返回发布管理</button>
        <div class="account-meta">
          <div class="account-brand">{{ accountBrandText || '—' }}</div>
          <div class="account-company">{{ accountNameText || '—' }}</div>
        </div>
      </div>

      <div class="toolbar-right">
        <el-select v-model="typeFilter" placeholder="发布类型" clearable class="filter-select">
          <el-option label="官网发布" value="official" />
          <el-option label="资源站发布" value="resource" />
        </el-select>

        <el-select v-model="statusFilter" placeholder="发布状态" clearable class="filter-select">
          <el-option label="已发布" value="published" />
          <el-option label="待发布" value="pending" />
          <el-option label="发布失败" value="failed" />
        </el-select>
      </div>
    </section>

    <section class="panel">
      <el-table
        :data="filteredRows"
        row-key="id"
        :header-cell-style="{ background: '#fafbfc', color: '#64748b', fontWeight: 600, fontSize: '13px' }"
      >
        <el-table-column label="文章标题" min-width="300" prop="title" />

        <el-table-column label="文章语言" width="120" align="center">
          <template #default="{ row }">{{ row.lang || '中文' }}</template>
        </el-table-column>

        <el-table-column label="发布类型" width="130" align="center">
          <template #default="{ row }">{{ typeLabel(row.publishPlatform) }}</template>
        </el-table-column>

        <el-table-column label="平台数量" width="120" align="center">
          <template #default="{ row }">{{ platformCount(row) }}</template>
        </el-table-column>

        <el-table-column label="发布状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag
              :type="row.status === 'published' ? 'success' : row.status === 'pending' ? 'warning' : row.status === 'failed' ? 'danger' : 'info'"
              effect="plain"
              size="small"
            >
              {{ row.status === 'published' ? '已发布' : row.status === 'pending' ? '待发布' : row.status === 'failed' ? '发布失败' : '未发布' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="落地页" width="180" align="center">
          <template #default="{ row }">
            <template v-if="row.postUrls && row.postUrls.length">
              <a
                v-for="(url, i) in row.postUrls"
                :key="i"
                :href="url"
                target="_blank"
                rel="noopener noreferrer"
                class="post-url-link"
              >
                {{ url.replace(/^https?:\/\//, '').slice(0, 25) }}{{ url.length > 30 ? '...' : '' }}
              </a>
            </template>
            <span v-else style="color: #c0c4cc">—</span>
          </template>
        </el-table-column>

        <el-table-column label="发布时间" width="180" align="center">
          <template #default="{ row }">{{ publishTime(row) }}</template>
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
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'

const route = useRoute()
const router = useRouter()

const accountId = computed(() => Number(route.params.accountId || 0))
const accountNameText = ref(String(route.query.accountName || ''))
const accountBrandText = ref(String(route.query.accountBrand || ''))

const rows = ref([])
const typeFilter = ref('')
const statusFilter = ref('')

function storageKey(id) {
  return `content_library_articles_${id || 'unknown'}`
}

function parseArticles(id) {
  const raw = localStorage.getItem(storageKey(id))
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

function typeLabel(type) {
  return type === 'official' ? '官网发布' : type === 'resource' ? '资源站发布' : '—'
}

function platformCount(row) {
  if (Array.isArray(row.platforms)) return row.platforms.length
  const n = Number(row.platformCount || 0)
  if (n > 0) return n
  return row.publishPlatform ? 1 : 0
}

function publishTime(row) {
  return row.publishedAt || row.scheduledAt || row.updatedAt || '—'
}

const filteredRows = computed(() => {
  const filtered = rows.value.filter((row) => {
    const typeOk = !typeFilter.value || row.publishPlatform === typeFilter.value
    const statusOk = !statusFilter.value || row.status === statusFilter.value
    return typeOk && statusOk
  })
  return [...filtered].sort((a, b) => {
    const ta = a.publishedAt || a.scheduledAt || a.updatedAt || ''
    const tb = b.publishedAt || b.scheduledAt || b.updatedAt || ''
    return tb.localeCompare(ta)
  })
})

async function loadHeaderMetaIfMissing() {
  if (accountNameText.value && accountBrandText.value) return
  try {
    const list = await api.listAccounts()
    const account = (Array.isArray(list) ? list : []).find((item) => Number(item.id) === accountId.value)
    if (!account) return
    if (!accountNameText.value) accountNameText.value = account.companyName || account.name || ''
    if (!accountBrandText.value) {
      const brands = normalizeBrands(account.companyBrands || account.companyBrand || account.brand || '')
      accountBrandText.value = brands.join(' / ')
    }
  } catch {
    // ignore
  }
}

function loadRows() {
  const all = parseArticles(accountId.value)
  // 只显示有发布记录的文章（已发布、待发布、发布失败），排除从未发布过的文章
  rows.value = all
    .filter((item) => item.status === 'published' || item.status === 'pending' || item.status === 'failed')
    .map((item) => ({
      ...item,
      lang: item.lang || '中文',
    }))
}

function goBack() {
  router.push('/publish/releases')
}

onMounted(async () => {
  await loadHeaderMetaIfMissing()
  loadRows()
})
</script>

<style scoped>
.release-records-page { display: flex; flex-direction: column; gap: 16px; }

.panel {
  background: #fff;
  border: 1px solid #eef1f6;
  border-radius: 12px;
  padding: 14px 16px;
}

.toolbar-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-left { display: flex; align-items: center; gap: 12px; }
.toolbar-right { display: flex; align-items: center; gap: 10px; }

.back-btn {
  border: 1px solid #dbe2ea;
  background: #fff;
  color: #334155;
  border-radius: 8px;
  padding: 8px 12px;
  cursor: pointer;
}

.post-url-link {
  color: #409eff;
  text-decoration: none;
  font-size: 12px;
  display: inline-block;
  margin: 2px 0;
}
.post-url-link:hover {
  text-decoration: underline;
  color: #66b1ff;
}
.back-btn:hover { background: #f8fafc; }

.account-meta { display: flex; flex-direction: column; }
.account-brand { font-size: 15px; font-weight: 700; color: #0f172a; }
.account-company { font-size: 12px; color: #94a3b8; margin-top: 2px; }

.filter-select { width: 150px; }
.table-empty { padding: 28px 0; text-align: center; color: #94a3b8; }

@media (max-width: 900px) {
  .toolbar-right { width: 100%; }
  .filter-select { width: 100%; }
}
</style>
