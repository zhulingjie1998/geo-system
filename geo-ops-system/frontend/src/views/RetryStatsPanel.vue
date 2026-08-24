<template>
  <div class="rs-wrap">
    <!-- 时间范围工具栏 -->
    <div class="rs-toolbar">
      <div class="rs-toolbar-left">
        <el-radio-group v-model="rsRange" size="default" @change="onRangePresetChange">
          <el-radio-button :label="1">今天</el-radio-button>
          <el-radio-button :label="3">近 3 天</el-radio-button>
          <el-radio-button :label="7">近 7 天</el-radio-button>
          <el-radio-button :label="14">近 14 天</el-radio-button>
          <el-radio-button :label="30">近 30 天</el-radio-button>
        </el-radio-group>
        <span class="rs-sep">或</span>
        <el-date-picker
          v-model="rsCustomRange"
          type="daterange"
          range-separator="→"
          start-placeholder="自定义起"
          end-placeholder="自定义止"
          value-format="YYYY-MM-DD"
          size="default"
          unlink-panels
          @change="onCustomRangeChange"
        />
      </div>
      <div class="rs-toolbar-right">
        <span class="rs-meta">{{ rsRangeLabel }}</span>
        <el-button :icon="Refresh" plain size="default" @click="loadRetryStats" :loading="rsLoading">刷新</el-button>
      </div>
    </div>

    <!-- KPI 概览 -->
    <div class="rs-kpis">
      <div class="rs-kpi rs-kpi-blue">
        <div class="rs-kpi-icon">📊</div>
        <div class="rs-kpi-body">
          <div class="rs-kpi-label">总查询</div>
          <div class="rs-kpi-val">{{ rsTotalAll.toLocaleString() }}</div>
          <div class="rs-kpi-sub">{{ retryStats.length }} 个模型</div>
        </div>
      </div>
      <div class="rs-kpi" :class="rsTrueRate >= 80 ? 'rs-kpi-green' : (rsTrueRate >= 60 ? 'rs-kpi-amber' : 'rs-kpi-red')">
        <div class="rs-kpi-icon">{{ rsTrueRate >= 80 ? '✓' : (rsTrueRate >= 60 ? '⚠' : '✗') }}</div>
        <div class="rs-kpi-body">
          <div class="rs-kpi-label">真一次过率</div>
          <div class="rs-kpi-val">{{ rsTrueRate }}<small>%</small></div>
          <div class="rs-kpi-sub">{{ rsTrueOk.toLocaleString() }} / {{ rsTotalAll.toLocaleString() }}</div>
        </div>
      </div>
      <div class="rs-kpi" :class="rsRescueAll > 0 ? 'rs-kpi-purple' : 'rs-kpi-gray'">
        <div class="rs-kpi-icon">🛟</div>
        <div class="rs-kpi-body">
          <div class="rs-kpi-label">跨行救援</div>
          <div class="rs-kpi-val">{{ rsRescueAll.toLocaleString() }}</div>
          <div class="rs-kpi-sub">sweep {{ rsSweep }} · morning {{ rsMorning }} · manual {{ rsManual }}</div>
        </div>
      </div>
      <div class="rs-kpi" :class="rsAlertModels > 0 ? 'rs-kpi-red' : 'rs-kpi-green'">
        <div class="rs-kpi-icon">{{ rsAlertModels > 0 ? '🔴' : '🟢' }}</div>
        <div class="rs-kpi-body">
          <div class="rs-kpi-label">需关注模型</div>
          <div class="rs-kpi-val">{{ rsAlertModels }}</div>
          <div class="rs-kpi-sub">真一次过 &lt; 50% 或 五次以上 &gt; 3%</div>
        </div>
      </div>
    </div>

    <!-- 指标说明卡 -->
    <div class="rs-explain" :class="{ collapsed: rsExplainCollapsed }">
      <div class="rs-explain-head" @click="rsExplainCollapsed = !rsExplainCollapsed">
        <span>📖 指标说明 · 6 桶严格互斥,加起来等于「总数」</span>
        <el-icon :size="12"><ArrowDown :class="{ flipped: rsExplainCollapsed }" /></el-icon>
      </div>
      <div v-show="!rsExplainCollapsed" class="rs-explain-body">
        <div class="rs-formula">
          <code>总数 = 真一次过 + 二次救 + 三次救 + 三次以上救 + 跨行救援 + 终败</code>
        </div>
        <ul class="rs-meta-list">
          <li><b class="dot-good">真一次过</b> — <code>rescue_round=initial</code> 且 <code>attempt=1</code> 且成功(主循环第一次就拿到结果,最理想)</li>
          <li><b class="dot-2">二次救</b> — 主循环 <code>attempt=2</code> 成功(第一次失败,程序立刻 2.5–3.5 秒后重试,这次成功)</li>
          <li><b class="dot-3">三次救</b> — 主循环 <code>attempt=3</code> 成功</li>
          <li><b class="dot-4">三次以上救</b> — 主循环 <code>attempt≥4</code> 成功(其中「五次以上」额外标红显示)</li>
          <li><b class="dot-rescue">跨行救援</b> — 主循环未救回,由<b>其他机制</b>重新跑一遍才成功的查询。包含 3 种来源:
            <ul class="rs-sub-list">
              <li><span class="rs-rescue-tag rs-rescue-sweep">sweep</span>任务跑完主循环立刻自动扫剩下的失败 pair 再跑一次(发生在任务结束前几分钟)</li>
              <li><span class="rs-rescue-tag rs-rescue-morning">morning</span>每天 <code>07:00</code> 凌晨定时扫昨夜没救回来的 pair 重跑</li>
              <li><span class="rs-rescue-tag rs-rescue-manual">manual</span>运营在「查词管理」点「重试失败」按钮手动触发</li>
            </ul>
          </li>
          <li><b class="dot-bad">终败</b> — 上面所有救援都失败,<code>success=0</code>(用户拿不到结果)</li>
        </ul>
      </div>
    </div>

    <!-- 主表 -->
    <div class="rs-panel">
      <div v-if="rsLoading" class="rs-loading">
        <el-icon class="rotating" :size="22"><Loading /></el-icon>
        <span style="margin-left:8px">加载中…</span>
      </div>
      <div v-else-if="!retryStats.length" class="rs-empty">
        <el-icon :size="36"><InfoFilled /></el-icon>
        <div style="margin-top:10px">该范围内没有数据</div>
      </div>
      <div v-else>
        <div class="rs-table">
          <div class="rs-row rs-header-row">
            <span class="rs-cell rs-model">模型 / 平台</span>
            <span class="rs-cell rs-num">总数</span>
            <span class="rs-cell rs-num"><span class="dot dot-good"></span>真一次过</span>
            <span class="rs-cell rs-num"><span class="dot dot-2"></span>二次救</span>
            <span class="rs-cell rs-num"><span class="dot dot-3"></span>三次救</span>
            <span class="rs-cell rs-num"><span class="dot dot-4"></span>三次以上救</span>
            <span class="rs-cell rs-num"><span class="dot dot-rescue"></span>跨行救援</span>
            <span class="rs-cell rs-num"><span class="dot dot-bad"></span>终败</span>
            <span class="rs-cell rs-bar-col">分布</span>
            <span class="rs-cell rs-check-col" title="6 桶之和应等于总数">校验</span>
          </div>
          <div v-for="p in retryStats" :key="p.platform+'-'+p.model" class="rs-row">
            <span class="rs-cell rs-model">
              <span class="rs-model-tag" :data-model="p.model">{{ p.model }}</span>
              <small class="rs-plat">{{ p.platform }}</small>
            </span>
            <span class="rs-cell rs-num">
              <span class="rs-num-main">{{ p.total.toLocaleString() }}</span>
            </span>
            <span class="rs-cell rs-num">
              <span class="rs-pct-pill" :class="rsRateClass(p.buckets.trueOneShot.pct)">
                {{ p.buckets.trueOneShot.pct }}%
              </span>
              <small class="rs-cnt">{{ p.buckets.trueOneShot.count.toLocaleString() }}</small>
            </span>
            <span class="rs-cell rs-num">
              <span class="rs-num-main">{{ p.buckets.initRetry2.count }}</span>
              <small class="rs-cnt">{{ p.buckets.initRetry2.pct }}%</small>
            </span>
            <span class="rs-cell rs-num">
              <span class="rs-num-main">{{ p.buckets.initRetry3.count }}</span>
              <small class="rs-cnt">{{ p.buckets.initRetry3.pct }}%</small>
            </span>
            <span class="rs-cell rs-num">
              <span class="rs-num-main" :class="{ 'rs-alert-text': p.buckets.initRetryGt3.pct > 10 }">
                {{ p.buckets.initRetryGt3.count }}
              </span>
              <small class="rs-cnt">
                {{ p.buckets.initRetryGt3.pct }}%
                <span v-if="p.initRetryGt5.count > 0" class="rs-sub-warn"
                      :title="`其中 attempt≥5 的有 ${p.initRetryGt5.count} 条(${p.initRetryGt5.pct}%)`">
                  · 5+ {{ p.initRetryGt5.count }}
                </span>
              </small>
            </span>
            <span class="rs-cell rs-num">
              <span class="rs-num-main" :class="{ 'rs-rescue-text': p.buckets.rescue.count > 0 }">
                {{ p.buckets.rescue.count }}
              </span>
              <small class="rs-cnt">
                {{ p.buckets.rescue.pct }}%
                <span v-if="p.buckets.rescue.count > 0" class="rs-rescue-detail">
                  <template v-if="p.rescueBreakdown.sweep.count">· sweep {{ p.rescueBreakdown.sweep.count }}</template>
                  <template v-if="p.rescueBreakdown.morningRetry.count">· morn {{ p.rescueBreakdown.morningRetry.count }}</template>
                  <template v-if="p.rescueBreakdown.manualRetry.count">· man {{ p.rescueBreakdown.manualRetry.count }}</template>
                </span>
              </small>
            </span>
            <span class="rs-cell rs-num">
              <span class="rs-num-main" :class="{ 'rs-alert-text': p.buckets.finalFail.count > 0 }">
                {{ p.buckets.finalFail.count }}
              </span>
              <small class="rs-cnt">{{ p.buckets.finalFail.pct }}%</small>
            </span>
            <span class="rs-cell rs-bar-col">
              <span class="rs-bar">
                <span class="rs-seg seg-one"    :style="{ flex: p.buckets.trueOneShot.count }"  :title="`真一次过 ${p.buckets.trueOneShot.count}`"></span>
                <span class="rs-seg seg-two"    :style="{ flex: p.buckets.initRetry2.count }"   :title="`二次救 ${p.buckets.initRetry2.count}`"></span>
                <span class="rs-seg seg-three"  :style="{ flex: p.buckets.initRetry3.count }"   :title="`三次救 ${p.buckets.initRetry3.count}`"></span>
                <span class="rs-seg seg-four"   :style="{ flex: p.buckets.initRetryGt3.count }" :title="`三次以上救 ${p.buckets.initRetryGt3.count}`"></span>
                <span class="rs-seg seg-rescue" :style="{ flex: p.buckets.rescue.count }"       :title="`跨行救援 ${p.buckets.rescue.count}`"></span>
                <span class="rs-seg seg-bad"    :style="{ flex: p.buckets.finalFail.count }"    :title="`终败 ${p.buckets.finalFail.count}`"></span>
              </span>
            </span>
            <span class="rs-cell rs-check-col">
              <span v-if="p.bucketsValid" class="rs-check rs-check-ok" :title="`${p.bucketsSum} = ${p.total}`">✓</span>
              <span v-else class="rs-check rs-check-bad" :title="`${p.bucketsSum} ≠ ${p.total}`">✗ {{ p.bucketsSum }}/{{ p.total }}</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { Refresh, Loading, InfoFilled, ArrowDown } from '@element-plus/icons-vue'

const retryStats = ref([])
const rsRange = ref(7)
const rsCustomRange = ref(null)
const rsLoading = ref(false)
const rsExplainCollapsed = ref(false)

const rsRangeLabel = computed(() => {
  if (rsCustomRange.value && rsCustomRange.value.length === 2) {
    return `${rsCustomRange.value[0]} → ${rsCustomRange.value[1]}`
  }
  return rsRange.value === 1 ? '今天' : `近 ${rsRange.value} 天`
})
const rsTotalAll = computed(() => retryStats.value.reduce((s, p) => s + p.total, 0))
const rsTrueOk   = computed(() => retryStats.value.reduce((s, p) => s + (p.buckets?.trueOneShot?.count || 0), 0))
const rsTrueRate = computed(() => rsTotalAll.value ? Math.round(rsTrueOk.value / rsTotalAll.value * 100) : 0)
const rsSweep    = computed(() => retryStats.value.reduce((s, p) => s + (p.rescueBreakdown?.sweep?.count || 0), 0))
const rsMorning  = computed(() => retryStats.value.reduce((s, p) => s + (p.rescueBreakdown?.morningRetry?.count || 0), 0))
const rsManual   = computed(() => retryStats.value.reduce((s, p) => s + (p.rescueBreakdown?.manualRetry?.count || 0), 0))
const rsRescueAll = computed(() => rsSweep.value + rsMorning.value + rsManual.value)
const rsAlertModels = computed(() => retryStats.value.filter(p =>
  (p.buckets?.trueOneShot?.pct ?? 0) < 50 || (p.initRetryGt5?.pct ?? 0) > 3
).length)
function rsRateClass(pct) {
  if (pct >= 80) return 'rs-pct-good'
  if (pct >= 60) return 'rs-pct-mid'
  if (pct >= 40) return 'rs-pct-warn'
  return 'rs-pct-bad'
}
function onRangePresetChange() {
  rsCustomRange.value = null
  loadRetryStats()
}
function onCustomRangeChange(v) {
  if (v && v.length === 2) loadRetryStats()
  else if (!v) loadRetryStats()
}
async function loadRetryStats() {
  rsLoading.value = true
  try {
    const params = (rsCustomRange.value && rsCustomRange.value.length === 2)
      ? { start_date: rsCustomRange.value[0], end_date: rsCustomRange.value[1] }
      : { days: rsRange.value }
    const r = await axios.get('/api/search/retry-stats', { params, withCredentials: true })
    retryStats.value = (r.data?.platforms || []).filter(p => p.total >= 5)
  } catch (e) {
    retryStats.value = []
  } finally {
    rsLoading.value = false
  }
}

onMounted(loadRetryStats)
</script>

<style scoped>
.rs-wrap { display: flex; flex-direction: column; }
.rotating { animation: rs-rotate 1.2s linear infinite; }
@keyframes rs-rotate { to { transform: rotate(360deg); } }

.rs-toolbar {
  display: flex; justify-content: space-between; align-items: center; gap: 14px;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
  padding: 12px 16px; margin-bottom: 14px; flex-wrap: wrap;
}
.rs-toolbar-left { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.rs-toolbar-right { display: flex; align-items: center; gap: 12px; }
.rs-sep { color: #94a3b8; font-size: 12px; }
.rs-meta { font-size: 12.5px; color: #4f46e5; font-weight: 600; background: #eef2ff; padding: 4px 10px; border-radius: 999px; }

.rs-kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 14px; }
@media (max-width: 1100px) { .rs-kpis { grid-template-columns: repeat(2, 1fr); } }
.rs-kpi { display: flex; align-items: center; gap: 12px; background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 16px; position: relative; overflow: hidden; transition: all .15s; }
.rs-kpi:hover { box-shadow: 0 4px 16px -8px rgba(15,23,42,.15); transform: translateY(-1px); }
.rs-kpi::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; }
.rs-kpi-blue::before  { background: linear-gradient(180deg, #3b82f6, #6366f1); }
.rs-kpi-green::before { background: linear-gradient(180deg, #10b981, #14b8a6); }
.rs-kpi-amber::before { background: linear-gradient(180deg, #f59e0b, #f97316); }
.rs-kpi-red::before   { background: linear-gradient(180deg, #dc2626, #b91c1c); }
.rs-kpi-purple::before{ background: linear-gradient(180deg, #8b5cf6, #6d28d9); }
.rs-kpi-gray::before  { background: linear-gradient(180deg, #94a3b8, #64748b); }
.rs-kpi-icon { font-size: 24px; flex-shrink: 0; }
.rs-kpi-body { flex: 1; min-width: 0; }
.rs-kpi-label { font-size: 11.5px; color: #64748b; font-weight: 600; }
.rs-kpi-val { font-size: 26px; font-weight: 800; color: #0f172a; font-variant-numeric: tabular-nums; line-height: 1.1; }
.rs-kpi-val small { font-size: 14px; color: #64748b; font-weight: 600; margin-left: 1px; }
.rs-kpi-sub { font-size: 11px; color: #94a3b8; margin-top: 2px; }

.rs-panel { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 16px; }
.rs-loading, .rs-empty { padding: 60px; text-align: center; color: #94a3b8; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.rs-table { display: flex; flex-direction: column; gap: 2px; }
.rs-row { display: grid; grid-template-columns: 130px 70px 110px 80px 80px 110px 130px 80px 1.2fr 60px; gap: 10px; align-items: center; font-size: 12.5px; padding: 8px 10px; border-radius: 8px; transition: background .12s; }
.rs-row:not(.rs-header-row):hover { background: #f8fafc; }
.rs-header-row { font-size: 11px; color: #64748b; font-weight: 700; text-transform: uppercase; letter-spacing: .02em; border-bottom: 1px solid #e2e8f0; padding: 10px 10px; }
.rs-cell.rs-model { display: flex; align-items: center; gap: 6px; min-width: 0; }
.rs-model-tag { font-weight: 700; color: #0f172a; font-size: 13px; padding: 2px 8px; border-radius: 6px; background: #f1f5f9; }
.rs-model-tag[data-model="douBao"]   { background: #fee2e2; color: #b91c1c; }
.rs-model-tag[data-model="deepseek"] { background: #dbeafe; color: #1e40af; }
.rs-model-tag[data-model="yuanBao"]  { background: #fef3c7; color: #92400e; }
.rs-model-tag[data-model="kimi"]     { background: #ede9fe; color: #6d28d9; }
.rs-model-tag[data-model="tongYi"]   { background: #dcfce7; color: #166534; }
.rs-model-tag[data-model="wenXin"]   { background: #cffafe; color: #155e75; }
.rs-plat { color: #94a3b8; font-size: 10.5px; }
.rs-cell.rs-num { color: #475569; font-variant-numeric: tabular-nums; display: flex; flex-direction: column; gap: 1px; }
.rs-num-main { font-weight: 600; color: #0f172a; }
.rs-cnt { color: #94a3b8; font-size: 10.5px; }
.rs-alert-text { color: #b91c1c !important; font-weight: 700; }
.rs-pct-pill { display: inline-block; font-weight: 700; font-size: 12.5px; padding: 2px 10px; border-radius: 999px; font-variant-numeric: tabular-nums; }
.rs-pct-good { background: #dcfce7; color: #166534; }
.rs-pct-mid  { background: #fef9c3; color: #854d0e; }
.rs-pct-warn { background: #ffedd5; color: #c2410c; }
.rs-pct-bad  { background: #fee2e2; color: #b91c1c; }
.rs-bar { display: flex; height: 12px; border-radius: 999px; overflow: hidden; background: #f1f5f9; }
.rs-seg { transition: flex .15s; }
.rs-seg.seg-one { background: #10b981; }
.rs-seg.seg-two { background: #84cc16; }
.rs-seg.seg-three { background: #eab308; }
.rs-seg.seg-four { background: #f97316; }
.rs-seg.seg-bad { background: #dc2626; }
.rs-seg.seg-rescue { background: #8b5cf6; }
.rs-rescue-tag { display: inline-flex; align-items: center; gap: 3px; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-variant-numeric: tabular-nums; border: 1px solid transparent; }
.rs-rescue-sweep { background: #f5f3ff; color: #6d28d9; border-color: #ede9fe; }
.rs-rescue-morning { background: #fff7ed; color: #c2410c; border-color: #fed7aa; }
.rs-rescue-manual { background: #f0f9ff; color: #0369a1; border-color: #bae6fd; }
.rs-explain { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; margin-bottom: 14px; overflow: hidden; }
.rs-explain-head { display: flex; justify-content: space-between; align-items: center; padding: 11px 16px; cursor: pointer; font-size: 13px; font-weight: 600; color: #0f172a; background: linear-gradient(180deg, #fafbfc 0%, #fff 100%); }
.rs-explain-head:hover { background: #f8fafc; }
.rs-explain-head .flipped { transform: rotate(-90deg); transition: transform .15s; }
.rs-explain-body { padding: 4px 18px 14px; font-size: 12.5px; color: #475569; line-height: 1.7; }
.rs-formula { background: #f1f5f9; border-radius: 8px; padding: 8px 12px; margin: 6px 0 10px; font-size: 13px; color: #0f172a; }
.rs-formula code { background: transparent; padding: 0; font-weight: 600; }
.rs-meta-list { margin: 0; padding-left: 18px; }
.rs-meta-list > li { margin-bottom: 4px; }
.rs-meta-list code { background: #f1f5f9; padding: 1px 5px; border-radius: 3px; font-size: 11.5px; color: #475569; }
.rs-meta-list b { font-weight: 700; }
.rs-meta-list b.dot-good { color: #047857; }
.rs-meta-list b.dot-2    { color: #4d7c0f; }
.rs-meta-list b.dot-3    { color: #a16207; }
.rs-meta-list b.dot-4    { color: #c2410c; }
.rs-meta-list b.dot-rescue { color: #6d28d9; }
.rs-meta-list b.dot-bad  { color: #b91c1c; }
.rs-sub-list { margin: 4px 0 4px 0; padding-left: 18px; list-style: none; }
.rs-sub-list > li { margin-bottom: 3px; display: flex; align-items: baseline; gap: 6px; }
.rs-sub-list .rs-rescue-tag { flex-shrink: 0; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }
.dot-good   { background: #10b981; }
.dot-2      { background: #84cc16; }
.dot-3      { background: #eab308; }
.dot-4      { background: #f97316; }
.dot-rescue { background: #8b5cf6; }
.dot-bad    { background: #dc2626; }
.rs-rescue-text { color: #6d28d9; font-weight: 700; }
.rs-rescue-detail { color: #94a3b8; font-size: 10px; }
.rs-sub-warn { color: #b91c1c; font-weight: 700; margin-left: 2px; }
.rs-cell.rs-check-col { text-align: center; }
.rs-check { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: 50%; font-size: 13px; font-weight: 700; }
.rs-check.rs-check-ok  { background: #dcfce7; color: #166534; }
.rs-check.rs-check-bad { background: #fee2e2; color: #b91c1c; width: auto; padding: 0 6px; border-radius: 999px; font-size: 11px; }
</style>
