<template>
  <div class="search-list-page">
    <!-- ============ KPI 栏 ============ -->
    <section class="kpi-strip">
      <div class="kpi-card" role="button" tabindex="0"
           :class="{ active: !filterStatus }"
           @click="filterStatus=''"
           @keydown.enter="filterStatus=''">
        <div class="kpi-icon kpi-icon-blue"><el-icon :size="18"><OfficeBuilding /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-label">总客户数</div>
          <div class="kpi-val">{{ accounts.length }}</div>
          <div class="kpi-sub">显示全部</div>
        </div>
      </div>
      <div class="kpi-card" role="button" tabindex="0"
           :class="{ active: filterStatus==='running' }"
           @click="filterStatus = filterStatus==='running' ? '' : 'running'"
           @keydown.enter="filterStatus = filterStatus==='running' ? '' : 'running'">
        <div class="kpi-icon kpi-icon-orange"><el-icon :size="18"><Loading /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-label">正在查词</div>
          <div class="kpi-val">{{ runningCount }}</div>
          <div class="kpi-sub" :class="{ 'kpi-sub-live': runningCount > 0 }">
            <span v-if="runningCount">实时进行中</span>
            <span v-else>当前空闲</span>
          </div>
        </div>
      </div>
      <div class="kpi-card" role="button" tabindex="0"
           :class="{ active: filterStatus==='today' }"
           @click="filterStatus = filterStatus==='today' ? '' : 'today'"
           @keydown.enter="filterStatus = filterStatus==='today' ? '' : 'today'">
        <div class="kpi-icon kpi-icon-green"><el-icon :size="18"><Sunny /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-label">今日已查</div>
          <div class="kpi-val">{{ todaySearched }}</div>
          <div class="kpi-sub">{{ scopedAccounts.length ? Math.round(todaySearched / scopedAccounts.length * 100) + '% 客户覆盖' : '暂无' }}</div>
        </div>
      </div>
      <div class="kpi-card" role="button" tabindex="0"
           :class="{ active: filterStatus==='stale' }"
           @click="staleCount && (filterStatus = filterStatus==='stale' ? '' : 'stale')"
           @keydown.enter="staleCount && (filterStatus = filterStatus==='stale' ? '' : 'stale')">
        <div class="kpi-icon kpi-icon-purple"><el-icon :size="18"><Key /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-label">总关键词</div>
          <div class="kpi-val">{{ totalKeywords }}</div>
          <div class="kpi-sub">
            <span v-if="staleCount" class="kpi-sub-bad">{{ staleCount }} 个 7 天未查</span>
            <span v-else class="kpi-sub-good">覆盖及时</span>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ 主面板 ============ -->
    <section class="panel">
      <!-- 类别 tabs：内部客户 / 临时任务（外贸版不做外部任务） -->
      <div class="category-tabs">
        <button class="cat-tab" :class="{ active: scope === 'internal' }" @click="setScope('internal')">
          内部客户 <span class="cat-count">{{ internalAccountsCount }}</span>
        </button>
        <button class="cat-tab cat-tab-temp" :class="{ active: scope === 'temp' }" @click="setScope('temp')">
          <span class="cat-tab-dot cat-tab-dot-temp"></span>临时任务 <span class="cat-count">{{ tempAccountsCount }}</span>
        </button>
      </div>

      <!-- 工具栏 -->
      <div class="toolbar">
        <div class="toolbar-tabs">
          <button class="seg" :class="{ active: !filterStatus }" @click="filterStatus=''">
            全部 <span class="seg-count">{{ scopedAccounts.length }}</span>
          </button>
          <button class="seg" :class="{ active: filterStatus==='running' }" @click="filterStatus='running'">
            查词中 <span class="seg-count">{{ runningCount }}</span>
          </button>
          <button class="seg" :class="{ active: filterStatus==='error' }" @click="filterStatus='error'">
            出错 <span class="seg-count">{{ errorCount }}</span>
          </button>
          <button class="seg" :class="{ active: filterStatus==='none' }" @click="filterStatus='none'">
            未查词 <span class="seg-count">{{ noneCount }}</span>
          </button>
        </div>
        <div class="toolbar-actions">
          <el-input
            v-model="searchText"
            placeholder="搜索公司或品牌..."
            clearable
            :prefix-icon="SearchIcon"
            class="toolbar-search"
          />
          <el-select v-model="filterPlatform" placeholder="覆盖平台" clearable class="toolbar-filter">
            <el-option v-for="p in allPlatforms" :key="p" :label="p" :value="p" />
          </el-select>
          <el-button type="primary" :icon="VideoPlay" @click="openCreateTask">创建查词任务</el-button>
          <el-button type="warning" :icon="Lightning" plain @click="openTempTask">⚡ 临时任务</el-button>
        </div>
      </div>

      <!-- 表格 -->
      <el-table
        ref="tableRef"
        :data="pagedAccounts"
        v-loading="loading"
        row-key="id"
        class="account-table"
        :header-cell-style="{ background: 'transparent', color: '#64748b', fontWeight: 600, fontSize: '12px', letterSpacing: '0.3px' }"
        @row-click="handleRowClick"
        @expand-change="handleExpandChange"
      >
        <el-table-column type="expand" width="36">
          <template #default="{ row }">
            <div class="task-panel">
              <div class="task-panel-header">
                <div class="tph-title">
                  <el-icon><Calendar /></el-icon>
                  <span>执行历史</span>
                  <span class="tph-count">{{ mergedTasks(row.id).length }} 天</span>
                  <span v-if="tasksLoading[row.id]" class="tph-loading">加载中...</span>
                </div>
                <div class="tph-actions">
                  <el-button
                    v-if="!row.running"
                    type="primary"
                    size="small"
                    @click.stop="startFromList(row)"
                  >
                    <el-icon><VideoPlay /></el-icon>开始查词
                  </el-button>
                  <el-button
                    v-else
                    type="danger"
                    size="small"
                    @click.stop="goDetail(row)"
                  >
                    <el-icon><View /></el-icon>查看进度
                  </el-button>
                  <el-button size="small" @click.stop="goDetail(row)">
                    <el-icon><View /></el-icon>完整详情
                  </el-button>
                  <el-tooltip content="删除该客户全部查词历史（含所有日期、查词结果、排名分析）" placement="top">
                    <el-button
                      v-if="!row.running && mergedTasks(row.id).length > 0"
                      type="danger" plain size="small" :icon="Delete"
                      @click.stop="deleteAllHistory(row)"
                    >清空全部历史</el-button>
                  </el-tooltip>
                </div>
              </div>

              <!-- 运行中任务条 -->
              <div v-if="row.running" class="task-bar task-bar-running" @click.stop="goDetail(row)">
                <div class="tb-date"><span class="live-dot"></span>正在查词</div>
                <div class="tb-stat"><span class="tb-lbl">进度</span><span class="tb-val">{{ row.runningProgress || 0 }}%</span></div>
                <div class="tb-progress">
                  <el-progress :percentage="Number(row.runningProgress) || 0" :stroke-width="6" :show-text="false" />
                </div>
                <span class="tb-status tbs-running">进行中</span>
                <el-icon class="tb-arrow"><ArrowRight /></el-icon>
              </div>

              <!-- 历史任务条列表（按日期合并） -->
              <div v-if="mergedTasks(row.id).length">
                <div
                  v-for="t in pagedTasks(row.id)"
                  :key="t.taskId"
                  class="task-bar"
                  :class="'task-bar-' + (t.status || '').toLowerCase()"
                  @click.stop="goDetailWithTask(row, t)"
                >
                  <div class="tb-date">
                    <el-icon><Calendar /></el-icon>
                    <span>{{ t._date }}</span>
                  </div>
                  <div class="tb-stat">
                    <span class="tb-lbl">模型</span>
                    <span class="tb-val">{{ t.modelCount }}</span>
                  </div>
                  <div class="tb-stat">
                    <span class="tb-lbl">成功</span>
                    <span class="tb-val">{{ t.success }}<span class="tb-sep">/</span>{{ t.target }}</span>
                  </div>
                  <div v-if="t.pending > 0" class="tb-stat">
                    <span class="tb-lbl">未完成</span>
                    <span class="tb-val tb-val-fail">{{ t.pending }}</span>
                  </div>
                  <el-button
                    v-if="t.pending > 0 && t.isToday"
                    size="small"
                    type="warning"
                    plain
                    class="tb-retry-btn"
                    @click.stop="retryDayFailed(row, t)"
                  >重试失败</el-button>
                  <div class="tb-models">
                    <span
                      v-for="ms in (t.modelStats || [])"
                      :key="ms.model"
                      class="tb-model-chip"
                      :title="modelDisplayName(ms.model)"
                    >
                      <PlatformIcon :name="ms.model" :size="16" /><span class="tb-model-num">{{ ms.success }}</span>
                    </span>
                  </div>
                  <span :class="['tb-status', taskStatusClass(t)]">{{ taskStatusLabel(t) }}</span>
                  <el-tooltip content="删除此天的查词历史（含该天所有搜索/排名结果）" placement="top">
                    <el-button
                      size="small" type="danger" plain
                      class="tb-del-btn"
                      :icon="Delete"
                      :disabled="row.running"
                      @click.stop="deleteHistoryDate(row, t)"
                    >删除</el-button>
                  </el-tooltip>
                  <el-icon class="tb-arrow"><ArrowRight /></el-icon>
                </div>
                <div v-if="mergedTasks(row.id).length > 5" class="task-pagination" @click.stop>
                  <el-pagination
                    v-model:current-page="taskPage[row.id]"
                    :page-size="5"
                    :total="mergedTasks(row.id).length"
                    layout="prev, pager, next"
                    background
                    small
                  />
                </div>
              </div>
              <div v-else-if="!tasksLoading[row.id]" class="task-empty">
                <span>暂无历史查词记录</span>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="客户" min-width="200" sortable
          :sort-method="(a,b) => (a.companyName||'').localeCompare(b.companyName||'')">
          <template #default="{ row }">
            <div class="customer-cell">
              <div class="ca-name-row">
                <span
                  class="ca-type-dot"
                  :class="row.userType === 'quote' ? 'ca-dot-quote' : 'ca-dot-paid'"
                  :title="row.userType === 'quote' ? '报价客户' : '正式客户'"
                ></span>
                <span class="ca-name">{{ row.companyName }}</span>
              </div>
              <div class="ca-meta">
                <span class="ca-meta-item">{{ row.keywordCount || 0 }} 词</span>
                <span class="ca-meta-sep">·</span>
                <span class="ca-meta-item">{{ row.platforms?.length || 0 }} 平台</span>
                <span class="ca-meta-sep">·</span>
                <span class="ca-meta-item" title="累计查询次数">累计 {{ row.totalSearches || 0 }} 次</span>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="品牌" min-width="160">
          <template #default="{ row }">
            <div class="brand-cell">
              <template v-if="parseBrandList(row.companyBrand).length">
                <span v-for="b in parseBrandList(row.companyBrand).slice(0, 2)" :key="b" class="brand-tag">{{ b }}</span>
                <el-tooltip
                  v-if="parseBrandList(row.companyBrand).length > 2"
                  :content="parseBrandList(row.companyBrand).slice(2).join('、')"
                  placement="top">
                  <span class="brand-tag brand-tag-more">+{{ parseBrandList(row.companyBrand).length - 2 }}</span>
                </el-tooltip>
              </template>
              <span v-else class="muted">未配置</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="覆盖平台" min-width="180">
          <template #default="{ row }">
            <div class="platforms-cell">
              <template v-if="(row.platforms || []).length">
                <PlatformIcon v-for="p in row.platforms" :key="p" :name="p" :size="20" />
              </template>
              <span v-else class="muted">—</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="今日" width="120" align="center">
          <template #default="{ row }">
            <template v-if="row.todayTotal > 0">
              <span class="today-pill">{{ row.todaySuccess ?? 0 }}<span class="today-sep">/</span>{{ row.todayTotal }}</span>
              <span class="today-rate" :style="{ color: rateColor(todayRate(row)) }">{{ todayRate(row) }}%</span>
            </template>
            <span v-else class="muted muted-zero">—</span>
          </template>
        </el-table-column>

        <el-table-column label="最近查词" width="140" sortable :sort-method="sortByTime">
          <template #default="{ row }">
            <template v-if="row.lastSearchTime">
              <el-tooltip :content="row.lastSearchTime" placement="top">
                <div class="last-search">
                  <span class="ls-rel" :class="{ 'ls-stale': isStale(row.lastSearchTime) }">{{ relativeTime(row.lastSearchTime) }}</span>
                  <span class="ls-date">{{ formatShortTime(row.lastSearchTime) }}</span>
                </div>
              </el-tooltip>
            </template>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="130" align="center">
          <template #default="{ row }">
            <div v-if="row.running" class="status-pill status-pill-running">
              <span class="live-dot"></span>查词中
              <span v-if="row.runningProgress" class="status-pct">{{ row.runningProgress }}%</span>
            </div>
            <span v-else-if="row.lastStatus" class="status-pill" :class="'status-pill-' + row.lastStatus.toLowerCase()">
              {{ statusText(row.lastStatus) }}
            </span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="190" fixed="right" align="right">
          <template #default="{ row }">
            <button class="act-btn act-btn-primary" @click.stop="goDetail(row)">
              查词<el-icon class="act-arrow" :size="11"><ArrowRight /></el-icon>
            </button>
            <el-tooltip v-if="scope === 'temp'" content="重命名任务" placement="top">
              <button class="act-btn act-btn-icon" @click.stop="renameAccount(row)">
                <el-icon :size="13"><EditPen /></el-icon>
              </button>
            </el-tooltip>
            <el-tooltip :content="row.totalSearches ? '导出查词结果' : '暂无查词记录'" placement="top">
              <button
                class="act-btn act-btn-icon"
                :disabled="!row.totalSearches"
                @click.stop="exportAccountSearch(row)"
              >
                <el-icon :size="13"><Download /></el-icon>
              </button>
            </el-tooltip>
            <el-tooltip
              :content="row.running ? '运行中无法删除（请先停止）' : (row.totalSearches ? '删除该客户全部查词任务（含所有日期、查词结果、排名分析；客户账号保留）' : '该客户暂无查词任务 — 点击删除账号（移入回收站，可恢复）')"
              placement="top"
            >
              <button
                class="act-btn act-btn-icon act-btn-danger"
                :disabled="row.running"
                @click.stop="onRowDelete(row)"
              >
                <el-icon :size="13"><Delete /></el-icon>
              </button>
            </el-tooltip>
          </template>
        </el-table-column>

        <template #empty>
          <div class="table-empty">
            <el-icon :size="40" color="#cbd5e1"><OfficeBuilding /></el-icon>
            <p>{{ isFiltering ? '未找到匹配的客户' : '暂无客户账号' }}</p>
            <el-button v-if="!isFiltering" type="primary" size="small" @click="$router.push('/dashboard/accounts')">去添加账号</el-button>
            <el-button v-else size="small" @click="resetFilters">清除筛选</el-button>
          </div>
        </template>
      </el-table>

      <!-- 分页 -->
      <div v-if="filteredAccounts.length > pageSize" class="pagination-row">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="filteredAccounts.length"
          layout="total, prev, pager, next, jumper"
          background
          small
        />
      </div>
    </section>

    <!-- ============ 创建查词任务 ============ -->
    <el-dialog
      v-model="createTaskVisible"
      title="创建查词任务"
      width="min(560px, 90vw)"
      :close-on-click-modal="false"
      @open="onCreateTaskOpen"
    >
      <div class="create-task-form">
        <div class="ct-row">
          <label class="ct-label">选择客户</label>
          <el-select
            v-model="createTaskAccountId"
            placeholder="请选择客户"
            filterable
            clearable
            class="ct-full"
            @change="onCreateTaskAccountChange"
          >
            <el-option
              v-for="a in accounts"
              :key="a.id"
              :label="`${a.companyName}${parseBrandList(a.companyBrand).length ? ' · ' + parseBrandList(a.companyBrand).join('、') : ''}`"
              :value="a.id"
              :disabled="a.running"
            />
          </el-select>
          <div v-if="createTaskAccount?.running" class="ct-hint ct-hint-warn">该客户正在查词中，请选择其他客户</div>
        </div>

        <div v-if="createTaskAccount" class="ct-row">
          <label class="ct-label">选择平台</label>
          <div v-if="createTaskAccountPlatforms.length" class="ct-platforms">
            <el-checkbox
              :model-value="createTaskPlatforms.length === createTaskAccountPlatforms.length"
              :indeterminate="createTaskPlatforms.length > 0 && createTaskPlatforms.length < createTaskAccountPlatforms.length"
              @change="toggleAllPlatforms"
            >全选</el-checkbox>
            <el-checkbox-group v-model="createTaskPlatforms" class="ct-platform-group">
              <el-checkbox v-for="p in createTaskAccountPlatforms" :key="p" :value="p">{{ p }}</el-checkbox>
            </el-checkbox-group>
          </div>
          <div v-else class="ct-hint ct-hint-warn">该客户尚未配置查询平台</div>
        </div>

        <div v-if="createTaskAccount && !createTaskAccount.keywordCount" class="ct-hint ct-hint-warn ct-hint-block">
          <el-icon :size="13"><InfoFilled /></el-icon>
          该客户尚未配置关键词,无法发起查词。
          <el-button link type="primary" size="small" @click="goConfigKeywords(createTaskAccount)">前往配置关键词 →</el-button>
        </div>

        <div v-if="createTaskAccount && createTaskAccount.keywordCount && createTaskPlatforms.length" class="ct-summary">
          <span>关键词 <strong>{{ createTaskAccount.keywordCount || 0 }}</strong> 条 × 平台 <strong>{{ createTaskPlatforms.length }}</strong> 个 =
          <strong>{{ (createTaskAccount.keywordCount || 0) * createTaskPlatforms.length }}</strong> 条查询</span>
        </div>
      </div>
      <template #footer>
        <el-button @click="createTaskVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="createTaskSubmitting"
          :disabled="!canSubmitCreateTask"
          @click="submitCreateTask"
        >创建任务</el-button>
      </template>
    </el-dialog>

    <!-- ═══ 临时查词 Dialog ═══ -->
    <el-dialog v-model="tempTaskOpen" width="min(640px, 94vw)"
               :close-on-click-modal="false">
      <template #header>
        <div class="temp-task-header">
          <el-icon :size="22" class="temp-task-header-icon"><Lightning /></el-icon>
          <div>
            <div class="temp-task-header-title">⚡ 临时查词任务</div>
            <div class="temp-task-header-sub">无需建客户，输入品牌+关键词+平台立即开始（结果会同步做品牌排名分析）</div>
          </div>
        </div>
      </template>

      <el-form :model="tempForm" label-width="92px">
        <el-form-item label="品牌名">
          <el-select v-model="tempForm.brands" multiple filterable allow-create default-first-option
                     :reserve-keyword="false" size="large" style="width:100%"
                     placeholder="可空。可填多个品牌（输入后回车添加）；填了会做品牌排名分析，不填只看 AI 回答">
          </el-select>
          <div class="temp-task-hint" v-if="tempForm.brands.length > 1">
            <el-icon :size="12"><InfoFilled /></el-icon>
            已添加 <strong>{{ tempForm.brands.length }}</strong> 个品牌，排名分析会逐一识别
          </div>
        </el-form-item>
        <el-form-item label="关键词" required>
          <el-input v-model="tempForm.keywordsText" type="textarea" :rows="6"
                    placeholder="每行一条 AI 提示词，例:&#10;南京哪家做家庭吸氧设备最好&#10;我爸有慢阻肺需要在家吸氧" />
          <div class="temp-task-hint">
            <el-icon :size="12"><InfoFilled /></el-icon>
            共 <strong>{{ tempKeywordsCount }}</strong> 条 · 每条会喂给所选 {{ tempForm.platforms.length }} 个平台
          </div>
        </el-form-item>
        <el-form-item label="覆盖平台" required>
          <el-checkbox-group v-model="tempForm.platforms">
            <el-checkbox v-for="p in TEMP_PLATFORM_OPTIONS" :key="p" :value="p">{{ p }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="tempTaskOpen = false">取消</el-button>
        <el-button type="warning" :icon="Lightning" :loading="tempSubmitting"
                   :disabled="!canSubmitTemp"
                   @click="submitTempTask">⚡ 立即查询</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search as SearchIcon, Refresh, ArrowRight, OfficeBuilding, Loading, Sunny, Key,
  Timer, Calendar, VideoPlay, View, Download, Delete, EditPen,
  Lightning, InfoFilled,
} from '@element-plus/icons-vue'
import api from '@/api/index.js'
import PlatformIcon from '@/components/PlatformIcon.vue'
import { platformName } from '@/utils/platformIcon.js'
import { parseBrands, brandsToStorage } from '@/utils/brands.js'
import { relativeTime, formatShortTime, isStale } from '@/utils/time.js'

const router = useRouter()
const accounts = ref([])
const loading = ref(false)
const searchText = ref('')
const filterStatus = ref('')
const filterPlatform = ref('')
const currentPage = ref(1)
const pageSize = 10
let autoRefreshTimer = null

const tableRef = ref(null)
const tasksByAccount = reactive({})
const tasksLoading = reactive({})
const taskPage = reactive({})
const TASK_PAGE_SIZE = 5
const EXPANDED_STORAGE_KEY = 'geoKeywordSearchExpandedIds'

function parseBrandList(b) { return parseBrands(b) }

/* ============ 模型显示名 ============ */
const modelNameMap = {
  douBao: '豆包', deepseek: 'DeepSeek',
  yuanbao: '元宝', yuanBao: '元宝',
  kimi: 'Kimi',
  qianwen: '通义千问', tongYi: '通义千问',
  wenxin: '文心一言', wenXin: '文心一言',
  naMi: '纳米',
  zhipu: '智谱清言',
  tiangong: '天工', xunfei: '讯飞星火', hailuo: '海螺AI',
}
function modelDisplayName(model) { return modelNameMap[model] || model }

function todayRate(row) {
  const t = row.todayTotal || 0
  if (!t) return 0
  return Math.round((row.todaySuccess || 0) / t * 100)
}
function rateColor(r) {
  if (r >= 80) return '#16a34a'
  if (r >= 50) return '#d97706'
  return '#dc2626'
}

/* ============ 统计 ============ */
// 顶部 KPI / seg 计数都按当前 scope（内部 / 外部）计算
const runningCount = computed(() => scopedAccounts.value.filter(a => a.running).length)
const todaySearched = computed(() => scopedAccounts.value.filter(a => a.todayTotal > 0).length)
const totalKeywords = computed(() => scopedAccounts.value.reduce((s, a) => s + (a.keywordCount || 0), 0))
const errorCount = computed(() => scopedAccounts.value.filter(a => !a.running && a.lastStatus === 'ERROR').length)
const noneCount = computed(() => scopedAccounts.value.filter(a => !a.running && !a.lastStatus).length)
const staleCount = computed(() => scopedAccounts.value.filter(a => a.lastSearchTime && isStale(a.lastSearchTime)).length)

const allPlatforms = computed(() => {
  // 按规范名去重:数据里 "kimi"/"Kimi" 等大小写变体合并为一个
  const set = new Set()
  accounts.value.forEach(a => (a.platforms || []).forEach(p => set.add(platformName(p))))
  return Array.from(set).sort()
})


const isFiltering = computed(() => !!(searchText.value || filterStatus.value || filterPlatform.value))

/* ============ 角色 + 类别（外部 vs 内部） ============ */
const isSuperAdmin = computed(() => (localStorage.getItem('geo_role') || '') === 'super_admin')
const scope = ref('internal')  // 'internal'(正式客户) | 'external'(外部邀请) | 'temp'(临时查词)

function setScope(v) {
  scope.value = v
  // 不再 reload；super_admin 的 accounts.value 一次性含全部三类，前端切 scope 即可
}

// 三类划分：
//   内部客户 internal = 正式账号(is_temp=0)
//   外部任务 external = 外部邀请码生成(is_temp=1 且 [外部·] 开头, isExternal)
//   临时任务 temp     = 临时查词生成(is_temp=1 且非外部, [临时] 开头)
const externalAccountsCount = computed(() => accounts.value.filter(a => a.isExternal).length)
const tempAccountsCount = computed(() => accounts.value.filter(a => a.isTemp && !a.isExternal).length)
const internalAccountsCount = computed(() => accounts.value.filter(a => !a.isTemp).length)

const scopedAccounts = computed(() => {
  const list = accounts.value
  // 外部任务仅 super_admin 可切；其它角色 list 本就不含外部，再加保险过滤
  if (scope.value === 'external' && isSuperAdmin.value) return list.filter(a => a.isExternal)
  if (scope.value === 'temp') return list.filter(a => a.isTemp && !a.isExternal)
  return list.filter(a => !a.isTemp)   // internal：纯正式客户(is_temp=0)
})

/* ============ 筛选 & 排序 ============ */
const filteredAccounts = computed(() => {
  let list = scopedAccounts.value.map(a => ({
    ...a,
  }))

  if (searchText.value.trim()) {
    const kw = searchText.value.trim().toLowerCase()
    list = list.filter(a =>
      (a.companyName || '').toLowerCase().includes(kw) ||
      (a.companyBrand || '').toLowerCase().includes(kw)
    )
  }

  if (filterStatus.value) {
    list = list.filter(a => {
      if (filterStatus.value === 'running') return a.running
      if (filterStatus.value === 'completed') return !a.running && a.lastStatus === 'COMPLETED'
      if (filterStatus.value === 'error') return !a.running && a.lastStatus === 'ERROR'
      if (filterStatus.value === 'none') return !a.running && !a.lastStatus
      if (filterStatus.value === 'today') return a.todayTotal > 0
      if (filterStatus.value === 'stale') return a.lastSearchTime && isStale(a.lastSearchTime)
      return true
    })
  }

  if (filterPlatform.value) {
    list = list.filter(a => (a.platforms || []).some(p => platformName(p) === filterPlatform.value))
  }

  // 默认按「最近查询」从近到远(最新在最上);运行中的优先置顶;从未查过的排最后
  list.sort((a, b) => {
    if (a.running !== b.running) return a.running ? -1 : 1
    const ta = a.lastSearchTime || ''
    const tb = b.lastSearchTime || ''
    if (!ta && !tb) return 0
    if (!ta) return 1
    if (!tb) return -1
    return tb.localeCompare(ta)
  })

  return list
})

watch([searchText, filterStatus, filterPlatform, scope], () => { currentPage.value = 1 })

const pagedAccounts = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredAccounts.value.slice(start, start + pageSize)
})

function resetFilters() {
  searchText.value = ''
  filterStatus.value = ''
  filterPlatform.value = ''
}

/* ============ 工具函数 ============ */
function statusText(s) {
  // F7: 补 STALE(僵尸,心跳过期)/PENDING(排队)/FAILED 映射，避免列表显示英文原状态
  return ({
    COMPLETED: '已完成', RUNNING: '运行中', CANCELLED: '已停止', ERROR: '出错',
    PENDING: '等待中', STALE: '已超时', FAILED: '失败',
  })[s] || s || '—'
}

function sortByTime(a, b) {
  return (a.lastSearchTime || '').localeCompare(b.lastSearchTime || '')
}

function goDetail(row) {
  router.push(`/dashboard/keyword-search/${row.id}`)
}

function goDetailWithTask(row, task) {
  const date = task._date || (task.createdAt || '').slice(0, 10)
  if (date) router.push(`/dashboard/keyword-search/${row.id}?date=${date}`)
  else router.push(`/dashboard/keyword-search/${row.id}`)
}

/* ============ 展开加载 ============ */
function handleRowClick(row, _col, event) {
  if (event?.target?.closest?.('.el-button, button, a')) return
  tableRef.value?.toggleRowExpansion(row)
}

async function handleExpandChange(row, expandedRows) {
  if (Array.isArray(expandedRows)) {
    try {
      sessionStorage.setItem(
        EXPANDED_STORAGE_KEY,
        JSON.stringify(expandedRows.map(r => r.id))
      )
    } catch {}
  }
  const isExpanded = Array.isArray(expandedRows)
    ? expandedRows.some(r => r.id === row.id)
    : !!expandedRows
  if (!isExpanded) return
  if (tasksByAccount[row.id] && !row.running) return
  await loadAccountTasks(row.id)
}

async function restoreExpandedRows() {
  let ids = []
  try {
    const raw = sessionStorage.getItem(EXPANDED_STORAGE_KEY)
    ids = raw ? JSON.parse(raw) : []
  } catch { ids = [] }
  if (!ids.length || !tableRef.value) return
  await nextTick()
  pagedAccounts.value
    .filter(r => ids.includes(r.id))
    .forEach(r => tableRef.value.toggleRowExpansion(r, true))
}

async function loadAccountTasks(accountId) {
  tasksLoading[accountId] = true
  if (!taskPage[accountId]) taskPage[accountId] = 1
  try {
    const list = await api.getAccountExecutionHistoryGrouped(accountId, 30)
    tasksByAccount[accountId] = list || []
  } catch {
    tasksByAccount[accountId] = []
  } finally {
    tasksLoading[accountId] = false
  }
}

function taskStatusText(s) {
  // F7: 与 statusText 映射对齐，补 STALE/FAILED
  return ({
    COMPLETED: '已完成', RUNNING: '进行中', CANCELLED: '已停止', ERROR: '失败',
    PENDING: '等待', STALE: '已超时', FAILED: '失败',
  })[s] || s || '—'
}

function taskFail(t) {
  return (t.modelStats || []).reduce((acc, m) => acc + (m.fail || 0), 0)
}
function taskStatusLabel(t) {
  if (t.status === 'COMPLETED' && taskFail(t) > 0) return '部分失败'
  return taskStatusText(t.status)
}
function taskStatusClass(t) {
  if (t.status === 'COMPLETED' && taskFail(t) > 0) return 'tbs-partial'
  return 'tbs-' + (t.status || '').toLowerCase()
}

function pagedTasks(accountId) {
  const all = mergedTasks(accountId)
  const page = taskPage[accountId] || 1
  const start = (page - 1) * TASK_PAGE_SIZE
  return all.slice(start, start + TASK_PAGE_SIZE)
}

function mergedTasks(accountId) {
  const list = tasksByAccount[accountId] || []
  const todayStr = new Date().toISOString().slice(0, 10)
  return list.map(g => {
    const modelStats = g.modelStats || []
    const subs = g.tasks || []
    const execTotal = subs.reduce((a, t) => a + (t.totalQueries || 0), 0)
    const execDone = subs.reduce((a, t) => a + (t.completedQueries || 0), 0)
    const target = g.targetQueries || 0
    const success = g.successQueries || 0
    const pending = g.pendingQueries || 0
    return {
      taskId: 'date-' + g.date,
      _date: g.date,
      isToday: g.date === todayStr,
      createdAt: g.firstAt || g.date,
      completedAt: g.lastAt || '',
      execTotal, execDone, target, success, pending,
      modelCount: modelStats.length,
      subtaskCount: subs.length,
      modelStats,
      status: g.status || 'COMPLETED',
      errorMessage: g.errorMessage || '',
    }
  })
}

async function retryDayFailed(row, t) {
  try {
    await api.continueSearch(row.id)
    ElMessage.success(`正在重试 ${t.pending} 个未完成查询...`)
    router.push(`/dashboard/keyword-search/${row.id}`)
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || e?.message || '重试失败')
  }
}

async function deleteHistoryDate(row, t) {
  const date = t._date
  if (!row?.id || !date) return
  try {
    await ElMessageBox.confirm(
      `确认删除「${row.companyName}」${date} 的全部查词历史？\n\n会同时删除该天的查词结果与排名分析数据，无法恢复。`,
      '删除查词历史',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
  } catch { return }
  try {
    const r = await api.deleteSearchHistory(row.id, date)
    ElMessage.success(`已删除 ${r?.deleted ?? ''} 条查词记录`)
    await loadData()
    delete tasksLoading[row.id]
    delete tasksByAccount[row.id]
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || e?.message || '删除失败')
  }
}

// 删除按钮分流：有查词记录→清空查词历史(账号保留)；无记录→删除账号(软删进回收站，可恢复)
async function onRowDelete(row) {
  if (!row?.id || row.running) return
  if (row.totalSearches) {
    return deleteAllHistory(row)
  }
  // 暂无查词任务：删除空账号本身（临时/外部/测试空账号清理）
  try {
    await ElMessageBox.confirm(
      `<p>该客户<b>暂无任何查词任务</b>，确认<b style="color:#dc2626">删除账号「${row.companyName}」</b>？</p>
       <p style="color:#64748b;font-size:12px;line-height:1.7;margin-top:8px">
         · 账号将<b style="color:#b45309">移入回收站</b>（30 天内可在「客户管理 → 回收站」恢复）<br/>
         · 关键词配置一并移除；如已有查词历史不会用此入口（此处仅针对空账号）
       </p>`,
      '删除空账号',
      { type: 'warning', dangerouslyUseHTMLString: true, confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
  } catch { return }
  try {
    await api.deleteAccount(row.id)
    ElMessage.success(`已删除账号「${row.companyName}」（已移入回收站）`)
    await loadData()
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || e?.message || '删除失败')
  }
}

async function deleteAllHistory(row) {
  if (!row?.id) return
  const days = mergedTasks(row.id).length
  try {
    await ElMessageBox.confirm(
      `<p>确认<b style="color:#dc2626">清空「${row.companyName}」全部查词历史</b>？</p>
       <p style="color:#64748b;font-size:12px;line-height:1.7;margin-top:8px">
         · 涉及 <b>${days}</b> 天的查词记录<br/>
         · 会级联删除：所有查词结果、所有排名分析数据<br/>
         · <b style="color:#b45309">客户账号本身保留</b>，关键词配置保留，可重新发起查词<br/>
         · 此操作<b style="color:#dc2626">不可恢复</b>
       </p>`,
      '清空全部查词历史',
      {
        type: 'error',
        dangerouslyUseHTMLString: true,
        confirmButtonText: '确认清空',
        cancelButtonText: '取消',
      }
    )
  } catch { return }
  try {
    const r = await api.deleteAllSearchHistory(row.id)
    ElMessage.success(`已清空全部历史：${r?.deletedDates ?? days} 天 · ${r?.deletedRows ?? '?'} 条结果`)
    await loadData()
    delete tasksLoading[row.id]
    delete tasksByAccount[row.id]
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || e?.message || '删除失败')
  }
}

function exportAccountSearch(row) {
  if (!row?.id) return
  if (!row.totalSearches) {
    ElMessage.warning('该客户暂无查词记录')
    return
  }
  window.open(api.exportSearchByAccount(row.id), '_blank')
  ElMessage.success('正在导出查词压缩包...')
}

async function startFromList(row) {
  try {
    await ElMessageBox.confirm(`开始对 "${row.companyName}" 执行查词？`, '确认', { type: 'warning' })
  } catch { return }
  try {
    await api.startSearch(row.id, { platforms: row.platforms || [] })
    ElMessage.success('任务已启动')
    router.push(`/dashboard/keyword-search/${row.id}`)
  } catch (e) {
    ElMessage.error(e?.message || '启动失败')
  }
}

/* ============ 创建查词任务 ============ */
const createTaskVisible = ref(false)
const createTaskAccountId = ref(null)
const createTaskPlatforms = ref([])
const createTaskSubmitting = ref(false)

const createTaskAccount = computed(() =>
  accounts.value.find(a => a.id === createTaskAccountId.value) || null
)
const createTaskAccountPlatforms = computed(() => createTaskAccount.value?.platforms || [])
const canSubmitCreateTask = computed(() =>
  !!createTaskAccount.value
  && !createTaskAccount.value.running
  && createTaskPlatforms.value.length > 0
  && (createTaskAccount.value.keywordCount || 0) > 0
)

function openCreateTask() {
  createTaskAccountId.value = null
  createTaskPlatforms.value = []
  createTaskVisible.value = true
}

function onCreateTaskOpen() {
  // noop — reserved for preloading if needed
}

function onCreateTaskAccountChange() {
  createTaskPlatforms.value = [...createTaskAccountPlatforms.value]
}

function goConfigKeywords(acc) {
  if (!acc?.id) return
  createTaskVisible.value = false
  router.push(`/dashboard/accounts?config=${acc.id}`)
}

function toggleAllPlatforms(checked) {
  createTaskPlatforms.value = checked ? [...createTaskAccountPlatforms.value] : []
}

async function submitCreateTask() {
  if (!canSubmitCreateTask.value) return
  const acc = createTaskAccount.value
  if (!acc.keywordCount) {
    ElMessage.warning('该客户尚未配置关键词，无法创建任务')
    return
  }
  createTaskSubmitting.value = true
  try {
    const resp = await api.startSearch(acc.id, { platforms: createTaskPlatforms.value })
    ElMessage.success(resp.overwrite ? `已覆盖「${acc.companyName}」当天查词任务` : `已为「${acc.companyName}」创建查词任务`)
    createTaskVisible.value = false
    router.push(`/dashboard/keyword-search/${acc.id}`)
  } catch (e) {
    ElMessage.error('创建失败：' + (e?.response?.data?.error || e?.message || '未知错误'))
  } finally {
    createTaskSubmitting.value = false
  }
}

/* ============ 临时任务（无需建客户）============ */
const TEMP_PLATFORM_OPTIONS = ['ChatGPT', 'Gemini', 'Google AIO', 'Google AIM', 'Perplexity', 'Copilot']
const tempTaskOpen = ref(false)
const tempSubmitting = ref(false)
const tempForm = reactive({
  brands: [],
  keywordsText: '',
  platforms: ['豆包', 'DeepSeek', '元宝'],
})
const tempKeywordsCount = computed(
  () => (tempForm.keywordsText || '').split(/\n/).map(s => s.trim()).filter(Boolean).length
)
const canSubmitTemp = computed(
  () => tempKeywordsCount.value > 0 && tempForm.platforms.length > 0
)

function openTempTask() {
  tempForm.brands = []
  tempForm.keywordsText = ''
  tempForm.platforms = ['豆包', 'DeepSeek', '元宝']
  tempTaskOpen.value = true
}

async function submitTempTask() {
  if (!canSubmitTemp.value) return
  const keywords = tempForm.keywordsText
    .split(/\n/).map(s => s.trim()).filter(Boolean)
  tempSubmitting.value = true
  try {
    const data = await api.startTempSearch({
      brand: brandsToStorage(tempForm.brands),
      keywords,
      platforms: tempForm.platforms,
    })
    ElMessage.success(`临时任务已启动：${data.companyName || '临时任务'}`)
    tempTaskOpen.value = false
    if (data.accountId) {
      router.push(`/dashboard/keyword-search/${data.accountId}`)
    }
  } catch (e) {
    ElMessage.error('启动失败：' + (e?.response?.data?.error || e?.message || '未知错误'))
  } finally {
    tempSubmitting.value = false
  }
}

/* ============ 重命名(临时任务)============ */
async function renameAccount(row) {
  let name
  try {
    const r = await ElMessageBox.prompt('请输入任务名称', '重命名任务', {
      inputValue: row.companyName || '',
      inputPlaceholder: '例如:品牌名 · 6月通用词',
      confirmButtonText: '保存', cancelButtonText: '取消',
      inputValidator: v => (v && v.trim() ? true : '名称不能为空'),
    })
    name = (r.value || '').trim()
  } catch { return }
  try {
    await api.patchAccount(row.id, { companyName: name })
    row.companyName = name      // 就地更新,免整表刷新
    ElMessage.success('已重命名')
  } catch (e) {
    ElMessage.error('重命名失败:' + (e?.response?.data?.error || e?.message || ''))
  }
}

/* ============ 数据加载 ============ */
async function loadData() {
  loading.value = true
  try {
    const accs = await api.getAccountSummary(isSuperAdmin.value)
    accounts.value = accs || []
  } catch {
    accounts.value = []
  } finally {
    loading.value = false
  }
}

function startAutoRefresh() {
  stopAutoRefresh()
  autoRefreshTimer = setInterval(() => {
    if (document.visibilityState === 'visible' && runningCount.value > 0) loadData()
  }, 30000)
}
function stopAutoRefresh() {
  if (autoRefreshTimer) { clearInterval(autoRefreshTimer); autoRefreshTimer = null }
}

onMounted(async () => {
  await loadData()
  startAutoRefresh()
  restoreExpandedRows()
})
onUnmounted(() => { stopAutoRefresh() })
</script>

<style scoped>
/* ===== 临时任务 dialog ===== */
.temp-task-header {
  display: flex; align-items: center; gap: 12px;
}
.temp-task-header-icon {
  width: 44px; height: 44px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #f59e0b, #ef4444);
  color: #fff;
  box-shadow: 0 8px 18px -4px rgba(245, 158, 11, .45);
}
.temp-task-header-title {
  font-size: 16px; font-weight: 700; color: #0f172a;
}
.temp-task-header-sub {
  margin-top: 3px; font-size: 12.5px; color: #64748b; line-height: 1.5;
}
.temp-task-hint {
  display: flex; align-items: center; gap: 4px;
  margin-top: 6px;
  font-size: 12px; color: #94a3b8;
}
.temp-task-hint strong { color: #f59e0b; font-weight: 700; }

.search-list-page {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* ===== KPI ===== */
.kpi-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.kpi-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 14px 16px;
  cursor: pointer;
  transition: transform .15s, box-shadow .15s, border-color .15s;
  outline: none;
}
.kpi-card:hover,
.kpi-card:focus-visible {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.06);
  border-color: #cbd5e1;
}
.kpi-card.active {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59,130,246,0.15);
}
.kpi-icon {
  width: 36px; height: 36px;
  border-radius: 9px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.kpi-icon-blue { background: #eff6ff; color: #2563eb; }
.kpi-icon-purple { background: #f5f3ff; color: #7c3aed; }
.kpi-icon-green { background: #ecfdf5; color: #059669; }
.kpi-icon-orange { background: #fff7ed; color: #ea580c; }
.kpi-body { flex: 1; min-width: 0; }
.kpi-label { font-size: 11px; color: #94a3b8; margin-bottom: 2px; }
.kpi-val {
  font-size: 22px; font-weight: 800; color: #0f172a;
  line-height: 1.1; letter-spacing: -0.3px;
  font-variant-numeric: tabular-nums;
}
.kpi-sub { font-size: 11px; color: #64748b; margin-top: 3px; }
.kpi-sub-good { color: #16a34a; font-weight: 600; }
.kpi-sub-bad { color: #dc2626; font-weight: 600; }
.kpi-sub-live { color: #ea580c; font-weight: 600; }

/* ===== 面板 ===== */
.panel {
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 14px;
  padding: 18px 22px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}

/* ===== 工具栏 ===== */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
/* 类别 tabs (super_admin 专属) */
.category-tabs {
  display: inline-flex;
  gap: 4px;
  margin-bottom: 14px;
  padding: 4px;
  background: #f1f5f9;
  border-radius: 10px;
}
.cat-tab {
  background: transparent; border: none; cursor: pointer;
  padding: 8px 18px;
  border-radius: 7px;
  font-size: 13px; font-weight: 600;
  color: #64748b;
  display: inline-flex; align-items: center; gap: 8px;
  transition: all .15s;
  font-family: inherit;
}
.cat-tab:hover { color: #0f172a; }
.cat-tab.active {
  background: #fff; color: #0f172a;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08);
}
.cat-tab-ext.active {
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  color: #92400e;
}
.cat-tab-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: #f59e0b;
  box-shadow: 0 0 6px rgba(245, 158, 11, 0.5);
}
.cat-tab-dot-temp { background: #14b8a6; box-shadow: 0 0 6px rgba(20,184,166,.5); }
.cat-tab-temp.active {
  background: linear-gradient(135deg, #ccfbf1, #99f6e4);
  color: #0f766e;
}
.cat-tab-temp.active .cat-count { background: rgba(15,118,110,.15); color: #0f766e; }
.cat-count {
  font-size: 11px;
  padding: 1px 8px;
  background: rgba(0,0,0,.06);
  border-radius: 99px;
  color: #64748b;
}
.cat-tab.active .cat-count { background: rgba(99, 102, 241, .12); color: #4338ca; }
.cat-tab-ext.active .cat-count { background: rgba(146, 64, 14, .15); color: #92400e; }

.tb-del-btn {
  margin-left: 6px;
  font-size: 11px !important;
  padding: 3px 9px !important;
  height: auto !important;
}

.toolbar-tabs {
  display: inline-flex;
  background: #f1f5f9;
  border-radius: 8px;
  padding: 3px;
  gap: 2px;
}
.seg {
  background: transparent;
  border: none;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: background .15s, color .15s, box-shadow .15s;
}
.seg:hover { color: #0f172a; }
.seg.active {
  background: #fff;
  color: #0f172a;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}
.seg-count {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 10px;
  background: rgba(148, 163, 184, 0.15);
  color: #64748b;
  font-weight: 600;
}
.seg.active .seg-count { background: #eff6ff; color: #2563eb; }

.toolbar-actions {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.toolbar-search { width: 240px; }
.toolbar-filter { width: 130px; }

/* ===== 表格 ===== */
.account-table {
  --el-table-border-color: transparent;
  --el-table-header-bg-color: transparent;
  --el-table-row-hover-bg-color: #f8fafc;
  cursor: pointer;
}
.account-table :deep(.el-table__header-wrapper) {
  border-bottom: 1px solid #f1f5f9;
}
.account-table :deep(.el-table__header th) {
  background: transparent !important;
  padding: 10px 0 !important;
  text-transform: none;
}
.account-table :deep(.el-table__body td) {
  border-bottom: 1px solid #f1f5f9 !important;
  padding: 9px 0 !important;
  background: transparent !important;
}
.account-table :deep(.el-table__row:hover > td) {
  background: #f8fafc !important;
}
.account-table :deep(.el-table::before) { display: none; }
.account-table :deep(.el-table__expanded-cell) {
  padding: 0 !important;
  background: #f8fafc;
}

/* 客户单元格 */
.customer-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  padding-right: 8px;
  padding-left: 2px;
}
.ca-name-row {
  display: flex; align-items: center; gap: 7px; min-width: 0;
}
.ca-type-dot {
  width: 7px; height: 7px; border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.8);
}
.ca-dot-paid { background: #22c55e; }
.ca-dot-quote { background: #f59e0b; }
.ca-name {
  font-size: 14px; font-weight: 600; color: #0f172a;
  letter-spacing: -0.1px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  transition: color .15s;
}
.customer-cell:hover .ca-name { color: #2563eb; }
.ca-badge {
  display: inline-flex; align-items: center; gap: 2px;
  font-size: 10px; padding: 1px 6px; border-radius: 4px;
  font-weight: 600; letter-spacing: 0.2px; flex-shrink: 0; white-space: nowrap;
}
.ca-badge-schedule { background: #fef3c7; color: #b45309; }
.ca-meta {
  display: flex; align-items: center; gap: 6px;
  font-size: 11.5px; color: #94a3b8; line-height: 1.3;
  padding-left: 14px;
}
.ca-meta-item {
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.1px;
}
.ca-meta-sep { color: #e2e8f0; }

/* 品牌列 */
.brand-cell {
  display: flex; flex-wrap: nowrap; gap: 4px;
  align-items: center; overflow: hidden;
}
.brand-tag {
  font-size: 12px; padding: 2px 8px; border-radius: 5px;
  background: #eff6ff; color: #1d4ed8;
  font-weight: 500; white-space: nowrap; flex-shrink: 0;
  letter-spacing: 0.1px;
  max-width: 120px; overflow: hidden; text-overflow: ellipsis;
}
.brand-tag-more {
  background: #f1f5f9; color: #64748b; cursor: default;
}

/* 平台列 */
.platforms-cell {
  display: flex; flex-wrap: wrap; gap: 4px;
  align-items: center;
}
.plat-tag {
  font-size: 11px; padding: 2px 8px; border-radius: 5px;
  background: #f1f5f9; color: #475569;
  white-space: nowrap; flex-shrink: 0; font-weight: 500;
}
.plat-tag-more {
  background: #f1f5f9; color: #64748b; cursor: default;
}

/* 今日徽章 */
.today-pill {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 26px; height: 22px; padding: 0 9px;
  font-size: 12px; font-weight: 700;
  background: rgba(16, 185, 129, 0.12);
  color: #059669;
  border-radius: 6px;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.2px;
}
.today-sep { opacity: 0.5; margin: 0 1px; }
.today-rate {
  display: block; font-size: 11px; font-weight: 700; margin-top: 2px;
  font-variant-numeric: tabular-nums;
}

/* 创建任务 — 提示 */
.ct-hint {
  display: flex; align-items: center; gap: 5px;
  font-size: 12px; color: #94a3b8; margin-top: 6px;
}
.ct-hint-warn { color: #d97706; }
.ct-hint-block {
  margin-top: 12px; padding: 10px 12px;
  background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px;
}

/* 最近查词 */
.last-search {
  display: flex; flex-direction: column; gap: 1px;
  white-space: nowrap; font-variant-numeric: tabular-nums;
  line-height: 1.3;
}
.ls-rel {
  font-size: 12.5px; font-weight: 500; color: #334155;
}
.ls-rel.ls-stale { color: #b45309; }
.ls-date {
  font-size: 11px; color: #94a3b8; letter-spacing: 0.1px;
}

.muted {
  font-size: 13px; color: #cbd5e1; letter-spacing: 0.2px;
}
.muted-zero { font-variant-numeric: tabular-nums; }

/* 状态 */
.status-pill {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 10px; border-radius: 10px;
  font-size: 11px; font-weight: 600;
  letter-spacing: 0.3px;
  white-space: nowrap;
}
.status-pill-running {
  background: #eff6ff; color: #1d4ed8;
}
.status-pill-completed { background: #dcfce7; color: #15803d; }
.status-pill-cancelled { background: #f1f5f9; color: #64748b; }
.status-pill-error { background: #fee2e2; color: #b91c1c; }
.status-pill-pending { background: #fef3c7; color: #b45309; }
.status-pill-stale { background: #fff7ed; color: #c2410c; }
.status-pill-failed { background: #fee2e2; color: #b91c1c; }
.status-pct { font-variant-numeric: tabular-nums; opacity: 0.7; }
.live-dot {
  display: inline-block; width: 6px; height: 6px; border-radius: 50%;
  background: #2563eb; animation: pulse 1.4s ease-in-out infinite;
}
@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.3;transform:scale(.7)} }

/* 操作 */
.act-btn {
  display: inline-flex; align-items: center; justify-content: center;
  background: transparent; border: none;
  padding: 5px 10px; font-size: 13px; font-weight: 500;
  cursor: pointer; border-radius: 5px;
  transition: background .15s, color .15s;
  line-height: 1; vertical-align: middle;
}
.act-btn-primary { color: #2563eb; gap: 3px; }
.act-btn-primary:hover { background: #eff6ff; color: #1d4ed8; }
.act-btn-icon {
  width: 28px; height: 28px; padding: 0; color: #94a3b8; margin-left: 4px;
}
.act-btn-icon:hover:not(:disabled) { background: #f1f5f9; color: #0f172a; }
.act-btn-icon:disabled { color: #e2e8f0; cursor: not-allowed; }
.act-btn-danger { color: #dc2626; }
.act-btn-danger:hover:not(:disabled) { background: #fef2f2; color: #b91c1c; }
.act-btn-danger:disabled { color: #fecaca; }
.act-arrow { transition: transform .15s; }
.act-btn-primary:hover .act-arrow { transform: translateX(2px); }

/* 空状态 */
.table-empty {
  padding: 40px 0; text-align: center; color: #94a3b8;
  display: flex; flex-direction: column; align-items: center; gap: 12px;
}
.table-empty p { margin: 0; }

/* 分页 */
.pagination-row {
  display: flex; justify-content: flex-end; padding: 12px 0 2px;
}

/* ===== 展开：任务历史面板 ===== */
.task-panel {
  padding: 14px 18px 18px;
  background: #f8fafc;
  border-top: 1px solid #eef2f7;
}
.task-panel-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 12px;
}
.tph-title {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; color: #475569; font-weight: 600;
}
.tph-count {
  background: #e2e8f0; color: #475569;
  padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: 600;
}
.tph-loading { font-size: 12px; color: #94a3b8; font-weight: 400; }
.tph-actions { display: flex; gap: 8px; }

.task-bar {
  display: flex; align-items: center; gap: 14px;
  padding: 10px 14px; margin-bottom: 8px;
  background: #fff; border-radius: 8px;
  border: 1px solid #e5e9f0;
  cursor: pointer;
  transition: all .15s;
}
.task-bar:last-child { margin-bottom: 0; }
.task-bar:hover {
  border-color: #93c5fd; box-shadow: 0 2px 8px rgba(59, 130, 246, 0.08);
  transform: translateX(2px);
}
.task-bar-running {
  background: linear-gradient(90deg, #eff6ff 0%, #fff 100%);
  border-color: #93c5fd;
}
.task-bar-error { border-left: 3px solid #ef4444; }
.task-bar-cancelled { border-left: 3px solid #94a3b8; }
.task-bar-completed { border-left: 3px solid #10b981; }
.tb-date {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 600; color: #1e293b;
  font-variant-numeric: tabular-nums;
  min-width: 140px;
}
.tb-stat { display: flex; flex-direction: column; gap: 2px; min-width: 70px; }
.tb-lbl { font-size: 11px; color: #94a3b8; }
.tb-val { font-size: 13px; font-weight: 600; color: #0f172a; font-variant-numeric: tabular-nums; }
.tb-val-fail { color: #dc2626; }
.tb-sep { color: #cbd5e1; margin: 0 2px; }
.tb-subcount {
  display: inline-block; padding: 1px 6px; border-radius: 3px;
  background: #fef3c7; color: #b45309; font-size: 11px; margin-left: 6px;
}
.tb-models { display: flex; flex-wrap: wrap; gap: 4px; flex: 1; min-width: 200px; }
.tb-model-chip {
  display: inline-flex; align-items: center; gap: 3px;
  font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: 4px;
}
.tb-model-num { font-variant-numeric: tabular-nums; opacity: .8; }
.tb-model-more {
  font-size: 11px; color: #94a3b8; padding: 2px 6px;
  background: #f1f5f9; border-radius: 4px;
}
.tb-progress { flex: 1; min-width: 120px; }
.tb-retry-btn { margin-left: 4px; }
.tb-status {
  padding: 3px 10px; border-radius: 10px;
  font-size: 11px; font-weight: 600;
}
.tbs-completed { background: #dcfce7; color: #15803d; }
.tbs-running { background: #dbeafe; color: #1d4ed8; }
.tbs-cancelled { background: #f1f5f9; color: #64748b; }
.tbs-error { background: #fee2e2; color: #dc2626; }
.tbs-pending { background: #fef3c7; color: #b45309; }
.tbs-partial { background: #fef3c7; color: #b45309; }
.tbs-stale { background: #fff7ed; color: #c2410c; }
.tbs-failed { background: #fee2e2; color: #b91c1c; }
.tb-arrow { color: #cbd5e1; transition: transform .15s; }
.task-bar:hover .tb-arrow { color: #3b82f6; transform: translateX(3px); }
.task-empty {
  padding: 24px; text-align: center; color: #94a3b8; font-size: 13px;
}
.task-pagination {
  display: flex;
  justify-content: center;
  padding: 10px 0 2px;
}

/* 响应式 */
@media (max-width: 1180px) {
  .kpi-strip { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 768px) {
  .toolbar { flex-direction: column; align-items: stretch; }
  .toolbar-actions { flex-direction: column; align-items: stretch; }
  .toolbar-search, .toolbar-filter { width: 100%; }
  .kpi-strip { grid-template-columns: 1fr; }
}
</style>
