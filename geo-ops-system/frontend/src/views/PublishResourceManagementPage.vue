<template>
  <div class="resource-page">
    <!-- 工具栏 -->
    <section class="panel toolbar-panel">
      <div class="toolbar-left">
        <el-tabs v-model="activeTab" class="resource-tabs" @tab-change="loadSites">
          <el-tab-pane label="博客" name="blog">
            <template #label>
              <span>博客 <el-tag v-if="typeCounts.blog" size="small" type="info" round>{{ typeCounts.blog }}</el-tag></span>
            </template>
          </el-tab-pane>
          <el-tab-pane label="论坛" name="forum">
            <template #label>
              <span>论坛 <el-tag v-if="typeCounts.forum" size="small" type="info" round>{{ typeCounts.forum }}</el-tag></span>
            </template>
          </el-tab-pane>
          <el-tab-pane label="B2B" name="b2b">
            <template #label>
              <span>B2B <el-tag v-if="typeCounts.b2b" size="small" type="info" round>{{ typeCounts.b2b }}</el-tag></span>
            </template>
          </el-tab-pane>
          <el-tab-pane label="问答" name="qa">
            <template #label>
              <span>问答 <el-tag v-if="typeCounts.qa" size="small" type="info" round>{{ typeCounts.qa }}</el-tag></span>
            </template>
          </el-tab-pane>
        </el-tabs>
      </div>
      <div class="toolbar-right">
        <el-button :icon="Connection" plain :loading="batchTesting" @click="testAllSites">一键测试</el-button>
        <el-button :icon="Upload" plain @click="showBatchImport = true">批量导入</el-button>
        <el-button type="primary" :icon="Plus" @click="openAddSite">新增站点</el-button>
      </div>
    </section>

    <!-- 站点列表 -->
    <section class="panel table-panel">
      <div class="auto-test-hint">
        <el-icon :size="14"><InfoFilled /></el-icon>
        系统每天 0:00 自动测试所有站点连通性，连接异常的站点将不支持发布。
      </div>
      <el-table
        v-loading="loading"
        :data="filteredRows"
        row-key="id"
        :header-cell-style="{ background: '#fafbfc', color: '#64748b', fontWeight: 600, fontSize: '13px' }"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="45" />
        <el-table-column prop="site_name" label="站点名称" min-width="220">
          <template #default="{ row }">
            <div class="site-name-cell">
              <el-link :href="row.site_url" target="_blank" type="primary" :underline="false">{{ row.site_name }}</el-link>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="site_url" label="站点地址" min-width="280">
          <template #default="{ row }">
            <span class="url-text">{{ row.site_url }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="site_type" label="类型" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="typeTagType(row.site_type)" effect="plain">{{ typeLabel(row.site_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="认证状态" width="120" align="center">
          <template #default="{ row }">
            <template v-if="row.last_test_result === 'ok'">
              <el-tag size="small" type="success" effect="light">
                <el-icon :size="12"><CircleCheckFilled /></el-icon> 已连通
              </el-tag>
            </template>
            <template v-else-if="row.last_test_result === 'fail'">
              <el-tooltip :content="row.last_test_error || '测试失败'" placement="top">
                <el-tag size="small" type="danger" effect="light">
                  <el-icon :size="12"><CircleCloseFilled /></el-icon> 失败
                </el-tag>
              </el-tooltip>
            </template>
            <template v-else>
              <el-tag size="small" type="info" effect="plain">未测试</el-tag>
            </template>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link size="small" :loading="testingId === row.id" @click="testSingleSite(row)">测试连接</el-button>
            <el-button link size="small" @click="openEditSite(row)">编辑</el-button>
            <el-button link size="small" type="danger" @click="deleteSite(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="table-empty">
            <el-empty description="暂无资源站点" :image-size="80">
              <el-button type="primary" :icon="Plus" @click="openAddSite">添加第一个站点</el-button>
            </el-empty>
          </div>
        </template>
      </el-table>

      <!-- 批量操作栏 -->
      <div v-if="selectedRows.length > 0" class="batch-bar">
        <span class="batch-info">已选 {{ selectedRows.length }} 个站点</span>
        <el-button size="small" type="primary" :disabled="!selectedRows.length" @click="openPublishDialog">
          发布文章到选中站点
        </el-button>
      </div>
    </section>

    <!-- ═══ 新增/编辑站点 Dialog ═══ -->
    <el-dialog
      v-model="siteDialogVisible"
      :title="editingSite ? '编辑站点' : '新增站点'"
      width="min(560px, 94vw)"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form ref="siteFormRef" :model="siteForm" :rules="siteRules" label-position="top" size="large">
        <el-form-item label="站点类型" prop="site_type">
          <el-radio-group v-model="siteForm.site_type">
            <el-radio-button value="blog">博客</el-radio-button>
            <el-radio-button value="forum">论坛</el-radio-button>
            <el-radio-button value="b2b">B2B</el-radio-button>
            <el-radio-button value="qa">问答</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="站点名称" prop="site_name">
          <el-input v-model="siteForm.site_name" placeholder="例：Optimal Blog" />
        </el-form-item>
        <el-form-item label="站点地址" prop="site_url">
          <el-input v-model="siteForm.site_url" placeholder="https://blogoptimal.com" />
          <div class="field-hint">WordPress 站点的完整地址，含 https://</div>
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="用户名" prop="username">
              <el-input v-model="siteForm.username" placeholder="WordPress 管理员用户名" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Application Password 令牌" prop="application_password">
              <el-input
                v-model="siteForm.application_password"
                type="password"
                show-password
                placeholder="WP 后台 → 用户 → Application Passwords 生成的令牌"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-alert
          v-if="editingSite && !siteForm.application_password"
          title="留空则保留原令牌不变；输入新值将覆盖旧令牌"
          type="info"
          :closable="false"
          show-icon
          style="margin-bottom: 8px"
        />
      </el-form>

      <template #footer>
        <el-button @click="siteDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingSite" @click="saveSite">
          {{ editingSite ? '保存修改' : '添加站点' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ═══ 批量导入 Dialog ═══ -->
    <el-dialog v-model="showBatchImport" title="批量导入站点" width="min(640px, 94vw)" destroy-on-close>
      <div class="import-hint">
        <p><strong>导入格式说明：</strong></p>
        <p>支持从 Excel 复制的数据格式，每行包含：平台类型、平台地址、平台名称、用户名、令牌</p>
        <p>平台类型可选：<code>博客</code><code>论坛</code><code>B2B</code><code>问答</code></p>
      </div>
      <el-input
        v-model="importText"
        type="textarea"
        :rows="14"
        placeholder="粘贴 Excel 数据（含表头），例：
平台类型	平台地址	平台名称	用户名	令牌
博客	blogoptimal.com	Optimal Blog	admin	gwni acM6 WBZS cuyZ WH3u QDYt
论坛	genresforum.com	Genues Forum	admin	N3vN 8kQm 2LsP 5rTc 1WzH 7yBd"
        class="import-textarea"
      />

      <template #footer>
        <el-button @click="showBatchImport = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="doBatchImport">
          开始导入
        </el-button>
      </template>
    </el-dialog>

    <!-- ═══ 发布文章 Dialog ═══ -->
    <el-dialog v-model="publishDialogVisible" title="发布文章到选中站点" width="min(720px, 94vw)" destroy-on-close>
      <el-form :model="publishForm" label-position="top" size="large">
        <el-form-item label="目标站点">
          <div class="target-sites-list">
            <el-tag v-for="s in selectedRows" :key="s.id" closable @close="removeFromSelection(s.id)" style="margin: 4px"
              :type="s.last_test_result === 'fail' ? 'danger' : 'success'">
              {{ s.site_name }}
              <span class="target-type">{{ typeLabel(s.site_type) }}</span>
            </el-tag>
            <span v-if="!selectedRows.length" class="no-target">未选择站点</span>
          </div>
          <div v-if="selectedRows.some(s => s.last_test_result === 'fail')" class="blocked-tip">
            <el-alert type="error" :closable="false" show-icon>
              存在连接异常的站点，已自动拦截。请先测试连接恢复后再发布。
            </el-alert>
          </div>
        </el-form-item>
        <el-form-item label="文章标题" prop="title" :rules="[{ required: true, message: '请输入标题' }]">
          <el-input v-model="publishForm.title" placeholder="输入要发布的文章标题" />
        </el-form-item>
        <el-form-item label="文章正文（HTML）" prop="content" :rules="[{ required: true, message: '请输入正文' }]">
          <el-input
            v-model="publishForm.content"
            type="textarea"
            :rows="10"
            placeholder="粘贴 HTML 格式的文章正文..."
          />
        </el-form-item>
        <el-form-item label="发布状态">
          <el-radio-group v-model="publishForm.status">
            <el-radio value="publish">立即发布</el-radio>
            <el-radio value="draft">保存为草稿</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="publishDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="publishing" :icon="Promotion" @click="doPublish">
          发布到 {{ selectedRows.length }} 个站点
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus, Upload, Connection, CircleCheckFilled, CircleCloseFilled, Promotion, InfoFilled,
} from '@element-plus/icons-vue'
import resourceApi from '@/api/resource'

// ── 状态 ──
const activeTab = ref('blog')
const loading = ref(false)
const rows = ref([])
const typeCounts = ref({})
const selectedRows = ref([])
const testingId = ref(null)

// Dialog 状态
const siteDialogVisible = ref(false)
const editingSite = ref(null)
const savingSite = ref(false)
const showBatchImport = ref(false)
const importText = ref('')
const importing = ref(false)
const batchTesting = ref(false)
const publishDialogVisible = ref(false)
const publishing = ref(false)

// 表单
const siteFormRef = ref()
const siteForm = reactive({
  site_type: 'blog',
  site_name: '',
  site_url: '',
  username: '',
  application_password: '',
})
const siteRules = {
  site_type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  site_name: [{ required: true, message: '请输入站点名称', trigger: 'blur' }],
  site_url: [{ required: true, message: '请输入站点地址', trigger: 'blur' }],
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  application_password: [{ required: true, message: '请输入令牌', trigger: 'blur' }],
}
const publishForm = reactive({
  title: '',
  content: '',
  status: 'publish',
})

// ── 计算属性 ──
const filteredRows = computed(() =>
  rows.value
    .filter(item => item.site_type === activeTab.value)
    .sort((a, b) => {
      const ta = a.updatedAt || a.createdAt || ''
      const tb = b.updatedAt || b.createdAt || ''
      return tb.localeCompare(ta)
    })
)

function typeLabel(type) {
  return { blog: '博客', forum: '论坛', b2b: 'B2B', qa: '问答' }[type] || '未知'
}
function typeTagType(type) {
  return { blog: '', forum: 'warning', b2b: 'success', qa: 'danger' }[type] || 'info'
}

// ── 数据加载 ──
async function loadSites() {
  loading.value = true
  try {
    const r = await resourceApi.listSites(activeTab.value)
    rows.value = r?.items || []
    typeCounts.value = r?.type_counts || {}
  } catch (e) {
    ElMessage.error('加载站点失败：' + (e.message || e))
    rows.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => loadSites())

// ── 新增/编辑站点 ──
function openAddSite() {
  editingSite.value = null
  Object.assign(siteForm, { site_type: activeTab.value, site_name: '', site_url: '', username: '', application_password: '' })
  siteDialogVisible.value = true
}

function openEditSite(row) {
  editingSite.value = row
  Object.assign(siteForm, {
    site_type: row.site_type,
    site_name: row.site_name,
    site_url: row.site_url,
    username: row.username,
    application_password: '', // 编辑时默认留空=不修改
  })
  siteDialogVisible.value = true
}

async function saveSite() {
  try {
    await siteFormRef.value.validate()
  } catch { return }

  savingSite.value = true
  try {
    if (editingSite.value) {
      const payload = {
        name: siteForm.site_name,
        url: siteForm.site_url,
        type: siteForm.site_type,
        username: siteForm.username,
        status: 1,
      }
      if (siteForm.application_password) {
        payload.token = siteForm.application_password
      }
      await resourceApi.updateSite(editingSite.value.id, payload)
      ElMessage.success('已更新')
    } else {
      await resourceApi.createSite({
        type: siteForm.site_type,
        name: siteForm.site_name,
        url: siteForm.site_url,
        username: siteForm.username,
        token: siteForm.application_password,
      })
      ElMessage.success('已添加')
    }
    siteDialogVisible.value = false
    await loadSites()
  } catch (e) {
    ElMessage.error((editingSite.value ? '更新' : '添加') + '失败：' + (e.message || e))
  } finally {
    savingSite.value = false
  }
}

// ── 删除 ──
async function deleteSite(row) {
  try {
    await ElMessageBox.confirm(`确认删除站点「${row.site_name}」？`, '提示', { type: 'warning' })
    await resourceApi.deleteSite(row.id)
    ElMessage.success('已删除')
    await loadSites()
  } catch (_) {}
}

// ── 单站测试连接 ──
async function testSingleSite(row) {
  testingId.value = row.id
  try {
    const r = await resourceApi.testSite(row.id)
    if (r.ok) {
      ElMessage.success(`「${row.site_name}」连接成功`)
    } else {
      ElMessage.error(`「${row.site_name}」连接失败：${r.error || '未知错误'}`)
    }
    await loadSites()
  } catch (e) {
    ElMessage.error(`「${row.site_name}」测试失败：${e.message || e}`)
  } finally {
    testingId.value = null
  }
}

// ── 一键测试所有站点 ──
async function testAllSites() {
  if (!filteredRows.value.length) {
    ElMessage.warning('当前没有站点可测试')
    return
  }
  batchTesting.value = true
  let success = 0, fail = 0
  try {
    // 逐个测试，避免并发过高
    for (const row of filteredRows.value) {
      try {
        const r = await resourceApi.testSite(row.id)
        if (r.ok) success++
        else fail++
      } catch {
        fail++
      }
    }
    ElMessage.success(`测试完成：成功 ${success} 条，失败 ${fail} 条`)
    await loadSites()
  } catch (e) {
    ElMessage.error('批量测试失败：' + (e.message || e))
  } finally {
    batchTesting.value = false
  }
}

// ── 批量导入 ──
async function doBatchImport() {
  if (!importText.value.trim()) {
    ElMessage.warning('请粘贴数据')
    return
  }

  // 解析 TSV 数据
  const lines = importText.value.trim().split('\n').map(l => l.trim()).filter(Boolean)
  if (lines.length < 2) {
    ElMessage.warning('数据至少需要表头 + 1 行数据')
    return
  }

  const header = lines[0].split('\t').map(s => s.trim())
  const items = []
  for (let i = 1; i < lines.length; i++) {
    const vals = lines[i].split('\t').map(s => s.trim())
    const obj = {}
    header.forEach((h, idx) => { obj[h] = vals[idx] || '' })
    items.push(obj)
  }

  if (!items.length) {
    ElMessage.warning('未能解析出有效数据行')
    return
  }

  importing.value = true
  try {
    const r = await resourceApi.batchImport(items)
    ElMessage.success(`导入完成：成功 ${r.created} 条，跳过 ${r.skipped} 条`)
    if (r.errors?.length) {
      console.warn('Import errors:', r.errors)
    }
    showBatchImport.value = false
    importText.value = ''
    await loadSites()
  } catch (e) {
    ElMessage.error('导入失败：' + (e.message || e))
  } finally {
    importing.value = false
  }
}

// ── 选择 / 批量操作 ──
function onSelectionChange(val) {
  selectedRows.value = val
}

function removeFromSelection(id) {
  selectedRows.value = selectedRows.value.filter(s => s.id !== id)
}

function openPublishDialog() {
  if (!selectedRows.value.length) {
    ElMessage.warning('请先选择目标站点')
    return
  }
  // 拦截未连通的站点
  const blocked = selectedRows.value.filter(s => s.last_test_result === 'fail')
  if (blocked.length) {
    const names = blocked.map(s => s.site_name).join('、')
    ElMessage.error(`以下站点连接异常，不支持发布：${names}。请先测试连接恢复后再发布。`)
    return
  }
  publishForm.title = ''
  publishForm.content = ''
  publishForm.status = 'publish'
  publishDialogVisible.value = true
}

async function doPublish() {
  if (!publishForm.title.trim()) {
    ElMessage.warning('请输入标题')
    return
  }
  if (!publishForm.content.trim()) {
    ElMessage.warning('请输入正文')
    return
  }

  publishing.value = true
  try {
    const r = await resourceApi.publish({
      site_ids: selectedRows.value.map(s => s.id),
      title: publishForm.title,
      content: publishForm.content,
      status: publishForm.status,
    })
    const ok = r.results?.filter(x => x.ok) || []
    const fail = r.results?.filter(x => !x.ok) || []
    if (fail.length === 0) {
      ElMessage.success(`全部发布成功！共 ${ok.length} 个站点`)
    } else {
      ElMessage.warning(`发布完成：成功 ${ok.length} 个，失败 ${fail.length} 个`)
      fail.forEach(f => console.warn(`${f.site_name}: ${f.error}`))
    }
    publishDialogVisible.value = false
    // 发布后刷新站点列表（发布失败可能更新了连接状态）
    await loadSites()
  } catch (e) {
    // 后端拦截未连通站点时返回 400 + blocked_sites
    const msg = e?.response?.data?.error || e?.message || e
    ElMessage.error(typeof msg === 'string' ? msg : '发布失败')
    await loadSites()
  } finally {
    publishing.value = false
  }
}
</script>

<style scoped>
.resource-page { display: flex; flex-direction: column; gap: 16px; }

.panel {
  background: #fff;
  border: 1px solid #eef1f6;
  border-radius: 12px;
  padding: 12px 16px 14px;
}

/* 工具栏 */
.toolbar-panel { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.toolbar-left { min-width: 300px; }
.toolbar-right { display: flex; gap: 8px; flex-shrink: 0; }
.resource-tabs { margin-bottom: 0; }
.resource-tabs :deep(.el-tabs__header) { margin-bottom: 0; }

/* 表格 */
.table-panel { position: relative; overflow: hidden; }
.url-text { font-size: 12px; color: #64748b; font-family: ui-monospace, SFMono-Regular, monospace; }
.site-name-cell { font-weight: 500; }
.table-empty { padding: 28px 0; text-align: center; color: #94a3b8; }

/* 批量操作栏 */
.batch-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; margin-top: -1px;
  background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 0 0 8px 8px;
}
.batch-info { font-size: 13px; color: #166534; font-weight: 500; }

/* 导入 */
.import-hint { margin-bottom: 12px; color: #64748b; font-size: 13px; line-height: 1.8; }
.import-hint code {
  background: #f1f5f9; padding: 1px 6px; border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, monospace; font-size: 12px;
}
.import-textarea :deep(.el-textarea__inner) {
  font-family: ui-monospace, SFMono-Regular, 'Cascadia Code', monospace;
  font-size: 12px; line-height: 1.6;
}

/* 发布目标列表 */
.target-sites-list { display: flex; flex-wrap: wrap; gap: 4px; }
.target-type { margin-left: 4px; opacity: 0.6; font-size: 11px; }
.no-target { color: #c0c4cc; font-size: 13px; }
.blocked-tip { margin-top: 8px; }

/* 自动测试提示 */
.auto-test-hint {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 14px; margin-bottom: 0;
  background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px 8px 0 0;
  font-size: 12px; color: #0369a1;
}

.field-hint { font-size: 12px; color: #909399; margin-top: 4px; line-height: 1.5; }
</style>
