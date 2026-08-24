<template>
  <div class="content-detail-page">
    <section class="panel">
      <div class="toolbar">
        <div class="toolbar-left">
          <button class="back-btn" @click="goBack">
            <el-icon><ArrowLeft /></el-icon>
            返回列表
          </button>
          <div class="account-meta">
            <div class="account-brand">{{ accountBrand || '—' }}</div>
            <div class="account-company">{{ accountName || '—' }}</div>
          </div>
        </div>
        <div class="toolbar-right">
          <el-input
            v-model="searchText"
            placeholder="搜索标题 / 正文"
            clearable
            :prefix-icon="Search"
            class="search-input"
          />
          <el-button :icon="Upload" type="primary" plain @click="showUpload = true">批量上传</el-button>
        </div>
      </div>
    </section>

    <section class="kpi-strip">
      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-blue"><el-icon><Document /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-val">{{ stats.total }}</div>
          <div class="kpi-label">文章数</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-green"><el-icon><Promotion /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-val">{{ stats.published }}</div>
          <div class="kpi-label">已发布</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-orange"><el-icon><EditPen /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-val">{{ stats.unpublished }}</div>
          <div class="kpi-label">未发布</div>
        </div>
      </div>
    </section>

    <section class="panel">
      <el-table
        :data="filteredRows"
        v-loading="loading"
        row-key="id"
        class="article-table"
        :header-cell-style="{ background: '#fafbfc', color: '#64748b', fontWeight: 600, fontSize: '13px' }"
      >
        <el-table-column label="标题" min-width="360">
          <template #default="{ row }">
            <div class="title-cell">
              <div class="title-main" :title="row.title">{{ row.title }}</div>
              <div class="title-sub" :title="row.content">{{ row.content }}</div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="生成方式" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="row.source === 'upload' ? 'warning' : 'success'" size="small" effect="plain">
              {{ row.source === 'upload' ? '上传' : 'AI' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="模型" width="140" align="center">
          <template #default="{ row }">
            <span>{{ row.source === 'upload' ? '—' : (row.model || 'qwen-plus') }}</span>
          </template>
        </el-table-column>

        <el-table-column label="语言" width="100" align="center">
          <template #default="{ row }">
            <span>{{ row.lang || '中文' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="更新时间" width="170" align="center" sortable prop="updatedAt">
          <template #default="{ row }">
            <span>{{ formatTime(row.updatedAt) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="160" align="center">
          <template #default="{ row }">
            <div class="status-cell">
              <el-tag :type="row.status === 'published' ? 'success' : 'info'" size="small" effect="plain">
                {{ row.status === 'published' ? '已发布' : '未发布' }}
              </el-tag>
              <button class="history-btn" @click="openHistory(row)">历史</button>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="250" align="right" fixed="right">
          <template #default="{ row }">
            <button class="op-link" @click="openView(row)">查看</button>
            <button class="op-link" @click="openEdit(row)">编辑</button>
            <button class="op-link" @click="publishRow(row)">发布</button>
            <button class="op-link danger" @click="removeRow(row)">删除</button>
          </template>
        </el-table-column>

        <template #empty>
          <div class="table-empty">暂无文章</div>
        </template>
      </el-table>
    </section>

    <!-- 批量上传 Dialog -->
    <el-dialog v-model="showUpload" title="批量上传文章" width="min(680px, 94vw)" destroy-on-close>
      <div class="upload-section">
        <div class="upload-tip">
          <p><strong>操作步骤：</strong></p>
          <ol>
            <li><a href="/templates/内容库批量上传模板.xlsx" download target="_blank">下载 Excel 模板</a></li>
              <li>按模板格式填写标题和正文（正文支持<strong>纯文本 / HTML / Markdown</strong> 格式）</li>
              <li>选择文件后预览确认，再点击导入</li>
            </ol>
            <div style="margin-top:8px;padding:8px;background:#fefce8;border-radius:6px;font-size:12px;color:#854d0e;">
              💡 正文格式说明：系统会自动识别 HTML 标签，纯文本和 Markdown 均可正常保存
            </div>
        </div>

        <el-upload
          ref="uploadRef"
          accept=".xlsx,.xls"
          :auto-upload="false"
          :limit="1"
          :on-change="handleFileChange"
          :on-remove="() => previewRows = []"
          drag
          class="upload-dragger"
        >
          <el-icon :size="40"><UploadFilled /></el-icon>
          <div style="margin-top: 8px">将 Excel 文件拖到此处，或<em>点击选择</em></div>
          <template #tip>
            <div class="el-upload__text">仅支持 .xlsx / .xls 格式</div>
          </template>
        </el-upload>
        
        <div v-if="previewRows.length" class="preview-area">
          <div class="preview-header">
            <span>预览（共 {{ previewRows.length }} 篇，将跳过重复标题）</span>
          </div>
          <el-table :data="previewRows.slice(0, 10)" max-height="280" size="small" border>
            <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
            <el-table-column prop="content" label="正文预览" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                <span>{{ (row.content || '').slice(0, 60) }}{{ (row.content || '').length > 60 ? '...' : '' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="lang" label="语言" width="80" align="center" />
          </el-table>
          <div v-if="previewRows.length > 10" class="preview-more">
            还有 {{ previewRows.length - 10 }} 篇未显示...
          </div>
        </div>
      </div>
      
      <template #footer>
        <el-button @click="showUpload = false; previewRows = []">取消</el-button>
        <el-button type="primary" :loading="uploading" :disabled="!previewRows.length" @click="doBatchUpload">
          导入 {{ previewRows.length }} 篇文章
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'view' ? '查看文章' : '编辑文章'"
      width="min(820px, 94vw)"
      top="6vh"
    >
      <el-form label-position="top">
        <el-form-item label="标题">
          <el-input v-model="form.title" :readonly="!isEditing" />
        </el-form-item>
        <el-form-item label="正文内容">
          <el-input v-model="form.content" type="textarea" :rows="14" :readonly="!isEditing" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">关闭</el-button>
        <el-button v-if="!isEditing" type="primary" @click="isEditing = true">编辑</el-button>
        <el-button v-else type="primary" @click="saveCurrent">保存</el-button>
      </template>
    </el-dialog>

    <!-- 发布历史 Dialog -->
    <el-dialog v-model="historyVisible" title="发布历史" width="min(720px, 94vw)">
      <el-table :data="historyRows" size="small" border v-loading="false">
        <el-table-column prop="title" label="发布标题" min-width="200" show-overflow-tooltip />
        <el-table-column label="发布类型" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="row.publishType === '官网' ? 'warning' : 'success'" size="small" effect="plain">
              {{ row.publishType }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="发布地址" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <a v-if="row.url" :href="row.url" target="_blank" class="history-url">{{ row.url }}</a>
            <span v-else style="color: #94a3b8">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="publishedAt" label="发布时间" width="160" align="center" />
      </el-table>
      <div v-if="!historyRows.length" class="table-empty">暂无发布历史</div>
      <template #footer>
        <el-button @click="historyVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Search, Document, Promotion, EditPen, Upload, UploadFilled } from '@element-plus/icons-vue'
import * as XLSX from 'xlsx'
import api from '@/api'

const route = useRoute()
const router = useRouter()

const accountId = computed(() => Number(route.params.accountId || route.query.accountId || 0))
const accountName = ref(String(route.query.accountName || ''))
const accountBrand = ref(String(route.query.accountBrand || ''))

const loading = ref(false)
const searchText = ref('')
const rows = ref([])

const dialogVisible = ref(false)
const dialogMode = ref('view') // view | edit
const isEditing = ref(false)
const currentId = ref(null)
const form = reactive({ title: '', content: '' })

// 发布历史
const historyVisible = ref(false)
const historyRows = ref([])

const stats = computed(() => {
  const total = rows.value.length
  const published = rows.value.filter(x => x.status === 'published').length
  return { total, published, unpublished: total - published }
})

const filteredRows = computed(() => {
  const q = searchText.value.trim().toLowerCase()
  let result = rows.value
  if (q) {
    result = result.filter((x) => {
      const t = String(x.title || '').toLowerCase()
      const c = String(x.content || '').toLowerCase()
      return t.includes(q) || c.includes(q)
    })
  }
  // 按更新时间倒序排列
  return [...result].sort((a, b) => {
    const ta = a.updatedAt || a.createdAt || ''
    const tb = b.updatedAt || b.createdAt || ''
    return tb.localeCompare(ta)
  })
})

function storageKey() {
  return `content_library_articles_${accountId.value || 'unknown'}`
}

function nowStr() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function persist() {
  localStorage.setItem(storageKey(), JSON.stringify(rows.value))
}

function loadRows() {
  loading.value = true
  try {
    const raw = localStorage.getItem(storageKey())
    rows.value = raw ? (JSON.parse(raw) || []) : []
  } catch {
    rows.value = []
  } finally {
    loading.value = false
  }
}

function formatTime(val) {
  if (!val) return '—'
  return String(val).slice(0, 16).replace('T', ' ')
}

function openView(row) {
  dialogMode.value = 'view'
  isEditing.value = false
  currentId.value = row.id
  form.title = row.title || ''
  form.content = row.content || ''
  dialogVisible.value = true
}

function openEdit(row) {
  dialogMode.value = 'edit'
  isEditing.value = true
  currentId.value = row.id
  form.title = row.title || ''
  form.content = row.content || ''
  dialogVisible.value = true
}

function saveCurrent() {
  if (!form.title.trim()) { ElMessage.warning('请输入标题'); return }
  const idx = rows.value.findIndex(x => x.id === currentId.value)
  if (idx < 0) return
  rows.value[idx] = {
    ...rows.value[idx],
    title: form.title,
    content: form.content,
    updatedAt: nowStr(),
  }
  persist()
  dialogVisible.value = false
  ElMessage.success('保存成功')
}

function publishRow(row) {
  const idx = rows.value.findIndex(x => x.id === row.id)
  if (idx >= 0) {
    rows.value[idx] = { ...rows.value[idx], status: 'published', updatedAt: nowStr() }
    persist()
  }
  router.push({
    path: `/publish/content-publish/${accountId.value}`,
    query: {
      accountId: accountId.value,
      articleId: row.id,
      accountName: accountName.value,
      accountBrand: accountBrand.value,
    },
  })
  ElMessage.success('已进入发布页面')
}

function openHistory(row) {
  const history = []
  // 从文章的 publishHistory 字段读取（如果存在）
  if (Array.isArray(row.publishHistory)) {
    for (const h of row.publishHistory) {
      history.push({
        title: h.title || row.title || '',
        publishType: h.publishType || (h.platform === 'official' ? '官网' : '资源站'),
        url: h.url || '',
        publishedAt: h.publishedAt || h.time || '',
      })
    }
  }
  // 如果没有 publishHistory，但有发布记录信息，构造一条
  if (history.length === 0 && row.status === 'published') {
    const platformLabel = row.publishPlatform === 'official' ? '官网' : '资源站'
    const urls = Array.isArray(row.postUrls) ? row.postUrls : []
    if (urls.length > 0) {
      for (const url of urls) {
        history.push({
          title: row.title || '',
          publishType: platformLabel,
          url: url,
          publishedAt: row.publishedAt || row.updatedAt || '',
        })
      }
    } else {
      history.push({
        title: row.title || '',
        publishType: platformLabel,
        url: '',
        publishedAt: row.publishedAt || row.updatedAt || '',
      })
    }
  }
  historyRows.value = history
  historyVisible.value = true
}

async function removeRow(row) {
  try {
    await ElMessageBox.confirm('确认删除该文章吗？删除后不可恢复。', '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    rows.value = rows.value.filter(x => x.id !== row.id)
    persist()
    ElMessage.success('删除成功')
  } catch {}
}

// ── 批量上传 ──
const showUpload = ref(false)
const uploading = ref(false)
const uploadRef = ref()
const previewRows = ref([])

function handleFileChange(file) {
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const wb = XLSX.read(e.target.result, { type: 'array' })
      const ws = wb.Sheets[wb.SheetNames[0]]
      const data = XLSX.utils.sheet_to_json(ws, { header: ['title', 'content', 'lang'] })
      
      // 跳过表头
      let startIdx = 0
      if (data.length && /^(title|标题|Title)$/i.test(data[0].title)) {
        startIdx = 1
      }
      
      // 过滤有效数据：标题非空
      const valid = []
      for (let i = startIdx; i < data.length; i++) {
        const row = data[i]
        if (row.title && String(row.title).trim()) {
          valid.push({
            title: String(row.title).trim(),
            content: String(row.content || '').trim(),
            lang: String(row.lang || '中文').trim() || '中文',
          })
        }
      }
      
      // 去重（按标题）
      const existingTitles = new Set(rows.value.map(r => r.title))
      previewRows.value = valid.filter(v => !existingTitles.has(v.title))
      
      if (!previewRows.value.length && valid.length) {
        ElMessage.warning('所有文章的标题与现有内容重复')
      } else if (valid.length !== previewRows.value.length + (startIdx ? 1 : 0)) {
        ElMessage.info(`已跳过 ${valid.length - previewRows.value.length} 篇重复文章`)
      }
    } catch (err) {
      console.error('Parse error:', err)
      ElMessage.error('文件解析失败，请检查格式')
      previewRows.value = []
    }
  }
  reader.readAsArrayBuffer(file.raw)
}

async function doBatchUpload() {
  if (!previewRows.value.length) return
  uploading.value = true
  try {
    const newArticles = previewRows.value.map((item, idx) => ({
      id: `batch_${Date.now()}_${idx}`,
      title: item.title,
      content: item.content,
      model: '',
      lang: item.lang || '中文',
      source: 'upload',  // 标记来源为上传
      status: 'unpublished',
      createdAt: nowStr(),
      updatedAt: nowStr(),
    }))
    rows.value = [...rows.value, ...newArticles]
    persist()
    ElMessage.success(`成功导入 ${newArticles.length} 篇文章`)
    showUpload.value = false
    previewRows.value = []
    if (uploadRef.value) uploadRef.value.clearFiles()
  } catch (e) {
    ElMessage.error('导入失败：' + (e.message || e))
  } finally {
    uploading.value = false
  }
}

function goBack() {
  router.push('/publish/content-library')
}

onMounted(loadRows)

onMounted(async () => {
  if (!accountId.value) return
  if (accountName.value && accountBrand.value) return
  try {
    const acc = await api.getAccount(accountId.value)
    accountName.value = accountName.value || acc?.companyName || ''
    accountBrand.value = accountBrand.value || acc?.companyBrand || ''
  } catch {
    // ignore
  }
})
</script>

<style scoped>
.content-detail-page { display: flex; flex-direction: column; gap: 16px; }

.panel {
  background: #fff;
  border: 1px solid #eef1f6;
  border-radius: 12px;
  padding: 16px 18px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-left { display: flex; align-items: center; gap: 12px; }
.toolbar-right { margin-left: auto; }
.search-input { width: 300px; }

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 7px 12px;
  border-radius: 8px;
  border: 1px solid #dbe2ea;
  background: #fff;
  color: #334155;
  cursor: pointer;
}
.back-btn:hover { background: #f8fafc; }

.account-meta { display: flex; flex-direction: column; }
.account-brand { font-size: 15px; font-weight: 700; color: #0f172a; }
.account-company { font-size: 12px; color: #94a3b8; margin-top: 2px; }

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

.article-table :deep(.el-table__row:hover > td) { background: #f8fafc !important; }
.title-cell { min-width: 0; }
.title-main {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.title-sub {
  margin-top: 4px;
  font-size: 12px;
  color: #94a3b8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.op-link {
  border: none;
  background: transparent;
  color: #2563eb;
  cursor: pointer;
  font-size: 13px;
  margin-left: 10px;
}
.op-link.danger { color: #dc2626; }
.op-link:hover { text-decoration: underline; }

.status-cell { display: flex; align-items: center; justify-content: center; gap: 8px; }
.history-btn {
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #64748b;
  border-radius: 4px;
  padding: 2px 8px;
  cursor: pointer;
  font-size: 12px;
  white-space: nowrap;
}
.history-btn:hover { background: #f1f5f9; color: #334155; }
.history-url { color: #2563eb; text-decoration: none; font-size: 12px; }
.history-url:hover { text-decoration: underline; }

.table-empty { padding: 28px 0; text-align: center; color: #94a3b8; }

/* 批量上传 */
.upload-section { display: flex; flex-direction: column; gap: 16px; }
.upload-tip {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 14px 18px;
  font-size: 13px;
  color: #475569;
}
.upload-tip p { margin: 0 0 6px; }
.upload-tip ol { margin: 0; padding-left: 20px; }
.upload-tip li { margin-bottom: 4px; }
.upload-tip a { color: #2563eb; text-decoration: none; }
.upload-tip a:hover { text-decoration: underline; }
.upload-dragger { width: 100%; }
.preview-area { border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; }
.preview-header {
  background: #f1f5f9;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  border-bottom: 1px solid #e2e8f0;
}
.preview-more {
  padding: 8px 14px;
  text-align: center;
  font-size: 12px;
  color: #94a3b8;
  background: #fafbfc;
  border-top: 1px solid #f1f5f9;
}

@media (max-width: 900px) {
  .kpi-strip { grid-template-columns: 1fr; }
  .search-input { width: 100%; }
}
</style>
