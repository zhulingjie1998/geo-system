<template>
  <div class="home-page">
    <section class="kpi-strip">
      <div class="kpi-card" role="button" tabindex="0" @click="go('/dashboard/accounts')">
        <div class="kpi-icon kpi-icon-blue"><el-icon><User /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-label">客户账号</div>
          <div class="kpi-val">{{ stats.accounts }}</div>
          <div class="kpi-sub">{{ stats.accounts ? `${totalPlatforms} 平台覆盖` : '去添加客户' }}</div>
        </div>
      </div>

      <div class="kpi-card" role="button" tabindex="0" @click="go('/dashboard/keyword-search')">
        <div class="kpi-icon kpi-icon-violet"><el-icon><Search /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-label">关键词总量</div>
          <div class="kpi-val">{{ stats.keywords }}</div>
          <div class="kpi-sub">平均 {{ avgKeywords }} 个/客户</div>
        </div>
      </div>

      <div class="kpi-card" role="button" tabindex="0" @click="go('/dashboard/keyword-search')">
        <div class="kpi-icon kpi-icon-green"><el-icon><TrendCharts /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-label">今日查词</div>
          <div class="kpi-val">{{ today.totalCount || 0 }}</div>
          <div class="kpi-sub">成功率 {{ today.totalSuccessRate ?? 0 }}%</div>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-orange"><el-icon><Loading /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-label">运行中任务</div>
          <div class="kpi-val">{{ stats.runningTasks }}</div>
          <div class="kpi-sub">{{ stats.runningTasks ? '查词进行中' : '当前空闲' }}</div>
        </div>
      </div>
    </section>

    <section v-if="hasNotices" class="alert-strip">
      <div v-for="(a, i) in alerts" :key="'a' + i" class="alert-item" :class="'alert-' + (a.level || 'info')"
           @click="go('/dashboard/' + (a.action || 'accounts'))">
        <el-icon><Warning /></el-icon><span>{{ a.text }}</span>
      </div>
      <div v-if="todos.needSearch && todos.needSearch.count" class="alert-item alert-info"
           @click="go('/dashboard/keyword-search')">
        <el-icon><Clock /></el-icon><span>{{ todos.needSearch.count }} 个客户今日未查词</span>
      </div>
      <div v-if="todos.failedTasks && todos.failedTasks.count" class="alert-item alert-warn"
           @click="go('/dashboard/keyword-search')">
        <el-icon><CircleClose /></el-icon><span>24 小时内 {{ todos.failedTasks.count }} 个查词任务失败</span>
      </div>
    </section>

    <div class="home-grid">
      <section class="panel">
        <div class="panel-head">
          <h3>运行中的查词任务</h3>
          <a v-if="running.length > 0" class="panel-link" @click="go('/dashboard/keyword-search')">全部任务 →</a>
        </div>
        <div v-if="!running.length" class="panel-empty">当前没有运行中的任务</div>
        <div v-for="t in running.slice(0, 3)" :key="t.taskId" class="task-row">
          <div class="task-info">
            <div class="task-name">{{ t.accountName || '—' }}</div>
            <div class="task-meta">{{ t.keyword || '查词中' }} · {{ t.completed }}/{{ t.total }}</div>
          </div>
          <el-progress :percentage="t.progress" :stroke-width="6" style="width:140px" />
        </div>
        <div v-if="running.length > 3" class="panel-footer">
          还有 {{ running.length - 3 }} 个任务在运行
          <a class="panel-link" @click="go('/dashboard/keyword-search')">查看全部 →</a>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head"><h3>近 7 天查词</h3></div>
        <div v-if="!trend.length" class="panel-empty">暂无查词数据</div>
        <div v-else class="trend-bars">
          <div v-for="d in trend" :key="d.date" class="trend-col">
            <el-tooltip :content="`${d.date} · ${d.count} 次`" placement="top" :show-after="200">
              <div class="trend-bar" :style="{ height: barHeight(d.count) }"></div>
            </el-tooltip>
            <div class="trend-day">{{ String(d.date).slice(5) }}</div>
          </div>
        </div>
      </section>
    </div>

    <section class="panel">
      <div class="panel-head">
        <h3>客户概览</h3>
        <a class="panel-link" @click="go('/dashboard/accounts')">全部客户 →</a>
      </div>
      <el-table v-if="recent.length" :data="recent" style="width:100%">
        <el-table-column label="客户" min-width="200">
          <template #default="{ row }">
            <div class="cell-main">{{ row.companyName }}</div>
            <div class="cell-sub">{{ row.companyBrand }}</div>
          </template>
        </el-table-column>
        <el-table-column label="覆盖平台" min-width="170">
          <template #default="{ row }">
            <el-tag v-for="p in row.platforms" :key="p" size="small" class="plat-tag">{{ p }}</el-tag>
            <span v-if="!row.platforms || !row.platforms.length" class="cell-sub">未配置</span>
          </template>
        </el-table-column>
        <el-table-column label="关键词" width="90" align="center" prop="keywordCount" />
        <el-table-column label="累计查词" width="100" align="center" prop="totalSearches" />
        <el-table-column label="今日" width="100" align="center">
          <template #default="{ row }">
            <span v-if="row.todayCount">{{ row.todaySuccess }}/{{ row.todayCount }}</span>
            <span v-else class="cell-sub">—</span>
          </template>
        </el-table-column>
        <el-table-column label="最近查词" min-width="120">
          <template #default="{ row }">
            <span :class="{ 'cell-sub': !row.lastSearchDate }">{{ row.lastSearchDate || '从未查询' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" align="right">
          <template #default="{ row }">
            <a class="cell-link" @click="go('/dashboard/keyword-search/' + row.id)">查词 →</a>
          </template>
        </el-table-column>
      </el-table>
      <div v-else class="panel-empty">还没有客户，<a class="cell-link" @click="go('/dashboard/accounts')">去添加</a></div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { User, Search, TrendCharts, Loading, Warning, Clock, CircleClose } from '@element-plus/icons-vue'
import api from '../api'

const router = useRouter()
const stats = ref({ accounts: 0, keywords: 0, searches: 0, runningTasks: 0 })
const today = ref({})
const running = ref([])
const recent = ref([])
const alerts = ref([])
const trend = ref([])
const todos = ref({})

const totalPlatforms = computed(() => {
  const s = new Set()
  recent.value.forEach(a => (a.platforms || []).forEach(p => s.add(p)))
  return s.size
})
const avgKeywords = computed(() =>
  stats.value.accounts ? Math.round(stats.value.keywords / stats.value.accounts) : 0)
const hasNotices = computed(() =>
  alerts.value.length ||
  (todos.value.needSearch && todos.value.needSearch.count) ||
  (todos.value.failedTasks && todos.value.failedTasks.count))

const maxTrend = computed(() => Math.max(1, ...trend.value.map(d => d.count || 0)))
function barHeight(c) { return Math.max(4, ((c || 0) / maxTrend.value) * 100) + '%' }
function go(path) { router.push(path) }

onMounted(async () => {
  try {
    const data = await api.getHomeOverview()
    stats.value = data.stats || stats.value
    today.value = data.today || {}
    running.value = data.running || []
    recent.value = data.recent || []
    alerts.value = data.alerts || []
    trend.value = data.trend || []
    todos.value = data.todos || {}
  } catch (e) {
    /* 首页聚合失败不阻塞其它模块 */
  }
})
</script>

<style scoped>
.home-page { display: flex; flex-direction: column; gap: 18px; }

.kpi-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(215px, 1fr)); gap: 16px; }
.kpi-card {
  display: flex; align-items: center; gap: 14px; cursor: pointer;
  background: #fff; border: 1px solid #eef1f6; border-radius: 12px; padding: 18px 20px;
  transition: box-shadow .2s ease, transform .12s ease;
}
.kpi-card:hover { box-shadow: 0 8px 24px rgba(15, 23, 42, .07); transform: translateY(-1px); }
.kpi-icon {
  width: 42px; height: 42px; border-radius: 10px; flex: none;
  display: flex; align-items: center; justify-content: center; font-size: 19px;
}
.kpi-icon-blue { background: #eef4ff; color: #3b82f6; }
.kpi-icon-violet { background: #f2eefe; color: #7c5cf6; }
.kpi-icon-green { background: #eafaf1; color: #10b981; }
.kpi-icon-orange { background: #fff3e8; color: #f59e0b; }
.kpi-label { font-size: 12.5px; color: #8a94a6; }
.kpi-val { font-size: 26px; font-weight: 700; line-height: 1.25; color: #0f172a; }
.kpi-sub { font-size: 12px; color: #9aa3b2; }

.alert-strip { display: flex; flex-wrap: wrap; gap: 10px; }
.alert-item {
  display: inline-flex; align-items: center; gap: 6px; cursor: pointer;
  font-size: 13px; padding: 7px 12px; border-radius: 8px; border: 1px solid transparent;
}
.alert-warn { background: #fff7ed; color: #b45309; border-color: #fde8cd; }
.alert-info { background: #eff6ff; color: #1d4ed8; border-color: #dbe7fe; }
.alert-item:hover { filter: brightness(.97); }

.home-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
@media (max-width: 900px) { .home-grid { grid-template-columns: 1fr; } }

.panel { background: #fff; border: 1px solid #eef1f6; border-radius: 12px; padding: 18px 20px; }
.panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.panel-head h3 { font-size: 15px; font-weight: 600; color: #0f172a; }
.panel-link, .cell-link { font-size: 13px; color: #3b82f6; cursor: pointer; }
.panel-link:hover, .cell-link:hover { text-decoration: underline; }
.panel-empty { padding: 26px 0; text-align: center; color: #9aa3b2; font-size: 13px; }

.task-row { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 10px 0; border-top: 1px solid #f4f6fa; }
.task-row:first-of-type { border-top: none; }
.task-name { font-size: 13.5px; font-weight: 600; color: #1f2937; }
.task-meta { font-size: 12px; color: #9aa3b2; }

.panel-footer {
  display: flex; align-items: center; justify-content: space-between;
  padding-top: 12px; margin-top: 8px;
  border-top: 1px dashed #eef1f6;
  font-size: 12.5px; color: #9aa3b2;
}

.trend-bars { display: flex; align-items: flex-end; gap: 8px; height: 130px; }
.trend-col { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%; }
.trend-bar { width: 100%; max-width: 30px; border-radius: 5px 5px 0 0; background: linear-gradient(180deg, #60a5fa, #3b82f6); }
.trend-day { margin-top: 6px; font-size: 11px; color: #9aa3b2; }

.cell-main { font-size: 13.5px; font-weight: 600; color: #1f2937; }
.cell-sub { font-size: 12px; color: #9aa3b2; }
.plat-tag { margin-right: 4px; }
</style>
