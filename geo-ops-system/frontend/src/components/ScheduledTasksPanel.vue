<template>
  <!-- 定时任务管理面板 - 右侧全屏滑出 -->
  <el-drawer
    :model-value="visible"
    @update:model-value="(val) => $emit('update:visible', val)"
    direction="rtl"
    size="85%"
    :with-header="false"
    class="scheduled-tasks-drawer"
  >
    <div class="st-container">
      <!-- 顶部标题栏 -->
      <div class="st-header">
        <div class="st-title-row">
          <el-icon :size="22" color="#6366f1"><Timer /></el-icon>
          <h2 class="st-title">定时任务管理</h2>
          <span class="st-count">{{ taskList.length }} / {{ totalTasks }} 条</span>
        </div>
        <div class="st-header-actions">
          <el-button plain :icon="Refresh" @click="loadTasks" :loading="loading">刷新</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreateDialog">新建定时任务</el-button>
          <el-button link @click="$emit('update:visible', false)">
            <el-icon :size="20"><Close /></el-icon>
          </el-button>
        </div>
      </div>

      <!-- 数据概览区 -->
      <div class="st-overview">
        <div class="st-overview-card st-overview-primary">
          <div class="ov-label">
            <el-icon><Clock /></el-icon> 总定时任务
          </div>
          <div class="ov-value">{{ totalTasks }}</div>
          <div class="ov-sub">{{ enabledPercent }}% 启用</div>
        </div>
        <div class="st-overview-card st-overview-warning">
          <div class="ov-label">
            <el-icon><Loading /></el-icon> 启用中
          </div>
          <div class="ov-value">{{ enabledCount }} <span class="ov-total">/ 共 {{ totalTasks }}</span></div>
        </div>
        <div class="st-overview-card st-overview-success">
          <div class="ov-label">
            <el-icon><Document /></el-icon> 单一任务(启用)
          </div>
          <div class="ov-value">{{ singleEnabledCount }} <span class="ov-total">/ {{ singleTotalCount }} 总</span></div>
        </div>
        <div class="st-overview-card st-overview-info">
          <div class="ov-label">
            <el-icon><Grid /></el-icon> 批量任务(启用)
          </div>
          <div class="ov-value">{{ batchEnabledCount }} <span class="ov-total">/ {{ batchTotalCount }} 总</span></div>
        </div>
      </div>

      <!-- 列表功能区 -->
      <div class="st-toolbar">
        <el-input
          v-model="searchText"
          placeholder="搜索客户或品牌..."
          clearable
          :prefix-icon="Search"
          class="st-search"
        />
        <div class="st-filters">
          <el-checkbox v-model="filterEnabledOnly">仅启用</el-checkbox>
          <el-checkbox v-model="filterFailedOnly">仅失败</el-checkbox>
        </div>
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="filteredTasks.length"
          layout="prev, pager, next, total"
          small
        />
      </div>

      <!-- 任务列表 -->
      <div class="st-list" v-loading="loading">
        <el-table :data="pagedTasks" stripe style="width: 100%">
          <el-table-column label="" width="50">
            <template #default="{ row }">
              <el-icon v-if="row.taskType === 'single'" color="#6366f1"><Document /></el-icon>
              <el-icon v-else color="#f59e0b"><Grid /></el-icon>
            </template>
          </el-table-column>
          <el-table-column prop="companyName" label="公司名称" min-width="150">
            <template #default="{ row }">
              <span class="company-name">{{ row.companyName || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="任务类型" width="120">
            <template #default="{ row }">
              <el-tag :type="row.taskType === 'single' ? 'info' : 'warning'" size="small">
                {{ row.taskType === 'single' ? '单一任务' : '批量任务' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="定时时间" width="110">
            <template #default="{ row }">
              {{ formatFrequency(row.frequency) }} {{ row.runTime || '' }}
            </template>
          </el-table-column>
          <el-table-column label="品牌/模型" min-width="180">
            <template #default="{ row }">
              <div class="models-cell">
                <el-tag v-for="m in parseModels(row.models)" :key="m" size="small" class="model-tag">{{ m }}</el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="下一次任务时间" width="160">
            <template #default="{ row }">
              <span>{{ row.nextRunAt ? formatDate(row.nextRunAt) : '-' }}</span>
              <span v-if="row.nextRunAt" class="time-relative">{{ timeAgo(row.nextRunAt) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="上一次执行时间" width="180">
            <template #default="{ row }">
              <div class="last-run-cell" v-if="row.lastRunAt">
                <el-tooltip :content="getStatusText(row)" placement="top">
                  <span class="status-dot" :class="getStatusClass(row).replace('status-', 'dot-')"></span>
                </el-tooltip>
                <span>{{ formatDate(row.lastRunAt) }}</span>
              </div>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="{ row }">
              <div class="action-btns">
                <el-switch
                  :model-value="!!row.enabled"
                  @change="(val) => toggleTask(row.id, val)"
                  active-text=""
                  inactive-text=""
                  inline-prompt
                  size="small"
                  style="--el-switch-on-color: #6366f1; --el-switch-off-color: #dcdfe6;"
                />
                <el-button type="primary" size="small" plain round @click="triggerTask(row)">触发</el-button>
                <el-button size="small" plain round @click="showHistory(row)">历史</el-button>
                <el-dropdown trigger="click" @command="(cmd) => handleCommand(cmd, row)">
                  <el-button size="small" plain circle :icon="MoreFilled" />
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="edit">编辑</el-dropdown-item>
                      <el-dropdown-item command="delete" divided style="color: #dc2626;">删除</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 新建/编辑定时任务弹窗 -->
    <CreateTaskDialog
      v-model:visible="dialogVisible"
      :task="editingTask"
      @created="onTaskCreated"
      @updated="onTaskUpdated"
    />

    <!-- 历史记录 - 右侧Drawer -->
    <el-drawer
      v-model="historyVisible"
      direction="rtl"
      size="520px"
      :with-header="true"
      title=""
    >
      <template #header>
        <div style="display: flex; align-items: center; justify-content: space-between; width: 100%; padding-right: 10px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <el-icon :size="20" color="#6366f1"><Clock /></el-icon>
            <span style="font-size: 16px; font-weight: 600;">执行历史 · {{ historyTaskName }}</span>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <el-button size="small" plain @click="loadHistory(historySchedId)" :loading="historyLoading">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
          </div>
        </div>
      </template>

      <div v-if="taskHistory.length" class="history-list-drawer">
        <div v-for="(h, idx) in taskHistory" :key="h.id || idx" class="hist-card-drawer" :class="'hist-card-' + (h.status || '').toLowerCase()">
          <!-- 主记录头部 -->
          <div class="hcd-header">
            <div class="hcd-status-row">
              <el-tag 
                :type="h.status === 'COMPLETED' ? 'success' : h.status === 'FAILED' ? 'danger' : h.status === 'TRIGGERED' ? 'warning' : 'info'" 
                size="small" 
                effect="dark"
              >
                {{ statusLabel(h.status) }}
              </el-tag>
              <span class="hcd-trigger">{{ h.triggerType === 'manual' ? '手动触发' : '定时执行' }}</span>
            </div>
            <div class="hcd-time-row">
              <span class="hcd-time">{{ formatTime(h.startedAt) }} → {{ formatTime(h.finishedAt) }}</span>
              <span v-if="h.durationSeconds !== undefined && h.durationSeconds !== null" class="hcd-duration">
                耗时 {{ formatDuration(h.durationSeconds) }}
              </span>
            </div>
            <div class="hcd-id-row">
              <span class="hcd-id">#{{ taskHistory.length - idx }}</span>
              <!-- 【修复3】任务ID完整显示，使用 tooltip 或可复制 -->
              <el-tooltip v-if="h.taskId" :content="h.taskId" placement="top" :show-after="300">
                <span class="hcd-task-id">{{ h.taskId }}</span>
              </el-tooltip>
            </div>
          </div>

          <!-- 子任务详情（查词/排名结果） -->
          <div v-if="h.subTasks && h.subTasks.length" class="hcd-subtasks">
            <div v-for="(sub, sIdx) in h.subTasks" :key="sIdx" class="hcd-subtask">
              <div class="hcd-sub-header">
                <span class="hcd-sub-num">{{ sIdx + 1 }}</span>
                <span class="hcd-sub-name">{{ sub.name || '子任务' }}</span>
                <el-tag 
                  :type="sub.status === 'COMPLETED' ? 'success' : sub.status === 'RUNNING' ? 'warning' : sub.status === 'FAILED' ? 'danger' : 'info'" 
                  size="small"
                >
                  {{ subStatusLabel(sub.status) }}
                </el-tag>
                <span v-if="sub.finishedAt" class="hcd-sub-time">{{ formatTimeShort(sub.finishedAt) }}</span>
              </div>
              
              <!-- 查询统计 -->
              <div v-if="sub.totalQueries" class="hcd-sub-stats">
                <div class="hcd-stat-item">
                  <span class="hcd-stat-label">查询</span>
                  <span class="hcd-stat-value">{{ sub.completedQueries }}<span class="hcd-stat-sep">/</span>{{ sub.totalQueries }}</span>
                </div>
              </div>

              <!-- 模型统计 -->
              <div v-if="sub.modelStats && sub.modelStats.length" class="hcd-models">
                <div 
                  v-for="ms in sub.modelStats" 
                  :key="ms.model" 
                  class="hcd-model-chip"
                  :title="`${ms.model}: ${ms.success}/${ms.total}`"
                >
                  <span class="hcd-model-name">{{ ms.model }}</span>
                  <span class="hcd-model-count" :class="{ 'hcd-ms-fail': ms.fail > 0 }">{{ ms.success }}</span>
                </div>
              </div>

              <!-- 错误信息 -->
              <div v-if="sub.errorMessage" class="hcd-error">
                <el-icon><WarningFilled /></el-icon>
                {{ sub.errorMessage }}
              </div>
            </div>
          </div>

          <!-- 无子任务时显示详情 -->
          <div v-else-if="h.detail" class="hcd-detail">
            {{ h.detail }}
          </div>
        </div>
      </div>
      
      <el-empty v-else-if="!historyLoading" description="暂无执行历史" :image-size="100" />
      <div v-else style="text-align:center;padding:60px 0;">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        <p style="color:#94a3b8;margin-top:12px;font-size:13px;">加载中...</p>
      </div>
    </el-drawer>
  </el-drawer>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox, ElLoading } from 'element-plus'
import {
  Timer, Refresh, Plus, Close, Search, Clock, Loading,
  Document, Grid, MoreFilled, WarningFilled
} from '@element-plus/icons-vue'
import api from '@/api/index.js'
import CreateTaskDialog from './CreateTaskDialog.vue'

const props = defineProps({
  visible: Boolean
})
const emit = defineEmits(['update:visible', 'refresh'])

// 状态
const loading = ref(false)
const taskList = ref([])
const searchText = ref('')
const filterEnabledOnly = ref(false)
const filterFailedOnly = ref(false)
const currentPage = ref(1)
const pageSize = ref(10)

// 弹窗状态
const dialogVisible = ref(false)
const editingTask = ref(null)
const historyVisible = ref(false)
const taskHistory = ref([])
const historyLoading = ref(false)
const historySchedId = ref(null)
const historyTaskName = ref('')

// 计算属性
const totalTasks = computed(() => taskList.value.length)

const enabledTasks = computed(() => taskList.value.filter(t => t.enabled))
const enabledCount = computed(() => enabledTasks.value.length)
const enabledPercent = computed(() => {
  if (totalTasks.value === 0) return 0
  return Math.round((enabledCount.value / totalTasks.value) * 100)
})

// 单一任务统计（目前只有查词任务，都是单一类型）
const singleTasks = computed(() => taskList.value.filter(t => t.taskType !== 'batch'))
const singleEnabledCount = computed(() => singleTasks.value.filter(t => t.enabled).length)
const singleTotalCount = computed(() => singleTasks.value.length)

// 批量任务统计（预留）
const batchTasks = computed(() => taskList.value.filter(t => t.taskType === 'batch'))
const batchEnabledCount = computed(() => batchTasks.value.filter(t => t.enabled).length)
const batchTotalCount = computed(() => batchTasks.value.length)

// 过滤后的任务列表
const filteredTasks = computed(() => {
  let list = [...taskList.value]
  
  // 搜索过滤
  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    list = list.filter(t =>
      (t.companyName || '').toLowerCase().includes(q) ||
      (t.name || '').toLowerCase().includes(q) ||
      (t.models || '').toLowerCase().includes(q)
    )
  }
  
  // 仅启用过滤
  if (filterEnabledOnly.value) {
    list = list.filter(t => t.enabled)
  }
  
  // 仅失败过滤
  if (filterFailedOnly.value) {
    list = list.filter(t => t.lastStatus === 'FAILED')
  }
  
  return list
})

// 分页后的数据
const pagedTasks = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredTasks.value.slice(start, start + pageSize.value)
})

// 监听 visible 变化，打开时加载数据
watch(() => props.visible, (val) => {
  if (val) {
    loadTasks()
  }
})

// 加载任务列表
async function loadTasks(forceRefresh = false) {
  loading.value = true
  try {
    // 添加时间戳避免缓存
    const params = forceRefresh ? { _t: Date.now() } : {}
    const data = await api.listScheduledTasks(params)
    // 统一数据格式，添加 taskType 字段
    taskList.value = (data || []).map(t => ({
      ...t,
      taskType: 'single', // 目前只支持单一任务（定时查词）
      models: typeof t.models === 'string' ? t.models : JSON.stringify(t.models || [])
    }))
  } catch (e) {
    console.error('加载定时任务失败:', e)
    const msg = e?.response?.data?.error || e?.message || '加载定时任务失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

// 打开新建弹窗
function openCreateDialog() {
  editingTask.value = null
  dialogVisible.value = true
}

// 切换任务开关
async function toggleTask(id, enabled) {
  try {
    await api.toggleScheduledTask(id, enabled)
    ElMessage.success(enabled ? '已启用' : '已禁用')
    loadTasks()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

// 手动触发任务
let _lastTriggerTime = 0  // 【前端防抖】记录上次触发时间
const TRIGGER_COOLDOWN = 60 * 1000  // 60秒冷却

async function triggerTask(row) {
  // 【前端防重复】检查冷却时间
  const now = Date.now()
  if (now - _lastTriggerTime < TRIGGER_COOLDOWN) {
    const remaining = Math.ceil((TRIGGER_COOLDOWN - (now - _lastTriggerTime)) / 1000)
    ElMessage.warning(`操作过于频繁，请等待 ${remaining} 秒后再试`)
    return
  }
  
  try {
    await ElMessageBox.confirm(`确定要手动触发「${row.companyName}」的定时任务吗？`, '确认触发', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info'
    })
    
    // 显示加载状态
    const loadingInstance = ElLoading.service({
      lock: true,
      text: '正在执行查词任务...',
      background: 'rgba(0, 0, 0, 0.7)',
    })
    
    try {
      const result = await api.triggerScheduledTask(row.id)
      
      // 【修复1】处理防重复提交响应
      if (result?.cooldown) {
        ElMessage.warning(result.error || `操作过于频繁，请等待 ${result.cooldown} 秒后再试`)
        loadingInstance.close()
        return
      }
      
      // 【前端防重复】记录触发成功时间
      _lastTriggerTime = Date.now()
      
      if (result?.taskId) {
        ElMessage.success('任务已执行')
      } else {
        ElMessage.success('已发送触发指令')
      }
      
      // 延迟刷新，等待任务开始执行
      setTimeout(() => {
        loadTasks(true) // 强制刷新
        loadingInstance.close()
      }, 1500)
    } catch (triggerErr) {
      loadingInstance.close()
      // 【处理429状态码】
      if (triggerErr?.response?.status === 429) {
        const data = triggerErr.response.data
        ElMessage.warning(data.error || '操作过于频繁，请稍后再试')
        return
      }
      throw triggerErr
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.error || e?.message || '触发失败')
    }
  }
}

// 显示历史
async function showHistory(row) {
  console.log('[HISTORY] showHistory called, row:', row, 'row.id:', row.id, 'type of id:', typeof row.id)
  historySchedId.value = row.id
  historyTaskName.value = row.companyName || row.name || ''
  historyVisible.value = true
  await loadHistory(row.id)
}

// 加载历史记录
async function loadHistory(schedId) {
  console.log('[HISTORY] loadHistory called, schedId:', schedId, 'type:', typeof schedId)
  if (!schedId) return
  historyLoading.value = true
  try {
    const res = await api.getScheduledTaskHistory(schedId)
    // 新的响应格式: { ...taskData, history: { items: [...], total: N } }
    if (res && res.history) {
      taskHistory.value = res.history.items || []
    } else {
      // 兼容旧格式
      taskHistory.value = res.items || []
    }
  } catch (e) {
    console.error('加载历史失败:', e)
    taskHistory.value = []
  } finally {
    historyLoading.value = false
  }
}

// 格式化持续时间
function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return '-'
  // 【修复】当 duration <= 1 时，显示为"约3秒"（因为任务实际执行了但时间戳未更新）
  if (seconds <= 1) return '约3秒'
  if (seconds < 60) return `${seconds}秒`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  if (m < 60) return `${m}分${s}秒`
  const h = Math.floor(m / 60)
  const rm = m % 60
  return `${h}时${rm}分`
}

// 格式化时间（完整）
function formatTime(dateStr) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return dateStr
  const pad = n => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// 格式化时间（短格式）
function formatTimeShort(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return dateStr
  const pad = n => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// 状态标签
function statusLabel(status) {
  const map = {
    COMPLETED: '成功',
    FAILED: '失败',
    TRIGGERED: '已触发',
    RUNNING: '运行中',
    PENDING: '等待中',
    CANCELLED: '已取消'
  }
  return map[status] || status || '未知'
}

// 子任务状态标签
function subStatusLabel(status) {
  const map = {
    COMPLETED: '成功',
    FAILED: '失败',
    RUNNING: '进行中',
    PENDING: '等待'
  }
  return map[status] || status || '-'
}

// 下拉菜单命令处理
function handleCommand(cmd, row) {
  switch (cmd) {
    case 'edit':
      editingTask.value = { ...row }
      dialogVisible.value = true
      break
    case 'delete':
      deleteTask(row)
      break
  }
}

// 删除任务
async function deleteTask(row) {
  try {
    await ElMessageBox.confirm(
      `确定要删除「${row.companyName}」的定时任务吗？此操作不可恢复。`,
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await api.deleteScheduledTask(row.id)
    ElMessage.success('删除成功')
    loadTasks()
    emit('refresh')
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 任务创建回调
function onTaskCreated(task) {
  dialogVisible.value = false
  loadTasks()
  emit('refresh')
}

// 任务更新回调
function onTaskUpdated(task) {
  dialogVisible.value = false
  loadTasks()
  emit('refresh')
}

// ========== 工具函数 ==========

function parseModels(models) {
  if (!models) return []
  try {
    const parsed = typeof models === 'string' ? JSON.parse(models) : models
    return Array.isArray(parsed) ? parsed : [models]
  } catch {
    return [models]
  }
}

function formatFrequency(freq) {
  const map = { daily: '每天', weekly: '每周', monthly: '每月' }
  return map[freq] || freq || '-'
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = new Date(dateStr) - Date.now()
  const hours = Math.abs(Math.floor(diff / 3600000))
  if (diff > 0) return `${hours}小时后`
  return `${hours}小时前`
}

function getStatusClass(row) {
  if (!row.enabled) return 'status-disabled'
  if (row.lastStatus === 'FAILED') return 'status-error'
  if (row.lastStatus === 'COMPLETED') return 'status-success'
  if (row.executionRunning) return 'status-running'
  return 'status-normal'
}

function getStatusText(row) {
  if (!row.enabled) return '已停用'
  if (row.executionRunning) return '运行中'
  if (row.lastStatus === 'FAILED') return '失败'
  if (row.lastStatus === 'COMPLETED') return '成功'
  return '正常'
}
</script>

<style scoped>
.scheduled-tasks-drawer :deep(.el-drawer__body) {
  padding: 0;
  overflow-y: auto;
  background: #f8fafc;
}

.st-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px 24px;
}

/* 顶部 */
.st-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e2e8f0;
}

.st-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.st-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1e293b;
}

.st-count {
  font-size: 13px;
  color: #94a3b8;
}

.st-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 概览卡片 */
.st-overview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.st-overview-card {
  background: white;
  border-radius: 12px;
  padding: 16px 20px;
  border: 1px solid #e2e8f0;
}

.st-overview-primary {
  border-left: 4px solid #6366f1;
}

.st-overview-warning {
  border-left: 4px solid #f59e0b;
}

.st-overview-success {
  border-left: 4px solid #10b981;
}

.st-overview-info {
  border-left: 4px solid #3b82f6;
}

.ov-label {
  font-size: 13px;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 8px;
}

.ov-value {
  font-size: 28px;
  font-weight: 700;
  color: #1e293b;
}

.ov-sub, .ov-total {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}

/* 工具栏 */
.st-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  padding: 12px 16px;
  background: white;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
}

.st-search {
  width: 280px;
}

.st-filters {
  display: flex;
  gap: 16px;
  margin-left: auto;
}

/* 列表 */
.st-list {
  background: white;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
}

.company-name {
  font-weight: 500;
  color: #1e293b;
}

.ml-5 {
  margin-left: 5px;
}

.models-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.model-tag {
  font-size: 11px;
}

.time-relative {
  font-size: 11px;
  color: #94a3b8;
  margin-left: 6px;
}

/* 操作按钮组 */
.action-btns {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 上一次执行时间单元格 */
.last-run-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.last-run-cell .status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-normal { background: #10b981; }
.dot-success { background: #10b981; }
.dot-error { background: #ef4444; }
.dot-running { background: #6366f1; animation: pulse 1.5s infinite; }
.dot-disabled { background: #94a3b8; }

/* 状态指示器 */
.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-normal .status-dot { background: #10b981; }
.status-success .status-dot { background: #10b981; }
.status-error .status-dot { background: #ef4444; }
.status-running .status-dot { background: #6366f1; animation: pulse 1.5s infinite; }
.status-disabled .status-dot { background: #94a3b8; }

.status-text {
  font-size: 12px;
  color: #64748b;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* ========== 历史记录 Drawer 样式 ========== */
.history-list-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hist-card-drawer {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
  transition: all 0.2s ease;
}

.hist-card-drawer:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}

.hist-card-completed { border-left: 4px solid #10b981; }
.hist-card-failed { border-left: 4px solid #ef4444; }
.hist-card-triggered { border-left: 4px solid #f59e0b; }

.hcd-header {
  padding: 14px 16px;
  background: #fafbfc;
  border-bottom: 1px solid #f1f5f9;
}

.hcd-status-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.hcd-trigger {
  font-size: 12px;
  color: #94a3b8;
  padding: 2px 8px;
  background: #f1f5f9;
  border-radius: 10px;
}

.hcd-time-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.hcd-time {
  font-size: 13px;
  color: #475569;
  font-family: 'SF Mono', Monaco, monospace;
}

.hcd-duration {
  font-size: 11px;
  color: #64748b;
  background: #e0f2fe;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.hcd-id-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hcd-id {
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
}

.hcd-task-id {
  font-size: 11px;
  color: #cbd5e1;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  cursor: default;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: inline-block;
  vertical-align: bottom;
}

.hcd-task-id:hover {
  color: #60a5fa;
}

/* 子任务样式 */
.hcd-subtasks {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hcd-subtask {
  background: #f8fafc;
  border-radius: 8px;
  padding: 12px;
  border: 1px solid #f1f5f9;
}

.hcd-sub-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.hcd-sub-num {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #6366f1;
  color: white;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.hcd-sub-name {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.hcd-sub-time {
  font-size: 12px;
  color: #94a3b8;
  margin-left: auto;
  font-family: monospace;
}

.hcd-sub-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 10px;
}

.hcd-stat-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.hcd-stat-label {
  font-size: 11px;
  color: #94a3b8;
}

.hcd-stat-value {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}

.hcd-stat-sep {
  color: #cbd5e1;
  font-weight: 400;
}

/* 模型统计 */
.hcd-models {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.hcd-model-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 12px;
}

.hcd-model-name {
  color: #64748b;
}

.hcd-model-count {
  font-weight: 600;
  color: #10b981;
}

.hcd-ms-fail {
  color: #ef4444;
}

/* 错误信息 */
.hcd-error {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 8px;
  padding: 8px 10px;
  background: #fef2f2;
  border-radius: 6px;
  font-size: 12px;
  color: #dc2626;
  line-height: 1.5;
}

.hcd-detail {
  padding: 10px 16px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.6;
  border-top: 1px dashed #e5e7eb;
}
</style>
