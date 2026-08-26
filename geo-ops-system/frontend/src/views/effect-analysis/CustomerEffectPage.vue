<template>
  <div class="customer-effect-page">
    <!-- 工具栏 -->
    <div class="cd-tools">
      <el-select v-model="selectedCustomerId" class="cd-pick" size="large" filterable placeholder="选择客户" @change="onCustomerChange">
        <el-option v-for="c in customers" :key="c.id" :label="c.company || c.name" :value="c.id" />
      </el-select>
      <div class="pb-fseg">
        <span class="pb-fseg-l">平台</span>
        <button v-for="p in platformOptions" :key="p" :class="['pb-fb', { on: selectedPlatform === p }]" @click="selectedPlatform = p">{{ p }}</button>
      </div>
      <div class="dcp">
        <span class="dcp-l">时间对比</span>
        <div class="pb-fseg dcp-seg">
          <button v-for="tc in timeCompareOptions" :key="tc.value" :class="['pb-fb', { on: timeCompare === tc.value }]" @click="timeCompare = tc.value">{{ tc.label }}</button>
        </div>
      </div>
      <el-date-picker v-if="timeCompare === 'custom'" v-model="dateA" type="date" size="large" placeholder="A 时间" value-format="YYYY-MM-DD" :disabled-date="disableDateA" />
      <span v-if="timeCompare === 'custom'" class="dcp-vs">vs</span>
      <el-date-picker v-if="timeCompare === 'custom'" v-model="dateB" type="date" size="large" placeholder="B 时间" value-format="YYYY-MM-DD" :disabled-date="disableDateB" />
      <span v-if="timeCompare === 'custom' && availableDates.length" class="dcp-count">共 {{ availableDates.length }} 个可选日</span>
      <el-button :icon="Refresh" @click="loadData" :loading="loading">刷新</el-button>
    </div>

    <!-- 数据内容（选择客户后显示） -->
    <template v-if="selectedCustomerId">

    <!-- 未选择客户时显示占位 -->
    <!-- 数据概览（按示例代码重做） -->
    <div class="cd-card cd-score" v-if="currentCustomer">
      <div class="cd-score-head">
        <div>
          <div class="cd-name">{{ currentCustomer.company || currentCustomer.name }}</div>
          <div class="cd-sub">
            <span class="cd-brand">{{ currentCustomer.brand || '丝涟' }} / {{ currentCustomer.brandEn || 'Sealy' }}</span>
            <span class="cd-owner">负责人 {{ currentCustomer.responsible || '马季冬' }}</span>
            <span class="cd-cmp">基准 <b>{{ dateA || today }}</b> · 较 <b>{{ dateB || prevDate }}</b></span>
          </div>
        </div>
        <span :class="['cd-h', scoreLevel.cls]">{{ scoreLevel.label }}</span>
      </div>
      <div class="cd-stat">
        <div class="cd-s hero"><b>{{ kpiData.coverageRate }}<i>%</i><span :class="['cd-d', kpiData.change >= 0 ? 'down' : 'up']">{{ kpiData.change >= 0 ? '▼' : '▲' }}{{ Math.abs(kpiData.change) }}</span></b><span>上榜率 · 较 {{ dateB || prevDate }}</span></div>
        <div class="cd-s"><b>{{ kpiData.top3Rate }}<i>%</i></b><span>TOP3 率</span></div>
        <div class="cd-s"><b>{{ kpiData.firstRate }}<i>%</i></b><span>首位率</span></div>
        <div class="cd-s"><b>{{ kpiData.citationRate }}<i>%</i></b><span>通用词率</span></div>
        <div class="cd-s"><b>{{ kpiData.onListCount }}</b><span>上榜词次</span></div>
      </div>
      <div class="cd-delta-strip">
        <span class="cd-ds-l">本期变动</span>
        <button class="cd-ds" @click="scrollToTab('onlist')"><b class="green">+{{ kpiData.change >= 0 ? kpiData.change : 0 }}</b> 新上榜</button>
        <button class="cd-ds" @click="scrollToTab('offline')"><b class="red">{{ offlineKeywords.length }}</b> 掉线</button>
        <button class="cd-ds" @click="scrollToTab('fluctuation')"><b class="green">▲{{ kpiData.rising }}</b> 上升</button>
        <button class="cd-ds" @click="scrollToTab('fluctuation')"><b class="red">▼{{ kpiData.falling }}</b> 下降</button>
      </div>
    </div>

    <!-- 上榜率 × 运营动作 组合图表 -->
    <div class="cd-card cd-aec-card">
      <div class="cd-card-h"><h4>上榜率 × 运营动作</h4><span class="cd-count">近 30 天 · 看你的发稿/生文有没有推动效果</span></div>
      <div class="aec" @mousemove="onAecHover" @mouseleave="aecHoverIdx = -1" ref="aecRef">
        <svg viewBox="0 0 800 210" preserveAspectRatio="none" class="aec-svg">
          <defs>
            <linearGradient id="aecAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#14b8a6" stop-opacity="0.25"/>
              <stop offset="100%" stop-color="#14b8a6" stop-opacity="0.02"/>
            </linearGradient>
            <filter id="aecGlow"><feGaussianBlur stdDeviation="2" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
          </defs>
          <!-- 上榜率面积 -->
          <path :d="aecAreaD" fill="url(#aecAreaGrad)" class="aec-area"/>
          <!-- 上榜率折线 -->
          <path :d="aecLineD" fill="none" stroke="#14b8a6" stroke-width="2" stroke-linejoin="round" filter="url(#aecGlow)" class="aec-line"/>
          <!-- 数据点 + tooltip -->
          <circle v-for="(v,i) in aecRates" :key="'ad'+i" :cx="8 + i * aecStepX" :cy="140 - v * aecScaleY" r="2.5" :class="['aec-dot', {active: aecHoverIdx === i}]">
            <title>{{ aecDates[i] }} · 上榜率 {{ v }}%</title>
          </circle>
          <!-- 分隔线 -->
          <line x1="8" y1="140" x2="792" y2="140" class="aec-sep"/>
          <!-- 生文/发稿柱状 -->
          <g v-for="(item,i) in aecActions" :key="'ab'+i">
            <rect v-if="item.draft > 0" :x="8 + i * aecStepX - 4" :y="194 - item.draft * aecBarScaleY" width="8" :height="item.draft * aecBarScaleY" class="aec-bar draft" rx="2">
              <title>{{ aecDates[i] }} · 生文 {{ item.draft }} 篇</title>
            </rect>
            <rect v-if="item.pub > 0" :x="8 + i * aecStepX - 4" :y="194 - item.pub * aecBarScaleY" width="8" :height="item.pub * aecBarScaleY" class="aec-bar pub" rx="2">
              <title>{{ aecDates[i] }} · 发稿 {{ item.pub }} 篇</title>
            </rect>
          </g>
        </svg>
        <!-- 悬浮 tooltip -->
        <div v-if="aecHoverIdx >= 0 && aecRates[aecHoverIdx] !== undefined" class="aec-tooltip" :style="aecTooltipStyle">
          <div class="aec-tt-date">{{ aecFullDates[aecHoverIdx] }}</div>
          <div class="aec-tt-rate">上榜率 <b>{{ aecRates[aecHoverIdx] }}%</b></div>
          <div v-if="aecActions[aecHoverIdx]?.draft" class="aec-tt-action">生文 {{ aecActions[aecHoverIdx].draft }} 篇</div>
          <div v-if="aecActions[aecHoverIdx]?.pub" class="aec-tt-action">发稿 {{ aecActions[aecHoverIdx].pub }} 篇</div>
        </div>
        <div class="aec-x"><span>{{ aecDates[0] }}</span><span>{{ aecDates[aecDates.length-1] }}</span></div>
        <div class="aec-legend">
          <span><i class="rate"></i>上榜率</span>
          <span><i class="draft"></i>生文</span>
          <span><i class="pub"></i>发稿/投放</span>
        </div>
      </div>
    </div>

    <!-- 各平台上榜率 -->
    <div class="cd-card cd-platform-card">
      <div class="cd-card-h"><h4>各平台上榜率</h4><span class="cd-count">强弱一览</span></div>
      <div class="cd-pbars">
        <div v-for="pp in platformData" :key="pp.name" class="cd-pbar">
          <PlatformIcon :name="pp.name" :size="18" />
          <span class="cd-pbar-n">{{ pp.name }}</span>
          <div class="cd-pbar-t"><span class="cd-pbar-f" :class="pp.level" :style="{ width: pp.rate + '%' }"></span></div>
          <b class="cd-pbar-r">{{ pp.rate }}%</b>
          <span class="cd-pbar-c">{{ pp.found }}/{{ pp.total }}</span>
        </div>
      </div>
    </div>

    <!-- 关键词明细（Tab切换） -->
    <div class="cd-card cd-detail-card" ref="detailCardRef">
      <div class="cd-tabs">
        <button class="cd-tab" :class="{ on: activeTab === 'onlist' }" @click="activeTab = 'onlist'">上榜词 <i>{{ onListKeywords.length }}</i></button>
        <button class="cd-tab" :class="{ on: activeTab === 'offline' }" @click="activeTab = 'offline'">掉线词 <i class="warn">{{ offlineKeywords.length }}</i></button>
        <button class="cd-tab" :class="{ on: activeTab === 'fluctuation' }" @click="activeTab = 'fluctuation'">排名波动 <i>{{ rankFluctuations.length }}</i></button>
        <el-button size="small" plain class="cd-tab-r" :icon="Download" @click="exportTable(activeTab)">导出</el-button>
      </div>

      <!-- 上榜词表格 -->
      <div v-show="activeTab === 'onlist'" class="cd-tbl-wrap">
        <table class="cd-tbl">
          <thead><tr><th class="l">提示词</th><th>平台</th><th>排名</th><th>词类型</th><th>截图</th></tr></thead>
          <tbody>
            <tr v-for="row in onListKeywords" :key="row.keyword + row.platform">
              <td class="l cd-kw">{{ row.keyword }}</td>
              <td><PlatformIcon :name="row.platform" :size="18" /></td>
              <td><span class="cd-rank" :class="{ first: row.rank === 1, top3: row.rank <= 3 }">#{{ row.rank }}</span></td>
              <td><span class="cd-wt" :class="row.typeClass">{{ row.type }}</span></td>
              <td><button class="cd-shot"><el-icon><Picture /></el-icon>查看</button></td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 掉线词表格 -->
      <div v-show="activeTab === 'offline'" class="cd-tbl-wrap">
        <table class="cd-tbl">
          <thead><tr><th class="l">提示词</th><th>平台</th><th>上次排名</th><th>状态</th><th>截图</th></tr></thead>
          <tbody>
            <tr v-for="row in offlineKeywords" :key="row.keyword + row.platform">
              <td class="l cd-kw">{{ row.keyword }}</td>
              <td><PlatformIcon :name="row.platform" :size="18" /></td>
              <td><span class="cd-rank">#{{ row.lastRank }}</span></td>
              <td><span class="cd-fell">已掉线</span></td>
              <td><span class="cd-empty-s">—</span></td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 排名波动表格 -->
      <div v-show="activeTab === 'fluctuation'" class="cd-tbl-wrap">
        <table class="cd-tbl">
          <thead><tr><th class="l">提示词</th><th>平台</th><th>名次变化</th></tr></thead>
          <tbody>
            <tr v-for="row in rankFluctuations" :key="row.keyword + row.platform">
              <td class="l cd-kw">{{ row.keyword }}</td>
              <td><PlatformIcon :name="row.platform" :size="18" /></td>
              <td><span class="cd-chg" :class="row.change >= 0 ? 'up' : 'down'">#{{ row.fromRank }} → #{{ row.toRank }} <b>{{ row.change >= 0 ? '↑' + row.change : '↓' + Math.abs(row.change) }}</b></span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    </template>

    <!-- 未选择客户时的占位提示 -->
    <div v-if="!selectedCustomerId" class="cd-empty-state">
      <el-icon :size="48" color="#cbd5e1"><UserFilled /></el-icon>
      <p>请先选择一个客户</p>
      <span>从上方下拉框中选择客户，查看详细效果分析数据</span>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { Refresh, Download, Picture, UserFilled } from '@element-plus/icons-vue'
import api from '@/api'
import PlatformIcon from '@/components/PlatformIcon.vue'

const activeTab = ref('onlist')
const aecRef = ref(null)
const detailCardRef = ref(null)

const PLATFORMS = ['ChatGPT', 'Gemini', 'Google AIO', 'Google AIM', 'Perplexity', 'Copilot']
const platformOptions = computed(() => ['全部', ...PLATFORMS])

const timeCompareOptions = [
  { value: 'last2', label: '最近两次' },
  { value: 'week', label: '周对比' },
  { value: 'month', label: '月对比' },
  { value: 'custom', label: '自定义' },
]

const loading = ref(false)
const customers = ref([])
const selectedCustomerId = ref(null)
const selectedPlatform = ref('全部')
const timeCompare = ref('last2')
const dateA = ref(null)
const dateB = ref(null)
const availableDates = ref([])

function disableDateA(date) {
  const s = date.toISOString().slice(0, 10)
  return !availableDates.value.includes(s)
}
function disableDateB(date) {
  const s = date.toISOString().slice(0, 10)
  return !availableDates.value.includes(s) || s === dateA.value
}
const today = new Date().toISOString().slice(0, 10)
const prevDate = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10)

const currentCustomer = computed(() => customers.value.find(c => c.id === selectedCustomerId.value))

// 评级徽章逻辑：基于上榜率
// ≥80% 优(绿色) | ≥50% 良(黄色) | >0% 需关注(红色) | 无数据(灰色)
const scoreLevel = computed(() => {
  const r = kpiData.coverageRate
  if (r === null || r === undefined || selectedCustomerId.value === null) return { label: '无数据', cls: 'none' }
  if (r >= 80) return { label: '优', cls: 'good' }
  if (r >= 50) return { label: '良', cls: 'ok' }
  return { label: '需关注', cls: 'bad' }
})

const kpiData = reactive({
  coverageRate: 0, top3Rate: 0, firstRate: 0,
  citationRate: 0, onListCount: 0, offlineCount: 0,
  change: 0, rising: 0, falling: 0,
})

const platformData = ref([])
const onListKeywords = ref([])
const offlineKeywords = ref([])
const rankFluctuations = ref([])

// ====== 组合图表数据（上榜率×运营动作）=======
const aecHoverIdx = ref(-1)
const aecRates = ref([])
const aecDates = ref([])
const aecFullDates = ref([])
const aecActions = ref([])
const aecStepX = computed(() => {
  if (!aecRates.value.length || aecRates.value.length <= 1) return 28
  return 784 / (aecRates.value.length - 1)
})
const aecRateMin = 0, aecRateMax = 100
const aecScaleY = computed(() => 120 / (aecRateMax - aecRateMin))
const aecMaxBar = 80
const aecBarScaleY = 54 / aecMaxBar

// 组合图表 SVG path
const aecLineD = computed(() => {
  if (!aecRates.value.length) return ''
  return aecRates.value.map((v, i) => {
    const x = 8 + i * aecStepX.value
    const y = 140 - (v - aecRateMin) * aecScaleY.value
    return `${i === 0 ? 'M' : 'L'}${x},${y}`
  }).join(' ')
})
const aecAreaD = computed(() => {
  if (!aecRates.value.length) return ''
  const linePts = aecRates.value.map((v, i) => {
    const x = 8 + i * aecStepX.value
    const y = 140 - (v - aecRateMin) * aecScaleY.value
    return `${i === 0 ? 'M' : 'L'}${x},${y}`
  }).join(' ')
  const lastX = 8 + (aecRates.value.length - 1) * aecStepX.value
  return linePts + ` L${lastX},140 L8,140 Z`
})

function onAecHover(e) {
  const rect = aecRef.value?.querySelector('.aec-svg')?.getBoundingClientRect() || e.currentTarget.getBoundingClientRect()
  const x = e.clientX - rect.left
  const ratio = x / rect.width
  const idx = Math.round(ratio * (aecRates.value.length - 1))
  aecHoverIdx.value = Math.max(0, Math.min(aecRates.value.length - 1, idx))
  aecTooltipPos.value = { x: e.clientX, y: e.clientY }
}

const aecTooltipPos = ref({ x: 0, y: 0 })
const aecTooltipStyle = computed(() => ({
  left: (aecTooltipPos.value.x - 60) + 'px',
  top: (aecTooltipPos.value.y - 90) + 'px',
}))

function scrollToTab(tab) {
  activeTab.value = tab
  nextTick(() => {
    detailCardRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

// ====== 平台名称映射 ======
// 后端 search_result.platform 存的是 AI 模型标识(如 gpt-4o, gemini-1.5)，
// 需映射到前端 6 大平台名称
const MODEL_TO_PLATFORM = {
  // ChatGPT
  'gpt-4o': 'ChatGPT', 'gpt-4o-mini': 'ChatGPT', 'gpt-4': 'ChatGPT',
  'gpt-3.5': 'ChatGPT', 'chatgpt': 'ChatGPT',
  // Gemini
  'gemini-1.5': 'Gemini', 'gemini-2.0': 'Gemini', 'gemini': 'Gemini',
  'gemini-1.5-pro': 'Gemini', 'gemini-1.5-flash': 'Gemini',
  // Google AIO
  'google-aio': 'Google AIO', 'google_aio': 'Google AIO',
  // Google AIM
  'google-aim': 'Google AIM', 'google_aim': 'Google AIM',
  // Perplexity
  'perplexity': 'Perplexity', 'pplx': 'Perplexity',
  // Copilot
  'copilot': 'Copilot', 'microsoft-copilot': 'Copilot',
}

function mapPlatform(rawPlatform, model) {
  const key = (rawPlatform || model || '').toLowerCase().trim()
  // 直接匹配
  if (MODEL_TO_PLATFORM[key]) return MODEL_TO_PLATFORM[key]
  // 模糊匹配
  for (const [k, v] of Object.entries(MODEL_TO_PLATFORM)) {
    if (key.includes(k)) return v
  }
  // 如果已经是标准平台名
  const std = PLATFORMS.find(p => p.toLowerCase() === key)
  if (std) return std
  return rawPlatform || model || '未知'
}

// ====== 从查词结果计算 KPI ======
function computeKpiFromResults(results, prevResults) {
  const cur = results.filter(r => r.success && r.brandRank !== null && r.brandRank > 0)
  const total = results.filter(r => r.success).length
  const totalAll = results.length || 1
  const ranked = cur.length
  const top3 = cur.filter(r => r.brandRank <= 3).length
  const first = cur.filter(r => r.brandRank === 1).length

  // 通用词率：intentCategory 为非品牌词的占比
  const generalWords = results.filter(r => {
    const cat = (r.intentCategory || '').toLowerCase()
    return cat && !cat.includes('brand') && !cat.includes('品牌')
  })
  const generalRanked = generalWords.filter(r => r.brandRank !== null && r.brandRank > 0).length
  const generalTotal = generalWords.length || 1

  // 上榜词次
  const onListCount = ranked

  // 上期数据
  const prevRanked = prevResults.filter(r => r.success && r.brandRank !== null && r.brandRank > 0).length
  const prevTotal = prevResults.filter(r => r.success).length || 1

  // 变动
  const change = total > 0 ? ranked - prevRanked : 0

  kpiData.coverageRate = total > 0 ? Math.round(ranked * 100 / totalAll) : 0
  kpiData.top3Rate = total > 0 ? Math.round(top3 * 100 / totalAll) : 0
  kpiData.firstRate = total > 0 ? Math.round(first * 100 / totalAll) : 0
  kpiData.citationRate = generalTotal > 0 ? Math.round(generalRanked * 100 / generalTotal) : 0
  kpiData.onListCount = onListCount
  kpiData.change = change
}

// ====== 从查词结果计算各平台上榜率 ======
function computePlatformData(results) {
  const map = {}
  for (const r of results) {
    if (!r.success) continue
    const p = mapPlatform(r.platform, r.model)
    if (!map[p]) map[p] = { found: 0, total: 0 }
    map[p].total++
    if (r.brandRank !== null && r.brandRank > 0) map[p].found++
  }
  // 确保所有平台都有条目
  const out = PLATFORMS.map(name => {
    const d = map[name] || { found: 0, total: 0 }
    const rate = d.total > 0 ? Math.round(d.found * 100 / d.total) : 0
    const level = rate >= 80 ? 'good' : rate >= 50 ? 'ok' : rate > 0 ? 'bad' : 'none'
    return { name, rate, found: d.found, total: d.total, level }
  })
  // 补上未识别的平台
  for (const [name, d] of Object.entries(map)) {
    if (!PLATFORMS.includes(name)) {
      const rate = d.total > 0 ? Math.round(d.found * 100 / d.total) : 0
      out.push({ name, rate, found: d.found, total: d.total, level: rate >= 80 ? 'good' : rate >= 50 ? 'ok' : 'bad' })
    }
  }
  platformData.value = out
}

// ====== 生成上榜词/掉线词/排名波动 ======
function computeKeywordDetails(curResults, prevResults) {
  // 当前上榜词：brandRank > 0
  const onList = curResults
    .filter(r => r.success && r.brandRank !== null && r.brandRank > 0)
    .map(r => ({
      keyword: r.keyword,
      platform: mapPlatform(r.platform, r.model),
      rank: r.brandRank,
      type: r.intentCategory || '通用词',
      typeClass: (r.intentCategory || '').includes('brand') ? 'brand' : 'general',
      screenshotUrl: r.screenshotUrl || '',
    }))
    .sort((a, b) => a.rank - b.rank)
  onListKeywords.value = onList

  // 构建 prev 的 (keyword|platform) → rank 映射
  const prevMap = {}
  for (const r of prevResults) {
    if (r.success && r.brandRank !== null && r.brandRank > 0) {
      const p = mapPlatform(r.platform, r.model)
      prevMap[`${r.keyword}|${p}`] = r.brandRank
    }
  }

  // 掉线词：上期有排名，本期无排名或排名消失
  const curMap = {}
  for (const r of curResults) {
    if (r.success) {
      const p = mapPlatform(r.platform, r.model)
      curMap[`${r.keyword}|${p}`] = r.brandRank
    }
  }
  const offline = []
  for (const [key, prevRank] of Object.entries(prevMap)) {
    if (!curMap[key] || curMap[key] === null || curMap[key] <= 0) {
      const [keyword, platform] = key.split('|')
      offline.push({ keyword, platform, lastRank: prevRank, status: '已掉线' })
    }
  }
  offlineKeywords.value = offline.sort((a, b) => a.lastRank - b.lastRank)

  // 排名波动：两期都有排名的词
  const fluct = []
  for (const [key, prevRank] of Object.entries(prevMap)) {
    const curRank = curMap[key]
    if (curRank && curRank > 0 && prevRank > 0 && curRank !== prevRank) {
      const [keyword, platform] = key.split('|')
      const change = prevRank - curRank // 正数=上升(排名数字变小)
      fluct.push({ keyword, platform, fromRank: prevRank, toRank: curRank, change })
    }
  }
  // 按变动绝对值排序
  fluct.sort((a, b) => Math.abs(b.change) - Math.abs(a.change))
  kpiData.rising = fluct.filter(f => f.change > 0).length
  kpiData.falling = fluct.filter(f => f.change < 0).length
  rankFluctuations.value = fluct
}

// ====== 从可用日期生成图表数据 ======
function generateAecFromDates(dates) {
  // dates: ["2026-07-28", ...] 升序
  const rates = [], shortDates = [], fullDates = [], actions = []
  for (const ymd of dates) {
    fullDates.push(ymd)
    const [, m, d] = ymd.split('-')
    shortDates.push(`${parseInt(m)}-${d}`)
    // 占位：后续可从运营动作API补充
    rates.push(0)
    actions.push({ draft: 0, pub: 0 })
  }
  aecRates.value = rates
  aecDates.value = shortDates
  aecFullDates.value = fullDates
  aecActions.value = actions
}

// ====== 加载客户列表（当前账户权限下） ======
async function loadCustomers() {
  try {
    const list = await api.getAccounts() || []
    customers.value = list.map(c => ({
      id: c.id,
      company: c.companyName,
      name: c.companyName,
      brand: c.companyBrand || '',
      brandEn: '',
      responsible: c.ownerName || c.businessOwner || '',
      platforms: c.platforms || [],
      lastSearchDate: c.lastSearchDate || '',
    }))
  } catch (e) {
    console.error('加载客户列表失败:', e)
    customers.value = []
  }
}

// ====== 加载客户数据 ======
async function loadData() {
  if (!selectedCustomerId.value) return
  loading.value = true
  try {
    const accountId = selectedCustomerId.value

    // 1. 获取可用日期列表
    let dates = []
    try {
      dates = await api.getSearchHistory(accountId) || []
    } catch { dates = [] }
    availableDates.value = dates

    // 默认选最近两个日期做对比
    if (dates.length >= 2 && !dateA.value && !dateB.value) {
      dateA.value = dates[0]        // 最近
      dateB.value = dates[1]        // 上一次
    } else if (dates.length === 1 && !dateA.value) {
      dateA.value = dates[0]
    }

    // 2. 生成图表数据（从真实日期）
    // 取最近30天有数据的日期（升序）
    const chartDates = [...dates].reverse().slice(-30)
    generateAecFromDates(chartDates)

    // 3. 获取本期查词结果
    const curDate = dateA.value || dates[0] || ''
    let curResults = []
    if (curDate) {
      try { curResults = await api.getSearchResults(accountId, curDate) || [] }
      catch { curResults = [] }
    }

    // 4. 获取上期查词结果
    const prevDate = dateB.value || dates[1] || ''
    let prevResults = []
    if (prevDate) {
      try { prevResults = await api.getSearchResults(accountId, prevDate) || [] }
      catch { prevResults = [] }
    }

    // 5. 尝试获取排名汇总（补充 KPI）
    try {
      const summary = await api.getRankingSummary(accountId)
      if (summary && summary.rankingRate !== undefined) {
        kpiData.coverageRate = summary.rankingRate || 0
        kpiData.top3Rate = summary.top3Rate || 0
      }
    } catch { /* 排名汇总不存在时用查词结果计算 */ }

    // 6. 从查词结果计算 KPI 和平台数据
    if (curResults.length) {
      computeKpiFromResults(curResults, prevResults)
      computePlatformData(curResults)
      computeKeywordDetails(curResults, prevResults)

      // 用真实上榜率填充图表
      if (chartDates.length) {
        const ratesByDate = {}
        for (const ymd of chartDates) {
          const dayResults = curResults.filter(r => r.searchDate === ymd)
          const total = dayResults.filter(r => r.success).length
          const ranked = dayResults.filter(r => r.success && r.brandRank !== null && r.brandRank > 0).length
          ratesByDate[ymd] = total > 0 ? Math.round(ranked * 100 / total) : 0
        }
        // 如果本期数据覆盖了图表日期，用真实数据
        const hasRealRates = Object.values(ratesByDate).some(v => v > 0)
        if (hasRealRates) {
          aecRates.value = chartDates.map(d => ratesByDate[d] || 0)
        }
      }
    } else {
      // 无数据时清零
      platformData.value = PLATFORMS.map(name => ({ name, rate: 0, found: 0, total: 0, level: 'none' }))
      onListKeywords.value = []
      offlineKeywords.value = []
      rankFluctuations.value = []
    }

    await nextTick()
  } catch (e) {
    console.error('加载数据失败:', e)
  } finally { loading.value = false }
}

function onCustomerChange() {
  // 切换客户时重置日期，避免旧客户日期残留
  dateA.value = null
  dateB.value = null
  loadData()
}
function exportTable(type) {}

onMounted(() => { loadCustomers().then(() => { if (selectedCustomerId.value) loadData() }) })
watch([selectedCustomerId], () => { if (selectedCustomerId.value) onCustomerChange() })
watch([dateA, dateB], () => { if (selectedCustomerId.value && dateA.value) loadData() })
</script>

<style scoped>
.customer-effect-page { display: flex; flex-direction: column; gap: 16px; }

.cd-tools { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; padding: 16px 20px; background: #fff; border-radius: 12px; border: 1px solid #e5eaf3; }
.cd-pick { width: 220px; flex-shrink: 0; }
.pb-fseg { display: flex; align-items: center; gap: 6px; }
.pb-fseg-l { font-size: 13px; color: #64748b; margin-right: 4px; white-space: nowrap; }
.pb-fb { padding: 6px 14px; border: 1px solid #e2e8f0; border-radius: 8px; background: #fff; color: #475569; font-size: 13px; cursor: pointer; transition: all .18s ease; white-space: nowrap; }
.pb-fb:hover { border-color: #14b8a6; color: #14b8a6; background: rgba(20, 184, 166, 0.06); }
.pb-fb.on { background: linear-gradient(135deg, #14b8a6, #0d9488); color: #fff; border-color: transparent; box-shadow: 0 2px 8px rgba(20, 184, 166, 0.3); }
.dcp { display: flex; align-items: center; gap: 8px; }
.dcp-l { font-size: 13px; color: #64748b; white-space: nowrap; }
.dcp-seg { gap: 4px; }

/* 旧cd-header已移除，合并到cd-score中 */

.cd-kpi-row { display: grid; grid-template-columns: 1fr; gap: 12px; }
.cd-card { background: #fff; border-radius: 12px; border: 1px solid #e5eaf3; overflow: hidden; }

/* ====== 数据概览 cd-score（按示例代码重做） ====== */
.cd-score { padding: 0; display: block; }
.cd-score-head { display: flex; align-items: flex-start; justify-content: space-between; padding: 18px 20px 14px; }
.cd-name { font-size: 17px; font-weight: 700; color: #0f172a; }
.cd-sub { display: flex; align-items: center; gap: 12px; margin-top: 6px; font-size: 13px; color: #64748b; }
.cd-brand { color: #334155; font-weight: 500; }
.cd-owner { color: #64748b; }
.cd-cmp { color: #94a3b8; }
.cd-cmp b { color: #334155; font-weight: 600; }
.cd-h { display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px; border-radius: 50%; font-size: 13px; font-weight: 700; flex-shrink: 0; margin-top: 2px; }
.cd-h.ok { background: rgba(16, 185, 129, 0.1); color: #10b981; }
.cd-h.warn { background: rgba(245, 158, 11, 0.1); color: #f59e0b; }
.cd-h.bad { background: rgba(239, 68, 68, 0.1); color: #ef4444; }
.cd-h.none { background: #f1f5f9; color: #94a3b8; }

/* 统计指标行 —— 平铺分布 */
.cd-stat { display: flex; align-items: stretch; gap: 0; padding: 16px 20px; border-top: 1px solid #f1f5f9; }
.cd-s { display: flex; flex-direction: column; justify-content: center; flex: 1; padding: 6px 12px; min-width: 0; }
.cd-s.hero { flex: 1.4; border-right: 1px solid #f1f5f9; }
.cd-s.hero b { font-size: 32px; font-weight: 800; color: #0f172a; line-height: 1; }
.cd-s b { font-size: 22px; font-weight: 700; color: #0f172a; line-height: 1.2; }
.cd-s b i { font-style: normal; font-size: 14px; font-weight: 600; color: #64748b; margin-left: 2px; }
.cd-s span { font-size: 12px; color: #94a3b8; margin-top: 4px; }
/* 变动标签 */
.cd-d { display: inline-block; margin-left: 6px; font-size: 13px; font-weight: 600; }
.cd-d.up { color: #10b981; }
.cd-d.down { color: #ef4444; }

/* 本期变动条 */
.cd-delta-strip { display: flex; align-items: center; gap: 8px; padding: 12px 20px; border-top: 1px solid #f1f5f9; background: #fafbfc; }
.cd-ds-l { font-size: 12px; color: #94a3b8; margin-right: 4px; }
.cd-ds { display: inline-flex; align-items: center; gap: 4px; padding: 5px 12px; border: 1px solid #e5eaf3; border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; color: #475569; transition: all .15s; }
.cd-ds:hover { border-color: #14b8a6; color: #14b8a6; }
.cd-ds b { font-weight: 700; }
.cd-ds b.green { color: #10b981; }
.cd-ds b.red { color: #ef4444; }

/* ====== 图表悬浮 tooltip ====== */
.aec { position: relative; }
.aec-tooltip { position: fixed; z-index: 100; background: #1e293b; color: #fff; border-radius: 8px; padding: 10px 14px; font-size: 12px; pointer-events: none; box-shadow: 0 8px 24px rgba(0,0,0,.18); white-space: nowrap; }
.aec-tt-date { color: #94a3b8; margin-bottom: 4px; }
.aec-tt-rate b { color: #14b8a6; font-weight: 700; }
.aec-tt-action { color: #cbd5e1; margin-top: 2px; font-size: 11px; }

/* 空状态 */
.cd-empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 80px 20px; background: #fff; border-radius: 12px; border: 1px solid #e5eaf3; text-align: center; }
.cd-empty-state p { margin: 16px 0 6px; font-size: 16px; font-weight: 600; color: #334155; }
.cd-empty-state span { font-size: 13px; color: #94a3b8; }

/* A/B 时间对比 */
.dcp-vs { font-size: 13px; color: #94a3b8; font-weight: 500; }
.dcp-count { font-size: 12px; color: #14b8a6; white-space: nowrap; }

.cd-charts-row { display: grid; grid-template-columns: 1fr; gap: 12px; }
.cd-aec-card { padding: 18px 20px; }
.cd-aec-card .cd-card-h { margin-bottom: 8px; }

/* ====== 组合图表 aec ====== */
.aec { position: relative; }
.aec-svg { display: block; width: 100%; height: auto; min-height: 200px; }
.aec-area { transition: opacity .2s; }
.aec-line { transition: stroke-width .2s; }
.aec-dot { fill: #14b8a6; cursor: pointer; transition: r .15s; }
.aec-dot:hover, .aec-dot.active { r: 4.5; fill: #fff; stroke: #14b8a6; stroke-width: 2; }
.aec-sep { stroke: #e5eaf3; stroke-width: 1; }
.aec-bar { transition: opacity .2s; cursor: pointer; }
.aec-bar.draft { fill: #94a3b8; }
.aec-bar.draft:hover { fill: #64748b; }
.aec-bar.pub { fill: #f59e0b; }
.aec-bar.pub:hover { fill: #d97706; }
.aec-x { display: flex; justify-content: space-between; margin-top: 4px; font-size: 11px; color: #94a3b8; }
.aec-legend { display: flex; gap: 16px; margin-top: 8px; font-size: 12px; color: #64748b; }
.aec-legend span { display: flex; align-items: center; gap: 4px; }
.aec-legend i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; }
.aec-legend i.rate { background: #14b8a6; border-radius: 50%; }
.aec-legend i.draft { background: #94a3b8; }
.aec-legend i.pub { background: #f59e0b; }

/* ====== 各平台上榜率 cd-pbars ====== */
.cd-platform-card { padding: 18px 20px; }
.cd-pbars { display: flex; flex-direction: column; gap: 12px; }
.cd-pbar { display: flex; align-items: center; gap: 10px; }
.cd-pbar-n { font-size: 13px; font-weight: 500; color: #334155; min-width: 90px; white-space: nowrap; }
.cd-pbar-t { flex: 1; height: 22px; background: #f1f5f9; border-radius: 6px; overflow: hidden; }
.cd-pbar-f { display: block; height: 100%; border-radius: 6px; transition: width .6s ease; }
.cd-pbar-f.good { background: linear-gradient(90deg, #10b981, #34d399); }
.cd-pbar-f.ok { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.cd-pbar-f.bad { background: linear-gradient(90deg, #ef4444, #f87171); }
.cd-pbar-r { font-size: 14px; font-weight: 700; color: #0f172a; min-width: 38px; text-align: right; }
.cd-pbar-c { font-size: 11px; color: #94a3b8; min-width: 36px; }
.cd-card-h { display: flex; align-items: baseline; gap: 10px; margin-bottom: 12px; }
.cd-card-h h4 { margin: 0; font-size: 15px; font-weight: 600; color: #0f172a; }
.cd-card-sub { font-size: 12px; color: #94a3b8; }
.cd-chart-body { height: 240px; }

/* 旧图表样式已移除，使用 aec 组合图表 */

/* ====== 关键词明细卡片（Tab切换） ====== */
.cd-detail-card { padding: 0; overflow: hidden; }
.cd-tabs { display: flex; align-items: center; gap: 0; padding: 0 20px; border-bottom: 1px solid #e5eaf3; }
.cd-tab { position: relative; padding: 14px 20px; border: none; background: none; font-size: 14px; color: #64748b; cursor: pointer; transition: all .2s; display: flex; align-items: center; gap: 4px; }
.cd-tab::after { content: ''; position: absolute; bottom: -1px; left: 20px; right: 20px; height: 2px; background: transparent; transition: all .2s; }
.cd-tab:hover { color: #0d9488; }
.cd-tab.on { color: #0d9488; font-weight: 600; }
.cd-tab.on::after { background: #14b8a6; }
.cd-tab i { font-style: normal; font-size: 12px; padding: 1px 6px; border-radius: 10px; background: #f1f5f9; color: #64748b; font-weight: 500; }
.cd-tab i.warn { background: rgba(239, 68, 68, 0.1); color: #ef4444; }
.cd-tab-r { margin-left: auto; }

.cd-tbl-wrap { overflow-x: auto; }
.cd-tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.cd-tbl th { padding: 10px 16px; text-align: left; font-weight: 500; color: #94a3b8; font-size: 12px; border-bottom: 1px solid #e5eaf3; white-space: nowrap; }
.cd-tbl th.l { padding-left: 20px; }
.cd-tbl td { padding: 10px 16px; color: #334155; border-bottom: 1px solid #f1f5f9; }
.cd-tbl td.l { padding-left: 20px; }
.cd-tbl tbody tr:hover { background: #f8fafc; }
.cd-kw { font-weight: 500; color: #0f172a; }

/* 排名样式 */
.cd-rank { display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 13px; font-weight: 600; color: #64748b; background: #f1f5f9; }
.cd-rank.first { background: linear-gradient(135deg, #f59e0b, #fbbf24); color: #fff; }
.cd-rank.top3 { background: rgba(20, 184, 166, 0.1); color: #0d9488; }
.cd-rank.first.top3 { background: linear-gradient(135deg, #f59e0b, #fbbf24); color: #fff; }

/* 词类型样式 */
.cd-wt { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.cd-wt.general { background: rgba(20, 184, 166, 0.1); color: #0d9488; }
.cd-wt.competitor { background: rgba(99, 102, 241, 0.1); color: #6366f1; }
.cd-wt.longtail { background: rgba(245, 158, 11, 0.1); color: #d97706; }
.cd-wt.scene { background: rgba(139, 92, 246, 0.1); color: #8b5cf6; }

/* 截图按钮 */
.cd-shot { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; border: 1px solid #e2e8f0; border-radius: 6px; background: #fff; color: #475569; font-size: 12px; cursor: pointer; transition: all .2s; }
.cd-shot:hover { border-color: #14b8a6; color: #14b8a6; background: rgba(20, 184, 166, 0.04); }
.cd-shot .el-icon { font-size: 14px; }
.cd-empty-s { color: #cbd5e1; }

/* 掉线状态 */
.cd-fell { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; background: rgba(239, 68, 68, 0.1); color: #ef4444; }

/* 排名变化 */
.cd-chg { display: inline-flex; align-items: center; gap: 4px; font-size: 13px; }
.cd-chg b { font-weight: 700; font-size: 12px; }
.cd-chg.up { color: #10b981; }
.cd-chg.up b { color: #10b981; }
.cd-chg.down { color: #ef4444; }
.cd-chg.down b { color: #ef4444; }

@media (max-width: 1400px) {
  .cd-kpi-row { grid-template-columns: 1fr 1fr; }
  .cd-score { grid-column: 1 / -1; }
}
@media (max-width: 900px) {
  .cd-kpi-row { grid-template-columns: 1fr; }
  .cd-charts-row { grid-template-columns: 1fr; }
  .cd-tools { padding: 12px 14px; }
  .cd-pick { width: 100%; }
  .pb-fseg { flex-wrap: wrap; }
  .cd-tabs { padding: 0 12px; }
  .cd-tab { padding: 12px 14px; font-size: 13px; }
}
</style>
