<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="`任务详情 - ${task?.brandName || ''}`"
    width="800px"
    top="5vh"
    destroy-on-close
  >
    <div v-loading="loading" class="task-detail">
      <!-- 任务信息 -->
      <div class="task-info" v-if="task">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="品牌">{{ task.brandName }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(task.status)" size="small">{{ statusLabel(task.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="提示词数">{{ task.totalPrompts || task.promptCount }}</el-descriptions-item>
          <el-descriptions-item label="创建时间" :span="2">{{ formatTime(task.createdAt) }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ task.completedAt ? formatTime(task.completedAt) : '-' }}</el-descriptions-item>
        </el-descriptions>
      </div>

      <!-- 提示词列表 -->
      <div class="prompts-section" v-if="prompts.length > 0">
        <div class="prompts-header">
          <span>生成的提示词（共 {{ prompts.length }} 条）</span>
          <el-button size="small" @click="copyAll">复制全部</el-button>
        </div>

        <el-table :data="prompts" stripe size="small" max-height="400">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column prop="intentCategory" label="意图分类" width="130" />
          <el-table-column prop="coreIntentWord" label="核心意图词" width="140" />
          <el-table-column prop="promptText" label="提示词" min-width="300" show-overflow-tooltip />
        </el-table>
      </div>

      <el-empty v-else-if="!loading && task && task.status === 'completed'" description="暂无提示词数据" />
      <el-empty v-else-if="!loading && task && (task.status === 'pending' || task.status === 'running')" description="任务执行中，请稍后查看..." />
    </div>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import geoExpansionApi from '../../api/geoExpansion'

const props = defineProps({
  visible: Boolean,
  taskId: [Number, String],
})

const emit = defineEmits(['update:visible'])

const loading = ref(false)
const task = ref(null)
const prompts = ref([])

// 加载详情
async function loadDetail() {
  if (!props.taskId) return

  loading.value = true
  try {
    const data = await geoExpansionApi.getTaskDetail(props.taskId)
    task.value = data.task
    prompts.value = data.prompts || []
  } catch (e) {
    console.error('Failed to load task detail:', e)
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

// 复制全部提示词
function copyAll() {
  const text = prompts.value.map((p, i) => `${i + 1}. [${p.intentCategory}] ${p.promptText}`).join('\n')
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

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
  return timeStr.replace('T', ' ').substring(0, 19)
}

watch(() => props.visible, (val) => {
  if (val) {
    loadDetail()
  } else {
    task.value = null
    prompts.value = []
  }
})
</script>

<style scoped>
.task-detail {
  min-height: 200px;
}

.task-info {
  margin-bottom: 20px;
}

.prompts-section {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  overflow: hidden;
}

.prompts-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: var(--el-fill-color-light);
  font-weight: 500;
  font-size: 14px;
}
</style>
