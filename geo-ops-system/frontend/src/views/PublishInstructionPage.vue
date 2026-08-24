<template>
  <div class="instruction-library-page">
    <!-- ===== 顶部工具栏 ===== -->
    <section class="toolbar-section">
      <div class="toolbar-left">
        <!-- 我的/全局指令切换 -->
        <div class="tab-group">
          <button 
            class="tab-btn" 
            :class="{ active: scopeFilter === 'mine' }" 
            @click="scopeFilter = 'mine'"
          >
            我的指令<span class="tab-count">{{ mineCount }}</span>
          </button>
          <button 
            class="tab-btn" 
            :class="{ active: scopeFilter === 'global' }" 
            @click="scopeFilter = 'global'"
          >
            全局指令<span class="tab-count">{{ globalCount }}</span>
          </button>
        </div>

        <!-- 搜索框 -->
        <el-input
          v-model="searchText"
          placeholder="搜索指令名 / 分类 / 描述"
          prefix-icon="Search"
          clearable
          class="search-input"
        />
      </div>

      <div class="toolbar-right">
        <span class="usage-info">累计使用 {{ totalUsage }} 次</span>
        <el-button type="primary" @click="openCreateDialog">
          <el-icon><Plus /></el-icon>
          新建指令
        </el-button>
      </div>
    </section>

    <!-- ===== 标签筛选栏（胶囊式） ===== -->
    <section class="tag-filter-section">
      <button 
        class="filter-pill" 
        :class="{ active: selectedTag === '' }" 
        @click="selectedTag = ''"
      >
        全部 <span class="pill-count">{{ allTags.length }}</span>
      </button>
      <button 
        v-for="tag in allTags" 
        :key="tag"
        class="filter-pill" 
        :class="{ active: selectedTag === tag }" 
        @click="selectedTag = tag"
      >
        {{ tag }} <span class="pill-count">{{ getTagCount(tag) }}</span>
      </button>
    </section>

    <!-- ===== 指令卡片列表 ===== -->
    <section class="cards-section">
      <div v-if="filteredInstructions.length === 0" class="empty-state">
        <el-empty description="暂无指令">
          <el-button type="primary" @click="openCreateDialog">新建指令</el-button>
        </el-empty>
      </div>
      
      <div v-else class="card-grid">
        <div 
          v-for="item in filteredInstructions" 
          :key="item.id" 
          class="instruction-card"
        >
          <!-- 卡片头部：大图标 + 名称 -->
          <div class="card-header">
            <div class="card-icon-lg" :class="getIconClass(item)">
              <el-icon v-if="item.scope === 'global'"><Trophy /></el-icon>
              <el-icon v-else><Document /></el-icon>
            </div>
            <div class="card-title-area">
              <h3 class="card-title">{{ item.name }}</h3>
              <div class="card-scope-tags">
                <span v-if="item.scope === 'global'" class="scope-badge global">通用</span>
                <span v-else class="scope-badge mine">我的</span>
                <el-tag 
                  v-for="tag in parseTags(item.tags)" 
                  :key="tag" 
                  size="small" 
                  effect="plain"
                  class="item-tag"
                >{{ tag }}</el-tag>
              </div>
            </div>
          </div>

          <!-- 描述/简介 -->
          <p v-if="item.description" class="card-desc">{{ item.description }}</p>

          <!-- 指令内容预览 -->
          <div class="card-content-preview">
            <pre>{{ truncateContent(item.prompt) }}</pre>
          </div>

          <!-- 变量标签云 -->
          <div class="var-tags-row">
            <span 
              v-for="v in extractVariables(item.prompt)" 
              :key="v" 
              class="var-tag"
            >{{ v }}</span>
          </div>

          <!-- 底部信息栏 -->
          <div class="card-footer">
            <span class="footer-info">
              <strong>{{ item.minWords || 800 }}~{{ item.maxWords || 1500 }} 字</strong>
            </span>
            <span class="footer-info">{{ item.model || '通义千问' }}</span>
            <span class="footer-info">用过 {{ item.usageCount || 0 }} 次</span>
          </div>

          <!-- 操作按钮 -->
          <div class="card-actions">
            <el-button type="primary" size="small" @click="useInstruction(item)">
              <el-icon><Promotion /></el-icon> 立即使用
            </el-button>
            <el-button size="small" plain @click="openEditDialog(item)">
              <el-icon><EditPen /></el-icon> 编辑
            </el-button>
            <el-button size="small" plain type="danger" @click="confirmDelete(item)">
              <el-icon><Delete /></el-icon> 删除
            </el-button>
          </div>
        </div>
      </div>
    </section>

    <!-- ===== 新建/编辑指令弹窗 ===== -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑指令' : '新建指令'"
      width="min(600px, 94vw)"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-form-item label="指令名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入指令名称" maxlength="50" show-word-limit />
        </el-form-item>

        <el-form-item label="标签" prop="tags">
          <el-select
            v-model="formData.tagList"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入标签后按回车添加"
            style="width: 100%"
          >
            <el-option
              v-for="tag in allTags"
              :key="tag"
              :label="tag"
              :value="tag"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="一句话简介" prop="description">
          <el-input 
            v-model="formData.description" 
            type="textarea" 
            :rows="2" 
            placeholder="简要描述该指令的用途"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>

        <el-form-item label="字数范围">
          <div class="word-range-control">
            <el-input-number 
              v-model="formData.minWords" 
              :min="100" 
              :max="5000" 
              :step="100" 
              controls-position="right"
            />
            <span class="range-separator">~</span>
            <el-input-number 
              v-model="formData.maxWords" 
              :min="100" 
              :max="10000" 
              :step="100" 
              controls-position="right"
            />
            <span class="range-unit">字符</span>
          </div>
        </el-form-item>

        <el-form-item label="默认LLM" prop="model">
          <el-select v-model="formData.model" placeholder="选择LLM模型" style="width: 100%">
            <el-option 
              v-for="m in availableModels" 
              :key="m.value" 
              :label="m.label" 
              :value="m.value" 
            />
          </el-select>
        </el-form-item>

        <el-form-item label="Prompt指令" prop="prompt">
          <!-- 变量插入工具栏 -->
          <div class="prompt-toolbar">
            <el-button 
              type="primary" 
              size="small" 
              plain
              :loading="optimizing"
              @click="optimizeWithAI"
            >
              <el-icon><MagicStick /></el-icon>
              一键添加指令
            </el-button>
            <div class="var-buttons">
              <span class="var-label">插入变量：</span>
              <el-button size="small" @click="insertVariable('{brand}')">{brand}</el-button>
              <el-button size="small" @click="insertVariable('{kb_content}')">{kb_content}</el-button>
              <el-button size="small" @click="insertVariable('{topic}')">{topic}</el-button>
              <el-button size="small" @click="insertVariable('{user_instruction}')">{user_instruction}</el-button>
              <el-button size="small" @click="insertVariable('{word_min}')">{word_min}</el-button>
              <el-button size="small" @click="insertVariable('{word_max}')">{word_max}</el-button>
            </div>
          </div>

          <!-- Prompt输入框 -->
          <el-input
            ref="promptInputRef"
            v-model="formData.prompt"
            type="textarea"
            :rows="8"
            placeholder="请输入生成内容的提示词/指令..."
            maxlength="10000"
            show-word-limit
          />

          <!-- 占位符说明 -->
          <div class="placeholder-hint">
            💡 占位符说明（生成时自动替换）：
            <code>{brand}</code>品牌 ·
            <code>{kb_content}</code>知识库 ·
            <code>{topic}</code>主题 ·
            <code>{user_instruction}</code>个性化要求 ·
            <code>{word_min}</code>最小字数 ·
            <code>{word_max}</code>最大字数
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveInstruction">
          确认
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, Plus, Promotion, EditPen, Delete, MagicStick, Trophy } from '@element-plus/icons-vue'
import api from '@/api'

const router = useRouter()

// ========== 状态管理 ==========
const searchText = ref('')
const scopeFilter = ref('mine') // mine | global
const selectedTag = ref('')
const dialogVisible = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const optimizing = ref(false) // AI优化加载状态
const formRef = ref()
const promptInputRef = ref() // Prompt输入框引用
const editingId = ref(null)

// 需要检查的变量列表
const requiredVariables = ['{brand}', '{kb_content}', '{topic}', '{user_instruction}', '{word_min}', '{word_max}']

// 指令列表数据
const instructions = ref([])

// 可用LLM模型列表（后续可从系统设置获取）
const availableModels = ref([
  { value: 'qwen-plus', label: '通义千问' },
])

// 默认模型（从系统设置加载）
const defaultModel = ref('qwen-plus')

// 加载系统设置中的默认模型
async function loadDefaultModel() {
  try {
    const res = await fetch('/api/settings')
    if (res.ok) {
      const data = await res.json()
      // 优先使用通义千问的model_name
      if (data.qwen_model_name) {
        defaultModel.value = data.qwen_model_name
        availableModels.value = [
          { value: data.qwen_model_name, label: data.qwen_model_name }
        ]
      }
    }
  } catch (e) {
    console.warn('加载模型设置失败，使用默认值')
  }
}

// 页面加载时获取默认模型
loadDefaultModel()

// 表单数据
const formData = ref({
  name: '',
  tagList: [],
  description: '',
  minWords: 800,
  maxWords: 1500,
  model: '',  // 从系统设置加载
  prompt: '',
})

// 表单验证规则
const formRules = {
  name: [{ required: true, message: '请输入指令名称', trigger: 'blur' }],
  prompt: [{ required: true, message: '请输入Prompt指令', trigger: 'blur' }],
}

// ========== 计算属性 ==========
// 所有唯一标签
const allTags = computed(() => {
  const tagSet = new Set()
  instructions.value.forEach(item => {
    parseTags(item.tags).forEach(t => tagSet.add(t))
  })
  return Array.from(tagSet).sort()
})

// 我的指令数量
const mineCount = computed(() => {
  return instructions.value.filter(i => i.scope !== 'global').length
})

// 全局指令数量
const globalCount = computed(() => {
  return instructions.value.filter(i => i.scope === 'global').length
})

// 总使用次数
const totalUsage = computed(() => {
  return instructions.value.reduce((sum, i) => sum + (i.usageCount || 0), 0)
})

// 过滤后的指令列表
const filteredInstructions = computed(() => {
  let result = instructions.value
  
  // 范围筛选
  if (scopeFilter.value === 'mine') {
    result = result.filter(i => i.scope !== 'global')
  } else if (scopeFilter.value === 'global') {
    result = result.filter(i => i.scope === 'global')
  }
  
  // 标签筛选
  if (selectedTag.value) {
    result = result.filter(i => parseTags(i.tags).includes(selectedTag.value))
  }
  
  // 搜索筛选
  if (searchText.value.trim()) {
    const keyword = searchText.value.trim().toLowerCase()
    result = result.filter(i => {
      const nameMatch = (i.name || '').toLowerCase().includes(keyword)
      const descMatch = (i.description || '').toLowerCase().includes(keyword)
      const tagMatch = parseTags(i.tags).some(t => t.toLowerCase().includes(keyword))
      const promptMatch = (i.prompt || '').toLowerCase().includes(keyword)
      return nameMatch || descMatch || tagMatch || promptMatch
    })
  }
  
  return result
})

// ========== 工具函数 ==========
function storageKey() {
  return 'geo_instruction_library'
}

function parseTags(tags) {
  if (!tags) return []
  if (Array.isArray(tags)) return tags.filter(Boolean)
  if (typeof tags === 'string') {
    return tags.split(/[,，、]/).map(t => t.trim()).filter(Boolean)
  }
  return []
}

function getTagCount(tag) {
  return instructions.value.filter(i => parseTags(i.tags).includes(tag)).length
}

function truncateContent(content, maxLen = 80) {
  if (!content) return ''
  const text = content.replace(/\n/g, ' ').trim()
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text
}

function getIconClass(item) {
  if (item.scope === 'global') return 'icon-global'
  return 'icon-mine'
}

// 从 prompt 内容中提取变量
function extractVariables(prompt) {
  if (!prompt) return []
  const matches = prompt.match(/\{[^}]+\}/g) || []
  return [...new Set(matches)]
}

// ========== 数据操作 ==========
function loadInstructions() {
  try {
    const raw = localStorage.getItem(storageKey())
    const parsed = raw ? JSON.parse(raw) : []
    instructions.value = Array.isArray(parsed) ? parsed : []
  } catch {
    instructions.value = []
  }
}

function persistInstructions() {
  localStorage.setItem(storageKey(), JSON.stringify(instructions.value))
}

function generateId() {
  return `inst_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

// ========== Prompt变量操作 ==========
// 插入变量到光标位置
function insertVariable(variable) {
  const textarea = promptInputRef.value?.textarea || promptInputRef.value?.$el?.querySelector('textarea')
  if (!textarea) {
    // 如果无法获取textarea，直接追加到末尾
    formData.value.prompt += variable
    return
  }
  
  const start = textarea.selectionStart
  const end = textarea.selectionEnd
  const text = formData.value.prompt
  
  // 在光标位置插入变量
  formData.value.prompt = text.slice(0, start) + variable + text.slice(end)
  
  // 重新设置光标位置（在插入的变量后面）
  setTimeout(() => {
    textarea.focus()
    textarea.setSelectionRange(start + variable.length, start + variable.length)
  }, 0)
}

// 检查Prompt是否包含所有必需变量
function checkRequiredVariables(prompt) {
  if (!prompt) return { missing: requiredVariables.slice(), allPresent: false }
  
  const missing = requiredVariables.filter(v => !prompt.includes(v))
  return {
    missing,
    allPresent: missing.length === 0
  }
}

// AI一键优化指令
async function optimizeWithAI() {
  const userInput = formData.value.prompt.trim()
  
  if (!userInput) {
    ElMessage.warning('请先输入一些指令内容，再使用AI优化功能')
    return
  }

  optimizing.value = true
  
  try {
    // 调用后端AI接口优化指令
    const response = await fetch('/api/ai/optimize-prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        input: userInput
      })
    })

    const result = await response.json()
    
    if (!response.ok) {
      throw new Error(result.error || 'AI服务请求失败')
    }
    
    if (result.ok && result.optimized) {
      // 左右对比布局的弹窗
      let messageHtml = `
        <div style="display:flex;gap:16px;max-height:60vh;overflow:hidden;">
          <!-- 左侧：原始输入 -->
          <div style="flex:1;display:flex;flex-direction:column;min-width:0;">
            <div style="background:#e8e8e8;padding:8px 12px;border-radius:6px 6px 0 0;font-size:13px;font-weight:bold;color:#666;">
              📝 原始输入
            </div>
            <pre style="background:#f5f7fa;padding:12px;border-radius:0 0 6px 6px;font-size:12px;white-space:pre-wrap;word-break:break-word;overflow-y:auto;max-height:calc(60vh - 50px);margin:0;border:1px solid #e4e7ed;">${escapeHtml(userInput)}</pre>
          </div>
          <!-- 右侧：AI优化后 -->
          <div style="flex:1;display:flex;flex-direction:column;min-width:0;">
            <div style="background:#e1f3d8;padding:8px 12px;border-radius:6px 6px 0 0;font-size:13px;font-weight:bold;color:#67c23a;">
              ✨ AI优化后
            </div>
            <pre style="background:#f0f9eb;padding:12px;border-radius:0 0 6px 6px;font-size:12px;white-space:pre-wrap;word-break:break-word;overflow-y:auto;max-height:calc(60vh - 50px);margin:0;border:1px solid #c2e7b0;">${escapeHtml(result.optimized)}</pre>
          </div>
        </div>
      `
      
      if (result.warning) {
        messageHtml += `<div style="margin-top:12px;padding:8px 12px;background:#fdf6ec;border-radius:6px;color:#E6A23C;font-size:12px;">⚠️ ${escapeHtml(result.warning)}</div>`
      }
      
      messageHtml += `</div>`

      // 确认是否采用AI优化的结果
      try {
        await ElMessageBox.confirm(
          messageHtml,
          'AI优化完成',
          {
            confirmButtonText: '采用优化结果',
            cancelButtonText: '取消',
            type: 'success',
            dangerouslyUseHTMLString: true,
          }
        )
        
        formData.value.prompt = result.optimized
        
        if (result.warning) {
          ElMessage.warning('已应用AI优化结果，但部分变量需要手动补充')
        } else {
          ElMessage.success('已应用AI优化结果，请检查并保存')
        }
      } catch {
        // 用户取消了
      }
    } else {
      throw new Error(result.error || 'AI返回结果为空')
    }
  } catch (error) {
    console.error('AI优化失败:', error)
    
    // 显示具体错误原因
    const errorMsg = error.message || '未知错误'
    ElMessage.error(`AI优化失败: ${errorMsg}`)
  } finally {
    optimizing.value = false
  }
}

// HTML转义函数
function escapeHtml(text) {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

// ========== 弹窗操作 ==========
function openCreateDialog() {
  isEditing.value = false
  editingId.value = null
  formData.value = {
    name: '',
    tagList: [],
    description: '',
    minWords: 800,
    maxWords: 1500,
    model: defaultModel.value || 'qwen-plus',
    prompt: '',
  }
  dialogVisible.value = true
}

function openEditDialog(item) {
  isEditing.value = true
  editingId.value = item.id
  formData.value = {
    name: item.name || '',
    tagList: parseTags(item.tags),
    description: item.description || '',
    minWords: item.minWords || 800,
    maxWords: item.maxWords || 1500,
    model: item.model || defaultModel.value || 'qwen-plus',
    prompt: item.prompt || '',
  }
  dialogVisible.value = true
}

async function saveInstruction() {
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  // 检查是否包含所有必需变量
  const varCheck = checkRequiredVariables(formData.value.prompt)
  if (!varCheck.allPresent) {
    const missingStr = varCheck.missing.join('、')
    try {
      await ElMessageBox.confirm(
        `指令中缺少以下变量：<strong>${missingStr}</strong><br/><br/>建议点击「一键添加指令」让AI自动优化并补全变量，是否继续保存？`,
        '变量检查提示',
        {
          confirmButtonText: '继续保存',
          cancelButtonText: '去优化',
          type: 'warning',
          dangerouslyUseHTMLString: true,
        }
      )
      // 用户选择继续保存，不做处理
    } catch {
      // 用户选择去优化，取消保存
      return
    }
  }

  saving.value = true

  try {
    const data = {
      id: isEditing.value ? editingId.value : generateId(),
      name: formData.value.name.trim(),
      tags: formData.value.tagList.join(','),
      description: formData.value.description.trim(),
      minWords: formData.value.minWords,
      maxWords: formData.value.maxWords,
      model: formData.value.model,
      prompt: formData.value.prompt,
      scope: isEditing.value ? undefined : 'mine', // 新建默认为我的指令
      usageCount: 0,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }

    if (isEditing.value) {
      // 编辑模式：更新现有记录
      const idx = instructions.value.findIndex(i => i.id === editingId.value)
      if (idx >= 0) {
        data.scope = instructions.value[idx].scope // 保持原有作用域
        data.usageCount = instructions.value[idx].usageCount || 0
        data.createdAt = instructions.value[idx].createdAt
        instructions.value[idx] = { ...instructions.value[idx], ...data }
      }
      ElMessage.success('指令已更新')
    } else {
      // 新建模式：添加新记录
      instructions.value.unshift(data)
      ElMessage.success('指令创建成功')
    }

    persistInstructions()
    dialogVisible.value = false
  } catch (e) {
    console.error('保存指令失败:', e)
    ElMessage.error('保存失败，请重试')
  } finally {
    saving.value = false
  }
}

async function confirmDelete(item) {
  const canDelete = item.scope !== 'global' || isSuperAdmin()
  if (!canDelete) {
    ElMessage.warning('全局指令仅超管可删除')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认删除指令「${item.name}」吗？删除后不可恢复。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonType: 'cancel', type: 'warning' }
    )

    const idx = instructions.value.findIndex(i => i.id === item.id)
    if (idx >= 0) {
      instructions.value.splice(idx, 1)
      persistInstructions()
      ElMessage.success('已删除')
    }
  } catch {
    // 用户取消
  }
}

function useInstruction(item) {
  // 增加使用次数
  const idx = instructions.value.findIndex(i => i.id === item.id)
  if (idx >= 0) {
    instructions.value[idx].usageCount = (instructions.value[idx].usageCount || 0) + 1
    instructions.value[idx].updatedAt = new Date().toISOString()
    persistInstructions()
  }

  // 跳转到智能生文页面，携带指令参数
  router.push({
    path: '/publish/ai-write',
    query: {
      instructionId: item.id,
      instructionName: item.name,
      model: item.model || 'qwen-plus',
      minWords: item.minWords || 800,
      maxWords: item.maxWords || 1500,
    },
  })
}

function isSuperAdmin() {
  return localStorage.getItem('geo_is_super') === '1'
}

// ========== 生命周期 ==========
onMounted(() => {
  loadInstructions()

  // 如果没有示例数据，初始化一些默认指令
  if (instructions.value.length === 0) {
    initDefaultInstructions()
  }
})

function initDefaultInstructions() {
  const defaults = [
    {
      id: generateId(),
      name: '内容生成指令-通用',
      tags: ['通用'],
      description: '适用于大多数SEO文章生成的通用指令模板',
      minWords: 800,
      maxWords: 1500,
      model: 'qwen-plus',
      prompt: `- Role: 资深SEO文案撰写人\n- Skills: 你非常精通GEO知识；【GEO全称Generative Engine Optimization】\n- Workflow:\n  1. 分析用户提供的主题和关键词\n  2. 结合GEO优化原则生成高质量内容\n  3. 确保内容结构清晰、逻辑连贯\n- Output: 符合SEO标准的原创文章`,
      scope: 'mine',
      usageCount: 55,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      keywords: ['brand', 'kb_content', 'topic', 'word_min'],
    },
    {
      id: generateId(),
      name: '丝涟-榜单体',
      tags: ['ranking'],
      description: '丝涟专属榜单体结构+产品+合规，替代通用榜单稿评',
      minWords: 1800,
      maxWords: 2600,
      model: 'claude',
      prompt: `你是丝涟（[brand]）床垫品牌的资深 GEO 软文写手。请就主题「[topic]」写一篇「市场榜单体」软文。\n\n要求：\n1. 以[brand]产品为核心\n2. 采用榜单形式呈现\n3. 包含合规声明\n4. 字数控制在{word_min}~{word_max}字之间`,
      scope: 'mine',
      usageCount: 12,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      keywords: ['brand', 'kb_content', 'topic', 'word_min', 'word_max'],
    },
  ]
  
  instructions.value = defaults
  persistInstructions()
}
</script>

<style scoped>
.instruction-library-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  height: calc(100vh - 120px);
  max-height: calc(100vh - 120px);
  background: #f5f7fa;
  overflow: hidden;
}

/* ===== 工具栏 ===== */
.toolbar-section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  background: #fff;
  padding: 14px 18px;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 14px;
  flex: 1;
}

.tab-group {
  display: flex;
  background: #f0f2f5;
  border-radius: 8px;
  padding: 3px;
}

.tab-btn {
  padding: 7px 16px;
  border: none;
  background: transparent;
  color: #606266;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 6px;
}

.tab-btn:hover {
  color: #409eff;
}

.tab-btn.active {
  background: #409eff;
  color: #fff;
  box-shadow: 0 2px 6px rgba(64,158,255,0.3);
}

.tab-count {
  font-size: 11px;
  opacity: 0.85;
}

.search-input {
  width: 280px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.usage-info {
  font-size: 13px;
  color: #909399;
}

/* ===== 标签筛选（胶囊式） ===== */
.tag-filter-section {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  background: transparent;
  padding: 4px 0;
}

.filter-pill {
  padding: 6px 16px;
  border: 1px solid #e4e7ed;
  background: #fff;
  color: #606266;
  font-size: 13px;
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.25s ease;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.filter-pill:hover {
  border-color: #7c3aed;
  color: #7c3aed;
}

.filter-pill.active {
  background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
  border-color: #7c3aed;
  color: #fff;
  box-shadow: 0 2px 8px rgba(124, 58, 237, 0.35);
}

.pill-count {
  font-size: 11px;
  opacity: 0.8;
}

/* ===== 卡片区域 ===== */
.cards-section {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.cards-section::-webkit-scrollbar {
  width: 6px;
}

.cards-section::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 3px;
}

.cards-section::-webkit-scrollbar-track {
  background: transparent;
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 300px;
  background: #fff;
  border-radius: 10px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
  align-content: start;
}

@media (max-width: 1200px) {
  .card-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 768px) {
  .card-grid { grid-template-columns: 1fr; }
}

/* ===== 指令卡片 ===== */
.instruction-card {
  background: #fff;
  border-radius: 14px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  transition: all 0.3s ease;
  border: 1px solid #f0f0f0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.instruction-card:hover {
  box-shadow: 0 8px 24px rgba(0,0,0,0.1);
  transform: translateY(-3px);
  border-color: #e8e0ff;
}

/* 卡片头部 */
.card-header {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.card-icon-lg {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}

.card-icon-lg.global {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  color: #d97706;
}

.card-icon-lg.mine {
  background: linear-gradient(135deg, #ede9fe 0%, #ddd6fe 100%);
  color: #7c3aed;
}

.card-title-area {
  flex: 1;
  min-width: 0;
}

.card-title {
  margin: 0 0 6px 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.3;
}

.card-scope-tags {
  display: flex;
  gap: 6px;
}

.scope-badge {
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 500;
}

.scope-badge.global {
  background: #dbeafe;
  color: #2563eb;
}

.scope-badge.mine {
  background: #f3e8ff;
  color: #7c3aed;
}

.card-header {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.card-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}

.icon-mine {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
}

.icon-global {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  color: #fff;
}

.card-title-row {
  flex: 1;
  min-width: 0;
}

.card-title {
  margin: 0 0 6px 0;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  line-height: 1.3;
}

.card-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.scope-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.scope-tag.mine {
  background: #e8f0fe;
  color: #1967d2;
}

.scope-tag.global {
  background: #fce4ec;
  color: #c62828;
}

.item-tag {
  font-size: 11px !important;
  border-radius: 10px !important;
  margin-left: 4px;
}

/* 变量标签行 */
.var-tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.var-tag {
  padding: 4px 10px;
  background: linear-gradient(135deg, #f0e6ff 0%, #e8deff 100%);
  border: 1px solid #d4b8ff;
  border-radius: 6px;
  font-size: 11px;
  color: #7c3aed;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-weight: 500;
  letter-spacing: 0.2px;
  transition: all 0.2s ease;
  cursor: default;
}

.var-tag:hover {
  background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
  color: #fff;
  border-color: #7c3aed;
  box-shadow: 0 2px 6px rgba(124, 58, 237, 0.35);
}

.card-desc {
  margin: 0;
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
}

.card-content-preview {
  background: #fafbfc;
  border-radius: 8px;
  padding: 10px 12px;
  border: 1px solid #f0f2f5;
}

.card-content-preview pre {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 12px;
  color: #666;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.6;
}

.keywords-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.keyword-tag {
  font-size: 11px;
  padding: 2px 8px;
  background: #f0f5ff;
  color: #409eff;
  border-radius: 4px;
  border: 1px solid #d9ecff;
}

.card-footer {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-top: 10px;
  border-top: 1px solid #f0f2f5;
}

.footer-info {
  font-size: 12px;
  color: #909399;
}

.footer-info strong {
  color: #7c3aed;
}

.card-actions {
  display: flex;
  gap: 8px;
  padding-top: 4px;
}

.card-actions .el-button {
  flex: 1;
}

/* ===== 弹窗样式调整 ===== */
:deep(.el-dialog) {
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}

:deep(.el-dialog__header) {
  flex-shrink: 0;
}

:deep(.el-dialog__body) {
  overflow-y: auto;
  overflow-x: hidden;
  max-height: calc(90vh - 120px);
}

:deep(.el-dialog__footer) {
  flex-shrink: 0;
  padding-top: 10px;
}
.word-range-control {
  display: flex;
  align-items: center;
  gap: 8px;
}

.range-separator {
  color: #909399;
  font-weight: 500;
}

.range-unit {
  color: #909399;
  font-size: 13px;
}

/* ===== Prompt工具栏 ===== */
.prompt-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.var-buttons {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.var-label {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}

.var-buttons .el-button {
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 11px !important;
  padding: 4px 8px !important;
}

.placeholder-hint {
  margin-top: 8px;
  padding: 8px 12px;
  background: #f0f9ff;
  border-radius: 6px;
  font-size: 12px;
  color: #0369a1;
  line-height: 1.6;
}

.placeholder-hint code {
  background: rgba(59, 130, 246, 0.15);
  color: #1d4ed8;
  padding: 1px 5px;
  border-radius: 3px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 11px;
}
</style>
