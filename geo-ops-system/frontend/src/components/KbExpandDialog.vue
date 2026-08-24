<template>
  <el-dialog :model-value="modelValue" title="AI 扩充知识库模块" width="min(720px, 95vw)" top="6vh"
             :close-on-click-modal="false" @update:model-value="$emit('update:modelValue', $event)" @open="onOpen">
    <div class="ke" v-loading="loading">
      <p class="ke-intro">在当前版本基础上，让 AI 围绕你选的资料和要求**新增若干个全新模块**（不改已有模块），生成后追加为新版本。</p>

      <!-- 资料选择 -->
      <div class="ke-block">
        <div class="ke-block-h">选择资料（可多选；也可上传新资料）</div>
        <div v-if="sources.length" class="ke-srcs">
          <el-checkbox v-for="s in sources" :key="s.id" v-model="picked[s.id]" class="ke-src">
            <span class="ke-src-name">{{ s.file_name || s.fileName || ('资料#'+s.id) }}</span>
            <span class="ke-src-type">{{ s.file_type || s.fileType || '' }}</span>
          </el-checkbox>
        </div>
        <div v-else class="ke-empty-src">该客户暂无已上传资料，可在下方上传新资料，或仅凭补充要求让 AI 扩充。</div>
        <el-upload :auto-upload="false" :show-file-list="true" :file-list="fileList" multiple
                   accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.md,.png,.jpg,.jpeg"
                   :on-change="onFileChange" :on-remove="onFileRemove">
          <el-button :icon="UploadFilled" plain size="small">上传新资料</el-button>
        </el-upload>
      </div>

      <!-- 要求 + 数量 -->
      <div class="ke-block">
        <div class="ke-block-h">补充要求</div>
        <el-input v-model="instruction" type="textarea" :autosize="{minRows:3,maxRows:8}"
          placeholder="例：补充售后服务体系、行业解决方案、客户成功案例等模块；侧重 XX 场景；语气更专业…" />
      </div>
      <div class="ke-row">
        <span class="ke-row-l">新增模块数量</span>
        <el-input-number v-model="addCount" :min="1" :max="10" size="default" />
        <span class="ke-row-tip">AI 将生成 {{ addCount }} 个全新模块，编号自当前最大模块号续接</span>
      </div>
    </div>

    <template #footer>
      <span class="ke-foot-hint">{{ statusText }}</span>
      <el-button @click="$emit('update:modelValue', false)" :disabled="running">取消</el-button>
      <el-button type="primary" :icon="MagicStick" :loading="running" :disabled="!canSubmit" @click="submit">
        开始 AI 扩充
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { UploadFilled, MagicStick } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import publishApi from '@/api/publish'

const props = defineProps({
  modelValue: Boolean,
  prevKbId: { type: [Number, String], default: null },
  accountId: { type: [Number, String], default: null },
})
const emit = defineEmits(['update:modelValue', 'done'])

const loading = ref(false)
const sources = ref([])
const picked = reactive({})
const fileList = ref([])
const newFiles = ref([])
const instruction = ref('')
const addCount = ref(3)
const running = ref(false)
const statusText = ref('')

async function onOpen() {
  Object.keys(picked).forEach(k => delete picked[k])
  fileList.value = []; newFiles.value = []; instruction.value = ''; addCount.value = 3; statusText.value = ''
  sources.value = []
  if (!props.accountId) return
  loading.value = true
  try { sources.value = (await publishApi.kbListSources(props.accountId)).items || [] } catch { sources.value = [] }
  finally { loading.value = false }
}

function onFileChange(f, list) { newFiles.value = list.map(x => x.raw).filter(Boolean); fileList.value = list }
function onFileRemove(f, list) { newFiles.value = list.map(x => x.raw).filter(Boolean); fileList.value = list }

const pickedIds = computed(() => Object.keys(picked).filter(k => picked[k]).map(Number))
const canSubmit = computed(() => !!props.prevKbId && !running.value)

async function submit() {
  if (!canSubmit.value) return
  running.value = true
  try {
    let ids = [...pickedIds.value]
    // 先上传新资料拿 id
    if (newFiles.value.length) {
      statusText.value = '上传资料中…'
      const up = await publishApi.kbUploadSources(props.accountId, newFiles.value)
      const upIds = (up.items || []).map(x => x.id).filter(Boolean)
      ids = [...ids, ...upIds]
    }
    statusText.value = 'AI 扩充生成中（约 1-3 分钟）…'
    const r = await publishApi.kbExpand(props.prevKbId, { instruction: instruction.value.trim(), additionalSourceIds: ids, addCount: addCount.value })
    const taskId = r.task_id
    // 轮询任务
    const poll = async () => {
      const t = await publishApi.kbTaskStatus(taskId)
      if (t.status === 'done') {
        ElMessage.success(`AI 扩充完成，已生成新版本${t.version ? ' v' + t.version : ''}`)
        running.value = false
        emit('done', { accountId: props.accountId })
        emit('update:modelValue', false)
      } else if (t.status === 'failed') {
        ElMessage.error('扩充失败：' + (t.error || '未知错误'))
        running.value = false; statusText.value = ''
      } else {
        setTimeout(poll, 3000)
      }
    }
    setTimeout(poll, 3000)
  } catch (e) {
    ElMessage.error('启动失败：' + (e.response?.data?.error || e.message))
    running.value = false; statusText.value = ''
  }
}
</script>

<style scoped>
.ke { display: flex; flex-direction: column; gap: 16px; }
.ke-intro { font-size: 13px; color: #64748b; margin: 0; line-height: 1.6; }
.ke-block-h { font-size: 13px; font-weight: 600; color: #334155; margin-bottom: 8px; }
.ke-srcs { display: flex; flex-direction: column; gap: 4px; max-height: 180px; overflow-y: auto; margin-bottom: 10px;
  border: 1px solid #f1f5f9; border-radius: 8px; padding: 8px 10px; }
.ke-src { width: 100%; }
.ke-src-name { font-size: 13px; color: #1e293b; }
.ke-src-type { font-size: 11px; color: #94a3b8; margin-left: 6px; }
.ke-empty-src { font-size: 12.5px; color: #94a3b8; padding: 8px 0; }
.ke-row { display: flex; align-items: center; gap: 12px; }
.ke-row-l { font-size: 13px; font-weight: 600; color: #334155; }
.ke-row-tip { font-size: 12px; color: #94a3b8; }
.ke-foot-hint { font-size: 12px; color: #2563eb; margin-right: auto; }
</style>
