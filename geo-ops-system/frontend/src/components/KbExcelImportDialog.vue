<template>
  <el-dialog :model-value="modelValue" :title="null" width="min(920px, 95vw)" top="5vh"
             :close-on-click-modal="false" class="kb-import-dialog"
             @update:model-value="$emit('update:modelValue', $event)" @open="onOpen">
    <!-- Header -->
    <template #header>
      <div class="kx-header">
        <div class="kx-header-left">
          <div class="kx-header-icon"><el-icon :size="18"><UploadFilled /></el-icon></div>
          <div>
            <div class="kx-header-title">Excel 导入知识库</div>
            <div class="kx-header-desc">选择客户 → 上传文件 → 预览编辑 → 确认导入</div>
          </div>
        </div>
      </div>
    </template>

    <div class="kx-body">
      <!-- 步骤1: 选客户 + 传表 -->
      <div class="kx-step1">
        <div class="kx-field-group">
          <div class="kx-field">
            <label>导入到客户</label>
            <span v-if="locked" class="kx-locked"><el-icon :size="14"><User /></el-icon>{{ lockedName }}</span>
            <el-select v-else v-model="accountId" filterable placeholder="搜索并选择客户" style="width:320px" clearable>
              <el-option v-for="a in accounts" :key="a.id" :label="a.companyName || a.company_name || ('客户#'+a.id)" :value="a.id" />
            </el-select>
          </div>
        </div>

        <div class="kx-upload-row">
          <el-upload ref="uploadRef" :auto-upload="false" :show-file-list="true" :limit="1"
                     accept=".xlsx,.xls" :on-change="onFile" :on-remove="onRemove" :file-list="fileList">
            <el-button :icon="UploadFilled" type="primary">选择 Excel 文件</el-button>
          </el-upload>
          <el-button link type="primary" @click="downloadTemplate">
            <el-icon :size="14"><Download /></el-icon>下载模板
          </el-button>
        </div>
      </div>

      <!-- 覆盖/追加 -->
      <div v-if="curVersion" class="kx-mode">
        <span class="kx-mode-l">导入方式</span>
        <el-radio-group v-model="mode" size="small">
          <el-radio-button label="overwrite">覆盖（新建版本，仅含本次内容）</el-radio-button>
          <el-radio-button label="append">追加（接到当前 v{{ curVersion.version }} 之后）</el-radio-button>
        </el-radio-group>
        <span class="kx-mode-tip">{{ mode === 'append' ? '当前版本所有模块 + 本次新模块 → 生成新版本' : '只用本次 Excel 内容生成新版本（旧版保留可回滚）' }}</span>
      </div>

      <!-- 步骤2: 可编辑预览 -->
      <div v-if="rows.length" class="kx-preview">
        <div class="kx-preview-h">
          <div class="kx-preview-title">
            <el-icon :size="15" color="#667eea"><Document /></el-icon>
            内容预览 · 可直接编辑
            <el-tag size="small" type="info" effect="plain" round>{{ rows.length }} 行</el-tag>
          </div>
          <el-button size="small" :icon="Plus" @click="addRow">添加行</el-button>
        </div>
        <el-table :data="rows" size="small" max-height="42vh" border class="kx-table">
          <el-table-column type="index" label="#" width="48" align="center" />
          <el-table-column label="模块名称" width="130">
            <template #default="{ row }"><el-input v-model="row.module" size="small" placeholder="M01" /></template>
          </el-table-column>
          <el-table-column label="标题" width="220">
            <template #default="{ row }"><el-input v-model="row.title" size="small" :class="{ bad: !row.title.trim() }" /></template>
          </el-table-column>
          <el-table-column label="知识库内容" min-width="200">
            <template #default="{ row }"><el-input v-model="row.content" size="small" type="textarea" :autosize="{minRows:1,maxRows:5}" :class="{ bad: !row.content.trim() }" /></template>
          </el-table-column>
          <el-table-column label="操作" width="60" align="center">
            <template #default="{ $index }">
              <el-button link type="danger" size="small" @click="rows.splice($index,1)"><el-icon :size="14"><Delete /></el-icon></el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="kx-note">
          <label>版本备注(可选)</label>
          <el-input v-model="note" size="small" placeholder="如：2026-06 知识库初版 / 第二次修订" style="width:380px" />
        </div>
      </div>
      <div v-else class="kx-empty">
        <el-icon :size="36" color="#e2e8f0"><UploadFilled /></el-icon>
        <p>选择客户并上传 Excel 后</p>
        <p class="kx-empty-sub">此处将出现可编辑的内容预览</p>
      </div>
    </div>

    <template #footer>
      <span class="kx-foot-hint">{{ validHint }}</span>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :icon="Check" :loading="submitting" :disabled="!canSubmit" @click="submit">
        确认导入
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { UploadFilled, Plus, Check, Download, Delete, Document, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as XLSX from 'xlsx'
import axios from 'axios'
import publishApi from '@/api/publish'

const props = defineProps({
  modelValue: Boolean,
  defaultAccountId: { type: [Number, String], default: null },
  clientName: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'done'])

const accounts = ref([])
const accountId = ref(null)
const locked = computed(() => !!props.defaultAccountId)
const lockedName = computed(() => props.clientName
  || (accounts.value.find(a => a.id === props.defaultAccountId)?.companyName) || '当前客户')
const rows = ref([])
const note = ref('')
const submitting = ref(false)
const mode = ref('overwrite')
const curVersion = ref(null)
const fileList = ref([])

async function fetchCurrent() {
  curVersion.value = null
  if (!accountId.value) return
  try {
    const r = await axios.get('/api/kb/current', { params: { account_id: accountId.value }, withCredentials: true })
    curVersion.value = r.data?.item || null
  } catch { curVersion.value = null }
}
watch(accountId, fetchCurrent)

async function onOpen() {
  accountId.value = props.defaultAccountId || accountId.value
  rows.value = []; note.value = ''; mode.value = 'overwrite'; fileList.value = []
  if (!accounts.value.length) {
    try { const r = await axios.get('/api/kb/accounts', { params: { formal: 1 }, withCredentials: true }); accounts.value = r.data?.accounts || [] } catch { accounts.value = [] }
  }
  fetchCurrent()
}

function onRemove() {
  // 文件被移除时清空解析结果（可选保留）
}

function onFile(uploadFile) {
  const file = uploadFile.raw || uploadFile
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const wb = XLSX.read(e.target.result, { type: 'array' })
      const ws = wb.Sheets[wb.SheetNames[0]]
      const aoa = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' })
      if (!aoa.length) { ElMessage.warning('表格为空'); return }
      // 列定位:按表头关键字,否则按 0/1/2 位置
      let h = aoa[0].map(x => String(x || '').trim())
      const findCol = (kw) => h.findIndex(c => kw.some(k => c.includes(k)))
      let mi = findCol(['模块']), ti = findCol(['标题', 'title']), ci = findCol(['内容', 'content'])
      let start = 1
      if (ti < 0 && ci < 0) { mi = 0; ti = 1; ci = 2; start = 0 } // 无表头,按位置
      else { if (mi < 0) mi = 0; if (ti < 0) ti = 1; if (ci < 0) ci = 2 }
      const out = []
      for (let i = start; i < aoa.length; i++) {
        const r = aoa[i]
        const module = String(r[mi] ?? '').trim()
        const title = String(r[ti] ?? '').trim()
        const content = String(r[ci] ?? '').trim()
        if (!title && !content && !module) continue
        out.push({ module, title, content })
      }
      if (!out.length) { ElMessage.warning('未解析到有效行'); return }
      rows.value = out
      ElMessage.success(`已解析 ${out.length} 行,请核对后导入`)
    } catch (err) { ElMessage.error('解析失败:' + (err.message || err)) }
  }
  reader.readAsArrayBuffer(file)
}

function addRow() { rows.value.push({ module: '', title: '', content: '' }) }

const validRows = computed(() => rows.value.filter(r => r.title.trim() && r.content.trim()))
const canSubmit = computed(() => !!accountId.value && validRows.value.length > 0)
const validHint = computed(() => {
  if (!accountId.value) return '请先选择客户'
  if (!rows.value.length) return ''
  const bad = rows.value.length - validRows.value.length
  return bad ? `${bad} 行标题/内容为空将被跳过` : `将导入 ${validRows.value.length} 行`
})

function buildMarkdown() {
  return validRows.value.map(r => {
    const head = r.module.trim() ? `## 【${r.module.trim()}】${r.title.trim()}` : `## ${r.title.trim()}`
    return `${head}\n\n${r.content.trim()}\n`
  }).join('\n')
}

async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  try {
    const md = buildMarkdown()
    const tail = note.value.trim() ? '：' + note.value.trim() : ''
    let r
    if (mode.value === 'append' && curVersion.value) {
      const combined = (curVersion.value.content || '').replace(/\s+$/, '') + '\n\n' + md
      r = await publishApi.kbSaveHuman(curVersion.value.id, combined, 'Excel追加导入' + tail)
    } else {
      r = await publishApi.kbImportHuman(accountId.value, md, 'Excel手动上传' + tail)
    }
    const act = (mode.value === 'append' && curVersion.value) ? '追加' : '导入'
    ElMessage.success(`已${act}为新版本${r.version ? ' v' + r.version : ''}，本次 ${validRows.value.length} 个模块`)
    emit('done', { accountId: accountId.value })
    emit('update:modelValue', false)
  } catch (e) {
    ElMessage.error('导入失败:' + (e.response?.data?.error || e.message))
  } finally { submitting.value = false }
}

// 下载用户提供的真实模板
function downloadTemplate() {
  const a = document.createElement('a')
  a.href = '/templates/知识库导入模板.xlsx'
  a.download = '知识库导入模板.xlsx'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  ElMessage.success('正在下载模板…')
}
</script>

<style scoped>
/* ===== KB Excel 导入弹窗 - 统一样式 ===== */

/* Dialog 容器 */
.kb-import-dialog :deep(.el-dialog) { border-radius: 16px; overflow: hidden; }
.kb-import-dialog :deep(.el-dialog__header) { padding: 0; margin: 0; }
.kb-import-dialog :deep(.el-dialog__body) { padding: 0; }
.kb-import-dialog :deep(.el-dialog__footer) { padding: 16px 24px 20px; border-top: 1px solid #f1f5f9; }
.kb-import-dialog :deep(.el-dialog__headerbtn .el-dialog__close) { color: rgba(255,255,255,0.85); font-size: 18px; }
.kb-import-dialog :deep(.el-dialog__headerbtn .el-dialog__close:hover) { color: #fff; }

/* Header */
.kx-header { display: flex; align-items: center; justify-content: space-between; padding: 20px 24px 16px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
.kx-header-left { display: flex; align-items: center; gap: 12px; }
.kx-header-icon { width: 40px; height: 40px; border-radius: 10px; background: rgba(255,255,255,0.2); backdrop-filter: blur(8px); display: flex; align-items: center; justify-content: center; color: #fff; flex-shrink: 0; }
.kx-header-title { font-size: 17px; font-weight: 700; color: #fff; line-height: 1.3; letter-spacing: -0.01em; }
.kx-header-desc { font-size: 12px; color: rgba(255,255,255,0.75); margin-top: 2px; }

/* Body */
.kx-body { padding: 20px 24px 24px; display: flex; flex-direction: column; gap: 16px; }

/* 步骤1: 选择区域 */
.kx-step1 { display: flex; flex-direction: column; gap: 14px; }
.kx-field-group { display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
.kx-field { display: flex; align-items: center; gap: 10px; }
.kx-field label { font-size: 13px; font-weight: 600; color: #374151; white-space: nowrap; }
.kx-locked { display: inline-flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; color: #1e293b; background: #f1f5f9; padding: 4px 12px; border-radius: 8px; }
.kx-upload-row { display: flex; align-items: center; gap: 16px; padding: 14px 16px; background: #fafbff; border: 1.5px dashed #d1d9ee; border-radius: 12px; }

/* 导入方式 */
.kx-mode { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; padding: 12px 16px; background: linear-gradient(135deg, #f8fafc, #fff); border: 1px solid #e2e8f0; border-radius: 12px; }
.kx-mode-l { font-size: 13px; color: #475569; font-weight: 600; }
.kx-mode-tip { font-size: 12px; color: #94a3b8; }

/* 预览区 */
.kx-preview { display: flex; flex-direction: column; gap: 10px; }
.kx-preview-h { display: flex; align-items: center; justify-content: space-between; }
.kx-preview-title { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 600; color: #334155; }
.kx-preview-title .el-tag { font-size: 11px; margin-left: 4px; }
.kx-table { border-radius: 10px; overflow: hidden; }
.kx-table :deep(.el-table__header th) { background: #f8fafc !important; color: #64748b; font-weight: 600; font-size: 12px; }
.kx-table :deep(.el-table__row:hover > td) { background: #f8fafc !important; }
.kx-note { display: flex; align-items: center; gap: 10px; margin-top: 4px; }
.kx-note label { font-size: 13px; color: #475569; font-weight: 500; }

/* 空态 */
.kx-empty { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 50px 0 30px; color: #cbd5e1; }
.kx-empty p { font-size: 14px; margin: 0; }
.kx-empty-sub { font-size: 12px !important; color: #e2e8f0 !important; }

/* Footer */
.kx-foot-hint { font-size: 12px; color: #94a3b8; margin-right: auto; }

/* 必填校验红框 */
:deep(.bad .el-input__wrapper), :deep(.bad .el-textarea__inner) { box-shadow: 0 0 0 1px #fca5a5 inset; }
</style>
