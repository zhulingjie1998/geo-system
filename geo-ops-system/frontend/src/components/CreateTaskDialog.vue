<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="(val) => $emit('update:visible', val)"
    :title="isEdit ? '编辑定时任务' : '新建定时任务'"
    width="780px"
    :close-on-click-modal="false"
    class="sched-form-dialog"
  >
    <!-- 自定义标题：图标 + 标题 + 副标题 -->
    <template #header>
      <div class="dlg-header">
        <div class="dlg-icon-wrap tcolor-bg-keyword">
          <el-icon class="tcolor-keyword" style="font-size: 20px"><Search /></el-icon>
        </div>
        <div class="dlg-titles">
          <div class="dlg-title">{{ isEdit ? '编辑定时任务' : '新建定时任务' }}</div>
          <div class="dlg-subtitle">{{ taskSubTitle }}</div>
        </div>
      </div>
    </template>

    <div class="form-body">
      <!-- ═══ ① 任务类型 ═══ -->
      <section class="sec sec-type">
        <div class="sec-title"><span class="sec-num">1</span><span>任务类型</span></div>

        <!-- 单一/批量 切换按钮 -->
        <div class="mode-toggle">
          <button type="button" class="mode-btn" :class="{ active: form.taskType === 'single' }" @click="!isEdit && (form.taskType = 'single')">
            <el-icon><Grid /></el-icon> 单一任务
          </button>
          <button type="button" class="mode-btn" :class="{ active: form.taskType === 'batch' }" @click="!isEdit && (form.taskType = 'batch')">
            <el-icon><CopyDocument /></el-icon> 批量任务
          </button>
        </div>

        <!-- 任务子类型网格卡片 -->
        <div class="type-grid">
          <button
            v-for="opt in subTypeOptions"
            :key="opt.value"
            type="button"
            class="type-tile"
            :class="[`tile-${opt.value}`, { active: form.taskType === 'single' ? form.subType === opt.value : form.batchSubTypes.includes(opt.value) }]"
            @click="form.taskType === 'single' ? (form.subType = opt.value) : toggleBatchType(opt.value)"
          >
            <el-icon style="font-size: 18px"><component :is="opt.icon" /></el-icon>
            <div class="tile-label">{{ opt.label }}</div>
            <div class="tile-desc">{{ opt.desc }}</div>
          </button>
        </div>

        <!-- 批量任务提示 -->
        <div v-if="form.taskType === 'batch'" class="form-hint">可多选，系统将按顺序依次执行各类型任务</div>

        <!-- 批量任务选中顺序显示 -->
        <div v-if="form.taskType === 'batch' && form.batchSubTypes.length > 0" class="batch-order">
          <span class="order-lbl">执行顺序：</span>
          <span v-for="(typeVal, idx) in form.batchSubTypes" :key="'order-' + typeVal" class="order-tag">
            <span class="order-num">{{ idx + 1 }}</span>
            {{ getSubTypeLabel(typeVal) }}
            <el-icon class="order-close" @click.stop="removeBatchType(typeVal)"><Close /></el-icon>
          </span>
        </div>
      </section>

      <!-- ═══ ② 客户与内容 ═══ -->
      <section class="sec">
        <div class="sec-title"><span class="sec-num">2</span><span>客户与内容</span></div>

        <!-- 客户选择 -->
        <div class="field">
          <label class="field-lbl"><span class="req-dot">●</span> 客户</label>
          <el-select
            v-model="form.accountId"
            filterable
            placeholder="选择客户..."
            :loading="accountsLoading"
            class="field-input"
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
        </div>

        <!-- 查词模型（仅查词任务显示） -->
        <div v-if="showModelSelect" class="field">
          <label class="field-lbl">
            <span class="req-dot">●</span> 查词模型
            <el-button type="primary" link size="small" class="reset-btn" @click="resetToCustomerPlatforms">
              <el-icon style="font-size: 11px"><RefreshRight /></el-icon> 重置为客户配置
            </el-button>
          </label>
          <div class="model-chips">
            <button
              v-for="opt in allModels"
              :key="opt.value"
              type="button"
              class="model-chip"
              :class="{ active: form.models.includes(opt.value) }"
              @click="toggleModel(opt.value)"
            >{{ opt.label }}</button>
          </div>
          <div class="field-hint">已自动选中该客户配置的 {{ customerPlatforms.length }} 个平台</div>
        </div>
      </section>

      <!-- ═══ ③ 执行频率 ═══ -->
      <section class="sec">
        <div class="sec-title">
          <span class="sec-num">3</span><span>执行频率</span>
          <div class="freq-preview" v-if="form.runTime">
            <el-icon style="font-size: 12px; color: #3b82f6"><Clock /></el-icon>
            <span>{{ frequencyText }} {{ form.runTime }}</span>
          </div>
        </div>

        <!-- 快捷预设 -->
        <div class="quick-presets">
          <span class="quick-lbl">快速预设</span>
          <button
            v-for="p in presets"
            :key="p.key"
            type="button"
            class="quick-chip"
            :class="{ active: isPresetActive(p) }"
            @click="applyPreset(p)"
          >{{ p.label }}</button>
        </div>

        <!-- 频率 + 时间 并排 -->
        <div class="freq-grid">
          <div class="field">
            <label class="field-lbl">频率</label>
            <el-radio-group v-model="form.frequency" size="default">
              <el-radio-button value="daily">每天</el-radio-button>
              <el-radio-button value="weekly">每周</el-radio-button>
              <el-radio-button value="monthly">每月</el-radio-button>
            </el-radio-group>
          </div>
          <div class="field">
            <label class="field-lbl">执行时间</label>
            <el-time-picker
              v-model="runTimeValue"
              format="HH:mm"
              value-format="HH:mm"
              placeholder="02:00"
              style="width: 140px"
              @change="onTimeChange"
            />
          </div>
        </div>

        <!-- 周几/月几号 -->
        <div v-if="form.frequency === 'weekly'" class="freq-extra">
          <el-select v-model="form.dayOfWeek" placeholder="选择星期" style="width: 140px">
            <el-option :value="0" label="周一" />
            <el-option :value="1" label="周二" />
            <el-option :value="2" label="周三" />
            <el-option :value="3" label="周四" />
            <el-option :value="4" label="周五" />
            <el-option :value="5" label="周六" />
            <el-option :value="6" label="周日" />
          </el-select>
        </div>
        <div v-if="form.frequency === 'monthly'" class="freq-extra">
          <el-input-number v-model="form.dayOfMonth" :min="1" :max="28" controls-position="right" size="default" />
          <span class="field-hint" style="margin-left: 8px">每月第几天（建议 1-28）</span>
        </div>
      </section>
    </div>

    <template #footer>
      <div class="dlg-footer">
        <el-button @click="$emit('update:visible', false)">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSubmit">
          {{ isEdit ? '更新任务' : '创建定时任务' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Grid, CopyDocument, RefreshRight, Clock, TrendCharts, Close } from '@element-plus/icons-vue'
import api from '@/api/index.js'

const props = defineProps({
  visible: Boolean,
  task: Object
})
const emit = defineEmits(['update:visible', 'created', 'updated'])

const formRef = ref(null)
const saving = ref(false)
const accountsLoading = ref(false)
const accountOptions = ref([])

const isEdit = computed(() => !!props.task)

// 表单数据
const form = ref({
  taskType: 'single',
  subType: 'search',
  batchSubTypes: [],
  accountId: null,
  models: [],
  frequency: 'daily',
  runTime: '02:00',
  dayOfWeek: 6,
  dayOfMonth: 1,
  name: '',
  enabled: true
})

// 任务子类型选项（2种，带 Element Plus 图标）
const subTypeOptions = [
  { value: 'search', label: '定时查词', icon: 'Search', desc: 'AI 多平台查词' },
  { value: 'ranking', label: '定时排名', icon: 'TrendCharts', desc: '品牌排名分析' }
]

// 执行频率选项
const frequencyOptions = [
  { value: 'daily', label: '每天' },
  { value: 'weekly', label: '每周' },
  { value: 'monthly', label: '每月' }
]

const frequencyText = computed(() => {
  const map = { daily: '每天', weekly: '每周', monthly: '每月' }
  return map[form.value.frequency] || '每天'
})

// 副标题文本
const taskSubTitle = computed(() => {
  if (form.value.taskType === 'batch') return '批量任务 · 多类型按顺序执行'
  const found = subTypeOptions.find(o => o.value === form.value.subType)
  return `${found?.label || '定时查词'} · ${found?.desc || 'AI 多平台查词'}`
})

// 是否显示模型选择（只有 search 类型需要）
const showModelSelect = computed(() => {
  if (form.value.taskType === 'single') return form.value.subType === 'search'
  if (form.value.taskType === 'batch') return form.value.batchSubTypes.includes('search')
  return false
})

// 快捷预设
const presets = [
  { key: 'daily-0200', label: '每天凌晨 02:00', freq: 'daily', time: '02:00' },
  { key: 'daily-0700', label: '每天早 07:00', freq: 'daily', time: '07:00' },
  { key: 'daily-1200', label: '每天午 12:00', freq: 'daily', time: '12:00' },
  { key: 'weekly-mon-0200', label: '每周一 02:00', freq: 'weekly', time: '02:00', dow: 0 },
  { key: 'weekly-sun-0200', label: '每周日 02:00', freq: 'weekly', time: '02:00', dow: 6 },
  { key: 'monthly-1-0200', label: '每月 1 号 02:00', freq: 'monthly', time: '02:00', dom: 1 }
]

function isPresetActive(p) {
  if (form.value.frequency !== p.freq || form.value.runTime !== p.time) return false
  if (p.freq === 'weekly' && form.value.dayOfWeek !== p.dow) return false
  if (p.freq === 'monthly' && form.value.dayOfMonth !== p.dom) return false
  return true
}

function applyPreset(p) {
  form.value.frequency = p.freq
  form.value.runTime = p.time
  runTimeValue.value = p.time
  if (p.dow !== undefined) form.value.dayOfWeek = p.dow
  if (p.dom !== undefined) form.value.dayOfMonth = p.dom
}

function resetToCustomerPlatforms() {
  if (customerPlatforms.value.length > 0) {
    form.value.models = [...customerPlatforms.value]
  }
}

const runTimeValue = ref('')

// 表单验证规则
const rules = computed(() => ({
  accountId: [{ required: true, message: '请选择客户', trigger: 'change' }],
  models: form.value.subType === 'search'
    ? [{ required: true, type: 'array', min: 1, message: '请至少选择一个查词平台', trigger: 'change' }]
    : [],
  frequency: [{ required: true, message: '请选择执行频率', trigger: 'change' }],
  runTime: [{ required: true, message: '请设置执行时间', trigger: 'change' }]
}))

// 全部可用的AI平台（6个固定平台）
const allModels = [
  { label: 'ChatGPT', value: 'chatgpt' },
  { label: 'Google AIO', value: 'google_aio' },
  { label: 'Google AIM', value: 'google_aim' },
  { label: 'Gemini', value: 'gemini' },
  { label: 'Perplexity', value: 'perplexity' },
  { label: 'Copilot', value: 'copilot' }
]

// 获取当前客户拥有的平台列表
const customerPlatforms = computed(() => {
  const selectedAcc = accountOptions.value.find(a => a.id === form.value.accountId)
  if (!selectedAcc) return []
  let platforms = selectedAcc.platforms || ''
  if (typeof platforms === 'string') {
    platforms = platforms.split(',').map(p => p.trim()).filter(Boolean)
  }
  // 映射到 value
  const nameMap = {
    'ChatGPT': 'chatgpt', 'Google AIO': 'google_aio', 'Google AIM': 'google_aim',
    'Gemini': 'gemini', 'Perplexity': 'perplexity', 'Copilot': 'copilot'
  }
  return platforms.map(p => nameMap[p] || p.toLowerCase()).filter(Boolean)
})

// 监听传入的 task 变化（编辑模式）
watch(() => props.task, (task) => {
  if (task && props.visible) {
    let models = []
    if (typeof task.models === 'string') {
      try { models = JSON.parse(task.models) } catch { models = [task.models] }
    } else if (Array.isArray(task.models)) {
      models = task.models
    }

    let batchSubTypes = []
    if (task.batchSubTypes) {
      try { batchSubTypes = typeof task.batchSubTypes === 'string' ? JSON.parse(task.batchSubTypes) : task.batchSubTypes } catch {}
    }

    form.value = {
      taskType: task.taskType || 'single',
      subType: task.subType || 'search',
      batchSubTypes: batchSubTypes,
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

    if (form.value.accountId) loadAccountDetail(form.value.accountId)
  }
}, { immediate: true })

// 监听 visible 重置表单并加载客户列表
watch(() => props.visible, (val) => {
  if (val && !isEdit.value) resetForm()
  if (val) loadAccounts()
})

async function loadAccounts() {
  accountsLoading.value = true
  try {
    const accounts = await api.listAccounts()
    accountOptions.value = (accounts || []).map(a => ({
      ...a,
      platforms: a.platforms || a.coveredPlatforms || ''
    }))
  } catch (e) {
    console.error('加载客户列表失败:', e)
    ElMessage.error('加载客户列表失败')
  } finally {
    accountsLoading.value = false
  }
}

async function loadAccountDetail(accountId) {
  try {
    const accounts = await api.listAccounts()
    const acc = (accounts || []).find(a => a.id === accountId)
    if (acc && !accountOptions.value.find(a => a.id === acc.id)) {
      accountOptions.value.push(acc)
    }
  } catch (e) {
    console.error('加载客户详情失败:', e)
  }
}

function onAccountChange(accountId) {
  setTimeout(() => {
    if (customerPlatforms.value.length > 0) {
      form.value.models = [...customerPlatforms.value]
    } else {
      form.value.models = []
    }
  }, 0)
}

function toggleModel(model) {
  const idx = form.value.models.indexOf(model)
  if (idx >= 0) form.value.models.splice(idx, 1)
  else form.value.models.push(model)
}

function toggleBatchType(typeValue) {
  const idx = form.value.batchSubTypes.indexOf(typeValue)
  if (idx >= 0) form.value.batchSubTypes.splice(idx, 1)
  else form.value.batchSubTypes.push(typeValue)
}

function removeBatchType(typeValue) {
  const idx = form.value.batchSubTypes.indexOf(typeValue)
  if (idx >= 0) form.value.batchSubTypes.splice(idx, 1)
}

function getSubTypeLabel(typeVal) {
  const found = subTypeOptions.find(o => o.value === typeVal)
  return found?.label || typeVal
}

function onTimeChange(val) {
  form.value.runTime = val || '02:00'
}

function resetForm() {
  form.value = {
    taskType: 'single',
    subType: 'search',
    batchSubTypes: [],
    accountId: null,
    models: [],
    frequency: 'daily',
    runTime: '02:00',
    dayOfWeek: 6,
    dayOfMonth: 1,
    enabled: true
  }
  runTimeValue.value = ''
}

async function handleSubmit() {
  if (!formRef.value) return
  try { await formRef.value.validate() } catch { return }

  if (form.value.taskType === 'batch') {
    if (!form.value.batchSubTypes || form.value.batchSubTypes.length === 0) {
      ElMessage.warning('请至少选择一种任务类型')
      return
    }
  }

  saving.value = true
  try {
    const payload = {
      taskType: form.value.taskType,
      subType: form.value.subType,
      batchSubTypes: JSON.stringify(form.value.batchSubTypes),
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
/* ═════════════════ 弹窗整体 ═════════════════ */
.sched-form-dialog :deep(.el-dialog__header) {
  padding: 16px 20px 0;
  border-bottom: none;
  margin-right: 0;
}
.sched-form-dialog :deep(.el-dialog__body) {
  padding: 8px 20px 0;
}
.sched-form-dialog :deep(.el-dialog__footer) {
  padding: 12px 20px;
  border-top: none;
}

/* ═══ 标题区 dlg-header ═══ */
.dlg-header {
  display: flex;
  align-items: center;
  gap: 10px;
}
.dlg-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  flex-shrink: 0;
}
/* 类型颜色 */
.tcolor-bg-keyword { background: #dbeafe; }
.tcolor-bg-ranking { background: #dcfce7; }
.tcolor-bg-citation { background: #fef3c7; }
.tcolor-bg-quote   { background: #f3e8ff; }

.tcolor-keyword { color: #2563eb; }
.tcolor-ranking { color: #16a34a; }
.tcolor-citation { color: #d97706; }
.tcolor-quote   { color: #7c3aed; }

.dlg-titles {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.dlg-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.3;
}
.dlg-subtitle {
  font-size: 13px;
  color: #9ca3af;
  line-height: 1.3;
}

/* ═══ 分区 sec ═══ */
.sec {
  padding: 14px 0;
  border-bottom: 1px solid #f3f4f6;
}
.sec:last-child {
  border-bottom: none;
  padding-bottom: 4px;
}
.sec-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}
.sec-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #409eff;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
}

/* ═══ 单一/批量 切换按钮 mode-toggle ═══ */
.mode-toggle {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.mode-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 16px;
  border: 1.5px solid #e5e7eb;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: #6b7280;
  background: #fff;
  transition: all 0.15s;
  user-select: none;
}
.mode-btn:hover {
  border-color: #93c5fd;
  color: #374151;
}
.mode-btn.active {
  border-color: #409eff;
  background: #ecf5ff;
  color: #409eff;
  font-weight: 500;
}

/* ═══ 任务类型网格 type-grid ═══ */
.type-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
.type-tile {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 8px 10px;
  border: 1.5px solid #e5e7eb;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  background: #fff;
  user-select: none;
}
.type-tile:hover {
  border-color: #93c5fd;
}
/* 各类型激活态颜色 */
.type-tile.tile-search.active {
  border-color: #3b82f6;
  background: #eff6ff;
  color: #2563eb;
}
.type-tile.tile-ranking.active {
  border-color: #22c55e;
  background: #f0fdf4;
  color: #16a34a;
}
.type-tile.tile-citation.active {
  border-color: #f59e0b;
  background: #fffbeb;
  color: #d97706;
}
.type-tile.tile-quote.active {
  border-color: #a855f7;
  background: #faf5ff;
  color: #7c3aed;
}

.tile-label {
  font-size: 13px;
  font-weight: 500;
  color: inherit;
}
.tile-desc {
  font-size: 11px;
  color: #9ca3af;
}

/* ═══ 字段 field ═══ */
.field {
  margin-bottom: 12px;
}
.field-lbl {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #374151;
  margin-bottom: 6px;
  font-weight: 500;
}
.req-dot {
  color: #ef4444;
  font-size: 10px;
}
.field-input {
  width: 100%;
}

/* ═══ 模型芯片 model-chips ═══ */
.model-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.model-chip {
  padding: 4px 14px;
  border: 1.5px solid #e5e7eb;
  border-radius: 16px;
  cursor: pointer;
  font-size: 13px;
  color: #6b7280;
  background: #fff;
  transition: all 0.15s;
  user-select: none;
}
.model-chip:hover {
  border-color: #93c5fd;
  color: #374151;
}
.model-chip.active {
  border-color: #409eff;
  background: #409eff;
  color: #fff;
  font-weight: 500;
}
.reset-btn {
  font-size: 12px;
  padding: 0;
  margin-left: auto;
}
.field-hint {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 6px;
}
.form-hint {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 8px;
}

/* ═══ 批量任务执行顺序显示 ═══ */
.batch-order {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  padding: 8px 10px;
  background: #f9fafb;
  border: 1px dashed #d1d5db;
  border-radius: 6px;
}
.order-lbl {
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
}
.order-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px 3px 4px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 4px;
  font-size: 12px;
  color: #2563eb;
  font-weight: 500;
}
.order-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #3b82f6;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
}
.order-close {
  cursor: pointer;
  font-size: 12px;
  color: #93a5b8;
  margin-left: 2px;
}
.order-close:hover { color: #ef4444; }

/* ═══ 执行频率区域 ═══ */
.freq-preview {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #6b7280;
}

.quick-presets {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
}
.quick-lbl {
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
  margin-right: 2px;
}
.quick-chip {
  padding: 4px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  color: #6b7280;
  background: #fafafa;
  transition: all 0.15s;
  user-select: none;
}
.quick-chip:hover {
  border-color: #93c5fd;
  color: #374151;
}
.quick-chip.active {
  border-color: #409eff;
  background: #ecf5ff;
  color: #409eff;
  font-weight: 500;
}

.freq-grid {
  display: flex;
  gap: 24px;
}
.freq-grid .field {
  flex: 1;
  margin-bottom: 0;
}
.freq-extra {
  margin-top: 10px;
}

/* ═══ 底部按钮 dlg-footer ═══ */
.dlg-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
