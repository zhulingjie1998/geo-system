<template>
  <Transition name="kb-task-float-tr">
    <div v-if="visible" class="kb-task-float" :class="{ minimized }">
      <div class="kb-task-float-head" @click="minimized = !minimized">
        <div class="kb-task-float-spin">
          <el-icon class="is-loading" :size="16"><Loading /></el-icon>
        </div>
        <div class="kb-task-float-title">{{ title }}</div>
        <span class="kb-task-float-elapsed">{{ elapsedText }}</span>
        <el-icon class="kb-task-float-tog" :size="14">
          <ArrowDown v-if="!minimized" />
          <ArrowUp v-else />
        </el-icon>
      </div>
      <div v-if="!minimized" class="kb-task-float-body">
        <div v-if="phase === 'upload'" class="kb-task-progress">
          <div class="kb-task-progress-bar">
            <div class="kb-task-progress-fill" :style="{ width: percent + '%' }"></div>
          </div>
          <div class="kb-task-progress-text">{{ percent }}%</div>
        </div>
        <div class="kb-task-text">{{ text }}</div>
        <div class="kb-task-tip">
          <el-icon :size="11"><InfoFilled /></el-icon>
          可继续做其它操作 / 切换页面，完成后会自动通知
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { Loading, ArrowDown, ArrowUp, InfoFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import publishApi from '@/api/publish'

const visible = ref(false)
const minimized = ref(false)
const phase = ref('llm')       // 'upload' | 'llm'
const percent = ref(0)
const title = ref('')
const text = ref('')
const taskId = ref(null)
const accountId = ref(null)
const taskType = ref('generate')  // 'generate' | 'recognize'
const startTime = ref(0)
const elapsed = ref(0)
let pollTimer = null
let elapsedTimer = null

const elapsedText = computed(() => {
  const s = elapsed.value
  if (s < 60) return s + 's'
  return Math.floor(s / 60) + 'm' + String(s % 60).padStart(2, '0') + 's'
})

function startTask(ev) {
  const d = ev.detail || {}
  phase.value = d.phase || 'llm'
  percent.value = d.percent || 0
  title.value = d.hint || 'AI 正在生成知识库...'
  text.value = d.text || ''
  taskId.value = d.taskId || null
  accountId.value = d.accountId || null
  taskType.value = d.taskType || 'generate'
  visible.value = true
  minimized.value = false
  startTime.value = Date.now()
  elapsed.value = 0

  // 启动计时器
  if (elapsedTimer) clearInterval(elapsedTimer)
  elapsedTimer = setInterval(() => {
    elapsed.value = Math.floor((Date.now() - startTime.value) / 1000)
  }, 1000)

  // 如果有 taskId，启动轮询
  if (taskId.value) {
    startPolling()
  }
}

function updateProgress(ev) {
  const d = ev.detail || {}
  if (d.phase) phase.value = d.phase
  if (d.percent != null) percent.value = d.percent
  if (d.hint) title.value = d.hint
  if (d.text) text.value = d.text
  if (d.taskId && !taskId.value) {
    taskId.value = d.taskId
    startPolling()
  }
}

function failTask(ev) {
  const err = ev?.detail?.error || '未知错误'
  ElMessage.error('任务失败：' + err)
  cleanup()
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    if (!taskId.value) return
    try {
      const r = await publishApi.kbTaskStatus(taskId.value)
      if (r.status === 'done') {
        const isRecognize = r.task_type === 'recognize' || taskType.value === 'recognize'
        if (isRecognize) {
          ElMessage.success('智能识别完成！')
          window.dispatchEvent(new CustomEvent('kb-recognize-done', {
            detail: { accountId: accountId.value, sourceId: r.source_id }
          }))
        } else {
          ElMessage.success('知识库生成完成！')
          window.dispatchEvent(new CustomEvent('kb-task-done', {
            detail: { accountId: accountId.value, kbId: r.kb_id, version: r.version }
          }))
        }
        cleanup()
      } else if (r.status === 'failed') {
        const isRecognize = r.task_type === 'recognize' || taskType.value === 'recognize'
        const label = isRecognize ? '识别失败' : '生成失败'
        ElMessage.error(label + '：' + (r.error || '未知错误'))
        cleanup()
      }
    } catch (e) {
      // 网络错误，继续轮询
      console.warn('轮询失败', e)
    }
  }, 3000)
}

function cleanup() {
  visible.value = false
  taskId.value = null
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null }
}

// 页面刷新后恢复正在运行的任务
async function restoreActiveTasks() {
  try {
    const r = await publishApi.kbActiveTasks()
    const tasks = r?.items || []
    if (tasks.length) {
      const t = tasks[0]
      taskId.value = t.id
      accountId.value = t.account_id
      taskType.value = t.task_type || 'generate'
      title.value = t.hint || 'AI 正在生成知识库...'
      text.value = '任务恢复中...'
      phase.value = 'llm'
      visible.value = true
      startTime.value = new Date(t.created_at).getTime()
      elapsed.value = Math.floor((Date.now() - startTime.value) / 1000)
      if (elapsedTimer) clearInterval(elapsedTimer)
      elapsedTimer = setInterval(() => {
        elapsed.value = Math.floor((Date.now() - startTime.value) / 1000)
      }, 1000)
      startPolling()
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
  if (pollTimer) clearInterval(pollTimer)
  if (elapsedTimer) clearInterval(elapsedTimer)
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
</style>
