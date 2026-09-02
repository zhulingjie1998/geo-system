<template>
  <div class="kb-page">
    <!-- 工具栏：返回 + 客户名 + 版本标签 | Excel导入/创建知识库 -->
    <div class="toolbar">
      <div class="tb-left">
        <el-button :icon="ArrowLeft" plain @click="goBack">返回客户列表</el-button>
        <span class="tb-title">{{ accountName }}</span>
        <span v-if="currentKbVersion" class="tb-current">
          当前 <strong>v{{ currentKbVersion.version }}</strong>
          <el-tag size="small" :type="currentKbVersion.created_by === 'ai' ? 'primary' : 'success'" effect="plain" style="margin-left:6px">
            {{ currentKbVersion.created_by === 'ai' ? 'AI 生成' : '人工编辑' }}
          </el-tag>
        </span>
      </div>
      <div class="tb-right">
        <el-button :icon="Upload" plain @click="handleExcelImport">Excel 导入</el-button>
        <el-button :icon="Plus" type="primary" @click="openCreateDialog">+ 创建知识库</el-button>
      </div>
    </div>

    <!-- 主体：左侧版本列表 + 右侧内容区 -->
    <div class="kb-body">
      <!-- 左：版本/资料 -->
      <aside class="kb-side">
        <div class="side-section">
          <div class="side-head">版本历史 ({{ versionList.length }})</div>
          <div v-if="!versionList.length" class="side-empty">还没有版本</div>
          <div v-else class="version-list">
            <div
              v-for="v in versionList"
              :key="v.id || v.version"
              class="ver-item"
              :class="{ active: currentKbVersion?.id === v.id }"
              @click="switchVersion(v)"
            >
              <div class="ver-row1">
                <span class="ver-tag">知识库 v{{ v.version }}</span>
                <el-tag size="small" :type="v.created_by === 'ai' ? 'primary' : 'success'" effect="plain">
                  {{ v.created_by === 'ai' ? 'AI' : '人工' }}
                </el-tag>
                <span v-if="currentVersionId === v.id" class="ver-current">● 当前</span>
              </div>
              <div class="ver-row2">{{ formatTime(v.created_at || v.createdAt) }}</div>
              <div class="ver-actions" @click.stop>
                <el-button v-if="currentVersionId !== v.id" link size="small" @click="setAsCurrent(v)">设为当前</el-button>
                <el-button link size="small" type="danger" @click="deleteVersion(v)">删</el-button>
              </div>
            </div>
          </div>
        </div>

        <div class="side-section">
          <div class="side-head">基础资料 ({{ materials.length }})</div>
          <div v-if="!materials.length" class="side-empty">还没上传资料</div>
          <div v-else class="src-list">
            <div v-for="s in materials" :key="s.id" class="src-item">
              <div class="src-row1">
                <el-icon class="src-icon" :size="14">
                  <component :is="srcIcon(s.file_type)" />
                </el-icon>
                <span class="src-name" :title="s.file_name">{{ s.file_name }}</span>
              </div>
              <div class="src-row2">
                <el-tag size="small" :type="srcStatusType(s.parser_status)" effect="plain">
                  {{ srcStatusText(s.parser_status) }}
                </el-tag>
                <span class="src-meta">{{ formatFileSize(s.file_size) }}</span>
                <el-button v-if="s.ai_status === 'done'" link size="small" type="primary" @click="viewAiText(s.id)">看文本</el-button>
                <el-button link size="small" type="danger" @click="delSource(s.id)">删</el-button>
              </div>
            </div>
          </div>
        </div>
      </aside>

      <!-- 右：内容主区 -->
      <section class="kb-main">
        <div v-if="!currentKbVersion" class="kb-empty">
          <el-empty description="还没有知识库，点击右上角「+ 创建知识库」">
            <el-button type="primary" :icon="Plus" @click="openCreateDialog">+ 创建知识库</el-button>
          </el-empty>
        </div>
        <template v-else>
          <!-- 阅读模式（分模块翻页） -->
          <div v-if="!isEditing" class="kb-view">
            <div class="kb-view-head">
              <div>
                <strong>知识库 v{{ currentKbVersion.version }}</strong>
                <span class="kb-view-time">· {{ formatTime(currentKbVersion.created_at || currentKbVersion.createdAt) }}</span>
                <span class="kb-view-inst">· {{ moduleCount }} 个模块</span>
              </div>
              <div class="kb-view-actions">
                <el-button :icon="Download" plain @click="exportPDF">导出 PDF</el-button>
                <el-button :icon="DocumentCopy" plain @click="exportWord">导出 Word</el-button>
                <el-button :icon="Plus" plain @click="showAddModule = true">添加模块</el-button>
                <el-button type="primary" :icon="Edit" @click="toggleEditMode">继续编辑</el-button>
              </div>
            </div>

            <!-- 模块导航条 -->
            <div v-if="kbModules.length > 1" class="kb-mod-nav">
              <button
                v-for="(m, i) in kbModules"
                :key="m.key"
                class="kb-mod-tab"
                :class="{ active: i === currentModuleIdx }"
                @click="currentModuleIdx = i"
                :title="m.title"
              >
                <span class="kb-mod-tab-key">{{ m.key }}</span>
              </button>
            </div>

            <!-- 当前模块标题 -->
            <div v-if="currentModule" class="kb-mod-header">
              <div class="kb-mod-header-left">
                <span class="kb-mod-header-key">{{ currentModule.key }}</span>
                <span class="kb-mod-header-title">{{ currentModule.title }}</span>
              </div>
            </div>

            <div class="kb-content kb-content-single" v-html="renderedContent"></div>

            <!-- 上下页 -->
            <div v-if="kbModules.length > 1" class="kb-mod-pager">
              <el-button :icon="ArrowLeft" :disabled="currentModuleIdx <= 0" @click="currentModuleIdx = Math.max(0, currentModuleIdx - 1)">
                上一模块{{ kbModules[currentModuleIdx - 1] ? ' · ' + kbModules[currentModuleIdx - 1].key : '' }}
              </el-button>
              <span class="kb-mod-pager-mid">{{ currentModuleIdx + 1 }} / {{ kbModules.length }}</span>
              <el-button type="primary" :disabled="currentModuleIdx >= kbModules.length - 1" @click="currentModuleIdx = Math.min(kbModules.length - 1, currentModuleIdx + 1)">
                下一模块{{ kbModules[currentModuleIdx + 1] ? ' · ' + kbModules[currentModuleIdx + 1].key : '' }}
                <el-icon class="el-icon--right"><ArrowRight /></el-icon>
              </el-button>
            </div>
          </div>

          <!-- 编辑模式 -->
          <div v-else class="kb-edit">
            <div class="kb-edit-head">
              <strong>编辑 知识库 v{{ currentKbVersion.version }}</strong>
              <span class="muted">→ 保存为新版本</span>
            </div>
            <el-input
              v-model="editingContent"
              type="textarea"
              :rows="22"
              placeholder="编辑当前知识库内容（markdown，包含全部模块）"
              class="edit-textarea"
            />

            <!-- 新要求 + 新资料 -->
            <div class="kb-edit-supplement">
              <div class="kb-edit-supplement-head">
                <strong>新要求 / 新资料</strong>
                <span class="muted">（可选）填写新要求并上传补充资料后，点击「AI 重新优化生成知识库」</span>
              </div>
              <el-input
                v-model="newRequirements"
                type="textarea"
                :rows="4"
                placeholder="例：补充竞品分析；M03 要更详细产品参数；新增 M11 售后服务体系…"
                class="edit-req-textarea"
              />
              <div class="kb-edit-upload-row">
                <el-upload
                  drag
                  multiple
                  :auto-upload="false"
                  :on-change="onSupplementFileChange"
                  :on-remove="onSupplementFileRemove"
                  :file-list="supplementFiles"
                  accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.png,.jpg,.jpeg,.webp"
                  class="kb-supplement-upload"
                >
                  <el-icon class="el-icon--upload"><Upload /></el-icon>
                  <div class="el-upload__text">拖拽或点击上传补充资料</div>
                  <template #tip>
                    <div class="el-upload__tip">支持 PDF / Word / Excel / TXT / 图片</div>
                  </template>
                </el-upload>
              </div>
            </div>

            <div class="kb-edit-actions">
              <el-button @click="isEditing = false">取消</el-button>
              <el-button type="primary" :icon="Check" :loading="savingEdit" @click="saveEdit">
                💾 保存修改 (新版本)
              </el-button>
              <el-button type="warning" :loading="refiningKb" @click="refineWithAi">
                ✨ AI 重新优化生成知识库
              </el-button>
            </div>
          </div>
        </template>
      </section>
    </div>

    <!-- Excel 导入知识库弹窗 -->
    <KbExcelImportDialog v-model="excelImportOpen" @done="onExcelImportDone" />

    <!-- 创建知识库弹窗（使用统一组件） -->
    <KbCreateKnowledgeDialog
      v-model="showCreateDialog"
      :default-account-id="accountId"
      @created="onKbCreated"
    />

    <!-- 添加模块弹窗 -->
    <el-dialog v-model="showAddModule" title="添加知识库模块" width="min(560px, 92vw)" top="8vh" :close-on-click-modal="false" class="add-mod-dialog">
      <div class="am-body">
        <div class="am-field">
          <label>模块编号</label>
          <el-input v-model="newModule.code" placeholder="如 M11（可留空）" clearable />
        </div>
        <div class="am-field">
          <label><span class="am-required">*</span> 标题</label>
          <el-input v-model="newModule.title" placeholder="模块标题，如 售后服务体系" />
        </div>
        <div class="am-field">
          <label><span class="am-required">*</span> 知识库内容</label>
          <el-input
            v-model="newModule.content"
            type="textarea"
            :rows="8"
            placeholder="该模块的知识库内容（支持 markdown）"
            resize="vertical"
          />
        </div>
        <p class="am-hint">将追加到当前 v{{ currentKbVersion?.version || '?' }} 之后，生成新版本（旧版保留可回滚）。</p>
      </div>
      <template #footer>
        <el-button @click="showAddModule = false">取消</el-button>
        <el-button type="primary" :loading="addingModule" :disabled="!canAddModule" @click="submitAddModule">
          追加为新版本
        </el-button>
      </template>
    </el-dialog>

    <!-- 智能识别文本查看弹窗 -->
    <el-dialog v-model="showAiTextDialog" title="智能识别文本" width="min(720px, 92vw)" top="6vh" class="ai-text-dialog">
      <div v-if="aiTextLoading" class="ai-text-loading">
        <el-icon class="is-loading" :size="20"><Loading /></el-icon>
        <span>加载中...</span>
      </div>
      <div v-else-if="aiTextContent" class="ai-text-body">
        <div class="ai-text-meta">
          <span>{{ aiTextContent.file_name }}</span>
        </div>
        <div class="ai-text-content">{{ aiTextContent.ai_text }}</div>
      </div>
      <div v-else class="ai-text-empty">暂无识别文本</div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft, ArrowRight, Download, Edit, Check, Plus,
  Document, DocumentCopy, Upload,
  Files, Picture, DataAnalysis, Loading
} from '@element-plus/icons-vue'
import api from '../api'
import publishApi from '@/api/publish'
import KbExcelImportDialog from '@/components/KbExcelImportDialog.vue'
import KbCreateKnowledgeDialog from '@/components/KbCreateKnowledgeDialog.vue'

const route = useRoute()
const router = useRouter()
const accountId = computed(() => Number(route.params.id))

// ===== 状态 =====
const loading = ref(false)
const accountName = ref('')
const currentKbVersion = ref(null)   // 当前正在查看的版本
const currentVersionId = ref(null)   // 数据库中 is_current=1 的版本 ID
const versionList = ref([])
const materials = ref([])
const currentModuleIdx = ref(0)
const isEditing = ref(false)
const editingContent = ref('')
const savingEdit = ref(false)
const newRequirements = ref('')
const supplementFiles = ref([])
const refiningKb = ref(false)

// ===== Excel 导入 =====
const excelImportOpen = ref(false)
function handleExcelImport() {
  excelImportOpen.value = true
}
function onExcelImportDone() {
  loadDetailData()
}

// ===== 创建知识库弹窗（统一组件） =====
const showCreateDialog = ref(false)
function openCreateDialog() {
  showCreateDialog.value = true
}
/** 知识库创建/上传完成回调：刷新页面数据 */
function onKbCreated(payload) {
  // 刷新资料列表和版本信息
  loadDetailData()
}

// 添加模块弹窗
const showAddModule = ref(false)
const addingModule = ref(false)
const newModule = reactive({ code: '', title: '', content: '' })

// ===== 模块列表（从 currentKbVersion.modules 提取） =====
const kbModules = computed(() => {
  const mods = currentKbVersion.value?.modules || []
  if (!Array.isArray(mods) || !mods.length) return []
  return mods.map((m) => ({
    key: m.key,
    title: m.title || m.key,
    content: m.content || '',
  }))
})
const moduleCount = computed(() => kbModules.value.length)
const canAddModule = computed(() => newModule.title.trim() && newModule.content.trim())

// 当前模块
const currentModule = computed(() => kbModules.value[currentModuleIdx.value] || null)

// 渲染后的 Markdown HTML
const renderedContent = computed(() => {
  if (currentModule.value) return renderMarkdown(currentModule.value.content)
  return renderMarkdown(currentKbVersion.value?.content || '')
})

// ===== Markdown 渲染（极简版，与 KnowledgeBasePage 一致） =====
function renderMarkdown(md) {
  if (!md) return ''
  let raw = String(md).replace(/^﻿/, '')
  raw = raw.replace(/^\s*---\s*\n[\s\S]*?\n---\s*(?:\n|$)/, '')
  raw = raw.replace(/^\s*```(?:markdown|md)?\s*\n([\s\S]*?)\n```\s*$/, '$1')
  raw = raw.replace(/^(?:\s*[-*_]{3,}\s*\n)+/, '')
  let html = raw
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^[-*_]{3,}\s*$/gm, '<hr class="kb-hr">')
    .replace(/(?:^\|.+\|$\n?)+/gm, m => {
      const lines = m.trim().split('\n').filter(l => l.trim())
      const rows = lines.map(l => l.replace(/^\||\|$/g, '').split('|').map(c => c.trim()))
      if (rows.length < 2) return m
      const sepRow = rows[1].every(c => /^:?-+:?$/.test(c))
      const head = sepRow ? rows[0] : null
      const body = sepRow ? rows.slice(2) : rows
      let h = '<table class="kb-table">'
      if (head) h += '<thead><tr>' + head.map(c => `<th>${c}</th>`).join('') + '</tr></thead>'
      h += '<tbody>' + body.map(r => '<tr>' + r.map(c => `<td>${c}</td>`).join('') + '</tr>').join('') + '</tbody>'
      h += '</table>'
      return h
    })
    .split(/\n\s*\n/).map(p => p.trim()).filter(Boolean)
    .map(p => /<(h[123]|blockquote|table|div|hr)/.test(p) ? p : `<p>${p.replace(/\n/g, '<br>')}</p>`)
    .join('\n')
  return html
}

// ===== 工具函数 =====
function formatTime(val) {
  if (!val) return '—'
  return String(val).slice(0, 16).replace('T', ' ')
}

function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0; let size = bytes
  while (size >= 1024 && i < units.length - 1) { size /= 1024; i++ }
  return size.toFixed(i > 0 ? 1 : 0) + ' ' + units[i]
}

function srcIcon(t) {
  if (t === 'image') return Picture
  if (t === 'xlsx' || t === 'xls') return DataAnalysis
  if (t === 'docx' || t === 'doc') return Document
  return Files
}
function srcStatusText(s) {
  return { pending: '待解析', parsing: '解析中', done: '已解析', failed: '失败' }[s] || s
}
function srcStatusType(s) {
  return { pending: 'info', parsing: 'warning', done: 'success', failed: 'danger' }[s] || ''
}

function goBack() {
  router.push('/publish/customer-kb')
}

// ===== 加载数据 =====
async function loadDetailData() {
  loading.value = true
  try {
    const accounts = await api.listAccounts()
    const list = Array.isArray(accounts) ? accounts : []

    const acc = list.find(a => a.id === accountId.value)
    if (acc) {
      accountName.value = acc.companyName || acc.name || '未知客户'
    }

    const [versionsRes, currentRes] = await Promise.all([
      publishApi.kbListVersions(accountId.value),
      publishApi.kbCurrent(accountId.value),
    ])
    versionList.value = Array.isArray(versionsRes?.items) ? versionsRes.items : []

    let current = currentRes?.item || null
    if (current?.id) {
      current = await publishApi.kbGetVersion(current.id)
    } else if (versionList.value.length) {
      current = await publishApi.kbGetVersion(versionList.value[0].id)
    }
    currentKbVersion.value = current
    currentVersionId.value = current?.id || null
    currentModuleIdx.value = 0
  } catch (e) {
    console.error('加载详情失败', e)
    ElMessage.error('加载知识库详情失败')
    currentKbVersion.value = null
    currentVersionId.value = null
    versionList.value = []
  }
  // 加载基础资料
  try {
    const srcRes = await publishApi.kbListSources(accountId.value, null)
    materials.value = (srcRes?.items || []).filter(s => !s.kb_version_id)
  } catch {
    materials.value = []
  }
  if (!accountName.value) accountName.value = '未知客户'
  loading.value = false
}

// ===== 资料操作 =====
async function delSource(id) {
  try {
    await ElMessageBox.confirm('确认删除此资料？(已生成的知识库不受影响)', '提示', { type: 'warning' })
    await publishApi.kbDeleteSource(id)
    const srcRes = await publishApi.kbListSources(accountId.value, null)
    materials.value = (srcRes?.items || []).filter(s => !s.kb_version_id)
    ElMessage.success('已删除')
  } catch (_) {}
}

// ===== 智能识别文本查看 =====
const showAiTextDialog = ref(false)
const aiTextLoading = ref(false)
const aiTextContent = ref(null)

async function viewAiText(sourceId) {
  showAiTextDialog.value = true
  aiTextLoading.value = true
  aiTextContent.value = null
  try {
    const r = await publishApi.kbSourceAiText(sourceId)
    aiTextContent.value = r
  } catch (e) {
    ElMessage.error('获取识别文本失败')
  } finally {
    aiTextLoading.value = false
  }
}

// ===== 识别完成回调 =====
function onRecognizeDone(ev) {
  const { accountId: doneAccountId } = ev.detail || {}
  if (doneAccountId && doneAccountId === accountId.value) {
    // 刷新基础资料列表
    publishApi.kbListSources(accountId.value, null).then(srcRes => {
      materials.value = (srcRes?.items || []).filter(s => !s.kb_version_id)
    }).catch(() => {})
  }
}

// ===== 版本操作 =====
async function switchVersion(v) {
  try {
    const detail = await publishApi.kbGetVersion(v.id)
    currentKbVersion.value = detail
    currentModuleIdx.value = 0
    ElMessage.info(`已切换到 v${v.version}`)
  } catch {
    ElMessage.error('切换版本失败')
  }
}

async function setAsCurrent(v) {
  try {
    await publishApi.kbSetCurrent(v.id)
    currentVersionId.value = v.id
    ElMessage.success(`已将 v${v.version} 设为当前版本`)
  } catch {
    ElMessage.error('设置当前版本失败')
  }
}

async function deleteVersion(v) {
  try {
    await ElMessageBox.confirm(
      `确定删除知识库 v${v.version} 吗？\n\n删除后该版本将无法恢复。`,
      '确认删除',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning', confirmButtonClass: 'el-button--danger' }
    )
    await publishApi.kbDeleteVersion(v.id)
    await loadDetailData()
    ElMessage.success(`已删除 v${v.version}`)
  } catch { /* 用户取消 */ }
}

// ===== 编辑模式 =====
function toggleEditMode() {
  if (!isEditing.value) {
    // 加载全部模块的完整 markdown 内容
    editingContent.value = currentKbVersion.value?.content || ''
    newRequirements.value = ''
    supplementFiles.value = []
    isEditing.value = true
  } else {
    saveEdit()
  }
}

async function saveEdit() {
  if (!editingContent.value.trim()) { ElMessage.warning('内容不能为空'); return }
  if (!currentKbVersion.value?.id) { ElMessage.warning('当前没有可编辑版本'); return }
  savingEdit.value = true
  try {
    // editingContent 已是全部模块的完整 markdown
    await publishApi.kbSaveHuman(currentKbVersion.value.id, editingContent.value, '编辑知识库全部内容')
    isEditing.value = false
    await loadDetailData()
    ElMessage.success('已保存为新版本')
  } catch (e) {
    ElMessage.error('保存失败')
  }
  savingEdit.value = false
}

// ===== 补充资料文件处理 =====
function onSupplementFileChange(file) {
  supplementFiles.value.push(file)
}
function onSupplementFileRemove(file) {
  supplementFiles.value = supplementFiles.value.filter(f => f.uid !== file.uid)
}

// ===== AI 重新优化生成知识库 =====
async function refineWithAi() {
  if (!currentKbVersion.value?.id) { ElMessage.warning('当前没有可编辑版本'); return }
  if (!editingContent.value.trim()) { ElMessage.warning('内容不能为空'); return }
  if (!newRequirements.value.trim() && supplementFiles.value.length === 0) {
    ElMessage.warning('请填写新要求或上传补充资料')
    return
  }

  refiningKb.value = true
  try {
    const prevKbId = currentKbVersion.value.id
    const instruction = newRequirements.value || '请基于编辑后的内容重新优化知识库'
    const content = editingContent.value
    let additionalSourceIds = []

    // 如果有补充资料文件，先上传
    if (supplementFiles.value.length > 0) {
      const acctId = accountId.value
      const newFiles = supplementFiles.value.map(x => x.raw).filter(Boolean)
      if (newFiles.length) {
        ElMessage.info('正在上传补充资料…')
        const upR = await publishApi.kbUploadSources(acctId, newFiles, prevKbId)
        const newIds = (upR.saved || []).map(x => x.id)
        additionalSourceIds = newIds
        if (!newIds.length) {
          ElMessage.warning('补充资料上传失败，将仅使用新要求进行优化')
        }
      }
    }

    // 调用 AI 优化接口
    const r = await publishApi.kbRefine(prevKbId, instruction, content, additionalSourceIds)
    if (r?.task_id) {
      ElMessage.success('AI 优化任务已提交，完成后右下角自动通知')
      // 启动浮动任务窗口
      window.dispatchEvent(new CustomEvent('kb-task-start', {
        detail: {
          phase: 'llm', taskId: r.task_id, accountId: accountId.value,
          hint: `${accountName.value} · 知识库 AI 优化中`,
          text: '正在基于编辑内容 + 新要求重新生成知识库…',
        },
      }))
      isEditing.value = false
    } else {
      ElMessage.error('AI 优化任务提交失败')
    }
  } catch (e) {
    ElMessage.error('AI 优化失败：' + (e?.message || '未知错误'))
  }
  refiningKb.value = false
}

// ===== 导出 PDF =====
function exportPDF() {
  const contentEl = document.querySelector('.kb-content')
  if (!contentEl) { ElMessage.warning('暂无可导出的内容'); return }
  const printWindow = window.open('', '_blank')
  printWindow.document.write(`
    <html><head><title>${accountName.value} - 知识库</title>
    <style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:40px;max-width:800px;margin:auto;color:#1e293b;line-height:1.8} h2{color:#334155;border-bottom:2px solid #e2e8f0;padding-bottom:8px} h3{color:#475569} p{margin:8px 0} strong{color:#0f172a}</style>
    </head><body>${contentEl.innerHTML}</body></html>`
  )
  printWindow.document.close()
  setTimeout(() => { printWindow.print() }, 300)
  ElMessage.success('正在准备 PDF 导出…')
}

function exportWord() {
  ElMessage.info('Word 导出功能开发中…')
}

// ===== 添加模块 =====
function submitAddModule() {
  if (!canAddModule.value) return
  if (!currentKbVersion.value?.id) {
    ElMessage.warning('请先创建知识库再添加模块')
    return
  }
  addingModule.value = true
  const newCode = (newModule.code || `M${String(kbModules.value.length + 1).padStart(2, '0')}`).toUpperCase()
  const appendBlock = `## ${newCode} ${newModule.title}\n\n${newModule.content}`
  const base = String(currentKbVersion.value.content || '').trim()
  const merged = base ? `${base}\n\n---\n\n${appendBlock}` : appendBlock
  publishApi.kbSaveHuman(currentKbVersion.value.id, merged, `新增模块 ${newCode}`)
    .then(async () => {
      await loadDetailData()
      // 切换到新添加的模块
      const idx = kbModules.value.findIndex(m => m.key === newCode)
      if (idx >= 0) currentModuleIdx.value = idx
      ElMessage.success(`已添加模块 ${newCode}：${newModule.title}`)
      showAddModule.value = false
      newModule.code = ''
      newModule.title = ''
      newModule.content = ''
    })
    .catch(() => {
      ElMessage.error('添加模块失败')
    })
    .finally(() => {
      addingModule.value = false
    })
}

// ===== 任务完成回调 =====
function onKbTaskDone(ev) {
  const { accountId: doneAccountId } = ev.detail || {}
  if (doneAccountId && doneAccountId === accountId.value) {
    loadDetailData()
  }
}

onMounted(() => {
  loadDetailData()
  window.addEventListener('kb-task-done', onKbTaskDone)
  window.addEventListener('kb-recognize-done', onRecognizeDone)
})
onUnmounted(() => {
  window.removeEventListener('kb-task-done', onKbTaskDone)
  window.removeEventListener('kb-recognize-done', onRecognizeDone)
})
</script>

<style scoped>
.kb-page {
  display: flex; flex-direction: column; gap: 12px;
  flex: 1; min-height: 0;
}

/* ===== 工具栏 ===== */
.toolbar {
  background: #fff; border-radius: 12px;
  padding: 12px 16px; display: flex; justify-content: space-between; align-items: center;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
  flex-wrap: wrap; gap: 12px;
}
.tb-left { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.tb-right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tb-title {
  font-size: 16px; font-weight: 700; color: #0f172a;
  letter-spacing: -0.2px;
}
.tb-current { color: #475569; font-size: 12.5px; margin-left: 4px; }

/* ===== 主体布局 ===== */
.kb-body {
  display: grid; grid-template-columns: 280px 1fr; gap: 12px;
  flex: 1; min-height: 0;
}

/* ===== 左侧边栏 ===== */
.kb-side {
  background: #fff; border-radius: 12px; padding: 14px;
  display: flex; flex-direction: column; gap: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
  min-height: 0; overflow-y: auto;
}
.side-section { display: flex; flex-direction: column; gap: 8px; }
.side-head {
  font-size: 12px; font-weight: 700; color: #475569;
  letter-spacing: 0.5px; padding-bottom: 4px; border-bottom: 1px solid #f1f5f9;
}
.side-empty { color: #94a3b8; font-size: 12px; padding: 8px 0; }

/* 版本列表 */
.version-list, .src-list { display: flex; flex-direction: column; gap: 6px; }
.ver-item {
  padding: 8px 10px; border-radius: 8px; cursor: pointer;
  border: 1px solid #f1f5f9; transition: all .15s;
}
.ver-item:hover { background: #f8fafc; border-color: #cbd5e1; }
.ver-item.active { background: #eef2ff; border-color: #818cf8; }
.ver-row1 { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 4px; }
.ver-tag { font-weight: 700; color: #4f46e5; }
.ver-current { color: #16a34a; font-size: 11px; font-weight: 600; }
.ver-row2 { color: #94a3b8; font-size: 11px; }
.ver-actions { margin-top: 4px; display: flex; gap: 4px; }

/* 基础资料 */
.src-item { padding: 8px 10px; border-radius: 8px; border: 1px solid #f1f5f9; }
.src-row1 { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.src-icon { color: #64748b; }
.src-name {
  font-size: 12px; font-weight: 600; color: #334155;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.src-row2 { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 11px; }
.src-meta { color: #94a3b8; }

/* ===== 智能识别文本弹窗 ===== */
.ai-text-dialog :deep(.el-dialog) { border-radius: 14px; overflow: hidden; }
.ai-text-dialog :deep(.el-dialog__header) { padding: 18px 24px 12px; border-bottom: 1px solid #f1f5f9; }
.ai-text-dialog :deep(.el-dialog__title) { font-size: 16px; font-weight: 700; color: #1e293b; }
.ai-text-loading { display: flex; align-items: center; gap: 8px; padding: 40px 0; justify-content: center; color: #6366f1; font-size: 14px; }
.ai-text-body { display: flex; flex-direction: column; gap: 12px; }
.ai-text-meta { font-size: 13px; color: #64748b; font-weight: 600; padding-bottom: 8px; border-bottom: 1px solid #f1f5f9; }
.ai-text-content {
  font-size: 13px; line-height: 1.8; color: #334155;
  white-space: pre-wrap; word-break: break-word;
  max-height: 60vh; overflow-y: auto; padding: 12px;
  background: #f8fafc; border-radius: 8px;
}
.ai-text-empty { text-align: center; padding: 40px 0; color: #94a3b8; font-size: 14px; }

/* ===== 右侧主区 ===== */
.kb-main {
  background: #fff; border-radius: 12px; padding: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
  min-width: 0;
  min-height: 0; overflow-y: auto;
}
.kb-empty { padding: 60px 0; }

/* 阅读模式头部 */
.kb-view-head {
  display: flex; justify-content: space-between; align-items: center;
  padding-bottom: 12px; margin-bottom: 12px; border-bottom: 1px solid #f1f5f9;
  gap: 12px; flex-wrap: wrap;
}
.kb-view-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.kb-view-time, .kb-view-inst { color: #94a3b8; font-size: 12px; margin-left: 8px; }

/* ===== 模块导航条 ===== */
.kb-mod-nav {
  display: flex; gap: 6px; flex-wrap: wrap;
  padding: 8px 0;
  margin-bottom: 12px;
  border-bottom: 1px dashed #e2e8f0;
}
.kb-mod-tab {
  position: relative;
  display: inline-flex; align-items: center; gap: 4px;
  padding: 6px 12px;
  background: #f1f5f9; border: 1px solid transparent;
  border-radius: 8px; cursor: pointer;
  font-size: 12.5px; font-weight: 600; color: #475569;
  transition: all .15s;
}
.kb-mod-tab:hover {
  background: #e2e8f0; color: #1e293b;
}
.kb-mod-tab.active {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff; border-color: transparent;
  box-shadow: 0 4px 10px -2px rgba(99,102,241,.45);
}
.kb-mod-tab-key { letter-spacing: 0.3px; }

/* ===== 当前模块标题 ===== */
.kb-mod-header {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; flex-wrap: wrap;
  padding: 12px 16px;
  background: linear-gradient(135deg, #eef2ff, #faf5ff);
  border-radius: 10px;
  margin-bottom: 16px;
}
.kb-mod-header-left { display: inline-flex; align-items: baseline; gap: 10px; }
.kb-mod-header-key {
  display: inline-block;
  padding: 3px 10px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  border-radius: 6px;
  font-size: 13px; font-weight: 700;
  letter-spacing: 0.5px;
  box-shadow: 0 4px 10px -2px rgba(99,102,241,.4);
}
.kb-mod-header-title { font-size: 16px; font-weight: 700; color: #0f172a; }

/* ===== 单模块内容（去掉首层 ## 标题，因为已在 kb-mod-header 显示） ===== */
.kb-content-single :deep(h2):first-child {
  display: none;
}

/* ===== 上下页 ===== */
.kb-mod-pager {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 24px; padding-top: 16px;
  border-top: 1px solid #f1f5f9;
}
.kb-mod-pager-mid {
  font-size: 12.5px; color: #94a3b8; font-variant-numeric: tabular-nums;
}

/* ===== Markdown 内容渲染 ===== */
.kb-content {
  font-size: 14px; line-height: 1.8; color: #0f172a;
  max-width: 900px;
}
.kb-content :deep(h1) { font-size: 24px; font-weight: 700; margin: 24px 0 12px; color: #0f172a; }
.kb-content :deep(h2) {
  font-size: 18px; font-weight: 700; margin: 20px 0 10px; color: #1e40af;
  padding: 8px 12px; background: linear-gradient(90deg, #eef2ff 0%, transparent 100%);
  border-left: 4px solid #6366f1;
}
.kb-content :deep(h3) { font-size: 15px; font-weight: 700; margin: 16px 0 8px; color: #334155; }
.kb-content :deep(p) { margin: 8px 0; }
.kb-content :deep(blockquote) {
  border-left: 4px solid #cbd5e1; padding: 4px 12px; color: #64748b;
  background: #f8fafc; margin: 8px 0;
}
.kb-content :deep(.kb-table) {
  border-collapse: collapse; margin: 12px 0; width: 100%;
}
.kb-content :deep(.kb-table th), .kb-content :deep(.kb-table td) {
  border: 1px solid #e2e8f0; padding: 6px 12px; font-size: 13px;
}
.kb-content :deep(.kb-table th) { background: #f1f5f9; font-weight: 700; color: #334155; }

/* ===== 编辑模式 ===== */
.kb-edit-head {
  margin-bottom: 12px; display: flex; align-items: center; gap: 8px;
  padding-bottom: 8px; border-bottom: 1px solid #f1f5f9;
}
.muted { color: #94a3b8; font-size: 13px; }
.edit-textarea :deep(.el-textarea__inner) {
  font-family: ui-monospace, SFMono-Regular, monospace;
  font-size: 13px; line-height: 1.6;
}
.kb-edit-actions {
  margin-top: 16px; padding-top: 12px; border-top: 1px solid #f1f5f9;
  display: flex; justify-content: flex-end; gap: 8px;
}

/* ===== 编辑模式 - 新要求/新资料 ===== */
.kb-edit-supplement {
  margin-top: 16px; padding: 16px;
  background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px;
}
.kb-edit-supplement-head {
  margin-bottom: 10px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.kb-edit-supplement-head strong { font-size: 14px; color: #1e293b; }
.edit-req-textarea :deep(.el-textarea__inner) {
  font-size: 13px; line-height: 1.6;
}
.kb-edit-upload-row { margin-top: 12px; }
.kb-supplement-upload :deep(.el-upload-dragger) {
  padding: 16px; border-radius: 8px;
}
.kb-supplement-upload :deep(.el-upload__text) { font-size: 13px; color: #64748b; }
.kb-supplement-upload :deep(.el-upload__tip) { font-size: 12px; color: #94a3b8; }

/* ===== 创建知识库弹窗 ===== */
.create-kb-dialog :deep(.el-dialog) { border-radius: 14px; overflow: hidden; }
.create-kb-dialog :deep(.el-dialog__header) { padding: 18px 24px 12px; border-bottom: 1px solid #f1f5f9; }
.create-kb-dialog :deep(.el-dialog__title) { font-size: 16px; font-weight: 700; color: #1e293b; }
.ckb-body { display: flex; flex-direction: column; gap: 14px; padding: 8px 0; }
.ckb-field label { font-size: 13px; font-weight: 600; color: #475569; display: block; margin-bottom: 6px; }
.ckb-req { color: #ef4444; }
.ckb-module-confirm :deep(.el-checkbox__label) { font-size: 12.5px; color: #166534; line-height: 1.5; }
.ckb-history-list { display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
.ckb-history-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px; border-radius: 8px; border: 1px solid #e2e8f0;
  font-size: 12.5px; cursor: pointer; transition: border-color .15s;
}
.ckb-history-item.checked { border-color: #6366f1; background: #f5f3ff; }
.ckb-history-item.disabled { opacity: .5; cursor: not-allowed; }
.ckb-history-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #334155; }
.ckb-history-size { color: #94a3b8; font-size: 11px; }
.ckb-no-history { font-size: 12px; color: #94a3b8; margin-bottom: 10px; }
.ckb-upload { width: 100%; }
.ckb-upload :deep(.el-upload-dragger) {
  padding: 20px; display: flex; flex-direction: column; align-items: center; gap: 6px;
  border-radius: 10px; border: 2px dashed #cbd5e1;
}
.ckb-upload-text { font-size: 13px; color: #475569; }
.ckb-upload-text em { color: #6366f1; font-style: normal; font-weight: 600; }
.ckb-upload-types { font-size: 11px; color: #94a3b8; }
.ckb-file-list { display: flex; flex-direction: column; gap: 4px; margin-top: 8px; }
.ckb-file-item {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 10px; border-radius: 6px; background: #f8fafc;
  font-size: 12px; color: #475569;
}
.ckb-file-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ckb-file-size { color: #94a3b8; font-size: 11px; }

/* ===== 添加模块弹窗 ===== */
.add-mod-dialog :deep(.el-dialog) { border-radius: 14px; overflow: hidden; }
.add-mod-dialog :deep(.el-dialog__header) { padding: 18px 24px 12px; border-bottom: 1px solid #f1f5f9; }
.add-mod-dialog :deep(.el-dialog__title) { font-size: 16px; font-weight: 700; color: #1e293b; }
.am-body { display: flex; flex-direction: column; gap: 14px; padding: 8px 0; }
.am-field label { font-size: 13px; font-weight: 600; color: #475569; display: block; margin-bottom: 6px; }
.am-required { color: #ef4444; margin-right: 2px; }
.am-hint { font-size: 12px; color: #94a3b8; line-height: 1.55; margin: 4px 0 0; padding: 8px 12px; background: #f8fafc; border-radius: 6px; }

/* 移动端适配 */
@media (max-width: 900px) {
  .kb-body { grid-template-columns: 1fr; }
  .kb-side { max-height: 280px; }
}

@media (max-width: 600px) {
  .toolbar { padding: 10px 14px; }
  .tb-title { font-size: 14px; }
  .tb-current { display: none; }
  .kb-main { padding: 12px; }
  .kb-view-head { flex-direction: column; align-items: stretch; }
  .kb-view-actions { justify-content: flex-end; }
  .kb-mod-nav { gap: 4px; }
  .kb-mod-tab { padding: 5px 10px; font-size: 11.5px; }
  .kb-mod-header-title { font-size: 14px; }
  .edit-textarea :deep(.el-textarea__inner) { font-size: 12px; }
}
</style>
