<template>
  <el-dialog
    v-model="visible"
    :title="null"
    width="min(760px, 92vw)"
    top="6vh"
    :close-on-click-modal="false"
    class="customer-create-dialog"
    destroy-on-close
  >
    <template #header>
      <div class="cd-header">
        <div class="cd-header-left">
          <div class="cd-header-icon">
            <el-icon :size="18"><OfficeBuilding /></el-icon>
          </div>
          <div>
            <div class="cd-header-title">新建客户</div>
            <div class="cd-header-desc">录入公司名称、品牌与覆盖平台，保存后可立即回到知识库创建流程</div>
          </div>
        </div>
      </div>
    </template>

    <div class="cd-body">
      <el-form :model="form" label-position="top" class="cd-form">
        <el-form-item label="公司名称" required>
          <el-input v-model="form.companyName" placeholder="请输入公司名称" />
        </el-form-item>

        <el-form-item label="公司品牌" required>
          <el-select
            v-model="form.companyBrands"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入品牌名后回车添加，支持多个"
            style="width: 100%"
          >
            <el-option v-for="b in brandSuggestions" :key="b" :label="b" :value="b" />
          </el-select>
        </el-form-item>

        <el-form-item label="覆盖平台">
          <PlatformSelector v-model="form.platforms" />
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">确认创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { OfficeBuilding } from '@element-plus/icons-vue'
import api from '@/api'
import PlatformSelector from '@/components/common/PlatformSelector.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  suggestions: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const saving = ref(false)
const form = reactive({
  companyName: '',
  companyBrands: [],
  platforms: [],
})

const brandSuggestions = computed(() => {
  const base = Array.isArray(props.suggestions) ? props.suggestions : []
  return [...new Set(base.filter(Boolean))].slice(0, 20)
})

function reset() {
  form.companyName = ''
  form.companyBrands = []
  form.platforms = []
}

async function submit() {
  const companyName = String(form.companyName || '').trim()
  const companyBrands = Array.isArray(form.companyBrands) ? form.companyBrands.filter(Boolean) : []
  if (!companyName) {
    ElMessage.warning('请输入公司名称')
    return
  }
  if (!companyBrands.length) {
    ElMessage.warning('请至少填写一个品牌')
    return
  }

  saving.value = true
  try {
    const created = await api.createAccount({
      companyName,
      companyBrand: companyBrands[0],
      platforms: Array.isArray(form.platforms) ? form.platforms : [],
    })
    ElMessage.success('客户创建成功')
    emit('saved', created)
    visible.value = false
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '创建客户失败')
  } finally {
    saving.value = false
  }
}

watch(
  () => visible.value,
  (show) => {
    if (!show) reset()
  }
)
</script>

<style scoped>
.customer-create-dialog :deep(.el-dialog__body) { padding-top: 0; }
.cd-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.cd-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.cd-header-icon {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: linear-gradient(135deg, #6d7cff, #4f46e5);
  box-shadow: 0 10px 24px rgba(79, 70, 229, 0.24);
}
.cd-header-title {
  font-size: 18px;
  font-weight: 800;
  color: #0f172a;
}
.cd-header-desc {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}
.cd-body { padding: 4px 0 6px; }
.cd-form :deep(.el-form-item__label) {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}
</style>
