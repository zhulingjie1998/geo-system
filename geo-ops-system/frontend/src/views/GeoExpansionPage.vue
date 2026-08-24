<template>
  <div class="geo-expansion-page">
    <!-- ============ KPI 栏 ============ -->
    <section class="kpi-strip">
      <div class="kpi-card" role="button" tabindex="0"
           @click="filterStatus=''">
        <div class="kpi-icon kpi-icon-blue"><el-icon :size="18"><List /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-label">任务总数</div>
          <div class="kpi-val">{{ overview.totalTasks }}</div>
          <div class="kpi-sub">全部拓词任务</div>
        </div>
      </div>
      <div class="kpi-card" role="button" tabindex="0"
           :class="{ active: filterStatus==='completed' }"
           @click="filterStatus = filterStatus==='completed' ? '' : 'completed'"
           @keydown.enter="filterStatus = filterStatus==='completed' ? '' : 'completed'">
        <div class="kpi-icon kpi-icon-green"><el-icon :size="18"><CircleCheck /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-label">已完成</div>
          <div class="kpi-val">{{ overview.completed }}</div>
          <div class="kpi-sub kpi-sub-good">可下载 / 导入</div>
        </div>
      </div>
      <div class="kpi-card" role="button" tabindex="0"
           :class="{ active: filterStatus==='running' }"
           @click="filterStatus = filterStatus==='running' ? '' : 'running'"
           @keydown.enter="filterStatus = filterStatus==='running' ? '' : 'running'">
        <div class="kpi-icon kpi-icon-orange"><el-icon :size="18"><Loading /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-label">进行中</div>
          <div class="kpi-val">{{ overview.running }}</div>
          <div class="kpi-sub" :class="{ 'kpi-sub-live': overview.running > 0 }">
            <span v-if="overview.running > 0">当前拓词中</span>
            <span v-else>当前空闲</span>
          </div>
        </div>
      </div>
      <div class="kpi-card" role="button" tabindex="0"
           :class="{ active: filterStatus==='failed' }"
           @click="overview.failed && (filterStatus = filterStatus==='failed' ? '' : 'failed')"
           @keydown.enter="overview.failed && (filterStatus = filterStatus==='failed' ? '' : 'failed')">
        <div class="kpi-icon kpi-icon-purple"><el-icon :size="18"><MagicStick /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-label">累计提示词</div>
          <div class="kpi-val">{{ formatNumber(overview.totalPrompts) }}</div>
          <div class="kpi-sub">已生成提示词总量</div>
        </div>
      </div>
    </section>

    <!-- ============ 主面板 ============ -->
    <section class="panel">
      <!-- 工具栏 -->
      <div class="toolbar">
        <div class="toolbar-tabs">
          <button class="seg" :class="{ active: !filterStatus }" @click="filterStatus=''">
            全部 <span class="seg-count">{{ overview.totalTasks }}</span>
          </button>
          <button class="seg" :class="{ active: filterStatus==='running' }" @click="filterStatus='running'">
            进行中 <span class="seg-count">{{ overview.running }}</span>
          </button>
          <button class="seg" :class="{ active: filterStatus==='completed' }" @click="filterStatus='completed'">
            已完成 <span class="seg-count">{{ overview.completed }}</span>
          </button>
          <button class="seg" :class="{ active: filterStatus==='failed' }" @click="filterStatus='failed'">
            异常 <span class="seg-count">{{ overview.failed || 0 }}</span>
          </button>
        </div>
        <div class="toolbar-actions">
          <el-button :icon="Refresh" @click="refreshAll" :loading="loading">刷新</el-button>
          <el-button type="primary" :icon="Plus" @click="showCreateDialog = true">创建任务</el-button>
        </div>
      </div>

      <!-- 表格 -->
      <el-table
        ref="tableRef"
        :data="filteredTasks"
        v-loading="loading"
        row-key="id"
        class="geo-table"
        :header-cell-style="{ background: 'transparent', color: '#64748b', fontWeight: 600, fontSize: '12px', letterSpacing: '0.3px' }"
        empty-text="暂无拓词任务，点击「创建任务」开始"
      >
        <el-table-column width="44">
          <template #default><span class="row-dot"></span></template>
        </el-table-column>

        <el-table-column prop="createdAt" label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.createdAt) }}
          </template>
        </el-table-column>



        <el-table-column prop="brandName" label="品牌" width="120">
          <template #default="{ row }">
            <span class="brand-name">{{ row.brandName }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small" effect="light">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="promptCount" label="提示词数" width="100" align="center">
          <template #default="{ row }">
            <span class="prompt-count">{{ row.promptCount }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="extraRequirements" label="补充要求" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.extraRequirements" class="extra-req">{{ row.extraRequirements }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="220" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-btns">
              <el-button size="small" link type="primary" @click.stop="handleExport(row)">
                <el-icon><Download /></el-icon> Excel
              </el-button>
              <el-button size="small" link type="primary" @click.stop="handleView(row)">
                <el-icon><View /></el-icon> 查看
              </el-button>
              <el-popconfirm title="确定删除此任务？" @confirm="handleDelete(row.id)">
                <template #reference>
                  <el-button size="small" link type="danger" @click.stop>
                    <el-icon><Delete /></el-icon> 删除
                  </el-button>
                </template>
              </el-popconfirm>
              <el-button
                v-if="row.status === 'pending' || row.status === 'failed'"
                size="small"
                link type="success"
                @click.stop="handleRun(row)"
              >
                执行
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- 创建任务弹窗 -->
    <CreateTaskDialog
      v-model:visible="showCreateDialog"
      @created="onTaskCreated"
    />

    <!-- 任务详情弹窗（查看提示词） -->
    <TaskDetailDialog
      v-model:visible="showDetailDialog"
      :taskId="currentTaskId"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Refresh, List, CircleCheck, Loading, MagicStick, Download, View, Delete } from '@element-plus/icons-vue'
import geoExpansionApi from '../api/geoExpansion'
import CreateTaskDialog from './geo/CreateTaskDialog.vue'
import TaskDetailDialog from './geo/TaskDetailDialog.vue'

// 状态
const loading = ref(false)
const filterStatus = ref('')
const showCreateDialog = ref(false)
const showDetailDialog = ref(false)
const currentTaskId = ref(null)

// 轮询：用于检测任务完成状态变化
let pollTimer = null
const prevRunningCount = ref(0)

// 数据概览
const overview = reactive({
  totalTasks: 0,
  completed: 0,
  running: 0,
  failed: 0,
  totalPrompts: 0,
})

// 任务列表
const tasks = ref([])

// 过滤后的任务列表
const filteredTasks = computed(() => {
  const filtered = filterStatus.value
    ? tasks.value.filter(t => t.status === filterStatus.value)
    : tasks.value
  return [...filtered].sort((a, b) => {
    const ta = a.createdAt || a.updatedAt || ''
    const tb = b.createdAt || b.updatedAt || ''
    return tb.localeCompare(ta)
  })
})

// 加载概览数据
async function loadOverview() {
  try {
    const data = await geoExpansionApi.getOverview()
    // 检测任务完成：进行中数量减少，说明有任务完成了（仅页面可见时提示）
    if (document.visibilityState === 'visible' && prevRunningCount.value > 0 && data.running < prevRunningCount.value) {
      ElMessage.success('任务已完成')
    }
    prevRunningCount.value = data.running
    Object.assign(overview, data)
  } catch (e) {
    console.error('Failed to load overview:', e)
  }
}

// 加载任务列表
async function loadTasks() {
  loading.value = true
  try {
    const data = await geoExpansionApi.listTasks()
    tasks.value = data || []
  } catch (e) {
    console.error('Failed to load tasks:', e)
  } finally {
    loading.value = false
  }
}

// 刷新全部数据
function refreshAll() {
  loadOverview()
  loadTasks()
}

// 任务创建成功回调
function onTaskCreated(taskId) {
  refreshAll()
  // 自动执行任务
  if (taskId) {
    handleRun({ id: taskId })
  }
}

// 执行任务
async function handleRun(row) {
  try {
    await geoExpansionApi.runTask(row.id)
    ElMessage.success('任务已启动')
    refreshAll()
  } catch (e) {
    ElMessage.error(e.message || '启动失败')
  }
}

// 导出
async function handleExport(row) {
  try {
    const res = await geoExpansionApi.exportTask(row.id)
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = `拓词任务_${row.id}_${row.brandName}.csv`
    link.click()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error('导出失败')
  }
}

// 查看
function handleView(row) {
  currentTaskId.value = row.id
  showDetailDialog.value = true
}

// 删除
async function handleDelete(id) {
  try {
    await geoExpansionApi.deleteTask(id)
    ElMessage.success('删除成功')
    refreshAll()
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  }
}

// 辅助函数
function statusTagType(status) {
  const map = { pending: 'info', running: 'warning', completed: 'success', failed: 'danger' }
  return map[status] || 'info'
}

function statusLabel(status) {
  const map = { pending: '待执行', running: '进行中', completed: '已完成', failed: '异常' }
  return map[status] || status
}

function formatTime(timeStr) {
  if (!timeStr) return '-'
  return timeStr.replace('T', ' ').substring(0, 16)
}

function formatNumber(num) {
  if (!num && num !== 0) return '0'
  return Number(num).toLocaleString()
}

onMounted(() => {
  refreshAll()
  // 启动轮询：每 5 秒刷新，检测任务完成状态
  pollTimer = setInterval(() => {
    loadOverview()
    loadTasks()
  }, 5000)
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<style scoped>
.geo-expansion-page {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* ===== KPI ===== */
.kpi-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.kpi-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 14px 16px;
  cursor: pointer;
  transition: transform .15s, box-shadow .15s, border-color .15s;
  outline: none;
}
.kpi-card:hover,
.kpi-card:focus-visible {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.06);
  border-color: #cbd5e1;
}
.kpi-card.active {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59,130,246,0.15);
}
.kpi-icon {
  width: 36px; height: 36px;
  border-radius: 9px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.kpi-icon-blue { background: #eff6ff; color: #2563eb; }
.kpi-icon-purple { background: #f5f3ff; color: #7c3aed; }
.kpi-icon-green { background: #ecfdf5; color: #059669; }
.kpi-icon-orange { background: #fff7ed; color: #ea580c; }
.kpi-body { flex: 1; min-width: 0; }
.kpi-label { font-size: 11px; color: #94a3b8; margin-bottom: 2px; }
.kpi-val {
  font-size: 22px; font-weight: 800; color: #0f172a;
  line-height: 1.1; letter-spacing: -0.3px;
  font-variant-numeric: tabular-nums;
}
.kpi-sub { font-size: 11px; color: #64748b; margin-top: 3px; }
.kpi-sub-good { color: #16a34a; font-weight: 600; }
.kpi-sub-bad { color: #dc2626; font-weight: 600; }
.kpi-sub-live { color: #ea580c; font-weight: 600; }

/* ===== 面板 ===== */
.panel {
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 14px;
  padding: 18px 22px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}

/* ===== 工具栏 ===== */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.toolbar-tabs {
  display: inline-flex;
  background: #f1f5f9;
  border-radius: 8px;
  padding: 3px;
  gap: 2px;
}
.seg {
  background: transparent;
  border: none;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: background .15s, color .15s, box-shadow .15s;
}
.seg:hover { color: #0f172a; }
.seg.active {
  background: #fff;
  color: #0f172a;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}
.seg-count {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 10px;
  background: rgba(148, 163, 184, 0.15);
  color: #64748b;
  font-weight: 600;
}
.seg.active .seg-count { background: #eff6ff; color: #2563eb; }

.toolbar-actions {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}

/* ===== 表格 ===== */
.geo-table {
  --el-table-border-color: transparent;
  --el-table-header-bg-color: transparent;
  --el-table-row-hover-bg-color: #f8fafc;
}
.geo-table :deep(.el-table__header-wrapper) {
  border-bottom: 1px solid #f1f5f9;
}
.geo-table :deep(.el-table__header th) {
  background: transparent !important;
  padding: 10px 0 !important;
  text-transform: none;
}
.geo-table :deep(.el-table__body td) {
  border-bottom: 1px solid #f1f5f9 !important;
  padding: 9px 0 !important;
  background: transparent !important;
}
.geo-table :deep(.el-table__row:hover > td) {
  background: #f8fafc !important;
}
.geo-table :deep(.el-table::before) { display: none; }

.row-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #e2e8f0;
}

.brand-name {
  font-weight: 600;
  color: #4338ca;
  font-size: 13px;
}

.prompt-count {
  font-weight: 700;
  color: #0f172a;
  font-size: 14px;
}

.extra-req {
  font-size: 12px;
  color: #475569;
}

.text-muted {
  color: #cbd5e1;
}

.action-btns {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
.action-btns .el-button {
  font-size: 12px;
}
</style>
