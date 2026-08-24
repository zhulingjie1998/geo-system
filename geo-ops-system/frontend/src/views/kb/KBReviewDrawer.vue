<template>
  <el-drawer
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    title="知识库审核" size="88%" direction="rtl" :destroy-on-close="true"
    @open="onOpen">
    <div v-loading="loading" class="kbr-wrap">
      <div v-if="!review" class="kbr-empty">未加载审核数据</div>
      <template v-else>
        <!-- 顶部说明条 -->
        <div class="kbr-bar">
          <div class="kbr-bar-left">
            <strong>知识库 v{{ review.version?.version }}</strong>
            <span class="kbr-hint">
              <template v-if="review.annotations.length">
                💡 已自动导入 AI 在生成知识库时标记的 <strong>{{ review.annotations.length }}</strong> 条待确认事项;在左侧选中文字可继续手动追加
              </template>
              <template v-else>
                在左侧正文中选中一段文字 → 选择类型 + 填写理由,即可标注待确认事项
              </template>
            </span>
          </div>
          <div class="kbr-bar-right">
            <el-tag v-for="c in CATS" :key="c.value" :style="{ background: c.color, color: '#fff', border: 'none', marginLeft: '6px' }">
              {{ c.label }} {{ countByCat(c.value) }}
            </el-tag>
          </div>
        </div>

        <div class="kbr-body">
          <!-- 左：正文(纯文本 + 高亮 + 可选区) -->
          <div class="kbr-doc">
            <div ref="contentRef" class="kbr-content" @mouseup="onSelect" v-html="highlightedHtml"></div>
          </div>

          <!-- 右：批注列表 + 资料建议 + 定稿 -->
          <div class="kbr-side">
            <div class="kbr-side-sec">
              <div class="kbr-side-head">待确认事项 ({{ review.annotations.length }})</div>
              <div v-if="!review.annotations.length" class="kbr-side-empty">还没有标注。在左侧选中文字开始。</div>
              <div v-for="a in review.annotations" :key="a.id" class="kbr-anno-card"
                   :style="{ borderLeftColor: catColor(a.category) }">
                <div class="kbr-anno-top">
                  <el-tag size="small" :style="{ background: catColor(a.category), color: '#fff', border: 'none' }">
                    {{ catLabel(a.category) }}
                  </el-tag>
                  <el-button text type="danger" size="small" @click="delAnno(a.id)">删除</el-button>
                </div>
                <div class="kbr-anno-quote">「{{ a.quote }}」</div>
                <div class="kbr-anno-reason">{{ a.reason || '（无理由说明）' }}</div>
              </div>
            </div>

            <div class="kbr-side-sec">
              <div class="kbr-side-head">建议客户提供的资料 ({{ materials.length }})</div>
              <div v-for="(m, i) in materials" :key="i" class="kbr-mat-row">
                <el-input v-model="m.name" size="small" placeholder="资料名称(如:近三月销量数据)" style="flex:1" />
                <el-input v-model="m.note" size="small" placeholder="备注(选填)" style="flex:1" />
                <el-button text type="danger" size="small" @click="materials.splice(i,1)">×</el-button>
              </div>
              <div class="kbr-mat-actions">
                <el-button size="small" @click="materials.push({ name: '', note: '' })">+ 添加一条</el-button>
                <el-button size="small" type="primary" plain @click="saveMaterials">保存资料建议</el-button>
              </div>
            </div>

            <div class="kbr-side-sec">
              <div class="kbr-side-head">定稿与分享</div>
              <el-button type="primary" :loading="finalizing" @click="finalize">
                {{ review.status === 'finalized' ? '重新生成分享链接' : '定稿并生成分享链接' }}
              </el-button>
              <div v-if="shareUrl" class="kbr-share">
                <el-input :model-value="shareUrl" readonly size="small">
                  <template #append>
                    <el-button @click="copyShare">复制</el-button>
                  </template>
                </el-input>
                <a :href="shareUrl" target="_blank" class="kbr-share-open">在新标签打开预览 ↗</a>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- 添加批注弹窗 -->
    <el-dialog v-model="addOpen" title="标注待确认事项" width="480px" append-to-body>
      <div class="kbr-add-quote">「{{ pending.quote }}」</div>
      <el-form label-position="top">
        <el-form-item label="类型">
          <el-radio-group v-model="pending.category">
            <el-radio-button v-for="c in CATS" :key="c.value" :value="c.value">{{ c.label }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="理由 / 需要客户确认什么">
          <el-input v-model="pending.reason" type="textarea" :rows="3"
                    placeholder="例:此处销量数据需客户提供最新口径;此宣传措辞需确认是否合规" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addOpen = false">取消</el-button>
        <el-button type="primary" :loading="adding" @click="confirmAdd">保存批注</el-button>
      </template>
    </el-dialog>
  </el-drawer>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import kbApi, { KB_REVIEW_CATEGORIES, kbReviewCategoryLabel, kbReviewCategoryColor } from '@/api/knowledge'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  accountId: { type: [Number, String], default: null },
  kbVersionId: { type: [Number, String], default: null },
})
defineEmits(['update:modelValue'])

const CATS = KB_REVIEW_CATEGORIES
const catLabel = kbReviewCategoryLabel
const catColor = kbReviewCategoryColor

const loading = ref(false)
const review = ref(null)
const materials = ref([])
const contentRef = ref(null)
const finalizing = ref(false)

const content = computed(() => review.value?.version?.content || '')

function countByCat(v) {
  return (review.value?.annotations || []).filter(a => a.category === v).length
}

function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

// 正文纯文本 + 批注高亮(quote+occurrence 锚定,绕开 markdown 渲染坐标问题)
const highlightedHtml = computed(() => {
  const text = content.value
  const annos = review.value?.annotations || []
  if (!text) return ''
  const spans = []
  for (const a of annos) {
    const q = a.quote || ''
    if (!q) continue
    let from = 0, count = 0, found = -1
    const occ = a.occurrence || 0
    while (true) {
      const p = text.indexOf(q, from)
      if (p === -1) break
      if (count === occ) { found = p; break }
      count++; from = p + q.length
    }
    if (found === -1) { const p = text.indexOf(q); if (p === -1) continue; found = p }
    spans.push({ start: found, end: found + q.length, anno: a })
  }
  spans.sort((x, y) => x.start - y.start)
  let html = '', cursor = 0
  for (const s of spans) {
    if (s.start < cursor) continue
    html += escapeHtml(text.slice(cursor, s.start))
    const cat = s.anno.category
    const tip = `${catLabel(cat)}：${(s.anno.reason || '').replace(/"/g, '&quot;')}`
    html += `<mark class="kbr-mark kbr-mark-${cat}" title="${escapeHtml(tip)}">${escapeHtml(text.slice(s.start, s.end))}</mark>`
    cursor = s.end
  }
  html += escapeHtml(text.slice(cursor))
  return html
})

const shareUrl = computed(() => {
  if (!review.value?.share_token || review.value.status !== 'finalized') return ''
  return `${location.origin}/share/kb-review/${props.accountId}/${review.value.id}?token=${review.value.share_token}`
})

async function onOpen() {
  if (!props.accountId || !props.kbVersionId) {
    ElMessage.warning('缺少客户或版本信息'); return
  }
  loading.value = true
  try {
    review.value = await kbApi.reviewStart(props.accountId, props.kbVersionId)
    materials.value = (review.value.material_suggestions || []).map(m => ({ ...m }))
  } catch (e) {
    ElMessage.error('加载审核失败：' + (e.message || e))
  } finally {
    loading.value = false
  }
}

// 选区 → 计算 quote + occurrence(选区前该片段出现次数,range.toString 不受 mark 影响)
const addOpen = ref(false)
const adding = ref(false)
const pending = ref({ quote: '', occurrence: 0, category: 'numeric', reason: '' })

function onSelect() {
  const sel = window.getSelection()
  if (!sel || sel.isCollapsed) return
  const quote = sel.toString().trim()
  if (!quote || !contentRef.value) return
  const range = sel.getRangeAt(0)
  if (!contentRef.value.contains(range.commonAncestorContainer)) return
  const pre = document.createRange()
  pre.selectNodeContents(contentRef.value)
  pre.setEnd(range.startContainer, range.startOffset)
  const before = pre.toString()
  const occurrence = before.split(quote).length - 1
  pending.value = { quote, occurrence: Math.max(0, occurrence), category: 'numeric', reason: '' }
  addOpen.value = true
}

async function confirmAdd() {
  adding.value = true
  try {
    await kbApi.reviewAddAnno(review.value.id, {
      category: pending.value.category,
      quote: pending.value.quote,
      occurrence: pending.value.occurrence,
      reason: pending.value.reason,
    })
    review.value = await kbApi.reviewGet(review.value.id)
    addOpen.value = false
  } catch (e) {
    ElMessage.error('保存批注失败：' + (e.message || e))
  } finally {
    adding.value = false
  }
}

async function delAnno(annoId) {
  try {
    await kbApi.reviewDelAnno(annoId)
    review.value = await kbApi.reviewGet(review.value.id)
  } catch (e) {
    ElMessage.error('删除失败：' + (e.message || e))
  }
}

async function saveMaterials() {
  try {
    review.value = await kbApi.reviewMaterials(review.value.id,
      materials.value.filter(m => (m.name || '').trim()))
    materials.value = (review.value.material_suggestions || []).map(m => ({ ...m }))
    ElMessage.success('资料建议已保存')
  } catch (e) {
    ElMessage.error('保存失败：' + (e.message || e))
  }
}

async function finalize() {
  finalizing.value = true
  try {
    // 先存一次资料建议,避免漏存
    await kbApi.reviewMaterials(review.value.id, materials.value.filter(m => (m.name || '').trim()))
    review.value = await kbApi.reviewFinalize(review.value.id)
    materials.value = (review.value.material_suggestions || []).map(m => ({ ...m }))
    ElMessage.success('已定稿,分享链接已生成')
  } catch (e) {
    ElMessage.error('定稿失败：' + (e.message || e))
  } finally {
    finalizing.value = false
  }
}

function copyShare() {
  navigator.clipboard?.writeText(shareUrl.value)
  ElMessage.success('已复制分享链接')
}
</script>

<style scoped>
.kbr-wrap { height: 100%; display: flex; flex-direction: column; }
.kbr-empty { padding: 40px; text-align: center; color: #9ca3af; }
.kbr-bar { display: flex; justify-content: space-between; align-items: center; padding: 8px 14px;
  background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 10px; flex-wrap: wrap; gap: 8px; }
.kbr-hint { color: #6b7280; font-size: 13px; margin-left: 10px; }
.kbr-body { display: flex; gap: 14px; flex: 1; min-height: 0; }
.kbr-doc { flex: 1.6; min-width: 0; border: 1px solid #e5e7eb; border-radius: 8px; overflow: auto; background: #fff; }
.kbr-content { padding: 18px 22px; white-space: pre-wrap; word-break: break-word; line-height: 1.85;
  font-size: 14px; color: #1f2937; font-family: ui-sans-serif, system-ui, sans-serif; user-select: text; }
.kbr-side { flex: 1; min-width: 320px; max-width: 420px; overflow: auto; display: flex; flex-direction: column; gap: 14px; }
.kbr-side-sec { border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; background: #fff; }
.kbr-side-head { font-weight: 600; color: #111827; margin-bottom: 10px; font-size: 14px; }
.kbr-side-empty { color: #9ca3af; font-size: 13px; }
.kbr-anno-card { border: 1px solid #f1f5f9; border-left: 4px solid #ccc; border-radius: 6px;
  padding: 8px 10px; margin-bottom: 8px; background: #fafafa; }
.kbr-anno-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.kbr-anno-quote { font-size: 13px; color: #374151; background: #fff; padding: 4px 6px; border-radius: 4px; margin-bottom: 4px; }
.kbr-anno-reason { font-size: 13px; color: #6b7280; }
.kbr-mat-row { display: flex; gap: 6px; align-items: center; margin-bottom: 6px; }
.kbr-mat-actions { display: flex; gap: 8px; margin-top: 6px; }
.kbr-share { margin-top: 10px; }
.kbr-share-open { display: inline-block; margin-top: 6px; font-size: 13px; color: #2563eb; }
.kbr-add-quote { background: #f8fafc; padding: 10px; border-radius: 6px; margin-bottom: 14px;
  color: #374151; font-size: 14px; border: 1px solid #e5e7eb; }
/* 三色高亮(与现有 kb-warn 风格一致) */
:deep(.kbr-mark) { padding: 1px 2px; border-radius: 3px; cursor: help; }
:deep(.kbr-mark-numeric) { background: #fde68a; }
:deep(.kbr-mark-discrepancy) { background: #fecaca; }
:deep(.kbr-mark-promotion) { background: #ddd6fe; }
</style>
