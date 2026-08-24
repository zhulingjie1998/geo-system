<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    title="转为正式客户" width="560px" append-to-body @open="onOpen">
    <div class="pad-tip">
      转正后客户将进入<strong>查词、报告、拓词、智能生文</strong>等运营功能。
      需补全<strong>覆盖平台</strong>和<strong>关键词</strong>（各至少 1 项）。
    </div>
    <el-form label-position="top">
      <el-form-item label="覆盖平台">
        <PlatformSelector v-model="platforms" />
      </el-form-item>
      <el-form-item label="关键词（每行一条，至少 1 条）">
        <el-input v-model="batchText" type="textarea" :autosize="{ minRows: 4, maxRows: 10 }"
                  placeholder="粘贴关键词，每行一条…" @blur="parseBatch" />
        <div class="pad-kw-count">已识别 <strong>{{ rows.length }}</strong> 条关键词</div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">确认转正</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import PlatformSelector from '@/components/common/PlatformSelector.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  account: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'promoted'])

const platforms = ref([])
const batchText = ref('')
const rows = ref([])
const submitting = ref(false)

function onOpen() {
  platforms.value = [...(props.account?.platforms || [])]
  batchText.value = ''
  rows.value = []
}

function parseBatch() {
  const lines = (batchText.value || '').split(/[\n\r]+/).map(s => s.trim()).filter(Boolean)
  rows.value = lines.map(l => ({ intentPrompt: l, coreIntentWord: l, intentCategory: '' }))
}

async function submit() {
  parseBatch()
  if (!platforms.value.length) { ElMessage.warning('请至少选择 1 个覆盖平台'); return }
  if (!rows.value.length) { ElMessage.warning('请至少录入 1 个关键词'); return }
  submitting.value = true
  try {
    await api.promoteAccount(props.account.id, { platforms: platforms.value, keywords: rows.value })
    ElMessage.success('已转为正式客户')
    emit('promoted')
    emit('update:modelValue', false)
  } catch (e) {
    ElMessage.error('转正失败：' + (e.response?.data?.error || e.message || e))
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.pad-tip { background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 8px;
  padding: 10px 12px; font-size: 13px; color: #4b5563; line-height: 1.7; margin-bottom: 16px; }
.pad-kw-count { font-size: 12px; color: #6b7280; margin-top: 4px; }
</style>
