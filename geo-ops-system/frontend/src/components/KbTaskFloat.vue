<template>
  <Transition name="kb-task-float-tr">
    <div v-if="tasks.length" class="kb-task-float" :class="{ minimized }">
      <!-- 任务数量标签 -->
      <div v-if="tasks.length > 1" class="kb-task-badge">{{ tasks.length }}</div>
      
      <div class="kb-task-float-head" @click="minimized = !minimized">
        <div class="kb-task-float-spin">
          <el-icon class="is-loading" :size="16"><Loading /></el-icon>
        </div>
        <div class="kb-task-float-title">
          {{ currentTask?.hint || 'AI 正在处理...' }}
          <span v-if="currentTask?.accountName" class="kb-task-acct-name">· {{ currentTask.accountName }}</span>
        </div>
        <span class="kb-task-float-elapsed">{{ currentElapsedText }}</span>
        <el-icon class="kb-task-float-tog" :size="14">
          <ArrowDown v-if="!minimized" />
          <ArrowUp v-else />
        </el-icon>
      </div>
      
      <div v-if="!minimized" class="kb-task-float-body">
        <!-- 多任务列表 -->
        <div v-if="tasks.length > 1" class="kb-task-list">
          <div v-for="t in tasks" :key="t.taskId" 
               class="kb-task-item" 
               :class="{ active: t.taskId === currentTask?.taskId }">
            <span class="kb-task-item-name">{{ t.hint || '任务处理中' }}</span>
            <span v-if="t.accountName" class="kb-task-item-acct">{{ t.accountName }}</span>
            <span class="kb-task-item-time">{{ formatElapsed(t.elapsed) }}</span>
          </div>
        </div>

        <!-- 单任务进度/文本 -->
        <template v-else>
          <div v-if="currentTask?.phase === 'upload'" class="kb-task-progress">
            <div class="kb-task-progress-bar">
              <div class="kb-task-progress-fill" :style="{ width: (currentTask?.percent || 0) + '%' }"></div>
            </div>
            <div class="kb-task-progress-text">{{ currentTask?.percent }}%</div>
          </div>
          <div class="kb-task-text">{{ currentTask?.text || '' }}</div>
        </template>
        
        <div class="kb-task-tip">
          <el-icon :size="11"><InfoFilled /></el-icon>
          可继续做其它操作 / 切换页面，完成后会自动通知
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { Loading, ArrowDown, ArrowUp, InfoFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import publishApi from '@/api/publish'

// ── 多任务支持：用数组管理所有活跃任务 ──
const tasks = ref([])       // [{ taskId, accountId, accountName, hint, text, phase, percent, taskType, startTime, elapsed }]
const minimized = ref(false)
const currentIndex = ref(0) // 当前显示的任务索引

// 当前显示的任务（最新的或用户切换的）
const currentTask = computed(() => {
  if (!tasks.value.length) return null
  return tasks.value[currentIndex.value] || tasks.value[0]
})

function formatElapsed(s) {
  if (!s) return '0s'
  if (s < 60) return s + 's'
  return Math.floor(s / 60) + 'm' + String(s % 60).padStart(2, '0') + 's'
}

const currentElapsedText = computed(() => formatElapsed(currentTask.value?.elapsed || 0))

// 更新所有任务的 elapsed
let globalElapsedTimer = null
function startGlobalTimer() {
  if (globalElapsedTimer) clearInterval(globalElapsedTimer)
  globalElapsedTimer = setInterval(() => {
    const now = Date.now()
    tasks.value.forEach(t => {
      t.elapsed = Math.floor((now - t.startTime) / 1000)
    })
  }, 1000)
}
function stopGlobalTimer() {
  if (globalElapsedTimer) { clearInterval(globalElapsedTimer); globalElapsedTimer = null }
}

// ── 事件处理 ──

function startTask(ev) {
  const d = ev.detail || {}
  const newTask = {
    taskId: d.taskId,
    accountId: d.accountId || null,
    accountName: d.accountName || '',
    hint: d.hint || 'AI 正在生成知识库...',
    text: d.text || '',
    phase: d.phase || 'llm',
    percent: d.percent || 0,
    taskType: d.taskType || 'generate',
    startTime: Date.now(),
    elapsed: 0,
    _pollTimer: null,
  }
  
  // 添加到列表尾部（先提交的任务在前）
  tasks.value.push(newTask)
  currentIndex.value = 0
  
  // 启动全局计时器
  if (tasks.value.length === 1) startGlobalTimer()
  
  minimized.value = false
  
  // 为这个任务启动轮询
  if (newTask.taskId) {
    startPollingFor(newTask)
  }
}

function updateProgress(ev) {
  const d = ev.detail || {}
  // 根据 taskId 找到对应任务更新
  if (d.taskId) {
    const task = tasks.value.find(t => t.taskId === d.taskId)
    if (task) {
      if (d.phase) task.phase = d.phase
      if (d.percent != null) task.percent = d.percent
      if (d.hint) task.hint = d.hint
      if (d.text) task.text = d.text
      if (d.accountName) task.accountName = d.accountName
    }
  }
}

function failTask(ev) {
  const err = ev?.detail?.error || '未知错误'
  ElMessage.error('任务失败：' + err)
  // 尝试找到对应任务移除
  const tid = ev?.detail?.taskId
  if (tid) removeTask(tid)
}

function removeTask(taskId) {
  const idx = tasks.value.findIndex(t => t.taskId === taskId)
  if (idx >= 0) {
    const task = tasks.value[idx]
    if (task._pollTimer) { clearInterval(task._pollTimer); task._pollTimer = null }
    tasks.value.splice(idx, 1)
    // 调整当前索引
    if (currentIndex.value >= tasks.value.length) {
      currentIndex.value = Math.max(0, tasks.value.length - 1)
    }
  }
  // 没有任务了，停止计时器
  if (!tasks.value.length) stopGlobalTimer()
}

// ── 单任务轮询 ──

function startPollingFor(task) {
  if (task._pollTimer) clearInterval(task._pollTimer)
  task._pollTimer = setInterval(async () => {
    try {
      const r = await publishApi.kbTaskStatus(task.taskId)
      if (r.status === 'done') {
        const isRecognize = r.task_type === 'recognize' || task.taskType === 'recognize'
        if (isRecognize) {
          ElMessage.success('智能识别完成！')
          window.dispatchEvent(new CustomEvent('kb-recognize-done', {
            detail: { accountId: task.accountId, sourceId: r.source_id }
          }))
        } else {
          ElMessage.success(`${task.accountName ? task.accountName + ' ' : ''}知识库生成完成！`)
          window.dispatchEvent(new CustomEvent('kb-task-done', {
            detail: { accountId: task.accountId, kbId: r.kb_id, version: r.version }
          }))
        }
        removeTask(task.taskId)
      } else if (r.status === 'failed') {
        const isRecognize = r.task_type === 'recognize' || task.taskType === 'recognize'
        const label = isRecognize ? '识别失败' : '生成失败'
        ElMessage.error(label + '：' + (r.error || '未知错误'))
        removeTask(task.taskId)
      }
    } catch (e) {
      console.warn('轮询失败', e)
    }
  }, 3000)
}

// ── 页面恢复 ──

async function restoreActiveTasks() {
  try {
    const r = await publishApi.kbActiveTasks()
    const items = r?.items || []
    if (items.length) {
      items.forEach(t => {
        const restored = {
          taskId: t.id,
          accountId: t.account_id,
          accountName: t.account_name || '',
          hint: t.hint || 'AI 正在生成知识库...',
          text: '正在获取任务进度...',
          phase: 'llm',
          percent: 0,
          taskType: t.task_type || 'generate',
          startTime: new Date(t.created_at).getTime(),
          elapsed: Math.floor((Date.now() - new Date(t.created_at).getTime()) / 1000),
          _pollTimer: null,
        }
        tasks.value.push(restored)
      })
      currentIndex.value = 0
      startGlobalTimer()
      // 为每个恢复的任务启动轮询
      items.forEach(t => {
        const task = tasks.value.find(tk => tk.taskId === t.id)
        if (task) startPollingFor(task)
      })
    }
  } catch {
    // 静默失败
  }
}

onMounted(() => {
  window.addEventListener('kb-task-start', startTask)
  window.addEventListener('kb-task-progress', updateProgress)
  window.addEventListener('kb-task-failed', failTask)
  restoreActiveTasks()
})

onBeforeUnmount(() => {
  window.removeEventListener('kb-task-start', startTask)
  window.removeEventListener('kb-task-progress', updateProgress)
  window.removeEventListener('kb-task-failed', failTask)
  stopGlobalTimer()
  tasks.value.forEach(t => { if (t._pollTimer) clearInterval(t._pollTimer) })
})
</script>

<style scoped>
.kb-task-float {
  position: fixed; right: 20px; bottom: 20px; z-index: 2000;
  width: 320px;
  background: #fff; border-radius: 14px;
  box-shadow:
    0 24px 64px -12px rgba(15, 23, 42, .25),
    0 0 0 1px rgba(99, 102, 241, .15);
  border: 1px solid rgba(99, 102, 241, .1);
  overflow: hidden;
}
.kb-task-float.minimized { width: 240px; }
.kb-task-float-tr-enter-active,
.kb-task-float-tr-leave-active { transition: transform .25s, opacity .25s; }
.kb-task-float-tr-enter-from,
.kb-task-float-tr-leave-to {
  opacity: 0; transform: translateY(20px) scale(.95);
}
.kb-task-float-head {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #fff;
  cursor: pointer;
}
.kb-task-float-spin { display: flex; align-items: center; }
.kb-task-float-title {
  flex: 1; font-size: 13px; font-weight: 600;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.kb-task-float-elapsed {
  font-size: 11.5px; color: rgba(255,255,255,.85);
  background: rgba(255,255,255,.18); padding: 2px 7px; border-radius: 10px;
  font-variant-numeric: tabular-nums;
}
.kb-task-float-tog { color: rgba(255,255,255,.85); }
.kb-task-float-body { padding: 12px 14px 14px; }
.kb-task-progress { margin-bottom: 10px; }
.kb-task-progress-bar {
  height: 6px; background: #f1f5f9; border-radius: 999px;
  overflow: hidden;
}
.kb-task-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
  border-radius: 999px;
  transition: width .2s;
}
.kb-task-progress-text {
  margin-top: 4px;
  font-size: 11.5px; color: #6366f1; font-weight: 600;
}
.kb-task-float-body .kb-task-text {
  font-size: 12.5px; color: #475569; line-height: 1.6;
  margin-bottom: 8px;
}
.kb-task-tip {
  display: flex; align-items: center; gap: 4px;
  font-size: 11px; color: #94a3b8; line-height: 1.5;
  padding-top: 8px; border-top: 1px dashed #e2e8f0;
}

/* ── 多任务支持 ── */
.kb-task-badge {
  position: absolute; top: -6px; right: -6px;
  min-width: 18px; height: 18px;
  background: #ef4444; color: #fff;
  font-size: 11px; font-weight: 700;
  border-radius: 9px;
  display: flex; align-items: center; justify-content: center;
  padding: 0 5px;
  box-shadow: 0 2px 6px rgba(239,68,68,.4);
  z-index: 1;
}
.kb-task-acct-name {
  font-size: 11.5px; font-weight: 400;
  color: rgba(255,255,255,.75);
  margin-left: 2px;
}
.kb-task-list {
  max-height: 160px; overflow-y: auto;
  margin-bottom: 10px;
}
.kb-task-item {
  display: flex; align-items: center; gap: 6px;
  padding: 7px 9px;
  border-radius: 6px;
  margin-bottom: 4px;
  background: #f8fafc;
  border: 1px solid transparent;
  transition: all .15s;
}
.kb-task-item.active {
  background: #eef2ff;
  border-color: #c7d2fe;
}
.kb-task-item-name {
  flex: 1; font-size: 12px; color: #334155;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.kb-task-item-acct {
  font-size: 11px; color: #6366f1; font-weight: 500;
  white-space: nowrap;
}
.kb-task-item-time {
  font-size: 11px; color: #94a3b8;
  font-variant-numeric: tabular-nums; white-space: nowrap;
}
</style>
