<template>
  <div class="publish-publish-page">
    <section class="panel hero-panel">
      <div class="hero-top">
        <button class="back-btn" @click="goBack">
          <span>←</span>
          返回内容库
        </button>
      </div>

      <div class="hero-grid">
        <div class="field-card">
          <label class="field-label">客户</label>
          <el-select v-model="selectedAccountId" filterable placeholder="选择客户" @change="handleAccountChange">
            <el-option
              v-for="item in accounts"
              :key="item.id"
              :label="item.companyName || item.name || '—'"
              :value="Number(item.id)"
            />
          </el-select>
        </div>
        <div class="field-card">
          <label class="field-label">文章</label>
          <el-select v-model="selectedArticleId" placeholder="选择文章" @change="handleArticleChange">
            <el-option
              v-for="item in articles"
              :key="item.id"
              :label="item.title || '未命名文章'"
              :value="item.id"
            />
          </el-select>
        </div>
      </div>
    </section>

    <section class="panel editor-panel" v-if="selectedArticle">
      <div class="field-block">
        <label class="field-label">标题</label>
        <el-input v-model="draftTitle" placeholder="请输入文章标题" />
      </div>

      <div class="field-block">
        <label class="field-label">正文</label>
        <div class="rtf-shell">
          <Toolbar class="rtf-toolbar" :editor="editorRef" :defaultConfig="toolbarConfig" mode="default" />
          <Editor
            class="rtf-editor"
            v-model="draftContent"
            :defaultConfig="editorConfig"
            mode="default"
            @onCreated="handleCreated"
          />
        </div>
      </div>

      <div class="field-grid">
        <div class="field-block">
          <label class="field-label">发布平台</label>
          <el-select v-model="publishPlatform" placeholder="选择平台" @change="handlePlatformChange">
            <el-option label="官网" value="official" />
            <el-option label="资源站（WordPress）" value="resource" />
          </el-select>
          <div v-if="publishPlatform === 'official' && !hasOfficialConfig" class="hint-warning">
            当前客户未完成官网 HTTP 设置，暂不支持官网发布。请先到「资源 - 官网配置」完成设置。
          </div>
        </div>

        <!-- 资源站选择 -->
        <div v-if="publishPlatform === 'resource'" class="field-block">
          <label class="field-label">
            目标站点
            <span class="select-all-hint">
              <button
                v-for="group in groupedSites"
                :key="'btn-' + group.label"
                class="select-all-btn"
                @click="selectAllConnected(group)"
              >全选{{ group.label }}</button>
              <button class="select-all-btn deselect-btn" @click="deselectAllSites">取消全选</button>
            </span>
          </label>
          <el-select
            v-model="selectedSiteIds"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择要发布的 WordPress 站点（可多选）"
            style="width: 100%"
          >
            <el-option-group v-for="group in groupedSites" :key="group.label" :label="group.label">
              <el-option
                v-for="s in group.options"
                :key="s.id"
                :label="`${s.site_name} (${s.site_url})${s.last_test_result === 'ok' ? '' : ' [未连通]'}`"
                :value="s.id"
                :disabled="s.last_test_result !== 'ok'"
              >
                <span style="font-weight: 500">{{ s.site_name }}</span>
                <span style="color: #909399; font-size: 12px; margin-left: 8px">{{ s.site_url }}</span>
                <el-tag v-if="s.last_test_result === 'ok'" size="small" type="success" style="margin-left: 8px">已连通</el-tag>
                <el-tag v-else size="small" type="danger" style="margin-left: 8px">未连通</el-tag>
              </el-option>
            </el-option-group>
          </el-select>
          <div v-if="!resourceSites.length" class="hint-warning">
            暂无可用资源站点。请到「资源管理」中添加 WordPress 站点。
          </div>
        </div>

        <div class="field-block">
          <label class="field-label">发布时间</label>
          <el-select v-model="publishMode" placeholder="选择发布模式">
            <el-option label="立即发布" value="immediate" />
            <el-option label="定时发布" value="scheduled" />
          </el-select>
        </div>
      </div>

      <div class="field-block" v-if="publishMode === 'scheduled'">
        <label class="field-label">定时发布时间</label>
        <el-date-picker
          v-model="scheduledAt"
          type="datetime"
          value-format="yyyy-MM-dd HH:mm:ss"
          placeholder="请选择定时发布时间"
        />
      </div>

      <div class="actions">
        <el-button @click="goBack">取消</el-button>
        <el-button type="primary" :loading="publishing" @click="saveAndPublish">
          {{ publishing ? '发布中...' : '保存并发布' }}
        </el-button>
      </div>
    </section>

    <section class="panel empty-panel" v-else>
      <div class="empty-title">该客户暂无可发布文章</div>
      <div class="empty-sub">请先回到内容库新增或生成文章。</div>
    </section>
  </div>
</template>

<script setup>
import '@wangeditor/editor/dist/css/style.css'
import { ref, computed, onMounted, onBeforeUnmount, watch, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import api from '@/api'
import publishApi from '@/api/publish'
import resourceApi from '@/api/resource'

const route = useRoute()
const router = useRouter()

const accountId = computed(() => Number(route.params.accountId || route.query.accountId || 0))
// articleId 支持字符串和数字格式（批量上传的文章ID为字符串如 "batch_xxx"）
const articleId = computed(() => {
  const raw = route.query.articleId || route.params.articleId
  // 如果是纯数字则转为Number，否则保留字符串
  return /^\d+$/.test(String(raw)) ? Number(raw) : String(raw)
})

const accounts = ref([])
const articles = ref([])
const selectedAccountId = ref(accountId.value || 0)
// selectedArticleId 支持字符串和数字
const selectedArticleId = ref(articleId.value || 0)
const draftTitle = ref('')
const draftContent = ref('')
const publishPlatform = ref('resource')
const publishMode = ref('immediate')
const scheduledAt = ref('')
const hasOfficialConfig = ref(false)
const editorRef = shallowRef()

// 资源站选择
const resourceSites = ref([])
const selectedSiteIds = ref([])
const publishing = ref(false) // 发布加载状态

const toolbarConfig = {
  toolbarKeys: [
    'headerSelect',
    '|',
    'bold',
    'underline',
    'italic',
    '|',
    'color',
    'bgColor',
    '|',
    'fontSize',
    'fontFamily',
    'lineHeight',
    '|',
    'bulletedList',
    'numberedList',
    '|',
    'justifyLeft',
    'justifyCenter',
    'justifyRight',
    'justifyJustify',
    '|',
    'insertLink',
    'uploadImage',
    'insertTable',
    '|',
    'fullScreen',
    'undo',
    'redo',
  ],
}

const editorConfig = {
  placeholder: '请输入正文内容...',
  MENU_CONF: {
    uploadImage: {
      customUpload: async (file, insertFn) => {
        const res = await publishApi.uploadImg(file)
        const url = res?.url || res?.data?.url || ''
        if (!url) throw new Error('图片上传失败')
        insertFn(url, file.name || 'image', url)
      },
    },
  },
}

// 使用字符串比较，兼容数字ID（如123）和字符串ID（如"batch_xxx"）
const selectedArticle = computed(() => {
  if (!selectedArticleId.value) return null
  return articles.value.find((item) => String(item.id) === String(selectedArticleId.value)) || null
})

// 资源站按类型分组
const groupedSites = computed(() => {
  const typeMap = { blog: '博客', forum: '论坛', b2b: 'B2B', qa: '问答' }
  const groups = {}
  for (const s of resourceSites.value) {
    const label = typeMap[s.site_type] || s.site_type
    if (!groups[label]) groups[label] = []
    groups[label].push(s)
  }
  return Object.entries(groups).map(([label, options]) => ({ label, options }))
})

function selectAllConnected(group) {
  const connectedIds = group.options
    .filter(s => s.last_test_result === 'ok')
    .map(s => s.id)
  const existing = new Set(selectedSiteIds.value)
  for (const id of connectedIds) {
    if (!existing.has(id)) existing.add(id)
  }
  selectedSiteIds.value = Array.from(existing)
}

function deselectAllSites() {
  selectedSiteIds.value = []
}

function nowStr() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function storageKey(id) {
  return `content_library_articles_${id || 'unknown'}`
}

function loadArticles(accountIdValue) {
  const raw = localStorage.getItem(storageKey(accountIdValue))
  let parsed = []
  try {
    parsed = raw ? JSON.parse(raw) : []
  } catch {
    parsed = []
  }

  articles.value = Array.isArray(parsed) ? parsed : []

  // 使用字符串比较，兼容批量上传的字符串ID
  const current = articles.value.find((item) => String(item.id) === String(selectedArticleId.value))
  if (current) {
    selectedArticleId.value = current.id
  } else if (articles.value.length) {
    selectedArticleId.value = articles.value[0].id
  } else {
    selectedArticleId.value = 0
  }
  syncDraftFromArticle()
}

function persistArticles(accountIdValue) {
  localStorage.setItem(storageKey(accountIdValue), JSON.stringify(articles.value))
}

async function loadAccounts() {
  try {
    const list = await api.listAccounts()
    accounts.value = Array.isArray(list) ? list : []
  } catch {
    accounts.value = []
  }
}

function syncDraftFromArticle() {
  const article = selectedArticle.value
  if (!article) {
    draftTitle.value = ''
    draftContent.value = ''
    return
  }
  draftTitle.value = article.title || ''
  draftContent.value = article.content || ''
  publishPlatform.value = article.publishPlatform || 'resource'
  publishMode.value = article.publishMode || 'immediate'
  scheduledAt.value = article.scheduledAt || ''
}

function handleAccountChange() {
  const id = Number(selectedAccountId.value)
  selectedArticleId.value = 0
  loadArticles(id)
  loadOfficialConfigStatus(id)
  router.replace({
    path: `/publish/content-publish/${id}`,
    query: {
      accountId: id,
    },
  })
}

function handleArticleChange() {
  syncDraftFromArticle()
}

function handleCreated(editor) {
  editorRef.value = editor
}

function handlePlatformChange(val) {
  if (val === 'official' && !hasOfficialConfig.value) {
    ElMessage.warning('该客户未配置官网 HTTP 设置，无法选择官网发布')
    publishPlatform.value = 'resource'
  }
}

async function loadOfficialConfigStatus(accountIdValue) {
  if (!accountIdValue) {
    hasOfficialConfig.value = false
    return
  }
  try {
    const cfg = await publishApi.officialConfigGet(accountIdValue)
    hasOfficialConfig.value = !!cfg?.configured
    if (!hasOfficialConfig.value && publishPlatform.value === 'official') {
      publishPlatform.value = 'resource'
    }
  } catch {
    hasOfficialConfig.value = false
    if (publishPlatform.value === 'official') {
      publishPlatform.value = 'resource'
    }
  }
}

// 加载资源站点列表（用于选择发布目标）
async function loadResourceSites() {
  try {
    const r = await resourceApi.listSites()
    resourceSites.value = r?.items || []
  } catch (e) {
    console.warn('加载资源站点失败', e)
    resourceSites.value = []
  }
}

function goBack() {
  router.push({
    path: `/publish/content-library/${selectedAccountId.value}`,
    query: {
      accountId: selectedAccountId.value,
      accountName: accounts.value.find((item) => Number(item.id) === Number(selectedAccountId.value))?.companyName || '',
    },
  })
}

async function saveAndPublish() {
  if (!selectedArticle.value) {
    ElMessage.warning('请选择一篇文章')
    return
  }
  if (!draftTitle.value.trim()) {
    ElMessage.warning('请输入标题')
    return
  }
  if (publishMode.value === 'scheduled' && !scheduledAt.value) {
    ElMessage.warning('请选择定时发布时间')
    return
  }
  if (publishPlatform.value === 'official' && !hasOfficialConfig.value) {
    ElMessage.warning('该客户未配置官网 HTTP 设置，请先到「资源 - 官网配置」完成设置')
    return
  }
  if (publishPlatform.value === 'resource' && !selectedSiteIds.value.length) {
    ElMessage.warning('请选择至少一个目标站点')
    return
  }

  publishing.value = true

  // 使用字符串比较，兼容批量上传的字符串ID
  const idx = articles.value.findIndex((item) => String(item.id) === String(selectedArticleId.value))
  if (idx < 0) { publishing.value = false; return }

  let status = publishMode.value === 'scheduled' ? 'pending' : 'published'
  let postUrls = [] // 存储落地页URL
  let publishFailed = false

  // ── 资源站发布（WordPress）──
  if (publishPlatform.value === 'resource') {
    try {
      const r = await resourceApi.publish({
        site_ids: selectedSiteIds.value,
        account_id: Number(selectedAccountId.value),
        article_id: selectedArticleId.value,
        title: draftTitle.value.trim(),
        content: draftContent.value || draftTitle.value.trim(),
        status: publishMode.value === 'immediate' ? 'publish' : 'draft',
      })
      const ok = r.results?.filter(x => x.ok) || []
      const fail = r.results?.filter(x => !x.ok) || []
      // 收集成功发布的落地页URL
      postUrls = ok.map(x => x.post_url || '').filter(Boolean)
      if (fail.length === 0) {
        ElMessage.success(`已成功发布到 ${ok.length} 个 WordPress 站点！`)
      } else {
        ElMessage.warning(`发布完成：成功 ${ok.length} 个，失败 ${fail.length} 个`)
        fail.forEach(f => console.warn(`${f.site_name}: ${f.error}`))
      }
      // 立即发布模式下，如果没有回传落地页URL，标记为发布失败
      if (publishMode.value === 'immediate' && postUrls.length === 0) {
        publishFailed = true
        status = 'failed'
      }
    } catch (e) {
      publishing.value = false
      ElMessage.error(e?.response?.data?.error || e?.message || '资源站发布失败')
      return
    }
  }

  // ── 官网 Webhook 发布 ──
  if (publishPlatform.value === 'official' && publishMode.value === 'immediate') {
    try {
      await publishApi.publishViaWebhook({
        accountId: Number(selectedAccountId.value),
        articleId: selectedArticleId.value,
        title: draftTitle.value.trim(),
        content: draftContent.value || draftTitle.value.trim(),
        slug: (selectedArticle.value?.slug || '').trim() || `article-${selectedArticleId.value}`,
        seo: {
          title: draftTitle.value.trim(),
          description: '',
          keywords: '',
          feature_image: '',
        },
      })
    } catch (e) {
      publishing.value = false
      ElMessage.error(e?.response?.data?.error || e?.message || '官网 webhook 发布失败')
      return
    }
  }

  // 更新文章状态（只更新一次，不产生重复记录）
  articles.value[idx] = {
    ...articles.value[idx],
    title: draftTitle.value.trim(),
    content: draftContent.value || draftTitle.value.trim(),
    updatedAt: nowStr(),
    status,
    publishPlatform: publishPlatform.value,
    publishMode: publishMode.value,
    scheduledAt: publishMode.value === 'scheduled' ? scheduledAt.value : '',
    publishedAt: publishMode.value === 'immediate' ? nowStr() : '',
    postUrls: postUrls, // 存储落地页URL
  }
  persistArticles(selectedAccountId.value)
  publishing.value = false
  if (publishFailed) {
    ElMessage.warning('发布完成但未获取到落地页地址，请检查站点配置')
  } else {
    ElMessage.success(publishMode.value === 'scheduled' ? '已保存，待定时发布' : '已保存并发布')
  }
  goBack()
}

watch(() => accountId.value, (value) => {
  if (value) {
    selectedAccountId.value = Number(value)
    loadArticles(Number(value))
  }
})

onMounted(async () => {
  await loadAccounts()
  const initialAccount = accounts.value.find((item) => Number(item.id) === Number(accountId.value))
  if (initialAccount) {
    selectedAccountId.value = Number(initialAccount.id)
  } else if (accounts.value.length) {
    selectedAccountId.value = Number(accounts.value[0].id)
  }
  await loadOfficialConfigStatus(Number(selectedAccountId.value))
  loadArticles(Number(selectedAccountId.value))
  loadResourceSites() // 加载资源站点列表
})

onBeforeUnmount(() => {
  const editor = editorRef.value
  if (editor) editor.destroy()
})
</script>

<style scoped>
.publish-publish-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel {
  background: #fff;
  border-radius: 14px;
  border: 1px solid #eef1f6;
  padding: 18px 20px;
}

.hero-top {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}

.back-btn {
  border: 1px solid #dbe2ea;
  background: #fff;
  color: #334155;
  border-radius: 8px;
  padding: 8px 12px;
  cursor: pointer;
}

.hero-grid,
.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 16px;
}

.field-card,
.field-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-label {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  display: flex;
  align-items: center;
  gap: 8px;
}

.select-all-hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}

.select-all-btn {
  border: 1px solid #409eff;
  background: #ecf5ff;
  color: #409eff;
  border-radius: 6px;
  padding: 2px 10px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.select-all-btn:hover {
  background: #409eff;
  color: #fff;
}

.deselect-btn {
  border-color: #f56c6c;
  background: #fef0f0;
  color: #f56c6c;
}

.deselect-btn:hover {
  background: #f56c6c;
  color: #fff;
}

.hint-warning {
  margin-top: 6px;
  font-size: 12px;
  color: #b45309;
}

.rtf-shell {
  border: 1px solid #dbe2ea;
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
}

.rtf-toolbar {
  border-bottom: 1px solid #dbe2ea;
}

.rtf-editor {
  min-height: 360px;
}

.rtf-editor :deep(.w-e-text-container) {
  min-height: 300px;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
}

.empty-panel {
  text-align: center;
  color: #64748b;
  padding: 40px 20px;
}

.empty-title {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.empty-sub {
  margin-top: 6px;
  font-size: 13px;
}

@media (max-width: 900px) {
  .hero-grid,
  .field-grid {
    grid-template-columns: 1fr;
  }
}
</style>
