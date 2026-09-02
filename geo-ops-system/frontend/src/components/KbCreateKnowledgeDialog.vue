<template>
  <el-dialog
    v-model="visible"
    width="min(780px, 94vw)"
    :close-on-click-modal="false"
    :show-close="false"
    class="kb-create-dialog"
    align-center
    destroy-on-close
  >
    <template #header>
      <div class="kb-dlg-hero">
        <div class="kb-dlg-hero-bg"></div>
        <div class="kb-dlg-hero-icon">
          <el-icon :size="22"><Files /></el-icon>
        </div>
        <div class="kb-dlg-hero-text">
          <div class="kb-dlg-hero-title">创建客户知识库</div>
          <div class="kb-dlg-hero-sub">上传基础资料 → AI 按 GEO 标准 10 模块（M01–M10）生成知识库</div>
        </div>
        <button class="kb-dlg-close" @click="visible = false" aria-label="关闭">
          <el-icon :size="18"><Close /></el-icon>
        </button>
      </div>
    </template>

    <el-form label-width="92px" class="kb-create-form" v-loading="loadingAll" @submit.prevent>
      <!-- 目标客户（无预选时显示） -->
      <el-form-item v-if="!defaultAccountId" label="目标客户" required>
        <div class="kb-field-row">
          <button type="button" class="kb-acct-picker" :class="{ empty: !accountId }"
                  @click="openAcctPicker">
            <template v-if="accountId">
              <span class="kb-acct-picker-name">{{ pickedAccountLabel }}</span>
            </template>
            <template v-else>
              <span class="kb-acct-picker-placeholder">点击选择客户</span>
            </template>
            <el-icon class="kb-acct-picker-arrow"><ArrowDown /></el-icon>
          </button>
          <el-button :icon="Plus" size="large" plain @click="newCustomerVisible = true">新建客户</el-button>
        </div>
        <div class="kb-field-hint">
          <el-icon :size="12"><InfoFilled /></el-icon>
          显示初始客户与正式客户（付费客户）。初始客户可在此搭建知识库，搭好后点「转为正式」进入运营；报价客户不在此列。
        </div>
      </el-form-item>

      <!-- 基础资料 -->
      <el-form-item label="基础资料" required>
        <div class="kb-upload-card">
          <!-- 历史已上传资料选择 -->
          <div v-if="existingSources.length" class="kb-existing-sources">
            <div class="kb-file-list-head">
              <span>历史已上传资料 <strong>{{ existingSources.length }}</strong></span>
              <el-button text type="primary" size="small" @click="toggleSelectAllSources">
                {{ isAllSourcesSelected ? '全部取消' : '全选' }}
              </el-button>
            </div>
            <div class="kb-file-grid">
              <label
                v-for="src in existingSources"
                :key="src.id"
                class="kb-file-card kb-source-selectable"
                :class="{ selected: selectedSourceIds.has(src.id) }"
              >
                <input
                  type="checkbox"
                  :value="src.id"
                  :checked="selectedSourceIds.has(src.id)"
                  @change="toggleSource(src.id)"
                  class="kb-source-checkbox"
                />
                <div class="kb-file-meta">
                  <div class="kb-file-name" :title="src.file_name">{{ src.file_name }}</div>
                  <div class="kb-file-status">
                    <span v-if="src.parsed" class="status-parsed">已解析</span>
                    <span v-else class="status-pending">解析中</span>
                    <span class="kb-file-size">{{ formatSize(src.file_size) }}</span>
                  </div>
                </div>
              </label>
            </div>
            <div class="kb-sources-hint">
              <el-icon :size="12"><InfoFilled /></el-icon>
              勾选历史资料后无需重复上传，可直接用于生成知识库
            </div>
          </div>

          <div v-if="existingSources.length && uploadQueue.length" class="kb-upload-divider">
            <span>或上传新资料</span>
          </div>
          <el-upload
            drag
            multiple
            class="kb-upload-zone-v2"
            :auto-upload="false"
            :show-file-list="false"
            accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.jpg,.jpeg,.png,.webp"
            :disabled="!accountId"
            @change="handlePickFiles"
          >
            <div class="kb-upload-inner">
              <div class="kb-upload-icon-wrap">
                <el-icon :size="28"><UploadFilled /></el-icon>
              </div>
              <div class="kb-upload-main">
                拖拽文件到此处，或<em>点击上传</em>
              </div>
              <div class="kb-upload-types">
                <span class="ft-chip ft-pdf">PDF</span>
                <span class="ft-chip ft-doc">Word</span>
                <span class="ft-chip ft-xls">Excel</span>
                <span class="ft-chip ft-img">图片</span>
                <span class="ft-chip ft-txt">TXT</span>
              </div>
              <div class="kb-upload-foot">单文件 ≤ 30MB · 图片走通义千问 Qwen-VL 智能识别</div>
            </div>
          </el-upload>

          <transition name="kb-fade">
            <div v-if="uploadQueue.length" class="kb-file-list">
              <div class="kb-file-list-head">
                <span>待上传 <strong>{{ uploadQueue.length }}</strong> 个文件</span>
                <el-button text type="danger" size="small" @click="clearUploads">全部清空</el-button>
              </div>
              <div class="kb-file-grid">
                <div v-for="file in uploadQueue" :key="file.uid" class="kb-file-card">
                  <div class="kb-file-meta">
                    <div class="kb-file-name" :title="file.name">{{ file.name }}</div>
                    <div class="kb-file-size">{{ formatSize(file.size) }}</div>
                  </div>
                  <button type="button" class="kb-file-rm" @click="removeUpload(file.uid)" aria-label="移除">
                    <el-icon :size="14"><Close /></el-icon>
                  </button>
                </div>
              </div>
            </div>
          </transition>
        </div>
      </el-form-item>

      <!-- 补充说明 -->
      <el-form-item label="补充说明">
        <el-input
          v-model="remark"
          type="textarea"
          :rows="3"
          placeholder="可留空。默认即按 GEO 10 模块标准模板生成。如需特殊强调，例：客户简称银联、重点突出适老化产品..."
        />
        <div class="kb-field-hint kb-hint-success">
          <el-icon :size="12"><Check /></el-icon>
          <strong>已内置 GEO 10 模块标准生成模板（M01–M10）</strong>
          ，留空直接生成；此处仅做客户特殊补充
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="kb-footer">
        <el-button size="large" @click="close">取消</el-button>
        <div class="kb-footer-actions">
          <el-button size="large" type="success" plain :disabled="!canUploadOnly" :loading="busy === 'upload'" @click="uploadOnly">仅上传资料</el-button>
          <el-button size="large" type="primary" :icon="MagicStick" :disabled="!canGenerate" :loading="busy === 'generate'" @click="generateKb" class="kb-btn-gen">上传并生成知识库</el-button>
        </div>
      </div>
    </template>

    <!-- 目标客户选择 Dialog -->
    <el-dialog
      v-model="acctPickerOpen"
      title="选择客户"
      width="min(560px, 92vw)"
      :close-on-click-modal="true"
      append-to-body
    >
      <div class="acct-picker-body">
        <el-input
          v-model="acctPickerSearch"
          placeholder="搜索公司名 / 品牌名"
          clearable
          size="large"
          :prefix-icon="Search"
          ref="acctPickerSearchRef"
          class="acct-picker-search"
        />
        <div class="acct-picker-count">
          匹配 {{ filteredPickerAccounts.length }} / {{ allAccounts.length }} 个客户
        </div>
        <div class="acct-picker-list">
          <button
            v-for="a in filteredPickerAccounts"
            :key="a.id"
            type="button"
            class="acct-picker-row"
            :class="{ active: accountId === a.id }"
            @click="pickAcct(a)"
          >
            <div class="acct-picker-row-main">
              <span class="acct-picker-row-name">{{ a.companyName || a.company_name }}</span>
              <span v-if="a.companyBrand || a.company_brand" class="acct-picker-row-brand">{{ a.companyBrand || a.company_brand }}</span>
            </div>
            <el-icon v-if="accountId === a.id" class="acct-picker-row-check"><Check /></el-icon>
          </button>
          <div v-if="!filteredPickerAccounts.length" class="acct-picker-empty">
            <span v-if="acctPickerSearch">未找到匹配「{{ acctPickerSearch }}」的客户</span>
            <span v-else>暂无客户，点「新建客户」创建</span>
          </div>
        </div>
      </div>
    </el-dialog>

    <CustomerCreateDialog
      v-model="newCustomerVisible"
      :suggestions="brandSuggestions"
      @saved="handleCustomerSaved"
    />
  </el-dialog>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Files, Close, ArrowDown, InfoFilled, UploadFilled,
  Plus, Check, MagicStick, Search,
} from '@element-plus/icons-vue'
import api from '@/api'
import publishApi from '@/api/publish'
import CustomerCreateDialog from '@/components/common/CustomerCreateDialog.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 预选客户 ID（详情页传入，此时隐藏客户选择器） */
  defaultAccountId: { type: [Number, String], default: null },
})
const emit = defineEmits(['update:modelValue', 'created'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const loadingAll = ref(false)
const busy = ref('')
const accountId = ref(null)
const allAccounts = ref([])
const uploadQueue = ref([])
const remark = ref('')
const newCustomerVisible = ref(false)
// 历史资料相关状态
const existingSources = ref([])
const selectedSourceIds = ref(new Set())
let pollTimer = null

// ── 客户选择弹窗 ──
const acctPickerOpen = ref(false)
const acctPickerSearch = ref('')
const acctPickerSearchRef = ref(null)

const filteredPickerAccounts = computed(() => {
  const q = acctPickerSearch.value.trim().toLowerCase()
  if (!q) return allAccounts.value
  return allAccounts.value.filter((a) => {
    const name = String(a.companyName || a.company_name || '').toLowerCase()
    const brand = String(a.companyBrand || a.company_brand || '').toLowerCase()
    return name.includes(q) || brand.includes(q)
  })
})

const pickedAccountLabel = computed(() => {
  const a = allAccounts.value.find((x) => x.id === accountId.value)
  if (!a) return ''
  const name = a.companyName || a.company_name || ''
  const brand = a.companyBrand || a.company_brand || ''
  return brand ? `${name} · ${brand}` : name
})

function openAcctPicker() {
  acctPickerOpen.value = true
  acctPickerSearch.value = ''
  nextTick(() => {
    try { acctPickerSearchRef.value?.focus?.() } catch {}
  })
}

function pickAcct(a) {
  accountId.value = a.id
  acctPickerOpen.value = false
  // 切换客户时重新加载历史资料
  loadExistingSources(a.id)
}

const canUploadOnly = computed(() => !!accountId.value && (uploadQueue.value.length > 0 || selectedSourceIds.value.size > 0))
const canGenerate = computed(() => !!accountId.value && (uploadQueue.value.length > 0 || selectedSourceIds.value.size > 0))

// 历史资料选择计算属性
const isAllSourcesSelected = computed(() => {
  return existingSources.value.length > 0 && selectedSourceIds.value.size === existingSources.value.length
})

const brandSuggestions = computed(() => {
  const brands = new Set()
  for (const acc of allAccounts.value) {
    if (Array.isArray(acc.companyBrands)) {
      acc.companyBrands.forEach((b) => b && brands.add(String(b)))
    }
    if (acc.companyBrand) brands.add(String(acc.companyBrand))
  }
  return [...brands]
})

function formatSize(size) {
  if (!size) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let idx = 0
  let value = size
  while (value >= 1024 && idx < units.length - 1) {
    value /= 1024
    idx += 1
  }
  return `${value.toFixed(idx > 0 ? 1 : 0)} ${units[idx]}`
}

function clearUploads() {
  uploadQueue.value = []
}

function handlePickFiles(uploadFile) {
  const raw = uploadFile?.raw
  if (!raw) return
  const exists = uploadQueue.value.some((item) => item.name === raw.name && item.size === raw.size)
  if (!exists) {
    uploadQueue.value.push({
      uid: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      file: raw,
      name: raw.name,
      size: raw.size,
      status: 'pending',
    })
  }
}

function removeUpload(uid) {
  uploadQueue.value = uploadQueue.value.filter((item) => item.uid !== uid)
}

// ── 历史资料选择功能 ──
async function loadExistingSources(accId) {
  if (!accId) {
    existingSources.value = []
    selectedSourceIds.value = new Set()
    return
  }
  try {
    const res = await publishApi.kbListSources(accId)
    const sources = Array.isArray(res) ? res : []
    existingSources.value = sources
    // 默认全选已解析的资料
    selectedSourceIds.value = new Set(
      sources.filter(s => s.parsed).map(s => s.id)
    )
  } catch (e) {
    console.warn('加载历史资料失败:', e)
    existingSources.value = []
    selectedSourceIds.value = new Set()
  }
}

function toggleSource(id) {
  const newSet = new Set(selectedSourceIds.value)
  if (newSet.has(id)) {
    newSet.delete(id)
  } else {
    newSet.add(id)
  }
  selectedSourceIds.value = newSet
}

function toggleSelectAllSources() {
  if (isAllSourcesSelected.value) {
    selectedSourceIds.value = new Set()
  } else {
    selectedSourceIds.value = new Set(existingSources.value.map(s => s.id))
  }
}

async function loadAccounts() {
  const accountsRes = await api.listAccounts()
  allAccounts.value = Array.isArray(accountsRes) ? accountsRes : []
}

async function handleCustomerSaved(created) {
  await loadAccounts()
  const newId = Number(created?.id)
  if (Number.isFinite(newId)) accountId.value = newId
}

async function uploadFiles(files, account) {
  if (!files.length) return { saved: [], recognizeTasks: [] }
  files.forEach((f) => { f.status = 'pending' })
  const rawFiles = files.map((f) => f.file)
  const result = await publishApi.kbUploadSources(account, rawFiles)
  files.forEach((f) => { f.status = 'uploaded' })
  return {
    saved: result?.saved || [],
    recognizeTasks: result?.recognize_tasks || [],
  }
}

async function uploadOnly() {
  if (!canUploadOnly.value) return
  busy.value = 'upload'
  try {
    const result = await uploadFiles(uploadQueue.value, accountId.value)
    uploadQueue.value = []
    
    // 处理识别任务，显示浮窗
    const recognizeTasks = result.recognizeTasks || []
    if (recognizeTasks.length) {
      const firstTask = recognizeTasks[0]
      const fileNames = recognizeTasks.map(t => t.file_name).join('、')
      // 触发浮窗显示识别进度
      window.dispatchEvent(new CustomEvent('kb-task-start', {
        detail: {
          phase: 'llm',
          taskId: firstTask.task_id,
          accountId: accountId.value,
          accountName: pickedAccountLabel.value,
          taskType: 'recognize',
          hint: `智能识别中：${firstTask.file_name}`,
          text: `正在智能识别 ${recognizeTasks.length} 份资料：${fileNames}`,
        },
      }))
      ElMessage.info(`资料上传完成，正在智能识别中（${fileNames}），完成后右下角自动通知`)
    } else {
      ElMessage.success('资料上传完成')
    }
    
    // 通知父组件刷新资料列表
    emit('created', { action: 'uploaded', accountId: accountId.value })
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || e.message || '上传失败')
  } finally {
    busy.value = ''
  }
}

async function generateKb() {
  if (!canGenerate.value) {
    ElMessage.warning('请选择客户并选择或上传基础资料')
    return
  }
  busy.value = 'generate'
  try {
    // 合并：新上传的文件 + 已选的历史资料
    const uploadResult = await uploadFiles(uploadQueue.value, accountId.value)
    uploadQueue.value = []
    const newSourceIds = (uploadResult.saved || []).map((r) => Number(r.id)).filter(Boolean)
    // 合并历史已选资料ID
    const historySourceIds = Array.from(selectedSourceIds.value)
    const sourceIds = [...new Set([...historySourceIds, ...newSourceIds])]
    
    if (!sourceIds.length) throw new Error('资料未准备完成，请稍后重试')

    const result = await publishApi.kbGenerate(accountId.value, remark.value, sourceIds)

    // 【修复】通知全局 KbTaskFloat 组件显示离线任务
    window.dispatchEvent(new CustomEvent('kb-task-start', {
      detail: {
        phase: 'llm',
        taskId: result.task_id,
        accountId: accountId.value,
        accountName: pickedAccountLabel.value,
        hint: `AI 正在生成 ${pickedAccountLabel.value} 知识库...`,
        text: '正在分析基础资料并按 GEO 10 模块生成...',
      },
    }))

    // 【修复】立即关闭弹窗 + 重置 busy 状态（支持多任务：用户可立即创建下一个）
    visible.value = false
    busy.value = ''
    ElMessage.info('知识库生成任务已提交，可继续做其它事，完成后右下角自动通知')

    // 后台静默轮询（fire-and-forget，不阻塞 UI）
    pollTask(result.task_id).catch(() => {})
  } catch (e) {
    window.dispatchEvent(new CustomEvent('kb-task-failed', { detail: { error: e.message || '生成失败' } }))
    ElMessage.error(e?.response?.data?.error || e.message || '生成失败')
  } finally {
    // 【修复】确保 busy 始终被重置
    if (busy.value === 'generate') busy.value = ''
  }
}

async function pollTask(id) {
  if (pollTimer) clearInterval(pollTimer)
  return new Promise((resolve, reject) => {
    let attempts = 0
    pollTimer = setInterval(async () => {
      attempts += 1
      try {
        const status = await publishApi.kbTaskStatus(id)
        if (status.status === 'done') {
          clearInterval(pollTimer)
          pollTimer = null
          // 【修复】通知全局组件任务完成
          window.dispatchEvent(new CustomEvent('kb-task-done', {
            detail: { accountId: accountId.value, kbId: status.kb_id, version: status.version }
          }))
          ElMessage.success(`知识库 v${status.version} 生成完成`)
          visible.value = false
          emit('created', { ...status, accountId: accountId.value })
          resolve(status)
          return
        }
        if (status.status === 'failed') {
          clearInterval(pollTimer)
          pollTimer = null
          // 【修复】通知全局组件任务失败
          window.dispatchEvent(new CustomEvent('kb-task-failed', { detail: { error: status.error || '生成失败' } }))
          reject(new Error(status.error || '生成失败'))
          return
        }
        if (attempts > 180) {
          clearInterval(pollTimer)
          pollTimer = null
          reject(new Error('任务等待超时，请稍后在知识库列表刷新查看结果'))
        }
      } catch (e) {
        clearInterval(pollTimer)
        pollTimer = null
        reject(e)
      }
    }, 3000)
  })
}

function close() {
  visible.value = false
}

watch(
  () => props.modelValue,
  async (show) => {
    if (!show) return
    // 如果有预选客户 ID（详情页传入），直接使用
    if (props.defaultAccountId) {
      accountId.value = Number(props.defaultAccountId)
    } else {
      accountId.value = null
    }
    uploadQueue.value = []
    remark.value = ''
    existingSources.value = []
    selectedSourceIds.value = new Set()
    loadingAll.value = true
    try {
      await loadAccounts()
      // 加载预选客户的历史资料
      if (accountId.value) {
        await loadExistingSources(accountId.value)
      }
      await nextTick()
    } finally {
      loadingAll.value = false
    }
  }
)

watch(
  () => visible.value,
  (show) => {
    if (!show && pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }
)

function open() {
  visible.value = true
}

defineExpose({ open })
</script>

<style scoped>
/* ═══ Dialog 外壳 ═══ */
.kb-create-dialog :deep(.el-dialog) {
  border-radius: 20px;
  overflow: hidden;
  box-shadow:
    0 24px 64px -12px rgba(15, 23, 42, .24),
    0 0 0 1px rgba(15, 23, 42, .04);
  border: none;
  background: #fff;
}
.kb-create-dialog :deep(.el-dialog__header) { padding: 0; margin: 0; }
.kb-create-dialog :deep(.el-dialog__body) { padding: 24px 28px 6px; }
.kb-create-dialog :deep(.el-dialog__footer) {
  padding: 16px 24px;
  border-top: 1px solid #f1f5f9;
  background: #fafbfc;
}

/* ── Hero Header ── */
.kb-dlg-hero {
  position: relative; overflow: hidden;
  display: flex; align-items: center; gap: 14px;
  padding: 20px 24px 22px;
  background: linear-gradient(135deg, #eef2ff 0%, #faf5ff 50%, #fdf2ff 100%);
  border-bottom: 1px solid rgba(99, 102, 241, .12);
}
.kb-dlg-hero-bg {
  position: absolute; inset: 0;
  background-image:
    radial-gradient(circle at 90% 10%, rgba(139, 92, 246, .15) 0%, transparent 40%),
    radial-gradient(circle at 10% 90%, rgba(99, 102, 241, .12) 0%, transparent 40%);
  pointer-events: none;
}
.kb-dlg-hero-icon {
  position: relative; z-index: 1;
  width: 46px; height: 46px; border-radius: 13px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  display: flex; align-items: center; justify-content: center;
  color: #fff; flex-shrink: 0;
  box-shadow: 0 8px 18px -4px rgba(99, 102, 241, .55);
}
.kb-dlg-hero-text { position: relative; z-index: 1; flex: 1; min-width: 0; }
.kb-dlg-hero-title {
  font-size: 17px; font-weight: 700; color: #0f172a; line-height: 1.3;
  letter-spacing: -0.2px;
}
.kb-dlg-hero-sub {
  margin-top: 3px;
  font-size: 12.5px; color: #64748b; line-height: 1.5;
}
.kb-dlg-close {
  position: relative; z-index: 1;
  width: 30px; height: 30px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  background: transparent; border: none; cursor: pointer;
  color: #94a3b8; transition: all .15s;
}
.kb-dlg-close:hover { background: rgba(15, 23, 42, .06); color: #475569; }

/* ── Form ── */
.kb-create-form :deep(.el-form-item) { margin-bottom: 22px; }
.kb-create-form :deep(.el-form-item:last-child) { margin-bottom: 8px; }
.kb-create-form :deep(.el-form-item__label) {
  font-weight: 600; color: #1e293b; font-size: 13.5px;
  padding-right: 14px;
}
.kb-create-form :deep(.el-input__wrapper),
.kb-create-form :deep(.el-textarea__inner),
.kb-create-form :deep(.el-select__wrapper) {
  border-radius: 10px;
  box-shadow: 0 0 0 1px #e2e8f0 inset;
  transition: all .2s;
}
.kb-create-form :deep(.el-input__wrapper:hover),
.kb-create-form :deep(.el-select__wrapper:hover),
.kb-create-form :deep(.el-textarea__inner:hover) {
  box-shadow: 0 0 0 1px #cbd5e1 inset;
}
.kb-create-form :deep(.el-input.is-focus .el-input__wrapper),
.kb-create-form :deep(.el-textarea__inner:focus),
.kb-create-form :deep(.el-select.is-focused .el-select__wrapper) {
  box-shadow: 0 0 0 2px #6366f1 inset, 0 0 0 4px rgba(99, 102, 241, .12) !important;
}
.kb-create-form :deep(.el-form-item__content) {
  width: 100%; display: block; line-height: normal;
}
.kb-create-form :deep(.el-form-item__content > div),
.kb-create-form :deep(.el-form-item__content > .el-input),
.kb-create-form :deep(.el-form-item__content > .el-textarea) {
  width: 100%;
}

/* ── 字段提示 ── */
.kb-field-hint {
  display: flex; align-items: center; gap: 5px;
  font-size: 12px; color: #94a3b8;
  margin-top: 6px; line-height: 1.6;
}
.kb-field-hint.kb-hint-success {
  color: #15803d;
  background: linear-gradient(90deg, rgba(34, 197, 94, .08), transparent);
  padding: 6px 10px; border-radius: 6px;
  border-left: 3px solid #22c55e;
}
.kb-field-hint.kb-hint-success strong { color: #166534; }

/* ── 客户选择 picker ── */
.kb-field-row {
  display: flex; gap: 10px; align-items: center;
  width: 100%;
}
.kb-acct-picker {
  flex: 1; min-width: 0;
  display: flex; align-items: center; justify-content: space-between;
  gap: 8px;
  height: 40px; padding: 0 14px;
  background: #fff; border: 1px solid #dcdfe6;
  border-radius: 8px;
  font-size: 14px; color: #1e293b;
  cursor: pointer; transition: border-color .15s, box-shadow .15s;
  font-family: inherit;
}
.kb-acct-picker:hover { border-color: #c0c4cc; }
.kb-acct-picker:focus { outline: none; border-color: #6366f1; box-shadow: 0 0 0 2px rgba(99,102,241,.15); }
.kb-acct-picker.empty .kb-acct-picker-placeholder { color: #a8abb2; }
.kb-acct-picker-name {
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-weight: 500;
}
.kb-acct-picker-arrow { color: #909399; font-size: 12px; flex-shrink: 0; }

/* ── 客户选择弹窗 ── */
.acct-picker-body { display: flex; flex-direction: column; gap: 12px; }
.acct-picker-search :deep(.el-input__wrapper) { border-radius: 8px; }
.acct-picker-count { font-size: 12px; color: #94a3b8; padding: 0 4px; }
.acct-picker-list {
  max-height: 50vh; overflow-y: auto;
  display: flex; flex-direction: column; gap: 4px;
  padding: 4px; border: 1px solid #f1f5f9; border-radius: 8px;
  background: #fafbfc;
}
.acct-picker-row {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; padding: 12px 14px;
  background: #fff; border: 1px solid transparent; border-radius: 7px;
  cursor: pointer; transition: all .12s;
  font-family: inherit; text-align: left; width: 100%;
}
.acct-picker-row:hover { border-color: #93c5fd; background: #eff6ff; }
.acct-picker-row.active { background: #eff6ff; border-color: #2563eb; }
.acct-picker-row-main { display: flex; flex-direction: column; gap: 3px; min-width: 0; flex: 1; }
.acct-picker-row-name { font-size: 14px; font-weight: 600; color: #0f172a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.acct-picker-row-brand { font-size: 12px; color: #64748b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.acct-picker-row-check { color: #2563eb; font-size: 18px; flex-shrink: 0; }
.acct-picker-empty {
  text-align: center; padding: 28px 16px;
  color: #94a3b8; font-size: 13px;
}

/* ── 上传卡片 ── */
.kb-upload-card {
  background: #f8fafc;
  border-radius: 14px;
  padding: 16px;
  border: 1px solid #e2e8f0;
  width: 100%; box-sizing: border-box;
}
.kb-upload-zone-v2 :deep(.el-upload) { display: block; width: 100%; }
.kb-upload-zone-v2 :deep(.el-upload-dragger) {
  width: 100%;
  padding: 22px 16px;
  border-radius: 12px;
  border: 2px dashed #cbd5e1;
  background: linear-gradient(180deg, #ffffff 0%, #fafbff 100%);
  transition: all .25s cubic-bezier(.4, 0, .2, 1);
  position: relative; overflow: hidden;
  box-sizing: border-box;
}
.kb-upload-zone-v2 :deep(.el-upload-dragger:hover) {
  border-color: #6366f1;
  background: linear-gradient(180deg, #ffffff 0%, #f0f3ff 100%);
  transform: translateY(-2px);
  box-shadow: 0 14px 32px -10px rgba(99, 102, 241, .28);
}
.kb-upload-zone-v2 :deep(.el-upload-dragger.is-dragover) {
  border-color: #6366f1;
  background: #eef2ff;
  transform: scale(1.005);
  box-shadow: 0 0 0 4px rgba(99, 102, 241, .15);
}
.kb-upload-inner {
  display: flex; flex-direction: column; align-items: center; gap: 10px;
}
.kb-upload-icon-wrap {
  width: 56px; height: 56px; border-radius: 16px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  box-shadow: 0 12px 24px -8px rgba(99, 102, 241, .45);
  animation: kbFloat 3.5s ease-in-out infinite;
}
@keyframes kbFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-5px); }
}
.kb-upload-main {
  font-size: 14.5px; color: #1e293b; font-weight: 500;
}
.kb-upload-main em {
  color: #6366f1; font-style: normal; font-weight: 700;
  position: relative;
}
.kb-upload-main em::after {
  content: ''; position: absolute;
  left: 0; right: 0; bottom: -2px; height: 2px;
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
  border-radius: 2px;
}
.kb-upload-types {
  display: flex; gap: 6px; flex-wrap: wrap; justify-content: center;
}
.ft-chip {
  padding: 3px 11px; border-radius: 999px;
  font-size: 11px; font-weight: 700; letter-spacing: 0.3px;
}
.ft-chip.ft-pdf { background: #fee2e2; color: #b91c1c; }
.ft-chip.ft-doc { background: #dbeafe; color: #1d4ed8; }
.ft-chip.ft-xls { background: #d1fae5; color: #047857; }
.ft-chip.ft-img { background: #fef3c7; color: #b45309; }
.ft-chip.ft-txt { background: #f1f5f9; color: #475569; }
.kb-upload-foot {
  font-size: 11.5px; color: #94a3b8; margin-top: 2px;
}

/* ── 已选文件列表 ── */
.kb-fade-enter-active, .kb-fade-leave-active { transition: opacity .25s; }
.kb-fade-enter-from, .kb-fade-leave-to { opacity: 0; }

.kb-file-list {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed #cbd5e1;
}
.kb-file-list-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 10px;
  font-size: 12.5px; color: #475569; font-weight: 500;
}
.kb-file-list-head strong { color: #6366f1; font-weight: 700; }
.kb-file-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 8px;
}
.kb-file-card {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px;
  background: #fff; border-radius: 10px;
  border: 1px solid #e2e8f0;
  transition: all .2s;
  position: relative;
}
.kb-file-card:hover {
  border-color: #c7d2fe;
  box-shadow: 0 6px 14px -4px rgba(99, 102, 241, .15);
  transform: translateY(-1px);
}
.kb-file-meta { flex: 1; min-width: 0; }
.kb-file-name {
  font-size: 12.5px; color: #1e293b; font-weight: 500;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.kb-file-size {
  font-size: 10.5px; color: #94a3b8; margin-top: 2px;
}
.kb-file-rm {
  width: 22px; height: 22px; border-radius: 6px;
  background: transparent; border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  color: #cbd5e1; transition: all .15s; flex-shrink: 0;
}
.kb-file-rm:hover { background: #fee2e2; color: #dc2626; }

/* ── 历史资料选择区域 ── */
.kb-existing-sources {
  margin-bottom: 14px;
  padding: 14px;
  background: #f8fafc;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}
.kb-source-selectable {
  cursor: pointer;
  user-select: none;
}
.kb-source-selectable:hover {
  border-color: #a5b4fc;
  background: #f5f3ff;
}
.kb-source-selectable.selected {
  border-color: #6366f1;
  background: #eef2ff;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, .1);
}
.kb-source-checkbox {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: #6366f1;
  flex-shrink: 0;
}
.kb-source-selectable .kb-file-meta {
  padding-left: 26px; /* 为checkbox留空间 */
}
.kb-file-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10.5px;
  margin-top: 2px;
}
.status-parsed {
  color: #16a34a;
  font-weight: 500;
}
.status-pending {
  color: #d97706;
  font-weight: 500;
}
.kb-upload-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 14px 0;
  color: #94a3b8;
  font-size: 12px;
}
.kb-upload-divider::before,
.kb-upload-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #e2e8f0;
}
.kb-sources-hint {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11.5px;
  color: #64748b;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #e2e8f0;
}

/* ── Footer ── */
.kb-footer {
  display: flex; justify-content: space-between; align-items: center; gap: 10px;
}
.kb-footer-actions { display: flex; gap: 8px; }
.kb-create-dialog :deep(.el-button) {
  border-radius: 10px;
  font-weight: 500;
  transition: transform .15s, box-shadow .15s, background .2s;
}
.kb-create-dialog :deep(.el-button.el-button--large) {
  height: 40px; padding: 0 18px; font-size: 13.5px;
}
.kb-create-dialog :deep(.el-button:not(.is-disabled):not(.is-text):hover) {
  transform: translateY(-1px);
}
.kb-btn-gen {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
  border-color: transparent !important;
  box-shadow: 0 6px 16px -4px rgba(99, 102, 241, .4);
}
.kb-btn-gen:not(.is-disabled):hover {
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%) !important;
  box-shadow: 0 12px 24px -6px rgba(99, 102, 241, .5) !important;
}
.kb-btn-gen.is-disabled {
  background: #cbd5e1 !important; box-shadow: none !important;
}

/* ── 响应式 ── */
@media (max-width: 640px) {
  .kb-field-row { flex-direction: column; align-items: stretch; }
  .kb-footer { flex-direction: column; align-items: stretch; }
  .kb-footer-actions { flex-direction: column; }
  .kb-file-grid { grid-template-columns: 1fr; }
}
</style>
