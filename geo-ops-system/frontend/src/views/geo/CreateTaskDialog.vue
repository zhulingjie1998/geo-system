<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="创建拓词任务"
    width="600px"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="120px" label-position="top">
      <!-- 品牌选择 -->
      <el-form-item label="品牌" prop="accountId">
        <el-select
          v-model="form.accountId"
          placeholder="请选择客户/品牌"
          filterable
          style="width: 100%"
          :loading="loadingAccounts"
        >
          <el-option
            v-for="acc in accounts"
            :key="acc.id"
            :label="`${acc.name}${acc.brandName ? `（${acc.brandName}）` : ''}`"
            :value="acc.id"
          />
        </el-select>
      </el-form-item>

      <!-- 提示词条数 -->
      <el-form-item label="提示词条数" prop="promptCount">
        <el-input-number
          v-model="form.promptCount"
          :min="1"
          :max="500"
          :step="10"
          controls-position="right"
          style="width: 100%"
        />
        <div class="form-tip">建议 ≤ 500；超过 300 条将触发多轮补差额生成（耗时较长）</div>
      </el-form-item>

      <!-- 拓词类型 -->
      <el-form-item label="拓词类型">
        <div class="type-options">
          <div class="type-option">
            <el-switch
              v-model="form.includeBrand"
              active-text="包含品牌词"
              inactive-text=""
            />
            <div class="type-desc" v-if="!form.includeBrand">
              全部为通用词（不含本品牌名），品类/场景/人群/价格/地域类别平均覆盖 —— 最能体现 GEO 效果
            </div>
            <div class="type-desc" v-else>
              按 品牌词 : 通用词 = 2 : 8 生成：约 <strong>{{ brandWordCount }}</strong> 条品牌词（含本品牌名）+ <strong>{{ genericWordCount }}</strong> 条通用词（品类/场景/人群/价格/地域类别平均覆盖）
            </div>
          </div>
          <div class="type-option" style="margin-top: 12px;">
            <el-switch
              v-model="form.includeComparison"
              active-text="包含对比词"
              inactive-text=""
            />
            <div class="type-desc" v-if="!form.includeComparison">
              不生成对比词，只用面向单一选择的直接择优 / 推荐句式
            </div>
            <div class="type-desc" v-else>
              允许竞品/品类对比择优问法（如"X 和 Y 哪个更值得买"），引导 AI 同时列多个品牌比较 —— 仍是"哪个好/怎么选"的推荐句式，非参数科普
            </div>
          </div>
        </div>
      </el-form-item>

      <!-- 补充要求 -->
      <el-form-item label="补充要求">
        <el-input
          v-model="form.extraRequirements"
          type="textarea"
          :rows="4"
          maxlength="2000"
          show-word-limit
          placeholder="例如：&#10;- 重点关注高端商务人群&#10;- 避免医疗相关场景&#10;- 必须涵盖售后服务相关问句"
        />
        <div class="form-tip">选填，最多 2000 字符</div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        开始拓词
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import geoExpansionApi from '../../api/geoExpansion'

const props = defineProps({
  visible: Boolean,
})

const emit = defineEmits(['update:visible', 'created'])

const formRef = ref(null)
const submitting = ref(false)
const loadingAccounts = ref(false)
const accounts = ref([])

// 表单数据
const form = reactive({
  accountId: null,
  promptCount: 100,
  includeBrand: false,
  includeComparison: false,
  extraRequirements: '',
})

// 校验规则
const rules = {
  accountId: [{ required: true, message: '请选择品牌（客户）', trigger: 'change' }],
  promptCount: [
    { required: true, message: '请输入提示词条数', trigger: 'blur' },
    { type: 'number', min: 1, max: 500, message: '请输入 1-500 的整数', trigger: 'blur' },
  ],
}

// 计算属性：品牌词和通用词数量
const brandWordCount = computed(() => {
  return Math.round(form.promptCount * 0.2)
})

const genericWordCount = computed(() => {
  return form.promptCount - brandWordCount.value
})

// 加载客户列表
async function loadAccounts() {
  loadingAccounts.value = true
  try {
    accounts.value = await geoExpansionApi.getAccounts()
  } catch (e) {
    console.error('Failed to load accounts:', e)
  } finally {
    loadingAccounts.value = false
  }
}

// 提交表单
async function handleSubmit() {
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    const result = await geoExpansionApi.createTask({
      accountId: form.accountId,
      promptCount: form.promptCount,
      includeBrand: form.includeBrand,
      includeComparison: form.includeComparison,
      extraRequirements: form.extraRequirements,
    })
    ElMessage.success('任务创建成功')
    emit('update:visible', false)
    emit('created', result.taskId)

    // 重置表单
    formRef.value?.resetFields()
    Object.assign(form, {
      accountId: null,
      promptCount: 100,
      includeBrand: false,
      includeComparison: false,
      extraRequirements: '',
    })
  } catch (e) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    submitting.value = false
  }
}

// 弹窗打开时加载客户列表
watch(() => props.visible, (val) => {
  if (val && accounts.value.length === 0) {
    loadAccounts()
  }
})
</script>

<style scoped>
.type-options {
  width: 100%;
}

.type-option {
  padding: 12px 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.type-desc {
  margin-top: 8px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}

.form-tip {
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}
</style>
