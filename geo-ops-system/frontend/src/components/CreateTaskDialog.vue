<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="(val) => $emit('update:visible', val)"
    :title="isEdit ? '编辑定时任务' : '新建定时任务'"
    width="600px"
    :close-on-click-modal="false"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="120px"
      label-position="top"
      hide-required-asterisk
    >
      <!-- 任务类型 -->
      <el-form-item label="任务类型" prop="taskType">
        <el-radio-group v-model="form.taskType" :disabled="isEdit">
          <el-radio value="single">单一任务</el-radio>
          <el-radio value="batch">批量任务</el-radio>
        </el-radio-group>
        <div v-if="form.taskType === 'batch'" class="form-tip">
          <el-alert type="info" :closable="false" show-icon>
            批量任务功能暂不支持，请选择"单一任务"
          </el-alert>
        </div>
      </el-form-item>

      <!-- 任务子类型（仅单一任务时显示） -->
      <el-form-item v-if="form.taskType === 'single'" label="任务内容" prop="subType">
        <el-select v-model="form.subType" placeholder="选择任务类型" style="width: 100%">
          <el-option value="search" label="定时查词" />
          <!-- 预留其他任务类型 -->
          <!-- <el-option value="ranking" label="定时排名分析" /> -->
        </el-select>
      </el-form-item>

      <!-- 选择客户 -->
      <el-form-item label="选择客户" prop="accountId">
        <el-select
          v-model="form.accountId"
          filterable
          placeholder="选择客户..."
          :loading="accountsLoading"
          style="width: 100%"
          @change="onAccountChange"
        >
          <el-option
            v-for="acc in accountOptions"
            :key="acc.id"
            :label="acc.companyName"
            :value="acc.id"
          >
            <span>{{ acc.companyName }}</span>
            <span style="float: right; color: #94a3b8; font-size: 12px">{{ acc.platforms || '' }}</span>
          </el-option>
        </el-select>
      </el-form-item>

      <!-- 覆盖平台（选择客户后自动选中该客户的平台） -->
      <el-form-item v-if="form.subType === 'search'" label="覆盖平台" prop="models">
        <div class="models-grid">
          <div
            v-for="opt in allModels"
            :key="opt.value"
            class="model-checkbox"
            :class="{ active: form.models.includes(opt.value), disabled: !isModelAvailable(opt.value) }"
            @click="toggleModel(opt.value)"
          >
            <PlatformIcon :name="opt.label" :size="28" />
            <span class="model-name">{{ opt.label }}</span>
            <span v-if="form.models.includes(opt.value)" class="model-check">✓</span>
          </div>
        </div>
        <div class="form-hint">点击选择/取消，可多选。选择客户后会自动勾选该客户的覆盖平台</div>
      </el-form-item>

      <!-- 执行频率 -->
      <el-form-item label="执行频率" prop="frequency">
        <el-radio-group v-model="form.frequency">
          <el-radio value="daily">每天</el-radio>
          <el-radio value="weekly">每周</el-radio>
          <el-radio value="monthly">每月</el-radio>
        </el-radio-group>
      </el-form-item>

      <!-- 执行时间 -->
      <el-form-item label="执行时间" prop="runTime">
        <div class="time-picker-row">
          <el-time-picker
            v-model="runTimeValue"
            format="HH:mm"
            value-format="HH:mm"
            placeholder="选择时间"
            @change="onTimeChange"
          />
          <span class="time-display" v-if="form.runTime">每天 {{ form.runTime }} 执行</span>
        </div>
      </el-form-item>

      <!-- 周几执行（仅每周时显示） -->
      <el-form-item v-if="form.frequency === 'weekly'" label="执行日期" prop="dayOfWeek">
        <el-select v-model="form.dayOfWeek" placeholder="选择星期">
          <el-option :value="0" label="周一" />
          <el-option :value="1" label="周二" />
          <el-option :value="2" label="周三" />
          <el-option :value="3" label="周四" />
          <el-option :value="4" label="周五" />
          <el-option :value="5" label="周六" />
          <el-option :value="6" label="周日" />
        </el-select>
      </el-form-item>

      <!-- 每月几号（仅每月时显示） -->
      <el-form-item v-if="form.frequency === 'monthly'" label="执行日期" prop="dayOfMonth">
        <el-input-number v-model="form.dayOfMonth" :min="1" :max="28" />
        <span class="form-hint ml-10">每月第几天执行（建议选 1-28 避免闰月问题）</span>
      </el-form-item>



      <!-- 启用状态 -->
      <el-form-item label="启用状态">
        <el-switch
          v-model="form.enabled"
          active-text="启用"
          inactive-text="禁用"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api/index.js'
import PlatformIcon from '@/components/PlatformIcon.vue'

const props = defineProps({
  visible: Boolean,
  task: Object  // 编辑时传入的任务对象
})
const emit = defineEmits(['update:visible', 'created', 'updated'])

const formRef = ref(null)
const saving = ref(false)
const accountsLoading = ref(false)
const accountOptions = ref([])

// 是否编辑模式
const isEdit = computed(() => !!props.task)

// 表单数据
const form = ref({
  taskType: 'single',     // single | batch
  subType: 'search',      // search | ranking (单一任务的子类型)
  accountId: null,
  models: [],             // 选中的模型列表
  frequency: 'daily',     // daily | weekly | monthly
  runTime: '02:00',
  dayOfWeek: 6,           // 周日
  dayOfMonth: 1,
  name: '',
  enabled: true
})

// 时间选择器绑定值
const runTimeValue = ref('')

// 表单验证规则
const rules = {
  accountId: [{ required: true, message: '请选择客户', trigger: 'change' }],
  models: [{ required: true, type: 'array', min: 1, message: '请至少选择一个查词模型', trigger: 'change' }],
  frequency: [{ required: true, message: '请选择执行频率', trigger: 'change' }],
  runTime: [{ required: true, message: '请设置执行时间', trigger: 'change' }]
}

// 全部可用的AI平台（固定6个，始终显示）
const allModels = [
  { label: 'ChatGPT', value: 'chatgpt' },
  { label: 'Google AIM', value: 'google_aim' },
  { label: 'Google AIO', value: 'google_aio' },
  { label: 'Perplexity', value: 'perplexity' },
  { label: 'Gemini', value: 'gemini' },
  { label: 'Bing', value: 'copilot' }
]

// 获取当前客户拥有的平台列表（用于自动选中）
const customerPlatforms = computed(() => {
  const selectedAcc = accountOptions.value.find(a => a.id === form.value.accountId)
  if (!selectedAcc) return []
  
  let platforms = selectedAcc.platforms || []
  if (typeof platforms === 'string') {
    platforms = platforms.split(',').map(p => p.trim()).filter(Boolean)
  }
  // 将平台名称映射到 value
  const platformValueMap = {
    'ChatGPT': 'chatgpt',
    'Google AIM': 'google_aim',
    'Perplexity': 'perplexity',
    'Gemini': 'gemini',
    'Claude': 'google_aio',
    'Bing': 'copilot',
    'Copilot': 'copilot'
  }
  return platforms.map(p => platformValueMap[p] || p.toLowerCase().replace(/\s+/g, '_')).filter(Boolean)
})

// 判断某个模型是否可用（客户拥有该平台时才可用）
function isModelAvailable(modelValue) {
  // 未选择客户时，所有模型都可用
  if (!form.value.accountId) return true
  // 选择客户后，只有客户拥有的平台才高亮显示（但仍可选择其他）
  return customerPlatforms.value.includes(modelValue)
}

// 可用的模型选项（保留兼容性，实际使用 allModels）
const availableModels = computed(() => allModels)

// 监听传入的 task 变化（编辑模式）
watch(() => props.task, (task) => {
  if (task && props.visible) {
    // 解析 models 字段
    let models = []
    if (typeof task.models === 'string') {
      try {
        models = JSON.parse(task.models)
      } catch {
        models = [task.models]
      }
    } else if (Array.isArray(task.models)) {
      models = task.models
    }
    
    form.value = {
      taskType: task.taskType || 'single',
      subType: 'search',
      accountId: task.accountId || task.account_id,
      models: models,
      frequency: task.frequency || 'daily',
      runTime: task.runTime || task.run_time || '02:00',
      dayOfWeek: task.dayOfWeek ?? 6,
      dayOfMonth: task.dayOfMonth ?? 1,
      name: task.name || '',
      enabled: task.enabled !== false && task.enabled !== 0
    }
    
    runTimeValue.value = form.value.runTime
    
    // 加载该客户信息
    if (form.value.accountId) {
      loadAccountDetail(form.value.accountId)
    }
  }
}, { immediate: true })

// 监听 visible 重置表单并加载客户列表
watch(() => props.visible, (val) => {
  if (val && !isEdit.value) {
    resetForm()
  }
  if (val) {
    // 每次打开弹窗都加载最新的客户列表
    loadAccounts()
  }
})

// 加载所有客户列表
async function loadAccounts() {
  accountsLoading.value = true
  try {
    const accounts = await api.listAccounts()
    accountOptions.value = (accounts || []).map(a => ({
      ...a,
      // 确保 platforms 字段可用 - 可能是数组或字符串
      platforms: a.platforms || a.coveredPlatforms || (Array.isArray(a.platforms) ? a.platforms : [])
    }))
  } catch (e) {
    console.error('加载客户列表失败:', e)
    ElMessage.error('加载客户列表失败')
  } finally {
    accountsLoading.value = false
  }
}

// 搜索客户（保留用于前端过滤）
function searchAccounts(query) {
  if (!query) {
    // 重新加载全部
    loadAccounts()
    return
  }
  const q = query.toLowerCase()
  // 在已加载的列表中过滤（实际由 el-select 的 filterable 处理）
}

// 加载单个客户详情
async function loadAccountDetail(accountId) {
  try {
    const accounts = await api.listAccounts()
    const acc = (accounts || []).find(a => a.id === accountId)
    if (acc) {
      // 如果选项列表中没有，添加进去
      if (!accountOptions.value.find(a => a.id === acc.id)) {
        accountOptions.value.push(acc)
      }
    }
  } catch (e) {
    console.error('加载客户详情失败:', e)
  }
}

// 客户选择变化 - 自动选中该客户的平台
function onAccountChange(accountId) {
  // 使用 nextTick 确保 DOM 更新后再处理
  setTimeout(() => {
    // 自动选中该客户拥有的平台
    if (customerPlatforms.value.length > 0) {
      form.value.models = [...customerPlatforms.value]
    } else {
      form.value.models = []
    }
  }, 0)
}

// 添加模型
function addModel(model) {
  if (!form.value.models.includes(model)) {
    form.value.models.push(model)
  }
}

// 移除模型
function removeModel(idx) {
  form.value.models.splice(idx, 1)
}

// 切换模型选中状态（用于 checkbox 样式）
function toggleModel(model) {
  const idx = form.value.models.indexOf(model)
  if (idx >= 0) {
    form.value.models.splice(idx, 1)
  } else {
    form.value.models.push(model)
  }
}

// 获取模型显示标签
function getModelLabel(model) {
  const opt = availableModels.value.find(o => o.value === model)
  return opt ? opt.label : model
}

// 时间变化
function onTimeChange(val) {
  form.value.runTime = val || '02:00'
}

// 重置表单
function resetForm() {
  form.value = {
    taskType: 'single',
    subType: 'search',
    accountId: null,
    models: [],
    frequency: 'daily',
    runTime: '02:00',
    dayOfWeek: 6,
    dayOfMonth: 1,
    enabled: true
  }
  runTimeValue.value = ''
  // 不清空 accountOptions，保持客户列表
}

// 提交表单
async function handleSubmit() {
  if (!formRef.value) return
  
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  // 批量任务暂不支持
  if (form.value.taskType === 'batch') {
    ElMessage.warning('批量任务功能暂不支持，请选择单一任务')
    return
  }

  saving.value = true
  try {
    const payload = {
      accountId: form.value.accountId,
      models: JSON.stringify(form.value.models),
      frequency: form.value.frequency,
      runTime: form.value.runTime,
      dayOfWeek: form.value.dayOfWeek,
      dayOfMonth: form.value.dayOfMonth,
      enabled: form.value.enabled ? 1 : 0
    }

    if (isEdit.value) {
      const result = await api.updateScheduledTask(props.task.id, payload)
      ElMessage.success('更新成功')
      emit('updated', result)
    } else {
      const result = await api.createScheduledTask(payload)
      ElMessage.success('创建成功')
      emit('created', result)
    }
  } catch (e) {
    console.error('保存失败:', e)
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.form-tip {
  margin-top: 8px;
}

.form-hint {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}

.ml-10 {
  margin-left: 10px;
}

/* 模型网格样式 */
.models-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.model-checkbox {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border: 2px solid #e4e7ed;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #fafafa;
}

.model-checkbox:hover {
  border-color: #409eff;
  background: #ecf5ff;
}

.model-checkbox.active {
  border-color: #409eff;
  background: #ecf5ff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.2);
}

/* 非客户平台时降低透明度（但仍可选择） */
.model-checkbox.disabled {
  opacity: 0.5;
}

.model-checkbox.disabled:hover {
  opacity: 0.7;
}

.model-name {
  font-size: 13px;
  font-weight: 500;
  color: #333;
  flex: 1;
}

.model-check {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 20px;
  height: 20px;
  background: #409eff;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}

.time-picker-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.time-display {
  font-size: 13px;
  color: #64748b;
}
</style>
