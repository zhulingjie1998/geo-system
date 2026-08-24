<template>
  <div class="publish-customers-page">
    <!-- 主面板：工具栏 + 表格 -->
    <section class="panel">
      <!-- 工具栏 -->
      <div class="toolbar">
        <div class="toolbar-tabs">
          <button class="seg active">
            正式客户 <span class="seg-count">{{ accounts.length }}</span>
          </button>
        </div>
        <div class="toolbar-actions">
          <el-input
            v-model="searchText"
            placeholder="搜索公司或品牌..."
            clearable
            :prefix-icon="Search"
            class="toolbar-search"
          />
          <el-button :icon="Refresh" plain @click="loadData">刷新</el-button>
          <el-button type="primary" :icon="Plus" @click="openAddDialog">新建客户</el-button>
        </div>
      </div>

      <!-- 表格 -->
      <el-table
        :data="filteredAccounts"
        v-loading="loading"
        row-key="id"
        class="account-table"
        :header-cell-style="{ background: 'transparent', color: '#64748b', fontWeight: 600, fontSize: '12px', letterSpacing: '0.3px' }"
      >
        <el-table-column label="" width="40" align="center">
          <template #default="{ row }">
            <span class="ca-type-dot ca-dot-paid"></span>
          </template>
        </el-table-column>

        <el-table-column label="客户" min-width="220" sortable>
          <template #default="{ row }">
            <div class="customer-cell" @click.stop="openEditDialog(row)">
              <div class="cust-avatar" :style="{ background: avatarColor(row) }">{{ avatarLetter(row) }}</div>
              <div class="cust-info">
                <div class="ca-name-row">
                  <span class="ca-name">{{ row.companyName }}</span>
                </div>
                <div class="ca-meta">
                  <span class="ca-meta-item">{{ row.keywordCount || 0 }} 词</span>
                  <span class="ca-meta-sep">·</span>
                  <span class="ca-meta-item">{{ row.platforms?.length || 0 }} 平台</span>
                </div>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="品牌" min-width="140">
          <template #default="{ row }">
            <template v-if="row.companyBrands?.length || row.companyBrand">
              <el-tag v-for="b in (row.companyBrands || (row.companyBrand ? [row.companyBrand] : []))" :key="b" size="small" class="brand-tag">{{ b }}</el-tag>
            </template>
            <span v-else class="muted">未设置</span>
          </template>
        </el-table-column>

        <el-table-column label="覆盖平台" min-width="160">
          <template #default="{ row }">
            <div v-if="row.platforms?.length" class="platforms-cell">
              <PlatformIcon v-for="p in row.platforms" :key="p" :name="p" :size="24" />
            </div>
            <span v-else class="muted">未配置</span>
          </template>
        </el-table-column>

        <el-table-column prop="createdAt" label="创建时间" width="160" sortable>
          <template #default="{ row }">
            <span v-if="row.createdAt" class="ymd-cell">{{ String(row.createdAt).slice(0, 16) }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="260" fixed="right" align="center">
          <template #default="{ row }">
            <div class="act-btn-group">
              <button class="act-btn act-btn-primary" @click.stop="goKnowledge(row)">知识库</button>
              <button class="act-btn act-btn-lib" @click.stop="goContentLibrary(row)">内容库</button>
              <button class="act-btn act-btn-default" @click.stop="openEditDialog(row)">编辑</button>
              <button class="act-btn act-btn-danger" @click.stop="handleDelete(row)">删除</button>
            </div>
          </template>
        </el-table-column>

        <template #empty>
          <div class="table-empty">
            <el-icon :size="40" color="#cbd5e1"><OfficeBuilding /></el-icon>
            <p>暂无客户数据</p>
            <el-button type="primary" size="small" @click="openAddDialog">添加第一个客户</el-button>
          </div>
        </template>
      </el-table>
    </section>

    <!-- ============ 添加/编辑弹窗（两步表单） ============ -->
    <el-dialog
      v-model="dialogVisible"
      :title="null"
      width="min(720px, 92vw)"
      top="6vh"
      :close-on-click-modal="false"
      class="customer-dialog"
      @opened="onDialogOpened"
    >
      <!-- 自定义 Header -->
      <template #header>
        <div class="cd-header">
          <div class="cd-header-left">
            <div class="cd-header-icon">
              <el-icon :size="18"><OfficeBuilding /></el-icon>
            </div>
            <div>
              <div class="cd-header-title">{{ isEditing ? '编辑客户信息' : '添加正式客户' }}</div>
              <div class="cd-header-desc">{{ isEditing ? '仅支持修改公司、品牌与平台信息' : '录入公司 · 品牌 · 查询关键词' }}</div>
            </div>
          </div>
        </div>
      </template>

      <!-- 步骤指示器 -->
      <div v-if="!isEditing" class="cd-steps">
        <div class="cd-step-item" :class="{ active: dialogStep === 1, done: dialogStep > 1 }">
          <div class="cd-step-num">
            <el-icon v-if="dialogStep > 1" :size="11"><Select /></el-icon>
            <span v-else>1</span>
          </div>
          <span class="cd-step-label">基础信息</span>
        </div>
        <div class="cd-step-connector">
          <div class="cd-step-line" :class="{ filled: dialogStep > 1 }"></div>
        </div>
        <div class="cd-step-item" :class="{ active: dialogStep === 2, done: dialogStep > 2 }">
          <div class="cd-step-num">
            <el-icon v-if="dialogStep > 2" :size="11"><Select /></el-icon>
            <span v-else>2</span>
          </div>
          <span class="cd-step-label">关键词（可空）</span>
        </div>
      </div>

      <!-- 第一步：基础信息 -->
      <div v-show="isEditing || dialogStep === 1" class="cd-body">
        <el-form :model="form" label-position="top" class="cd-form">
          <el-form-item label="公司名称" required>
            <el-input ref="companyInput" v-model="form.companyName" placeholder="请输入公司名称" />
          </el-form-item>
          <el-form-item label="公司品牌" required>
            <el-select
              v-model="form.companyBrands"
              multiple filterable allow-create default-first-option
              placeholder="输入品牌名后回车添加，支持多个" style="width: 100%"
            >
              <el-option v-for="b in brandSuggestions(form.companyBrands)" :key="b" :label="b" :value="b" />
            </el-select>
          </el-form-item>
          <el-form-item label="覆盖平台">
            <PlatformSelector v-model="form.platforms" />
          </el-form-item>
        </el-form>
      </div>

      <!-- 第二步：关键词导入 -->
      <div v-show="!isEditing && dialogStep === 2" class="cd-body cd-body-kw">
        <div class="kw-hint-bar">
          <span class="kw-hint-text">
            每行一条，格式：<code>AI提示词｜类型｜搜索意图</code>
            （支持 <code>|</code> <code>｜</code> Tab 分隔）
          </span>
          <el-button link type="primary" size="small" @click="downloadTemplate">
            <el-icon :size="13"><Download /></el-icon>下载模板
          </el-button>
        </div>

        <el-input
          v-model="keywordBatchText"
          type="textarea"
          :autosize="{ minRows: 3, maxRows: 8 }"
          placeholder="粘贴关键词，每行一条..."
          class="kw-textarea"
        />

        <div class="kw-actions">
          <el-button type="primary" size="small" @click="importBatchKeywords">
            <el-icon :size="13"><Upload /></el-icon>批量导入
          </el-button>
          <span v-if="keywordBatchText.trim()" class="kw-paste-count">
            已输入 {{ keywordBatchText.trim().split(/\n+/).filter(Boolean).length }} 行
          </span>
        </div>

        <div class="kw-section-title">
          <span class="kw-section-icon"><el-icon :size="15"><Document /></el-icon></span>
          关键词列表
          <el-tag size="small" type="info" effect="plain" round>{{ keywordDraftRows.length }} 条</el-tag>
        </div>

        <el-table :data="keywordDraftRows" height="220" border size="small" class="kw-table" empty-text="暂无关键词，请在上方粘贴或手动添加">
          <el-table-column type="index" label="#" width="46" align="center" />
          <el-table-column prop="intentPrompt" label="AI 提示词" min-width="260" show-overflow-tooltip />
          <el-table-column prop="intentCategory" label="类型" width="100" />
          <el-table-column prop="coreIntentWord" label="搜索意图" width="130" />
          <el-table-column label="操作" width="56" align="center">
            <template #default="{ $index }">
              <el-button link type="danger" size="small" @click="keywordDraftRows.splice($index, 1)">
                <el-icon :size="14"><Delete /></el-icon>
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="isEditing && originalKeywordsCount > 0" class="kw-warning-box">
          <el-icon :size="15" color="#eab308"><WarningFilled /></el-icon>
          <span>原有 <b>{{ originalKeywordsCount }}</b> 条关键词，保存后将 {{ keywordDraftRows.length ? '<b>被替换</b>' : '<b>清空</b>' }}</span>
        </div>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button v-if="!isEditing && dialogStep === 2" :icon="ArrowLeft" @click="dialogStep = 1">上一步</el-button>
        <el-button v-if="!isEditing && dialogStep === 1" type="primary" @click="onNextStep">
          下一步 <el-icon class="el-icon--right"><ArrowRight /></el-icon>
        </el-button>
        <el-button v-if="isEditing || dialogStep === 2" type="primary" :loading="saving" @click="handleSubmit">
          {{ isEditing ? '保存修改' : '确认创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Search, Refresh, Plus, ArrowLeft, ArrowRight, OfficeBuilding, InfoFilled, Select, Download, Upload, Delete, Document, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import PlatformIcon from '../components/PlatformIcon.vue'
import PlatformSelector from '../components/common/PlatformSelector.vue'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const searchText = ref('')
const accounts = ref([])

/* ========== 弹窗状态 ========== */
const dialogVisible = ref(false)
const dialogStep = ref(1)       // 1=基础信息  2=关键词
const isEditing = ref(false)    // false=新建  true=编辑
const editAccount = ref(null)   // 编辑时当前客户对象
const originalKeywordsCount = ref(0) // 编辑时原有关键词数

const form = reactive({
  companyName: '',
  companyBrands: [],
  platforms: [],
})

const keywordBatchText = ref('')
const keywordDraftRows = ref([])
const companyInput = ref(null)

// 筛选后的数据
const filteredAccounts = computed(() => {
  const q = searchText.value.trim().toLowerCase()
  const filtered = q
    ? accounts.value.filter(a =>
        (a.companyName || '').toLowerCase().includes(q) ||
        (a.companyBrand || '').toLowerCase().includes(q) ||
        (a.companyBrands || []).some(b => b.toLowerCase().includes(q))
      )
    : accounts.value
  return [...filtered].sort((a, b) => {
    const ta = a.updatedAt || a.createdAt || ''
    const tb = b.updatedAt || b.createdAt || ''
    return tb.localeCompare(ta)
  })
})

function brandSuggestions(selected) {
  const all = new Set(accounts.value.flatMap(a => a.companyBrands || []))
  return [...all].filter(b => !selected.includes(b)).slice(0, 20)
}

async function loadData() {
  loading.value = true
  try {
    const data = await api.listAccounts()
    // 兼容后端只返回单一 companyBrand 字段：统一在前端维护 companyBrands 数组用于 UI
    const rows = Array.isArray(data) ? data : []
    accounts.value = rows.map(r => ({
      ...r,
      companyBrands: Array.isArray(r.companyBrands) && r.companyBrands.length ? r.companyBrands : (r.companyBrand ? [r.companyBrand] : []),
    }))
  } catch {
    // 静默失败
  } finally {
    loading.value = false
  }
}

/* ========== 新建客户 ========== */
function openAddDialog() {
  isEditing.value = false
  editAccount.value = null
  form.companyName = ''
  form.companyBrands = []
  form.platforms = []
  keywordDraftRows.value = []
  keywordBatchText.value = ''
  dialogStep.value = 1
  dialogVisible.value = true
}

/* ========== 编辑客户 ========== */
async function openEditDialog(row) {
  isEditing.value = true
  editAccount.value = row
  form.companyName = row.companyName || ''
  form.companyBrands = Array.isArray(row.companyBrands) && row.companyBrands.length ? [...row.companyBrands] : (row.companyBrand ? [row.companyBrand] : [])
  form.platforms = Array.isArray(row.platforms) ? [...row.platforms] : []
  keywordBatchText.value = ''
  dialogStep.value = 1
  dialogVisible.value = true
}

function onDialogOpened() {
  nextTick(() => { companyInput.value?.focus?.() })
}

function onNextStep() {
  if (!form.companyName?.trim()) {
    ElMessage.warning('请输入公司名称')
    return
  }
  if (!(form.companyBrands || []).length) {
    ElMessage.warning('请至少添加一个公司品牌')
    return
  }
  dialogStep.value = 2
}

/* ========== 提交：新建 or 编辑 ========== */
async function handleSubmit() {
  if (!form.companyName || !form.companyBrands?.length) {
    ElMessage.warning('请填写公司名称和品牌'); dialogStep.value = 1; return
  }

  saving.value = true
  try {
    if (isEditing.value) {
      // 编辑模式：仅更新客户信息
      await api.updateAccount(editAccount.value.id, {
        companyName: form.companyName,
        // 后端存储单一 companyBrand 字段，取第一个作为主品牌
        companyBrand: (form.companyBrands && form.companyBrands.length) ? form.companyBrands[0] : (form.companyBrands || '') ,
        platforms: form.platforms,
      })
      ElMessage.success('客户信息已更新')
    } else {
      // 新建模式：创建客户 + 关键词
      const created = await api.createAccount({
        companyName: form.companyName,
        companyBrand: (form.companyBrands && form.companyBrands.length) ? form.companyBrands[0] : (form.companyBrands || ''),
        platforms: form.platforms,
      })
      if (keywordDraftRows.value.length && created?.id) {
        try { await api.updateAccountKeywords(created.id, keywordDraftRows.value) }
        catch { ElMessage.warning('客户已创建，但关键词保存失败，请补录') }
      }
      ElMessage.success(keywordDraftRows.value.length
        ? `客户创建成功，已配置 ${keywordDraftRows.value.length} 条关键词`
        : '客户创建成功')
    }

    dialogVisible.value = false
    await loadData()
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || (isEditing.value ? '保存失败' : '创建失败'))
  } finally {
    saving.value = false
  }
}

/* ========== 关键词导入 ========== */
function importBatchKeywords() {
  const lines = String(keywordBatchText.value || '').split(/\n+/).map(l => l.trim()).filter(Boolean)
  if (!lines.length) { ElMessage.warning('请先输入关键词内容'); return }
  const existing = new Set(keywordDraftRows.value.map(k => k.intentPrompt.trim()))
  let success = 0, failed = 0, duped = 0
  for (const line of lines) {
    const parts = line.split(/[|｜\t]/)
    const prompt = (parts[0] || '').trim()
    if (!prompt) { failed++; continue }
    if (existing.has(prompt)) { duped++; continue }
    keywordDraftRows.value.push({
      intentPrompt: prompt,
      intentCategory: (parts[1] || '').trim(),
      coreIntentWord: (parts[2] || '').trim(),
    })
    existing.add(prompt)
    success++
  }
  keywordBatchText.value = ''
  let msg = `导入成功 ${success} 条`
  if (duped) msg += `，跳过重复 ${duped} 条`
  if (failed) msg += `，格式错误 ${failed} 条`
  ElMessage.success(msg)
}

function downloadTemplate() {
  const rows = [
    ['AI提示词', '类型（可选）', '搜索意图（可选）'],
    ['帮我推荐一款好用的手推车', '产品推荐', '手推车推荐'],
    ['哪家公司的物流设备比较好', '品牌对比', '物流设备品牌'],
    ['我需要找有丰富经验的设备供应商', '供应商寻找', '设备供应商'],
  ]
  const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = '关键词导入模板.csv'; a.click()
  URL.revokeObjectURL(url)
}

/* ========== 删除（二次确认） ========== */
async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定要删除客户「<b>${row.companyName}</b>」吗？<br/><span style="color:#94a3b8;font-size:12px">删除后该客户的所有数据将被移除，此操作不可恢复。</span>`,
      '确认删除',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
        dangerouslyUseHTMLString: true,
      }
    )
  } catch {
    return // 用户取消
  }

  try {
    await api.deleteAccount(row.id)
    ElMessage.success(`客户「${row.companyName}」已删除`)
    await loadData()
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '删除失败')
  }
}

/* ========== 导航 ========== */
function goKnowledge(row) {
  // 跳转到该客户的知识库详情页（如果已有知识库）或列表页
  router.push({ path: `/publish/customer-kb/${row.id}` })
}

function goContentLibrary(row) {
  // 跳转到该客户的内容库详情页
  const brand = Array.isArray(row.companyBrands) && row.companyBrands.length
    ? row.companyBrands[0]
    : (row.companyBrand || '')
  router.push({
    path: `/publish/content-library/${row.id}`,
    query: { accountId: row.id, accountName: row.companyName, accountBrand: brand },
  })
}

// 头像颜色（根据名称生成稳定颜色）
function avatarColor(row) {
  const colors = ['#6366f1', '#10b981', '#ec4899', '#f59e0b', '#14b8a6', '#8b5cf6']
  const name = (row.companyName || '')
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return colors[Math.abs(hash) % colors.length]
}

function avatarLetter(row) {
  return (row.companyName || '?')[0] || '?'
}

onMounted(() => loadData())
</script>

<style scoped>
/* ===== 面板 ===== */
.publish-customers-page { display: flex; flex-direction: column; gap: 18px; }

.panel {
  background: #fff; border: 1px solid #eef1f6; border-radius: 12px;
  padding: 20px 24px;
}

/* ===== 工具栏 ===== */
.toolbar { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
.toolbar-tabs { display: flex; gap: 8px; }
.seg {
  padding: 7px 16px; border-radius: 8px; font-size: 13px; font-weight: 500;
  border: 1px solid #e2e8f0; background: #fff; color: #475569; cursor: pointer;
  transition: all .18s ease;
}
.seg.active {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #fff; border-color: transparent; box-shadow: 0 2px 8px rgba(59,130,246,.3);
}
.seg-count { opacity: .85; margin-left: 3px; font-size: 12px; }

.toolbar-actions { display: flex; align-items: center; gap: 10px; margin-left: auto; flex-wrap: wrap; }
.toolbar-search { width: 220px; }

/* ===== 表格样式 ===== */
.account-table { width: 100%; }
.account-table :deep(.el-table__row:hover > td) {
  background: #f8fafc !important;
}

/* 客户单元格 */
.customer-cell { cursor: pointer; display: flex; align-items: center; gap: 12px; }
.cust-avatar {
  width: 38px; height: 38px; border-radius: 10px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 15px; font-weight: 600;
}
.cust-info { display: flex; flex-direction: column; min-width: 0; }
.ca-name-row { display: flex; align-items: center; gap: 6px; }
.ca-name { font-size: 13.5px; font-weight: 600; color: #1e293b; }
.ca-type-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.ca-dot-paid { background: #22c55e; box-shadow: 0 0 6px rgba(34,197,94,.35); }
.ca-meta { display: flex; align-items: center; gap: 4px; margin-top: 3px; font-size: 12px; color: #94a3b8; }
.ca-meta-sep { color: #cbd5e1; }

/* 品牌标签 */
.brand-tag { margin-right: 4px; border-radius: 5px; font-size: 11.5px; }
.brand-more { font-size: 12px; color: #94a3b8; margin-left: 4px; }

/* 平台图标 */
.platforms-cell { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }

/* 时间 */
.ymd-cell { font-size: 13px; color: #475569; }
.muted { color: #94a3b8; font-size: 13px; }

/* 操作按钮 - 单行显示 */
.act-btn-group { display: flex; align-items: center; justify-content: center; gap: 6px; flex-wrap: nowrap; }
.act-btn {
  padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 500;
  border: 1px solid #e2e8f0; background: #fff; color: #475569; cursor: pointer;
  transition: all .15s ease; white-space: nowrap;
}

/* 解决操作列左右被裁切的问题：允许单元格溢出可见 */
.account-table :deep(.el-table__body td),
.account-table :deep(.el-table__fixed-right) {
  overflow: visible !important;
}

/* 提高固定列层级，避免被其他元素遮挡 */
.account-table :deep(.el-table__fixed-right) { z-index: 3; }
.act-btn:hover { border-color: #cbd5e1; background: #f8fafc; }
.act-btn-primary { color: #3b82f6; border-color: #bfdbfe; background: #eff6ff; }
.act-btn-primary:hover { background: #dbeafe; border-color: #93c5fd; }
.act-btn-lib { color: #7c5cf6; border-color: #ddd6fe; background: #f5f3ff; }
.act-btn-lib:hover { background: #ede9fe; border-color: #c4b5fd; }
.act-btn-default { color: #64748b; }
.act-btn-default:hover { color: #1e293b; }
.act-btn-danger { color: #dc2626; border-color: #fecaca; background: #fef2f2; }
.act-btn-danger:hover { background: #fee2e2; border-color: #fca5a5; }

/* 空状态 */
.table-empty {
  text-align: center; padding: 36px 0; color: #94a3b8;
}
.table-empty p { margin: 10px 0 16px; font-size: 14px; }

/* ===== 弹窗样式（两步表单 - 精致版） ===== */

/* Dialog 容器 */
.customer-dialog :deep(.el-dialog) {
  border-radius: 16px;
  overflow: hidden;
}
.customer-dialog :deep(.el-dialog__header) {
  padding: 0;
  margin: 0;
}
.customer-dialog :deep(.el-dialog__body) {
  padding: 0;
}
.customer-dialog :deep(.el-dialog__footer) {
  padding: 16px 24px 20px;
  border-top: 1px solid #f1f5f9;
}

/* ===== Header 区域 ===== */
.cd-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.cd-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.cd-header-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}
.cd-header-title {
  font-size: 17px;
  font-weight: 700;
  color: #fff;
  line-height: 1.3;
  letter-spacing: -0.01em;
}
.cd-header-desc {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.75);
  margin-top: 2px;
}
/* 关闭按钮变白 */
.customer-dialog :deep(.el-dialog__headerbtn .el-dialog__close) {
  color: rgba(255, 255, 255, 0.85);
  font-size: 18px;
}
.customer-dialog :deep(.el-dialog__headerbtn .el-dialog__close:hover) {
  color: #fff;
}

/* ===== 步骤指示器 ===== */
.cd-steps {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  padding: 20px 24px 0;
  background: #fff;
}
.cd-step-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.cd-step-num {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  border: 2px solid #e2e8f0;
  color: #94a3b8;
  background: #f8fafc;
  transition: all 0.3s ease;
  flex-shrink: 0;
}
.cd-step-label {
  font-size: 13.5px;
  font-weight: 500;
  color: #94a3b8;
  transition: color 0.3s ease;
}
/* 当前步骤 */
.cd-step-item.active .cd-step-num {
  background: linear-gradient(135deg, #667eea, #764ba2);
  border-color: transparent;
  color: #fff;
  box-shadow: 0 3px 10px rgba(102, 126, 234, 0.35);
}
.cd-step-item.active .cd-step-label {
  color: #334155;
  font-weight: 600;
}
/* 已完成步骤 */
.cd-step-item.done .cd-step-num {
  background: #22c55e;
  border-color: #22c55e;
  color: #fff;
}
.cd-step-item.done .cd-step-label {
  color: #22c55e;
}
/* 连接线 */
.cd-step-connector {
  width: 80px;
  height: 2px;
  background: #e2e8f0;
  margin: 0 12px;
  border-radius: 1px;
  position: relative;
  overflow: hidden;
}
.cd-step-line {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  width: 0%;
  background: linear-gradient(90deg, #22c55e, #667eea);
  border-radius: 1px;
  transition: width 0.4s ease;
}
.cd-step-line.filled {
  width: 100%;
}

/* ===== 内容区域 ===== */
.cd-body {
  padding: 20px 24px 24px;
}
.cd-form {
  /* Element Plus form 样式微调 */
}
.cd-form :deep(.el-form-item__label) {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  padding-bottom: 6px;
}
.cd-form :deep(.el-input__wrapper),
.cd-form :deep(.el-select .el-input__wrapper) {
  border-radius: 8px;
  box-shadow: 0 0 0 1px #e2e8f0 inset;
  transition: all 0.2s;
}
.cd-form :deep(.el-input__wrapper:hover),
.cd-form :deep(.el-select .el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #cbd5e1 inset;
}
.cd-form :deep(.el-input__wrapper.is-focus),
.cd-form :deep(.el-select .el-input.is-focus .el-input__wrapper) {
  box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2), 0 0 0 1px #667eea inset !important;
}

/* ===== 关键词区域 ===== */
.cd-body-kw {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.kw-hint-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  background: #f8fafc;
  border: 1px solid #f1f5f9;
  border-radius: 8px;
}
.kw-hint-text {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
  flex: 1;
}
.kw-hint-text code {
  background: #e2e8f0;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 11.5px;
  color: #475569;
  font-family: 'SF Mono', Consolas, monospace;
}
.kw-textarea :deep(.el-textarea__inner) {
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.6;
}
.kw-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.kw-paste-count {
  font-size: 12px;
  color: #94a3b8;
}
.kw-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  padding-bottom: 10px;
  border-bottom: 1px solid #f1f5f9;
  margin-top: 4px;
}
.kw-section-icon {
  display: flex;
  color: #667eea;
}
.kw-section-title .el-tag {
  font-size: 11px;
  margin-left: 4px;
}
.kw-table {
  border-radius: 8px;
  overflow: hidden;
}
.kw-table :deep(.el-table__row:hover > td) {
  background: #f8fafc !important;
}
.kw-warning-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: linear-gradient(90deg, #fefce8, #fff);
  border: 1px solid #fde68a;
  border-radius: 8px;
  font-size: 12.5px;
  color: #854d0e;
  line-height: 1.5;
}
.kw-warning-box b {
  color: #a16207;
}

/* ===== 响应式 ===== */
@media (max-width: 900px) {
  .panel { padding: 14px 16px; }
  .toolbar-search { width: 180px; }
}

@media (max-width: 700px) {
  .toolbar { flex-direction: column; align-items: stretch; }
  .toolbar-actions { margin-left: 0; justify-content: stretch; }
  .toolbar-search { width: 100%; }
  .panel { padding: 12px; }
}

@media (max-width: 480px) {
  .panel { padding: 10px 12px; }
  .seg { font-size: 12px; padding: 6px 12px; }
  .act-btn { padding: 4px 8px; font-size: 11.5px; margin-left: 4px; }
}
</style>