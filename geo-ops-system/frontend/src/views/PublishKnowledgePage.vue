<template>
  <div class="publish-knowledge-page">
    <!-- KPI 统计卡片 -->
    <section class="kpi-strip">
      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-blue"><el-icon><User /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-val">{{ stats.customers }}</div>
          <div class="kpi-label">客户总数</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-green"><el-icon><Notebook /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-val">{{ stats.built }}</div>
          <div class="kpi-label">已建知识库</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-orange"><el-icon><Plus /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-val">{{ stats.pending }}</div>
          <div class="kpi-label">待建知识库</div>
        </div>
      </div>
    </section>

      <!-- 主面板 -->
      <section class="panel">
        <!-- 工具栏 -->
        <div class="toolbar">
          <div class="toolbar-left">
            <el-input
              v-model="searchText"
              placeholder="搜索品牌名 / 公司名称"
              clearable
              :prefix-icon="Search"
              class="kb-search"
            />
            <span class="kb-count">{{ filteredItems.length }} 个客户</span>
          </div>
          <div class="toolbar-right">
            <button class="tb-btn" @click="loadData">
              <el-icon><Refresh /></el-icon> 刷新
            </button>
            <button class="tb-btn" @click="handleExcelImport">
              <el-icon><Upload /></el-icon> Excel 导入
            </button>
            <button class="tb-btn tb-primary" @click="openCreateDialog">
              <el-icon><Plus /></el-icon> 创建知识库
            </button>
          </div>
        </div>

        <!-- 表格 -->
      <el-table
        :data="filteredItems"
        v-loading="loading"
        row-key="id"
        class="kb-table"
        :header-cell-style="{ background: '#fafbfc', color: '#64748b', fontWeight: 600, fontSize: '13px' }"
      >
        <el-table-column label="客户" min-width="240">
          <template #default="{ row }">
            <div class="cust-cell">
              <div class="cust-avatar" :style="{ background: avatarColor(row) }">{{ avatarLetter(row) }}</div>
              <div class="cust-info">
                <div class="cust-name">{{ row.companyName || row.name || '—' }}</div>
                <div class="cust-company">{{ row.companyBrand || row.brand || '' }}</div>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="知识库" width="120" align="center">
          <template #default="{ row }">
            <span class="kb-count-cell">{{ Number(row.kb_count || 0) }}个版本</span>
          </template>
        </el-table-column>

        <el-table-column label="当前版本" width="170" align="center">
          <template #default="{ row }">
            <span class="version-cell">{{ currentVersionText(row) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="updatedAt" label="更新时间" width="180" sortable>
          <template #default="{ row }">
            <span class="time-cell">{{ formatTime(row.updatedAt || row.latest_kb_at || row.current_created_at || row.createdAt) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <a class="view-link" @click="viewDetail(row)">查看</a>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <KbCreateKnowledgeDialog ref="createDialogRef" v-model="createVisible" @created="onKnowledgeCreated" />

    <!-- Excel 导入知识库弹窗 -->
    <KbExcelImportDialog v-model="excelImportOpen" @done="onExcelImportDone" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import {
  Search, Refresh, Plus, Upload, User, Notebook,
  FolderOpened, Close, InfoFilled, UploadFilled, Document, MagicStick
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import api from '../api'
import publishApi from '../api/publish'
import KbExcelImportDialog from '@/components/KbExcelImportDialog.vue'
import KbCreateKnowledgeDialog from '@/components/KbCreateKnowledgeDialog.vue'

const loading = ref(false)
const creating = ref(false)
const searchText = ref('')
const items = ref([])
const allAccounts = ref([])
const createVisible = ref(false)
const createDialogRef = ref(null)
const showNewCustomer = ref(false)
const excelImportOpen = ref(false)
const router = useRouter()

const stats = ref({ customers: 0, built: 0, pending: 0 })

// 创建表单
const createForm = reactive({
  accountId: null,
  name: '',
  remark: '',
  files: [],           // 基础资料文件列表
})

// 新建客户表单
const newCustomerForm = reactive({
  companyName: '',
  brand: '',
})

// 计算属性：是否可以保存资料（至少有客户）
const canSaveMaterial = computed(() => !!createForm.accountId)
// 计算属性：是否可以生成知识库（至少有客户 + 有资料）
const canGenerate = computed(() =>
  !!createForm.accountId && createForm.files.length > 0
)

// 筛选后的数据
const filteredItems = computed(() => {
  const q = searchText.value.trim().toLowerCase()
  const filtered = q
    ? items.value.filter(item =>
        (item.companyName || item.name || '').toLowerCase().includes(q) ||
        (item.companyBrand || item.brand || '').toLowerCase().includes(q)
      )
    : items.value
  return [...filtered].sort((a, b) => {
    const ta = a.updatedAt || a.latest_kb_at || a.createdAt || ''
    const tb = b.updatedAt || b.latest_kb_at || b.createdAt || ''
    return tb.localeCompare(ta)
  })
})

// 头像颜色（根据名称生成稳定颜色）
function avatarColor(row) {
  const colors = ['#6366f1', '#10b981', '#ec4899', '#f59e0b', '#14b8a6', '#8b5cf6']
  const name = (row.companyName || row.name || '')
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return colors[Math.abs(hash) % colors.length]
}

function avatarLetter(row) {
  return (row.companyName || row.name || '?')[0] || '?'
}

function formatTime(val) {
  if (!val) return '—'
  return String(val).slice(0, 16).replace('T', ' ')
}

function currentVersionText(row) {
  const ver = Number(row.current_version || 0)
  if (!ver) return '—'
  const createdBy = String(row.current_created_by || '').toLowerCase()
  const typeLabel = createdBy === 'human' ? '人工' : 'AI'
  return `V${ver}-${typeLabel}`
}

function normalizeId(v) {
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function pickAccountId(row) {
  return normalizeId(row?.id ?? row?.account_id ?? row?.accountId)
}

async function loadData() {
  loading.value = true
    try {
    // 加载客户列表作为知识库条目，并合并 KB 概览（含文章数 / 最新时间）
    const data = await api.listAccounts()
    const list = Array.isArray(data) ? data : []
    let overview = { items: [] }
    try {
      overview = await publishApi.kbCustomerOverview()
    } catch (e) {
      // 如果概览接口失败，继续显示基本客户信息
      overview = { items: [] }
    }
    const overviewMap = new Map(
      (overview.items || [])
        .map((o) => [pickAccountId(o), o])
        .filter(([id]) => id != null)
    )
    const rows = list.map(a => {
      const accId = pickAccountId(a)
      const ov = (accId != null ? overviewMap.get(accId) : null) || {}
      return {
        ...a,
        id: a.id ?? a.account_id ?? a.accountId,
        companyName: a.companyName || a.company_name || a.name || '',
        companyBrand: a.companyBrand || a.company_brand || a.brand || '',
        kb_count: Number(ov.kb_count ?? 0),
        current_version: Number(ov.current_version ?? ov.latest_version ?? 0),
        current_created_by: ov.current_created_by || ov.latest_created_by || '',
        current_created_at: ov.current_created_at || ov.current_at || null,
        latest_kb_at: ov.latest_kb_at || null,
        updatedAt: ov.latest_kb_at || ov.current_created_at || a.updatedAt || a.createdAt,
      }
    })
    items.value = rows
    allAccounts.value = list

    // 统计数据：客户总数 / 已建知识库 / 待建知识库
    try {
      const built = rows.filter(x => Number(x.kb_count || 0) > 0).length
      stats.value = {
        customers: rows.length,
        built,
        pending: rows.length - built,
      }
    } catch (e) {
      stats.value = { customers: rows.length, built: 0, pending: rows.length }
    }
  } catch (e) {
    console.error('加载失败', e)
  } finally {
    loading.value = false
  }
}

function openCreateDialog() {
  createDialogRef.value?.open?.()
}

// ===== 文件处理 =====
function onKnowledgeCreated(payload) {
  loadData()
  if (payload?.accountId) {
    router.push(`/publish/customer-kb/${payload.accountId}`)
  }
}

// ===== Excel 导入 =====
function handleExcelImport() {
  excelImportOpen.value = true
}

function onExcelImportDone(payload) {
  loadData()
}

// ===== 进入详情页 =====
function viewDetail(row) {
  router.push(`/publish/customer-kb/${row.id}`)
}

onMounted(() => loadData())
</script>

<style scoped>
.publish-knowledge-page { display: flex; flex-direction: column; gap: 18px; }

/* ===== KPI 卡片 ===== */
.kpi-strip { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.kpi-card {
  display: flex; align-items: center; gap: 14px;
  background: #fff; border: 1px solid #eef1f6; border-radius: 12px; padding: 18px 24px;
}
.kpi-icon {
  width: 44px; height: 44px; border-radius: 11px; flex: none;
  display: flex; align-items: center; justify-content: center; font-size: 20px;
}
.kpi-icon-blue { background: #eef4ff; color: #3b82f6; }
.kpi-icon-green { background: #ecfdf5; color: #10b981; }
.kpi-icon-orange { background: #fff7ed; color: #f59e0b; }
.kpi-val { font-size: 28px; font-weight: 700; line-height: 1.2; color: #0f172a; }
.kpi-label { font-size: 13px; color: #94a3b8; margin-top: 2px; }

/* ===== 面板 ===== */
.panel {
  background: #fff; border: 1px solid #eef1f6; border-radius: 12px;
  padding: 20px 24px;
  overflow-x: hidden; /* 防止内容溢出 */
}

/* ===== 工具栏 ===== */
.toolbar {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 4px; flex-wrap: wrap; gap: 12px;
}
.toolbar-left { display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0; }
.kb-search { width: 240px; max-width: 100%; flex-shrink: 1; }
.kb-count { font-size: 13px; color: #94a3b8; white-space: nowrap; flex-shrink: 0; }
.toolbar-right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }

.tb-btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 8px 16px; border-radius: 8px; font-size: 13.5px; font-weight: 500;
  border: 1px solid #e2e8f0; background: #fff; color: #475569; cursor: pointer;
  transition: all .15s ease;
}
.tb-btn:hover { border-color: #cbd5e1; background: #f8fafc; }
.tb-btn .el-icon { font-size: 15px; }
.tb-primary {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #fff; border-color: transparent;
  box-shadow: 0 2px 8px rgba(59,130,246,.3);
}
.tb-primary:hover {
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  box-shadow: 0 4px 14px rgba(59,130,246,.45);
  transform: translateY(-1px);
  color: #fff !important;
}

/* ===== 表格 ===== */
.kb-table { width: 100%; overflow-x: auto; }
.kb-table :deep(.el-table__row:hover > td) { background: #f8fafc !important; }

/* 客户单元格 */
.cust-cell { display: flex; align-items: center; gap: 12px; }
.cust-avatar {
  width: 36px; height: 36px; border-radius: 10px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 15px; font-weight: 600;
}
.cust-info { min-width: 0; }
.cust-name { font-size: 14px; font-weight: 600; color: #1e293b; }
.cust-company { font-size: 12.5px; color: #94a3b8; margin-top: 2px; }

/* 类型标签 */
.type-tag {
  display: inline-block; padding: 3px 10px; border-radius: 5px;
  font-size: 12px; font-weight: 500;
}
.type-paid { background: #ecfdf5; color: #059669; }

/* 知识库数量 */
.kb-count-cell { font-size: 13.5px; font-weight: 600; color: #334155; }

/* 版本标签 */
.ver-tag {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 10px; border-radius: 5px;
  font-size: 12.5px; font-weight: 500;
  background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0;
}
.ver-tag-sub {
  font-size: 11px; color: #15803d;
  padding-left: 6px; border-left: 1px solid #86efac;
}

/* 时间 */
.time-cell { font-size: 13px; color: #475569; }
.muted { color: #94a3b8; font-size: 13px; }

/* 查看链接 */
.view-link {
  font-size: 13.5px; color: #64748b; cursor: pointer; text-decoration: none;
  transition: color .15s ease;
}
.view-link:hover { color: #3b82f6; }

@media (max-width: 768px) {
  .kpi-strip { grid-template-columns: 1fr; gap: 12px; }
  .kpi-card { padding: 14px 18px; }
  .kpi-val { font-size: 24px; }
  .panel { padding: 14px 16px; border-radius: 10px; }
  .toolbar { flex-direction: column; align-items: stretch; }
  .toolbar-left, .toolbar-right {
    justify-content: stretch;
    width: 100%;
  }
  .kb-search { width: 100%; max-width: none; }
  .tb-btn { padding: 8px 12px; font-size: 13px; }
  /* 表格列隐藏 */
  .kb-table :deep(.el-table__body-wrapper) { overflow-x: auto; -webkit-overflow-scrolling: touch; }
}

/* 超小屏幕 */
@media (max-width: 480px) {
  .kpi-strip { grid-template-columns: repeat(2, 1fr); }
  .kpi-card { padding: 12px 14px; gap: 10px; }
  .kpi-icon { width: 36px; height: 36px; font-size: 17px; border-radius: 9px; }
  .kpi-val { font-size: 20px; }
  .kpi-label { font-size: 11.5px; }
  .cust-avatar { width: 30px; height: 30px; font-size: 13px; border-radius: 8px; }
  .cust-name { font-size: 13px; }
  .cust-company { font-size: 11.5px; }
}

/* ===== 创建知识库弹窗 ===== */
.create-kb-dialog :deep(.el-dialog) { border-radius: 16px; overflow: hidden; max-width: 96vw; }
.create-kb-dialog :deep(.el-dialog__header) { padding: 0; margin: 0; }
.create-kb-dialog :deep(.el-dialog__body) { padding: 24px 28px 12px; max-height: calc(80vh - 120px); overflow-y: auto; }

/* 弹窗头部 */
.ckb-header {
  display: flex; align-items: center; gap: 14px;
  background: linear-gradient(135deg, #eef2ff, #ede9fe);
  padding: 20px 24px; position: relative;
}
.ckb-header-icon {
  width: 44px; height: 44px; border-radius: 11px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 20px; flex-shrink: 0;
}
.ckb-title { font-size: 17px; font-weight: 700; color: #1e293b; line-height: 1.3; }
.ckb-subtitle { font-size: 12.5px; color: #6366f1; margin-top: 3px; }
.ckb-close {
  position: absolute; top: 14px; right: 14px;
  width: 30px; height: 30px; border-radius: 8px;
  border: none; background: rgba(255,255,255,.7); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  color: #64748b; transition: all .15s ease;
}
.ckb-close:hover { background: #fff; color: #334155; }

/* 弹窗内容区 */
.ckb-body { display: flex; flex-direction: column; gap: 18px; }

/* 分区 */
.ckb-section { display: flex; flex-direction: column; gap: 8px; }
.ckb-section-label {
  font-size: 14px; font-weight: 600; color: #1e293b;
  display: flex; align-items: center; gap: 4px;
}
.ckb-required { color: #ef4444; font-size: 14px; }

/* 目标客户行 */
.ckb-customer-row { display: flex; align-items: center; gap: 10px; }
.ckb-customer-select { flex: 1; }
.ckb-new-btn {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 9px 16px; border-radius: 8px; font-size: 13.5px; font-weight: 500;
  border: 1px dashed #c7d2fe; background: #f5f3ff; color: #6366f1; cursor: pointer;
  white-space: nowrap; transition: all .15s ease; flex-shrink: 0;
}
.ckb-new-btn:hover { border-color: #818cf8; background: #ede9fe; }

/* 提示文字 */
.ckb-hint-row {
  display: flex; align-items: flex-start; gap: 5px;
  font-size: 12px; color: #94a3b8; line-height: 1.55;
}
.ckb-hint-row .el-icon { margin-top: 2px; color: #94a3b8; flex-shrink: 0; font-size: 14px; }
.ckb-hint-sm { margin-top: 2px; }

/* 上传区域 */
.ckb-upload-zone {
  border: 2px dashed #d1d5db; border-radius: 12px;
  padding: 32px 20px; text-align: center;
  cursor: pointer; transition: all .2s ease;
  background: #fafbfc;
}
.ckb-upload-zone:hover { border-color: #93c5fd; background: #eff6ff; }
.ckb-upload-icon { font-size: 40px; color: #6366f1; margin-bottom: 10px; }
.ckb-upload-text { font-size: 14px; color: #475569; }
.ckb-upload-link { color: #3b82f6; font-weight: 600; cursor: pointer; }
.ckb-upload-tags { display: flex; justify-content: center; gap: 8px; margin-top: 12px; }
.ckb-upload-tip { font-size: 11.5px; color: #94a3b8; margin-top: 8px; }

/* 文件类型标签 */
.ut {
  display: inline-block; padding: 2px 10px; border-radius: 4px;
  font-size: 11.5px; font-weight: 600;
}
.ut-pdf { background: #fee2e2; color: #dc2626; }
.ut-word { background: #dbeafe; color: #2563eb; }
.ut-excel { background: #dcfce7; color: #16a34a; }
.ut-img { background: #fef3c7; color: #d97706; }
.ut-txt { background: #f3e8ff; color: #7c3aed; }
.ut-html { background: #ecfdf5; color: #059669; }

/* 文件列表 */
.ckb-file-list { margin-top: 12px; display: flex; flex-direction: column; gap: 6px; }
.ckb-file-item {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 12px; border-radius: 8px; background: #f8fafc;
  border: 1px solid #eef1f6; font-size: 13px;
}
.ckb-file-item .el-icon { color: #64748b; font-size: 15px; }
.ckb-fn { flex: 1; color: #334155; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ckb-fs { color: #94a3b8; font-size: 12px; white-space: nowrap; }
.ckb-frm {
  width: 22px; height: 22px; border-radius: 50%; border: none;
  background: transparent; color: #94a3b8; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all .15s ease; flex-shrink: 0;
}
.ckb-frm:hover { background: #fef2f2; color: #ef4444; }

/* 参考报告信息 */
.ckb-report-info {
  display: flex; align-items: flex-start; gap: 6px;
  padding: 10px 14px; border-radius: 8px;
  background: #f0fdf4; border: 1px solid #bbf7d0;
  font-size: 12.5px; color: #166534; line-height: 1.55;
}
.ckb-report-info .el-icon { margin-top: 1px; flex-shrink: 0; font-size: 15px; }

/* 报告选择/上传行 */
.ckb-report-select-row, .ckb-report-upload-row {
  display: flex; align-items: center; gap: 10px;
}
.ckb-rs-label { font-size: 13px; color: #475569; font-weight: 500; white-space: nowrap; min-width: 72px; }
.ckb-rs-select { flex: 1; }
.ckb-rup-zone {
  flex: 1; display: flex; align-items: center; justify-content: center; gap: 6px;
  padding: 10px 16px; border: 1.5px dashed #d1d5db; border-radius: 8px;
  cursor: pointer; font-size: 13px; color: #64748b; transition: all .15s ease;
  background: #fafbfc;
}
.ckb-rup-zone:hover { border-color: #93c5fd; color: #3b82f6; background: #eff6ff; }
.ckb-rup-zone .rup-tags { display: inline-flex; gap: 4px; margin-left: 4px; }

/* 补充说明 */
.ckb-remark :deep(textarea) { font-size: 13.5px; }
.ckb-module-confirm {
  margin-top: 8px; padding: 10px 14px; border-radius: 8px;
  background: #f0fdf4; border: 1px solid #bbf7d0;
}
.ckb-module-confirm :deep(.el-checkbox__label) { font-size: 12.5px; color: #166534; line-height: 1.5; }
.ckb-module-confirm strong { color: #15803d; }

/* 底部按钮区 */
.create-kb-dialog :deep(.el-dialog__footer) { padding: 16px 28px 24px; border-top: none; }
.ckb-footer { display: flex; justify-content: flex-end; gap: 10px; }
.ckb-btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 9px 20px; border-radius: 8px; font-size: 13.5px; font-weight: 500;
  cursor: pointer; transition: all .15s ease; border: 1px solid transparent;
}
.ckb-btn-cancel {
  background: #fff; color: #64748b; border-color: #e2e8f0;
}
.ckb-btn-cancel:hover { background: #f8fafc; border-color: #cbd5e1; }
.ckb-btn-material {
  background: #f0fdf4; color: #166534; border-color: #bbf7d0;
}
.ckb-btn-material:hover:not(:disabled) { background: #dcfce7; border-color: #86efac; }
.ckb-btn-material:disabled { opacity: .5; cursor: not-allowed; }
.ckb-btn-generate {
  background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff;
  box-shadow: 0 2px 8px rgba(99,102,241,.35);
}
.ckb-btn-generate:hover:not(:disabled) { box-shadow: 0 4px 14px rgba(99,102,241,.45); transform: translateY(-1px); }
.ckb-btn-generate:disabled { opacity: .5; cursor: not-allowed; box-shadow: none; transform: none; }

/* ===== 弹窗移动端适配 ===== */
@media (max-width: 600px) {
  .create-kb-dialog :deep(.el-dialog) { width: 98vw !important; margin: 2vh auto !important; }
  .create-kb-dialog :deep(.el-dialog__body) { padding: 16px 18px 10px; max-height: calc(75vh - 80px); }
  .ckb-header { padding: 16px 18px; flex-wrap: wrap; }
  .ckb-header-icon { width: 36px; height: 36px; font-size: 17px; border-radius: 9px; }
  .ckb-title { font-size: 15px; }
  .ckb-subtitle { font-size: 11.5px; }
  .ckb-body { gap: 14px; }
  .ckb-customer-row { flex-direction: column; align-items: stretch; }
  .ckb-new-btn { justify-content: center; width: 100%; }
  .ckb-upload-zone { padding: 24px 14px; }
  .ckb-upload-icon { font-size: 32px; }
  .ckb-upload-tags { gap: 6px; flex-wrap: wrap; }
  .ckb-report-select-row, .ckb-report-upload-row { flex-direction: column; align-items: stretch; gap: 8px; }
  .ckb-rs-label { min-width: unset; }
  .ckb-rup-zone { padding: 12px; font-size: 12.5px; }
  .create-kb-dialog :deep(.el-dialog__footer) { padding: 12px 16px 20px; }
  .ckb-footer { flex-direction: column-reverse; gap: 8px; }
  .ckb-btn { justify-content: center; width: 100%; padding: 10px 16px; }
}
</style>
