<template>
  <div class="sc-page">
    <!-- ===== 顶部工具栏 ===== -->
    <div class="sc-toolbar">
      <button
        v-if="isGenerating"
        type="button"
        class="sc-running-pill"
        @click="showTaskDialog = true"
      >
        <span class="sc-running-dot"></span>
        {{ runningTasks.length }} 个批次生成中 · 点击查看
      </button>
      <el-badge :value="runningTasks.length" :hidden="runningTasks.length === 0" class="sc-task-badge">
        <el-button plain @click="showTaskDialog = true">
          <el-icon><List /></el-icon>
          <span>生成任务</span>
        </el-button>
      </el-badge>
    </div>

    <!-- ===== 卡片滚动区 ===== -->
    <div class="sc-cards-scroll">
      <div class="sc-cards">

        <!-- ===== 第一行：目标客户 + 生成依据 ===== -->
        <div class="sc-row-2">
          <!-- 目标客户 -->
          <div class="sc-card">
            <div class="sc-card-head">
              <div class="sc-card-head-icon sc-icon-blue">
                <el-icon><User /></el-icon>
              </div>
              <div class="sc-card-head-text">
                <div class="sc-card-title">目标客户</div>
                <div class="sc-card-sub">选定后自动载入该客户知识库</div>
              </div>
            </div>
            <button
              type="button"
              class="sc-acct-picker"
              :class="{ empty: !selectedCustomer }"
              @click="openCustomerDialog"
            >
              <template v-if="selectedCustomer">
                <span class="sc-acct-name">{{ selectedCustomer.companyName || selectedCustomer.name }}</span>
                <span v-if="selectedCustomer.brandName" class="sc-acct-brand">品牌: {{ selectedCustomer.brandName }}</span>
                <span v-if="kbModules.length" class="sc-acct-kb">知识库 v{{ kbVersion }} · {{ kbModules.length }} 个模块</span>
              </template>
              <span v-else class="sc-acct-placeholder">点击选择客户</span>
              <el-icon class="sc-acct-arrow"><ArrowDown /></el-icon>
            </button>
            <!-- 知识库模块（选择客户后显示） -->
            <div v-if="selectedCustomer && kbModules.length" class="sc-kb-section">
              <div class="sc-kb-header">
                <span class="sc-kb-title">引用知识库模块</span>
                <button class="sc-kb-all-btn" @click.stop="toggleAllKbModules">
                  {{ isAllKbSelected ? '取消全选' : '全选' }}
                </button>
              </div>
              <div class="sc-kb-grid">
                <label
                  v-for="mod in kbModules"
                  :key="mod.id"
                  class="sc-kb-item"
                  :class="{ checked: selectedKbModuleIds.includes(mod.id) }"
                >
                  <input type="checkbox" :checked="selectedKbModuleIds.includes(mod.id)" @change="toggleKbModule(mod.id)" />
                  <span class="sc-kb-name">{{ mod.name }}</span>
                </label>
              </div>
            </div>
          </div>

          <!-- 生成依据 -->
          <div class="sc-card">
            <div class="sc-card-head">
              <div class="sc-card-head-icon sc-icon-purple">
                <el-icon><MagicStick /></el-icon>
              </div>
              <div class="sc-card-head-text">
                <div class="sc-card-title">生成依据</div>
                <div class="sc-card-sub">按指令库模板生成</div>
              </div>
              <el-radio-group v-model="instTab" size="small" class="sc-genmode-radio">
                <el-radio-button value="instruction">指令库</el-radio-button>
              </el-radio-group>
            </div>
            <button
              type="button"
              class="sc-tpl-empty"
              :class="{ 'has-value': selectedInstruction }"
              @click="openInstructionDialog"
            >
              <el-icon class="sc-tpl-icon"><Grid /></el-icon>
              <span>{{ selectedInstruction ? selectedInstruction.title : '点击选择写作指令' }}</span>
              <el-icon class="sc-tpl-arrow"><ArrowRight /></el-icon>
            </button>
          </div>
        </div>

        <!-- ===== 提示词 ===== -->
        <div class="bt-card">
          <div class="bt-card-head">
            <div class="bt-card-head-icon">
              <el-icon><Collection /></el-icon>
            </div>
            <div class="bt-card-head-text">
              <div class="bt-card-title">提示词</div>
              <div class="bt-card-sub">按上榜平台数分档挑选，或从客户词表中手动选</div>
            </div>
          </div>
          <!-- 未合并模式 -->
          <template v-if="!keywordMergeMode">
            <div v-if="selectedKeywords.length === 0" class="bt-summary empty" @click="openKeywordDialog">
              <el-icon class="bt-summary-icon"><Plus /></el-icon>
              <span class="bt-summary-empty-text">点击选择提示词</span>
              <el-icon class="bt-summary-arrow"><ArrowRight /></el-icon>
            </div>
            <div v-else class="bt-kw-list">
              <div
                v-for="kw in selectedKeywords"
                :key="kw.id"
                class="bt-kw-item"
              >
                <el-tag closable @close="removeKeyword(kw.id)" effect="plain">{{ kw.word }}</el-tag>
                <div class="bt-kw-count">
                  <input
                    type="number"
                    :value="kw.count || 1"
                    min="1"
                    max="99"
                    @change="updateKeywordCount(kw.id, $event.target.value)"
                  />
                  <span class="bt-kw-count-label">篇</span>
                </div>
              </div>
              <button class="bt-kw-add" @click="openKeywordDialog">
                <el-icon><Plus /></el-icon>
              </button>
            </div>
          </template>
          <!-- 合并模式 -->
          <div v-else class="bt-merge-mode">
            <div class="bt-merge-info">
              <span class="bt-merge-text">已选 {{ selectedKeywords.length }} 个提示词，合并成 {{ mergeTotalCount }} 篇</span>
              <span class="bt-merge-hint">，每篇都覆盖全部</span>
            </div>
            <div class="bt-merge-count">
              <span class="bt-merge-label">合成</span>
              <input type="number" v-model.number="mergeTotalCount" min="1" max="999" />
              <span class="bt-merge-label">篇</span>
            </div>
          </div>
          <!-- 合并开关 -->
          <div class="bt-actions-row">
            <label class="bt-merge-toggle">
              <input type="checkbox" v-model="keywordMergeMode" />
              <span>多个提示词合并生成</span>
            </label>
          </div>
        </div>

        <!-- ===== 重点补充 ===== -->
        <div class="sc-card sc-card-focus">
          <div class="sc-card-head">
            <div class="sc-card-head-icon sc-icon-red">
              <el-icon><Star /></el-icon>
            </div>
            <div class="sc-card-head-text">
              <div class="sc-card-title">重点补充 <span class="sc-priority-tag">最高优先级</span></div>
              <div class="sc-card-sub">本批每篇都会优先满足这里的要求（凌驾于类型蓝图与客户规则之上）</div>
            </div>
            <span class="sc-card-meta-count">{{ supplementText.length }} 字</span>
          </div>
          <el-input
            v-model="supplementText"
            type="textarea"
            :rows="3"
            placeholder="例如:&#10;- 本批主打「以旧换新」补贴政策，每篇都要自然带到&#10;- 重点突出 2026 新款的静音技术"
            class="sc-instr-input"
          />
        </div>

        <!-- ===== LLM 模型 ===== -->
        <div class="sc-card sc-card-llm">
          <div class="sc-card-head">
            <div class="sc-card-head-icon sc-icon-rose">
              <el-icon><Cpu /></el-icon>
            </div>
            <div class="sc-card-head-text">
              <div class="sc-card-title">LLM 模型</div>
              <div class="sc-card-sub">字数由所选指令控制</div>
            </div>
          </div>
          <el-radio-group v-model="selectedModel" class="sc-llm-radio">
            <el-radio-button
              v-for="m in modelOptions"
              :key="m.value"
              :value="m.value"
            >{{ m.label }}</el-radio-button>
          </el-radio-group>
        </div>

      </div>
    </div>

    <!-- ===== 底部操作栏 ===== -->
    <div class="sc-actionbar">
      <div class="sc-actionbar-info">
        <template v-if="isGenerating">
          <el-icon class="is-loading"><Loading /></el-icon>
          {{ generationProgress.statusText || '正在生成...' }}
          <span class="sc-progress-text">({{ generationProgress.current }}/{{ generationProgress.total }})</span>
        </template>
        <template v-else-if="!selectedCustomer">请先选择客户</template>
      </div>
      <div class="sc-actionbar-btns">
        <el-button :disabled="isGenerating" @click="handleReset">
          <el-icon><RefreshRight /></el-icon>
          <span>重置</span>
        </el-button>
        <el-button
          type="primary"
          size="large"
          class="sc-btn-gen"
          :disabled="!canGenerate || isGenerating"
          :loading="isGenerating"
          @click="handleGenerate"
        >
          <el-icon v-if="!isGenerating"><MagicStick /></el-icon>
          <span>{{ isGenerating ? '生成中...' : `生成 ${totalArticleCount} 篇批次` }}</span>
        </el-button>
      </div>
    </div>

    <!-- ===== 弹窗：客户选择 ===== -->
    <el-dialog
      v-model="showCustomerDialog"
      title="选择目标客户"
      width="560px"
      :close-on-click-modal="false"
      class="customer-dialog"
    >
      <el-input
        v-model="customerSearch"
        placeholder="搜索客户名称、品牌.."
        prefix-icon="Search"
        clearable
        class="customer-search"
      />
      <div class="customer-list">
        <div
          v-for="acc in filteredCustomers"
          :key="acc.id"
          class="customer-option"
          :class="{ selected: selectedCustomerId === acc.id }"
          @click="selectCustomer(acc)"
        >
          <div class="option-name">{{ acc.companyName || acc.name || '未命名客户' }}</div>
          <div class="option-meta">
            <span v-if="acc.brandName">品牌: {{ acc.brandName }}</span>
            <span v-if="acc.email">{{ acc.email }}</span>
          </div>
        </div>
        <div v-if="filteredCustomers.length === 0" class="no-data">无匹配客户</div>
      </div>
    </el-dialog>

    <!-- ===== 弹窗：指令库选择 ===== -->
    <el-dialog
      v-model="showInstructionDialog"
      title="选择写作指令"
      width="600px"
      :close-on-click-modal="false"
      class="instruction-dialog"
    >
      <div class="inst-dialog-tabs">
        <button
          :class="{ active: instructionScope === 'mine' }"
          @click="instructionScope = 'mine'"
        >我的指令</button>
        <button
          :class="{ active: instructionScope === 'global' }"
          @click="instructionScope = 'global'"
        >全局指令</button>
      </div>
      <div class="inst-list">
        <div
          v-for="inst in filteredInstructions"
          :key="inst.id"
          class="inst-option"
          :class="{ selected: selectedInstruction?.id === inst.id }"
          @click="selectInstruction(inst)"
        >
          <div class="inst-title">{{ inst.title }}</div>
          <div class="inst-desc">{{ inst.description || '暂无描述' }}</div>
          <div class="inst-meta">
            <el-tag v-if="inst.scope === 'global'" size="small" type="warning" effect="plain">全局</el-tag>
            <span class="inst-vars" v-if="inst.variables?.length">
              <el-icon><Document /></el-icon>
              {{ inst.variables.length }} 个变量
            </span>
          </div>
        </div>
        <div v-if="filteredInstructions.length === 0" class="no-data">暂无指令</div>
      </div>
    </el-dialog>

    <!-- ===== 弹窗：提示词/关键词选择 ===== -->
    <el-dialog
      v-model="showKeywordDialog"
      title="选择提示词"
      width="600px"
      :close-on-click-modal="false"
      class="keyword-dialog"
    >
      <div class="kw-dialog-toolbar">
        <el-input
          v-model="keywordSearchInput"
          placeholder="搜索提示词.."
          prefix-icon="Search"
          clearable
          class="kw-dialog-search"
        />
        <div class="kw-dialog-actions">
          <button @click="selectAllKeywords">全选</button>
          <button @click="clearAllKeywords">清空</button>
        </div>
      </div>
      <div class="kw-dialog-list">
        <label
          v-for="kw in filteredKeywordList"
          :key="kw.id"
          class="kw-dialog-item"
          :class="{ checked: isKeywordSelected(kw.id) }"
        >
          <input type="checkbox" :checked="isKeywordSelected(kw.id)" @change="toggleKeywordSelect(kw)" />
          <span class="kw-word">{{ kw.word }}</span>
          <el-tag v-if="kw.category" size="small" type="info" effect="plain">{{ kw.category }}</el-tag>
        </label>
        <div v-if="filteredKeywordList.length === 0" class="no-data">无匹配结果</div>
      </div>
    </el-dialog>

    <!-- ===== 弹窗：生成任务列表 ===== -->
    <el-dialog
      v-model="showTaskDialog"
      title="生成任务"
      width="640px"
      class="task-dialog"
    >
      <div class="task-list">
        <div v-if="runningTasks.length === 0 && completedTasks.length === 0" class="no-data">
          暂无生成任务
        </div>
        <div v-for="task in runningTasks" :key="task.id" class="task-item task-running">
          <div class="task-status">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>生成中</span>
          </div>
          <div class="task-info">
            <div class="task-title">{{ task.title }}</div>
            <div class="task-progress">
              <el-progress :percentage="task.progress" :stroke-width="6" />
            </div>
          </div>
        </div>
        <div v-for="task in completedTasks" :key="task.id" class="task-item" :class="`task-${task.status || 'completed'}`">
          <div class="task-status" :class="{ 'status-error': task.status === 'failed' }">
            <el-icon v-if="task.status === 'failed'"><CircleClose /></el-icon>
            <el-icon v-else><CircleCheck /></el-icon>
            <span>{{ task.status === 'failed' ? '失败' : '已完成' }}</span>
          </div>
          <div class="task-info">
            <div class="task-title">{{ task.title }}</div>
            <div v-if="task.error" class="task-error">{{ task.error }}</div>
            <div class="task-time">{{ task.completedAt }}</div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  User, MagicStick, Collection, Star, Cpu,
  List, Search, ArrowDown, ArrowRight, Plus, Grid,
  RefreshRight, Loading, CircleCheck, CircleClose, Document,
} from '@element-plus/icons-vue'
import api from '@/api'
import publishApi from '@/api/publish'

// ============================================================
// 状态定义
// ============================================================

/** 客户相关 */
const loadingCustomers = ref(false)
const customerList = ref([])
const selectedCustomerId = ref(null)
const showCustomerDialog = ref(false)
const customerSearch = ref('')

/** 客户信息 */
const selectedCustomer = computed(() =>
  customerList.value.find(a => a.id === selectedCustomerId.value) || null
)

/** 知识库模块 */
const kbModules = ref([])
const selectedKbModuleIds = ref([])
const kbVersion = ref('')

/** 生成依据 / 指令 */
const instTab = ref('content')
const showInstructionDialog = ref(false)
const instructionScope = ref('mine') // mine | global
const instructionList = ref([]) // 我的指令
const globalInstructionList = ref([]) // 全局指令
const selectedInstruction = ref(null)

/** 提示词/关键词 */
const showKeywordDialog = ref(false)
const keywordSearchInput = ref('')
const allKeywords = ref([]) // 客户词表
const selectedKeywords = ref([]) // [{id, word, count}]
const keywordMergeMode = ref(false)
const mergeTotalCount = ref(1)

/** 重点补充 */
const supplementText = ref('')

/** LLM 模型 */
const selectedModel = ref('')
const modelOptions = ref([
  { value: 'qwen-plus', label: '通义千问' },
])

/** 从系统配置加载模型设置 */
async function loadModelSettings() {
  try {
    const res = await fetch('/api/settings', { credentials: 'include' })
    if (!res.ok) return
    const data = await res.json()
    const modelName = data.qwen_model_name || 'qwen-plus'
    // 目前仅支持通义千问
    modelOptions.value = [{ value: modelName, label: '通义千问' }]
    selectedModel.value = modelName
  } catch (e) {
    console.warn('加载模型设置失败，使用默认值')
    selectedModel.value = 'qwen-plus'
  }
}

/** 生成任务 */
const showTaskDialog = ref(false)
const runningTasks = ref([])
const completedTasks = ref([])

// ============================================================
// 计算属性
// ============================================================

/** 过滤后的客户列表 */
const filteredCustomers = computed(() => {
  if (!customerSearch.value.trim()) return customerList.value
  const q = customerSearch.value.toLowerCase()
  return customerList.value.filter(acc => {
    const name = (acc.companyName || acc.name || '').toLowerCase()
    const brand = (acc.brandName || '').toLowerCase()
    return name.includes(q) || brand.includes(q)
  })
})

/** 是否全选知识库模块 */
const isAllKbSelected = computed(() =>
  kbModules.value.length > 0 && selectedKbModuleIds.value.length === kbModules.value.length
)

/** 过滤后的指令列表 */
const filteredInstructions = computed(() =>
  instructionScope.value === 'mine' ? instructionList.value : globalInstructionList.value
)

/** 过滤后的关键词列表 */
const filteredKeywordList = computed(() => {
  if (!keywordSearchInput.value.trim()) return allKeywords.value
  const q = keywordSearchInput.value.toLowerCase()
  return allKeywords.value.filter(kw => kw.word.toLowerCase().includes(q))
})

/** 判断关键词是否已选中 */
function isKeywordSelected(id) {
  return selectedKeywords.value.some(kw => kw.id === id)
}

/** 总篇数计算 */
const totalArticleCount = computed(() => {
  if (!selectedKeywords.value.length) return 0
  if (keywordMergeMode.value) {
    return mergeTotalCount.value
  }
  return selectedKeywords.value.reduce((sum, kw) => sum + (kw.count || 1), 0)
})

/** 是否可以开始生成 */
const canGenerate = computed(() => (
  selectedCustomerId.value &&
  selectedKeywords.value.length > 0 &&
  selectedModel.value
))

// ============================================================
// 客户相关方法
// ============================================================

/** 加载客户列表 */
async function loadCustomers() {
  loadingCustomers.value = true
  try {
    const accounts = await api.listAccounts()
    customerList.value = Array.isArray(accounts) ? accounts : []
  } catch (e) {
    console.error('加载客户列表失败', e)
    customerList.value = []
  } finally {
    loadingCustomers.value = false
  }
}

/** 打开客户选择弹窗 */
function openCustomerDialog() {
  showCustomerDialog.value = true
  customerSearch.value = ''
}

/** 选择客户 */
function selectCustomer(acc) {
  selectedCustomerId.value = acc.id
  showCustomerDialog.value = false
  // 重置关联数据
  selectedKbModuleIds.value = []
  selectedKeywords.value = []
  selectedInstruction.value = null
  // 加载客户关联数据
  loadCustomerData(acc.id)
}

/** 从 prompt 文本中提取 {变量} */
function extractVariables(prompt) {
  if (!prompt) return []
  const matches = prompt.match(/\{[^}]+\}/g) || []
  return [...new Set(matches)]
}

/** 加载客户关联数据 */
async function loadCustomerData(customerId) {
  try {
    // 1. 加载知识库模块（从真实 KB API）
    try {
      const kbRes = await publishApi.kbCurrent(customerId, true)
      const modules = kbRes?.item?.modules || kbRes?.modules || []
      kbModules.value = modules.map(m => ({ id: m.key || m.id, name: m.title || m.name }))
      kbVersion.value = kbRes?.item?.version || kbRes?.version || ''
    } catch (e) {
      console.warn('加载知识库失败', e)
      kbModules.value = []
      kbVersion.value = ''
    }
    // 默认全选
    selectedKbModuleIds.value = kbModules.value.map(m => m.id)

    // 2. 加载客户提示词/关键词（从真实 API）
    try {
      const kwRes = await api.getAccountKeywords(customerId)
      const kwList = Array.isArray(kwRes) ? kwRes : (kwRes?.items || kwRes?.data || [])
      allKeywords.value = kwList.map(k => ({
        id: k.id,
        word: k.coreIntentWord || k.intentPrompt || k.word || '',
        category: k.intentCategory || k.category || '',
      }))
    } catch (e) {
      console.warn('加载关键词失败', e)
      allKeywords.value = []
    }

    // 3. 加载指令列表（从 localStorage 指令库）
    try {
      const raw = localStorage.getItem('geo_instruction_library')
      const allInstructions = raw ? JSON.parse(raw) : []
      // 映射字段：localStorage 中用 name，模板用 title
      const mapInst = (i) => ({
        ...i,
        id: i.id,
        title: i.name || i.title || '',
        description: i.description || '',
        scope: i.scope || 'mine',
        variables: i.variables || extractVariables(i.prompt),
        prompt: i.prompt || '',
        minWords: i.minWords || 800,
        maxWords: i.maxWords || 1500,
        model: i.model || '',
      })
      instructionList.value = allInstructions.filter(i => i.scope !== 'global').map(mapInst)
      globalInstructionList.value = allInstructions.filter(i => i.scope === 'global').map(mapInst)
    } catch (e) {
      console.warn('加载指令库失败', e)
      instructionList.value = []
      globalInstructionList.value = []
    }
  } catch (e) {
    console.error('加载客户数据失败', e)
    ElMessage.warning('加载数据失败')
  }
}

// ============================================================
// 知识库模块操作
// ============================================================

function toggleKbModule(id) {
  const idx = selectedKbModuleIds.value.indexOf(id)
  if (idx >= 0) {
    selectedKbModuleIds.value.splice(idx, 1)
  } else {
    selectedKbModuleIds.value.push(id)
  }
}

function toggleAllKbModules() {
  if (isAllKbSelected.value) {
    selectedKbModuleIds.value = []
  } else {
    selectedKbModuleIds.value = kbModules.value.map(m => m.id)
  }
}

// ============================================================
// 指令相关方法
// ============================================================

function openInstructionDialog() {
  showInstructionDialog.value = true
}

function selectInstruction(inst) {
  selectedInstruction.value = inst
  showInstructionDialog.value = false
}

// ============================================================
// 提示词相关方法
// ============================================================

function openKeywordDialog() {
  showKeywordDialog.value = true
  keywordSearchInput.value = ''
}

function toggleKeywordSelect(kw) {
  const idx = selectedKeywords.value.findIndex(k => k.id === kw.id)
  if (idx >= 0) {
    selectedKeywords.value.splice(idx, 1)
  } else {
    selectedKeywords.value.push({ id: kw.id, word: kw.word, count: 1 })
  }
}

function removeKeyword(id) {
  const idx = selectedKeywords.value.findIndex(k => k.id === id)
  if (idx >= 0) selectedKeywords.value.splice(idx, 1)
}

function updateKeywordCount(id, val) {
  const kw = selectedKeywords.value.find(k => k.id === id)
  if (kw) kw.count = Math.max(1, Math.min(99, parseInt(val) || 1))
}

function selectAllKeywords() {
  const existingIds = selectedKeywords.value.map(k => k.id)
  filteredKeywordList.value.forEach(kw => {
    if (!existingIds.includes(kw.id)) {
      selectedKeywords.value.push({ id: kw.id, word: kw.word, count: 1 })
    }
  })
}

function clearAllKeywords() {
  selectedKeywords.value = []
}

/** 重置所有选项 */
function handleReset() {
  // 如果正在生成，确认是否中断
  if (isGenerating.value) {
    ElMessageBox.confirm('正在生成中，确定要重置吗？', '提示', {
      confirmButtonText: '确定重置',
      cancelButtonText: '继续生成',
      type: 'warning',
    }).then(() => {
      isGenerating.value = false
      doReset()
    }).catch(() => {})
    return
  }
  doReset()
}

function doReset() {
  selectedCustomerId.value = null
  selectedKbModuleIds.value = []
  selectedKeywords.value = []
  selectedInstruction.value = null
  supplementText.value = ''
  keywordMergeMode.value = false
  mergeTotalCount.value = 1
  kbModules.value = []
  runningTasks.value = []
  completedTasks.value = []
  isGenerating.value = false
  generationProgress.value = { current: 0, total: 0, statusText: '' }
  ElMessage.info('已重置所有选项')
}

// ============================================================
// 生文状态
// ============================================================
const isGenerating = ref(false)
const generationProgress = ref({ current: 0, total: 0, statusText: '' })

// ============================================================
// 生成操作 — 完整四步流程
// ============================================================

/**
 * Step 1: 根据客户知识库和关键词，生成主题列表
 * 每个主题要求描述方向不同（角度差异化）
 */
async function generateTopics(keywords, kbContext, count) {
  // 构建知识库上下文摘要
  const kbSummary = kbModules.value
    .filter(m => selectedKbModuleIds.value.includes(m.id))
    .map(m => m.name)
    .join('、') || '全部知识库'

  const prompt = `你是一个专业的 SEO 内容策划师。请根据以下信息生成 ${count} 个文章主题。

【客户】${selectedCustomer.value?.companyName || '未知客户'}
【品牌】${selectedCustomer.value?.brandName || ''}
【行业领域】${kbSummary}
【关键词列表】${keywords.map(k => k.word).join('、')}

要求：
1. 每个主题必须围绕上述关键词，但描述角度/方向必须不同
2. 角度示例：产品评测、技术解析、应用案例、行业趋势、选购指南、对比分析、问题解答等
3. 主题要具体，能直接用于指导文章写作
4. 返回 JSON 数组格式：[{"keyword": "关键词", "title": "主题标题", "angle": "写作角度/方向描述", "targetAudience": "目标读者"}]

直接返回 JSON，不要其他内容。`

  try {
    // 调用后端主题生成接口
    const res = await publishApi.cntGenerateTopics({
      account_id: selectedCustomerId.value,
      keywords: keywords.map(k => ({ id: k.id, word: k.word })),
      kb_modules: selectedKbModuleIds.value,
      count,
      prompt,
    })
    return res.topics || res || []
  } catch (e) {
    console.warn('主题生成 API 调用失败，使用本地模拟', e)
    // Fallback: 本地模拟生成主题（角度差异化）
    const angles = [
      '产品深度评测', '技术原理解析', '实际应用案例',
      '行业趋势洞察', '选购指南', '竞品对比分析',
      '常见问题解答', '新手入门指南', '维护保养技巧', '市场前景分析'
    ]
    const topics = []
    let angleIdx = 0
    for (const kw of keywords) {
      const cnt = kw.count || 1
      for (let i = 0; i < cnt; i++) {
        if (topics.length >= count) break
        const angle = angles[(angleIdx + i) % angles.length]
        topics.push({
          keyword: kw.word,
          title: `${kw.word}：${angle}`,
          angle,
          targetAudience: '潜在采购决策者',
          _keywordId: kw.id,
        })
      }
      if (topics.length >= count) break
      angleIdx += 2
    }
    return topics.slice(0, count)
  }
}

/**
 * Step 2: 将设置项替换到指令模板的变量中
 * 变量来源：品牌、生文变量、提示词、重点补充、主题
 */
function replaceTemplateVariables(templateContent, topic, extraVars = {}) {
  let result = templateContent

  // 标准变量替换映射
  const varMap = {
    // 客户/品牌信息
    '{公司名}': selectedCustomer.value?.companyName || '',
    '{品牌名}': selectedCustomer.value?.brandName || '',
    '{品牌}': selectedCustomer.value?.brandName || '',
    '{客户名}': selectedCustomer.value?.companyName || '',
    '{行业}': selectedCustomer.value?.industry || '',
    '{网站}': selectedCustomer.value?.website || '',
    '{邮箱}': selectedCustomer.value?.email || '',

    // 主题/关键词
    '{主关键词}': topic.keyword || '',
    '{关键词}': topic.keyword || '',
    '{主题标题}': topic.title || '',
    '{写作角度}': topic.angle || '',
    '{目标读者}': topic.targetAudience || '',
    '{核心词}': topic.keyword || '',

    // 提示词（合并或首个）
    '{提示词}': keywordMergeMode.value
      ? selectedKeywords.value.map(k => k.word).join('；')
      : (selectedKeywords.value[0]?.word || ''),
    '{所有提示词}': selectedKeywords.value.map(k => k.word).join('；'),

    // 重点补充
    '{重点补充}': supplementText.value,
    '{优先要求}': supplementText.value,
    '{特殊要求}': supplementText.value,

    // 知识库上下文
    '{知识库模块}': kbModules.value
      .filter(m => selectedKbModuleIds.value.includes(m.id))
      .map(m => m.name).join('、'),
    '{KB版本}': kbVersion.value || '',

    // 模型/字数
    '{模型}': modelOptions.value.find(m => m.value === selectedModel.value)?.label || '',
    '{字数范围}': '800~1500',

    ...extraVars,
  }

  // 执行替换（按 key 长度降序，避免短 key 误匹配长 key 子串）
  const sortedKeys = Object.keys(varMap).sort((a, b) => b.length - a.length)
  for (const key of sortedKeys) {
    result = result.replaceAll(key, varMap[key])
  }

  // 处理未替换的变量（标记为空）
  result = result.replace(/\{[^{}]+\}/g, '[待填充]')

  return result
}

/**
 * Step 3 & 4: 创建任务队列并执行生成
 * 每个主题 → 替换变量 → 形成任务 → 加入队列 → 同步至任务列表
 */
async function handleGenerate() {
  // 前置校验
  if (!canGenerate.value) {
    if (!selectedCustomerId.value) ElMessage.warning('请先选择客户')
    else if (!selectedKeywords.value.length) ElMessage.warning('请选择至少一个提示词')
    else if (!selectedInstruction.value) ElMessage.warning('请选择写作指令/内容类型')
    else if (!selectedModel.value) ElMessage.warning('请选择 LLM 模型')
    return
  }

  isGenerating.value = true
  const totalCount = totalArticleCount.value

  try {
    // ═══ Step 1: 生成主题 ═══
    generationProgress.value = { current: 0, total: totalCount, statusText: '正在生成主题...' }

    const topics = await generateTopics(selectedKeywords.value, null, totalCount)
    console.log('[生文] 生成主题数:', topics.length, topics)

    if (topics.length === 0) {
      ElMessage.error('未能生成任何主题，请检查关键词和知识库配置')
      isGenerating.value = false
      return
    }

    // ═══ Step 2: 变量替换 + Step 3: 构建任务队列 ═══
    generationProgress.value = { current: 0, total: topics.length, statusText: '正在准备生成任务...' }

    const taskQueue = []
    for (let i = 0; i < topics.length; i++) {
      const topic = topics[i]

      // 替换指令模板中的变量
      const filledInstruction = replaceTemplateVariables(
        selectedInstruction.value.prompt || selectedInstruction.value.content || selectedInstruction.value.template || `请根据以下主题撰写一篇高质量文章：\n\n主题：{主题标题}\n角度：{写作角度}\n\n要求：\n- 内容专业且易于理解\n- 自然融入关键词 {主关键词}\n- 字数控制在 800~1500 字`,
        topic,
        { '{序号}': String(i + 1), '{总篇数}': String(topics.length) }
      )

      const task = {
        uuid: `gen_${Date.now()}_${i}`,
        account_id: selectedCustomerId.value,
        account_name: selectedCustomer.value?.companyName || '',
        keyword_id: topic._keywordId,
        keyword: topic.keyword,
        topic_title: topic.title,
        topic_angle: topic.angle,
        instruction_id: selectedInstruction.value.id,
        instruction_title: selectedInstruction.value.title,
        filled_instruction: filledInstruction,
        model: selectedModel.value,
        supplement: supplementText.value,
        keywords_selected: selectedKeywords.value.map(k => ({ id: k.id, word: k.word, count: k.count || 1 })),
        kb_module_ids: [...selectedKbModuleIds.value],
        merge_mode: keywordMergeMode.value,
        status: 'pending',     // pending → generating → success | failed
        progress: 0,
        created_at: new Date().toISOString(),
        error: null,
        article_id: null,     // 生成后的文章 ID
        article_title: null,
      }

      taskQueue.push(task)

      // 加入运行中任务列表（UI 即时显示）
      runningTasks.value.push({
        id: task.uuid,
        title: task.topic_title,
        progress: 0,
        status: 'running',
      })
    }

    console.log('[生文] 任务队列已构建:', taskQueue.length, '个任务')
    ElMessage.success(`已创建 ${taskQueue.length} 个生成任务，开始执行...`)

    // ═══ Step 4: 逐个执行生成 + 同步任务状态 ═══
    let successCount = 0
    let failCount = 0

    for (let i = 0; i < taskQueue.length; i++) {
      const task = taskQueue[i]
      generationProgress.value = {
        current: i + 1,
        total: taskQueue.length,
        statusText: `正在生成 (${i + 1}/${taskQueue.length}): ${task.topic_title}`,
      }

      // 更新 UI 进度
      const uiTask = runningTasks.value.find(t => t.id === task.uuid)
      if (uiTask) uiTask.progress = 5

      try {
        // 调用后端生成接口
        const genResult = await publishApi.cntGenerate({
          account_id: task.account_id,
          instruction: task.filled_instruction,
          model: task.model,
          keyword: task.keyword,
          topic_title: task.topic_title,
          topic_angle: task.topic_angle,
          supplement: task.supplement,
          kb_module_ids: task.kb_module_ids,
          metadata: {
            task_uuid: task.uuid,
            instruction_id: task.instruction_id,
            source: 'ai-write-page',
          },
        })

        // 更新任务状态为成功
        task.status = 'success'
        task.progress = 100
        task.article_id = genResult.article_id || genResult.id || null
        task.article_title = genResult.title || task.topic_title

        if (uiTask) uiTask.progress = 100
        successCount++

        // 从 running 移到 completed
        setTimeout(() => {
          runningTasks.value = runningTasks.value.filter(t => t.id !== task.uuid)
          completedTasks.value.unshift({
            id: task.uuid,
            title: task.topic_title,
            progress: 100,
            status: 'completed',
            completedAt: new Date().toLocaleString(),
            articleId: task.article_id,
          })
          // 保持 badge 计数
          showTaskDialog.value = false
        }, 500)

      } catch (genErr) {
        console.error(`[生文] 任务 ${task.uuid} 失败:`, genErr)
        task.status = 'failed'
        task.error = genErr.message || '生成失败'
        failCount++

        // 标记 UI 任务为失败
        if (uiTask) {
          uiTask.status = 'failed'
          uiTask.error = task.error
        }
        setTimeout(() => {
          runningTasks.value = runningTasks.value.filter(t => t.id !== task.uuid)
          completedTasks.value.unshift({
            id: task.uuid,
            title: task.topic_title,
            progress: 0,
            status: 'failed',
            completedAt: new Date().toLocaleString(),
            error: task.error,
          })
        }, 300)
      }
    }

    // 全部完成
    generationProgress.value = {
      current: taskQueue.length,
      total: taskQueue.length,
      statusText: `完成！成功 ${successCount}，失败 ${failCount}`,
    }

    ElMessage.success(`生成完成！成功 ${successCount} 篇${failCount > 0 ? `，失败 ${failCount} 篇` : ''}`)

    // 自动打开任务列表弹窗
    if (taskQueue.length > 0) {
      showTaskDialog.value = true
    }

  } catch (err) {
    console.error('[生文] 流程异常:', err)
    ElMessage.error('生文流程出错: ' + (err.message || '未知错误'))
  } finally {
    isGenerating.value = false
  }
}

// ============================================================
// 生命周期
// ============================================================

onMounted(() => {
  loadCustomers()
  loadModelSettings()
})
</script>

<style scoped>
/* ============================================================
   AI 智能生文页面 - 参考设计重构
   ============================================================ */

.sc-page {
  min-height: calc(100vh - var(--header-height, 60px));
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
  position: relative;
}

/* ===== 顶部工具栏 ===== */
.sc-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 24px;
  background: transparent;
  position: sticky;
  top: 0;
  z-index: 10;
}
.sc-running-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 13px;
  color: #3370ff;
  background: #ecf3ff;
  border: 1px solid #d4e3ff;
  cursor: pointer;
  transition: all .2s;
}
.sc-running-pill:hover { background: #e0edff; }
.sc-running-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #3370ff;
  animation: sc-pulse 1.5s ease-in-out infinite;
}
@keyframes sc-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: .5; transform: scale(1.3); }
}
.sc-task-badge :deep(.el-badge__content) { font-size: 11px; }

/* ===== 卡片滚动区 ===== */
.sc-cards-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 20px 0 100px;
}
.sc-cards {
  max-width: 920px;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ===== 两列行 ===== */
.sc-row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

/* ===== 通用卡片 ===== */
.sc-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
  overflow: hidden;
  transition: box-shadow .25s;
}
.sc-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,.08); }

.sc-card-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px 12px;
}
.sc-card-head-icon {
  width: 36px; height: 36px;
  border-radius: 9px;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; flex-shrink: 0;
}
.sc-icon-blue   { background: #ecf3ff; color: #3370ff; }
.sc-icon-purple { background: #f3f0ff; color: #7b61ff; }
.sc-icon-red    { background: #fef0ef; color: #f56c6c; }
.sc-icon-rose   { background: #fef0f5; color: #eb6db8; }
.sc-card-head-text { flex: 1; min-width: 0; }
.sc-card-title {
  font-size: 15px; font-weight: 600; color: #1a1a2e;
  display: flex; align-items: center; gap: 8px;
}
.sc-card-sub {
  font-size: 12px; color: #909399; margin-top: 2px;
  line-height: 1.4;
}
.sc-card-meta-count {
  font-size: 12px; color: #c0c4cc; white-space: nowrap;
  margin-left: auto;
}

/* ===== 客户选择器 ===== */
.sc-acct-picker {
  display: flex; align-items: center; gap: 8px;
  width: 100%;
  padding: 14px 20px;
  border: none; border-top: 1px dashed #e8ecf0;
  background: none;
  cursor: pointer;
  transition: all .2s;
  font-size: 14px;
  text-align: left;
}
.sc-acct-picker:hover { background: #f8fbff; }
.sc-acct-picker.empty { color: #c0c4cc; }
.sc-acct-name { font-size: 15px; font-weight: 600; color: #1a1a2e; }
.sc-acct-brand, .sc-acct-kb {
  font-size: 12px; color: #909399;
  background: #f0f2f5; padding: 2px 8px; border-radius: 4px;
}
.sc-acct-placeholder { color: #c0c4cc; font-size: 14px; }
.sc-acct-arrow { margin-left: auto; color: #c0c4cc; font-size: 14px; }

/* ===== 知识库模块 ===== */
.sc-kb-section {
  padding: 14px 20px 16px;
  border-top: 1px solid #f0f2f5;
}
.sc-kb-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 10px;
}
.sc-kb-title { font-size: 13px; font-weight: 500; color: #606266; }
.sc-kb-all-btn {
  font-size: 12px; color: #3370ff; background: none; border: none;
  cursor: pointer; padding: 4px 8px; border-radius: 4px;
}
.sc-kb-all-btn:hover { background: #ecf3ff; }
.sc-kb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 8px;
}
.sc-kb-item {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 12px;
  border: 1px solid #ebeef5; border-radius: 8px;
  cursor: pointer; transition: all .2s;
  font-size: 13px; color: #606266;
}
.sc-kb-item:hover { border-color: #c6e2ff; background: #f5f9ff; }
.sc-kb-item.checked { border-color: #3370ff; background: #ecf5ff; color: #3370ff; }
.sc-kb-item input[type="checkbox"] { accent-color: #3370ff; cursor: pointer; }
.sc-kb-name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* ===== 生成依据 - 指令选择 ===== */
.sc-genmode-radio { margin-left: auto; }
.sc-tpl-empty {
  display: flex; align-items: center; gap: 10px;
  width: 100%;
  padding: 16px 20px;
  border: none; border-top: 1px dashed #e8ecf0;
  background: none;
  cursor: pointer;
  transition: all .2s;
  font-size: 14px; color: #606266;
  text-align: left;
}
.sc-tpl-empty:hover { background: #faf8ff; }
.sc-tpl-empty.has-value { color: #1a1a2e; font-weight: 500; }
.sc-tpl-icon { font-size: 20px; color: #7b61ff; }
.sc-tpl-arrow { margin-left: auto; color: #c0c4cc; }

/* ===== 提示词卡片 (bt-card) ===== */
.bt-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
  overflow: hidden;
  transition: box-shadow .25s;
}
.bt-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,.08); }
.bt-card-head {
  display: flex; align-items: center; gap: 12px;
  padding: 16px 20px 12px;
}
.bt-card-head-icon {
  width: 36px; height: 36px; border-radius: 9px;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; flex-shrink: 0;
  background: #e8faf7; color: #00bfa5;
}
.bt-card-head-text { flex: 1; }
.bt-card-title { font-size: 15px; font-weight: 600; color: #1a1a2e; }
.bt-card-sub { font-size: 12px; color: #909399; margin-top: 2px; line-height: 1.4; }

.bt-summary {
  display: flex; align-items: center; gap: 10px;
  width: 100%;
  padding: 16px 20px;
  border: none; border-top: 1px dashed #e8ecf0;
  background: none;
  cursor: pointer;
  transition: all .2s;
  font-size: 14px; color: #606266;
  text-align: left;
}
.bt-summary:hover { background: #f0fdfa; }
.bt-summary.empty { color: #c0c4cc; justify-content: center; }
.bt-summary-icon { font-size: 16px; color: #00bfa5; }
.bt-summary-empty-text { color: #c0c4cc; }
.bt-summary-arrow { margin-left: auto; color: #c0c4cc; }

.bt-kw-list {
  display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
  padding: 14px 20px;
}
.bt-kw-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 12px 6px 6px;
  background: #f8fbff; border: 1px solid #d9e8fc; border-radius: 8px;
}
.bt-kw-count { display: flex; align-items: center; gap: 2px; }
.bt-kw-count input {
  width: 44px; height: 28px; text-align: center;
  border: 1px solid #dcdfe6; border-radius: 4px;
  font-size: 13px; outline: none; color: #3370ff; font-weight: 500;
}
.bt-kw-count input:focus { border-color: #3370ff; }
.bt-kw-count-label { font-size: 12px; color: #909399; }
.bt-kw-add {
  width: 34px; height: 34px;
  border: 2px dashed #dcdfe6; border-radius: 8px;
  background: none; color: #909399; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; transition: all .2s;
}
.bt-kw-add:hover { border-color: #00bfa5; color: #00bfa5; }

.bt-merge-mode {
  display: flex; align-items: center; gap: 16px;
  padding: 14px 20px;
  background: linear-gradient(135deg, #f0fdfa 0%, #ecfeff 100%);
  border-top: 1px solid #99f6e4;
}
.bt-merge-info { font-size: 14px; color: #00bfa5; font-weight: 500; }
.bt-merge-hint { color: #99f6e4; font-weight: 400; }
.bt-merge-count { display: flex; align-items: center; gap: 4px; margin-left: auto; }
.bt-merge-count input {
  width: 64px; height: 32px; text-align: center;
  border: 1px solid #99f6e4; border-radius: 6px;
  font-size: 15px; outline: none; color: #00bfa5; font-weight: 600;
}
.bt-merge-count input:focus { border-color: #00bfa5; }
.bt-merge-label { font-size: 13px; color: #666; }
.bt-actions-row { padding: 0 20px 14px; display: flex; justify-content: flex-end; }
.bt-merge-toggle {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; color: #606266; cursor: pointer;
}
.bt-merge-toggle input[type="checkbox"] { accent-color: #00bfa5; width: 16px; height: 16px; cursor: pointer; }

/* ===== 重点补充 ===== */
.sc-card-focus .sc-instr-input {
  padding: 0 20px 16px;
}
.sc-card-focus .sc-instr-input :deep(.el-textarea__inner) {
  font-size: 14px; line-height: 1.65; resize: vertical;
  box-shadow: none; border: 1px solid #ebeef5; border-radius: 8px;
}
.sc-priority-tag {
  font-size: 11px; font-weight: 500;
  color: #f56c6c; background: #fef0f0;
  padding: 2px 8px; border-radius: 10px;
}

/* ===== LLM 模型 ===== */
.sc-card-llm .sc-llm-radio {
  padding: 0 20px 16px;
}

/* ===== 底部操作栏 ===== */
.sc-actionbar {
  position: fixed; bottom: 0; left: 220px; right: 0;
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 24px;
  background: rgba(255,255,255,.95); backdrop-filter: blur(12px);
  border-top: 1px solid #e8ecf0; z-index: 100;
  box-shadow: 0 -4px 20px rgba(0,0,0,.06);
}
.sc-actionbar-info {
  font-size: 13px; color: #e6a23c;
  display: flex; align-items: center; gap: 6px;
}
.sc-progress-text { color: #909399; font-size: 12px; }
.sc-actionbar-btns { display: flex; gap: 12px; }
.sc-btn-gen {
  background: linear-gradient(135deg, #3370ff 0%, #06b6d4 100%) !important;
  border: none !important;
  box-shadow: 0 4px 14px rgba(51,112,255,.35);
}
.sc-btn-gen:hover:not(.is-disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(51,112,255,.45);
}

/* ===== 弹窗通用 ===== */
.customer-dialog :deep(.el-dialog__body),
.instruction-dialog :deep(.el-dialog__body),
.keyword-dialog :deep(.el-dialog__body),
.task-dialog :deep(.el-dialog__body) { padding: 16px 22px 24px; }

.customer-search { margin-bottom: 14px; }
.customer-list { max-height: 380px; overflow-y: auto; }
.customer-option { padding: 12px 14px; border-radius: 8px; cursor: pointer; transition: background .15s; margin-bottom: 4px; }
.customer-option:hover { background: #f5f7fa; }
.customer-option.selected { background: #ecf5ff; border: 1px solid #a0cfff; }
.option-name { font-size: 14px; font-weight: 500; color: #303133; margin-bottom: 2px; }
.option-meta { font-size: 12px; color: #909399; display: flex; gap: 12px; }

.inst-dialog-tabs { display: flex; gap: 0; margin-bottom: 14px; border-bottom: 2px solid #f0f2f5; }
.inst-dialog-tabs button { padding: 10px 22px; font-size: 14px; border: none; background: none; color: #909399; cursor: pointer; position: relative; transition: color .2s; }
.inst-dialog-tabs button.active { color: #7b61ff; font-weight: 500; }
.inst-dialog-tabs button.active::after { content: ''; position: absolute; bottom: -2px; left: 0; right: 0; height: 2px; background: #7b61ff; border-radius: 1px; }
.inst-list { max-height: 400px; overflow-y: auto; }
.inst-option { padding: 14px 16px; border: 1px solid #ebeef5; border-radius: 10px; margin-bottom: 10px; cursor: pointer; transition: all .2s; }
.inst-option:hover { border-color: #c6e2ff; background: #f8fbff; }
.inst-option.selected { border-color: #7b61ff; background: #f8f5ff; }
.inst-title { font-size: 14px; font-weight: 600; color: #1a1a2e; margin-bottom: 4px; }
.inst-desc { font-size: 12px; color: #909399; margin-bottom: 8px; line-height: 1.4; }
.inst-meta { display: flex; align-items: center; gap: 10px; }
.inst-vars { font-size: 12px; color: #909399; display: flex; align-items: center; gap: 3px; }

.kw-dialog-toolbar { display: flex; gap: 10px; margin-bottom: 14px; align-items: center; }
.kw-dialog-search { flex: 1; }
.kw-dialog-actions { display: flex; gap: 6px; }
.kw-dialog-actions button { padding: 7px 14px; font-size: 12px; border: 1px solid #dcdfe6; border-radius: 6px; background: #fff; color: #606266; cursor: pointer; transition: all .2s; }
.kw-dialog-actions button:hover { border-color: #00bfa5; color: #00bfa5; }
.kw-dialog-list { max-height: 400px; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; }
.kw-dialog-item { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border: 1px solid #ebeef5; border-radius: 8px; cursor: pointer; transition: all .2s; font-size: 13px; }
.kw-dialog-item:hover { background: #f5f7fa; }
.kw-dialog-item.checked { border-color: #00bfa5; background: #f0fdfa; }
.kw-dialog-item input[type="checkbox"] { accent-color: #00bfa5; cursor: pointer; width: 16px; height: 16px; }
.kw-word { font-weight: 500; color: #303133; }

.task-list { max-height: 450px; overflow-y: auto; }
.task-item { display: flex; align-items: flex-start; gap: 14px; padding: 16px; border: 1px solid #ebeef5; border-radius: 10px; margin-bottom: 10px; }
.task-running { border-left: 3px solid #e6a23c; background: #fdfaf3; }
.task-completed { border-left: 3px solid #67c23a; background: #f0f9eb; }
.task-failed { border-left: 3px solid #f56c6c; background: #fef0f0; }
.task-status { display: flex; align-items: center; gap: 4px; font-size: 12px; font-weight: 500; white-space: nowrap; padding-top: 2px; }
.task-status.status-error { color: #f56c6c; }
.task-running .task-status { color: #e6a23c; }
.task-completed .task-status { color: #67c23a; }
.task-info { flex: 1; min-width: 0; }
.task-title { font-size: 14px; font-weight: 500; color: #303133; margin-bottom: 6px; }
.task-progress { max-width: 280px; }
.task-time { font-size: 12px; color: #909399; }
.task-error { font-size: 12px; color: #f56c6c; margin-bottom: 4px; word-break: break-all; }

.no-data { text-align: center; padding: 32px 16px; color: #c0c4cc; font-size: 13px; }

@media (max-width: 768px) {
  .sc-row-2 { grid-template-columns: 1fr; }
  .sc-cards { padding: 0 16px; }
  .sc-actionbar { left: 0; padding: 12px 16px; }
}
</style>
